# Nexus — Onlayn Ta'lim Platformasi

Python, Django, JavaScript va React o'rgatuvchi video kurslar platformasi.

## Nima bor

- **73 video dars** 4 yo'nalishda (Python 15, Django 13, React 15, JavaScript 30)
- **Obuna tizimi** — Payme / Click avtomatik yoki qo'lda tasdiqlash, 1/3/6/12 oy
- **Testlar** — server tomonda tekshiriladigan, natijasi soxtalashtirilmaydigan
- **PDF sertifikat** — 80%+ ballda avtomatik, ommaviy tekshirish kodi bilan
- **O'zlashtirish nazorati** — dars tugatish, level tizimi, haftalik faollik
- **Parolni tiklash** — emailga 6 xonali kod
- **Telegram xabarnomalar** — to'lov rekvizitlari, tasdiq, muddat eslatmalari
- **AI Mentor** — Claude API'ga ulangan haqiqiy o'qituvchi chat
- **Kod muharriri** — brauzerda **Python** (Pyodide) va JavaScript
- **Brute-force himoyasi** — login urinishlari cheklovi
- **Boshqaruv paneli** (`/panel/`) — hisobotlar, pul aylanmasi, darslik joylash,
  xabar yuborish va kuzatish, o'z kirishi va parol tiklashi bilan

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
  lockout.py           login urinishlari cheklovi (brute-force himoyasi)
  certificates.py      PDF sertifikat generatsiyasi va tekshirish
  ai_mentor.py         Claude API orqali o'qituvchi chat
  admin.py             kontent admin paneli
