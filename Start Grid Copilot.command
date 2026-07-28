#!/bin/bash
# Double-click this file to start Utility Grid Copilot and open it in your browser.
set -e
cd "$(dirname "$0")"

echo "Utility Grid Copilot — starting..."

if ! docker info > /dev/null 2>&1; then
  echo "Docker isn't running — starting Docker Desktop (this can take a minute the first time)..."
  open -a Docker
  until docker info > /dev/null 2>&1; do
    sleep 2
  done
fi

echo "Starting containers (no-op if already running)..."
docker compose up -d

echo "Waiting for the backend to be ready..."
until curl -sf http://localhost:8000/health > /dev/null 2>&1; do
  sleep 2
done

echo "Ready. Opening http://localhost:3000"
open http://localhost:3000

echo ""
echo "Grid Copilot is running in the background — you can close this window."
echo "It'll keep running until you stop it or restart Docker Desktop."
