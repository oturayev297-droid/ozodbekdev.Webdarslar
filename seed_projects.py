import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stitch_backend.settings')
django.setup()

from core.models import Project

def seed_projects():
    # If projects already exist, clear them to ensure fresh premium content
    Project.objects.all().delete()

    projects_data = [
        {
            "title": "Nexus OS Dashboard",
            "description": "Futuristik va interaktiv boshqaruv paneli. Real-time ma'lumotlar, chiroyli grafiklar va shisha effekti (glassmorphism) bilan boyitilgan.",
            "image_url": "https://img.freepik.com/free-vector/gradient-ui-ux-background_23-2149051556.jpg",
            "difficulty": "Pro",
            "tech_stack": "React, TailwindCSS, Chart.js, Framer Motion",
            "demo_url": "https://example.com/demo1",
            "repo_url": "https://github.com/example/nexus-os",
            "order": 1
        },
        {
            "title": "Cyber-Market E-commerce",
            "description": "To'liq funksional onlayn do'kon. Savatcha tizimi, to'lov integratsiyasi va kiberpank uslubidagi dizayn.",
            "image_url": "https://img.freepik.com/free-vector/cyber-monday-landing-page-template_23-2148722256.jpg",
            "difficulty": "Architect",
            "tech_stack": "Next.js, Node.js, MongoDB, Stripe",
            "demo_url": "https://example.com/demo2",
            "repo_url": "https://github.com/example/cyber-market",
            "order": 2
        },
        {
            "title": "AI Image Generator",
            "description": "OpenAI API orqali rasmlar yaratuvchi portal. Promptlar bilan ishlash va galereya tizimi mavjud.",
            "image_url": "https://img.freepik.com/free-vector/artificial-intelligence-landing-page_23-2148386373.jpg",
            "difficulty": "Pro",
            "tech_stack": "React, Python, OpenAI API, AWS S3",
            "demo_url": "https://example.com/demo3",
            "repo_url": "https://github.com/example/ai-gen",
            "order": 3
        },
        {
            "title": "Social Nexus Network",
            "description": "Kichik ijtimoiy tarmoq platformasi. Postlar, daxshatli animatsiyalar va real-vaqtda muloqot qilish imkoniyati.",
            "image_url": "https://img.freepik.com/free-vector/social-media-landing-page_23-2148293345.jpg",
            "difficulty": "Architect",
            "tech_stack": "Socket.io, Express, Redis, PostgreSQL",
            "demo_url": "https://example.com/demo4",
            "repo_url": "https://github.com/example/social-nexus",
            "order": 4
        },
        {
            "title": "Quantum Portfolio Template",
            "description": "Dasturchilar uchun minimalist va zamonaviy portfolio. 3D elementlar va silliq sahifa o'tishlariga ega.",
            "image_url": "https://img.freepik.com/free-vector/flat-design-portfolio-landing-page_23-2149129596.jpg",
            "difficulty": "Entry",
            "tech_stack": "HTML5, Vanilla JS, GSAP, CSS3",
            "demo_url": "https://example.com/demo5",
            "repo_url": "https://github.com/example/quantum-port",
            "order": 5
        }
    ]

    for data in projects_data:
        Project.objects.create(**data)

    print(f"Muvaffaqiyatli yakunlandi! {len(projects_data)} ta ultra-premium loyiha kiritildi.")

if __name__ == '__main__':
    seed_projects()
