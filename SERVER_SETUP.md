
# Развертывание Discord CronBot на Ubuntu 24.04

Ниже — минимальная и надежная инструкция для продакшен-развертывания бота на отдельном пользователе, с виртуальным окружением, systemd и (опционально) HTTP healthcheck через Nginx.

> Пример команды локального запуска: `uv sync --group dev && python -m src.cronbot.main`  
> На сервере по умолчанию ставим только runtime-зависимости. Раздел с dev-зависимостями — внизу, по желанию.

---

## 1) Предусловия
- Ubuntu 24.04 x64
- Домен для панели/healthcheck, например: `cronbot.example.com`
- Открыты 80/443 (если нужен HTTPS)
- Репозиторий бота (пример): `https://github.com/psssart/Discord-support-bot.git`

## 2) Создать системного пользователя и каталоги
```bash
sudo adduser --system --group --home /opt/cronbot cronbot
sudo mkdir -p /opt/cronbot/app /opt/cronbot/.venv /opt/cronbot/run
sudo chown -R cronbot:cronbot /opt/cronbot
```

## 3) Установить системные пакеты
```bash
sudo apt update
sudo apt install -y python3.12-venv python3.12-dev build-essential git curl
```

## 4) Установить `uv` и зависимости проекта
### Вариант A: только runtime-зависимости (рекомендуется на сервере)
```bash
# установить uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# клонировать проект и установить зависимости
sudo -u cronbot bash -lc '
cd /opt/cronbot/app
git clone https://github.com/psssart/Discord-support-bot.git .
uv venv /opt/cronbot/.venv
source /opt/cronbot/.venv/bin/activate
uv sync
'
```

### Вариант B: с dev-зависимостями (если нужны тесты/линтеры на сервере)
```bash
sudo -u cronbot bash -lc '
cd /opt/cronbot/app
source /opt/cronbot/.venv/bin/activate
uv sync --group dev
'
```

## 5) Конфигурация окружения
Хранить переменные окружения удобнее в `/etc/cronbot/cronbot.env`.

```bash
sudo install -d -m 755 /etc/cronbot
sudo tee /etc/cronbot/cronbot.env >/dev/null <<'EOF'
# Требуется токен бота
DISCORD_TOKEN=PASTE_YOUR_TOKEN_HERE

# Путь к SQLite. Писать будем только сюда.
DB_PATH=/opt/cronbot/run/cronbot.sqlite

# Часовой пояс (опционально)
# TZ=Europe/Tallinn
EOF

sudo chown root:cronbot /etc/cronbot/cronbot.env
sudo chmod 640 /etc/cronbot/cronbot.env
```

Подготовить директорию для БД:
```bash
sudo -u cronbot mkdir -p /opt/cronbot/run
sudo chown -R cronbot:cronbot /opt/cronbot/run
sudo chmod 750 /opt/cronbot/run
```

## 6) systemd unit для бота
`/etc/systemd/system/cronbot.service`:
```ini
[Unit]
Description=Discord CronBot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=cronbot
Group=cronbot
WorkingDirectory=/opt/cronbot/app
EnvironmentFile=/etc/cronbot/cronbot.env
ExecStart=/opt/cronbot/.venv/bin/python -m src.cronbot.main
Restart=on-failure
RestartSec=3

# Безопасность
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true
ReadWritePaths=/opt/cronbot/run

# Логи в journalctl
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Применить и запустить:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now cronbot
sudo systemctl status cronbot --no-pager
journalctl -u cronbot -f
```

## 7) Деплой обновлений
```bash
sudo -u cronbot bash -lc '
cd /opt/cronbot/app
git pull
source /opt/cronbot/.venv/bin/activate
uv sync        # или uv sync --group dev, если вы ставили dev-зависимости
'
sudo systemctl restart cronbot
```

---

# Опционально: HTTP healthcheck и панель на поддомене

Ниже — простой `/healthz` на FastAPI + uvicorn, проксируем через Nginx на `cronbot.example.com`.

## 8) Мини-приложение healthcheck
Создайте `src/cronbot/health.py`:
```python
# src/cronbot/health.py
import os
import sqlite3
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()
DB_PATH = os.getenv("DB_PATH", "/opt/cronbot/run/cronbot.sqlite")

@app.get("/healthz")
def healthz():
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1;")
        cur.fetchone()
        conn.close()
        db_ok = True
    except Exception:
        db_ok = False

    status = "ok" if db_ok else "degraded"
    return JSONResponse({"status": status, "db": db_ok})
```

Поставить зависимости и запустить отдельным сервисом:
```bash
sudo -u cronbot bash -lc '
source /opt/cronbot/.venv/bin/activate
uv pip install fastapi "uvicorn[standard]"
'
```

`/etc/systemd/system/cronbot-health.service`:
```ini
[Unit]
Description=CronBot Health HTTP
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=cronbot
Group=cronbot
WorkingDirectory=/opt/cronbot/app
EnvironmentFile=/etc/cronbot/cronbot.env
ExecStart=/opt/cronbot/.venv/bin/uvicorn src.cronbot.health:app --host 127.0.0.1 --port 8010
Restart=on-failure
RestartSec=2

NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true
ReadWritePaths=/opt/cronbot/run

[Install]
WantedBy=multi-user.target
```

