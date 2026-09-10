"""
Testlardagi xatolarni tuzatish.

1. TAKRORLAR. Yettita testda (Python, Django, JavaScript, React
   darslari) har bir savol ikki marta turardi: "1. Python qanday til?"
   va "16. Python qanday til?" — 15 ta savol 30 ta bo'lib ko'rinardi.
   Raqamdan keyingi matni va variantlari AYNAN bir xil bo'lgan savolning
   keyingi nusxasi o'chiriladi. Variantlari farq qilsa — tegilmaydi.

2. MAVZUGA MOS KELMAGAN TESTLAR:
     * "Ro'yhat va uning metodlari" (Python) — JavaScript savollari turardi;
     * "React Lesson 1" — JavaScript savollari turardi;
     * Python "Kirish" va "Ro'yhat davomi" — "Python Lesson 1" testining
       aynan nusxasi edi.
   Ular darsning o'z mavzusidagi savollar bilan almashtiriladi.

ADMIN O'ZGARTIRGAN TESTGA TEGILMAYDI: almashtirish faqat test hali
o'sha eski holatda bo'lsa (o'sha darsga bog'langan, 15 ta noyob savol,
birinchi savoli kutilgandek) bajariladi. Aks holda panel orqali
qo'lda tuzatilgan test bosib ketilardi.

O'quvchilarning natijalari (`QuizResult`) savollarga bog'lanmagan —
ball va sertifikatlar saqlanib qoladi.

Savollar `core/fixtures/content.json` ga ham xuddi shu ma'lumotdan
yozilgan — yangi bo'sh bazaga xato qayta yuklanmasin.
"""

import re

from django.db import migrations

_NUMBER = re.compile(r'^\s*\d+\.\s*')


def normalize(text: str) -> str:
    """Savol matni boshidagi "16. " raqamisiz."""
    return _NUMBER.sub('', text or '').strip()


# Har bir savol: (matn, to'g'ri javob, [uchta noto'g'ri javob]).
# To'g'ri javob o'rni `choices()` da aylantiriladi — hamma savolda
# birinchi variant to'g'ri bo'lib qolmasin.

KIRISH = [
    ("Dasturlash nima?",
     "Kompyuterga bajariladigan buyruqlar ketma-ketligini yozish",
     ["Kompyuterni qismlardan yig'ish", "Internetdan fayl yuklab olish",
      "Matnni chiroyli bezash"]),
    ("Python qanday turdagi til?",
     "Yuqori darajali, interpretatsiya qilinadigan til",
     ["Faqat mashina kodi", "Faqat brauzerda ishlaydigan belgilash tili",
      "Ma'lumotlar bazasi"]),
    ("Nega Python boshlovchilar uchun qulay?",
     "Sintaksisi sodda va o'qilishi oson",
     ["Faqat o'yin yaratish uchun mo'ljallangan", "Kod yozmasdan ishlaydi",
      "Faqat Windows'da ishlaydi"]),
    ("Python kodi saqlanadigan fayl kengaytmasi qaysi?",
     ".py", [".js", ".html", ".exe"]),
    ("Ekranga matn chiqaradigan funksiya qaysi?",
     "print()", ["input()", "len()", "type()"]),
    ("Python qayerlarda ishlatiladi?",
     "Veb, ma'lumotlar tahlili, sun'iy intellekt va avtomatlashtirishda",
     ["Faqat veb-sahifa dizaynida", "Faqat telefon o'yinlarida",
      "Faqat matn muharriri sifatida"]),
    ("Python'da izoh (kommentariya) qanday yoziladi?",
     "# belgisi bilan", ["// bilan", "<!-- --> bilan", "** bilan"]),
    ('print("Salom") qanday natija chiqaradi?',
     "Salom", ['"Salom"', "print Salom", "Xato beradi"]),
    ("Python'da kod bloklari nima bilan ajratiladi?",
     "Chekinish (qator boshidagi bo'sh joy) bilan",
     ["Jingalak qavs {} bilan", "begin va end so'zlari bilan",
      "Nuqtali vergul bilan"]),
    ("Interpretator nima qiladi?",
     "Kodni qatorma-qator o'qib bajaradi",
     ["Kodni chiroyli formatlaydi", "Internetga ulaydi", "Fayllarni o'chiradi"]),
    ("Python tilini kim yaratgan?",
     "Guido van Rossum", ["Brendan Eich", "Bill Gates", "Linus Torvalds"]),
    ("Dastur xato bersa, birinchi navbatda nima qilinadi?",
     "Xato xabarini o'qib, qaysi qatorda ekanini aniqlash",
     ["Kompyuterni o'chirib yoqish", "Butun kodni o'chirib qayta yozish",
      "Xatoga e'tibor bermaslik"]),
]

