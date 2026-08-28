#!/usr/bin/env bash
#
# Render start command for Reach Developments Station — MVP 1.0.
#
#   Render dashboard -> Settings -> Start Command:  ./scripts/render-start.sh
#
# Order matters: the schema is migrated to head before the first request is
# ever accepted. If PostgreSQL is unreachable, this script exits non-zero and
# Render reports a failed deploy — the previous healthy instance keeps serving.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

echo "==> Applying database migrations"
alembic upgrade head

echo "==> Starting Uvicorn on port ${PORT:-8000}"
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}"
