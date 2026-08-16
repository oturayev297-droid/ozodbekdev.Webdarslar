"""
Dars sxemalarini chizish
========================

NEGA KOD BILAN CHIZILADI, tayyor rasm emas:

1. Rasmlar git ga tushmaydi (`media/` e'tiborsiz qoldiriladi), demak
   yangi serverga ko'chirilganda darslar rasmsiz qolardi. Kod esa
   ko'chadi — buyruqni qayta ishga tushirish yetarli.
2. Matn tuzatilsa rasm ham darhol yangilanadi. Grafik muharrirda
   chizilgan rasmda esa xato yillab qolib ketardi.
3. Sayt rangi o'zgarsa bir joyda o'zgartiriladi.

SHRIFT: server Linux, ishlab chiqish Windows — shrift yo'llari
boshqacha. Shuning uchun bir nechta nom ketma-ket sinaladi va hech
qaysisi topilmasa Pillow ning ichki shrifti ishlatiladi. Rasm biroz
xunukroq chiqadi, lekin buyruq YIQILMAYDI: dars rasmsiz qolgandan
ko'ra oddiyroq rasm bilan bo'lgani yaxshi.
"""

import io

from PIL import Image, ImageDraw, ImageFont

#: Sayt ranglari (`templates/lessons.html` bilan bir xil)
BG = (2, 6, 23)             # slate-950
PANEL = (15, 23, 42)        # slate-900
BORDER = (30, 41, 59)       # slate-800
PRIMARY = (14, 165, 233)    # sky-500
ACCENT = (45, 212, 191)     # teal-400
TEXT = (226, 232, 240)      # slate-200
MUTED = (100, 116, 139)     # slate-500
WARN = (251, 191, 36)       # amber-400
DANGER = (248, 113, 113)    # red-400
OK = (52, 211, 153)         # emerald-400

WIDTH = 1200

#: Ketma-ket sinaladigan shriftlar: Linux, Windows, macOS
FONT_CANDIDATES = (
    "DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
)
FONT_BOLD_CANDIDATES = (
    "DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
)


def _font(size, bold=False):
    for path in (FONT_BOLD_CANDIDATES if bold else FONT_CANDIDATES):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _text_width(draw, text, font):
    return draw.textbbox((0, 0), text, font=font)[2]


def _center(draw, text, font, cx, y, fill=TEXT):
    draw.text((cx - _text_width(draw, text, font) / 2, y), text, font=font, fill=fill)


def _wrap(draw, text, font, max_width):
    """So'zlarni sig'dirib qatorlarga bo'ladi."""
    words = text.split()
    lines, current = [], ''
    for word in words:
        candidate = f"{current} {word}".strip()
        if _text_width(draw, candidate, font) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _canvas(height):
    img = Image.new('RGB', (WIDTH, height), BG)
    return img, ImageDraw.Draw(img)


