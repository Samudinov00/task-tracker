# ── Stage 1: builder ──────────────────────────────────────────────────────────
# Собираем Python-зависимости в wheel-архивы, чтобы в production-образе
# не нужны были компиляторы (gcc, libpq-dev и т.д.)
FROM python:3.12-slim AS builder

WORKDIR /app

# Системные зависимости для сборки (только в builder-слое)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Копируем только requirements для максимального кэширования слоёв
COPY requirements.txt .

# Собираем wheels (бинарные пакеты)
RUN pip install --upgrade pip && \
    pip wheel --no-cache-dir --no-deps --wheel-dir /wheels -r requirements.txt


# ── Stage 2: production ───────────────────────────────────────────────────────
# Финальный минимальный образ без компиляторов
FROM python:3.12-slim AS production

# Создаём непривилегированного пользователя ДО копирования файлов
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --no-create-home --shell /bin/sh appuser

WORKDIR /app

# Только runtime-библиотека PostgreSQL (libpq5 вместо libpq-dev)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем wheels из builder-стадии — без pip download
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

# Копируем проект с правильным владельцем
COPY --chown=appuser:appgroup . .

# Создаём директории для статики и медиа
RUN mkdir -p /app/staticfiles /app/media && \
    chown -R appuser:appgroup /app/staticfiles /app/media

# Делаем entrypoint исполняемым
RUN chmod +x /app/entrypoint.sh

# Переключаемся на непривилегированного пользователя
USER appuser

EXPOSE 8000

# entrypoint: migrate + collectstatic + gunicorn
ENTRYPOINT ["/app/entrypoint.sh"]
