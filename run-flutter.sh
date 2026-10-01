#!/bin/bash
# Run Anxin Companion Flutter client on Linux
# Usage: ./run-flutter.sh
# Prerequisites: Flutter SDK must be installed (see instructions below)
# Run this from your native Linux terminal AFTER the backend is running

set -e

PROJECT_DIR="/home/pc/.wine/drive_c/users/pc/Documents/Programming/Gen AI Hackathon Project/5-more-minutes-project"

cd "$PROJECT_DIR/app"

API_ORIGIN="${1:-http://127.0.0.1:8000}"

echo "Starting Flutter app (API: $API_ORIGIN)..."
flutter pub get
flutter run --dart-define="API_ORIGIN=$API_ORIGIN"
