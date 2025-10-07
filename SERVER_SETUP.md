# Развертка бота на Linux сервере
1) Создаём юзера и каталоги
```
sudo adduser --system --group --home /opt/cronbot cronbot
sudo mkdir -p /opt/cronbot/app /opt/cronbot/.venv /opt/cronbot/run
sudo chown -R cronbot:cronbot /opt/cronbot
```
2) Ставим Python и зависимости
```
sudo apt update
sudo apt install -y python3.12-venv python3.12-dev build-essential
```
```
curl -LsSf https://astral.sh/uv/install.sh | sh
sudo -u cronbot bash -lc '
cd /opt/cronbot/app
git clone <твой-репозиторий> .
uv venv /opt/cronbot/.venv
source /opt/cronbot/.venv/bin/activate
uv pip install -U pip
uv pip install -r <(uv pip compile pyproject.toml --quiet)  # или просто: uv pip install .
'
```
3) Создание .env файла
4) systemd unit (`/etc/systemd/system/cronbot.service`)
```
[Unit]
Description=Discord CronBot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=cronbot
Group=cronbot
WorkingDirectory=/opt/cronbot/app
EnvironmentFile=/opt/cronbot/app/.env
# Environment=TZ=Europe/Tallinn
ExecStart=/opt/cronbot/.venv/bin/python -m src.cronbot.main
Restart=on-failure
RestartSec=3
# Права и безопасность
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
5) Права на SQLite
```
sudo -u cronbot mkdir -p /opt/cronbot/run
sudo -u cronbot bash -lc 'printf "%s\n" \
  "DB_PATH=/opt/cronbot/run/cronbot.sqlite" \
  >> /opt/cronbot/app/.env'

sudo chown -R cronbot:cronbot /opt/cronbot/run
sudo chmod 750 /opt/cronbot/run
sudo -u cronbot touch /opt/cronbot/run/cronbot.sqlite
sudo chmod 660 /opt/cronbot/run/cronbot.sqlite
```
6) Деплой обновлений
```
sudo -u cronbot bash -lc '
cd /opt/cronbot/app
git pull
source /opt/cronbot/.venv/bin/activate
pip install -U .
'
sudo systemctl restart cronbot
```
7) Перезапуск бота
```
sudo systemctl daemon-reload
sudo systemctl restart cronbot
journalctl -u cronbot -n 100 --no-pager
```
## Панель бота
1) systemd-юнит для health-сервера (uvicorn) (`/etc/systemd/system/cronbot-health.service`)
```
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
2) Поставь зависимости и запусти
```
sudo -u cronbot bash -lc '
source /opt/cronbot/.venv/bin/activate
pip install fastapi uvicorn[standard]
'
sudo systemctl daemon-reload
sudo systemctl enable --now cronbot-health
sudo systemctl status cronbot-health
curl -s http://127.0.0.1:8010/healthz
```
3) Nginx: сервер для healthcheck (`/etc/nginx/sites-available/sub.example.com`)
```
server {
    listen 80;
    listen [::]:80;
    server_name sub.example.com;

    location /.well-known/acme-challenge/ {
        root /var/www/letsencrypt;
    }

    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name sub.example.com;

    ssl_certificate     /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;
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

    location / {
        return 404;
    }
}
```
4) Активируй сайт и перезагрузи nginx:
```
sudo ln -s /etc/nginx/sites-available/sub.example.com /etc/nginx/sites-enabled/sub.example.com
sudo nginx -t && sudo systemctl reload nginx
```
