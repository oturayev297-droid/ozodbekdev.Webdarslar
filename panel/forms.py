"""
Panel formalari
===============

DIQQAT — `is_free`:

Dars bepulmi yoki obuna talab qiladimi, shu bayroq hal qiladi va u
ATAYLAB standart holatda O'CHIQ (`Lesson.is_free` default=False).
Formada ham u ochiq qoldirilmaydi: yangi dars qo'shilganda u avtomatik
PULLIK bo'ladi. Teskarisi bo'lganda, e'tibordan chetda qolgan bitta
bayroq butun kursni bepulga chiqarib yuborardi.
"""

from django import forms

from core.models import Lesson, Module

#: Tailwind bilan bo'yalgan maydonlar uchun umumiy sinflar
INPUT = (
    "w-full bg-slate-900/60 border border-white/10 rounded-xl px-4 py-3 "
    "text-slate-100 placeholder-slate-500 focus:border-primary focus:ring-1 "
    "focus:ring-primary outline-none transition"
)
TEXTAREA = INPUT + " font-mono text-sm leading-relaxed"


class ModuleForm(forms.ModelForm):
    class Meta:
        model = Module
        fields = ['category', 'title', 'order']
        labels = {
            'category': "Bo'lim",
            'title': "Modul nomi",
            'order': "Tartib raqami",
        }
        widgets = {
            'category': forms.Select(attrs={'class': INPUT}),
            'title': forms.TextInput(attrs={'class': INPUT}),
            'order': forms.NumberInput(attrs={'class': INPUT}),
        }


class LessonForm(forms.ModelForm):
    class Meta:
        model = Lesson
        fields = [
            'module',
            'title',
            'order',
            'theory',
            'practice_code',
            'video_url',
            'video_file',
            'is_free',
        ]
        labels = {
            'module': "Modul",
            'title': "Dars nomi",
            'order': "Tartib raqami",
            'theory': "Nazariya",
            'practice_code': "Kod namunasi",
            'video_url': "Video havolasi (tashqi)",
            'video_file': "Video fayl",
            'is_free': "Bepul dars (obunasiz ochiq)",
        }
        help_texts = {
            'theory': (
                "Dars matni. Test generatsiya qilish uchun kamida 200 belgi "
                "bo'lishi kerak — qisqa matndan savol chiqmaydi."
            ),
            'is_free': "Belgilanmasa dars OBUNA talab qiladi. Standart holat — pullik.",
            'video_file': "Katta fayl yuklash uzoq davom etadi. Sahifani yopmang.",
        }
        widgets = {
            'module': forms.Select(attrs={'class': INPUT}),
            'title': forms.TextInput(attrs={'class': INPUT}),
            'order': forms.NumberInput(attrs={'class': INPUT}),
            'theory': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 12}),
            'practice_code': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 8}),
            'video_url': forms.URLInput(attrs={'class': INPUT}),
            'video_file': forms.ClearableFileInput(attrs={'class': INPUT}),
            'is_free': forms.CheckboxInput(
                attrs={'class': "w-5 h-5 rounded bg-slate-900 border-white/20 text-primary"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Modul ro'yxatida bo'lim nomi ham ko'rinsin — bir xil nomli
        # modullar turli bo'limlarda uchraydi
        self.fields['module'].queryset = Module.objects.select_related('category').order_by(
            'category__name', 'order'
        )
        self.fields['module'].label_from_instance = (
            lambda obj: f"{obj.category.name} / {obj.title}"
        )

    def clean(self):
        cleaned = super().clean()
        # Ikkalasi ham bo'sh bo'lsa dars ochilganda bo'sh sahifa
        # ko'rinardi — o'quvchi buni nosozlik deb qabul qiladi.
        if not (cleaned.get('theory') or '').strip() and not cleaned.get('video_file') \
                and not cleaned.get('video_url'):
            raise forms.ValidationError(
                "Darsda hech bo'lmasa nazariya matni yoki video bo'lishi kerak."
            )
        return cleaned