ROYXAT_DAVOMI = [
    ("users = {1: 'Ali', 2: 'Vali'} — bu qanday ma'lumot turi?",
     "Lug'at (dict)", ["Ro'yxat (list)", "Kortej (tuple)", "To'plam (set)"]),
    ("Lug'atning faqat kalitlarini qaysi metod qaytaradi?",
     ".keys()", [".values()", ".items()", ".get()"]),
    ("Lug'atning faqat qiymatlarini qaysi metod qaytaradi?",
     ".values()", [".keys()", ".items()", ".pop()"]),
    ("for key, value in users.items(): — sikl har qadamda nimani beradi?",
     "Kalit va qiymat juftligini",
     ["Faqat kalitlarni", "Faqat qiymatlarni", "Lug'at uzunligini"]),
    ("for x in users: — lug'at bo'ylab oddiy for sikli nimani aylanadi?",
     "Kalitlarni", ["Qiymatlarni", "Kalit-qiymat juftliklarini",
                    "Hech narsani, xato beradi"]),
    ("sonlar = [3, 1, 2]\nfor s in sonlar:\n    print(s)\nNima chiqadi?",
     "3, 1, 2 — har biri alohida qatorda",
     ["1, 2, 3 — har biri alohida qatorda", "[3, 1, 2]", "6"]),
    ("Ro'yxatning oxirgi elementi qanday olinadi?",
     "sonlar[-1]", ["sonlar[0]", "sonlar[len]", "sonlar.last()"]),
    ("sonlar = [10, 20, 30, 40] bo'lsa, sonlar[1:3] nima qaytaradi?",
     "[20, 30]", ["[10, 20, 30]", "[20, 30, 40]", "[10, 20]"]),
    ("Ro'yxatda element borligi qanday tekshiriladi?",
     "20 in sonlar", ["sonlar.has(20)", "sonlar.find(20)", "20 of sonlar"]),
    ("users[3] = 'Hasan' nima qiladi?",
     "Lug'atga 3 kaliti bilan yangi qiymat qo'shadi",
     ["Xato beradi", "3-elementni o'chiradi", "Yangi ro'yxat yaratadi"]),
    ("Mavjud bo'lmagan kalitda xato bermasdan qiymat olish usuli qaysi?",
     "users.get(5)", ["users[5]", "users.find(5)", "users.value(5)"]),
    ("for i, harf in enumerate(['a', 'b']): — sikl har qadamda nimani beradi?",
     "Indeks va element juftligini",
     ["Faqat indeksni", "Faqat elementni", "Ro'yxat uzunligini"]),
]

ROYXAT_METODLARI = [
    ("Ro'yxat oxiriga element qo'shadigan metod qaysi?",
     "append()", ["add()", "insert()", "push()"]),
    ("mevalar = ['olma']\nmevalar.insert(0, 'nok')\nNatija qanday?",
     "['nok', 'olma']", ["['olma', 'nok']", "['nok']", "Xato beradi"]),
    ("Elementni QIYMATI bo'yicha o'chiradigan metod qaysi?",
     "remove()", ["pop()", "clear()", "index()"]),
    ("pop() argumentsiz chaqirilsa nima qiladi?",
     "Oxirgi elementni o'chirib, uni qaytaradi",
     ["Birinchi elementni o'chiradi", "Ro'yxatni butunlay tozalaydi",
      "Xato beradi"]),
    ("Ro'yxatni o'sish tartibida joyida tartiblaydigan metod qaysi?",
     "sort()", ["order()", "arrange()", "sorted_list()"]),
    ("sort() va sorted() ning farqi nima?",
     "sort() ro'yxatning o'zini o'zgartiradi, sorted() yangi ro'yxat qaytaradi",
     ["Hech qanday farqi yo'q", "sorted() faqat sonlar bilan ishlaydi",
      "sort() yangi ro'yxat qaytaradi, sorted() esa o'zini o'zgartiradi"]),
    ("Ro'yxat uzunligi qanday topiladi?",
     "len(royxat)", ["royxat.length", "royxat.size()", "count(royxat)"]),
    ("[1, 2, 2, 3].count(2) natijasi nima?",
     "2", ["1", "3", "4"]),
    ("['a', 'b', 'c'].index('c') natijasi nima?",
     "2", ["3", "1", "'c'"]),
    ("Ro'yxatni teskari tartibga aylantiradigan metod qaysi?",
     "reverse()", ["back()", "invert()", "flip()"]),
    ("Ro'yxatning barcha elementlarini o'chiradigan metod qaysi?",
     "clear()", ["remove()", "delete()", "empty()"]),
    ("a = [1, 2]\na.extend([3, 4])\nNatija qanday?",
     "[1, 2, 3, 4]", ["[1, 2, [3, 4]]", "[3, 4]", "Xato beradi"]),
]

