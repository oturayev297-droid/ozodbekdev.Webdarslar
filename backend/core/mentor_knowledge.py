"""
AI Mentor bilimi
================

Mentor platformani BILMAS edi: "sertifikat qanday olinadi?", "muharrirda
nega xato deyapti?", "keyingi dars nima?" degan savollarga umumiy
javob berardi yoki taxmin qilardi. Bu modul unga ikki narsani beradi:

  GUIDE      — o'zgarmas matn: sahifalar, qoidalar, kod yozish uslubi,
               kurslar nega kerak. Kodda turadi, chunki u sayt
               KODIGA bog'liq (sahifa qo'shilsa, shu yerda yoziladi).

  catalog()  — bazadan quriladigan kurs va darslar ro'yxati. Admin
               panelda dars qo'shsa yoki nomini o'zgartirsa, mentor
               buni qo'lda yangilashsiz ko'radi.

KESH UCHUN TARTIB MUHIM (`core.ai_mentor._system_prompt`): model
so'rovning takrorlanadigan boshlanishini keshlaydi. GUIDE hech qachon
o'zgarmaydi, katalog esa faqat admin kontentni
o'zgartirganda. Shu sababli katalog BARQAROR tartibda quriladi —
`order` teng bo'lgan darslar `id` bo'yicha. Tartib har so'rovda
boshqacha chiqsa, kesh har safar buzilib, bilimning to'liq narxi
qayta to'lanardi.

MAXFIY NARSA KATALOGGA TUSHMAYDI: muharrir yechimlari va kutilgan
natijalar, test javoblari. Mentor ularni bilsa, o'quvchi so'rab
olardi.
"""

#: Dars matni shundan qisqa bo'lsa "yozma matn bor" deyilmaydi.
#: Bazadagi ko'p video darslarda matn o'rnida "Theory here..." yoki
#: "Nazariy TGDA---->" kabi to'ldiruvchi turibdi — u matn emas.
TEXT_MIN_CHARS = 200