def _panel(draw, box, fill=PANEL, outline=BORDER, radius=20, width=2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _arrow(draw, x1, y1, x2, y2, color=PRIMARY, width=3, head=12):
    """Gorizontal o'q."""
    draw.line([(x1, y1), (x2 - head, y2)], fill=color, width=width)
    draw.polygon(
        [(x2, y2), (x2 - head, y2 - head // 2), (x2 - head, y2 + head // 2)],
        fill=color,
    )


def _title(draw, text, y=36):
    _center(draw, text, _font(34, bold=True), WIDTH / 2, y, fill=(255, 255, 255))


def _save(img) -> bytes:
    buffer = io.BytesIO()
    img.save(buffer, format='PNG', optimize=True)
    return buffer.getvalue()


# ══════════════════════════ Sxemalar ══════════════════════════
#
# Har biri PNG baytlarini qaytaradi. Nomi `seed_ai_course` dagi
# darslarga bog'langan.


def ai_ml_llm():
    """Ichma-ich doiralar: AI > ML > Chuqur o'qitish > LLM."""
    img, draw = _canvas(620)
    _title(draw, "Sun'iy intellekt ichida nima bor")

    layers = [
        ("Sun'iy intellekt", 208, PRIMARY, "Aqlli xatti-harakat"),
        ("Mashinaviy o'qitish", 158, ACCENT, "Misollardan o'rganish"),
        ("Chuqur o'qitish", 110, WARN, "Neyron tarmoqlar"),
        ("Til modeli", 62, OK, "Matn bilan ishlash"),
    ]
    # Pastdagi izoh eng tashqi doiraga TEGMASLIGI kerak: markaz
    # yuqoriroqda va radiuslar shunga qarab tanlangan.
    cx, cy = WIDTH / 2, 320

    for name, radius, color, _ in layers:
        draw.ellipse(
            [cx - radius * 1.55, cy - radius, cx + radius * 1.55, cy + radius],
            outline=color, width=3,
        )

    # Nomlar chapdan o'ngga, doiralarning yuqori chetiga
    label_font = _font(19, bold=True)
    for i, (name, radius, color, _) in enumerate(layers):
        y = cy - radius + 10
        _center(draw, name, label_font, cx, y, fill=color)

    _center(draw, "Har biri o'zidan kattasining bir qismi",
            _font(18), cx, 560, fill=MUTED)
    return _save(img)


def next_token():
    """Model keyingi so'zni qanday tanlaydi."""
    img, draw = _canvas(560)
    _title(draw, "Model keyingi so'zni qanday tanlaydi")

    prompt_font = _font(24, bold=True)
    _panel(draw, [90, 130, 640, 210])
    draw.text((120, 155), "Bugun havo juda ...", font=prompt_font, fill=TEXT)

    _arrow(draw, 660, 170, 740, 170)

    # Ehtimolliklar
    options = [("issiq", 42), ("sovuq", 27), ("yaxshi", 18), ("qora", 3)]
    y = 130
    bar_x, bar_max = 900, 210
    for word, percent in options:
        draw.text((770, y + 8), word, font=_font(20), fill=TEXT)
        width = int(bar_max * percent / 45)
        draw.rounded_rectangle([bar_x, y + 10, bar_x + bar_max, y + 32],
                               radius=8, fill=BORDER)
        draw.rounded_rectangle([bar_x, y + 10, bar_x + width, y + 32],
                               radius=8, fill=PRIMARY if percent > 20 else MUTED)
        draw.text((bar_x + bar_max + 14, y + 10), f"{percent}%",
                  font=_font(17, bold=True), fill=MUTED)
        y += 48

    note_font = _font(19)
    lines = [
        "Model ma'noni tushunmaydi — u keyingi so'zning ehtimolini hisoblaydi.",
        "Shuning uchun bir savolga ikki marta ikki xil javob berishi mumkin.",
    ]
    y = 400
    for line in lines:
        _center(draw, line, note_font, WIDTH / 2, y, fill=MUTED)
        y += 32

    _panel(draw, [90, 468, 1110, 528], fill=(20, 12, 6), outline=(80, 60, 20))
    _center(draw, "Aynan shu sabab model ishonch bilan xato javob bera oladi",
            _font(19, bold=True), WIDTH / 2, 486, fill=WARN)
    return _save(img)


def prompt_anatomy():
    """Yaxshi promptning to'rt qismi."""
    img, draw = _canvas(640)
    _title(draw, "Yaxshi promptning to'rt qismi")

    parts = [
        ("1. ROL", PRIMARY, "Kim bo'lib javob bersin",
         "Sen 5-sinf o'qituvchisisan."),
        ("2. VAZIFA", ACCENT, "Aniq nima qilish kerak",
         "Fotosintezni tushuntir."),
        ("3. KONTEKST", WARN, "Qanday sharoitda",
         "O'quvchilar 11 yoshda."),
        ("4. FORMAT", OK, "Javob qanday ko'rinsin",
         "5 ta qisqa band, misol bilan."),
    ]

    x, y = 70, 120
    box_w, box_h = 520, 118
    for i, (name, color, hint, example) in enumerate(parts):
        col = i % 2
        row = i // 2
        bx = x + col * (box_w + 40)
        by = y + row * (box_h + 30)

        _panel(draw, [bx, by, bx + box_w, by + box_h])
        draw.rounded_rectangle([bx, by, bx + 6, by + box_h], radius=3, fill=color)

        draw.text((bx + 26, by + 16), name, font=_font(17, bold=True), fill=color)
        draw.text((bx + 26, by + 44), hint, font=_font(16), fill=MUTED)
        draw.text((bx + 26, by + 74), example, font=_font(17), fill=TEXT)

    _panel(draw, [70, 430, 1130, 590], fill=(6, 20, 26), outline=(20, 70, 80))
    draw.text((100, 452), "Hammasi birga:", font=_font(17, bold=True), fill=ACCENT)
    body_font = _font(18)
    text = ("Sen 5-sinf o'qituvchisisan. 11 yoshli o'quvchilarga fotosintezni "
            "tushuntir. Javobni 5 ta qisqa bandda ber, har biriga kundalik "
            "hayotdan misol qo'sh.")
    y = 484
    for line in _wrap(draw, text, body_font, 1000):
        draw.text((100, y), line, font=body_font, fill=TEXT)
        y += 30
    return _save(img)


def vague_vs_clear():
    """Noaniq va aniq promptni yonma-yon solishtirish."""
    img, draw = _canvas(600)
    _title(draw, "Noaniq va aniq prompt")

    columns = [
        (70, DANGER, "NOANIQ", [
            ("Prompt:", "Marketing haqida yoz."),
            ("Natija:", "Umumiy, hammaga mos, hech kimga kerak bo'lmagan matn."),
        ]),
        (630, OK, "ANIQ", [
            ("Prompt:", "Toshkentdagi kichik gul do'koni uchun "
                        "Instagram'da 7 kunlik post rejasi tuz. "
                        "Byudjet yo'q, faqat telefonda suratga olish mumkin."),
            ("Natija:", "Ishlatsa bo'ladigan, aniq rejaga aylanadigan javob."),
        ]),
    ]

    for x, color, title, rows in columns:
        _panel(draw, [x, 120, x + 500, 540])
        draw.rounded_rectangle([x, 120, x + 500, 126], radius=3, fill=color)
        draw.text((x + 30, 146), title, font=_font(20, bold=True), fill=color)

        y = 194
        for label, text in rows:
            draw.text((x + 30, y), label, font=_font(15, bold=True), fill=MUTED)
            y += 26
            for line in _wrap(draw, text, _font(18), 440):
                draw.text((x + 30, y), line, font=_font(18), fill=TEXT)
                y += 28
            y += 22

    _center(draw, "Model o'ylab topa olmaydigan narsani siz aytishingiz kerak",
            _font(19), WIDTH / 2, 562, fill=MUTED)
    return _save(img)


def few_shot():
    """Namuna berish nima uchun ishlaydi."""
    img, draw = _canvas(560)
    _title(draw, "Namuna berish (uslubni ko'rsatish)")

    _panel(draw, [70, 120, 1130, 400])
    mono = _font(19)
    lines = [
        ("Quyidagi uslubda davom ettir:", MUTED),
        ("", TEXT),
        ("Mahsulot: termos", TEXT),
        ("Tavsif: Choyingiz 12 soat issiq qoladi.", ACCENT),
        ("", TEXT),
        ("Mahsulot: noutbuk sumkasi", TEXT),
        ("Tavsif: Yomg'irda ham quruq, yelkangizda yengil.", ACCENT),
        ("", TEXT),
        ("Mahsulot: simsiz quloqchin", TEXT),
        ("Tavsif: ___", PRIMARY),
    ]
    y = 148
    for text, color in lines:
        if text:
            draw.text((110, y), text, font=mono, fill=color)
        y += 25

    _panel(draw, [70, 430, 1130, 520], fill=(6, 20, 26), outline=(20, 70, 80))
    _center(draw,
            "Ikki namunadan keyin model uslubni tushunadi: qisqa, foyda haqida, «siz»ga murojaat",
            _font(18), WIDTH / 2, 448, fill=TEXT)
    _center(draw, "Uzun tushuntirishdan ko'ra ikkita yaxshi namuna kuchliroq",
            _font(17), WIDTH / 2, 482, fill=MUTED)
    return _save(img)


def iteration_loop():
    """Prompt bilan ishlash — bir martalik emas, aylanma jarayon."""
    # Balandlik mazmunga qarab tanlangan: ortiqcha bo'sh joy qolsa
    # darsda rasm "singanday" ko'rinadi.
    img, draw = _canvas(420)
    _title(draw, "Prompt bir martada tayyor bo'lmaydi")

    steps = [
        ("Yozish", PRIMARY),
        ("Javobni o'qish", ACCENT),
        ("Nima yetishmadi?", WARN),
        ("Qo'shib aniqlashtirish", OK),
    ]
    box_w, box_h = 235, 92
    gap = 42
    total = len(steps) * box_w + (len(steps) - 1) * gap
    x = (WIDTH - total) / 2
    y = 170

    for i, (name, color) in enumerate(steps):
        bx = x + i * (box_w + gap)
        _panel(draw, [bx, y, bx + box_w, y + box_h])
        draw.rounded_rectangle([bx, y, bx + box_w, y + 5], radius=3, fill=color)
        cx = bx + box_w / 2
        for j, line in enumerate(_wrap(draw, name, _font(19, bold=True), box_w - 30)):
            _center(draw, line, _font(19, bold=True), cx, y + 34 + j * 26, fill=TEXT)
        if i < len(steps) - 1:
            _arrow(draw, bx + box_w + 8, y + box_h / 2, bx + box_w + gap - 8, y + box_h / 2)

    # Qaytish o'qi
    loop_y = y + box_h + 46
    draw.line([(x + total - box_w / 2, y + box_h), (x + total - box_w / 2, loop_y)],
              fill=MUTED, width=2)
    draw.line([(x + box_w / 2, loop_y), (x + total - box_w / 2, loop_y)],
              fill=MUTED, width=2)
    draw.line([(x + box_w / 2, loop_y), (x + box_w / 2, y + box_h + 12)],
              fill=MUTED, width=2)
    draw.polygon([(x + box_w / 2, y + box_h),
                  (x + box_w / 2 - 6, y + box_h + 12),
                  (x + box_w / 2 + 6, y + box_h + 12)], fill=MUTED)

    _center(draw, "Odatda 2-3 urinishdan keyin javob kerakli darajaga yetadi",
            _font(19), WIDTH / 2, loop_y + 40, fill=MUTED)
    return _save(img)


def hallucination():
    """Model xato javobni ham ishonch bilan beradi."""
    img, draw = _canvas(580)
    _title(draw, "Model xatoni ham ishonch bilan aytadi")

    _panel(draw, [70, 120, 1130, 250], fill=(26, 10, 10), outline=(90, 30, 30))
    draw.text((104, 146), "Savol: «Bu qonun qachon qabul qilingan?»",
              font=_font(19, bold=True), fill=TEXT)
    draw.text((104, 186), "Javob: «2019-yil 14-martda.»  ← sana o'ylab topilgan bo'lishi mumkin",
              font=_font(19), fill=DANGER)

    _center(draw, "Model «bilmayman» deyish o'rniga ishonarli ko'rinadigan javob to'qiydi",
            _font(19), WIDTH / 2, 274, fill=MUTED)

    _panel(draw, [70, 330, 1130, 540], fill=(6, 22, 16), outline=(20, 80, 55))
    draw.text((104, 354), "Nimani doim tekshirish kerak:",
              font=_font(20, bold=True), fill=OK)

    checks = [
        "Raqamlar, sanalar va statistika",
        "Qonun, hujjat va rasmiy qoidalar",
        "Kitob, maqola va havolalar — ular umuman mavjudmi",
        "Tibbiyot, huquq va moliya bo'yicha har qanday maslahat",
    ]
    y = 394
    for item in checks:
        draw.ellipse([110, y + 7, 122, y + 19], fill=OK)
        draw.text((140, y), item, font=_font(18), fill=TEXT)
        y += 34
    return _save(img)


def privacy():
    """Modelga nima yubormaslik kerak."""
    img, draw = _canvas(520)
    _title(draw, "Modelga nima yubormaslik kerak")

    columns = [
        (70, DANGER, "YUBORMANG", [
            "Parol va kirish kalitlari",
            "Passport, JSHSHIR ma'lumotlari",
            "Karta raqami va bank ma'lumotlari",
            "Mijozlarning shaxsiy ma'lumotlari",
            "Kompaniyaning maxfiy hujjatlari",
        ]),
        (630, OK, "BEMALOL", [
            "Umumiy savollar va tushunchalar",
            "O'zingiz yozgan matn qoralamasi",
            "Ochiq ma'lumotlar bilan ishlash",
            "Nomlar o'zgartirilgan misollar",
            "O'quv topshiriqlari",
        ]),
    ]

    for x, color, title, items in columns:
        _panel(draw, [x, 120, x + 500, 440])
        draw.rounded_rectangle([x, 120, x + 500, 126], radius=3, fill=color)
        draw.text((x + 30, 146), title, font=_font(20, bold=True), fill=color)
        y = 194
        for item in items:
            draw.text((x + 30, y), "•", font=_font(18, bold=True), fill=color)
            for line in _wrap(draw, item, _font(18), 420):
                draw.text((x + 52, y), line, font=_font(18), fill=TEXT)
                y += 26
            y += 12

    _center(draw, "Yozganingiz sizdan chiqib ketadi — qaytarib bo'lmaydi",
            _font(19), WIDTH / 2, 466, fill=MUTED)
    return _save(img)


#: Buyruq shu jadval orqali rasm chaqiradi
DIAGRAMS = {
    'ai_ml_llm': ai_ml_llm,
    'next_token': next_token,
    'prompt_anatomy': prompt_anatomy,
    'vague_vs_clear': vague_vs_clear,
    'few_shot': few_shot,
    'iteration_loop': iteration_loop,
    'hallucination': hallucination,
    'privacy': privacy,
}


def render(name: str) -> bytes:
    """Nomi bo'yicha sxemani chizadi va PNG baytlarini qaytaradi."""
    if name not in DIAGRAMS:
        raise KeyError(f"Bunday sxema yo'q: {name}")
    return DIAGRAMS[name]()
