import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stitch_backend.settings')
django.setup()

from core.models import Category, Module, Lesson

def populate():
    with open('population_log.txt', 'w') as f:
        f.write("Starting population...\n")
        try:
            # Delete old categories
            count_del = Category.objects.all().delete()
            f.write(f"Deleted old data: {count_del}\n")
            
            data = [
                {'name': 'Python', 'slug': 'python', 'desc': 'Python Basics'},
                {'name': 'Django', 'slug': 'django', 'desc': 'Django Framework'},
                {'name': 'React', 'slug': 'react', 'desc': 'React UI Library'},
                {'name': 'JavaScript', 'slug': 'javascript', 'desc': 'Modern JavaScript'},
            ]
            
            for item in data:
                cat = Category.objects.create(name=item['name'], slug=item['slug'], description=item['desc'])
                mod = Module.objects.create(category=cat, title='Basics', order=0)
                Lesson.objects.create(module=mod, title=f'{item["name"]} Lesson 1', theory='Theory here', practice_code='print("Hello")', order=0)
                f.write(f"Created {item['name']} with slug {item['slug']}\n")
            
            f.write(f"Final Category count: {Category.objects.count()}\n")
            f.write(f"Final Lesson count: {Lesson.objects.count()}\n")
            f.write("DONE\n")
        except Exception as e:
            f.write(f"ERROR: {str(e)}\n")

if __name__ == '__main__':
    populate()
