import os
import django
from django.utils.text import slugify

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stitch_backend.settings')
django.setup()

from core.models import Category, Module, Lesson

def populate():
    # Clear existing data to avoid slug conflicts and start fresh
    print("Clearing old categories and lessons...")
    Category.objects.all().delete()
    
    # Define Categories and their sample lessons
    # Slugs MUST match frontend expectations: 'python', 'django', 'react', 'javascript'
    data = [
        {
            'name': 'Python',
            'slug': 'python',
            'description': 'Python dasturlash tili asoslari',
            'modules': [
                {
                    'title': 'Kirish',
                    'lessons': [
                        {'title': 'Python o\'rnatish', 'theory': 'Pythonni rasmiy saytdan yuklab oling...', 'code': 'print("Hello World")'},
                        {'title': 'O\'zgaruvchilar', 'theory': 'O\'zgaruvchilar ma\'lumotni saqlash uchun ishlatiladi.', 'code': 'x = 5\ny = "Hello"'},
                        {'title': 'Ma\'lumot turlari', 'theory': 'Python da int, str, float va boshqa turlar bor.', 'code': 'price = 10.5\nname = "Olma"'},
                    ]
                }
            ]
        },
        {
            'name': 'Django',
            'slug': 'django',
            'description': 'Django framework bilan tanishish',
            'modules': [
                {
                    'title': 'Boshlang\'ich',
                    'lessons': [
                        {'title': 'Django o\'rnatish', 'theory': 'pip install django', 'code': 'django-admin startproject myproject'},
                        {'title': 'Model va Migratsiya', 'theory': 'Modellar ma\'lumotlar bazasi strukturasini belgilaydi.', 'code': 'class Item(models.Model):\n    name = models.CharField(max_length=100)'},
                    ]
                }
            ]
        },
        {
            'name': 'React',
            'slug': 'react',
            'description': 'React kutubxonasi va komponentlar',
            'modules': [
                {
                    'title': 'React Asoslari',
                    'lessons': [
                        {'title': 'React nima?', 'theory': 'React - UI qurish uchun JavaScript kutubxonasi.', 'code': 'npx create-react-app my-app'},
                        {'title': 'Komponentlar', 'theory': 'React ilovani mayda bo\'laklarga (komponentlarga) bo\'lib boshqarish imkonini beradi.', 'code': 'function MyButton() {\n  return <button>Click me</button>;\n}'},
                    ]
                }
            ]
        },
        {
            'name': 'JavaScript',
            'slug': 'javascript',
            'description': 'Zamonaviy JavaScript (ES6+)',
            'modules': [
                {
                    'title': 'JS Kirish',
                    'lessons': [
                        {'title': 'Sintaksis', 'theory': 'JS o\'zgaruvchilari let, const, var bilan e\'lon qilinadi.', 'code': 'let a = 10;'},
                        {'title': 'Funksiyalar', 'theory': 'Arrow functions va oddiy funksiyalar.', 'code': 'const add = (a, b) => a + b;'},
                    ]
                }
            ]
        }
    ]

    print("Populating database...")

    for item in data:
        category, created = Category.objects.get_or_create(
            name=item['name'], 
            defaults={
                'slug': item['slug'],
                'description': item['description']
            }
        )
        if created:
            print(f"Created Category: {item['name']} (slug: {item['slug']})")
        else:
            # Update slug if it was empty or different
            category.slug = item['slug']
            category.save()
            print(f"Updated slug for {item['name']}: {item['slug']}")

        for i, mod_data in enumerate(item['modules']):
            module, m_created = Module.objects.get_or_create(
                category=category, 
                title=mod_data['title'], 
                defaults={'order': i}
            )
            
            for j, lesson_data in enumerate(mod_data['lessons']):
                lesson, l_created = Lesson.objects.update_or_create(
                    module=module, 
                    title=lesson_data['title'], 
                    defaults={
                        'theory': lesson_data['theory'],
                        'practice_code': lesson_data['code'],
                        'order': j
                    }
                )
                print(f"  - Synchronized Lesson: {lesson_data['title']}")

    print("Database population complete!")

if __name__ == '__main__':
    populate()
