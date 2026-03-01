#!/usr/bin/env bash
# ufw-setup.sh — настройка файрвола UFW на сервере Ubuntu/Debian
#
# Открывает только: SSH (22), HTTP (80), HTTPS (443)
# Всё остальное — запрещено.
#
# Использование (от root или через sudo):
#   chmod +x ufw-setup.sh
#   sudo ./ufw-setup.sh
#
set -euo pipefail

# Проверяем root
[[ "$(id -u)" -eq 0 ]] || { echo "Запустите от root: sudo $0"; exit 1; }

echo "==> Configuring UFW firewall..."

# Сбрасываем все правила (чистая конфигурация)
ufw --force reset

# Политики по умолчанию
ufw default deny incoming   # запретить весь входящий трафик
ufw default allow outgoing  # разрешить весь исходящий

# ── Разрешённые порты ─────────────────────────────────────────────────────────

# SSH — ВАЖНО: добавьте ДО включения UFW, иначе потеряете доступ!
# Если используете нестандартный SSH-порт, замените 22 на ваш порт:
ufw allow 22/tcp comment 'SSH'

# HTTP и HTTPS (Nginx)
ufw allow 80/tcp  comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'

# ── Применяем ─────────────────────────────────────────────────────────────────
ufw --force enable

echo ""
echo "==> UFW status:"
ufw status verbose

echo ""
echo "==> Done. Active rules:"
echo "    - SSH  (22/tcp)   ✓"
echo "    - HTTP (80/tcp)   ✓"
echo "    - HTTPS (443/tcp) ✓"
echo "    - Everything else: DENIED"
