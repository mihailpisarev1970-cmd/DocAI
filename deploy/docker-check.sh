#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# DocAI — проверка после деплоя (Docker)
# Запуск:  sudo bash docker-check.sh
# ═══════════════════════════════════════════════════════════════════════════
DOMAIN="${DOMAIN:-check.pisarev-n8n.ru}"
CONTAINER="${CONTAINER:-DocAI}"
BASE="https://$DOMAIN"
FAILED=0

pass() { echo -e "  \033[1;32m+\033[0m $*"; }
fail() { echo -e "  \033[1;31mx\033[0m $*"; FAILED=1; }
info() { echo -e "  \033[1;34m.\033[0m $*"; }

echo "==============================================================="
echo " Проверка DocAI (Docker) на $DOMAIN"
echo "==============================================================="

echo ""
echo "1. Контейнер"
if docker ps --format "{{.Names}}" | grep -qx "$CONTAINER"; then
    pass "$CONTAINER запущен"
    docker ps --filter "name=$CONTAINER" --format "    {{.Status}} | {{.Ports}}"
else
    fail "$CONTAINER НЕ запущен"
fi

echo ""
echo "2. Процессы внутри контейнера"
docker exec "$CONTAINER" supervisorctl -c /etc/supervisor/conf.d/supervisord.conf status 2>/dev/null | while read -r line; do
    info "$line"
done || fail "supervisorctl недоступен"

echo ""
echo "3. Healthcheck приложения"
code=$(curl -s -o /dev/null -w "%{http_code}" -m 15 http://127.0.0.1:8000/health/ 2>/dev/null || echo ERR)
if [[ "$code" == "200" ]]; then
    pass "127.0.0.1:8000/health/ -> $code"
    curl -sS http://127.0.0.1:8000/health/ | head -c 200
    echo ""
else
    fail "127.0.0.1:8000/health/ -> $code"
fi

echo ""
echo "4. Порты"
if ss -tln 2>/dev/null | grep -q "127.0.0.1:8000"; then
    pass "порт 8000 слушается (только localhost)"
else
    fail "порт 8000 не слушается"
fi
if ss -tln 2>/dev/null | grep -q ":443 "; then pass "порт 443 (nginx)"; else fail "порт 443"; fi

echo ""
echo "5. HTTPS-эндпоинты"
for pair in "/health/:200" "/admin/:302" "/api/plans/:403"; do
    path="${pair%:*}"
    want="${pair##*:}"
    code=$(curl -s -o /dev/null -w "%{http_code}" -m 15 "$BASE$path" 2>/dev/null || echo ERR)
    if [[ "$code" == "$want" ]]; then
        pass "https://$DOMAIN$path -> $code"
    else
        fail "https://$DOMAIN$path -> $code (ожидалось $want)"
    fi
done

echo ""
echo "6. Вебхук Robokassa"
code=$(curl -s -o /dev/null -w "%{http_code}" -m 15 -X POST "$BASE/api/payments/robokassa/result/" 2>/dev/null || echo ERR)
if [[ "$code" == "400" || "$code" == "403" ]]; then
    pass "ResultURL доступен извне (HTTP $code) - Robokassa достучится"
else
    fail "ResultURL -> $code (ожидалось 400/403)"
fi

echo ""
echo "7. Страницы оплаты"
for p in success fail; do
    code=$(curl -s -o /dev/null -w "%{http_code}" -m 15 "$BASE/api/payments/robokassa/$p/?InvId=0" 2>/dev/null || echo ERR)
    if [[ "$code" == "200" ]]; then pass "$p -> 200"; else fail "$p -> $code"; fi
done

echo ""
echo "8. SSL-сертификат"
expiry=$(echo | timeout 10 openssl s_client -servername "$DOMAIN" -connect "$DOMAIN:443" 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)
if [[ -n "$expiry" ]]; then
    pass "действителен до: $expiry"
else
    fail "не удалось получить сертификат"
fi

echo ""
echo "9. База данных"
if docker exec "$CONTAINER" test -f /app/backend/db.sqlite3 2>/dev/null; then
    size=$(docker exec "$CONTAINER" stat -c %s /app/backend/db.sqlite3 2>/dev/null)
    pass "db.sqlite3 на месте (${size} байт)"
    orders=$(docker exec "$CONTAINER" python -c "import sqlite3;c=sqlite3.connect('/app/backend/db.sqlite3');print(c.execute('SELECT COUNT(*) FROM api_robokassaorder').fetchone()[0])" 2>/dev/null)
    info "заказов Robokassa в БД: ${orders:-?}"
else
    fail "db.sqlite3 не найден в контейнере"
fi

echo ""
echo "10. Ресурсы контейнера"
docker stats --no-stream --format "    CPU {{.CPUPerc}} | RAM {{.MemUsage}} | Net {{.NetIO}}" "$CONTAINER" 2>/dev/null || true

echo ""
echo "==============================================================="
if [[ $FAILED -eq 0 ]]; then
    echo -e "\033[1;32m ВСЁ РАБОТАЕТ - можно тестировать оплату в боте\033[0m"
else
    echo -e "\033[1;31m ЕСТЬ ПРОБЛЕМЫ - смотрите вывод выше\033[0m"
    echo "  Логи: docker logs --tail 100 $CONTAINER"
fi
echo "==============================================================="
