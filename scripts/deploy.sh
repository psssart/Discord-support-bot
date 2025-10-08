#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/cronbot/app"

sudo -u cronbot bash -lc "
  cd '$APP_DIR' && \
  git fetch --all && \
  git reset --hard origin/main
"

sudo -u cronbot bash -lc "
  cd '$APP_DIR' && \
  uv sync
"

sudo systemctl restart cronbot
# sudo systemctl restart cronbot-health

echo "===> Git reset и зависимости обновлены"
systemctl status cronbot --no-pager -l | head -n 20

# curl -fsS https://cronbot.example.com/healthz || echo "healthcheck failed"
