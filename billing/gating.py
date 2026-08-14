"""
Kontent darvozasi
=================

crmauto da darvoza YOZISHni bloklaydi, o'qish ochiq qoladi — u yerda
qimmatli narsa foydalanuvchining o'z ma'lumoti edi. Bu yerda esa aksincha:
qimmatli narsa aynan KONTENT, ya'ni o'qish. Shuning uchun qoida
o'zgartirilgan, lekin naqsh o'sha: qaror bitta joyda chiqariladi,
ko'rinishlar ichida `if` yozilmaydi.

QOIDA:
  * `Lesson.is_free = True`  -> tizimga kirgan har kimga ochiq
  * `Lesson.is_free = False` -> faol obuna talab qiladi
  * Test darsdan huquqni MEROS OLADI (o'z bayrog'i yo'q — ikkita manba
    bo'lsa ular ertami-kechmi bir-biriga to'g'ri kelmay qolardi)
  * Admin va xodimlar hech qachon cheklanmaydi (`get_state` da)

FAIL CLOSED: yangi dars `is_free=False` bilan tug'iladi. Bayroqni
qo'yishni unutish kontentni bepul qilib qo'ymaydi.
"""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render

from .services import get_state


def can_access_lesson(user, lesson) -> bool:
    """Foydalanuvchi shu darsni ko'ra oladimi."""
    if lesson.is_free:
        return True
    return get_state(user).active


def can_access_quiz(user, quiz) -> bool:
    """Test darsdan huquqni meros oladi."""
    return can_access_lesson(user, quiz.lesson)


def _is_ajax(request) -> bool:
    return (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or request.content_type == 'application/json'
        or request.headers.get('Accept', '').startswith('application/json')
    )


def paywall(request, message=None):
    """
    Obuna talab qilinganda qaytariladigan javob.

    JSON so'rovga 402 Payment Required, oddiy so'rovga tarif sahifasi.
    """
    message = message or (
        "Bu dars obuna talab qiladi. Bepul darslar hamma uchun ochiq, "
        "qolganlari uchun obuna rasmiylashtiring."
    )
    if _is_ajax(request):
        return JsonResponse(
            {'success': False, 'error': message, 'code': 'SUBSCRIPTION_REQUIRED'},
            status=402,
        )
    return render(
        request,
        'billing/paywall.html',
        {'message': message, 'state': get_state(request.user)},
        status=402,
    )


def subscription_required(view):
    """
    Butun sahifa obuna talab qilganda ishlatiladi.

    Dars darajasidagi cheklov uchun `can_access_lesson` ishlatiladi —
    u yerda bepul darslar o'tishi kerak.
    """

    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not get_state(request.user).active:
            return paywall(request)
        return view(request, *args, **kwargs)

    return wrapper


def subscription_context(request) -> dict:
    """Shablonlarga obuna holatini beradigan kontekst protsessori."""
    if not request.user.is_authenticated:
        return {'subscription_state': None}
    return {'subscription_state': get_state(request.user)}
