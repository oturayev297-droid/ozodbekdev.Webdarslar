# Ishga tushirish qo'llanmasi

## 0. Tuzilma

Repozitoriy ikki MUSTAQIL qismdan iborat:

```
backend/    Django + DRF   ->  Railway  (Root Directory = backend)
frontend/   Next.js        ->  Vercel   (Root Directory = frontend)
```

Backendning hamma narsasi — `.env`, `requirements.txt`, `Procfile`,
`railway.json`, `runtime.txt` — `backend/` ichida. Railway boshqa hech
narsani ko'rmaydi.

**Quyidagi barcha `python manage.py ...` buyruqlari `backend/` ichida
bajariladi.**

## 1. Lokal ishlab chiqish

Backend (birinchi oyna):

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt

cp .env.example .env           # va qiymatlarni to'ldiring
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

`.env` da lokal uchun `DJANGO_DEBUG=True` va `DATABASE_URL=` (bo'sh — SQLite ishlatiladi).

Frontend (ikkinchi oyna):

```bash
cd frontend
npm install
npm run dev                    # http://localhost:3000
```

## 2. Testlarni ishga tushirish

```bash
cd backend
python manage.py test           # hammasi (464 ta)
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

    client_max_body_size 500M;   # panelda video yuklash uchun

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

    # Dars rasmlari (sxemalar) — ochiq.
    # Video yopiq, rasm ochiq: video darsning O'ZI, rasm esa matnning
    # kichik qismi. Bu qator BO'LMASA yozma darslardagi barcha rasmlar
    # 404 beradi — quyidagi "location /media/ { return 404; }" ularni
    # ham to'sib qo'yadi.
    location /media/lesson_images/ {
        alias /var/www/stitch/media/lesson_images/;
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
python manage.py seed_billing --price 100000 --free-lessons 3
```

So'ng **panel → Sozlamalar** dan karta rekvizitlarini kiriting. Har
karta uchun bitta qator: raqam, egasi, banki va izoh. Ilgari bu JSON
matn sifatida Django adminiga qo'lda yozilardi — bitta vergul xatosi
butun ro'yxatni yo'q qilardi.

Raqam saqlashda tekshiriladi (16-19 xona). Kartalar ro'yxati
**butunlay almashtiriladi**: qatorni o'chirib saqlasangiz, o'sha karta
o'quvchiga ko'rinmay qoladi.

Bu rekvizitlar sahifada turmaydi — faqat so'rovi **"Karta berildi"**
holatidagi o'quvchi ko'radi.

### Kunlik vazifa (cron)

Javobsiz to'lov so'rovlarini kuydiradi va 7/3/0 kun qolganda eslatma yuboradi.

```cron
# Har kuni Toshkent vaqti bilan 09:00 da
0 9 * * *  cd /var/www/stitch && /var/www/stitch/venv/bin/python manage.py subscription_daily >> logs/cron.log 2>&1

# Eski login urinishlari yozuvlarini tozalash (jadval cheksiz o'smasin)
30 3 * * * cd /var/www/stitch && /var/www/stitch/venv/bin/python manage.py prune_login_attempts >> logs/cron.log 2>&1

# Paneldan yuborilgan, navbatda qolgan xabarlarni yuborish (12-bo'limga qarang)
*/5 * * * * cd /var/www/stitch && /var/www/stitch/venv/bin/python manage.py send_panel_messages --budget 240 >> logs/cron.log 2>&1

# Ota-onalarga farzandi haqida haftalik hisobot (dushanba ertalab)
0 8 * * 1  cd /var/www/stitch && /var/www/stitch/venv/bin/python manage.py parent_weekly_report >> logs/cron.log 2>&1
```

> Yo'llarda `/var/www/stitch` — bu **backend** papkasi (`.../stitch/backend`),
> chunki `manage.py` o'sha yerda.

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

### Admin ruxsati

Yangi o'quvchi ro'yxatdan o'tganda hisobi YOPIQ bo'ladi va admin
paneldan ruxsat bermaguncha u darslarni ko'rmaydi.

Ruxsat berish: `/panel/oquvchilar/` — kutayotganlar ro'yxat tepasida.
Yangi ro'yxatdan o'tish haqida adminlarga Telegramda xabar keladi
(8-bo'lim sozlangan bo'lsa).

MIGRATSIYA HAQIDA: `core.0021` mavjud BARCHA o'quvchilarga ruxsatni
avtomatik beradi. Yangi qoida faqat bundan keyingi ro'yxatdan
o'tishlarga tegishli — aks holda allaqachon to'lagan o'quvchilar
ertalab turib kirish yopilganini ko'rardi.

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

## 11. Test savollarini generatsiya qilish

`ANTHROPIC_API_KEY` sozlangandan keyin (10-bo'lim) darslardan qoralama
test savollari yozdirish mumkin:

```bash
# Avval ko'rib chiqing — hech narsa saqlanmaydi
python manage.py generate_quizzes --category python --limit 3 --dry-run

# Keyin haqiqiy generatsiya
python manage.py generate_quizzes --category python --limit 10
```

**Natija QORALAMA** — o'quvchi ko'rmaydi. Admin panel → Testlar →
har savolni o'qib chiqing → "Nashr qilish" amali.

### Matn yetarli bo'lishi kerak

Buyruq matni 200 belgidan qisqa darslarni o'tkazib yuboradi va ro'yxatini
ko'rsatadi. Sabab: model faqat berilgan matndan savol yoza oladi, dars
mazmuni esa videoda. Matnsiz generatsiya qilingan savol darsga mos
kelmaydi va o'quvchi ko'rmagan narsasidan imtihon topshiradi.

Video transkriptini fayl sifatida berish:

```
dars_matnlari/
  34.txt    <- 34-dars matni
  35.txt
  36.md
```

```bash
python manage.py generate_quizzes --notes-dir ./dars_matnlari --category python
```

### Xarajat

Har dars bitta so'rov. Tizim ko'rsatmasi keshlanadi. `--limit` bilan
bir yurishdagi darslar sonini cheklang; buyruq oxirida sarflangan
tokenlarni ko'rsatadi.

## 12. Boshqaruv paneli (`/panel/`)

Kundalik ish shu panelda: hisobotlar, to'lovlarni tasdiqlash, dars
joylash, loyihalar, xabar yuborish, kuzatish, ota-onalarni bog'lash va
sozlamalar.

Django'ning standart `/admin/` paneli **o'chirilgan**. Ilgari faqat u
orqali kiritiladigan ma'lumotlar panelga ko'chirildi:

| Ilgari admin'da | Endi panelda |
|---|---|
| Karta rekvizitlari (`AdminSetting`) | Sozlamalar |
| Obuna narxi (`SubscriptionPlan`) | Sozlamalar |
| Bo'limlar (`Category`) | Darsliklar -> Bo'limlar |
| Test savollari (`Question`, `Choice`) | Testlar -> Savollar |
| Ota-ona bog'lanishi | Ota-onalar |
| Loyihalar (`Project`) | Loyihalar |

### Kirish huquqi

Panel `is_staff` talab qiladi. Huquq **har so'rovda** qayta tekshiriladi —
xodimlik olib tashlansa, ochiq seans ham keyingi sahifadayoq yopiladi.

```bash
# Yangi xodim
python manage.py createsuperuser

# Mavjud hisobga huquq berish
python manage.py shell -c "from django.contrib.auth.models import User; u=User.objects.get(username='NOM'); u.is_staff=True; u.save()"

# Huquqni olib tashlash (hisob o'chirilmaydi)
python manage.py shell -c "from django.contrib.auth.models import User; u=User.objects.get(username='NOM'); u.is_staff=False; u.save()"
```

Kirish urinishlari o'quvchi loginidagi bilan **bir xil** cheklovga
bo'ysunadi (15 daqiqada 5 urinish). Qulf paytidagi urinishlar
yozilmaydi, demak muddatni uzaytirmaydi.

Parolni tiklash: `/panel/forgot-password/` — emailga 6 xonali kod, 15
daqiqa amal qiladi. Bu ishlashi uchun SMTP sozlangan bo'lishi kerak
(7-bo'limdagi "Email" qismi), aks holda kod terminalga chiqadi va xodim
uni ololmaydi.

### Xabar yuborish

Faqat **Telegrami ulangan** o'quvchilar oladi. Panel nechta odam
ulanganini va nechtasi ulanmaganini ko'rsatib turadi.

Katta ro'yxat bitta so'rovda yuborilmaydi (gunicorn uzib qo'yadi):
panel ~10 soniya yuboradi, qolgani navbatda qoladi. Navbatni yuqoridagi
cron yopadi:

```bash
python manage.py send_panel_messages            # navbatni tugatish
python manage.py send_panel_messages --dry-run  # faqat ko'rish
python manage.py send_panel_messages --budget 240
```

`--budget` — bir yurishga ajratiladigan soniya. Cron har 5 daqiqada
ishlasa, 240 qo'yilsa oldingi yurish tugamasdan yangisi boshlanmaydi.

Bir odam bitta xabarni **ikki marta olmaydi**: har oluvchi uchun alohida
qator bor va u `(xabar, foydalanuvchi)` bo'yicha unique. Yuborish uzilsa
to'xtagan joyidan davom etadi.

### Hisobot raqamlari nimadan olinadi

Tushum **faqat** `SubscriptionPeriod` dagi `source=PAYMENT` yozuvlaridan.
Bepul berilgan davrlar (`ADMIN_GRANT`, `TRIAL`) tushumga **kirmaydi** va
alohida ko'rsatiladi. Summa to'lov paytida muzlatib yozilgan
`amount_tiyin` dan olinadi — tarif narxi keyin o'zgarsa ham o'tgan
oylarning raqamlari o'zgarmaydi.

Aylanma sanasi — `created_at` (pul kelgan payt), `start_date` emas.
Oylar Asia/Tashkent bo'yicha bo'linadi.

Kutayotgan to'lov so'rovlari **tushum emas** — ular alohida "kutilmoqda"
sifatida ko'rsatiladi.

## 13. Yozma darslar va tayyor AI kursi

Yozma dars uchun serverda alohida sozlama kerak emas — faqat nginx da
rasm papkasi ochiq bo'lsin (5-bo'limdagi `location /media/lesson_images/`).
Bu qator bo'lmasa barcha dars rasmlari 404 beradi.

Tayyor kursni yozish:

```bash
python manage.py seed_ai_course --dry-run   # avval ko'rib chiqing
python manage.py seed_ai_course
python manage.py collectstatic --noinput
```

Buyruq QAYTA ISHGA TUSHIRILISHI XAVFSIZ: darslar `(modul, sarlavha)`
bo'yicha topilib yangilanadi, ikkinchi nusxa yaratilmaydi.
O'quvchilarning o'zlashtirishi va test natijalari saqlanadi.

Testlar QORALAMA holatida tushadi va o'quvchiga ko'rinmaydi. Savollarni
o'qib chiqib `/panel/testlar/` da nashr qilasiz. Darhol nashr qilish
kerak bo'lsa: `--publish-quizzes`.

Sxemalar Pillow bilan chiziladi. Serverda DejaVu shrifti bo'lmasa
buyruq YIQILMAYDI — oddiyroq shrift ishlatiladi. Debian/Ubuntu da
yaxshiroq natija uchun:

```bash
sudo apt install fonts-dejavu-core
```

Rasmlarsiz yozish kerak bo'lsa: `--no-images`.

## 14. Vercel + Railway (frontend/backend alohida)

Bu yo'l ixtiyoriy. Bitta serverdagi nginx + gunicorn sxemasi (5-6 bo'limlar)
ishlashda davom etadi va oddiyroq.

### MAJBURIY SHART: videolar bulutda bo'lishi

Railway'da fayl tizimi **vaqtinchalik** — har deployda o'chadi. Ustiga
nginx yo'q, ya'ni `X-Accel-Redirect` ishlamaydi va Django 5 GB faylni
o'zi uzatishga majbur bo'lardi: bitta tomoshabin bitta worker'ni butun
video davomida band qilib turardi.

Shuning uchun avval videolarni ko'chiring:

```bash
# 1) Cloudflare R2 (yoki S3) da bucket yarating. OCHIQ QILMANG.
# 2) .env ga kalitlarni yozing (VIDEO_STORAGE_*)
python manage.py migrate_videos --dry-run    # avval ko'ring
python manage.py migrate_videos
```

Buyruq lokal fayllarni **o'chirmaydi** va qayta ishga tushirilishi
xavfsiz. O'chirish alohida, ongli qadam: `--delete-local` (u faqat
bulutda fayl borligi va hajmi mos kelgani tasdiqlangach o'chiradi).

Sozlama bo'sh qolsa eski yo'l ishlashda davom etadi.

### Backend — Railway

**Root Directory = `backend`** — buni albatta qo'ying. Aks holda
Railway ildizda `requirements.txt` topa olmay quruvni to'xtatadi.

`backend/` ichida `Procfile`, `railway.json` va `runtime.txt` tayyor.

**Bazani ulash:** Railway'da `+ New` → `Database` → `PostgreSQL`, so'ng
uni backend xizmatiga bog'lang. `DATABASE_URL` **o'zi qo'shiladi** —
qo'lda yozmang. Qo'lda yozilsa, parol almashtirilganda Railway o'z
qiymatini yangilaydi, sizniki eskirib qoladi va deploy bazaga ulana
olmaydi.

Muhit o'zgaruvchilari (Railway → Variables):

```
DJANGO_SECRET_KEY=<yangi tasodifiy kalit>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=<railway-domeningiz>
FRONTEND_URL=https://<vercel-domeningiz>
FRONTEND_ORIGINS=https://<vercel-domeningiz>
VIDEO_STORAGE_BUCKET=...
VIDEO_STORAGE_ENDPOINT=...
VIDEO_STORAGE_ACCESS_KEY=...
VIDEO_STORAGE_SECRET_KEY=...
TELEGRAM_BOT_TOKEN=...
ANTHROPIC_API_KEY=...
EMAIL_HOST_USER=...
EMAIL_HOST_PASSWORD=...
```

`USE_X_ACCEL_REDIRECT` ni **qo'ymang** — Railway'da nginx yo'q.

`FRONTEND_URL` ni ham unutmang: sertifikatdagi QR kod va to'lovdan
keyin qaytish manzili shundan quriladi.

Migratsiya `railway.json` dagi `startCommand` da avtomatik bajariladi —
har deployda `migrate` ishlaydi va faqat undan keyin gunicorn
ko'tariladi. Migratsiya yiqilsa xizmat ishga tushmaydi: yarim
ko'chirilgan baza bilan ishlagandan ko'ra shu yaxshi.

### Frontend — Vercel

1. Loyihani import qiling, **Root Directory** = `frontend`
2. Muhit o'zgaruvchisi: `BACKEND_URL=https://<railway-domeningiz>`
3. Boshqa hech narsa kerak emas — `next.config.mjs` qolganini hal qiladi

### Nima uchun `rewrites`, CORS emas

Frontend `/api/*` so'rovlarini Vercel orqali Railway'ga uzatadi. Bu
xavfsizlik qarori:

- Cookie **birinchi tomon** bo'lib qoladi. Safari va iOS uchinchi tomon
  cookie'larini bloklaydi — to'g'ridan-to'g'ri murojaatda o'sha
  brauzerlarda kirish umuman ishlamasdi.
- Token `localStorage` da saqlanmaydi, ya'ni XSS hisobni o'g'irlay olmaydi.

Agar baribir to'g'ridan-to'g'ri murojaat qilmoqchi bo'lsangiz,
`FRONTEND_ORIGINS` ni to'ldiring — CORS va CSRF sozlamalari shundan
o'qiladi.

### Ikkita nozik joy (ular allaqachon hal qilingan)

**Oxiridagi `/`** — Next.js uni olib tashlaydi, Django talab qiladi.
Ikkalasi `next.config.mjs` da hal qilingan. Busiz har bir POST so'rov
redirectga tushib GET ga aylanardi va kirish ishlamasdi.

**`CSRF_TRUSTED_ORIGINS`** — Django POST so'rovda `Origin` sarlavhasini
tekshiradi. `FRONTEND_ORIGINS` to'ldirilmasa har bir forma
"CSRF Failed: Origin checking failed" bilan rad etiladi.

### Panel va Django admin

Ular **backendda qoladi** va server tomonda render qilinadi:
`https://<railway-domeningiz>/panel/`. Ularni React'ga ko'chirishning
hojati yo'q — ular faqat siz uchun.

## 15. Ortiqcha video fayllar

Panelda video qayta yuklanganda Django eski faylni **o'chirmaydi** —
yangi nom bilan yoniga qo'yadi (`1-dars_Xm098yg.mp4`). Vaqt o'tib bu
fayllar diskni bekorga egallaydi.

```bash
python manage.py prune_orphan_videos            # faqat ko'rsatadi
python manage.py prune_orphan_videos --delete   # o'chiradi (tasdiq so'raydi)
```

Standart holda **hech narsa o'chirilmaydi**. Backup borligiga ishonch
hosil qilmasdan `--delete` ishlatmang — video fayllarni qaytarib
bo'lmaydi.

## 16. Backup

```bash
# Baza
pg_dump -U stitch stitch_db | gzip > backup_$(date +%F).sql.gz

# Media (5 GB — sekin, haftada bir marta yetarli)
rsync -av /var/www/stitch/media/ /backup/media/
```

## 17. Loglar

`logs/django.log` (5 MB dan oshganda avtomatik aylanadi, 5 nusxa saqlanadi).