GUIDE = """# PLATFORMA HAQIDA BILIM

Bu bo'lim ozodbekdev.uz saytining o'zi haqida. O'quvchi sayt, sahifa,
qoida yoki kurs haqida so'rasa, shu ma'lumotga tayan. Bu yerda
yozilmagan imkoniyatni o'ylab topma — bilmasang, "bu haqda aniq
ma'lumotim yo'q, administratordan so'rang" de.

## Umumiy tuzilma

Sayt ikki qismdan iborat: o'quvchi ko'radigan sayt va faqat xodimlar
kiradigan boshqaruv paneli (/panel/). O'quvchini hech qachon panelga
yo'naltirma — u yerga faqat administrator kiradi.

O'quv yo'li: Kurs -> Modul -> Dars -> (ba'zi darslarda) Test.
Qo'shimcha: kod muharriri topshiriqlari, portfolio loyihalari va
sertifikatlar.

## Sahifalar va ular nima uchun

- **Bosh sahifa (/)** — sayt bilan tanishtiradi. Tizimga kirmagan
  odam shu yerdan ro'yxatdan o'tadi yoki kiradi; kirgan odam
  "Darslarga o'tish" tugmasini ko'radi.

- **Ro'yxatdan o'tish (/register)** — login, email, parol va to'liq
  ism so'raladi. Yangi hisob DARHOL ochilmaydi: administrator
  ruxsat berguncha o'quvchi "kutish" sahifasida turadi.

- **Kirish (/login)** — login va parol bilan. Ruxsati hali yo'q
  odam kutish sahifasiga, ruxsati bor odam kurslarga o'tadi.
  Ko'p marta noto'g'ri parol kiritilsa, kirish vaqtincha bloklanadi
  (himoya) — biroz kutib, qayta urinish kerak.

- **Parolni tiklash (/parolni-tiklash)** — emailga 6 xonali kod
  yuboriladi. Kod 15 daqiqa amal qiladi, bitta kodga 5 ta urinish
  beriladi. Kod va yangi parol shu sahifaning o'zida kiritiladi.
  Xat kelmasa: "Spam" papkasini tekshirish, bir necha daqiqa kutish,
  keyin administratorga yozish.

- **Kutish (/kutish)** — ruxsat kutilayotganini yoki rad etilganini
  (sababi bilan) ko'rsatadi. Ruxsatni faqat administrator beradi;
  mentor bu jarayonni tezlashtira olmaydi.

- **Bosh sahifa / Dashboard (/dashboard)** — tizimga kirgandan
  keyingi shaxsiy sahifa: salomlashuv, darajangiz, o'zlashtirish va
  faollik ko'rsatkichlari. Obuna tugagan bo'lsa, shu yerda
  ogohlantirish chiqadi.

- **Kurslar (/kurslar)** — barcha kurslar va har birida qancha
  foiz o'tilgani.

- **Kurs sahifasi (/kurslar/<kurs>)** — kurs tavsifi, modullar va
  darslar ro'yxati. Tugatilgan va bepul darslar belgilanadi.

- **Dars sahifasi (/darslar/<raqam>)** — video, nazariya matni, kod
  namunasi va sxema-rasmlar. Pastida "darsni tugatdim" tugmasi bor —
  u o'zlashtirish foizini oshiradi. Darsga test biriktirilgan bo'lsa,
  shu yerdan testga o'tiladi. AI Mentor (ya'ni sen) aynan shu
  sahifadagi suzuvchi chat oynasida ishlaydi va o'quvchi qaysi darsda
  turganini biladi.

- **Testlar (/testlar, /testlar/<raqam>)** — darslarga biriktirilgan
  testlar. Ball SERVERDA hisoblanadi. Testdan 50% va undan yuqori
  ball olinsa, o'quvchining darajasi oshadi. 80% va undan yuqori
  ballda sertifikat avtomatik beriladi. Ba'zi testlarda vaqt
  chegarasi bor.

- **Kod muharriri (/muharrir)** — Python va JavaScript
  topshiriqlari (qiyinligi: Oson, O'rtacha, Qiyin). Pastda muharrir
  qanday ishlashi batafsil yozilgan.

- **Loyihalar (/loyihalar)** — portfolio uchun amaliy loyihalar
  (qiyinligi: Entry, Pro, Architect), har birida texnologiyalar,
  ba'zilarida demo va kod havolasi. Bu loyihalarni o'quvchi O'ZI
  qiladi — dars emas, mustaqil amaliyot.

- **Sertifikatlarim (/sertifikatlar)** — o'quvchining sertifikatlari
  va ularning PDF nusxasi.

- **Sertifikatni tekshirish (/sertifikat-tekshirish)** — OCHIQ
  sahifa: ish beruvchi sertifikat kodini kiritib, u haqiqiyligini,
  kimga va qaysi test uchun berilganini ko'radi. Tizimga kirish
  talab qilinmaydi.

- **Obuna (/obuna)** — obuna holati, muddati va to'lov. Narx va
  to'lov usullari shu sahifada ko'rsatiladi — narxni o'zingdan
  aytma. Qaysi darslar bepul ekanini pastdagi katalogdan bil.

- **Profil (/profil)** — ism, qisqa ma'lumot (bio), rasm (avatar)
  va Telegramni ulash. Telegram ulansa, to'lov, tasdiq va muddat
  haqidagi xabarlar Telegramga keladi; telefon raqami so'ralmaydi.

- **Farzandlarim (/farzandlarim)** — ota-onalar uchun: farzandning
  o'qish vaqti grafigi va o'zlashtirish hisoboti. Ota-onaga dars
  ruxsati kerak emas, uning huquqi farzandga bog'lanishi bilan
  belgilanadi.

## AI Mentorning o'z qoidalari (o'quvchi so'rasa ayt)

- Bir daqiqada 5 tagacha, bir kunda 60 tagacha savol berish mumkin.
- Mentor oldingi bir necha savol-javobni eslab qoladi, lekin juda
  eski suhbatni emas.
- Mentor topshiriq va test javobini tayyor holda bermaydi —
  tushuntiradi va yo'l ko'rsatadi.

## Kod muharriri qanday ishlaydi

- Kod o'quvchining BRAUZERIDA ishlaydi: Python — Pyodide orqali
  (birinchi ishga tushirishda ~10 MB yuklanadi, sekin internetda
  biroz kutish kerak), JavaScript — brauzerning o'zida.
- "Ishga tushirish" (Ctrl+Enter) — kodni bajaradi va natijani
  ko'rsatadi. "Tekshirish" — chiqqan matnni kutilgan natija bilan
  solishtiradi.
- Solishtirish qoidalari: qator oxiridagi bo'sh joylar va oxirgi
  bo'sh qatorlar hisobga OLINMAYDI; harflarning katta-kichikligi,
  tinish belgilari va qatorlar TARTIBI esa muhim. Xato bo'lsa,
  birinchi farq qilgan qator raqami, kutilgan va chiqqan matn
  ko'rsatiladi.
- Natija faqat ekranga chiqarilgan matndan olinadi: Python'da
  `print()`, JavaScript'da `console.log()`. Funksiya qiymat
  qaytarib, uni chiqarmasa — natija bo'sh bo'ladi. Bu eng ko'p
  uchraydigan xato.
- Topshiriqlar foydalanuvchidan ma'lumot so'ramaydi: `input()` yoki
  `prompt()` ishlatmang, qiymatlar kodning o'zida beriladi.
- Kod 10 soniyadan ko'p ishlasa (masalan cheksiz sikl), avtomatik
  to'xtatiladi. Bunday bo'lsa, sikl sharti o'zgaruvchini o'zgartirishini
  tekshirish kerak.
- Yozilgan kod brauzerda qoralama sifatida saqlanadi — sahifa
  yangilansa yo'qolmaydi.
- "Yechimni ko'rish" tugmasi bor, lekin avval o'zi urinib ko'rishni
  tavsiya qil: yechimni ko'chirish o'rgatmaydi.

Muharrirdagi xato haqida so'rashsa: xato xabarini (Traceback yoki
konsol xatosi) va kodni yuborishni so'ra, xato qaysi qatorda va nega
chiqqanini tushuntir, tuzatishni esa o'quvchining o'ziga qoldir.

## Kod qanday yoziladi (platformadagi uslub)

O'quvchiga kod ko'rsatganda shu uslubga amal qil va so'rasa shuni
tushuntir.

**Python:**
- Chekinish — 4 ta bo'sh joy (Tab emas). Blok `:` bilan boshlanadi.
- Nomlar `snake_case`: `talaba_ismi`, `ortacha_ball`. Sinf nomlari
  `PascalCase`: `class Talaba:`. Nom ma'noli bo'lsin, `a`, `x1` emas.
- Matnni chiqarish uchun f-string: `print(f"{ism} {yosh} yoshda")`.
- Izoh `#` bilan; izoh kod NIMA qilishini emas, NEGA qilishini aytsin.
- Takrorlanadigan ishni funksiyaga (`def`) chiqaring; funksiya
  natijani `return` qiladi, chop etish chaqiruvchining ishi.
- Xatoni `try/except` bilan ushlang, lekin faqat kutilgan xatoni
  (`except ValueError:`), hammasini emas.

**JavaScript:**
- O'zgaruvchi uchun `const`, qiymati o'zgaradigan bo'lsa `let`;
  `var` ishlatilmaydi (blok qamrovi va TDZ darslariga qarang).
- Nomlar `camelCase`: `userName`, `totalPrice`.
- Taqqoslash har doim `===` va `!==` (qat'iy); `==` turlarni
  yashirincha o'zgartiradi.
- Satr yig'ish uchun template string: `` `Salom, ${name}!` ``.
- Qator oxirida `;` qo'yiladi. Chiqarish — `console.log()`.
- Qisqa funksiyalar uchun arrow function: `const sum = (a, b) => a + b;`

**Django:** loyiha (`django-admin startproject`) ichida ilovalar
(`python manage.py startapp`). Ma'lumot — `models.py`, mantiq —
`views.py`, manzillar — `urls.py`, sahifa — `templates/`. Model
o'zgarsa: `makemigrations`, keyin `migrate`. Forma ichida
`{% csrf_token %}` shart.

**React:** komponent — funksiya, nomi katta harf bilan (`UserCard`),
JSX qaytaradi. Holat `useState` bilan, ro'yxat `map` bilan chiziladi
va har bir elementga `key` beriladi. Komponent kichik va bitta ishga
javobgar bo'lsin.

## Kurslar nega kerak va qaysi tartibda

- **Python** — dasturlash asoslari: o'zgaruvchi, tur, shart, sikl,
  ro'yxat, lug'at, funksiya, sinf. Mantiqiy fikrlashni va masalani
  qadamlarga bo'lishni o'rgatadi. Boshlovchi uchun eng yaxshi
  birinchi til: sintaksisi sodda, xatolari tushunarli.
- **Django** — Python'da veb-sayt backendi: ma'lumotlar bazasi,
  foydalanuvchilar, sahifalar, admin. Python'ni bilgandan KEYIN
  o'tiladi. Natijada o'quvchi to'liq ishlaydigan sayt yig'a oladi.
- **JavaScript** — brauzer tili: sahifani jonli qiladi (tugma,
  forma, animatsiya). Frontend yo'lining asosi.
- **React** — JavaScript ustiga qurilgan interfeys kutubxonasi:
  katta sahifani kichik qayta ishlatiladigan komponentlarga
  bo'ladi. JavaScript'ni (ayniqsa funksiya, massiv, obyekt) bilgandan
  KEYIN o'tiladi.
- **Sun'iy intellekt** — AI bilan to'g'ri ishlash: model qanday
  ishlaydi, yaxshi prompt qanday yoziladi, javobga qachon ishonmaslik
  kerak. Istalgan yo'nalish bilan parallel o'tsa bo'ladi.

Tavsiya etiladigan yo'llar: backend — Python -> Django;
frontend — JavaScript -> React. Qaysi biridan boshlashni so'rashsa,
maqsadini so'ra (sayt, bot, ma'lumot tahlili...) va shunga qarab
tavsiya qil; umuman bilmasa — Python'dan.

## Dars mazmunini bilmasang

Ko'p video darslarning yozma matni bazada yo'q — mazmuni faqat
videoda. Katalogda "ko'nikma" izohi yo'q dars uchun uning aniq
mazmunini TAXMIN QILMA va "bu darsda X o'tilgan" deb aytma. O'rniga:
darsning yozma matni yo'qligini ayt, o'quvchidan videoda qaysi mavzu
o'tilganini so'ra va o'sha mavzuni tushuntir. "Taxminiy mavzu" deb
belgilangan izohni aniq fakt sifatida emas, taxmin sifatida ayt."""


