# ═══════════════════════════════════════════════════════════════════════════
# DocAI — образ для backend (Django) + bot (aiogram)
# Один образ, два процесса: gunicorn и бот запускаются через supervisord
# ═══════════════════════════════════════════════════════════════════════════
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Europe/Moscow

# Системные зависимости:
#   ffmpeg        — конвертация голосовых сообщений (pydub)
#   libpq-dev     — на случай перехода на PostgreSQL
#   curl          — healthcheck
#   supervisor    — запуск двух процессов в одном контейнере
#   tzdata        — корректное время
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        supervisor \
        tzdata \
        libjpeg62-turbo \
        zlib1g \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --- Зависимости (отдельным слоем для кэша) ---
COPY backend/requirements.txt /app/backend/requirements.txt
COPY bot/requirements.txt /app/bot/requirements.txt

RUN pip install --upgrade pip \
    && pip install -r /app/backend/requirements.txt \
    && pip install -r /app/bot/requirements.txt

# --- Код приложения ---
COPY backend/ /app/backend/
COPY bot/ /app/bot/
COPY deploy/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY deploy/entrypoint.sh /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh \
    && mkdir -p /app/backend/logs /app/backend/staticfiles /app/data

# --- Пользователь без root ---
RUN useradd --system --create-home --shell /usr/sbin/nologin docai \
    && chown -R docai:docai /app

USER docai

WORKDIR /app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health/ || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
