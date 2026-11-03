# DocAI — деплой в Docker на VPS

**Статус: развёрнуто и работает** на `https://check.pisarev-n8n.ru`

| Параметр | Значение |
|---|---|
| Сервер | 85.137.92.197 (Ubuntu 24.04) |
| Домен | check.pisarev-n8n.ru |
| Контейнер | **DocAI** |
| Проект на сервере | `/opt/docai` |
| Админка | https://check.pisarev-n8n.ru/admin/ (`admin` / `DocAI-Admin-2026`) |

---

## Архитектура

```
Интернет
   │
   ▼
nginx (на хосте, порт 80/443)
   │  проксирует check.pisarev-n8n.ru
   ▼
127.0.0.1:8000
   │
   ▼
┌─────────────────────────────────┐
│  Контейнер DocAI                │
│  ┌───────────────────────────┐  │
│  │ supervisord               │  │
│  │  ├── docai-backend        │  │
│  │  │   gunicorn :8000       │  │
│  │  └── docai-bot            │  │
│  │      aiogram polling      │  │
│  └───────────────────────────┘  │
└─────────────────────────────────┘
```

Один контейнер, два процесса через supervisord. nginx на хосте (не в Docker) —
чтобы не конфликтовать с другими сайтами сервера.

---

## Файлы деплоя

| Файл | Назначение |
|---|---|
| `Dockerfile` | Образ: Python 3.12 + ffmpeg + зависимости |
| `docker-compose.yml` | Контейнер `DocAI`, порт 127.0.0.1:8000, тома |
| `entrypoint.sh` | Миграции, статика, запуск supervisord |
| `supervisord.conf` | Два процесса: gunicorn + бот |
| `docai-nginx.conf` | nginx на хосте для домена |
| `docker-deploy.sh` | Полная установка одной командой |
| `docker-check.sh` | Проверка после деплоя (10 пунктов) |

---

## Команды управления

```bash
# Логи в реальном времени
docker logs -f DocAI

# Статус процессов
docker exec DocAI supervisorctl -c /etc/supervisor/conf.d/supervisord.conf status

# Перезапуск
docker restart DocAI

# Перезапуск только бота
docker exec DocAI supervisorctl -c /etc/supervisor/conf.d/supervisord.conf restart docai-bot

# Перезапуск только бэкенда
docker exec DocAI supervisorctl -c /etc/supervisor/conf.d/supervisord.conf restart docai-backend

# Потребление ресурсов
docker stats DocAI

# Остановка
cd /opt/docai/deploy && docker compose down

# Запуск
cd /opt/docai/deploy && docker compose up -d

# Полная проверка
bash /opt/docai/deploy/docker-check.sh
```

---

## Обновление кода

**С локальной машины (PowerShell):**
```powershell
cd "D:\Программирование\Python\DocAI"
.\.venv\Scripts\python.exe _upload.py        # если есть скрипт
# или вручную через scp
```

**На сервере:**
```bash
cd /opt/docai/deploy
docker compose build && docker compose up -d
```

Миграции применяются автоматически в `entrypoint.sh` при старте.

---

## Настройка Robokassa

Личный кабинет → **Технические настройки**:

| Поле | Значение | Метод |
|---|---|---|
| **Result URL** | `https://check.pisarev-n8n.ru/api/payments/robokassa/result/` | **POST** |
| **Success URL** | `https://check.pisarev-n8n.ru/api/payments/robokassa/success/` | **GET** |
| **Fail URL** | `https://check.pisarev-n8n.ru/api/payments/robokassa/fail/` | **GET** |

- Алгоритм хеша: **MD5**
- MerchantLogin: `gptagent`
- Пароли #1/#2/#3 уже в `/opt/docai/backend/.env`

---

## Конфигурация

Все секреты в двух файлах, монтируются в контейнер read-only:

### `/opt/docai/backend/.env`
```ini
SECRET_KEY=<сгенерируйте сами: python -c "import secrets;print(secrets.token_urlsafe(50))">
DEBUG=False
ALLOWED_HOSTS=check.pisarev-n8n.ru,127.0.0.1,localhost
BOT_API_KEY=<сгенерируйте: python -c "import secrets;print(secrets.token_urlsafe(32))">

ROBOKASSA_LOGIN=gptagent
ROBOKASSA_PASSWORD1=<из личного кабинета Robokassa>
ROBOKASSA_PASSWORD2=<из личного кабинета Robokassa>
ROBOKASSA_PASSWORD3=<из личного кабинета Robokassa>
ROBOKASSA_HASH_ALGORITHM=MD5
ROBOKASSA_TEST_MODE=False

BACKEND_PUBLIC_URL=https://check.pisarev-n8n.ru
BOT_LINK=https://t.me/clause_bot_bot
CSRF_TRUSTED_ORIGINS=https://check.pisarev-n8n.ru
SECURE_COOKIES=True
```

### `/opt/docai/bot/.env`
```ini
BOT_TOKEN=<токен от @BotFather>...
BACKEND_URL=http://127.0.0.1:8000
BOT_API_KEY=<сгенерируйте: python -c "import secrets;print(secrets.token_urlsafe(32))">
OPENAI_API_KEY=<ключ из AIDostup>...
OPENAI_BASE_URL=https://aidostup.site/v1
OPENAI_MODEL=claude-opus-5-5
```

> ⚠️ `BOT_API_KEY` в обоих файлах **обязан совпадать**.

---

## Бэкап

```bash
# База
cp /opt/docai/backend/db.sqlite3 /opt/backups/db-$(date +%F).sqlite3

# Автоматически в 3:00
crontab -e
0 3 * * * cp /opt/docai/backend/db.sqlite3 /opt/backups/db-$(date +\%F).sqlite3
```

---

## Решение проблем

| Симптом | Причина | Решение |
|---|---|---|
| `no such table: api_*` | Не применены миграции | `docker exec -w /app/backend DocAI python manage.py migrate` |
| `403 Invalid API key` | `BOT_API_KEY` различается | Сверить оба `.env` |
| Бот молчит | Не стартовал | `docker logs DocAI \| grep -i bot` |
| Вебхук 404 | nginx не проксирует | `nginx -t && systemctl reload nginx` |
| `неверная подпись` | Не тот Пароль #2 | Проверить `ROBOKASSA_PASSWORD2` |
| `сумма не совпадает` | Цена тарифа изменилась | Проверить `PlanPrice` в админке |
