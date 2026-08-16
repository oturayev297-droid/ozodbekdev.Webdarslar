"""
Dars matnini HTML ga aylantirish testlari.

ASOSIY E'TIBOR — XAVFSIZLIK. Natija brauzerda `innerHTML` ga
qo'yiladi, ya'ni bu funksiyadan chiqqan har qanday teg SAHIFADA
BAJARILADI. Shuning uchun "chiqishda faqat biz qo'ygan teglar bo'lsin"
degan qoida testlar bilan mahkamlab qo'yilgan.
"""

from django.test import TestCase

from core import richtext


class SecurityTests(TestCase):
    """Chiqishda faqat ruxsat etilgan teglar bo'lishi."""

    def test_script_tegi_matnga_aylanadi(self):
        html = richtext.render("<script>alert('xss')</script>")
        self.assertNotIn('<script', html)
        self.assertIn('&lt;script&gt;', html)

    def test_hodisa_atributi_otmaydi(self):
        """
        `onerror=` MATNI chiqishda qolishi mumkin va bu xavfsiz — teg
        bo'lmagach, atribut ham yo'q. Muhimi: `<img` tegi qurilmasin va
        `<` belgisi ekranlangan bo'lsin.
        """
        html = richtext.render('<img src=x onerror="alert(1)">')
        self.assertNotIn('<img', html)
        self.assertIn('&lt;img', html)

    def test_bolingan_teg_hiylasi_ishlamaydi(self):
        """
        "Keraksiz teglarni olib tashlash" yondashuvi aynan shu yerda
        sinardi: `<scr<script>ipt>` filtrdan o'tib, brauzerda butun
        teg bo'lib yig'ilardi. Biz avval EKRANLAYMIZ, shuning uchun
        bunday hiyla umuman ta'sir qilmaydi.
        """
        html = richtext.render('<scr<script>ipt>alert(1)</scr</script>ipt>')
        self.assertNotIn('<script', html)

    def test_javascript_havolasi_rad_etiladi(self):
        html = richtext.render('[bosing](javascript:alert(1))')
        self.assertNotIn('javascript:', html)
        self.assertNotIn('<a ', html)
        # Matn qoladi — foydalanuvchi nima yozilganini ko'rsin
        self.assertIn('bosing', html)

    def test_data_havolasi_rad_etiladi(self):
        html = richtext.render('[bosing](data:text/html,<script>alert(1)</script>)')
        self.assertNotIn('<a ', html)

    def test_https_havolasi_otadi(self):
        html = richtext.render('[sayt](https://example.uz)')
        self.assertIn('href="https://example.uz"', html)
        self.assertIn('rel="noopener noreferrer"', html)

    def test_havola_matnidagi_teg_ham_ekranlanadi(self):
        html = richtext.render('[<b>qalin</b>](https://example.uz)')
        self.assertNotIn('<b>', html)

    def test_kod_ichidagi_teg_bajarilmaydi(self):
        html = richtext.render('Bu `<script>` tegi')
        self.assertNotIn('<script>', html)
        self.assertIn('<code>&lt;script&gt;</code>', html)


class FormattingTests(TestCase):
    """Bezaklar to'g'ri ishlashi."""

    def test_sarlavhalar(self):
        self.assertIn('<h3>Katta</h3>', richtext.render('## Katta'))
        self.assertIn('<h4>Kichik</h4>', richtext.render('### Kichik'))

    def test_h1_ham_h3_ga_tushadi(self):
        """Sahifada dars nomi allaqachon h1 — matn ichidan yana h1 chiqmasin."""
        self.assertIn('<h3>', richtext.render('# Sarlavha'))
        self.assertNotIn('<h1>', richtext.render('# Sarlavha'))

    def test_qalin_va_kursiv(self):
        self.assertIn('<strong>muhim</strong>', richtext.render('**muhim**'))
        self.assertIn('<em>eslatma</em>', richtext.render('*eslatma*'))

    def test_yulduzcha_qalinni_buzmaydi(self):
        """`**a**` kursivga bo'linib ketmasligi kerak."""
        html = richtext.render('**a**')
        self.assertIn('<strong>a</strong>', html)
        self.assertNotIn('<em>', html)

    def test_belgili_royxat(self):
        html = richtext.render("- birinchi\n- ikkinchi")
        self.assertIn('<ul>', html)
        self.assertEqual(html.count('<li>'), 2)

    def test_raqamli_royxat(self):
        html = richtext.render("1. birinchi\n2. ikkinchi")
        self.assertIn('<ol>', html)
        self.assertEqual(html.count('<li>'), 2)

    def test_eslatma(self):
        self.assertIn('<blockquote>', richtext.render('> diqqat'))

    def test_ajratuvchi_chiziq(self):
        self.assertIn('<hr>', richtext.render('---'))

    def test_kod_bloki(self):
        html = richtext.render("```\nprint('salom')\n```")
        self.assertIn('<pre><code>', html)
        self.assertIn("print(&#x27;salom&#x27;)", html)

    def test_kod_blokida_ortiqcha_bosh_qator_yoq(self):
        """`<pre>` ichida har bir qator ko'rinadi — boshida bo'sh qator turmasin."""
        html = richtext.render("```\nkod\n```")
        self.assertIn('<pre><code>kod</code></pre>', html)

    def test_kod_blokidagi_bezaklar_ishlamaydi(self):
        """Kodda ** va ## — bu kodning o'zi, bezak emas."""
        html = richtext.render("```\n## sarlavha emas **qalin emas**\n```")
        self.assertNotIn('<h3>', html)
        self.assertNotIn('<strong>', html)

    def test_bosh_qator_yangi_xatboshi_ochadi(self):
        html = richtext.render("Birinchi\n\nIkkinchi")
        self.assertEqual(html.count('<p>'), 2)

    def test_royxat_va_matn_aralashganda_bloklar_yopiladi(self):
        html = richtext.render("Matn\n\n- element\n\nYana matn")
        self.assertEqual(html.count('<ul>'), 1)
        self.assertEqual(html.count('</ul>'), 1)
        self.assertEqual(html.count('<p>'), html.count('</p>'))

    def test_bosh_matn_bosh_natija(self):
        self.assertEqual(richtext.render(''), '')
        self.assertEqual(richtext.render(None), '')

    def test_juda_uzun_matn_kesiladi(self):
        html = richtext.render('a' * (richtext.MAX_LENGTH + 5000))
        self.assertLess(len(html), richtext.MAX_LENGTH + 100)

    def test_windows_qator_oxiri(self):
        html = richtext.render("Bir\r\n\r\nIkki")
        self.assertNotIn('\r', html)
        self.assertEqual(html.count('<p>'), 2)


