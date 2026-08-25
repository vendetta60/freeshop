#!/bin/sh
# Migrate, then serve. A fresh clone is one `docker compose up` from working.
set -eu

echo "[entrypoint] applying database migrations..."
alembic upgrade head

if [ "${SEED_ON_START:-false}" = "true" ]; then
  echo "[entrypoint] seeding (tier=${SEED_TIER:-minimal})..."
  python seeds/seed.py --tier "${SEED_TIER:-minimal}"
fi

echo "[entrypoint] starting: $*"
exec "$@"
