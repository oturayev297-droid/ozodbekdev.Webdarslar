"""
To'lov tizimlari (Payme, Click).

QO'LDA TASDIQLASH OQIMI SAQLANADI. Avtomatik to'lov unga QO'SHIMCHA,
o'rnini bosuvchi emas: kalitlar sozlanmagan bo'lsa yoki tizim ishlamasa
o'quvchi baribir kartaga o'tkazib, chek yuborib to'lay oladi.

IKKALASI HAM BIR JOYGA KELADI: to'lov tasdiqlangach
`payment_requests.confirm_request` chaqiriladi, ya'ni obunani uzaytirish
yo'li bitta — `services.extend_subscription`. Shu sababli
idempotentlik, narxni muzlatish va davr jurnali qoidalari avtomatik
to'lovda ham xuddi qo'lda tasdiqlangandagidek ishlaydi.
"""
