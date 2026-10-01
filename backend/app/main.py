"""FastAPI application entry point for Anxin Companion."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings
from .db import initialize_database, make_engine, make_session_factory
from .orchestrator import ConversationOrchestrator
from .routers import actions, auth, conversations, family, tasks
from .routers import family_messages
from .routers import memories, stories, resources
from .routers import safety, check_ins, speech
from .routers import community, scam
from .resource_service import seed_resources
from .seed_extras import seed_community_activities, seed_scam_resources


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    if settings.environment == "production" and not settings.auth_secret:
        raise RuntimeError("AUTH_SECRET must be configured when APP_ENV=production")
    engine = make_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        initialize_database(app.state.engine)
        with app.state.session_factory() as db:
            seed_resources(db)
            seed_community_activities(db)
            seed_scam_resources(db)
        yield
        app.state.engine.dispose()

    app = FastAPI(title=settings.app_name, version="0.3.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    app.state.orchestrator = ConversationOrchestrator(settings)

    # Flutter's local development client runs on a different origin. A
    # deployment can place the API behind a stricter gateway policy.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router)
    app.include_router(family.router)
    app.include_router(family_messages.router)
    app.include_router(memories.router)
    app.include_router(stories.router)
    app.include_router(resources.router)
    app.include_router(conversations.router)
    app.include_router(actions.router)
    app.include_router(tasks.router)
    app.include_router(safety.router)
    app.include_router(check_ins.router)
    app.include_router(speech.router)
    app.include_router(community.router)
    app.include_router(scam.router)

    @app.get("/health", tags=["system"])
    def health() -> dict[str, object]:
        adapter = app.state.orchestrator.adapter
        return {
            "status": "ok",
            "mode": adapter.mode,
            "demo_mode": adapter.mode == "deterministic_demo",
            "langgraph": app.state.orchestrator._graph is not None,
            "database": "postgresql" if settings.database_url.startswith("postgres") else "sqlite",
        }

    return app


app = create_app()