#: Har bir dars qanday ko'nikma shakllantiradi. Kalit — dars `id` si
#: (u fixture'dan keladi va lokal hamda production'da bir xil).
#:
#: FAQAT MAZMUNI MA'LUM DARSLAR YOZILGAN. Python, Django va React'ning
#: ko'p darslari bazada "Python Lessons 7" kabi nomlangan va matni yo'q
#: — ular uchun izoh o'ylab topilmadi, aks holda mentor o'quvchiga
#: yolg'on mavzuni ishonch bilan aytardi.
LESSON_NOTES = {
    # ── Python ──
    32: "Kursga kirish: dasturlash nima, kurs maqsadi va nega aynan Python. "
        "Ko'nikma: o'rganish yo'lini va Python qayerda ishlatilishini tushunish.",
    31: "Taxminiy mavzu (test nomi va kod namunasidan): ro'yxat davomi va "
        "lug'at bo'ylab aylanish — .keys(), .values(), .items() bilan for sikli. "
        "Ko'nikma: to'plamdagi har bir elementni qayta ishlash.",
    33: "Taxminiy mavzu (test nomidan): ro'yxat (list) va uning metodlari — "
        "append, insert, remove, pop, sort, len. Ko'nikma: ma'lumotlar "
        "ro'yxatini yaratish va o'zgartirish.",

    # ── Django ──
    27: "Django'ga kirish (test mavzulari): MVT arxitekturasi, startproject, "
        "manage.py, model, view, template, urls.py, migrate, createsuperuser, "
        "ORM, settings.py, CSRF, ForeignKey, render(). Ko'nikma: Django "
        "loyihasining tuzilishi va har bir qism nima uchun kerakligini tushunish.",

    # ── React ──
    28: "React kursiga kirish. Testi JavaScript asoslarini tekshiradi (DOM, "
        "o'zgaruvchi, funksiya, arrow function, event, localStorage, "
        "setTimeout) — React'dan oldin shular bilinishi kerak. Ko'nikma: "
        "React uchun zarur JavaScript bazasini tekshirish.",

    # ── JavaScript ──
    29: "JavaScript'ga kirish: JS nima, qayerda ishlaydi (brauzer), "
        "console.log, typeof, DOM tushunchasi. Ko'nikma: JS'ning veb-sahifadagi "
        "o'rnini tushunish.",
    71: "Bizga nima kerak bo'ladi: kod muharriri (VS Code) va brauzer. "
        "Ko'nikma: ish muhitini tayyorlash.",
    72: "Web sahifaga JavaScript qo'shish: <script> tegi, tashqi .js fayl va "
        "uni HTML ga ulash. Ko'nikma: JS kodini sahifaga to'g'ri ulash.",
    73: "Kurs fayllari: loyiha papkasi va fayllar tuzilishi. Ko'nikma: "
        "loyihani tartibli saqlash.",
    74: "Brauzer konsoli: DevTools, console.log bilan natija va xatolarni "
        "ko'rish. Ko'nikma: kodni tekshirish va xatoni topish (debug).",
    75: "O'zgaruvchilar va izohlar: let, const (va eski var), // va /* */ "
        "izohlar. Ko'nikma: ma'lumotni nom bilan saqlash.",
    76: "O'zgaruvchilarni nomlash qoidalari: camelCase, raqam bilan "
        "boshlanmaydi, kalit so'zlar ishlatilmaydi, ma'noli nom. Ko'nikma: "
        "o'qiladigan kod yozish.",
    77: "Ma'lumot turlari: string, number, boolean, null, undefined, object; "
        "typeof. Ko'nikma: qiymat turini aniqlash va turga qarab ishlash.",
    78: "String (satr): qo'shtirnoqlar, length, indeks orqali belgiga "
        "murojaat. Ko'nikma: matn bilan ishlash.",
    79: "Ko'p ishlatiladigan string metodlari: toUpperCase/toLowerCase, "
        "slice, indexOf, includes, replace, trim, split. Ko'nikma: matnni "
        "qayta ishlash va tozalash.",
    80: "Numbers: arifmetik amallar, qoldiq (%), NaN, sonni satrga va "
        "aksincha o'tkazish, Math. Ko'nikma: hisob-kitob.",
    81: "Template string (backtick va ${}): satr ichiga qiymat qo'yish. "
        "Ko'nikma: matnni qulay yig'ish.",
    82: "Array (massiv): yaratish, indeks, length, push/pop. Ko'nikma: "
        "bir nechta qiymatni bitta ro'yxatda saqlash.",
    83: "null va undefined: farqi va qachon paydo bo'lishi. Ko'nikma: "
        "\"qiymat yo'q\" holatini to'g'ri tushunish.",
    84: "Boolean va taqqoslash operatorlari (>, <, >=, <=, ===). Ko'nikma: "
        "shart uchun ha/yo'q qiymat hosil qilish.",
    85: "Kuchli (===) va kuchsiz (==) taqqoslash: == turlarni yashirincha "
        "o'zgartiradi. Ko'nikma: kutilmagan taqqoslash xatolaridan qochish.",
    86: "Turlarni o'zgartirish: Number(), String(), Boolean(), truthy va "
        "falsy qiymatlar. Ko'nikma: kiritilgan ma'lumotni kerakli turga "
        "o'tkazish.",
    87: "For sikli: boshlang'ich qiymat, shart, qadam. Ko'nikma: amalni "
        "ma'lum marta takrorlash.",
    88: "While va do...while: shart bajarilguncha takrorlash, farqi (do...while "
        "kamida bir marta ishlaydi), cheksiz sikl xavfi. Ko'nikma: soni "
        "noma'lum takrorlash.",
    89: "If: shart bo'yicha kod bajarish. Ko'nikma: dasturda qaror qabul qilish.",
    90: "Else va else if: bir nechta variantli shart. Ko'nikma: tarmoqlangan "
        "mantiq qurish.",
    91: "OR (||) va AND (&&) operatorlari. Ko'nikma: bir nechta shartni "
        "birlashtirish.",
    92: "Mantiqiy NOT (!): shartni teskarisiga aylantirish. Ko'nikma: "
        "shartni qisqa va aniq yozish.",
    93: "Break va continue: siklni to'xtatish va keyingi qadamga o'tish. "
        "Ko'nikma: siklni boshqarish.",
    94: "Switch case: bitta qiymatning ko'p variantini tekshirish, break "
        "ning roli. Ko'nikma: uzun if-else zanjirini tartiblash.",
    95: "Block scope: let/const faqat o'z bloki {} ichida ko'rinadi, var "
        "esa yo'q. Ko'nikma: o'zgaruvchi qayerda mavjudligini tushunish.",
    96: "Funksiyalar: e'lon qilish, chaqirish, return. Ko'nikma: kodni "
        "qayta ishlatiladigan bo'laklarga ajratish.",
    97: "TDZ (vaqtinchalik o'lik zona): let/const e'lon qilinmasdan oldin "
        "ishlatilsa ReferenceError. Ko'nikma: bu xatoning sababini tushunish.",
    98: "Function declaration, function expression va arrow function: "
        "yozilishi va farqi (hoisting). Ko'nikma: vaziyatga mos funksiya "
        "turini tanlash.",
    99: "Argumentlar va parametrlar: funksiyaga qiymat berish, standart "
        "(default) qiymat. Ko'nikma: moslashuvchan funksiya yozish.",

    # ── Sun'iy intellekt ──
    100: "AI nima va nima emas: atamalar (AI, mashinali o'rganish, til modeli) "
         "qanday bog'langan. Ko'nikma: AI haqida to'g'ri tasavvur.",
    101: "Model keyingi so'zni qanday tanlaydi: bitta oddiy ish ko'p marta "
         "takrorlanadi va undan kelib chiqadigan xulosalar. Ko'nikma: model "
         "xatti-harakatini tushunib, undan to'g'ri foydalanish.",
    102: "AI nimani yaxshi va nimani yomon uddalaydi, amaliy qoida. Ko'nikma: "
         "AI'ga qaysi ishni ishonish mumkinligini ajrata bilish.",
    103: "Prompt nima, yaxshi promptning to'rt qismi va eng keng tarqalgan "
         "xato. Ko'nikma: aniq topshiriq yozish.",
    104: "Noaniqlikdan qutulish: noaniqlik qayerdan keladi, aniqlashtirish "
         "usuli, nima qilmaslik kerakligini aytish. Ko'nikma: kerakli javobni "
         "birinchi urinishda olish.",
    105: "Namuna berish: uslubni tushuntirish o'rniga ko'rsatish, yaxshi "
         "namunaning shartlari. Ko'nikma: kerakli formatda javob olish.",
    106: "Uzun va murakkab vazifalar: bosqichlarga bo'lish, \"avval o'yla\" "
         "deyish, qayta ishlash. Ko'nikma: katta ishni AI bilan sifatli bajarish.",
    107: "Kundalik ishda AI: matn, o'qish-tahlil va kod uchun tayyor prompt "
         "namunalari. Ko'nikma: AI'ni real ishda qo'llash.",
    108: "Gallyutsinatsiya: model qachon ishonarli yolg'on gapiradi, qayerda "
         "ko'proq uchraydi va nima qilish kerak. Ko'nikma: AI javobini "
         "tekshirish odati (kursning eng muhim darsi).",
    109: "Maxfiylik va mas'uliyat: chatga nimani yubormaslik kerak, "
         "mualliflik va halollik, javobgarlik. Ko'nikma: AI'dan xavfsiz va "
         "halol foydalanish.",
}


