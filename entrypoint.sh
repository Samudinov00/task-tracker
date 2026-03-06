#!/bin/sh
# entrypoint.sh — запускается внутри контейнера перед стартом Uvicorn
set -e

echo "==> [entrypoint] Running database migrations..."
python -m alembic upgrade head

echo "==> [entrypoint] Starting Uvicorn..."
exec uvicorn app.main:app \
    --host "0.0.0.0" \
    --port 8000 \
    --workers "${UVICORN_WORKERS:-3}" \
    --log-level "${UVICORN_LOG_LEVEL:-info}" \
    --proxy-headers \
    --forwarded-allow-ips "*"
