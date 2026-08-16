"""
«Sun'iy intellekt va prompt engineering» kursining mazmuni
==========================================================

BU FAYL — MA'LUMOT, KOD EMAS. Shuning uchun `seed_ai_course` dan
ajratilgan: matn tahrirlanganda buyruq mantig'iga umuman tegilmaydi.

Nomi `_` bilan boshlangani ham ataylab: Django `management/commands/`
ichidagi shunday fayllarni buyruq deb hisoblamaydi.

MATN FORMATI — `core/richtext.py` qo'llab-quvvatlaydigan oddiy belgilar.
HTML yozilmaydi: u ekranlanadi va matn bo'lib ko'rinib qoladi.

TEST SAVOLLARI QOIDASI:
  * har savolda ROPPA-ROSA bitta to'g'ri javob
  * noto'g'ri variantlar ham ishonarli bo'lsin — "hammasi to'g'ri" yoki
    kulgili variant testni ma'nosiz qiladi
  * javob dars matnidan chiqsin, umumiy bilimdan emas
"""

#: Bo'lim
CATEGORY = {
    'name': "Sun'iy intellekt",
    'slug': 'ai',
    'description': (
        "Sun'iy intellekt bilan ishlashni noldan o'rganish: model qanday "
        "ishlaydi, unga qanday topshiriq berish kerak va javobga qachon "
        "ishonmaslik lozim."
    ),
}

