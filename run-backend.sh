#!/bin/bash
# Run Anxin Companion backend on Linux
# Usage: ./run-backend.sh
# Run this from your native Linux terminal (NOT inside WorkBuddy/Bottles)

set -e

PROJECT_DIR="/home/pc/.wine/drive_c/users/pc/Documents/Programming/Gen AI Hackathon Project/5-more-minutes-project"

cd "$PROJECT_DIR"

echo "=== Anxin Companion Backend Startup ==="

# Step 1: Create venv if it doesn't exist
if [ ! -f ".venv/bin/python" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Step 2: Install dependencies if needed
if [ ! -f ".venv/.deps_installed" ] || [ "backend/requirements.lock.txt" -nt ".venv/.deps_installed" ]; then
    echo "Installing backend dependencies..."
    .venv/bin/pip install --upgrade pip
    .venv/bin/pip install -r backend/requirements.lock.txt
    touch .venv/.deps_installed
fi

# Step 3: Set AUTH_SECRET if not already set
if [ -z "$AUTH_SECRET" ]; then
    export AUTH_SECRET=$(.venv/bin/python -c "import secrets; print(secrets.token_urlsafe(48))")
    echo "Generated AUTH_SECRET for this session."
fi

# Step 4: Start the backend
echo "Starting backend on http://127.0.0.1:8000 ..."
echo "API docs at http://127.0.0.1:8000/docs"
echo "Press Ctrl+C to stop."
echo ""

cd backend
exec ../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
