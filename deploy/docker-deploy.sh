#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# DocAI — деплой в Docker на VPS (Ubuntu 24.04)
# Запуск: sudo bash docker-deploy.sh   (из папки /opt/docai/deploy)
# Идемпотентен. Контейнер называется DocAI.
# ═══════════════════════════════════════════════════════════════════════════
set -euo pipefail

PROJECT_DIR="/opt/docai"
DOMAIN="check.pisarev-n8n.ru"
EMAIL="admin@${DOMAIN}"
CONTAINER="DocAI"

log()  { echo -e "\n\033[1;36m==> $*\033[0m"; }
ok()   { echo -e "\033[1;32m   + $*\033[0m"; }
warn() { echo -e "\033[1;33m   ! $*\033[0m"; }
err()  { echo -e "\033[1;31m   x $*\033[0m"; }

if [[ $EUID -ne 0 ]]; then
    echo "Запустите от root: sudo bash docker-deploy.sh"
    exit 1
fi

log "Проверка конфигурации"
for f in "$PROJECT_DIR/backend/.env" "$PROJECT_DIR/bot/.env"; do
    if [[ ! -f "$f" ]]; then
        err "Не найден $f"
        exit 1
    fi
    ok "$f"
done

KEY_BE=$(grep -E "^BOT_API_KEY=" "$PROJECT_DIR/backend/.env" | cut -d= -f2- | tr -d " \r")
KEY_BOT=$(grep -E "^BOT_API_KEY=" "$PROJECT_DIR/bot/.env" | cut -d= -f2- | tr -d " \r")
if [[ "$KEY_BE" == "$KEY_BOT" ]]; then
    ok "BOT_API_KEY совпадает в обоих .env"
else
    err "BOT_API_KEY РАЗЛИЧАЕТСЯ! Бот не сможет обращаться к API."
    exit 1
fi

log "Подготовка базы данных"
if [[ ! -f "$PROJECT_DIR/backend/db.sqlite3" ]]; then
    touch "$PROJECT_DIR/backend/db.sqlite3"
    warn "Создан пустой db.sqlite3"
fi
mkdir -p "$PROJECT_DIR/backend/logs"
chmod 666 "$PROJECT_DIR/backend/db.sqlite3"
chmod 777 "$PROJECT_DIR/backend/logs"
ok "права на БД и логи выставлены"

log "Сборка Docker-образа"
cd "$PROJECT_DIR/deploy"
docker compose build --no-cache
ok "образ собран"

log "Запуск контейнера $CONTAINER"
docker compose up -d
sleep 8
ok "контейнер запущен"

log "Статус контейнера"
docker ps --filter "name=$CONTAINER" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "-> последние строки лога:"
docker logs --tail 25 "$CONTAINER" 2>&1 || true

log "Проверка здоровья приложения (до 90 сек)"
HEALTH_OK=0
for i in $(seq 1 18); do
    if curl -fsS http://127.0.0.1:8000/health/ >/dev/null 2>&1; then
        ok "приложение отвечает"
        curl -sS http://127.0.0.1:8000/health/ | head -c 300
        echo ""
        HEALTH_OK=1
        break
    fi
    sleep 5
done
if [[ $HEALTH_OK -eq 0 ]]; then
    err "приложение не отвечает! Смотрите: docker logs $CONTAINER"
fi

log "Настройка nginx для $DOMAIN"
cp "$PROJECT_DIR/deploy/docai-nginx.conf" /etc/nginx/sites-available/docai
ln -sf /etc/nginx/sites-available/docai /etc/nginx/sites-enabled/docai
if nginx -t 2>&1 | grep -q "successful"; then
    systemctl reload nginx
    ok "nginx перезагружен (другие сайты не тронуты)"
else
    err "ошибка конфига nginx:"
    nginx -t
    exit 1
fi

log "SSL-сертификат для $DOMAIN"
if [[ -d "/etc/letsencrypt/live/$DOMAIN" ]]; then
    ok "сертификат уже существует"
else
    if certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --email "$EMAIL" --redirect; then
        ok "сертификат выпущен"
    else
        warn "certbot не смог выпустить сертификат. Запустите вручную:"
        warn "sudo certbot --nginx -d $DOMAIN"
    fi
fi

log "ИТОГ"
echo ""
echo "  Контейнер : $CONTAINER"
docker ps --filter "name=$CONTAINER" --format "  статус   : {{.Status}}"
echo ""
echo "  Проверка эндпоинтов:"
curl -s -o /dev/null -w "    https://$DOMAIN/health/     -> HTTP %{http_code}\n" "https://$DOMAIN/health/" || true
curl -s -o /dev/null -w "    https://$DOMAIN/admin/      -> HTTP %{http_code}\n" "https://$DOMAIN/admin/" || true
curl -s -o /dev/null -w "    https://$DOMAIN/api/plans/  -> HTTP %{http_code}\n" "https://$DOMAIN/api/plans/" || true

echo ""
echo "==============================================================="
echo " Впишите в Robokassa -> Технические настройки:"
echo ""
echo "   Result URL  : https://$DOMAIN/api/payments/robokassa/result/"
echo "   Success URL : https://$DOMAIN/api/payments/robokassa/success/"
echo "   Fail URL    : https://$DOMAIN/api/payments/robokassa/fail/"
echo ""
echo "   Метод Result URL : POST"
echo "   Метод Success URL: GET"
echo "   Метод Fail URL   : GET"
echo "==============================================================="
echo ""
echo " Полезные команды:"
echo "   docker logs -f $CONTAINER"
echo "   docker restart $CONTAINER"
echo "   docker stats $CONTAINER"
echo ""
echo "Готово."
