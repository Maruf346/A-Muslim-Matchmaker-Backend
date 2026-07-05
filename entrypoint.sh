#!/bin/sh
# ──────────────────────────────────────────────────────────────────────────────
#  AMM API — Container Entrypoint
#
#  Controlled by SERVICE_TYPE environment variable (set in docker-compose.yml):
#    django        → migrate + collectstatic + Daphne (ASGI/WebSocket server)
#    celery_worker → Celery worker
#    celery_beat   → Celery Beat scheduler
# ──────────────────────────────────────────────────────────────────────────────
set -e

echo "════════════════════════════════════════════"
echo "  AMM API — Starting: ${SERVICE_TYPE:-django}"
echo "════════════════════════════════════════════"

# ── Wait for Redis ─────────────────────────────────────────────────────────────
# All services (Django + Celery) need Redis. We block until it responds to PING.
echo "  Waiting for Redis at ${REDIS_HOST}:${REDIS_PORT}..."
until redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" ping 2>/dev/null | grep -q "PONG"; do
    echo "    Redis not ready — retrying in 2s..."
    sleep 2
done
echo "  Redis is ready."

# ── Resolve SERVICE_TYPE ───────────────────────────────────────────────────────
SERVICE_TYPE="${SERVICE_TYPE:-django}"

# ──────────────────────────────────────────────────────────────────────────────
if [ "$SERVICE_TYPE" = "django" ]; then
# ──────────────────────────────────────────────────────────────────────────────

    echo "  Applying database migrations..."
    python manage.py migrate --noinput
    echo "  Migrations complete."

    echo "  Collecting static files..."
    python manage.py collectstatic --noinput --clear
    echo "  Static files collected."

    echo "  Starting Daphne ASGI server on 0.0.0.0:8000..."
    # Daphne serves both HTTP and WebSocket traffic.
    # Nginx (in docker-compose) proxies in front of it.
    exec daphne \
        -b 0.0.0.0 \
        -p 8000 \
        --access-log - \
        --proxy-headers \
        core.asgi:application

# ──────────────────────────────────────────────────────────────────────────────
elif [ "$SERVICE_TYPE" = "celery_worker" ]; then
# ──────────────────────────────────────────────────────────────────────────────

    echo "  Starting Celery Worker..."
    # --pool=prefork is the production default on Linux for better throughput.
    # On Windows/macOS Docker Desktop, use --pool=solo to avoid fork() issues.
    exec celery -A core worker \
        --loglevel=info \
        --pool=prefork \
        --concurrency=4

# ──────────────────────────────────────────────────────────────────────────────
elif [ "$SERVICE_TYPE" = "celery_beat" ]; then
# ──────────────────────────────────────────────────────────────────────────────

    echo "  Starting Celery Beat scheduler..."
    exec celery -A core beat \
        --loglevel=info \
        --scheduler django_celery_beat.schedulers:DatabaseScheduler

# ──────────────────────────────────────────────────────────────────────────────
else
# ──────────────────────────────────────────────────────────────────────────────
    echo "  ERROR: Unknown SERVICE_TYPE='${SERVICE_TYPE}'"
    echo "    Valid values: django | celery_worker | celery_beat"
    exit 1
fi
