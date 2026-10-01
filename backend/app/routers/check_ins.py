"""Proactive check-in router: schedule management and message generation.

The elder configures a check-in schedule (daily or weekly, between 09:00 and
20:59 Hong Kong time). The backend persists the schedule and can generate a
check-in conversation turn on demand or when triggered by a scheduler.

A check-in message is an assistant message in the elder's default conversation
created through the orchestrator, so it benefits from memory retrieval and the
safety node just like a user-initiated turn. The only difference is that the
"trigger" is the check-in schedule rather than the user typing a message.
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import get_current_account, require_elder
from ..models import Account, Conversation, Message
from ..safety_models import CheckInSchedule
from ..schemas import (
    CheckInScheduleCreate,
    CheckInScheduleOut,
    CheckInTriggerOut,
    CheckInTriggerRequest,
)

router = APIRouter(prefix="/check-ins", tags=["check-ins"])

HK = ZoneInfo("Asia/Hong_Kong")

CHECK_IN_TRIGGER_MESSAGE = "（這是一個定時關心訊息）你好，今天過得怎麼樣？有沒有什麼想聊聊的？"


def _schedule_out(schedule: CheckInSchedule) -> CheckInScheduleOut:
    return CheckInScheduleOut(
        id=schedule.id,
        elder_id=schedule.elder_id,
        enabled=schedule.enabled,
        frequency=schedule.frequency,
        check_in_time=schedule.check_in_time,
        weekday=schedule.weekday,
        last_check_in_at=schedule.last_check_in_at,
        created_at=schedule.created_at,
        updated_at=schedule.updated_at,
    )


@router.get("/schedule", response_model=CheckInScheduleOut | None)
def get_schedule(
    account: Account = Depends(require_elder),
    db: Session = Depends(get_db),
) -> CheckInScheduleOut | None:
    schedule = db.scalar(
        select(CheckInSchedule).where(CheckInSchedule.elder_id == account.id)
    )
    return _schedule_out(schedule) if schedule else None


@router.put("/schedule", response_model=CheckInScheduleOut)
def upsert_schedule(
    payload: CheckInScheduleCreate,
    account: Account = Depends(require_elder),
    db: Session = Depends(get_db),
) -> CheckInScheduleOut:
    schedule = db.scalar(
        select(CheckInSchedule).where(CheckInSchedule.elder_id == account.id)
    )
    if schedule is None:
        schedule = CheckInSchedule(
            elder_id=account.id,
            enabled=payload.enabled,
            frequency=payload.frequency,
            check_in_time=payload.check_in_time,
            weekday=payload.weekday,
        )
        db.add(schedule)
    else:
        schedule.enabled = payload.enabled
        schedule.frequency = payload.frequency
        schedule.check_in_time = payload.check_in_time
        schedule.weekday = payload.weekday
    schedule.updated_at = datetime.now(timezone.utc)
    db.commit()
    return _schedule_out(schedule)


@router.post("/trigger", response_model=CheckInTriggerOut)
async def trigger_check_in(
    payload: CheckInTriggerRequest,
    request: Request,
    account: Account = Depends(require_elder),
    db: Session = Depends(get_db),
) -> CheckInTriggerOut:
    """Generate a check-in message in the elder's conversation.

    This creates or reuses a conversation titled "定時關心" (Scheduled check-in),
    then runs the orchestrator with a check-in trigger message. The resulting
    assistant message is persisted as a normal conversation turn.
    """

    # Find or create the check-in conversation.
    if payload.conversation_id:
        conversation = db.get(Conversation, payload.conversation_id)
        if conversation is None or conversation.owner_id != account.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    else:
        conversation = db.scalar(
            select(Conversation).where(
                Conversation.owner_id == account.id,
                Conversation.title == "定時關心",
            )
        )
        if conversation is None:
            conversation = Conversation(owner_id=account.id, title="定時關心")
            db.add(conversation)
            db.commit()
            db.refresh(conversation)

    context: dict = {
        "rolling_summary": conversation.rolling_summary or "",
        "recent_context": list(conversation.recent_context or []),
        "check_in_trigger": True,
    }

    db.rollback()
    reply = await request.app.state.orchestrator.run(context, CHECK_IN_TRIGGER_MESSAGE)

    if reply.mode == "error":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"message": reply.text, "mode": "error"},
        )

    db.rollback()
    from sqlalchemy import func

    max_ordinal = db.scalar(select(func.max(Message.ordinal)).where(Message.conversation_id == conversation.id))
    next_ordinal = int(max_ordinal or 0) + 1

    # The user message is the check-in trigger (system-generated, not typed by the elder).
    trigger_message = Message(
        conversation_id=conversation.id,
        sender_id=account.id,
        role="user",
        content=CHECK_IN_TRIGGER_MESSAGE,
        metadata_json={"check_in_trigger": True},
        ordinal=next_ordinal,
    )
    assistant_message = Message(
        conversation_id=conversation.id,
        sender_id=None,
        role="assistant",
        content=reply.text,
        metadata_json={
            "mode": reply.mode,
            "check_in": True,
        },
        ordinal=next_ordinal + 1,
    )
    db.add_all([trigger_message, assistant_message])

    # Update the schedule's last_checkIn fields.
    schedule = db.scalar(select(CheckInSchedule).where(CheckInSchedule.elder_id == account.id))
    if schedule is not None:
        schedule.last_check_in_at = datetime.now(timezone.utc)
        schedule.last_check_in_message_id = assistant_message.id

    # Refresh the conversation context.
    messages = db.scalars(
        select(Message).where(Message.conversation_id == conversation.id).order_by(Message.ordinal.asc())
    ).all()
    recent = [
        {"role": msg.role, "content": msg.content, "ordinal": msg.ordinal}
        for msg in messages[-12:]
    ]
    conversation.recent_context = recent
    conversation.updated_at = datetime.now(timezone.utc)

    db.commit()

    return CheckInTriggerOut(
        triggered=True,
        conversation_id=conversation.id,
        message_id=assistant_message.id,
        assistant_text=reply.text,
        mode=reply.mode,
    )