Применить и проверить локально:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now cronbot-health
curl -s http://127.0.0.1:8010/healthz
```

## 9) Сертификат для поддомена
Если у вас отдельный сертификат под `cronbot.example.com`:
```bash
sudo certbot --nginx -d cronbot.example.com
```
Или расширьте существующий сертификат, добавив SAN поддомен (по ситуации).

## 10) Nginx для поддомена `cronbot.example.com`
`/etc/nginx/sites-available/cronbot.example.com`:
```nginx
# HTTP -> HTTPS + ACME
server {
    listen 80;
    listen [::]:80;
    server_name cronbot.example.com;

    location /.well-known/acme-challenge/ {
        root /var/www/letsencrypt;
    }

    return 301 https://$host$request_uri;
}

# HTTPS с проксей на локальный health
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name cronbot.example.com;

    ssl_certificate     /etc/letsencrypt/live/cronbot.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/cronbot.example.com/privkey.pem;
    include             /etc/nginx/snippets/ssl-params.conf;
    ssl_dhparam         /etc/letsencrypt/ssl-dhparams.pem;

    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header Referrer-Policy no-referrer;

    location = /healthz {
        proxy_pass http://127.0.0.1:8010/healthz;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 5s;
        proxy_connect_timeout 3s;
        access_log off;
    }

    # по умолчанию ничего не отдаём
    location / {
        return 404;
    }
}
```

Активировать и перезагрузить nginx:
```bash
sudo ln -s /etc/nginx/sites-available/cronbot.example.com /etc/nginx/sites-enabled/cronbot.example.com
sudo nginx -t && sudo systemctl reload nginx
```

Проверка:
```bash
curl -sS https://cronbot.example.com/healthz
```

---

## 11) Диагностика проблем с БД и правами
- `DB_PATH` указывает на `/opt/cronbot/run/cronbot.sqlite`.
- Каталог `dirname(DB_PATH)` принадлежит `cronbot:cronbot`, права `750`.
- В unit разрешена запись: `ReadWritePaths=/opt/cronbot/run`.
- В логах нет `sqlite3.OperationalError: unable to open database file`.

---

## 12) Полезные команды
```bash
# Логи и статус
journalctl -u cronbot -f
systemctl status cronbot --no-pager

# Быстрый взгляд на таблицы
sudo -u cronbot sqlite3 /opt/cronbot/run/cronbot.sqlite '.tables'

# Перезапуск после обновления
sudo systemctl restart cronbot
```

---

## 13) Примечания по `uv`
- Локально: `uv sync --group dev && python -m src.cronbot.main`
- На сервере: обычно достаточно `uv sync`, чтобы не тянуть dev-инструменты. При необходимости: `uv sync --group dev`.
- Если используете `pyproject.toml` с группами, убедитесь, что прод-зависимости действительно в `default`.

---

# *Авто-деплой на сервер

## 1) Создание пользователя для деплоя на сервере
```bash
sudo adduser --disabled-password --gecos "" deploy
sudo usermod -s /bin/bash deploy
```
## 2) Создаем и настраиваем SSH-ключи:
  * На локальной машине генерируем ssh:
    ```bash
    ssh-keygen -t ed25519 -f deploy_key -C "github-actions"
    ```
  * На сервере создаём папку для ключей:
    ```bash
    sudo mkdir -p /home/deploy/.ssh
    sudo chmod 700 /home/deploy/.ssh
    ```
  * Cоздать `/home/deploy/.ssh/authorized_keys` с содержимым `deploy_key.pub`
    ```bash
    sudo chmod 600 /home/deploy/.ssh/authorized_keys
    sudo chown -R deploy:deploy /home/deploy/.ssh
    ```
  * Создать GitHub Secrets
    * DEPLOY_SSH_KEY — содержимое файла `deploy_key`
    * DEPLOY_HOST — твой хост
    * DEPLOY_PORT — порт SSH, например 22 
    * DEPLOY_USER — deploy
## 3) Разрешим деплоеру выполнять нужные команды без пароля:
  *
    ```bash
    sudo tee /etc/sudoers.d/cronbot-deploy >/dev/null <<'EOF'
    deploy ALL=(cronbot) NOPASSWD: /usr/bin/git, /usr/bin/uv, /usr/bin/bash, /usr/bin/env
    deploy ALL=(root)    NOPASSWD: /bin/systemctl restart cronbot, /bin/systemctl restart cronbot-health
    EOF
    sudo visudo -cf /etc/sudoers.d/cronbot-deploy
    ```
  * Убедиться, что uv установлен системно (чтобы был в PATH у всех):
    ```bash
    sudo apt update
    curl -LsSf https://astral.sh/uv/install.sh | sh
    sudo cp /root/.local/bin/uv /usr/local/bin/
    sudo chmod 755 /usr/local/bin/uv
    uv --version
    ```