#: Modullar va darslar.
#:
#: `image` — `core/diagrams.py` dagi sxema nomi (bo'lsa).
#: `free`  — bepul darsmi. ATAYLAB kam: birinchi modul ochiq, qolgani
#:           obuna bilan. Hammasi bepul bo'lsa kursning savdo qiymati
#:           qolmaydi; hech biri bepul bo'lmasa odam nima sotib
#:           olayotganini ko'rmaydi.
MODULES = [
    # ══════════════════════════════════════════════════════════════
    {
        'title': "Sun'iy intellekt asoslari",
        'order': 1,
        'lessons': [
            {
                'title': "Sun'iy intellekt nima va nima emas",
                'free': True,
                'image': 'ai_ml_llm',
                'image_caption': "Sun'iy intellekt, mashinaviy o'qitish va til modeli — biri ikkinchisining ichida",
                'theory': """
Sun'iy intellekt haqida ikki xil noto'g'ri tasavvur bor. Birinchisi —
"bu shunchaki reklama, hech qanday foydasi yo'q". Ikkinchisi — "bu
hamma narsani biladigan aql". Ikkalasi ham xato, va ikkalasi ham
ishlashga xalaqit beradi.

## Aslida nima bo'lyapti

Bugungi chatbotlar **til modellari** ustiga qurilgan. Til modeli — bu
juda ko'p matnni o'qib chiqqan va shu matnlardagi qonuniyatlarni
o'zlashtirgan dastur.

U ma'lumotlar bazasidan javob **qidirmaydi**. Uning ichida "javoblar
ro'yxati" yo'q. U har safar javobni **qaytadan yozadi** — so'zma-so'z,
o'zi o'rgangan qonuniyatlarga tayanib.

Shuning uchun:

- bir xil savolga ikki marta biroz boshqacha javob berishi mumkin
- hech qachon uchramagan savolga ham javob yozadi
- javob **chiroyli ko'rinishi** uning **to'g'riligini bildirmaydi**

## Atamalar bir-biriga qanday bog'langan

Ko'pincha bu so'zlar aralashtirib yuboriladi:

- **Sun'iy intellekt (AI)** — eng keng tushuncha. Odam aqli talab
  qiladigan ishni bajaradigan har qanday dastur.
- **Mashinaviy o'qitish** — AI ning bir turi. Dasturchi qoidalarni
  yozmaydi, dastur misollardan o'zi o'rganadi.
- **Til modeli (LLM)** — matn bilan ishlaydigan tur. ChatGPT, Claude,
  Gemini — hammasi shu.

Bir-birining ichida turgan doiralar deb tasavvur qiling: har biri
o'zidan kattasining bir qismi.

## Bu nimani anglatadi

Til modeli — bu **asbob**, xodim emas. Bolg'a mixni o'zi qoqmaydi;
qayerga urishni siz ko'rsatasiz. Model ham xuddi shunday: natija
sizning topshirig'ingizga bog'liq.

Kursning qolgan qismi aynan shu haqda — topshiriqni qanday berish
kerakligi haqida.

> Eng muhim xulosa: model o'ylamaydi, u matn yozadi. Javobni
> tekshirish har doim sizning zimmangizda qoladi.
""",
                'quiz': {
                    'title': "Sun'iy intellekt asoslari",
                    'questions': [
                        {
                            'text': "Til modeli javobni qayerdan oladi?",
                            'choices': [
                                ("O'rgangan qonuniyatlariga tayanib har safar qaytadan yozadi", True),
                                ("Tayyor javoblar bazasidan qidirib topadi", False),
                                ("Internetdan mos sahifani ko'chiradi", False),
                                ("Oldingi foydalanuvchilarning javoblarini takrorlaydi", False),
                            ],
                        },
                        {
                            'text': "Nima uchun model bir savolga ikki xil javob berishi mumkin?",
                            'choices': [
                                ("Javobni har safar qaytadan yozgani uchun", True),
                                ("Serverda xatolik borligi uchun", False),
                                ("Foydalanuvchini chalg'itish uchun", False),
                                ("Bazadagi yozuv o'zgargani uchun", False),
                            ],
                        },
                        {
                            'text': "Sun'iy intellekt, mashinaviy o'qitish va til modeli o'zaro qanday bog'langan?",
                            'choices': [
                                ("Til modeli mashinaviy o'qitishning, u esa sun'iy intellektning bir qismi", True),
                                ("Uchtasi bir xil narsaning uch xil nomi", False),
                                ("Ular bir-biriga bog'liq bo'lmagan uch xil texnologiya", False),
                                ("Sun'iy intellekt til modelining bir qismi", False),
                            ],
                        },
                        {
                            'text': "Javobning chiroyli va ishonarli yozilgani nimani bildiradi?",
                            'choices': [
                                ("Hech narsani — to'g'riligini alohida tekshirish kerak", True),
                                ("Javob to'g'ri ekanini", False),
                                ("Model manbani tekshirganini", False),
                                ("Savol to'g'ri berilganini", False),
                            ],
                        },
                    ],
                },
            },
            {
                'title': "Model keyingi so'zni qanday tanlaydi",
                'free': True,
                'image': 'next_token',
                'image_caption': "Model har bir so'zni ehtimollikka qarab tanlaydi",
                'theory': """
Oldingi darsda model javobni "qaytadan yozadi" dedik. Endi buni biroz
chuqurroq ko'ramiz — chunki modelning deyarli barcha g'alati
xatti-harakati shundan kelib chiqadi.

## Bitta oddiy ish, ko'p marta takrorlangan

Til modeli aslida **bitta** ish qiladi: berilgan matndan keyin qaysi
so'z kelishini taxmin qiladi.

"Bugun havo juda ..." degan matndan keyin nima kelishi mumkin? Model
har bir ehtimolni baholaydi: *issiq* — ehtimoli yuqori, *sovuq* — ham
yuqori, *yaxshi* — o'rtacha, *qora* — deyarli nol.

Keyin bittasini tanlaydi, uni matnga qo'shadi va **hammasini
boshqatdan** qiladi. Butun javob ana shunday, so'zma-so'z quriladi.

## Bundan kelib chiqadigan uchta narsa

**1. Javob har safar boshqacha.** Model har doim eng ehtimolli so'zni
tanlamaydi — biroz tasodifiylik bor. Busiz javoblar quruq va bir xil
bo'lardi.

**2. Model "bilmayman" deyishga moyil emas.** U keyingi so'zni
taxmin qiladi, "menda bu ma'lumot yo'q" degan holat uning uchun
alohida holat emas. Shuning uchun bilmagan narsasini ham **ishonch
bilan** yozib yuboradi. Buni *gallyutsinatsiya* deyishadi va bu
alohida darsning mavzusi.

**3. Boshlanish davomini belgilaydi.** Javobning birinchi jumlasi
qolganini tortadi. Aynan shuning uchun promptning boshi — rol va
vazifa — shunchalik kuchli ta'sir qiladi.

## Amaliy xulosa

Model — ehtimollik mashinasi. Siz unga qanday boshlanish bersangiz, u
shu boshlanishga eng mos davomni quradi.

Demak sizning ishingiz — **to'g'ri boshlanish berish**. Bu prompt
engineering degani.

> Model sizning fikringizni o'qimaydi. U faqat yozganingizni ko'radi.
""",
                'quiz': {
                    'title': "Model qanday ishlaydi",
                    'questions': [
                        {
                            'text': "Til modeli asosan qanday ishni bajaradi?",
                            'choices': [
                                ("Berilgan matndan keyin qaysi so'z kelishini taxmin qiladi", True),
                                ("Savolni tahlil qilib bazadan javob tanlaydi", False),
                                ("Matnni tarjima qilib qidiruvga yuboradi", False),
                                ("Javobni oldindan tayyorlab qo'yadi", False),
                            ],
                        },
                        {
                            'text': "Nima uchun model «bilmayman» deyish o'rniga xato javob yozadi?",
                            'choices': [
                                ("«Bilmayman» — bu uning uchun alohida holat emas, u faqat davomni taxmin qiladi", True),
                                ("Dasturchilar bunday javobni taqiqlagan", False),
                                ("U foydalanuvchini xursand qilishga harakat qiladi", False),
                                ("Bazada bo'sh javob saqlanmaydi", False),
                            ],
                        },
                        {
                            'text': "Nima uchun promptning boshi javobga kuchli ta'sir qiladi?",
                            'choices': [
                                ("Model har bir keyingi so'zni oldingi matnga qarab tanlaydi", True),
                                ("Model faqat birinchi jumlani o'qiydi", False),
                                ("Boshidagi so'zlar ko'proq to'lanadi", False),
                                ("Oxirgi jumlalar e'tiborsiz qoldiriladi", False),
                            ],
                        },
                    ],
                },
            },
            {
                'title': "AI nimani uddalaydi, nimani uddalay olmaydi",
                'free': False,
                'theory': """
Kutgan narsangiz noto'g'ri bo'lsa, natijadan doim hafsalangiz pir
bo'ladi. Shuning uchun bu darsda chegaralarni aniq belgilab olamiz.

## Yaxshi uddalaydigan ishlar

**Matnni o'zgartirish.** Uzunni qisqartirish, rasmiyni soddaga
aylantirish, qoralamani tartibga solish, uslubni almashtirish. Bu yerda
model kuchli, chunki manba matn allaqachon sizda.

**Qoralama yozish.** Bo'sh sahifadan boshlash eng qiyin qismi. Model
30 soniyada o'rtacha qoralama beradi — siz uni tuzatasiz. Bu noldan
yozishdan tezroq.

**Tushuntirish.** Tushunmagan mavzuni sodda tilda, misollar bilan
tushuntirish. Ayniqsa "buni 12 yoshli bolaga tushuntir" kabi
so'rovlarda yaxshi ishlaydi.

**Ro'yxat va variantlar.** "20 ta sarlavha varianti ber" — model
charchamaydi va uyalmaydi. Siz eng yaxshisini tanlaysiz.

**Tuzilgan matnga aylantirish.** Tartibsiz eslatmalarni jadvalga,
uzun matnni qisqa bandlarga.

## Yomon uddalaydigan ishlar

**Aniq faktlar.** Sana, raqam, statistika, qonun moddasi, narx. Model
buni **to'qib chiqarishi** mumkin va qaysi biri to'qilganini o'zi ham
aytmaydi.

**Yangi voqealar.** Modelning bilimi ma'lum sanada to'xtaydi. Undan
keyingi voqealarni bilmaydi — lekin baribir javob yozib berishi
mumkin.

**Murakkab hisob-kitob.** U raqamlarni ham matn kabi taxmin qiladi.
Oddiy amallarda adashadi. Hisob uchun kalkulyator ishlating.

**Sizning kontekstingiz.** Model kompaniyangizni, mijozlaringizni,
kelishuvlaringizni bilmaydi. Aytmasangiz — bilmaydi.

**Mas'uliyatli qaror.** Tibbiy tashxis, huquqiy xulosa, moliyaviy
qaror. Model bularda maslahatchi ham emas — u shunchaki ishonarli
matn yozuvchi.

## Amaliy qoida

Ishni ikkiga bo'ling:

- **Modelga bering:** matn bilan ishlash, variantlar, qoralama
- **O'zingizda qoldiring:** faktlarni tekshirish, qaror qabul qilish,
  yakuniy javobgarlik

> Model — bu tez, arzon va charchamaydigan yordamchi. Lekin uning
> ishini har doim kimdir tekshirishi kerak, va bu kimdir — siz.
""",
                'quiz': {
                    'title': "AI ning imkoniyatlari va chegaralari",
                    'questions': [
                        {
                            'text': "Quyidagilardan qaysi biri til modeli eng yaxshi uddalaydigan ish?",
                            'choices': [
                                ("Uzun matnni qisqartirish va uslubini o'zgartirish", True),
                                ("Aniq statistik raqamlarni eslab qolish", False),
                                ("Murakkab matematik hisob-kitob", False),
                                ("Kecha bo'lgan voqeani aytib berish", False),
                            ],
                        },
                        {
                            'text': "Nima uchun modeldan aniq sana va raqam so'rash xavfli?",
                            'choices': [
                                ("U ularni to'qib chiqarishi va buni bildirmasligi mumkin", True),
                                ("Raqamlarni umuman yoza olmaydi", False),
                                ("Bunday savollarga javob berish taqiqlangan", False),
                                ("Raqamlar juda ko'p joy egallaydi", False),
                            ],
                        },
                        {
                            'text': "Model sizning kompaniyangiz haqidagi ma'lumotni qayerdan oladi?",
                            'choices': [
                                ("Faqat siz promptda yozib bergan joydan", True),
                                ("Kompaniya saytidan avtomatik o'qiydi", False),
                                ("Oldingi suhbatlaringizdan doimiy eslab qoladi", False),
                                ("Ochiq reyestrlardan qidirib topadi", False),
                            ],
                        },
                        {
                            'text': "Nima uchun hisob-kitobni modelga ishonib bo'lmaydi?",
                            'choices': [
                                ("U raqamlarni ham matn kabi taxmin qiladi, hisoblamaydi", True),
                                ("Hisob-kitob juda ko'p vaqt oladi", False),
                                ("Matematik amallar bloklangan", False),
                                ("U faqat butun sonlar bilan ishlaydi", False),
                            ],
                        },
                    ],
                },
            },
        ],
    },
    # ══════════════════════════════════════════════════════════════
    {
        'title': "Prompt engineering",
        'order': 2,
        'lessons': [
            {
                'title': "Prompt nima va yaxshi prompt qanday bo'ladi",
                'free': True,
                'image': 'prompt_anatomy',
                'image_caption': "Yaxshi promptning to'rt qismi: rol, vazifa, kontekst, format",
                'theory': """
**Prompt** — bu modelga bergan topshirig'ingiz. Xolos. Sirli hech narsa
yo'q.

Lekin bir xil savolni ikki xil qilib berish natijani tubdan
o'zgartiradi. Farqi shunda: birinchisi topshiriq, ikkinchisi shunchaki
so'z.

## To'rt qism

Yaxshi promptda odatda to'rttasi bo'ladi. Hammasi har doim shart
emas, lekin qanchasi bo'lsa — javob shunchalik aniq.

**1. Rol.** Model kim bo'lib javob bersin.
`Sen 5-sinf o'qituvchisisan.`

**2. Vazifa.** Aniq nima qilish kerak.
`Fotosintezni tushuntir.`

**3. Kontekst.** Qanday sharoitda, kim uchun.
`O'quvchilar 11 yoshda, biologiyani endi boshlagan.`

**4. Format.** Javob qanday ko'rinishda bo'lsin.
`5 ta qisqa band, har biriga kundalik hayotdan misol.`

Hammasini birlashtiring:

```
Sen 5-sinf o'qituvchisisan. 11 yoshli o'quvchilarga fotosintezni
tushuntir. Ular biologiyani endi boshlagan. Javobni 5 ta qisqa
bandda ber, har biriga kundalik hayotdan misol qo'sh.
```

Buni `Fotosintez haqida yoz` bilan solishtiring. Farqi katta.

## Nega bu ishlaydi

Oldingi darsdan eslang: model keyingi so'zni oldingi matnga qarab
tanlaydi. Siz qancha ko'p aniqlik bersangiz, u shunchalik tor va
mos yo'ldan boradi.

`Marketing haqida yoz` — model qaysi biznes, qaysi bozor, qaysi
byudjet haqida yozishini bilmaydi. U hammaga mos, demak hech kimga
kerak bo'lmagan matn yozadi.

## Eng keng tarqalgan xato

Odamlar modeldan **fikrni o'qishini** kutishadi. Ular boshlarida
aniq tasavvur bilan `Menga matn yoz` deb yozishadi va javob
kutganidek chiqmaganda hafsalasi pir bo'ladi.

Model sizning boshingizdagini ko'rmaydi. Faqat yozganingizni ko'radi.

> Qoida: promptni o'qib chiqing va o'zingizdan so'rang — "buni
> mavzuni bilmaydigan odam o'qisa, nima qilishni tushunarmidi?"
> Tushunmasa, model ham tushunmaydi.
""",
                'quiz': {
                    'title': "Prompt asoslari",
                    'questions': [
                        {
                            'text': "Prompt nima?",
                            'choices': [
                                ("Modelga berilgan topshiriq", True),
                                ("Modelning ichki sozlamasi", False),
                                ("Javobni tekshiruvchi dastur", False),
                                ("Model o'rgangan ma'lumotlar to'plami", False),
                            ],
                        },
                        {
                            'text': "«Sen 5-sinf o'qituvchisisan» — bu promptning qaysi qismi?",
                            'choices': [
                                ("Rol", True),
                                ("Vazifa", False),
                                ("Format", False),
                                ("Kontekst", False),
                            ],
                        },
                        {
                            'text': "«Javobni 5 ta qisqa bandda ber» — bu qaysi qism?",
                            'choices': [
                                ("Format", True),
                                ("Rol", False),
                                ("Kontekst", False),
                                ("Vazifa", False),
                            ],
                        },
                        {
                            'text': "Nima uchun «Marketing haqida yoz» yomon prompt?",
                            'choices': [
                                ("Qaysi biznes, bozor va byudjet haqida ekani ko'rsatilmagan", True),
                                ("Juda qisqa yozilgan", False),
                                ("Model marketingni bilmaydi", False),
                                ("Unda buyruq mayli ishlatilgan", False),
                            ],
                        },
                        {
                            'text': "Promptni tekshirishning eng oddiy usuli qaysi?",
                            'choices': [
                                ("Mavzuni bilmaydigan odam o'qisa tushunarmidi deb ko'rish", True),
                                ("Uzunligini sanash", False),
                                ("Bir necha modelda sinash", False),
                                ("Imlo xatolarini tekshirish", False),
                            ],
                        },
                    ],
                },
            },
            {
                'title': "Noaniqlikdan qutulish",
                'free': False,
                'image': 'vague_vs_clear',
                'image_caption': "Bir xil mavzu, ikki xil natija",
                'theory': """
Yomon javobning eng ko'p uchraydigan sababi — yomon savol. Bu darsda
noaniqlikni topish va yo'qotishni o'rganamiz.

## Noaniqlik qayerdan keladi

Uch joydan:

**1. Aytilmagan maqsad.** `Xat yoz` — nima uchun? Uzr so'rashmi,
taklif qilishmi, rad etishmi? Model tanlaydi, va odatda siz
o'ylagandek tanlamaydi.

**2. Aytilmagan auditoriya.** `Tushuntir` — kimga? Boshlovchigami yoki
mutaxassisgami? Bu javobni butunlay o'zgartiradi.

**3. Aytilmagan cheklovlar.** Uzunligi, tili, uslubi, nimani
ishlatmaslik kerakligi.

## Aniqlashtirish usuli

Promptni yozgandan keyin uchta savol bering:

- **Kim uchun?** — auditoriya
- **Nima uchun?** — maqsad
- **Qanday ko'rinishda?** — format va hajm

Javobi promptda yo'q bo'lsa — qo'shing.

### Misol

Noaniq:
```
Mijozga xat yoz.
```

Aniqlashtirilgan:
```
Mijozga xat yoz. Biz yetkazib berishni ikki kunga kechiktirdik.
Maqsad — uzr so'rash va yangi sanani aytish, mijozni yo'qotmaslik.
Uslub: samimiy, ortiqcha rasmiyatchiliksiz.
Uzunligi: 5-6 jumla. Bahona izlamang, faktni ayting.
```

Ikkinchisi uzunroq, lekin **bir marta** yoziladi va **darhol**
ishlatsa bo'ladigan javob beradi.

## Nima qilmaslik kerakligini ham ayting

Bu ko'pincha unutiladi, lekin juda kuchli:

- `Klishe iboralar ishlatma.`
- `Kirish so'z yozma, to'g'ridan-to'g'ri mavzuga o't.`
- `Ma'lumot yetarli bo'lmasa, to'qib yozma — so'rab ol.`

Oxirgisi ayniqsa foydali: model taxmin qilish o'rniga sizdan
aniqlashtiruvchi savol beradi.

## Qisqa prompt ham yaxshi bo'lishi mumkin

Uzunlik o'z-o'zidan sifat emas. `Bu jumlani qisqartir: ...` — qisqa
va mukammal prompt, chunki unda noaniqlik yo'q.

Maqsad — **uzun yozish** emas, **noaniqlikni yo'qotish**.

> Vaqtingizni promptga sarflang. Yomon promptni tuzatishga ketgan
> vaqt, uni boshidan yaxshi yozishga ketadigan vaqtdan ko'p.
""",
                'quiz': {
                    'title': "Aniq prompt yozish",
                    'questions': [
                        {
                            'text': "Yomon javobning eng ko'p uchraydigan sababi nima?",
                            'choices': [
                                ("Noaniq yozilgan prompt", True),
                                ("Modelning eskirgan versiyasi", False),
                                ("Internet tezligi", False),
                                ("Savolning juda qisqaligi", False),
                            ],
                        },
                        {
                            'text': "Promptni tekshirish uchun beriladigan uchta savol qaysi?",
                            'choices': [
                                ("Kim uchun? Nima uchun? Qanday ko'rinishda?", True),
                                ("Qachon? Qayerda? Necha marta?", False),
                                ("Qancha turadi? Kim to'laydi? Qachon tayyor?", False),
                                ("Kim yozdi? Qachon yozildi? Nima uchun kerak?", False),
                            ],
                        },
                        {
                            'text': "«Ma'lumot yetarli bo'lmasa, to'qib yozma — so'rab ol» ko'rsatmasi nima beradi?",
                            'choices': [
                                ("Model taxmin qilish o'rniga aniqlashtiruvchi savol beradi", True),
                                ("Model javob berishdan bosh tortadi", False),
                                ("Javob avtomatik qisqaradi", False),
                                ("Model internetdan ma'lumot qidiradi", False),
                            ],
                        },
                        {
                            'text': "Uzun prompt har doim yaxshiroqmi?",
                            'choices': [
                                ("Yo'q — maqsad uzunlik emas, noaniqlikni yo'qotish", True),
                                ("Ha, prompt qancha uzun bo'lsa shuncha yaxshi", False),
                                ("Ha, chunki model uzun matnni yaxshi tushunadi", False),
                                ("Yo'q, prompt har doim bir jumladan iborat bo'lishi kerak", False),
                            ],
                        },
                    ],
                },
            },
            {
                'title': "Namuna berish — uslubni ko'rsatish",
                'free': False,
                'image': 'few_shot',
                'image_caption': "Ikki namunadan keyin model uslubni o'zi tushunadi",
                'theory': """
Ba'zan kerakli uslubni **tushuntirish** qiyin, lekin **ko'rsatish**
oson. Shu paytda namuna beriladi.

## Muammo

Aytaylik, mahsulot tavsiflari kerak. Siz yozasiz:

```
Mahsulot tavsifini yoz: simsiz quloqchin.
```

Model uzun, reklama uslubidagi, "innovatsion yechim" degan iboralar
bilan to'la matn beradi. Sizga esa qisqa va sodda kerak.

Uslubni so'z bilan tasvirlashga urinasiz: "qisqa yoz", "sodda yoz",
"reklama uslubida bo'lmasin"... har safar biror narsa mos kelmaydi.

## Yechim: ko'rsating

```
Quyidagi uslubda davom ettir:

Mahsulot: termos
Tavsif: Choyingiz 12 soat issiq qoladi.

Mahsulot: noutbuk sumkasi
Tavsif: Yomg'irda ham quruq, yelkangizda yengil.

Mahsulot: simsiz quloqchin
Tavsif:
```

Model ikki namunadan uslubni o'zi ajratib oladi: bitta jumla,
foyda haqida, "siz"ga murojaat, sifatlar ko'p emas.

Buni ingliz tilida **few-shot** deyishadi — "bir necha namuna".

## Qachon namuna berish kerak

Namuna eng ko'p foyda beradigan holatlar:

- **Aniq format kerak** — jadval, JSON, ma'lum tuzilishdagi matn
- **Uslub muhim** — brend ovozi, muayyan ohang
- **Vazifa g'ayrioddiy** — model bunday ishni kam ko'rgan
- **Tushuntirish uzoq chiqadi** — namuna qisqaroq

## Yaxshi namunaning shartlari

**Ikki-uchta yetarli.** Bittasi tasodif bo'lib ko'rinadi, o'ntasi
o'rniga vaqt ketadi.

**Bir-biridan farq qilsin.** Uchta juda o'xshash namuna bergan
bo'lsangiz, model faqat o'sha tor holatni takrorlaydi.

**Namunalar to'g'ri bo'lsin.** Model xatoni ham nusxa oladi. Namunada
xato bo'lsa, u javoblarga ko'chadi.

**Format bir xil bo'lsin.** `Mahsulot:` / `Tavsif:` — har namunada
aynan bir xil. Model tuzilishni ham nusxa oladi.

## Kichik hiyla

Namunani oxirida **yarim qoldiring** — yuqoridagi misolda `Tavsif:`
dan keyin bo'sh joy. Model bo'shliqni to'ldirishga tushadi va kirish
so'zlar yozmaydi.

> Uzun tushuntirishdan ko'ra ikkita yaxshi namuna kuchliroq ishlaydi.
""",
                'quiz': {
                    'title': "Namuna berish",
                    'questions': [
                        {
                            'text': "Namuna berish (few-shot) nima uchun ishlatiladi?",
                            'choices': [
                                ("Kerakli uslub va formatni tushuntirish o'rniga ko'rsatish uchun", True),
                                ("Modelni doimiy o'rgatib qo'yish uchun", False),
                                ("Javobni tezlashtirish uchun", False),
                                ("Model xatosini tuzatish uchun", False),
                            ],
                        },
                        {
                            'text': "Odatda nechta namuna yetarli?",
                            'choices': [
                                ("Ikki-uchta", True),
                                ("Kamida o'nta", False),
                                ("Bitta", False),
                                ("Qancha ko'p bo'lsa shuncha yaxshi", False),
                            ],
                        },
                        {
                            'text': "Namunada xato bo'lsa nima bo'ladi?",
                            'choices': [
                                ("Model xatoni ham nusxa oladi va javoblarga ko'chiradi", True),
                                ("Model xatoni o'zi tuzatadi", False),
                                ("Model namunani e'tiborsiz qoldiradi", False),
                                ("Hech narsa — namuna faqat uslub uchun", False),
                            ],
                        },
                        {
                            'text': "Nima uchun namunalar bir-biridan farq qilishi kerak?",
                            'choices': [
                                ("Juda o'xshash namunalarda model faqat o'sha tor holatni takrorlaydi", True),
                                ("Bir xil namunalar xatolikka olib keladi", False),
                                ("Model takrorlanishni yoqtirmaydi", False),
                                ("Farqli namunalar kamroq joy egallaydi", False),
                            ],
                        },
                    ],
                },
            },
            {
                'title': "Uzun va murakkab vazifalar",
                'free': False,
                'image': 'iteration_loop',
                'image_caption': "Prompt bir martada emas, bir necha urinishda tayyor bo'ladi",
                'theory': """
Katta vazifani bitta promptda so'rasangiz, natija odatda yuzaki
chiqadi. Buning sababi bor va yechimi ham bor.

## Nega katta vazifa yuzaki bajariladi

Model javobni so'zma-so'z quradi va oldinga qarab reja tuzmaydi. Katta
vazifada u boshini yozib, keyin o'sha boshlanishga moslashib ketadi —
umumiy tuzilish esa o'ylanmay qoladi.

## Yechim 1: bosqichlarga bo'ling

Bitta katta so'rov o'rniga ketma-ket bir necha so'rov:

1. `Avval maqola uchun reja tuz. Faqat reja, matn yozma.`
2. Rejani ko'rib chiqasiz, tuzatasiz.
3. `Endi 2-bo'limni yoz.`

Har bosqichda siz nazorat qilasiz. Xato bo'lsa — o'sha bosqichda
tuzatiladi, oxirida hammasini qaytadan yozish kerak bo'lmaydi.

## Yechim 2: "avval o'yla" deb ayting

Modeldan javobdan **oldin** mulohaza yuritishni so'rash mumkin:

```
Avval qanday yondashishni bosqichma-bosqich yoz,
keyin yakuniy javobni ber.
```

Bu sodda hiyla murakkab vazifalarda sezilarli farq qiladi: model
mulohazani ham matn sifatida yozgani uchun, keyingi qadamlar shu
mulohazaga tayanadi.

## Yechim 3: qayta ishlang

Prompt bir martada tayyor bo'lmaydi. Odatiy jarayon:

1. **Yozasiz** — birinchi variant
2. **O'qiysiz** — javob nimasi bilan mos kelmadi
3. **Aniqlaysiz** — aynan nima yetishmadi
4. **Qo'shasiz** — o'sha narsani promptga kiritasiz

Va yana boshidan. Odatda 2-3 urinishda javob kerakli darajaga yetadi.

Muhimi: **butun promptni qaytadan yozmang**. Faqat yetishmagan
narsani qo'shing. Ishlagan qismini buzmaysiz.

## Suhbatni davom ettirish

Chat oynasida oldingi xabarlar saqlanadi. Demak `Uchinchi bandni
kengaytir` deb yozish kifoya — hammasini takrorlash shart emas.

Lekin ehtiyot bo'ling: suhbat uzayganda model boshidagi
ko'rsatmalarni "unuta" boshlaydi. Muhim shartlarni vaqti-vaqti bilan
takrorlab turing.

> Qoida: agar javob uchinchi urinishda ham yaxshilanmasa, muammo
> promptda emas — vazifa noto'g'ri qo'yilgan bo'lishi mumkin.
""",
                'quiz': {
                    'title': "Murakkab vazifalar",
                    'questions': [
                        {
                            'text': "Nima uchun katta vazifa bitta promptda yuzaki bajariladi?",
                            'choices': [
                                ("Model javobni so'zma-so'z quradi va oldindan reja tuzmaydi", True),
                                ("Modelda javob uzunligi cheklangan", False),
                                ("Katta vazifalar qo'shimcha to'lov talab qiladi", False),
                                ("Model uzun savollarni o'qimaydi", False),
                            ],
                        },
                        {
                            'text': "«Avval qanday yondashishni yoz, keyin javob ber» nima uchun yordam beradi?",
                            'choices': [
                                ("Model mulohazani matn sifatida yozadi va keyingi qadamlar shunga tayanadi", True),
                                ("Model ko'proq vaqt oladi va yaxshiroq o'ylaydi", False),
                                ("Javob avtomatik tekshiriladi", False),
                                ("Bu javobni qisqartiradi", False),
                            ],
                        },
                        {
                            'text': "Javob to'liq chiqmasa nima qilish kerak?",
                            'choices': [
                                ("Yetishmagan narsani promptga qo'shish, ishlagan qismini saqlab qolish", True),
                                ("Promptni butunlay qaytadan yozish", False),
                                ("Bir xil promptni qayta-qayta yuborish", False),
                                ("Boshqa modelga o'tish", False),
                            ],
                        },
                        {
                            'text': "Uzun suhbatda nimaga e'tibor berish kerak?",
                            'choices': [
                                ("Model boshidagi ko'rsatmalarni «unuta» boshlaydi, ularni takrorlash kerak", True),
                                ("Suhbat avtomatik o'chib ketadi", False),
                                ("Javoblar tezlashadi", False),
                                ("Model oldingi xabarlarni umuman ko'rmaydi", False),
                            ],
                        },
                    ],
                },
            },
        ],
    },
    # ══════════════════════════════════════════════════════════════
    {
        'title': "Amaliyot va xavfsizlik",
        'order': 3,
        'lessons': [
            {
                'title': "Kundalik ishda AI: matn, tahlil, kod",
                'free': False,
                'theory': """
Nazariyani amaliyotga o'tkazamiz. Quyida uchta soha bo'yicha tayyor
prompt namunalari — ularni o'zingizga moslab ishlating.

## Matn bilan ishlash

**Qoralamani tuzatish**
```
Quyidagi matnni tahrirla. Ma'noni o'zgartirma, faqat
ravonlashtir va takrorlarni olib tashla. Uzunligi
o'zgarmasin. Nima o'zgartirganingni oxirida qisqacha yoz.

Matn: ...
```

Oxirgi jumla muhim: nima o'zgarganini ko'rmasangiz, matn sizniki
bo'lishdan to'xtaydi.

**Uzunni qisqartirish**
```
Bu matnni 3 ta jumlaga qisqartir. Asosiy xulosa
saqlansin, tafsilotlar tushib qolsin.
```

**Sarlavha variantlari**
```
Bu maqolaga 10 ta sarlavha varianti ber.
5 tasi jiddiy, 5 tasi qiziqtiruvchi bo'lsin.
Har biri 60 belgidan oshmasin.
```

## O'qish va tahlil

**Uzun hujjatni tushunish**
```
Quyidagi matnni o'qib chiq va menga ayt:
1. Asosiy fikr nima
2. Qanday dalillar keltirilgan
3. Nima aytilmagan yoki tushib qolgan

Matn: ...
```

Uchinchi savol eng qimmatlisi — u sizni matnga tanqidiy qarashga
majbur qiladi.

**Solishtirish**
```
Bu ikki variantni jadval ko'rinishida solishtir:
narx, muddat, xavf. Oxirida qaysi biri kimga
mos kelishini yoz.
```

## Kod bilan ishlash

**Kodni tushuntirish**
```
Bu kod nima qilishini qator-qator tushuntir.
Men Python'ni endi o'rganyapman.

Kod: ...
```

**Xatoni topish**
```
Bu kod xato beradi. Xato matni: ...
Sababini tushuntir va tuzatilgan variantini ber.
Nima uchun bunday bo'lganini ham yoz.
```

"Nima uchun" so'ramasangiz, tuzatilgan kodni nusxa olasiz-u,
xatoni tushunmay qolasiz. Keyingi safar yana takrorlanadi.

**Kod yozdirish**
```
Python'da funksiya yoz: fayldan satrlarni o'qisin va
bo'sh satrlarni tashlab yuborsin. Izohlar o'zbek tilida.
Fayl topilmasa tushunarli xato bersin.
```

## Umumiy tavsiya

Yaxshi ishlagan promptlarni **saqlab boring**. Bir marta yozib
qo'ygan prompt keyin o'nlab marta ishlatiladi. Oddiy matn fayli ham
yetarli.

> Modelning javobini o'zgartirmasdan ishlatmang. Uni qoralama deb
> qarang: o'qing, tekshiring, o'zingiznikiga aylantiring.
""",
                'quiz': {
                    'title': "Amaliy qo'llash",
                    'questions': [
                        {
                            'text': "Matnni tahrirlatganda nima uchun «nima o'zgartirganingni yoz» deb qo'shiladi?",
                            'choices': [
                                ("O'zgarishlarni ko'rmasangiz matn sizniki bo'lishdan to'xtaydi", True),
                                ("Model aks holda ishlamaydi", False),
                                ("Bu javobni qisqartiradi", False),
                                ("Bu xatolarni oldini oladi", False),
                            ],
                        },
                        {
                            'text': "Kod xatosini tuzatishda nima uchun «nima uchun bunday bo'lgani»ni so'rash kerak?",
                            'choices': [
                                ("Aks holda tuzatilgan kodni nusxa olasiz-u, xatoni tushunmay qolasiz", True),
                                ("Model tushuntirmasa kod ishlamaydi", False),
                                ("Bu javobni tezlashtiradi", False),
                                ("Bu qoidalar talabi", False),
                            ],
                        },
                        {
                            'text': "Hujjat tahlilida «nima aytilmagan» degan savol nima uchun qimmatli?",
                            'choices': [
                                ("U matnga tanqidiy qarashga majbur qiladi", True),
                                ("U javobni uzaytiradi", False),
                                ("Model bunday savollarni yaxshi biladi", False),
                                ("U matnni qisqartiradi", False),
                            ],
                        },
                        {
                            'text': "Yaxshi ishlagan prompt bilan nima qilish tavsiya etiladi?",
                            'choices': [
                                ("Saqlab qo'yish — u keyin o'nlab marta ishlatiladi", True),
                                ("Har safar yangisini yozish", False),
                                ("Uni imkon qadar qisqartirish", False),
                                ("Boshqalarga bermaslik", False),
                            ],
                        },
                    ],
                },
            },
            {
                'title': "Gallyutsinatsiya: model qachon yolg'on gapiradi",
                'free': False,
                'image': 'hallucination',
                'image_caption': "Model bilmagan narsasini ham ishonch bilan yozadi",
                'theory': """
Bu kursning eng muhim darsi. Qolgan hamma narsani unutsangiz ham,
shuni eslab qoling.

## Gallyutsinatsiya nima

Model bilmagan narsasini **to'qib chiqarishi** va buni **ishonch
bilan** taqdim etishi — gallyutsinatsiya deyiladi.

Bu nosozlik emas. Bu modelning ishlash usulidan kelib chiqadigan
tabiiy oqibat: u keyingi so'zni taxmin qiladi, "menda bu ma'lumot
yo'q" degan holat unda alohida ko'zda tutilmagan.

## Eng xavflisi — ishonarli ko'rinishi

Model "menimcha, taxminan..." deb yozmaydi. U aniq sana, aniq raqam,
aniq ism yozadi. Tashqi ko'rinishidan to'g'ri javobdan **farq
qilmaydi**.

Mavzuni bilmasangiz — xatoni sezmaysiz. Aynan shu narsa
gallyutsinatsiyani xavfli qiladi.

## Qayerda ko'proq uchraydi

- **Sana va raqamlar** — statistika, yillar, foizlar
- **Iqtiboslar** — "falonchi shunday degan" (aytmagan bo'lishi mumkin)
- **Manbalar** — kitob, maqola, havola. Model mavjud bo'lmagan
  manbani ham chiroyli qilib yozib beradi
- **Qonun va qoidalar** — modda raqami, muddat
- **Kam ma'lum mavzular** — mahalliy voqealar, tor sohalar
- **Yangi voqealar** — modelning bilimi ma'lum sanada to'xtaydi

## Nima qilish kerak

**1. Turini ajrating.** Ikki xil savol bor:
- *Fikr talab qiladigan* — "bu matnni qanday yaxshilash mumkin?"
  Bu yerda gallyutsinatsiya deyarli xavf tug'dirmaydi.
- *Fakt talab qiladigan* — "bu qonun qachon qabul qilingan?"
  Bu yerda javobni **doim** tekshiring.

**2. Manbani so'rang.** `Bu ma'lumotni qayerdan olding?` Model
manbani ayta olmasa yoki mavjud bo'lmagan manba bersa — bu ogohlantiruvchi
belgi.

**3. Ruxsat bering.** Promptga qo'shing:
```
Aniq bilmasang, «bilmayman» deb yoz. Taxmin qilma.
```
Bu gallyutsinatsiyani butunlay yo'qotmaydi, lekin kamaytiradi.

**4. Manbani o'zingiz bering.** Eng ishonchli usul: kerakli hujjatni
promptga qo'ying va `faqat shu matnga tayanib javob ber` deb yozing.
Shunda modelning "o'ylab topish" imkoni keskin torayadi.

**5. Ikkinchi manbadan tekshiring.** Rasmiy sayt, hujjat, mutaxassis.
Modelning o'zidan qayta so'rash tekshiruv EMAS — u bir xil xatoni
takrorlashi mumkin.

## Chegara

Tibbiyot, huquq, moliya. Bu sohalarda modelning javobi — bu
**ma'lumot emas, matn**. Qaror qabul qilishda unga tayanmang.

> Model — bu ishonchli manba emas, tez yordamchi. Farqi shunda:
> yordamchining ishini tekshirasiz, manbaga esa ishonasiz.
""",
                'quiz': {
                    'title': "Gallyutsinatsiya",
                    'questions': [
                        {
                            'text': "Gallyutsinatsiya nima?",
                            'choices': [
                                ("Model bilmagan narsasini to'qib, ishonch bilan taqdim etishi", True),
                                ("Modelning javob berishdan bosh tortishi", False),
                                ("Serverdagi texnik nosozlik", False),
                                ("Javobning juda uzun chiqishi", False),
                            ],
                        },
                        {
                            'text': "Nima uchun gallyutsinatsiya xavfli?",
                            'choices': [
                                ("Xato javob tashqi ko'rinishidan to'g'risidan farq qilmaydi", True),
                                ("U dasturni ishdan chiqaradi", False),
                                ("U javobni sekinlashtiradi", False),
                                ("U faqat uzun matnlarda uchraydi", False),
                            ],
                        },
                        {
                            'text': "Gallyutsinatsiya xavfini kamaytirishning eng ishonchli usuli qaysi?",
                            'choices': [
                                ("Kerakli hujjatni promptga qo'yib, «faqat shu matnga tayan» deyish", True),
                                ("Savolni qayta-qayta berish", False),
                                ("Promptni qisqartirish", False),
                                ("Modeldan javobiga ishonchini so'rash", False),
                            ],
                        },
                        {
                            'text': "Modeldan «ishonchingiz komilmi?» deb qayta so'rash tekshiruv bo'ladimi?",
                            'choices': [
                                ("Yo'q — u bir xil xatoni takrorlashi mumkin, mustaqil manba kerak", True),
                                ("Ha, model o'z xatosini topadi", False),
                                ("Ha, bu eng ishonchli usul", False),
                                ("Faqat uzun javoblarda", False),
                            ],
                        },
                        {
                            'text': "Qaysi turdagi savolda gallyutsinatsiya kamroq xavf tug'diradi?",
                            'choices': [
                                ("Fikr talab qiladigan: «bu matnni qanday yaxshilash mumkin?»", True),
                                ("Sana so'raydigan savol", False),
                                ("Statistika so'raydigan savol", False),
                                ("Qonun moddasi haqidagi savol", False),
                            ],
                        },
                    ],
                },
            },
            {
                'title': "Maxfiylik va mas'uliyat",
                'free': False,
                'image': 'privacy',
                'image_caption': "Nima yuborish mumkin, nima mumkin emas",
                'theory': """
Oxirgi dars — texnika haqida emas, ehtiyotkorlik haqida.

## Yozganingiz sizdan chiqib ketadi

Chatga yozgan har bir so'z boshqa kompaniyaning serveriga boradi.
U saqlanishi, xodimlar tomonidan ko'rilishi yoki modelni yaxshilashda
ishlatilishi mumkin — bu xizmat shartlariga bog'liq.

Amaliy qoida oddiy: **ochiq maydonga yozmaydigan narsangizni chatga
ham yozmang.**

## Hech qachon yubormang

- Parol, kirish kalitlari, API kalitlari
- Passport, JSHSHIR va shunga o'xshash hujjat ma'lumotlari
- Karta raqami, bank ma'lumotlari
- Mijozlar yoki xodimlarning shaxsiy ma'lumotlari
- Kompaniyaning maxfiy hujjatlari, shartnomalari
- Tibbiy ma'lumotlar — o'zingizniki ham, boshqaniki ham

## Bemalol yuborsa bo'ladi

- Umumiy savollar va tushunchalar
- O'zingiz yozgan matn qoralamasi
- Ochiq manbalardagi ma'lumotlar
- **Nomlari o'zgartirilgan** misollar
- O'quv topshiriqlari

Oxirgisi foydali usul: haqiqiy hujjat kerak bo'lsa, ism va
raqamlarni o'zgartiring. `Mijoz A`, `100 000 so'm` — vazifa
o'zgarmaydi, ma'lumot esa chiqib ketmaydi.

## Mualliflik va halollik

**Model yozgan matn sizniki emas** — hech bo'lmaganda uni o'qib,
tekshirib, o'zgartirmagunicha.

Ikki narsani ajrating:

- **Yordamchi sifatida** — qoralama oldingiz, tuzatdingiz,
  o'zingiznikiga aylantirdingiz. Bu normal ish usuli.
- **O'rniga qo'yish** — javobni o'zgartirmasdan, o'qimasdan
  topshirdingiz. Bu ham xavfli, ham halol emas.

O'quv ishida, ishda va ayniqsa mijozga topshiriladigan ishda birinchi
yo'lni tanlang.

## Kim javobgar

Modelning javobi uchun **siz** javobgarsiz. "AI shunday dedi" — bu
uzr emas.

Xato hisobot topshirsangiz, xato maslahat bersangiz, xato kod
qo'ysangiz — javobgarlik sizda qoladi. Model bu javobgarlikni ololmaydi.

## Kursdan asosiy xulosalar

1. Model o'ylamaydi — u matn yozadi
2. Aniq topshiriq aniq javob beradi
3. Tushuntirish qiyin bo'lsa — namuna ko'rsating
4. Katta vazifani bosqichlarga bo'ling
5. Faktni doim tekshiring
6. Maxfiy ma'lumotni yubormang
7. Javobgarlik sizda

> Sun'iy intellekt sizning o'rningizni egallamaydi. Lekin undan
> foydalanishni bilgan odam bilmaganidan tezroq ishlaydi.
""",
                'quiz': {
                    'title': "Maxfiylik va mas'uliyat",
                    'questions': [
                        {
                            'text': "Chatga maxfiy ma'lumot yozish bo'yicha amaliy qoida qanday?",
                            'choices': [
                                ("Ochiq maydonga yozmaydigan narsani chatga ham yozmaslik", True),
                                ("Faqat kechqurun yozmaslik", False),
                                ("Qisqa qilib yozish", False),
                                ("Faqat rasmiy hisobdan yozish", False),
                            ],
                        },
                        {
                            'text': "Haqiqiy hujjat bilan ishlash kerak bo'lsa, xavfsiz yo'l qaysi?",
                            'choices': [
                                ("Ism va raqamlarni o'zgartirib yuborish", True),
                                ("Hujjatni bo'laklarga bo'lib yuborish", False),
                                ("Faylni rasm ko'rinishida yuborish", False),
                                ("Suhbatni keyin o'chirib tashlash", False),
                            ],
                        },
                        {
                            'text': "Model yozgan matnni o'zgartirmasdan topshirish nima uchun noto'g'ri?",
                            'choices': [
                                ("Matn tekshirilmagan bo'ladi va bu halol ish usuli emas", True),
                                ("Bunday matn texnik jihatdan ishlamaydi", False),
                                ("Model buni taqiqlaydi", False),
                                ("Matn juda uzun bo'lib qoladi", False),
                            ],
                        },
                        {
                            'text': "Modelning xato javobi tufayli muammo chiqsa, javobgar kim?",
                            'choices': [
                                ("Javobni ishlatgan odam — ya'ni siz", True),
                                ("Modelni yaratgan kompaniya", False),
                                ("Hech kim — bu texnika xatosi", False),
                                ("Ma'lumotni bergan manba", False),
                            ],
                        },
                    ],
                },
            },
        ],
    },
]
