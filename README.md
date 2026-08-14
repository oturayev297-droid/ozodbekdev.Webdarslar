# Nexus — Onlayn Ta'lim Platformasi

Python, Django, JavaScript va React o'rgatuvchi video kurslar platformasi.

## Nima bor

- **73 video dars** 4 yo'nalishda (Python 15, Django 13, React 15, JavaScript 30)
- **Obuna tizimi** — qo'lda tasdiqlanadigan to'lov, 1/3/6/12 oy
- **Testlar** — server tomonda tekshiriladigan, natijasi soxtalashtirilmaydigan
- **O'zlashtirish nazorati** — dars tugatish, level tizimi, haftalik faollik
- **Parolni tiklash** — emailga 6 xonali kod
- **Kod muharriri** — brauzerda JavaScript topshiriqlari
- **Admin panel** — kontent, o'quvchilar va to'lovlarni boshqarish

## Tez boshlash

```bash
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Batafsil: [DEPLOY.md](DEPLOY.md)

## Loyiha tuzilishi

```
core/                  kontent va autentifikatsiya
  models.py            Category -> Module -> Lesson -> Quiz -> Question -> Choice
  views.py             sahifalar va API endpointlari
  password_reset.py    6 xonali kod bilan parol tiklash
  admin.py             kontent admin paneli
billing/               obuna va to'lov
  models.py            Tarif, Obuna, Davr jurnali, To'lov so'rovi
  dates.py             Toshkent vaqti bo'yicha sana hisobi
  services.py          obunani uzaytirish (YAGONA yo'l) va holat
  payment_requests.py  to'lov so'rovi oqimi
  gating.py            kontent darvozasi (bepul dars / obuna)
  admin.py             to'lovlarni ko'rib chiqish paneli
stitch_backend/        Django proyekt sozlamalari
templates/             HTML shablonlar (Tailwind CDN)
media/lesson_videos/   dars videolari (git ga tushmaydi, ~5 GB)
```

## Obuna tizimi

To'lov **qo'lda** tasdiqlanadi (Click/Payme keyingi bosqichda):

```
o'quvchi muddat tanlaydi    -> REQUESTED
admin kartani beradi        -> CARD_ISSUED       (karta shundan keyingina ko'rinadi)
o'quvchi "chekni yubordim"  -> RECEIPT_UPLOADED  (kutish rejimi yoqiladi)
admin tasdiqlaydi           -> CONFIRMED         (obuna uzayadi)
admin rad etadi             -> REJECTED          (kutish darhol tugaydi)
javobsiz qoladi             -> EXPIRED
```

Sozlash:

```bash
python manage.py seed_billing --price 99000 --free-lessons 3
```

So'ng admin panel -> **Admin sozlamalari** -> `subscription.cards` ga karta
rekvizitlarini kiriting (JSON massiv), aks holda o'quvchi to'lay olmaydi.

Kunlik vazifalar (cron): so'rovlarni kuydirish va 7/3/0 kunlik eslatmalar.

```bash
python manage.py subscription_daily
```

## Muhim qoidalar

Bularni buzish pul yoki kontent yo'qotadi. O'zgartirishdan oldin
`python manage.py test` ni ishga tushiring:

1. **Test javoblari HTML ga chiqmaydi.** `is_correct` shablonlarga hech qachon
   berilmaydi. Ball faqat `submit_quiz` da, serverda hisoblanadi.
2. **Video faqat `/lessons/<id>/video/` orqali.** `/media/lesson_videos/` marshruti
   ataylab yopilgan (nginx da ham `return 404`).
3. **Kontent sahifalari `@login_required`.** Faqat `/`, `/login/`, `/register/`
   va parol tiklash sahifalari ochiq.
4. **Challenge yechimi HTML da turmaydi** — `/editor/<id>/solution/` dan olinadi.
5. **Qulflangan dars mazmuni JSON ga umuman tushmaydi** — CSS bilan yashirish
   yetarli emas, sahifa manbasidan o'qib olinardi.
6. **Yangi dars `is_free=False` bilan tug'iladi** (fail closed). Bayroqni
   qo'yishni unutish kontentni bepul qilib qo'ymaydi.
7. **Narxlar TIYINDA, butun son.** Kasrli son ishlatilmaydi.
8. **`current_period_end` ni faqat `services.extend_subscription` o'zgartiradi** —
   u davr jurnalini ham o'sha tranzaksiyada yozadi.
9. **Narx davrga muzlatiladi.** Hisobot joriy tarifga bog'lanmaydi, aks holda
   narx oshirilganda o'tgan tushum tarixi qayta hisoblanardi.
10. **`ADMIN_GRANT` tushum hisobotiga kirmaydi** — faqat `PAYMENT`.
11. **Parol tiklash kodi bazada xeshlangan** (SHA-256), bir marta ishlaydi,
    5 urinishdan keyin kuyadi, javob email bor-yo'qligidan qat'i nazar bir xil.

## Testlar

```bash
python manage.py test          # hammasi
python manage.py test billing  # faqat obuna
```

## Hali qilinmagan (3-bosqich)

- Click / Payme avtomatik integratsiyasi (`external_tx_id` maydoni tayyor)
- Telegram bot orqali xabarnomalar (hozir faqat email)
- PDF sertifikat generatsiyasi
- Login urinishlarini cheklash (django-axes)
- Videolarni CDN / S3 ga ko'chirish
- 66 darsga test yaratish (hozir 7 test bor)
- Kod muharririga Python qo'llab-quvvatlashi
- "AI Mentor" ni haqiqiy AI ga ulash (hozir qattiq kodlangan javoblar)
