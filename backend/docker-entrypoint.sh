#!/usr/bin/env bash
set -euo pipefail

echo "[entrypoint] Running database migrations..."
alembic upgrade head

if [[ -n "${SUPER_ADMIN_EMAIL:-}" && -n "${SUPER_ADMIN_PASSWORD:-}" ]]; then
  echo "[entrypoint] Ensuring super admin exists..."
  python -m app.scripts.seed_super_admin || echo "[entrypoint] super admin seeding skipped"
fi

echo "[entrypoint] Starting: $*"
exec "$@"
