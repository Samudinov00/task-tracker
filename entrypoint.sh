#!/bin/sh
# entrypoint.sh — запускается внутри контейнера перед стартом Uvicorn
set -e

echo "==> [entrypoint] Waiting for database to be ready..."
n=0
until python -c "
import psycopg2, os, sys
try:
    psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        port=int(os.environ.get('DB_PORT', '5432')),
        dbname=os.environ.get('DB_NAME', 'tasktracker'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', ''),
    ).close()
except Exception:
    sys.exit(1)
" 2>/dev/null; do
    n=$((n+1))
    if [ "$n" -ge 30 ]; then
        echo "[entrypoint] Database not available after 30 attempts. Exiting."
        exit 1
    fi
    echo "[entrypoint] Database not ready, retrying in 2s... ($n/30)"
    sleep 2
done
echo "==> [entrypoint] Database is ready."

echo "==> [entrypoint] Running database migrations..."
if ! python -m alembic upgrade head 2>&1; then
    echo "[entrypoint] ERROR: alembic upgrade head failed (see above). Exiting." >&2
    exit 1
fi

echo "==> [entrypoint] Starting Uvicorn..."
exec uvicorn app.main:app \
    --host "0.0.0.0" \
    --port 8000 \
    --workers "${UVICORN_WORKERS:-3}" \
    --log-level "${UVICORN_LOG_LEVEL:-info}" \
    --proxy-headers \
    --forwarded-allow-ips "*"
