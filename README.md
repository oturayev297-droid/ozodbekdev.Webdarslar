# Nexus — Onlayn Ta'lim Platformasi

Python, Django, JavaScript va React o'rgatuvchi video kurslar platformasi.

## Nima bor

- **73 video dars** 4 yo'nalishda (Python 15, Django 13, React 15, JavaScript 30)
- **Testlar** — server tomonda tekshiriladigan, natijasi soxtalashtirilmaydigan
- **O'zlashtirish nazorati** — dars tugatish, level tizimi, haftalik faollik
- **Kod muharriri** — brauzerda JavaScript topshiriqlari
- **Admin panel** — kontent va o'quvchilarni boshqarish

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
core/                  asosiy ilova
  models.py            Category → Module → Lesson → Quiz → Question → Choice
  views.py             barcha sahifalar va API endpointlari
  admin.py             admin panel sozlamalari
  tests.py             28 test
stitch_backend/        Django proyekt sozlamalari
templates/             HTML shablonlar (Tailwind CDN)
media/lesson_videos/   dars videolari (git ga tushmaydi, ~5 GB)
```

## Muhim xavfsizlik qoidalari

Bu qoidalarni buzish pullik kontentni bepul qilib qo'yadi — o'zgartirishdan
oldin `python manage.py test core` ni ishga tushiring:

1. **Test javoblari HTML ga chiqmaydi.** `is_correct` shablonlarga hech qachon
   berilmaydi. Ball faqat `submit_quiz` da, serverda hisoblanadi.
2. **Video faqat `/lessons/<id>/video/` orqali.** `/media/lesson_videos/` marshruti
   ataylab yopilgan (nginx da ham `return 404`).
3. **Kontent sahifalari `@login_required`.** Faqat `/`, `/login/`, `/register/` ochiq.
4. **Challenge yechimi HTML da turmaydi** — `/editor/<id>/solution/` dan olinadi.

## Testlar

```bash
python manage.py test core
```

## Hali qilinmagan (2-bosqich)

- To'lov tizimi (Payme / Click) va obuna modeli
- Kontentni bepul/pullik tariflarga bo'lish
- Parolni tiklash va email tasdiqlash
- PDF sertifikat generatsiyasi
- Login urinishlarini cheklash (django-axes)
- Videolarni CDN / S3 ga ko'chirish
- 66 darsga test yaratish (hozir 7 test bor)
- Kod muharririga Python qo'llab-quvvatlashi
- "AI Mentor" ni haqiqiy AI ga ulash (hozir qattiq kodlangan javoblar)
