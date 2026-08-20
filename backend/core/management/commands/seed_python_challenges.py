"""
Python topshiriqlarini qo'shadi.

Platforma asosan Python o'rgatadi, lekin muharrirda faqat JavaScript
topshiriqlari bor edi. Bu buyruq yetishmayotgan Python topshiriqlarini
qo'shadi — mavjudlariga tegmaydi (idempotent, sarlavha bo'yicha).

    python manage.py seed_python_challenges
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Challenge

CHALLENGES = [
    {
        'title': "Salom, dunyo!",
        'difficulty': 'Oson',
        'description': (
            "<h3>Vazifa:</h3>"
            "<p><code>print()</code> funksiyasidan foydalanib ekranga "
            "<b>Salom, dunyo!</b> matnini chiqaring.</p>"
            "<p>Python da matn qo'shtirnoq ichida yoziladi.</p>"
        ),
        'initial_code': '# Matnni shu yerda chiqaring\n',
        'solution_code': 'print("Salom, dunyo!")\n',
    },
    {
        'title': "O'zgaruvchilar va f-string",
        'difficulty': 'Oson',
        'description': (
            "<h3>Vazifa:</h3>"
            "<p><code>ism</code> va <code>yosh</code> o'zgaruvchilarini yarating, "
            "so'ng f-string yordamida <b>\"Ozodbek 25 yoshda\"</b> ko'rinishida "
            "chiqaring.</p>"
            "<p>f-string: <code>f\"{o'zgaruvchi}\"</code></p>"
        ),
        'initial_code': "ism = \nyosh = \n\n# f-string bilan chiqaring\n",
        'solution_code': 'ism = "Ozodbek"\nyosh = 25\nprint(f"{ism} {yosh} yoshda")\n',
    },
    {
        'title': "Ro'yxat bilan ishlash",
        'difficulty': 'Oson',
        'description': (
            "<h3>Vazifa:</h3>"
            "<p>Berilgan ro'yxatdagi sonlarning <b>yig'indisi</b> va "
            "<b>o'rtachasini</b> hisoblab chiqaring.</p>"
            "<p>Foydali funksiyalar: <code>sum()</code>, <code>len()</code></p>"
        ),
        'initial_code': (
            "sonlar = [12, 45, 7, 23, 56, 89, 34]\n\n"
            "# Yig'indi va o'rtachani hisoblang\n"
        ),
        'solution_code': (
            "sonlar = [12, 45, 7, 23, 56, 89, 34]\n"
            "yigindi = sum(sonlar)\n"
            "ortacha = yigindi / len(sonlar)\n"
            'print(f"Yig\'indi: {yigindi}")\n'
            'print(f"O\'rtacha: {ortacha:.2f}")\n'
        ),
    },
    {
        'title': "Shart operatori",
        'difficulty': "O'rtacha",
        'description': (
            "<h3>Vazifa:</h3>"
            "<p><code>baho(ball)</code> funksiyasini yozing:</p>"
            "<ul>"
            "<li>90 va undan yuqori — <code>\"A'lo\"</code></li>"
            "<li>70–89 — <code>\"Yaxshi\"</code></li>"
            "<li>50–69 — <code>\"Qoniqarli\"</code></li>"
            "<li>50 dan past — <code>\"Qoniqarsiz\"</code></li>"
            "</ul>"
        ),
        'initial_code': (
            "def baho(ball):\n"
            "    # Shartlarni shu yerda yozing\n"
            "    pass\n\n"
            "for b in [95, 78, 55, 30]:\n"
            '    print(b, "->", baho(b))\n'
        ),
        'solution_code': (
            "def baho(ball):\n"
            '    if ball >= 90:\n        return "A\'lo"\n'
            '    if ball >= 70:\n        return "Yaxshi"\n'
            '    if ball >= 50:\n        return "Qoniqarli"\n'
            '    return "Qoniqarsiz"\n\n'
            "for b in [95, 78, 55, 30]:\n"
            '    print(b, "->", baho(b))\n'
        ),
    },
    {
        'title': "Sikl va shart birga",
        'difficulty': "O'rtacha",
        'description': (
            "<h3>Vazifa:</h3>"
            "<p>1 dan 50 gacha bo'lgan sonlar ichidan <b>3 ga ham, 5 ga ham "
            "bo'linadiganlarini</b> topib chiqaring.</p>"
            "<p>Qoldiqni olish: <code>son % 3 == 0</code></p>"
        ),
        'initial_code': "# 1 dan 50 gacha aylanib chiqing\n",
        'solution_code': (
            "for son in range(1, 51):\n"
            "    if son % 3 == 0 and son % 5 == 0:\n"
            "        print(son)\n"
        ),
    },
    {
        'title': "Lug'at (dictionary)",
        'difficulty': "O'rtacha",
        'description': (
            "<h3>Vazifa:</h3>"
            "<p>Matndagi har bir <b>harf nechta marta</b> uchraganini "
            "sanaydigan kod yozing.</p>"
            "<p>Maslahat: lug'at (<code>dict</code>) va <code>.get()</code> "
            "metodidan foydalaning.</p>"
        ),
        'initial_code': (
            'matn = "dasturlash"\n\n'
            "# Har bir harfni sanang\n"
        ),
        'solution_code': (
            'matn = "dasturlash"\n'
            "hisob = {}\n"
            "for harf in matn:\n"
            "    hisob[harf] = hisob.get(harf, 0) + 1\n\n"
            "for harf, son in hisob.items():\n"
            '    print(f"{harf}: {son}")\n'
        ),
    },
    {
        'title': "Sinf (class) yaratish",
        'difficulty': 'Qiyin',
        'description': (
            "<h3>Vazifa:</h3>"
            "<p><code>Talaba</code> sinfini yarating:</p>"
            "<ul>"
            "<li><code>__init__</code> — ism va baholar ro'yxatini qabul qiladi</li>"
            "<li><code>ortacha()</code> — o'rtacha bahoni qaytaradi</li>"
            "<li><code>__str__</code> — \"Ozodbek: 4.50\" ko'rinishida qaytaradi</li>"
            "</ul>"
        ),
        'initial_code': (
            "class Talaba:\n"
            "    def __init__(self, ism, baholar):\n"
            "        pass\n\n"
            "t = Talaba(\"Ozodbek\", [5, 4, 5, 4])\n"
            "print(t)\n"
        ),
        'solution_code': (
            "class Talaba:\n"
            "    def __init__(self, ism, baholar):\n"
            "        self.ism = ism\n"
            "        self.baholar = baholar\n\n"
            "    def ortacha(self):\n"
            "        return sum(self.baholar) / len(self.baholar)\n\n"
            "    def __str__(self):\n"
            '        return f"{self.ism}: {self.ortacha():.2f}"\n\n'
            't = Talaba("Ozodbek", [5, 4, 5, 4])\n'
            "print(t)\n"
        ),
    },
]

#: Yechim TO'G'RI ishlaganda ekranga chiqadigan matn.
#:
#: NEGA ALOHIDA LUG'AT, har topshiriqning ichida emas: kutilgan
#: natijalar shu yerda yonma-yon turadi va ularni yechim kodi bilan
#: solishtirish oson. Topshiriq matnlari esa uzun — natija ular orasida
#: yo'qolib ketardi.
#:
#: BU QIYMATLAR YECHIMDAN OLINGAN: har biri yechim kodi ishga
#: tushirilib, chiqqan matn ko'chirilgan. Qo'lda yozilsa, bitta bo'sh
#: joy ham to'g'ri yechimni "noto'g'ri" qilib qo'yardi.
EXPECTED = {
    "Salom, dunyo!": "Salom, dunyo!\n",
    "O'zgaruvchilar va f-string": "Ozodbek 25 yoshda\n",
    "Ro'yxat bilan ishlash": "Yig'indi: 266\nO'rtacha: 38.00\n",
    "Shart operatori": (
        "95 -> A'lo\n"
        "78 -> Yaxshi\n"
        "55 -> Qoniqarli\n"
        "30 -> Qoniqarsiz\n"
    ),
    "Sikl va shart birga": "15\n30\n45\n",
    "Lug'at (dictionary)": "d: 1\na: 2\ns: 2\nt: 1\nu: 1\nr: 1\nl: 1\nh: 1\n",
    "Sinf (class) yaratish": "Ozodbek: 4.50\n",

    # Quyidagi uchtasi JavaScript va ular YUQORIDAGI RO'YXATDA YO'Q:
    # bazaga qo'lda kiritilgan, bu buyruq ularni yaratmaydi. Lekin
    # tekshirish maydoni ularga ham kerak, shuning uchun natijalari
    # shu yerda turadi va mavjud yozuvga to'ldiriladi.
    "Salom Node.js!": "Salom Node.js\n",
    "O'zgaruvchilar bilan ishlash": "Ozodbek\n",
    "Arifmetik amallar": "20\n",
}


class Command(BaseCommand):
    help = "Python topshiriqlarini qo'shadi (mavjudlariga tegmaydi)"

    @transaction.atomic
    def handle(self, *args, **options):
        # Yangilari mavjudlardan keyin tursin
        last_order = Challenge.objects.order_by('-order').values_list(
            'order', flat=True
        ).first() or 0

        added = 0
        filled = 0
        for i, data in enumerate(CHALLENGES, start=1):
            expected = EXPECTED.get(data['title'], '')
            challenge, created = Challenge.objects.get_or_create(
                title=data['title'],
                defaults={
                    **data,
                    'expected_output': expected,
                    'language': Challenge.Language.PYTHON,
                    'order': last_order + i,
                },
            )

            # MAVJUD TOPSHIRIQQA FAQAT SHU MAYDON QO'SHILADI.
            #
            # Tekshirish keyinroq qo'shilgan imkoniyat: bazadagi eski
            # topshiriqlarda `expected_output` bo'sh va usiz "Tekshirish"
            # tugmasi umuman chiqmaydi. Qolgan maydonlarga TEGILMAYDI —
            # ular panelda tahrirlangan bo'lishi mumkin.
            if not created and expected and not (challenge.expected_output or '').strip():
                challenge.expected_output = expected
                challenge.save(update_fields=['expected_output'])
                filled += 1

            mark = self.style.SUCCESS("qo'shildi") if created else "mavjud"
            self.stdout.write(f"  [{mark}] {challenge.title}")
            added += int(created)

        # RO'YXATDA YO'Q topshiriqlar (JavaScript) — ular bu buyruq
        # bilan yaratilmaydi, faqat tekshirish maydoni to'ldiriladi.
        seeded_titles = {item['title'] for item in CHALLENGES}
        for title, expected in EXPECTED.items():
            if title in seeded_titles:
                continue
            filled += Challenge.objects.filter(
                title=title, expected_output=''
            ).update(expected_output=expected)

        if filled:
            self.stdout.write(f"\n{filled} ta topshiriqqa kutilgan natija qo'shildi.")

        self.stdout.write(self.style.SUCCESS(
            f"\n{added} ta yangi Python topshirig'i. "
            f"Jami: {Challenge.objects.count()} "
            f"({Challenge.objects.filter(language='python').count()} Python, "
            f"{Challenge.objects.filter(language='javascript').count()} JavaScript)"
        ))
