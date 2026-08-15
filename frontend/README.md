# Nexus frontend

Next.js 16 (App Router) — Django backendning REST API si ustiga qurilgan.

## Ishga tushirish

```bash
npm install
cp .env.example .env.local     # BACKEND_URL ni to'ldiring
npm run dev                    # http://localhost:3000
```

Backend ham ishlab turishi kerak:

```bash
cd ..
python manage.py runserver
```

## Arxitektura

### `/api/*` so'rovlari backendga UZATILADI, to'g'ridan-to'g'ri bormaydi

Bu `next.config.mjs` dagi `rewrites` bilan hal qilinadi va bu shunchaki
qulaylik emas — **xavfsizlik qarori**:

- Brauzer uchun so'rov o'z domenimizga ketayotgandek ko'rinadi, shuning
  uchun sessiya cookie **birinchi tomon** bo'lib qoladi.
- Safari va iOS uchinchi tomon cookie'larini bloklaydi. To'g'ridan-to'g'ri
  `railway.app` ga murojaat qilinsa, o'sha brauzerlarda kirish umuman
  ishlamasdi.
- CORS umuman kerak bo'lmaydi.

Muqobil yo'l — tokenni `localStorage` da saqlash — sahifadagi har qanday
skript uni o'qiy olishini bildiradi. Sessiya cookie esa `HttpOnly`.

### Ikkita nozik joy

**1. Oxiridagi `/` saqlanadi.** Next.js standart holatda uni olib
tashlaydi, Django esa talab qiladi. Ikkalasi ham `next.config.mjs` da
hal qilingan (`skipTrailingSlashRedirect` + manzil oxiridagi slash).
Busiz har bir POST so'rov redirectga tushib, GET ga aylanib qolardi.

**2. `CSRF_TRUSTED_ORIGINS`.** Django POST so'rovda `Origin` sarlavhasini
tekshiradi. Frontend boshqa portda yoki domenda bo'lsa, backend
sozlamasida `FRONTEND_ORIGINS` to'ldirilishi kerak.

## Tuzilishi

```
src/
  lib/
    api.ts           barcha endpointlar va turlar; CSRF shu yerda
    auth-context.tsx joriy foydalanuvchi (bir marta so'raladi)
  components/
    Nav.tsx          yuqori menyu
    Guard.tsx        kirmagan -> /login, ruxsatsiz -> /kutish
  app/
    page.tsx              bosh sahifa
    login/ register/      autentifikatsiya
    kutish/               admin ruxsatini kutish
    kurslar/              kurslar ro'yxati va bo'lim
    darslar/[id]/         dars: matn, rasm, video
    testlar/              testlar va yechish
    obuna/                tarif va to'lov oqimi
```

## Xavfsizlik qoidalari

1. **`Guard` — bu faqat qulaylik.** Haqiqiy himoya serverda: uni
   chetlab o'tgan odam API dan 403 oladi va mazmun unga umuman
   yuborilmaydi.
2. **`dangerouslySetInnerHTML` FAQAT `theory_html` uchun.** U serverda
   `core/richtext.py` da qurilgan: matn to'liq ekranlangan va faqat
   ruxsat etilgan teglar qo'yilgan. Boshqa manbadan kelgan HTML bu
   yerga tushmasligi kerak.
3. **To'g'ri javoblar frontendda yo'q.** `Choice` turida `is_correct`
   maydoni ataylab yozilmagan — ball serverda hisoblanadi.

## Vercel'ga deploy

1. Loyihani import qiling, **Root Directory** = `frontend`
2. Muhit o'zgaruvchisi: `BACKEND_URL=https://<railway-domeningiz>`
3. Backend `.env` da `FRONTEND_ORIGINS` ga Vercel manzilini qo'shing

Batafsil: loyiha ildizidagi `DEPLOY.md`.
