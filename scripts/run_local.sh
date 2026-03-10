#!/bin/bash
# Run the application locally for development.
# Usage: ./scripts/run_local.sh

set -e

echo "Starting Reach Developments Station (local development)..."
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
