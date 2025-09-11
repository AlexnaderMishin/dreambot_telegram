# ---- base image ----
FROM python:3.11-slim

# ---- system setup ----
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Если psycopg2 (не binary) — нужны системные зависимости.
# Для psycopg2-binary этого обычно не надо, но оставим "тонкий" набор.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# ---- python deps ----
COPY requirements.txt .
RUN python -m pip install --upgrade pip && \
    pip install -r requirements.txt

# ---- app code ----
COPY . .

# Alembic будет искать конфиг в корне репозитория
ENV ALEMBIC_CONFIG=alembic.ini

# ---- run ----
# 1) Пробуем выполнить миграции (если нечего применять — не падаем)
# 2) Запускаем телеграм-бота
CMD sh -c "alembic upgrade head || true; python -m app.bot.main"