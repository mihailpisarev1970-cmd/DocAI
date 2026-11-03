#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# DocAI — entrypoint контейнера: миграции, статика, запуск supervisord
# ═══════════════════════════════════════════════════════════════════════════
set -e

echo "==========================================================="
echo " DocAI - запуск контейнера"
echo "==========================================================="

cd /app/backend

if [ ! -f /app/backend/.env ]; then
    echo "ОШИБКА: /app/backend/.env не найден"
    exit 1
fi
if [ ! -f /app/bot/.env ]; then
    echo "ОШИБКА: /app/bot/.env не найден"
    exit 1
fi
echo "[OK] конфиги на месте"

echo "-> применение миграций..."
python manage.py migrate --noinput

echo "-> сбор статики..."
python manage.py collectstatic --noinput -v 0

if [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
    echo "-> проверка суперпользователя..."
    python manage.py createsuperuser --noinput 2>/dev/null || echo "   (уже существует)"
fi

echo "[OK] подготовка завершена"
echo "-> запуск gunicorn + бота через supervisord"
echo "==========================================================="

exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
