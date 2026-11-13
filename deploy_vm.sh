#!/bin/bash
set -e

DOMAIN_NAME="${1:-kiraayagrid.kirayasaathi.app}"

echo "=========================================="
echo "  KiraayaGrid Automated VM Deployment    "
if [ -n "$DOMAIN_NAME" ]; then
    echo "  Domain / Subdomain: $DOMAIN_NAME"
fi
echo "=========================================="

export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a

# 1. Update system & install dependencies
sudo DEBIAN_FRONTEND=noninteractive apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" python3-pip python3-venv python3-dev libmysqlclient-dev default-libmysqlclient-dev build-essential pkg-config nginx mysql-server git certbot python3-certbot-nginx

# 2. Setup MySQL (Isolated database & user for KiraayaGrid)
sudo systemctl start mysql
sudo systemctl enable mysql
sudo mysql -e "CREATE DATABASE IF NOT EXISTS grahvia CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
sudo mysql -e "CREATE USER IF NOT EXISTS 'kiraaya_user'@'localhost' IDENTIFIED BY 'Kiraaya@2026!Secure';"
sudo mysql -e "GRANT ALL PRIVILEGES ON grahvia.* TO 'kiraaya_user'@'localhost';"
sudo mysql -e "FLUSH PRIVILEGES;"

# 3. Clone or Update Repository
sudo mkdir -p /var/www/kiraayagrid
sudo chown -R $USER:$USER /var/www/kiraayagrid
cd /var/www/kiraayagrid

if [ ! -d ".git" ]; then
    git clone https://github.com/GouravBerwal/KiraayaGrid.git .
else
    git pull origin main
fi

# 4. Virtual environment & Packages (Isolated in /var/www/kiraayagrid/venv)
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 5. Production .env configuration
cat << 'EOF' > .env
DJANGO_SECRET_KEY='django-prod-key-kiraayagrid-2026-production-ultra-secure'
DEBUG=False

DB_ENGINE=django.db.backends.mysql
DB_NAME=grahvia
DB_USER=kiraaya_user
DB_PASSWORD=Kiraaya@2026!Secure
DB_HOST=127.0.0.1
DB_PORT=3306

DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=support.kiraayagrid@gmail.com
EMAIL_HOST_PASSWORD=pggvnerljmbqdscw
DEFAULT_FROM_EMAIL=KiraayaGrid <support.kiraayagrid@gmail.com>

FIREBASE_API_KEY=AIzaSyBY89Vu_As3WzIYSlyTibSDaTHfa3bEwf8
FIREBASE_AUTH_DOMAIN=kiraayagrid.firebaseapp.com
FIREBASE_PROJECT_ID=kiraayagrid
FIREBASE_STORAGE_BUCKET=kiraayagrid.firebasestorage.app
FIREBASE_MESSAGING_SENDER_ID=316544409426
FIREBASE_APP_ID=1:316544409426:web:7f6d1b90297c7945bfe48b
EOF

# 6. Database migrations & Static files collection
python manage.py migrate
python manage.py collectstatic --noinput

# Auto-create superadmin if not exists
python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Grahvia.settings')
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='superadmin').exists():
    User.objects.create_superuser('superadmin', 'support.kiraayagrid@gmail.com', 'Admin@12345')
    print('Superadmin created!')
else:
    print('Superadmin already exists.')
"

# 7. Setup Gunicorn systemd service (Isolated name: kiraayagrid.service)
CURRENT_USER=$(whoami)
sudo bash -c "cat << EOF > /etc/systemd/system/kiraayagrid.service
[Unit]
Description=Gunicorn daemon for KiraayaGrid
After=network.target

[Service]
User=$CURRENT_USER
Group=www-data
WorkingDirectory=/var/www/kiraayagrid
ExecStart=/var/www/kiraayagrid/venv/bin/gunicorn --access-logfile - --workers 3 --bind unix:/var/www/kiraayagrid/kiraayagrid.sock Grahvia.wsgi:application

[Install]
WantedBy=multi-user.target
EOF"

sudo systemctl daemon-reload
sudo systemctl restart kiraayagrid
sudo systemctl enable kiraayagrid

# 8. Setup Nginx Reverse Proxy (DO NOT touch existing sites, strictly route by server_name)
NGINX_SERVER_NAME="${DOMAIN_NAME:-kiraayagrid.local}"

sudo bash -c "cat << EOF > /etc/nginx/sites-available/kiraayagrid
server {
    listen 80;
    server_name $NGINX_SERVER_NAME;

    client_max_body_size 50M;

    location /static/ {
        alias /var/www/kiraayagrid/staticfiles/;
    }

    location /media/ {
        alias /var/www/kiraayagrid/media/;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/var/www/kiraayagrid/kiraayagrid.sock;
    }
}
EOF"

sudo ln -sf /etc/nginx/sites-available/kiraayagrid /etc/nginx/sites-enabled/kiraayagrid
sudo nginx -t
sudo systemctl restart nginx

# 9. Free SSL with Certbot if real domain was passed
if [ -n "$DOMAIN_NAME" ] && [ "$DOMAIN_NAME" != "kiraayagrid.local" ]; then
    echo "Installing free SSL certificate for $DOMAIN_NAME..."
    sudo certbot --nginx -d "$DOMAIN_NAME" --non-interactive --agree-tos -m "gouravberwal003@gmail.com" --redirect || true
fi

echo "=========================================="
echo "  KiraayaGrid Deployment Completed 🚀     "
if [ -n "$DOMAIN_NAME" ]; then
    echo "  Live at: https://$DOMAIN_NAME/          "
else
    echo "  Live with Nginx configured!             "
fi
echo "=========================================="
