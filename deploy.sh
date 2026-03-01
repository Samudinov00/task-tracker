#!/usr/bin/env bash
# deploy.sh — ручное обновление проекта на сервере
#
# Использование:
#   chmod +x deploy.sh
#   ./deploy.sh                    # обновить до latest
#   ./deploy.sh sha-abc1234        # обновить до конкретного тега
#
set -euo pipefail

# ── Конфигурация ──────────────────────────────────────────────────────────────
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE="docker compose -f ${APP_DIR}/docker-compose.yml"
TIMESTAMP="$(date '+%Y-%m-%d %H:%M:%S')"
# Тег образа: первый аргумент или "latest"
IMAGE_TAG="${1:-latest}"

# ── Цвета для вывода ──────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}==> [${TIMESTAMP}] $*${NC}"; }
warn() { echo -e "${YELLOW}[WARN] $*${NC}"; }
die()  { echo -e "${RED}[ERROR] $*${NC}"; exit 1; }

# ── Проверки ──────────────────────────────────────────────────────────────────
[[ -f "${APP_DIR}/.env" ]] || die ".env не найден. Скопируйте .env.example в .env и заполните."
command -v docker &>/dev/null || die "Docker не установлен."
docker info &>/dev/null       || die "Docker не запущен или нет прав."

# ── Деплой ────────────────────────────────────────────────────────────────────
log "Начало деплоя (тег образа: ${IMAGE_TAG})..."

cd "${APP_DIR}"

# 1. Обновляем код из репозитория
log "Pulling latest code from git..."
git pull origin main

# 2. Обновляем переменную образа в .env (если указан конкретный тег)
if [[ "${IMAGE_TAG}" != "latest" ]]; then
    # Извлекаем базовое имя образа из .env (без тега)
    BASE_IMAGE="$(grep '^DOCKER_IMAGE=' .env | cut -d= -f2 | cut -d: -f1)"
    if [[ -n "${BASE_IMAGE}" ]]; then
        sed -i "s|^DOCKER_IMAGE=.*|DOCKER_IMAGE=${BASE_IMAGE}:${IMAGE_TAG}|" .env
        log "DOCKER_IMAGE установлен: ${BASE_IMAGE}:${IMAGE_TAG}"
    fi
fi

# 3. Тянем новые образы из реестра
log "Pulling Docker images..."
${COMPOSE} pull web

# 4. Убеждаемся, что БД запущена и здорова
log "Ensuring database is running..."
${COMPOSE} up -d db
log "Waiting for database to be healthy..."
timeout 60 bash -c "until ${COMPOSE} ps db | grep -q 'healthy'; do sleep 2; done" \
    || die "База данных не стала healthy за 60 секунд."

# 5. Поднимаем новый контейнер приложения
# --no-deps    — не трогать другие сервисы
# --wait       — ждать healthy-статуса нового контейнера
log "Deploying new web container..."
${COMPOSE} up -d --no-deps --wait web

# 6. Перезагружаем nginx (применяем изменения конфига без downtime)
log "Reloading nginx..."
${COMPOSE} exec nginx nginx -s reload

# 7. Удаляем старые образы (экономим место)
log "Pruning unused Docker images..."
docker image prune -f

# ── Итог ──────────────────────────────────────────────────────────────────────
echo ""
log "Деплой завершён успешно!"
echo ""
echo "Статус контейнеров:"
${COMPOSE} ps
echo ""
echo "Последние логи приложения:"
${COMPOSE} logs --tail=20 web
