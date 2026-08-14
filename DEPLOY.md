# Ishga tushirish qo'llanmasi

## 1. Lokal ishlab chiqish

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt

cp .env.example .env           # va qiymatlarni to'ldiring
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

`.env` da lokal uchun `DJANGO_DEBUG=True` va `DATABASE_URL=` (bo'sh — SQLite ishlatiladi).

## 2. Testlarni ishga tushirish

```bash
python manage.py test core
```

## 3. SQLite → PostgreSQL ko'chirish

```bash
# 1) Mavjud ma'lumotlarni chiqarib olish (SQLite hali faol bo'lganda)
python manage.py dumpdata --natural-foreign --natural-primary \
    -e contenttypes -e auth.Permission -e sessions \
    --indent 2 -o data_backup.json

# 2) PostgreSQL bazasini yaratish
#    psql -U postgres -c "CREATE DATABASE stitch_db;"
#    psql -U postgres -c "CREATE USER stitch WITH PASSWORD 'kuchli-parol';"
#    psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE stitch_db TO stitch;"

# 3) .env da DATABASE_URL ni ko'rsatish
#    DATABASE_URL=postgres://stitch:kuchli-parol@localhost:5432/stitch_db

# 4) Migratsiya va ma'lumotlarni yuklash
python manage.py migrate
python manage.py loaddata data_backup.json
```

## 4. Production sozlamalari

`.env`:

```
DJANGO_SECRET_KEY=<yangi tasodifiy kalit>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=sizning-domen.uz,www.sizning-domen.uz
DATABASE_URL=postgres://stitch:parol@localhost:5432/stitch_db
USE_X_ACCEL_REDIRECT=True
```

`DJANGO_DEBUG=False` bo'lganda avtomatik yoqiladi:
HTTPS redirect, HSTS, secure cookie'lar, `nosniff`, `Referrer-Policy`.

Tekshirish:

```bash
python manage.py check --deploy      # 0 ogohlantirish bo'lishi kerak
python manage.py collectstatic --noinput
gunicorn stitch_backend.wsgi:application --bind 127.0.0.1:8000 --workers 3
```

## 5. nginx konfiguratsiyasi (video himoyasi uchun MUHIM)

Dars videolari **hech qachon** to'g'ridan-to'g'ri `/media/lesson_videos/` orqali
berilmasligi kerak. Django ruxsatni tekshiradi, faylni nginx uzatadi:

```nginx
server {
    listen 443 ssl http2;
    server_name sizning-domen.uz;

    ssl_certificate     /etc/letsencrypt/live/sizning-domen.uz/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/sizning-domen.uz/privkey.pem;

    client_max_body_size 500M;   # admin panelda video yuklash uchun

    # Statik fayllar
    location /static/ {
        alias /var/www/stitch/staticfiles/;
        expires 30d;
        access_log off;
    }

    # Profil rasmlari — ochiq
    location /media/profiles/ {
        alias /var/www/stitch/media/profiles/;
        expires 7d;
    }

    # DIQQAT: dars videolari FAQAT shu internal location orqali.
    # Tashqaridan bu manzilga murojaat qilib bo'lmaydi — faqat Django
    # X-Accel-Redirect sarlavhasi bilan yo'naltirganda ishlaydi.
    location /protected/ {
        internal;
        alias /var/www/stitch/media/;
    }

    # Boshqa /media/ so'rovlarini butunlay bloklash
    location /media/ {
        return 404;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;   # HTTPS aniqlash uchun majburiy
    }
}

server {
    listen 80;
    server_name sizning-domen.uz www.sizning-domen.uz;
    return 301 https://$host$request_uri;
}
```

## 6. systemd xizmati

`/etc/systemd/system/stitch.service`:

```ini
[Unit]
Description=Stitch Django
After=network.target

[Service]
User=www-data
WorkingDirectory=/var/www/stitch
EnvironmentFile=/var/www/stitch/.env
ExecStart=/var/www/stitch/venv/bin/gunicorn stitch_backend.wsgi:application \
    --bind 127.0.0.1:8000 --workers 3 --timeout 120
Restart=always

[Install]
WantedBy=multi-user.target
```

## 7. Backup

```bash
# Baza
pg_dump -U stitch stitch_db | gzip > backup_$(date +%F).sql.gz

# Media (5 GB — sekin, haftada bir marta yetarli)
rsync -av /var/www/stitch/media/ /backup/media/
```

## 8. Loglar

`logs/django.log` (5 MB dan oshganda avtomatik aylanadi, 5 nusxa saqlanadi).
