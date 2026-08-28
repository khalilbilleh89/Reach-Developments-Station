#!/usr/bin/env bash
#
# Render build command for Reach Developments Station — MVP 1.0.
#
#   Render dashboard -> Settings -> Build Command:  ./scripts/render-build.sh
#
# This script installs dependencies and produces the static frontend. That is
# all it does.
#
# It deliberately does NOT run database migrations, seed data, or call any
# external service. In the legacy deployment, migrations ran during build, so a
# transient database problem failed the whole source build. Migrations now run
# in scripts/render-start.sh, which turns a database outage into a deployment
# readiness failure instead of a build failure.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

echo "==> Python: $(python --version 2>&1)"
echo "==> Node:   $(node --version)"
echo "==> npm:    $(npm --version)"

echo "==> Installing backend production dependencies"
python -m pip install --upgrade pip
python -m pip install --no-cache-dir -r requirements.txt

echo "==> Installing frontend dependencies"
npm ci --prefix frontend

echo "==> Building static frontend export"
npm run build --prefix frontend

if [[ ! -f "frontend/out/index.html" ]]; then
  echo "ERROR: frontend build did not produce frontend/out/index.html" >&2
  exit 1
fi

echo "==> Build complete. No database connection was required."