billing/               obuna va to'lov
  models.py            Tarif, Obuna, Davr jurnali, To'lov so'rovi
  dates.py             Toshkent vaqti bo'yicha sana hisobi
  services.py          obunani uzaytirish (YAGONA yo'l) va holat
  payment_requests.py  to'lov so'rovi oqimi
  gating.py            kontent darvozasi (bepul dars / obuna)
  telegram.py          xabarnomalar va hisobni ulash
  gateways/payme.py    Payme Merchant API (JSON-RPC)
  gateways/click.py    Click SHOP API (prepare / complete)
  gateway_links.py     to'lov sahifasiga havola qurish
  admin.py             to'lovlarni ko'rib chiqish paneli
panel/                 boshqaruv paneli (/panel/)
  auth.py              xodim kirishi, chiqish, parol tiklash
  reports.py           hisobotlar — FAQAT o'qiydi, hech narsa o'zgartirmaydi
  messaging.py         Telegramga xabar yuborish (navbat bilan)
  views.py             sahifalar — biznes mantiqni billing dan CHAQIRADI
  forms.py             dars va modul formalari
  context.py           menyudagi hisoblagichlar
stitch_backend/        Django proyekt sozlamalari
templates/             HTML shablonlar (Tailwind CDN)
media/lesson_videos/   dars videolari (git ga tushmaydi, ~5 GB)
```

## Obuna tizimi

Ikki yo'l bor. **Avtomatik** — Payme yoki Click orqali, obuna darhol
ochiladi. **Qo'lda** — kartaga o'tkazma, admin tasdiqlaydi:

```
o'quvchi muddat tanlaydi    -> REQUESTED
admin kartani beradi        -> CARD_ISSUED       (karta shundan keyingina ko'rinadi)
o'quvchi "chekni yubordim"  -> RECEIPT_UPLOADED  (kutish rejimi yoqiladi)
admin tasdiqlaydi           -> CONFIRMED         (obuna uzayadi)
admin rad etadi             -> REJECTED          (kutish darhol tugaydi)
javobsiz qoladi             -> EXPIRED
```

To'lov tizimi kalitlari bo'sh bo'lsa tugmalar ko'rinmaydi va qo'lda
tasdiqlash ishlashda davom etadi — avtomatik to'lov **qo'shimcha**,
o'rnini bosuvchi emas.

**BIRLIKLAR HAR XIL:** Payme tiyinda (`30000000`), Click so'mda
(`300000.00`). Aylantirish faqat `gateway_links.py` va gateway
modullarida — boshqa joyda yozmang.

Sozlash:

```bash
python manage.py seed_billing --price 99000 --free-lessons 3
```

So'ng admin panel -> **Admin sozlamalari** -> `subscription.cards` ga karta
rekvizitlarini kiriting (JSON massiv), aks holda o'quvchi to'lay olmaydi.

Kunlik vazifalar (cron): so'rovlarni kuydirish va 7/3/0 kunlik eslatmalar.

```bash
python manage.py subscription_daily
python manage.py prune_login_attempts
```

Video qayta yuklanganda eski fayl diskda qoladi — vaqti-vaqti bilan
tozalang (standart holda faqat ko'rsatadi, o'chirmaydi):

```bash
python manage.py prune_orphan_videos
```

## Sertifikatlar

Testda **80%+** ball olinganda sertifikat avtomatik beriladi (`certificates.PASS_SCORE`).
Har birida tasodifiy tekshirish kodi bor — ish beruvchi `/verify/` sahifasida
kodni kiritib haqiqiyligini ko'radi (login talab qilinmaydi).

PDF diskda **saqlanmaydi** — har so'rovda `reportlab` bilan qayta chiziladi.
Mazmun `Certificate` yozuvida muzlatilgan, PDF esa uning ko'rinishi.

## AI Mentor

Chat `claude-opus-5` modeliga ulangan. `ANTHROPIC_API_KEY` bo'sh bo'lsa
o'quvchi "sozlanmagan" xabarini oladi va sayt buzilmaydi.

Xarajat nazorati:
- Har o'quvchiga daqiqada 5, kunida 60 savol
- Suhbat tarixidan faqat oxirgi 6 almashuv yuboriladi
- Tizim ko'rsatmasi keshlanadi (`cache_control`)
- `effort=low` — tushuntirish uchun chuqur fikrlash kerak emas

**Suhbat tarixi SERVERDA saqlanadi**, klientdan qabul qilinmaydi. Aks
holda o'quvchi soxta "assistant" javoblarini yuborib modelni boshqarib
olardi (prompt injection).

**Model javobi SERVERDA HTML ga aylantiriladi** va tozalanadi — matn
to'g'ridan-to'g'ri `innerHTML` ga tushmaydi.

Streaming ataylab ishlatilmagan: loyiha gunicorn'ning sinxron
worker'larida ishlaydi va oqim butun javob davomida worker'ni band
qilib turardi.

## Test savollarini generatsiya qilish

```bash
python manage.py generate_quizzes --category python --limit 5
python manage.py generate_quizzes --notes-dir ./dars_matnlari --lesson-id 34
python manage.py generate_quizzes --lesson-id 34 --dry-run
```

**Natija har doim QORALAMA** (`is_published=False`) — o'quvchi uni
ko'rmaydi. Admin panel -> Testlar -> o'qib chiqing -> "Nashr qilish".

**Matn yetarli bo'lmasa buyruq ishlamaydi.** Model faqat berilgan
matndan savol yoza oladi. Bu platformada darslarning mazmuni **videoda**,
`theory` maydonida esa ko'pincha bir necha so'z. Shunday darsdan
generatsiya qilinsa, model sarlavhadan taxmin qilib darsga mos
kelmaydigan savollar yozadi.

Shuning uchun matni `--min-theory` (standart 200 belgi) dan qisqa
darslar o'tkazib yuboriladi. Uch yo'l bor:

| Yo'l | Qachon |
|---|---|
| `theory` ni admin panelda to'ldirish | Eng yaxshisi — matn saytda ham foydali |
| `--notes-dir ./papka` | Har dars uchun `<dars_id>.txt` yoki `.md` — video transkripti, konspekt, slayd matni |
| `--allow-thin` | Majburlash. Sifat past bo'ladi, qatorma-qator tekshiring |

Model javobining shakli **JSON sxema** bilan kafolatlanadi, lekin ma'no
emas — buyruq har savolni qo'shimcha tekshiradi: aynan bitta to'g'ri
javob, kerakli sondagi variant, takroriy va bo'sh variant yo'qligi.
Yaroqsiz test **saqlanmaydi**.

## Kod muharriri

Python brauzerda **Pyodide** (CPython -> WebAssembly) orqali ishlaydi —
server ishtirok etmaydi. Kod hech qayerga yuborilmaydi va serverda begona
kod ijro etilmaydi. Pyodide ~10 MB, shuning uchun sahifa ochilganda emas,
faqat birinchi "Ishga tushirish" bosilganda yuklanadi.

Topshiriq tili `Challenge.language` da (`python` yoki `javascript`).

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
12. **`confirm_reset` butun funksiya `@transaction.atomic` BO'LMASLIGI kerak** —
    bo'lsa xato ko'tarilganda `attempts++` orqaga qaytarilib, brute-force
    himoyasi butunlay o'chib qolardi.
13. **Login qulfi davomida yangi urinish yozilmaydi** — aks holda hujumchi
    urinib turib qulfni cheksiz uzaytirardi va haqiqiy egasi kira olmasdi.
14. **`X-Forwarded-For` dan OXIRGI qiymat olinadi** — nginx o'zi ko'rgan
    manzilni oxiriga qo'shadi, chapdagilar klientdan kelgan va soxta bo'lishi mumkin.
15. **Sertifikat kodi tasodifiy**, ketma-ket ID emas — aks holda `/verify/1`,
    `/verify/2` deb butun bazani sanab chiqib bo'lardi.
16. **Berilgan sertifikat qayta yozilmaydi** — test qayta topshirilib ball
    oshsa ham hujjatdagi ball o'zgarmaydi.
17. **`telegram.py` dagi hech bir funksiya xato tashlamaydi** — xabarnoma
    yuborilmagani uchun tasdiqlangan to'lov bekor bo'lib qolmasligi kerak.
18. **Ko'p qatorli `{# #}` ISHLATILMAYDI** — u faqat bir qatorli izoh,
    ko'p qatorda matn sahifaga chiqib ketadi. `{% comment %}` ishlatiladi.
19. **To'lov tizimi summasi SERVERDAGI qiymat bilan solishtiriladi.**
    Payme/Click yuborgan summaga hech qachon ishonilmaydi.
20. **Gateway obunani `confirm_request` orqali uzaytiradi** — qo'lda
    tasdiqlash bilan aynan bir xil yo'l. Ikkinchi yo'l yozilsa
    idempotentlik va jurnal qoidalari ikki joyda takrorlanardi.
21. **Takror so'rov obunani ikki marta uzaytirmaydi.** Payme va Click
    tarmoq uzilganda so'rovni ATAYLAB qayta yuboradi. Ikki qatlam himoya:
    `GatewayTransaction (provider, external_id)` va
    `SubscriptionPeriod.payment_request` unique.
22. **`secrets.compare_digest` satrlarda faqat ASCII qabul qiladi** —
    tashqi ma'lumot bilan solishtirishda BAYTLAR ishlatiladi, aks holda
    buzilgan sarlavha serverni 500 ga tushirardi.
23. **To'lovdan keyin bekor qilishda davr jurnali o'chirilmaydi** —
    adminga xabar boradi, qarorni u qabul qiladi.
24. **AI Mentor suhbat tarixi serverda** — klientdan qabul qilinmaydi.
25. **Model javobi serverda HTML ga aylantiriladi** — `_to_html` faqat
    kerakli teglarni chiqaradi, qolgani qochiriladi.
26. **Generatsiya qilingan test QORALAMA bo'ladi** (`is_published=False`)
    va o'quvchiga ko'rinmaydi. Tekshirilmagan savol o'quvchini chalg'itadi
    va sertifikatni ma'nosiz qiladi.
27. **Matn yetarli bo'lmasa savol generatsiya qilinmaydi** — model
    sarlavhadan taxmin qilgan savol darsga mos kelmaydi.
28. **Panel biznes mantiqni takrorlamaydi.** To'lovni tasdiqlash, obunani
    uzaytirish, sinov berish — hammasi `billing.payment_requests` va
    `billing.services` orqali chaqiriladi. Ikki nusxa bo'lsa qaysi biri
    to'g'ri ekani bilinmay qoladi.
29. **Panel `is_staff` talab qiladi va huquq har so'rovda tekshiriladi.**
    Kirgan, lekin huquqsiz foydalanuvchi 403 oladi — login sahifasiga
    qaytarilmaydi, aks holda to'g'ri parol bilan cheksiz aylanardi.
30. **Panel kirishida xodimlik OSHKOR QILINMAYDI.** Parol xato bo'lsa ham,
    hisob xodim bo'lmasa ham xabar bir xil. Aks holda panel "qaysi hisob
    admin" degan savolga javob beradigan asbobga aylanardi.
31. **Tushum hisoboti faqat `source=PAYMENT` davrlaridan.** `ADMIN_GRANT`
    va `TRIAL` — bu pul emas; qo'shilsa oylik tushum o'ylab topilgan
    raqamga aylanadi.
32. **Aylanma sanasi — `created_at`** (pul kelgan payt), `start_date` emas.
    Oylar Toshkent vaqti bo'yicha bo'linadi.

## Boshqaruv paneli

`/panel/` — kundalik ish uchun. Django'ning standart `/admin/` paneli
zaxira yo'l sifatida qoladi (model darajasidagi tuzatishlar uchun).

| Bo'lim | Nima qiladi |
|---|---|
| Bosh sahifa | Oylik tushum, faol obunachilar, javob kutayotgan to'lovlar |
| Pul aylanmasi | Oylar grafigi, to'lov usullari kesimi, bepul berilganlar |
| To'lov so'rovlari | Karta berish, tasdiqlash, rad etish (sabab majburiy) |
| Obuna jurnali | O'zgartirilmaydigan moliyaviy tarix |
| Payme / Click | Tranzaksiyalar — faqat ko'rish |
| O'quvchilar | Ro'yxat, holat, bepul kun berish, shaxsiy xabar |
| Darsliklar | Modul va dars qo'shish, video yuklash, bepul/pullik |
| Testlar | Qoralamalarni ko'rib chiqib nashr qilish |
| Xabar yuborish | Telegramga guruh yoki shaxsiy xabar |
| Kuzatish | Kirish urinishlari, AI Mentor, sertifikatlar |

Xodim yaratish:

```bash
python manage.py createsuperuser
# yoki mavjud hisobga huquq berish:
python manage.py shell -c "from django.contrib.auth.models import User; u=User.objects.get(username='NOM'); u.is_staff=True; u.save()"
```

Parolni tiklash `/panel/forgot-password/` da — o'quvchinikidan alohida
sahifa, lekin ichida bir xil modul ishlaydi (kod uzunligi, muddati va
urinishlar soni bir joyda turadi).

## Testlar

```bash
python manage.py test                  # hammasi
python manage.py test billing          # obuna va to'lov
python manage.py test core.tests_phase3  # cheklov, sertifikat, muharrir
python manage.py test billing.tests_gateways  # Payme / Click
python manage.py test core.tests_mentor       # AI Mentor
python manage.py test core.tests_generate_quizzes  # savol generatsiyasi
python manage.py test panel                   # boshqaruv paneli
```

## Hali qilinmagan

- Videolarni CDN / S3 ga ko'chirish
- Darslarning `theory` maydonini to'ldirish (hozir ko'pchiligi bo'sh —
  `generate_quizzes` ishlashi uchun matn kerak)

> **Payme / Click:** kod yozilgan va testlar bilan qoplangan, lekin
> haqiqiy merchant kalitlarisiz faqat soxta so'rovlar bilan sinalgan.
> Ishga tushirishdan oldin **sandbox** da to'liq oqimni o'tkazing —
> `DEPLOY.md` 9-bo'limi.
