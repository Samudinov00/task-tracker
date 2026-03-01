#!/bin/sh
# entrypoint.sh — запускается внутри контейнера перед стартом Gunicorn
set -e

echo "==> [entrypoint] Running database migrations..."
python manage.py migrate --noinput

echo "==> [entrypoint] Collecting static files..."
python manage.py collectstatic --noinput --clear

echo "==> [entrypoint] Starting Gunicorn..."
exec gunicorn task_tracker.wsgi:application \
    --bind "0.0.0.0:8000" \
    --workers "${GUNICORN_WORKERS:-3}" \
    --timeout "${GUNICORN_TIMEOUT:-60}" \
    --keep-alive "${GUNICORN_KEEPALIVE:-5}" \
    --access-logfile "-" \
    --error-logfile "-" \
    --log-level "${GUNICORN_LOG_LEVEL:-info}"
