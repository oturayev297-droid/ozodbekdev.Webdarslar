# Nexus — Onlayn Ta'lim Platformasi

Python, Django, JavaScript va React o'rgatuvchi video kurslar platformasi.

## Nima bor

- **73 video dars** 4 yo'nalishda (Python 15, Django 13, React 15, JavaScript 30)
- **Yozma darslar** — matn, sxema-rasmlar va test bilan; «Sun'iy intellekt»
  kursi (10 dars, 41 savol) tayyor holda kiritilgan
- **Admin ruxsati** — ro'yxatdan o'tgan o'quvchi admin tasdiqlamaguncha kira olmaydi
- **Obuna tizimi** — oylik, 100 000 so'm; Payme / Click yoki qo'lda tasdiqlash
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
- **REST API** (`/api/v1/`) — alohida deploy qilinadigan frontend uchun
- **React frontend** (`frontend/`) — Next.js 16, 17 sahifa, Vercel uchun tayyor

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
  richtext.py          dars matnini XAVFSIZ HTML ga aylantirish
  diagrams.py          dars sxemalarini kod bilan chizish (PNG)
  approval.py          admin ruxsati darvozasi
  quiz_scoring.py      ball hisoblash (shablon va API bir joydan oladi)
  video_storage.py     S3/R2 imzolangan havolalar
  views.py             sahifalar va API endpointlari
  password_reset.py    6 xonali kod bilan parol tiklash
  lockout.py           login urinishlari cheklovi (brute-force himoyasi)
  certificates.py      PDF sertifikat generatsiyasi va tekshirish
  ai_mentor.py         Claude API orqali o'qituvchi chat
  study_time.py        o'quv vaqtini serverda o'lchash
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
api/                   REST API (/api/v1/)
  permissions.py       darvozalarni CHAQIRADI, qayta yozmaydi
  serializers.py       qulflangan mazmun serializerga tushmaydi
  views.py             biznes mantiq billing/core dan chaqiriladi
frontend/              Next.js 16 frontend (Vercel)
  src/lib/api.ts       barcha endpointlar, CSRF, sessiya cookie
  src/lib/runner.ts    kodni brauzerda ishga tushirish (Pyodide)
  src/components/      Nav, Guard, MentorChat
  src/app/             17 ta sahifa
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

## Kirish qoidasi

Kontent ochilishi uchun **ikkita darvoza** o'tilishi kerak. Ular alohida
va bir-birining o'rnini bosmaydi:

| Darvoza | Nima | Qachon |
|---|---|---|
| **Ruxsat** | Adminning bu odamni qabul qilishi | BIR MARTA, panelda |
| **Obuna** | Joriy oy uchun to'lov | HAR OY yangilanadi |

```
Ro'yxatdan o'tdi        -> hisob YOPIQ (is_approved=False)
Admin ruxsat berdi      -> tanishtiruv darslari ochildi (har kursdan 3 ta)
100 000 so'm to'ladi    -> admin tasdiqlaydi
                        -> HAMMA dars ochiq, 1 oy
Oy tugadi               -> kirish AVTOMATIK yopiladi
```

Ruxsat obunani almashtirsa, bir marta to'lagan odam abadiy kirardi.
Obuna ruxsatni almashtirsa, admin kimni qabul qilishini nazorat qila
olmasdi. Shuning uchun ikkalasi ham kerak.

**Ruxsatsiz odam kirishi BLOKLANMAYDI** — u tizimga kiradi va
`/kutish/` sahifasida aynan nima kutayotganini ko'radi. Login butunlay
yopilsa, u to'g'ri parol bilan ham kira olmay "parolim ishlamayapti"
deb o'ylardi.

Ruxsat berish: **`/panel/oquvchilar/`** — kutayotganlar ro'yxat tepasida
turadi. Ruxsatni olib tashlashda **sabab majburiy**, chunki u
o'quvchiga ko'rsatiladi.

## Obuna tizimi

