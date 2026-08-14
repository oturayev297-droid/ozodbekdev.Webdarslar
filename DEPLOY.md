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
python manage.py test           # hammasi
python manage.py test billing   # faqat obuna va to'lov
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

## 7. Obuna tizimini sozlash

Deploydan keyin bir marta:

```bash
# Tarif va bepul darslar
python manage.py seed_billing --price 99000 --free-lessons 3
```

So'ng **admin panel → Admin sozlamalari** dan `subscription.cards` kalitiga
karta rekvizitlarini kiriting. Qiymat — JSON massiv:

```json
[
  {"number": "8600 1234 5678 9012", "holder": "OZODBEK T.", "bank": "Uzcard", "note": "Asosiy"},
  {"number": "9860 1234 5678 9012", "holder": "OZODBEK T.", "bank": "Humo", "note": ""}
]
```

Bu rekvizitlar sahifada turmaydi — faqat so'rovi **"Karta berildi"**
holatidagi o'quvchi ko'radi.

### Kunlik vazifa (cron)

Javobsiz to'lov so'rovlarini kuydiradi va 7/3/0 kun qolganda eslatma yuboradi.

```cron
# Har kuni Toshkent vaqti bilan 09:00 da
0 9 * * *  cd /var/www/stitch && /var/www/stitch/venv/bin/python manage.py subscription_daily >> logs/cron.log 2>&1

# Eski login urinishlari yozuvlarini tozalash (jadval cheksiz o'smasin)
30 3 * * * cd /var/www/stitch && /var/www/stitch/venv/bin/python manage.py prune_login_attempts >> logs/cron.log 2>&1
```

Avval quruq sinab ko'ring: `python manage.py subscription_daily --dry-run`

### Email (parolni tiklash va eslatmalar)

`.env` da `EMAIL_HOST_USER` va `EMAIL_HOST_PASSWORD` bo'sh bo'lsa xatlar
**terminalga** chiqadi — productionda bu parolni tiklashni ishlamas qiladi.

