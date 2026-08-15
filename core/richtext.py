"""
Dars matnini HTML ga aylantirish
================================

NEGA O'ZIMIZ YOZDIK: o'qituvchi HTML bilmasligi kerak. U oddiy matn
yozadi, biz uni serverda xavfsiz HTML ga aylantiramiz.

XAVFSIZLIK QOIDASI (buzilmasin):

    AVVAL HAMMASI EKRANLANADI, KEYIN faqat biz qo'ygan teglar
    qaytariladi.

Teskarisi — "keraksiz teglarni olib tashlash" — hech qachon to'liq
ishlamaydi: `<scr<script>ipt>` kabi hiylalar filtrdan o'tib ketadi. Shu
sabab bu yerda hech qachon "qora ro'yxat" ishlatilmaydi.

Matn admin tomonidan yoziladi, ya'ni manba nisbatan ishonchli. Lekin
himoya baribir kerak: dars matni kelajakda boshqa joydan (import,
generatsiya) kelib qolishi mumkin, o'shanda bu funksiya yagona to'siq
bo'lib qoladi.

QO'LLAB-QUVVATLANADIGAN BELGILAR (Markdown ning kichik qismi):

    ## Sarlavha              -> <h3>
    ### Kichik sarlavha      -> <h4>
    **qalin**                -> <strong>
    *kursiv*                 -> <em>
    `kod`                    -> <code>
    ```                      -> <pre><code> ... </code></pre>
    - ro'yxat                -> <ul><li>
    1. raqamli ro'yxat       -> <ol><li>
    > eslatma                -> <blockquote>
    ---                      -> <hr>
    [matn](https://...)      -> <a> (faqat http/https)
    bo'sh qator              -> yangi <p>

Rasmlar bu yerda EMAS: ular `LessonImage` modelida alohida turadi.
Sababi — rasm fayli bazada boshqariladi, matn ichidagi havola esa
fayl o'chirilganda "singan rasm" bo'lib qolardi.
"""

import re
from html import escape

#: Havolalarda faqat shu sxemalarga ruxsat. `javascript:` ni to'sish
#: uchun oq ro'yxat ishlatiladi — `javascript` so'zini qidirish emas,
#: chunki uni yashirish yo'llari juda ko'p.
ALLOWED_SCHEMES = ('http://', 'https://')

#: Bir dars matnining eng katta uzunligi. Cheklovsiz bitta yozuv
#: sahifani ham, bazani ham cho'ktirib qo'yishi mumkin.
MAX_LENGTH = 100_000