**Faqat oylik, 100 000 so'm.** Uzoq muddatli variantlar (3/6/12 oy)
ataylab olib tashlangan: o'quvchi har oy davom etish-etmaslikni qayta
hal qiladi va narx bitta bo'lgani uchun hisobda chalkashlik bo'lmaydi.

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
python manage.py seed_billing --price 100000 --free-lessons 3
```

So'ng `/panel/sozlamalar/` da karta rekvizitlarini kiriting, aks holda
o'quvchi to'lay olmaydi. Raqam shu yerda tekshiriladi (16-19 xona):
tekshiruvsiz xato terilgan raqam saqlanardi va pul yo'q kartaga
ketardi.

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
33. **Dars matni HTML ga faqat `core.richtext.render` orqali aylanadi.**
    U avval HAMMASINI ekranlaydi, keyin faqat o'zi qo'ygan teglarni
    qaytaradi. "Keraksiz teglarni olib tashlash" yondashuvi hech qachon
    ishlatilmaydi: `<scr<script>ipt>` kabi hiylalar undan o'tib ketadi.
34. **Qulflangan darsning rasmlari ham JSON ga tushmaydi.** Dars mazmuni
    rasmda bo'lsa, ularni qoldirish qulfni ma'nosiz qilardi.
35. **Kurs kartochkalari shablonda yozilmaydi** — `courseData` dan
    quriladi. Qo'lda yozilganda yangi bo'lim sahifada ko'rinmasdi va
    dars sonlari bazadagi haqiqatga bog'lanmagan edi.
36. **Yangi hisob `is_approved=False` bilan tug'iladi** (fail closed).
    Ro'yxatdan o'tish formasini topgan har kim darhol ichkariga
    kirmasin.
37. **Ruxsat va obuna ARALASHTIRILMAYDI.** Ruxsat — adminning odamni
    tanishi (bir marta), obuna — joriy oy uchun to'lov (har oy).
    Ikkalasi ham o'tishi kerak.
38. **Ruxsatni olib tashlashda sabab MAJBURIY** — u o'quvchiga
    ko'rsatiladi. Sababsiz rad javobi odamni butunlay yo'qotadi.
39. **Ruxsatsiz odam login sahifasiga qaytarilmaydi** — u `/kutish/`
    sahifasiga tushadi. Anonim odam esa login sahifasiga. Bu ikki xil
    holat va ikki xil javob talab qiladi.
40. **API darvozani QAYTA YOZMAYDI** — `core.approval` va
    `billing.gating` chaqiriladi. Nusxa yozilsa, API paywallda
    teshik bo'lardi va buni sezish uchun hech qanday belgi
    bo'lmasdi.
41. **Qulflangan darsning mazmuni API javobiga umuman tushmaydi.**
    "Frontend yashiradi" ishlamaydi: API javobi brauzerning tarmoq
    bo'limida ochiq ko'rinadi.
42. **`is_correct` serializerda YO'Q va qo'shilmasin.** Test javobi
    klientga yuborilsa, test ham, sertifikat ham ma'nosini yo'qotadi.
43. **Ball `core.quiz_scoring` da, bitta joyda.** Shablonli sahifa ham,
    API ham o'sha funksiyani chaqiradi — bir xil test ikki joyda ikki
    xil ball bermasligi kerak.
44. **Frontend `/api/*` ni PROXY orqali chaqiradi** (Vercel rewrites).
    Cookie birinchi tomon bo'lib qoladi va Safari uni bloklamaydi.
    Token `localStorage` da saqlanmaydi.
45. **Topshiriq yechimi ALOHIDA endpointda.** Ro'yxatga yoki topshiriq
    ma'lumotiga qo'shilsa, u sahifa ochilishidayoq javobga tushib
    qolardi va topshiriqning ma'nosi qolmasdi.
46. **Kod BRAUZERDA ishlaydi, serverda emas.** Begona kodni serverda
    ijro etish — serverni begona odamga topshirish demak.
47. **Profil serializerida `is_approved` va `level` YO'Q.** Bo'lganda
    o'quvchi bitta so'rov bilan o'ziga admin ruxsatini berib qo'yardi.

## Yozma darslar

Platforma dastlab faqat video uchun qurilgan edi: dars matni serverdan
kelardi, lekin sahifada **ko'rsatilmasdi** va rasm uchun maydon umuman
yo'q edi. Endi dars uch qismdan iborat bo'lishi mumkin: video, matn va
rasmlar. Uchalasi ham ixtiyoriy.

### Matn qanday yoziladi

`Lesson.theory` maydoniga **oddiy matn** yoziladi. HTML yozilmaydi — u
ekranlanadi va matn bo'lib ko'rinib qoladi. Bezaklar:

```
## Sarlavha              ### Kichik sarlavha
**qalin**                *kursiv*
`kod`                    ``` kod bloki ```
- ro'yxat                1. raqamli ro'yxat
> eslatma                ---  (ajratuvchi chiziq)
[matn](https://...)      (faqat http/https)
```

Xatboshi ochish uchun **bo'sh qator** qoldiriladi. Bitta qator uzilishi
bo'sh joyga aylanadi — matn manbada qulay kenglikda yozilaveradi.

Uzun ro'yxat elementining davomi **ichkariga suriladi**:

```
- **Til modeli** — matn bilan ishlaydigan tur.
  ChatGPT, Claude, Gemini shu turga kiradi.
```

### Rasmlar

Rasm matn ichiga havola bilan qo'yilmaydi — u alohida model
(`LessonImage`). Panelda dars sahifasining pastidan yuklanadi, izoh va
tartib raqami bilan. Rasmlar matndan keyin, tartib bo'yicha chiqadi.

Rasm fayllari `/media/lesson_images/` da va **ochiq** beriladi. Video esa
yopiq: video — darsning o'zi, rasm esa matnning kichik qismi.

### Tayyor kurs

```bash
python manage.py seed_ai_course              # yaratadi yoki yangilaydi
python manage.py seed_ai_course --dry-run    # faqat ko'rsatadi
python manage.py seed_ai_course --no-images  # sxemalarsiz
```

«Sun'iy intellekt va prompt engineering» — 3 modul, 10 dars, 8 sxema,
10 test (41 savol). Birinchi 3 dars bepul.

Buyruq **qayta ishga tushirilishi xavfsiz**: mavjud darslar yangilanadi,
ikkinchi nusxa yaratilmaydi, o'quvchilarning o'zlashtirishi saqlanadi.
Testlar **qoralama** bo'lib tushadi — savollarni o'qib chiqib
`/panel/testlar/` da nashr qilasiz.

Sxemalar `core/diagrams.py` da **kod bilan chiziladi**. Sababi: `media/`
git ga tushmaydi, demak yangi serverda rasmlar yo'q bo'lardi — kod esa
ko'chadi va buyruqni qayta ishga tushirish yetarli.

## Boshqaruv paneli

`/panel/` — **butun tizim shu yerdan boshqariladi**. Django'ning
standart `/admin/` paneli o'chirilgan: ikki xil boshqaruv o'rniga bitta
qoldi. Ilgari admin orqali kiritilgan hamma narsa (karta rekvizitlari,
tarif narxi, bo'limlar, test savollari) endi panelda o'z bo'limiga ega.

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
| Ota-onalar | O'quvchini ota-onasiga bog'lash — **faqat admin qo'lida** |
| Sozlamalar | Karta rekvizitlari va obuna narxi |

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
python manage.py test core.tests_richtext     # dars matni va xavfsizligi
python manage.py test core.tests_ai_course    # tayyor AI kursi
python manage.py test core.tests_approval     # admin ruxsati darvozasi
python manage.py test api                     # REST API va paywall
python manage.py test core.tests_video_storage  # video ombori
python manage.py test core.tests_study_time   # o'quv vaqti va ota-ona paneli
python manage.py test panel.tests_sections    # kartalar, narx, savollar
```

## Ota-ona paneli

Ota-ona farzandi qanday o'qiyotganini ko'radi: kunlik soatlar, test
natijalari, o'zlashtirish foizi va sertifikatlar.

Bog'lanishni **faqat admin yaratadi** (`/panel/ota-onalar/`). Ota-ona
o'zini istagan o'quvchiga bog'lay olsa, begona odam bolaning shaxsiy
natijalarini ko'rib olardi — shuning uchun bu yo'l ochiq emas.

O'quv vaqti brauzerdan har daqiqada keladigan signal bilan o'lchanadi
(`core/study_time.py`):

  * sana **serverda** belgilanadi — telefon soatini o'zgartirish ta'sir qilmaydi
  * ikki signal orasi 45 soniyadan kam bo'lsa hisoblanmaydi
  * kuniga eng ko'pi 14 soat yoziladi
  * varaq ko'rinmayotgan yoki 3 daqiqa harakatsiz bo'lsa signal ketmaydi

Ota-onaga `is_approved` kerak emas — u o'quvchi emas, shuning uchun
darsga ruxsat talab qilinsa hisobotni umuman ko'ra olmasdi.

## Hali qilinmagan

- Videolarni CDN / S3 ga ko'chirish
- Darslarning `theory` maydonini to'ldirish (hozir ko'pchiligi bo'sh —
  `generate_quizzes` ishlashi uchun matn kerak)

> **Payme / Click:** kod yozilgan va testlar bilan qoplangan, lekin
> haqiqiy merchant kalitlarisiz faqat soxta so'rovlar bilan sinalgan.
> Ishga tushirishdan oldin **sandbox** da to'liq oqimni o'tkazing —
> `DEPLOY.md` 9-bo'limi.
