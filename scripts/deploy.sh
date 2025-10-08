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
echo 'deploy: OK'