REACT_KIRISH = [
    ("React nima?",
     "Foydalanuvchi interfeysi yaratish uchun JavaScript kutubxonasi",
     ["Ma'lumotlar bazasi", "Alohida dasturlash tili", "Server operatsion tizimi"]),
    ("React'ni qaysi kompaniya ishlab chiqqan?",
     "Meta (Facebook)", ["Google", "Microsoft", "Apple"]),
    ("JSX nima?",
     "JavaScript ichida HTML'ga o'xshash belgilash yozish sintaksisi",
     ["Yangi dasturlash tili", "CSS kutubxonasi", "Ma'lumot saqlash formati"]),
    ("React komponenti nima?",
     "Interfeysning qayta ishlatiladigan mustaqil bo'lagi",
     ["CSS fayli", "Server manzili", "Brauzer kengaytmasi"]),
    ("Komponent nomi qanday yoziladi?",
     "Katta harf bilan boshlanadi: UserCard",
     ["Faqat kichik harflar bilan: usercard", "Raqam bilan boshlanadi",
      "Tire bilan: user-card"]),
    ("Funksional komponent nimani qaytaradi?",
     "JSX — interfeysning ko'rinishini",
     ["Faqat sonni", "CSS kodini", "Hech narsa qaytarmaydi"]),
    ("Komponentga tashqaridan ma'lumot qanday uzatiladi?",
     "props orqali", ["state orqali", "import orqali", "CSS orqali"]),
    ("Komponent ichidagi o'zgaruvchan holat uchun qaysi hook ishlatiladi?",
     "useState", ["useProps", "useStyle", "useClass"]),
    ("JSX'da HTML'dagi class atributi qanday yoziladi?",
     "className", ["class", "cssClass", "styleClass"]),
    ("JSX ichida JavaScript ifodasi qanday qo'yiladi?",
     "Jingalak qavs {} ichida",
     ['Qo\'shtirnoq "" ichida', "Kvadrat qavs [] ichida", "${} ichida"]),
    ("Ro'yxatni map() bilan chizganda har bir elementga nima beriladi?",
     "Noyob key", ["id nomli CSS klassi", "Alohida index.html", "style atributi"]),
    ("Yangi React loyihasini yaratishning zamonaviy usuli qaysi?",
     "npm create vite@latest",
     ["pip install react", "react new app", "django-admin startproject"]),
]

#: quiz pk -> (dars pk, eski holatdagi birinchi savol, yangi savollar)
REPLACEMENTS = {
    8: (32, "Python qanday til?", KIRISH),
    10: (31, "Python qanday til?", ROYXAT_DAVOMI),
    11: (33, "JavaScript qanday til?", ROYXAT_METODLARI),
    6: (28, "JavaScript qanday til?", REACT_KIRISH),
}

#: Eski (xato) holatda testdagi NOYOB savollar soni
OLD_UNIQUE_COUNT = 15


def choices(index: int, correct: str, wrong: list):
    """
    (matn, to'g'rimi) ro'yxati. To'g'ri javob o'rni savoldan savolga
    aylanadi: 0, 1, 2, 3, 0, ...
    """
    items = [(text, False) for text in wrong]
    items.insert(index % (len(wrong) + 1), (correct, True))
    return items


def _choice_set(question):
    return sorted((c.text, c.is_correct) for c in question.choices.all())


def remove_duplicates(apps, schema_editor):
    Quiz = apps.get_model('core', 'Quiz')

    for quiz in Quiz.objects.all():
        kept = {}
        for question in quiz.questions.order_by('id').prefetch_related('choices'):
            key = normalize(question.text)
            first = kept.get(key)
            if first is None:
                kept[key] = question
            elif _choice_set(first) == _choice_set(question):
                # Choice'lar CASCADE bilan birga o'chadi
                question.delete()


def replace_off_topic(apps, schema_editor):
    Quiz = apps.get_model('core', 'Quiz')
    Question = apps.get_model('core', 'Question')
    Choice = apps.get_model('core', 'Choice')

    for quiz_id, (lesson_id, old_first, new_questions) in REPLACEMENTS.items():
        quiz = Quiz.objects.filter(pk=quiz_id, lesson_id=lesson_id).first()
        if quiz is None:
            continue

        current = list(quiz.questions.order_by('id'))
        still_broken = (
            len({normalize(q.text) for q in current}) == OLD_UNIQUE_COUNT
            and current
            and normalize(current[0].text) == old_first
        )
        if not still_broken:
            continue

        quiz.questions.all().delete()
        for number, (text, correct, wrong) in enumerate(new_questions, 1):
            question = Question.objects.create(quiz=quiz, text=f"{number}. {text}")
            Choice.objects.bulk_create([
                Choice(question=question, text=choice_text, is_correct=is_correct)
                for choice_text, is_correct in choices(number - 1, correct, wrong)
            ])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0025_all_lessons_free'),
    ]

    operations = [
        migrations.RunPython(remove_duplicates, migrations.RunPython.noop),
        migrations.RunPython(replace_off_topic, migrations.RunPython.noop),
    ]
