"""
Panelga kirish va huquq tekshiruvi
==================================

QOIDALAR (buzilmasligi kerak):

1. Panel FAQAT `is_staff` uchun. To'g'ri parol o'z-o'zidan yetarli emas.

2. Tizimga kirgan, lekin xodim BO'LMAGAN foydalanuvchi login sahifasiga
   QAYTARILMAYDI — u 403 oladi. Aks holda u to'g'ri parolini kiritib
   turib login sahifasiga qayta-qayta tushardi va "parolim noto'g'ri"
   deb o'ylardi.

3. Huquq HAR SO'ROVDA qayta tekshiriladi. Xodimlik olib tashlansa,
   allaqachon kirgan odam ham keyingi sahifadayoq chiqarib yuboriladi.
   Seansda "men adminman" degan bayroq SAQLANMAYDI.

4. Brute-force himoyasi o'quvchi loginidagi bilan BIR XIL modul
   (`core.lockout`). Ikkinchi nusxa yozilsa biri yangilanib ikkinchisi
   eskirib qolardi.

5. XODIM EKANINI OSHKOR QILMAYMIZ. Parol to'g'ri, lekin hisob xodim
   emas — bu holatda ham xuddi parol noto'g'ri kabi UMUMIY xabar
   chiqadi va urinish muvaffaqiyatsiz deb yoziladi. Aks holda panel
   "qaysi hisob admin" degan savolga javob beradigan asbobga aylanardi:
   hujumchi oddiy hisoblarni bittalab sinab, adminni topib olardi.

6. `?next=` FAQAT ichki manzil bo'lsa ishlatiladi. Tekshirilmasa panel
   login sahifasi begona saytga olib ketadigan havolaga aylanardi.
"""

from functools import wraps
from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from core import lockout, password_reset

#: Muvaffaqiyatli kirgandan keyin standart manzil
DEFAULT_REDIRECT = 'panel:dashboard'

#: Xodimlik tekshiruvidan o'tmagan urinish uchun ham, parol xato bo'lgan
#: urinish uchun ham AYNAN SHU matn chiqadi (5-qoida).
GENERIC_LOGIN_ERROR = "Login yoki parol noto'g'ri, yoki bu hisob uchun panel yopiq."


def staff_required(view):
    """
    Panel sahifalarini himoyalaydi.

    `@login_required` DAN FARQI: kirgan, lekin huquqsiz foydalanuvchini
    login sahifasiga qaytarmaydi — 403 beradi (2-qoida).
    """

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            login_url = reverse('panel:login')
            return redirect(f"{login_url}?next={request.get_full_path()}")

        if not request.user.is_staff:
            raise PermissionDenied("Bu bo'lim faqat xodimlar uchun.")

        if not request.user.is_active:
            # AMALDA BU YERGA YETIB KELINMAYDI: `ModelBackend.get_user`
            # faolsiz foydalanuvchini qaytarmaydi, demak seans yuqorida
            # allaqachon anonim bo'lib qoladi. Tekshiruv boshqa
            # autentifikatsiya usuli qo'shilgan kunda kerak bo'lib
            # qolishi mumkin — shuning uchun qoldirilgan.
            raise PermissionDenied("Hisob faolsizlantirilgan.")

        return view(request, *args, **kwargs)

    return wrapped


def _safe_next(request) -> str:
    """`?next=` ni tekshiradi. Begona manzil bo'lsa — standart sahifa (6-qoida)."""
    candidate = request.POST.get('next') or request.GET.get('next') or ''
    if candidate and url_has_allowed_host_and_scheme(
        url=candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return reverse(DEFAULT_REDIRECT)


def panel_login(request):
    """Panelga kirish."""
    if request.user.is_authenticated and request.user.is_staff:
        return redirect(_safe_next(request))

    if request.method != 'POST':
        return render(request, 'panel/login.html', {'next': request.GET.get('next', '')})

    username = (request.POST.get('username') or '').strip()
    password = request.POST.get('password') or ''
    ip = lockout.client_ip(request)

    # DARVOZA: parolni tekshirishdan OLDIN. Qulf paytida urinish
    # yozilmaydi ham — aks holda hujumchi urinib turib qulfni cheksiz
    # uzaytirardi va haqiqiy egasi hech qachon kira olmasdi.
    locked, retry_after, _ = lockout.check_locked(username, ip)
    if locked:
        messages.error(request, lockout.lockout_message(retry_after))
        return render(
            request,
            'panel/login.html',
            {'next': request.POST.get('next', ''), 'locked': True},
            status=429,
        )

    user = authenticate(request, username=username, password=password)

    if user is None or not user.is_staff:
        # Ikkala holat ham bir xil qaraladi (5-qoida).
        lockout.record_failure(request, username)

        # Oxirgi urinish chegaraga yetgan bo'lsa darhol aytamiz —
        # xodim nima bo'lganini tushunsin
        locked, retry_after, _ = lockout.check_locked(username, ip)
        if locked:
            messages.error(request, lockout.lockout_message(retry_after))
        else:
            messages.error(request, GENERIC_LOGIN_ERROR)
        return render(
            request, 'panel/login.html', {'next': request.POST.get('next', '')}, status=401
        )

    login(request, user)
    lockout.record_success(request, user)
    return redirect(_safe_next(request))


def panel_logout(request):
    """
    Paneldan chiqish.

    FAQAT POST: GET bilan chiqarish mumkin bo'lsa, begona saytdagi
    <img src="/panel/logout/"> adminni chiqarib yuborardi.
    """
    if request.method == 'POST':
        logout(request)
    return redirect('panel:login')


def panel_forgot_password(request):
    """
    Parolni tiklash — 1-qadam: emailga kod.

    O'quvchinikidan ALOHIDA sahifa, lekin ICHIDA bir xil modul
    (`core.password_reset`) ishlaydi: kod uzunligi, muddati, urinishlar
    soni bir joyda turadi.

    Bu yerda ham hisob xodimmi-yo'qmi TEKSHIRILMAYDI va xabar har doim
    bir xil. Aks holda "bu email admin" degan ma'lumot oshkor bo'lardi.
    """
    if request.method != 'POST':
        return render(request, 'panel/forgot_password.html')

    email = (request.POST.get('email') or '').strip()
    ip = lockout.client_ip(request)

    # Cheklovsiz bu begonaning pochtasiga xat yuborish vositasi bo'lardi
    throttled, retry_after = lockout.check_reset_throttle(ip)
    if throttled:
        messages.error(request, lockout.reset_throttle_message(retry_after))
        return render(request, 'panel/forgot_password.html', status=429)

    lockout.record_reset_request(request, email)
    messages.success(request, password_reset.request_reset(email))
    return redirect(f"{reverse('panel:reset_password')}?email={quote(email.lower())}")


def panel_reset_password(request):
    """Parolni tiklash — 2-qadam: kod + yangi parol."""
    email = (request.POST.get('email') or request.GET.get('email') or '').strip()

    if request.method != 'POST':
        return render(request, 'panel/reset_password.html', {'email': email})

    code = (request.POST.get('code') or '').strip()
    new_password = request.POST.get('new_password') or ''
    confirm = request.POST.get('confirm_password') or ''

    if new_password != confirm:
        messages.error(request, "Parollar bir-biriga mos kelmadi.")
        return render(request, 'panel/reset_password.html', {'email': email})

    try:
        result = password_reset.confirm_reset(email, code, new_password)
    except password_reset.ResetError as exc:
        messages.error(request, str(exc))
        return render(request, 'panel/reset_password.html', {'email': email})

    messages.success(request, result)
    return redirect('panel:login')
