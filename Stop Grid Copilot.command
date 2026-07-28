#!/bin/bash
# Double-click this file to stop Utility Grid Copilot's containers.
cd "$(dirname "$0")"
echo "Stopping Utility Grid Copilot..."
docker compose stop
echo "Stopped. (Data is preserved — double-click Start again anytime.)"
