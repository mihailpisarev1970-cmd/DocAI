# ⚖️ DocAI — Telegram-бот для анализа юридических документов

<div align="center">

**Юрист-нейросеть в Telegram: разбирает договоры и документы за минуту**

Находит скрытые риски · Объясняет сложные пункты · Подсказывает, что исправить

[![Telegram Bot](https://img.shields.io/badge/Telegram-%40clause__bot__bot-2CA5E0?logo=telegram&logoColor=white)](https://t.me/clause_bot_bot)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://python.org)
[![Django](https://img.shields.io/badge/Django-4.2-092E20?logo=django&logoColor=white)](https://djangoproject.com)
[![aiogram](https://img.shields.io/badge/aiogram-3.x-2CA5E0?logo=telegram&logoColor=white)](https://aiogram.dev)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)](https://docker.com)

[![Tests](https://img.shields.io/badge/tests-40%20passed-brightgreen)](#-тестирование)
[![Status](https://img.shields.io/badge/status-production-success)](#-деплой-на-vps)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](#-contributing)

[Возможности](#-возможности) · [Архитектура](#-архитектура) · [Быстрый старт](#-быстрый-старт) · [Деплой](#-деплой-на-vps) · [FAQ](#-faq)

</div>

---

## 🔍 Ключевые слова

`Telegram-бот` · `анализ документов` · `юридические документы` · `договор` ·
`нейросеть` · `искусственный интеллект` · `ИИ-юрист` · `LegalTech` ·
`Python` · `Django` · `aiogram` · `Claude` · `LLM` · `OCR` ·
`Robokassa` · `приём платежей` · `СБП` · `ФЗ-54` · `онлайн-касса` ·
`Docker` · `nginx` · `VPS` · `реферальная программа` ·
`распознавание речи` · `PDF` · `Word` · `чат-бот`

---

## 📖 О проекте

**DocAI** — production-ready Telegram-бот, который анализирует юридические документы с помощью нейросети. Пользователь отправляет фото договора, PDF, Word или голосовое сообщение — и получает структурированный разбор: тип документа, суть, риски, плюсы, что исправить, совет юриста.

Проект включает **полный цикл монетизации**: тарифы, оплату через Robokassa (СБП, карты, электронные кошельки), автоматическую активацию подписок по вебхукам, реферальную программу и админ-панель.

### Кому подойдёт

- 👔 **Юристам** — быстрый первичный разбор входящих документов
- 🏢 **Предпринимателям** — проверка договоров перед подписанием
- 👥 **Физлицам** — понять, что подписываешь, без консультации за 5000 ₽
- 💻 **Разработчикам** — референс интеграции Telegram-бота с Robokassa и AI

---

## ✨ Возможности

### 🤖 Анализ документов

| Тип | Описание |
|---|---|
| 📷 **Фото** | Скан или снимок документа |
| 📄 **PDF** | Многостраничные файлы |
| 📝 **Word** | Файлы `.docx` |
| 💬 **Текст** | Вставить прямо в чат |
| 🎤 **Голос** | Распознавание речи |

### 💳 Монетизация

- **Robokassa** — СБП, банковские карты, электронные кошельки
- **Автоактивация** — по вебхуку за секунды
- **Чеки ФЗ-54** — корректная фискализация
- **Идемпотентность** — защита от двойных начислений
- **Сверка платежей** — поиск «потерянных» оплат

### 👥 Реферальная программа

- **+30 анализов** за каждого оплатившего друга
- Персональная ссылка `t.me/bot?start=ref_<id>`
- Статистика в боте
- Защита от самоприглашения и накрутки

### 🛠 Админ-панель

- **Django Admin** + Jazzmin
- Пользователи, тарифы, лимиты
- Заказы Robokassa со статусами
- Рефералы с бонусами
- Кнопка «Проверить оплату в Robokassa»

### 🔒 Надёжность

| Механизм | Описание |
|---|---|
| **Проверка подписи** | MD5/SHA-256, `hmac.compare_digest` против timing-атак |
| **Сверка суммы** | Оплата 1 ₽ не активирует тариф за 399 ₽ |
| **Идемпотентность** | Повторный вебхук не начисляет дни дважды |
| **Блокировка при расхождении** | Заказ требует ручной проверки в админке |
| **Healthcheck** | Docker следит за живостью контейнера |
| **Логирование** | Ротация логов, структурированный вывод |
| **Path traversal защита** | Статика защищена от `../` атак |


---

## 🏗 Архитектура

```
                    ┌─────────────────┐
                    │    Telegram     │
                    │   (пользователь)│
                    └────────┬────────┘
                             │ polling
                    ┌────────▼────────┐
                    │   aiogram Bot   │
                    │      bot/       │
                    └────────┬────────┘
                             │ HTTP (X-Bot-Api-Key)
                    ┌────────▼────────┐        ┌──────────────┐
                    │  Django REST    │◄───────┤  Robokassa   │
                    │    backend/     │ webhook│  (ResultURL) │
                    └────────┬────────┘        └──────────────┘
                             │
                    ┌────────▼────────┐        ┌──────────────┐
                    │  SQLite /       │        │  AIDostup.ai │
                    │  PostgreSQL     │        │   (Claude)   │
                    └─────────────────┘        └──────────────┘
```

### Компоненты

| Компонент | Технология | Назначение |
|---|---|---|
| **Бот** | aiogram 3.31 | Приём сообщений, отправка в API, UI |
| **Бэкенд** | Django 4.2 + DRF | Бизнес-логика, платежи, пользователи |
| **БД** | SQLite (старт) | Пользователи, заказы, лимиты |
| **AI** | AIDostup (Claude Opus) | Анализ документов, транскрипция |
| **Оплата** | Robokassa | Приём платежей, чеки |
| **Деплой** | Docker + nginx | Контейнер `DocAI`, SSL |

### Структура проекта

```
DocAI/
├── backend/                    # Django REST API
│   ├── api/
│   │   ├── models.py           # User, Plan, RobokassaOrder, ReferralLog
│   │   ├── views.py            # Бизнес-логика, платежи, вебхуки
│   │   ├── robokassa.py        # Подписи, сборка URL, чеки
│   │   ├── payment_checker.py  # Сверка с Robokassa (XML API)
│   │   ├── static_serve.py     # Отдача статики при DEBUG=False
│   │   ├── health.py           # Healthcheck
│   │   ├── admin.py            # Админка с действиями
│   │   ├── tests_robokassa.py  # 22 теста оплаты
│   │   ├── tests_referral.py   # 12 тестов рефералки
│   │   └── tests_reconcile.py  # 6 тестов сверки
│   ├── config/
│   │   ├── settings.py         # Настройки + логирование
│   │   └── settings_test.py    # Изолированные тестовые настройки
│   └── requirements.txt
│
├── bot/                        # Telegram-бот
│   ├── handlers/
│   │   ├── start.py            # /start + разбор ref_
│   │   ├── payments.py         # Выбор тарифа, оплата
│   │   ├── menu_commands.py    # Меню, рефералка
│   │   ├── admin_tools.py      # /check_orders (только админ)
│   │   ├── document.py         # PDF/Word
│   │   ├── photo.py            # Фото
│   │   ├── voice.py            # Голос
│   │   └── text.py             # Текст
│   ├── services/
│   │   ├── ai_service.py       # AIDostup / OpenAI
│   │   └── backend_client.py   # HTTP-клиент к Django
│   ├── keyboards/
│   └── main.py
│
├── deploy/                     # Docker-деплой
│   ├── Dockerfile
│   ├── docker-compose.yml      # Контейнер DocAI
│   ├── entrypoint.sh           # Миграции + запуск
│   ├── supervisord.conf        # gunicorn + бот
│   ├── docai-nginx.conf        # Reverse proxy + SSL
│   ├── docker-deploy.sh        # Автоустановка
│   ├── docker-check.sh         # Проверка (10 пунктов)
│   └── README.md               # Инструкция деплоя
│
├── .gitignore                  # Защита секретов
├── .dockerignore
└── README.md

---

## 🚀 Быстрый старт

### Требования

- **Python** 3.12+
- **Git**
- **Docker** (опционально, для продакшена)
- Токен бота от [@BotFather](https://t.me/BotFather)
- Аккаунт [Robokassa](https://robokassa.ru) (для оплаты)
- Ключ [AIDostup](https://aidostup.site) или OpenAI

### 1. Клонирование

```bash
git clone https://github.com/mihailpisarev1970-cmd/DocAI.git
cd DocAI
```

### 2. Виртуальное окружение

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate
```

### 3. Зависимости

```bash
pip install -r backend/requirements.txt
pip install -r bot/requirements.txt
```

### 4. Переменные окружения

**Бэкенд** — скопируйте шаблон и заполните:

```bash
cp backend/.env.example backend/.env
```

```ini
# backend/.env

# Сгенерируйте: python -c "import secrets;print(secrets.token_urlsafe(50))"
SECRET_KEY=<ваш_секрет>
DEBUG=True
ALLOWED_HOSTS=*

# Сгенерируйте: python -c "import secrets;print(secrets.token_urlsafe(32))"
# Должен совпадать с bot/.env
BOT_API_KEY=<ваш_ключ>

# Robokassa — из ЛК, раздел «Технические настройки»
ROBOKASSA_LOGIN=<логин_магазина>
ROBOKASSA_PASSWORD1=<пароль_1>
ROBOKASSA_PASSWORD2=<пароль_2>
ROBOKASSA_PASSWORD3=<пароль_3>
ROBOKASSA_HASH_ALGORITHM=MD5
ROBOKASSA_TEST_MODE=True

# Фискализация (ФЗ-54)
ROBOKASSA_SEND_RECEIPT=True
ROBOKASSA_RECEIPT_TAX=none      # none | vat0 | vat10 | vat20

# Публичные адреса
BACKEND_PUBLIC_URL=https://ваш-домен.ru
BOT_LINK=https://t.me/ваш_бот

SUBSCRIPTION_PERIOD_DAYS=30

# Рефералка
REFERRAL_BONUS_ANALYSES=30
REFERRAL_WELCOME_BONUS=0
REFERRAL_MAX_BONUSES=0
```

**Бот**:

```bash
cp bot/.env.example bot/.env
```

```ini
# bot/.env

BOT_TOKEN=<токен_от_BotFather>
BACKEND_URL=http://127.0.0.1:8000
BOT_API_KEY=<тот_же_что_в_backend>   # ОБЯЗАТЕЛЬНО совпадает

OPENAI_API_KEY=<ключ_AI>
OPENAI_BASE_URL=https://aidostup.site/v1
OPENAI_MODEL=claude-opus-5-5

# Для команд /check_orders — ваш tg_id
ADMIN_TG_IDS=<ваш_telegram_id>

PAYMENT_POLL_TIMEOUT=180
PAYMENT_POLL_INTERVAL=5
```

> **`BOT_API_KEY` должен быть идентичен** в обоих файлах, иначе бот получит `403`.

### 5. База данных

```bash
cd backend
python manage.py migrate
python manage.py createsuperuser
```

### 6. Тарифы

Создайте в админке (`/admin/`) или через shell:

```bash
python manage.py shell
```

```python
from api.models import Plan, PlanPrice
from decimal import Decimal

for slug, name, limit, price, order in [
    ('free',     'Free',     3,    None,     0),
    ('personal', 'Personal', 30,   '399.00', 1),
    ('business', 'Бизнес',   None, '1490.00', 2),
]:
    plan, _ = Plan.objects.get_or_create(
        slug=slug,
        defaults={'name': name, 'analyses_limit': limit,
                  'is_active': True, 'order': order},
    )
    if price:
        PlanPrice.objects.get_or_create(
            plan=plan, currency='RUB',
            defaults={'amount': Decimal(price)},
        )
```

### 7. Запуск (2 терминала)

**Терминал 1 — Django:**
```bash
cd backend
python manage.py runserver
```

**Терминал 2 — Бот:**
```bash
cd bot
python main.py
```

Проверка: http://127.0.0.1:8000/health/ → `{"status": "ok"}`

---

## 🧪 Тестирование

```bash
cd backend

# Все тесты (40)
python manage.py test api --settings=config.settings_test

# По модулям
python manage.py test api.tests_robokassa --settings=config.settings_test   # 22
python manage.py test api.tests_referral --settings=config.settings_test    # 12
python manage.py test api.tests_reconcile --settings=config.settings_test   # 6
```

### Покрытие

| Модуль | Тестов | Что проверяется |
|---|---|---|
| `tests_robokassa` | 22 | Подписи, чеки, вебхуки, суммы, идемпотентность |
| `tests_referral` | 12 | Привязка реферера, бонусы, самоприглашение |
| `tests_reconcile` | 6 | Сверка платежей, массовая проверка |


---

## 💳 Настройка Robokassa

### 1. Личный кабинет → Технические настройки

| Поле | Значение | Метод |
|---|---|---|
| **Result URL** | `https://ваш-домен/api/payments/robokassa/result/` | **POST** |
| **Success URL** | `https://ваш-домен/api/payments/robokassa/success/` | **GET** |
| **Fail URL** | `https://ваш-домен/api/payments/robokassa/fail/` | **GET** |

Алгоритм: **MD5**. Пароли #1–#3 — из того же окна.

> **Обязательно `https://`** и полный путь. Если Result URL ведёт на корень домена — Robokassa получит 404 и оплата не активируется.

### 2. Как формируются подписи

```
# Ссылка на оплату (Пароль #1)
MerchantLogin:OutSum:InvId:Пароль1[:Shp_order=InvId]

# С чеком ФЗ-54
MerchantLogin:OutSum:InvId:Receipt:Пароль1[:Shp_order=InvId]

# Проверка вебхука (Пароль #2)
OutSum:InvId:Пароль2[:Shp_order=InvId]

# Ответ Robokassa
OK<InvId>
```

### 3. Проверка после оплаты

В ЛК Robokassa → **«Лог уведомлений»**:

```
[OK]  POST https://ваш-домен/api/payments/robokassa/result/ -> 200
      Ответ: OK<InvId>

[ERR] ERROR: bad signature   -> неверный Пароль #2
[ERR] 404                    -> Result URL неверный
```

### 4. Если платёж «потерялся»

```bash
# В боте (только для ADMIN_TG_IDS)
/check_orders              # сверка всех pending за 72 часа
/reconcile 793686596       # сверка конкретного заказа
```

Или в админке: **Заказы Robokassa** → выбрать → **«Проверить оплату в Robokassa»**

---

## 🐳 Деплой на VPS

Подробная инструкция — в [`deploy/README.md`](deploy/README.md).

### Требования

Ubuntu 22.04/24.04, Docker, домен с A-записью на IP сервера.

### Кратко

```bash
# 1. На сервере
mkdir -p /opt/docai && cd /opt/docai

# 2. Загрузить проект
git clone https://github.com/mihailpisarev1970-cmd/DocAI.git .

# 3. Настроить .env
cp backend/.env.example backend/.env
cp bot/.env.example bot/.env
nano backend/.env    # заполнить секреты
nano bot/.env        # BOT_API_KEY должен совпадать

# 4. Деплой
cd deploy
sudo bash docker-deploy.sh
```

Скрипт выполнит:

1. Проверку `.env` и совпадения `BOT_API_KEY`
2. Сборку Docker-образа
3. Запуск контейнера `DocAI`
4. Миграции + статику
5. Настройку nginx
6. Выпуск SSL (Let's Encrypt)

### Проверка

```bash
bash docker-check.sh
```

```
1. Контейнер            [OK] DocAI запущен (healthy)
2. Процессы             [OK] docai-backend, docai-bot RUNNING
3. Healthcheck          [OK] 127.0.0.1:8000/health/ -> 200
4. Порты                [OK] 8000 (localhost), 443 (nginx)
5. HTTPS-эндпоинты      [OK] /health/, /admin/, /api/plans/
6. Вебхук Robokassa     [OK] доступен извне
7. Страницы оплаты      [OK] success, fail -> 200
8. SSL-сертификат       [OK] действителен
9. База данных          [OK] db.sqlite3
10. Ресурсы             [OK] CPU, RAM, Net
```

### Управление

```bash
docker logs -f DocAI                    # логи
docker restart DocAI                    # перезапуск
docker stats DocAI                      # ресурсы
docker exec DocAI supervisorctl -c /etc/supervisor/conf.d/supervisord.conf status

cd /opt/docai/deploy && docker compose down    # остановка
```

### Обновление

```bash
cd /opt/docai
git pull
cd deploy
docker compose up -d --build
```

---

## 🔐 Безопасность

### Что НЕ попадает в репозиторий

`.gitignore` исключает:

```gitignore
.env              # все секреты
.env.*            # .env.production
!.env.example     # кроме шаблонов
*.sqlite3         # база с данными
logs/             # логи
venv/             # окружение
_*.py, _*.sh      # временные скрипты
```

### Переменные окружения

**Никогда не коммитьте:**

| Переменная | Где взять |
|---|---|
| `SECRET_KEY` | `python -c "import secrets;print(secrets.token_urlsafe(50))"` |
| `BOT_API_KEY` | `python -c "import secrets;print(secrets.token_urlsafe(32))"` |
| `BOT_TOKEN` | [@BotFather](https://t.me/BotFather) |
| `OPENAI_API_KEY` | Личный кабинет AIDostup |
| `ROBOKASSA_PASSWORD*` | ЛК Robokassa → Технические настройки |

### Встроенные защиты

- `hmac.compare_digest` для сравнения подписей
- Сверка `OutSum` с ценой тарифа
- Проверка пути в `static_serve` (path traversal)
- `X-Bot-Api-Key` на всех API-эндпоинтах
- `PROTECT` на внешних ключах заказов
- `SECURE_COOKIES`, `CSRF_TRUSTED_ORIGINS` в продакшене


---

## 📡 API Reference

Все эндпоинты требуют заголовок `X-Bot-Api-Key` (кроме `/health/`).

| Метод | Путь | Описание |
|---|---|---|
| `POST` | `/api/users/get-or-create/` | Создать/получить пользователя |
| `GET` | `/api/users/<tg_id>/referrals/` | Статистика рефералов |
| `POST` | `/api/users/<tg_id>/increment-usage/` | Списать анализ |
| `GET` | `/api/plans/` | Список тарифов |
| `POST` | `/api/documents/` | Сохранить документ |
| `POST` | `/api/payments/create/` | Создать заказ, получить ссылку |
| `GET` | `/api/payments/<inv_id>/status/` | Статус заказа |
| `POST` | `/api/payments/<inv_id>/reconcile/` | Сверить с Robokassa |
| `POST` | `/api/payments/reconcile-all/` | Сверить все pending |
| `GET` | `/health/` | Healthcheck (без ключа) |

### Пример

```bash
curl -X POST https://ваш-домен/api/payments/create/ \
  -H "X-Bot-Api-Key: <ваш_ключ>" \
  -H "Content-Type: application/json" \
  -d '{"tg_id": 123456789, "plan": "personal"}'
```

```json
{
  "order_id": 793686596,
  "inv_id": 793686596,
  "amount": "399.00",
  "plan": "personal",
  "is_test": false,
  "confirmation_url": "https://auth.robokassa.ru/Merchant/Index.aspx?..."
}
```

---

## 🛠 Технологии

| Слой | Технология | Версия |
|---|---|---|
| Язык | Python | 3.12 |
| Бот | aiogram | 3.31 |
| Бэкенд | Django | 4.2 |
| API | Django REST Framework | 3.17 |
| Админка | django-jazzmin | 3.0 |
| HTTP-клиент | httpx | 0.28 |
| PDF | PyMuPDF | 1.23+ |
| Word | python-docx | 1.2 |
| Медиа | Pillow, pydub, ffmpeg | — |
| AI | AIDostup API (Claude) | — |
| Оплата | Robokassa | API v2 |
| Деплой | Docker, nginx | — |

---

## 🤝 Contributing

```bash
# 1. Форк
# 2. Ветка
git checkout -b feature/новая-фича

# 3. Изменения + тесты
python manage.py test api --settings=config.settings_test

# 4. Коммит
git commit -m "feat: добавил экспорт документов в PDF"

# 5. Push
git push origin feature/новая-фича

# 6. Pull Request
```

### Стиль коммитов

```
feat:     новая функциональность
fix:      исправление бага
docs:     документация
test:     тесты
refactor: рефакторинг
chore:    служебное
```

---

## 📄 Лицензия

MIT License — см. [LICENSE](LICENSE).

---

## ❓ FAQ

<details>
<summary><b>Оплата прошла, но тариф не активировался</b></summary>

1. В ЛК Robokassa → **«Лог уведомлений»** у операции
2. Если `ERROR: bad signature` — неверный **Пароль #2** в `backend/.env`
3. Если `404` — неправильный **Result URL**
4. Если запросов нет вообще — Result URL не сохранён в ЛК

**Быстрое решение:** в боте `/check_orders` или в админке кнопка «Проверить оплату».

</details>

<details>
<summary><b>Ошибка 29 «Оплата счетов недоступна» при переходе к оплате</b></summary>

Причина — параметры `SuccessUrl2`/`FailUrl2` в ссылке. Robokassa ожидает эти адреса **в личном кабинете**, а не в запросе.

Решение: они уже не передаются в коде (`api/robokassa.py`). Убедитесь, что URL настроены в ЛК.

</details>

<details>
<summary><b>Бот отвечает 403 Invalid API key</b></summary>

`BOT_API_KEY` в `backend/.env` и `bot/.env` **должны совпадать**.

```bash
grep BOT_API_KEY backend/.env bot/.env
```

</details>

<details>
<summary><b>Фискальный чек не выдаётся</b></summary>

В `.env` должно быть:

```ini
ROBOKASSA_SEND_RECEIPT=True
ROBOKASSA_RECEIPT_TAX=none    # для УСН/патента
```

Проверьте, что к магазину подключена онлайн-касса в ЛК Robokassa.

</details>

<details>
<summary><b>Админка открывается без стилей</b></summary>

nginx должен проксировать `/static/`. Проверьте:

```bash
curl -I https://ваш-домен/static/admin/css/base.css
# ожидается: 200
```

Смотрите блок `location /static/` в `deploy/docai-nginx.conf`.

</details>

<details>
<summary><b>Как перейти на PostgreSQL</b></summary>

```python
# backend/config/settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}
```

Добавьте `psycopg2-binary` в `requirements.txt` и сервис `postgres` в `docker-compose.yml`.

</details>

<details>
<summary><b>Как настроить автобэкап</b></summary>

```bash
mkdir -p /opt/backups
crontab -e

# Добавить:
0 3 * * * cp /opt/docai/backend/db.sqlite3 /opt/backups/db-$(date +\%F).sqlite3
```

</details>

---

<div align="center">

**Сделано для тех, кто читает договоры перед подписанием**

[⬆ Наверх](#️-docai--telegram-бот-для-анализа-юридических-документов)

</div>

```