_BOLD = re.compile(r'\*\*(.+?)\*\*', re.DOTALL)
_ITALIC = re.compile(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', re.DOTALL)
_CODE = re.compile(r'`([^`]+?)`')
#: Havola. Manzil ichida BITTA daraja qavs bo'lishi mumkin —
#: Vikipediya havolalarida bu odatiy hol:
#: https://uz.wikipedia.org/wiki/Python_(dasturlash_tili)
_LINK = re.compile(r'\[([^\]]+)\]\(([^()\s]*(?:\([^()\s]*\)[^()\s]*)*)\)')


def _inline(text: str) -> str:
    """
    Qator ichidagi belgilar.

    DIQQAT — TARTIB MUHIM: matn allaqachon ekranlangan holda keladi.
    Shu sabab bu yerda faqat BIZ qo'shayotgan teglar paydo bo'ladi,
    foydalanuvchi yozgani esa `&lt;` bo'lib qolaveradi.
    """
    # Kod birinchi: uning ichidagi ** va * bezak sifatida o'qilmasin
    placeholders = []

    def stash_code(match):
        placeholders.append(f"<code>{match.group(1)}</code>")
        return f"\x00{len(placeholders) - 1}\x00"

    text = _CODE.sub(stash_code, text)

    text = _BOLD.sub(r'<strong>\1</strong>', text)
    text = _ITALIC.sub(r'<em>\1</em>', text)

    def link(match):
        label, href = match.group(1), match.group(2)
        # Ekranlashda & -> &amp; bo'lgani uchun havolani qaytaramiz,
        # aks holda manzildagi parametrlar buzilardi
        href = href.replace('&amp;', '&')
        if not href.lower().startswith(ALLOWED_SCHEMES):
            # Ruxsatsiz sxema — havola emas, oddiy matn bo'lib qoladi
            return label
        return f'<a href="{escape(href, quote=True)}" target="_blank" rel="noopener noreferrer">{label}</a>'

    text = _LINK.sub(link, text)

    for i, code in enumerate(placeholders):
        text = text.replace(f"\x00{i}\x00", code)

    return text


def render(raw: str) -> str:
    """
    Dars matnini HTML ga aylantiradi.

    Natija `innerHTML` ga qo'yish uchun xavfsiz: kirish matni to'liq
    ekranlangan, chiqishdagi teglar esa faqat shu funksiya qo'shgan.
    """
    if not raw:
        return ''

    raw = raw[:MAX_LENGTH]
    # Windows va Mac qator oxirlarini bir ko'rinishga keltiramiz
    raw = raw.replace('\r\n', '\n').replace('\r', '\n')

    lines = escape(raw).split('\n')

    out = []
    #: Ochiq turgan blok: None | 'p' | 'ul' | 'ol' | 'pre' | 'quote'
    block = None
    #: Kod bloki qatorlari. ALOHIDA YIG'ILADI, chunki `<pre>` ichida har
    #: bir qator oxiri ko'rinadi: umumiy ro'yxatga qo'shilsa,
    #: `<pre><code>` dan keyin ortiqcha bo'sh qator paydo bo'lardi.
    pre_lines = []

    def close():
        nonlocal block
        if block == 'p':
            out.append('</p>')
        elif block == 'ul':
            out.append('</ul>')
        elif block == 'ol':
            out.append('</ol>')
        elif block == 'pre':
            # Oxiridagi bo'sh qatorlar kesiladi — ular kodning qismi emas
            while pre_lines and not pre_lines[-1].strip():
                pre_lines.pop()
            out.append('<pre><code>' + '\n'.join(pre_lines) + '</code></pre>')
            pre_lines.clear()
        elif block == 'quote':
            out.append('</blockquote>')
        block = None

    for line in lines:
        stripped = line.strip()

        # ── Kod bloki ──
        # Ichidagi hamma narsa o'zgarishsiz qoladi: kodda ** va #
        # bezak emas, kodning o'zi.
        if stripped.startswith('```'):
            if block == 'pre':
                close()
            else:
                close()
                block = 'pre'
            continue

        if block == 'pre':
            pre_lines.append(line)
            continue

        # ── Bo'sh qator: blokni yopadi ──
        if not stripped:
            close()
            continue

        # ── Ajratuvchi chiziq ──
        if stripped in ('---', '***', '___'):
            close()
            out.append('<hr>')
            continue

        # ── Sarlavhalar ──
        # h1 va h2 ATAYLAB yo'q: sahifada dars nomi allaqachon h1/h2.
        # Matn ichidan yana h1 chiqsa sarlavhalar ierarxiyasi buzilardi.
        if stripped.startswith('### '):
            close()
            out.append(f'<h4>{_inline(stripped[4:])}</h4>')
            continue
        if stripped.startswith('## '):
            close()
            out.append(f'<h3>{_inline(stripped[3:])}</h3>')
            continue
        if stripped.startswith('# '):
            close()
            out.append(f'<h3>{_inline(stripped[2:])}</h3>')
            continue

        # ── Eslatma ──
        if stripped.startswith('&gt; '):
            if block != 'quote':
                close()
                out.append('<blockquote>')
                block = 'quote'
            out.append(_inline(stripped[5:]))
            continue

        # ── Ro'yxat elementining DAVOMI ──
        #
        # Uzun element manbada ikki qatorga bo'linadi:
        #
        #     - **Til modeli** — matn bilan ishlaydigan tur.
        #       ChatGPT, Claude, Gemini shu turga kiradi.
        #
        # Ikkinchi qator ichkariga surilgan. Busiz tekshiruv u yangi
        # xatboshi deb qaralib, ro'yxatdan CHIQIB ketardi: ekranda
        # element yarmida uzilib, davomi pastda alohida matn bo'lib
        # turardi.
        if block in ('ul', 'ol') and line.startswith(('  ', '\t')) and out:
            previous = out[-1]
            if previous.endswith('</li>'):
                out[-1] = previous[:-5] + ' ' + _inline(stripped) + '</li>'
                continue

        # ── Belgili ro'yxat ──
        if stripped.startswith(('- ', '* ', '• ')):
            if block != 'ul':
                close()
                out.append('<ul>')
                block = 'ul'
            out.append(f'<li>{_inline(stripped[2:])}</li>')
            continue

        # ── Raqamli ro'yxat ──
        numbered = re.match(r'^(\d+)[.)]\s+(.*)$', stripped)
        if numbered:
            if block != 'ol':
                close()
                out.append('<ol>')
                block = 'ol'
            out.append(f'<li>{_inline(numbered.group(2))}</li>')
            continue

        # ── Oddiy matn ──
        if block == 'p':
            # BITTA QATOR UZILISHI — BO'SH JOY, `<br>` EMAS.
            #
            # Matn manbada o'qish uchun qulay kenglikda (~72 belgi)
            # yoziladi. Har qator `<br>` bo'lsa, ekranda matn o'sha 72
            # belgida uzilardi — telefonda ham, katta monitorda ham.
            # Xatboshi ochish uchun BO'SH QATOR qoldiriladi.
            out.append(' ' + _inline(stripped))
        else:
            close()
            out.append(f'<p>{_inline(stripped)}')
            block = 'p'

    close()
    return '\n'.join(out)


def plain_summary(raw: str, length: int = 160) -> str:
    """
    Ro'yxatlarda ko'rsatish uchun qisqa tavsif.

    Bezak belgilari OLIB TASHLANADI: kartochkada "## Sarlavha" yoki
    "**qalin**" ko'rinib qolsa, matn sinmagandek emas, tashlandiqdek
    ko'rinadi.
    """
    if not raw:
        return ''

    text = raw.replace('\r\n', '\n')
    # Kod bloklari tavsifga umuman kirmaydi
    text = re.sub(r'```.*?```', ' ', text, flags=re.DOTALL)
    # Qator boshidagi bezaklar: ##, >, -, * va raqamli ro'yxat ("1.")
    text = re.sub(r'^\s{0,3}(?:[#>\-*•]+|\d+[.)])\s*', ' ', text, flags=re.MULTILINE)
    text = _LINK.sub(r'\1', text)
    text = text.replace('**', '').replace('`', '').replace('*', '')
    text = ' '.join(text.split())

    if len(text) <= length:
        return text
    # So'zning o'rtasidan kesmaymiz
    return text[:length].rsplit(' ', 1)[0] + '...'