class SummaryTests(TestCase):
    """Ro'yxatlardagi qisqa tavsif."""

    def test_bezaklar_olib_tashlanadi(self):
        summary = richtext.plain_summary("## Sarlavha\n\n**Qalin** va `kod`")
        for marker in ('##', '**', '`'):
            self.assertNotIn(marker, summary)

    def test_raqamli_royxat_markeri_olib_tashlanadi(self):
        summary = richtext.plain_summary("1. Birinchi\n2. Ikkinchi")
        self.assertNotIn('1.', summary)
        self.assertIn('Birinchi', summary)

    def test_kod_bloki_tavsifga_kirmaydi(self):
        summary = richtext.plain_summary("Matn\n\n```\nkod bloki\n```\n\nDavomi")
        self.assertNotIn('kod bloki', summary)

    def test_havola_matni_qoladi(self):
        summary = richtext.plain_summary('[Sayt](https://example.uz) haqida')
        self.assertIn('Sayt', summary)
        self.assertNotIn('https://', summary)

    def test_uzun_matn_sozning_ortasidan_kesilmaydi(self):
        summary = richtext.plain_summary('so\'z ' * 100, length=50)
        self.assertTrue(summary.endswith('...'))
        self.assertLessEqual(len(summary), 55)

    def test_qisqa_matn_ozgarmaydi(self):
        self.assertEqual(richtext.plain_summary('Qisqa matn'), 'Qisqa matn')


class ParagraphWrapTests(TestCase):
    """
    Manbadagi qator uzilishi ekranga KO'CHMASLIGI.

    NEGA MUHIM: dars matni faylda o'qish uchun qulay kenglikda
    (~72 belgi) yoziladi. Har bir qator `<br>` ga aylansa, matn
    telefonda ham, katta monitorda ham o'sha 72 belgida uzilib
    ko'rinardi — ya'ni o'quvchining ekraniga umuman moslashmasdi.
    """

    def test_bitta_qator_uzilishi_br_bermaydi(self):
        html = richtext.render("Birinchi qator\nikkinchi qator")
        self.assertNotIn('<br>', html)
        self.assertEqual(html.count('<p>'), 1)

    def test_qatorlar_bitta_xatboshida_qoladi(self):
        """
        Chiqishda qator uzilishi qolishi mumkin (`<p>Bir\\n ikki`) —
        HTML uni bo'sh joyga aylantiradi. Muhimi: `<br>` yo'q va
        ikkala so'z BITTA xatboshi ichida.
        """
        html = richtext.render("Bir\nikki")
        collapsed = ' '.join(html.split())
        self.assertIn('<p>Bir ikki </p>', collapsed + ' ')
        self.assertNotIn('<br>', html)

    def test_bosh_qator_yangi_xatboshi_beradi(self):
        html = richtext.render("Bir\n\nIkki")
        self.assertEqual(html.count('<p>'), 2)
        self.assertNotIn('<br>', html)


class ListContinuationTests(TestCase):
    """
    Uzun ro'yxat elementining ikkinchi qatori ro'yxatda QOLISHI.

    NEGA: manbada uzun element ikki qatorga bo'linadi va ikkinchisi
    ichkariga suriladi. Busiz tekshiruv u yangi xatboshi deb qaralib,
    element ekranda yarmida uzilib, davomi pastda alohida matn bo'lib
    turardi.
    """

    SOURCE = (
        "- **Til modeli** — matn bilan ishlaydigan tur.\n"
        "  ChatGPT va Claude shu turga kiradi.\n"
        "- Ikkinchi element\n"
        "\n"
        "Oddiy matn."
    )

    def test_davomi_shu_elementga_qoshiladi(self):
        html = richtext.render(self.SOURCE)
        self.assertIn('ChatGPT va Claude shu turga kiradi.</li>', html)

    def test_element_soni_ozgarmaydi(self):
        html = richtext.render(self.SOURCE)
        self.assertEqual(html.count('<li>'), 2)

    def test_royxatdan_keyingi_matn_alohida_qoladi(self):
        html = richtext.render(self.SOURCE)
        self.assertIn('<p>Oddiy matn.', html)
        self.assertEqual(html.count('<ul>'), 1)

    def test_raqamli_royxatda_ham_ishlaydi(self):
        html = richtext.render("1. Birinchi qadam\n   uning davomi\n2. Ikkinchi")
        self.assertIn('uning davomi</li>', html)
        self.assertEqual(html.count('<li>'), 2)

    def test_surilmagan_qator_royxatni_yopadi(self):
        """Ichkariga surilmagan qator — bu yangi xatboshi, davomi emas."""
        html = richtext.render("- Element\nSurilmagan qator")
        self.assertIn('<p>Surilmagan qator', html)
        self.assertEqual(html.count('<li>'), 1)
