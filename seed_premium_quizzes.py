import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stitch_backend.settings')
django.setup()

from core.models import Category, Module, Lesson, Quiz, Question, Choice

def seed_premium_tests():
    # Setup Hierarchy
    category, _ = Category.objects.get_or_create(name='Full-Stack Mastery', slug='full-stack-mastery')
    module, _ = Module.objects.get_or_create(category=category, title='Sertifikatlash Imtihonlari', order=10)
    
    # 1. Entry Tier (10 questions)
    lesson_entry, _ = Lesson.objects.get_or_create(module=module, title='Lvl 1: Entry Level Exam', order=1)
    quiz_entry, _ = Quiz.objects.get_or_create(lesson=lesson_entry, defaults={'title': 'Frontend & JS Asoslari (Entry)', 'time_limit': 15})
    
    # 2. Pro Tier (10 questions)
    lesson_pro, _ = Lesson.objects.get_or_create(module=module, title='Lvl 2: Pro Level Exam', order=2)
    quiz_pro, _ = Quiz.objects.get_or_create(lesson=lesson_pro, defaults={'title': 'Backend & Node.js (Pro)', 'time_limit': 20})
    
    # 3. Architect Tier (10 questions)
    lesson_arch, _ = Lesson.objects.get_or_create(module=module, title='Lvl 3: Architect Level Exam', order=3)
    quiz_arch, _ = Quiz.objects.get_or_create(lesson=lesson_arch, defaults={'title': 'Tizim Dizayni & Advanced (Architect)', 'time_limit': 25})

    def add_questions(quiz, data):
        if quiz.questions.exists(): quiz.questions.all().delete()
        for q_text, answers, correct_answer in data:
            question = Question.objects.create(quiz=quiz, text=q_text)
            for ans in answers:
                Choice.objects.create(question=question, text=ans, is_correct=(ans == correct_answer))

    # Entry Level Data
    entry_data = [
        ("HTML-da havola yaratish uchun qaysi teg ishlatiladi?", ["<link>", "<a>", "<href>", "<url>"], "<a>"),
        ("CSS-da rang berish uchun qaysi xususiyat ishlatiladi?", ["bg-color", "color", "text-style", "font-color"], "color"),
        ("Bo'shliq yaratish (ichki) uchun qaysi xususiyat ishlatiladi?", ["margin", "padding", "border", "gap"], "padding"),
        ("JavaScript-da 'alert()' nima qiladi?", ["Konsolga yozadi", "Xabar oynasini chiqaradi", "Sahifani yangilaydi", "Fonni o'zgartiradi"], "Xabar oynasini chiqaradi"),
        ("DOM nimani anglatadi?", ["Document Object Model", "Data Object Management", "Digital Online Media", "Display Object Mode"], "Document Object Model"),
        ("Qaysi CSS selectori ID-ni bildiradi?", [".", "#", "*", "@"], "#"),
        ("Massiv e'lon qilishning to'g'ri usuli?", ["let a = {}", "let a = []", "let a = ()", "let a = <>"], "let a = []"),
        ("Input turini 'parol' qilish uchun qaysi qiymat ishlatiladi?", ["text", "secret", "password", "hidden"], "password"),
        ("Brauzerda JS-ni qaysi tab orqali debug qilsa bo'ladi?", ["Elements", "Console", "Network", "Sources"], "Console"),
        ("CSS-da elementni markazga keltirishning eng zamonaviy usuli?", ["float", "flexbox", "table-align", "margin-left"], "flexbox"),
    ]

    # Pro Level Data
    pro_data = [
        ("Node.js-da 'npm init' nima qiladi?", ["Serverni ishga tushiradi", "package.json faylini yaratadi", "Modullarni o'chiradi", "Hech narsa"], "package.json faylini yaratadi"),
        ("Middleware nima?", ["Ma'lumotlar bazasi", "So'rov va javob o'rtasidagi funksiya", "Frontend kutubxonasi", "Dasturlash tili"], "So'rov va javob o'rtasidagi funksiya"),
        ("JWT nima uchun ishlatiladi?", ["Rasm siqish uchun", "Autentifikatsiya (Xavfsizlik)", "Video oqim uchun", "Sizdagi xatolarni tuzatish"], "Autentifikatsiya (Xavfsizlik)"),
        ("Mongoose nima?", ["JavaScript freymvorki", "MongoDB uchun ODM kutubxonasi", "Dizayn vositasi", "Server turi"], "MongoDB uchun ODM kutubxonasi"),
        ("HTTP 404 kodi nimani anglatadi?", ["Success", "Forbidden", "Not Found", "Internal Server Error"], "Not Found"),
        ("REST API-da ma'lumotni yangilash uchun qaysi metod ishlatiladi?", ["GET", "POST", "PUT/PATCH", "DELETE"], "PUT/PATCH"),
        ("Node.js asinxronlik kuchi nima bilan bog'liq?", ["Ko'p tarmoqlilik", "Event Loop va Non-blocking I/O", "Tezkor protsessor", "C++ tillari"], "Event Loop va Non-blocking I/O"),
        ("Environment variables (o'zgaruvchilar) qaysi faylda saqlanadi?", [".env", ".config", ".settings", ".var"], ".env"),
        ("Callback hell-dan qanday qutulish mumkin?", ["if/else ishlatib", "Promise va Async/Await orqali", "Faqat bir qator kod yozib", "Hech qanday yo'li yo'q"], "Promise va Async/Await orqali"),
        ("Express-da portni qanday tinglash mumkin?", ["app.listen()", "app.start()", "app.run()", "app.open()"], "app.listen()"),
    ]

    # Architect Level Data
    arch_data = [
        ("Microservices arxitekturasi nima?", ["Bitta katta ilova", "Ilovani kichik, mustaqil servislarga bo'lish", "Ma'lumotlar bazasi turi", "Dizayn patterni"], "Ilovani kichik, mustaqil servislarga bo'lish"),
        ("Docker nima uchun kerak?", ["Kodni formatlash", "Konteynerizatsiya uchun", "Brauzer yaratish", "Git boshqarish"], "Konteynerizatsiya uchun"),
        ("SQL va NoSQL farqi?", ["Biri pullik, biri tekin", "Biri relyatsion (jadvalli), biri hujjatsimon (schema-less)", "Farqi yo'q", "SQL faqat mobil ilovalar uchun"], "Biri relyatsion (jadvalli), biri hujjatsimon (schema-less)"),
        ("Load Balancer-ning vazifasi?", ["Elektr energiyasini tejash", "Trafikni serverlar o'rtasida taqsimlash", "Kodni xatolardan tozalash", "Faqat reklamani ko'rsatish"], "Trafikni serverlar o'rtasida taqsimlash"),
        ("CI/CD jarayoni nima?", ["Kod yozish usuli", "Avtomatik testlash va deploy qilish jarayoni", "Dizayn tizimi", "Muloqot usuli"], "Avtomatik testlash va deploy qilish jarayoni"),
        ("Redis nima uchun ishlatiladi?", ["Rasm tahrirlash", "Keshlashtirish va tezkor xotira (In-memory buffer)", "Admin panel yaratish", "Faqat o'yinlar uchun"], "Keshlashtirish va tezkor xotira (In-memory buffer)"),
        ("Event-Driven Architecture nima?", ["Faqat tugmalar bosilishi", "Voqealar (events) orqali tizimlararo muloqot", "Darslik turi", "Hech narsa"], "Voqealar (events) orqali tizimlararo muloqot"),
        ("Scalability (Masshtablilik) turlari?", ["Vertical va Horizontal", "Big va Small", "Fast va Slow", "Internal va External"], "Vertical va Horizontal"),
        ("Idempotency (Idempotentlik) API-da nimani anglatadi?", ["Tez ishlash", "Bir xil so'rovni bir necha marta yuborganda natija o'zgarmasligi", "Xavfsiz ulanish", "Ma'lumotlarni o'chirish"], "Bir xil so'rovni bir necha marta yuborganda natija o'zgarmasligi"),
        ("Kubernetes (K8s) nima?", ["Konteynerlarni boshqarish (Orchestration) platformasi", "Dasturlash tili", "OS nomi", "Frontend freymvorki"], "Konteynerlarni boshqarish (Orchestration) platformasi"),
    ]

    add_questions(quiz_entry, entry_data)
    add_questions(quiz_pro, pro_data)
    add_questions(quiz_arch, arch_data)

    print("Ultra-Premium Quiz Seeding Complete: Entry, Pro, Architect tiers initialized.")

if __name__ == '__main__':
    seed_premium_tests()