Gmail uchun oddiy hisob paroli **ishlamaydi**: 2FA yoqilgan bo'lishi va
[App password](https://myaccount.google.com/apppasswords) (16 belgi)
yaratilishi shart.

```bash
# Tekshirish
python manage.py shell -c "from django.core.mail import send_mail; send_mail('Sinov','Ishladi',None,['siz@gmail.com'])"
```

## 8. Telegram bot

1. [@BotFather](https://t.me/BotFather) da bot yarating, tokenni oling.
2. `.env` ga yozing:

```
TELEGRAM_BOT_TOKEN=123456789:AAE...
TELEGRAM_BOT_USERNAME=ozodbekweb_bot
TELEGRAM_ADMIN_CHAT_IDS=123456789
TELEGRAM_WEBHOOK_SECRET=uzun-tasodifiy-satr
```

Chat ID ingizni bilish uchun [@userinfobot](https://t.me/userinfobot) ga yozing.

3. Webhook ni ro'yxatdan o'tkazing (HTTPS majburiy):

```bash
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook"   -d "url=https://sizning-domen.uz/obuna/telegram/hook/<TELEGRAM_WEBHOOK_SECRET>/"
```

Manzildagi maxfiy qism busiz har kim bot nomidan soxta `/start` yuborib
begona hisobni o'ziga bog'lab olardi.

Token bo'sh bo'lsa tizim **mock rejimda** ishlaydi: xabarlar faqat logga
yoziladi, to'lov oqimi buzilmaydi.

O'quvchi profil sahifasidan bir martalik havola oladi va bosadi — telefon
raqami so'ralmaydi.

## 9. To'lov tizimlari (Payme / Click)

Kalitlar bo'sh bo'lsa tugmalar ko'rinmaydi va **qo'lda tasdiqlash oqimi
ishlashda davom etadi**. Avtomatik to'lov qo'shimcha, o'rnini bosuvchi emas.

### Birliklar — ENG KO'P XATO QILINADIGAN JOY

| Tizim | Birlik | Misol (300 000 so'm) |
|---|---|---|
| Payme | **tiyin** (butun son) | `30000000` |
| Click | **so'm** (kasrli son) | `300000.00` |

Kodda bu farq bir joyda hal qilingan (`gateway_links.py` va har bir
gateway moduli). Boshqa joyda aylantirish yozmang.

### Payme

`.env`:

```
PAYME_MERCHANT_ID=<kabinetdan>
PAYME_KEY=<kabinetdan, "Kalit" bo'limi>
PAYME_ACCOUNT_FIELD=order_id
```

Payme kabinetida ko'rsatiladigan manzil:

```
https://sizning-domen.uz/obuna/payme/
```

Kabinetda **bitta maydon** sozlanadi — nomi `PAYME_ACCOUNT_FIELD` bilan
aynan bir xil bo'lishi shart (standart `order_id`). Unga bizning to'lov
so'rovimiz raqami yoziladi.

Payme sinov (sandbox) rejimida barcha metodlarni tekshiradi:
`CheckPerformTransaction`, `CreateTransaction`, `PerformTransaction`,
`CancelTransaction`, `CheckTransaction`, `GetStatement`. Hammasi yozilgan.

### Click

`.env`:

```
CLICK_SERVICE_ID=<kabinetdan>
CLICK_MERCHANT_ID=<kabinetdan>
CLICK_SECRET_KEY=<kabinetdan>
```

Click kabinetida ikkita manzil ko'rsatiladi:

```
Prepare:  https://sizning-domen.uz/obuna/click/prepare/
Complete: https://sizning-domen.uz/obuna/click/complete/
```

### Ishga tushirishdan oldin

1. **HTTPS majburiy** — ikkala tizim ham shifrlanmagan manzilni qabul qilmaydi.
2. Avval **sinov rejimida** (sandbox) to'liq oqimni o'tkazing. Kod
   protokolga muvofiq yozilgan va testlar bilan qoplangan, lekin haqiqiy
   kalitlarsiz faqat soxta so'rovlar bilan sinalgan.
3. Sinovda tekshiring: to'lov o'tgach obuna **darhol** ochilishi, takror
   so'rovda obuna **ikki marta uzaymasligi**, noto'g'ri summa **rad
   etilishi**.
4. Admin panel → **To'lov tizimi tranzaksiyalari** da har bir chaqiruv
   ko'rinadi (`raw_request` bilan birga) — nosozlikni shu yerdan qidiring.

### To'lovdan keyin bekor qilish

Payme `CancelTransaction` ni to'lovdan keyin ham yuborishi mumkin (pul
qaytarish). Bunda **obuna davri avtomatik o'chirilmaydi** — u moliyaviy
jurnal va o'zgarmasligi kerak. Adminga Telegram xabari boradi, qarorni
u qabul qiladi.

## 10. AI Mentor (Claude API)

1. [platform.claude.com](https://platform.claude.com) da API kalit oling.
2. `.env` ga yozing:

```
ANTHROPIC_API_KEY=sk-ant-api03-...
ANTHROPIC_MODEL=claude-opus-5
ANTHROPIC_EFFORT=low
```

Kalit bo'sh bo'lsa chat "sozlanmagan" xabarini beradi — sayt buzilmaydi.

### Xarajat

Har savol pul turadi, shuning uchun cheklovlar kodda qat'iy belgilangan
(`core/ai_mentor.py`):

| Nima | Qiymat |
|---|---|
| Daqiqada savol | 5 |
| Kunda savol | 60 |
| Yuboriladigan tarix | oxirgi 6 almashuv |
| Javob uzunligi | 4096 token |

Tizim ko'rsatmasi keshlanadi, ya'ni har so'rovda qayta hisoblanmaydi.
`ANTHROPIC_EFFORT=low` — dasturlash tushunchasini tushuntirish chuqur
fikrlashni talab qilmaydi. Javoblar sifati yetarli bo'lmasa `medium`
qiling.

Admin panel → **AI Mentor savollari** da barcha suhbatlar ko'rinadi —
javob sifatini va suiiste'molni shu yerdan kuzating.

## 11. Ortiqcha video fayllar

Admin panelda video qayta yuklanganda Django eski faylni **o'chirmaydi** —
yangi nom bilan yoniga qo'yadi (`1-dars_Xm098yg.mp4`). Vaqt o'tib bu
fayllar diskni bekorga egallaydi.

```bash
python manage.py prune_orphan_videos            # faqat ko'rsatadi
python manage.py prune_orphan_videos --delete   # o'chiradi (tasdiq so'raydi)
```

Standart holda **hech narsa o'chirilmaydi**. Backup borligiga ishonch
hosil qilmasdan `--delete` ishlatmang — video fayllarni qaytarib
bo'lmaydi.

## 12. Backup

```bash
# Baza
pg_dump -U stitch stitch_db | gzip > backup_$(date +%F).sql.gz

# Media (5 GB — sekin, haftada bir marta yetarli)
rsync -av /var/www/stitch/media/ /backup/media/
```

## 13. Loglar

`logs/django.log` (5 MB dan oshganda avtomatik aylanadi, 5 nusxa saqlanadi).