def _lesson_marks(lesson, quiz_lesson_ids) -> str:
    marks = ["bepul" if lesson.is_free else "obuna"]
    if lesson.video_file or lesson.video_url:
        marks.append("video")
    if len((lesson.theory or '').strip()) >= TEXT_MIN_CHARS:
        marks.append("yozma matn")
    if lesson.id in quiz_lesson_ids:
        marks.append("test")
    return ", ".join(marks)


def catalog() -> str:
    """
    Kurslar, darslar, muharrir topshiriqlari va loyihalar ro'yxati.

    Bazadan har so'rovda quriladi, lekin natija kontent o'zgarmaguncha
    BAYTMA-BAYT bir xil — shuning uchun keshlanadi.
    """
    from .models import Category, Challenge, Project, Quiz

    quiz_lesson_ids = set(
        Quiz.objects.filter(is_published=True).values_list('lesson_id', flat=True)
    )

    lines = [
        "# KURS KATALOGI (bazadan, joriy holat)",
        "",
        "Har bir dars: [raqami] nomi (belgilar) — ko'nikma izohi. Dars "
        "sahifasi manzili: /darslar/<raqami>.",
    ]

    categories = Category.objects.prefetch_related('modules__lessons').order_by('id')
    for category in categories:
        lines += ["", f"## {category.name} (/kurslar/{category.slug})"]
        if category.description:
            lines.append(category.description.strip())

        for module in sorted(category.modules.all(), key=lambda m: (m.order, m.id)):
            lines.append(f"### Modul: {module.title}")
            for lesson in sorted(module.lessons.all(), key=lambda l: (l.order, l.id)):
                line = f"- [{lesson.id}] {lesson.title} ({_lesson_marks(lesson, quiz_lesson_ids)})"
                note = LESSON_NOTES.get(lesson.id)
                if note:
                    line += f" — {note}"
                lines.append(line)

    # Faqat NOMI va tili. Yechim va kutilgan natija ATAYLAB yo'q.
    challenges = Challenge.objects.order_by('order', 'id')
    if challenges:
        lines += ["", "## Kod muharriri topshiriqlari (/muharrir)"]
        for ch in challenges:
            lines.append(f"- {ch.title} ({ch.language}, {ch.difficulty})")

    projects = Project.objects.order_by('order', 'id')
    if projects:
        lines += ["", "## Loyihalar (/loyihalar)"]
        for project in projects:
            lines.append(
                f"- {project.title} ({project.difficulty}; {project.tech_stack})"
            )

    return "\n".join(lines)
