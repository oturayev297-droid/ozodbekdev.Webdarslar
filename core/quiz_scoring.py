"""
Test ballini hisoblash
======================

NEGA ALOHIDA MODUL: bu mantiqni IKKI joy chaqiradi — shablonli sahifa
(`core.views.submit_quiz`) va API (`api.views.QuizSubmitView`). Nusxa
ko'chirilsa, biri o'zgarganda ikkinchisi eskirib qolardi va bir xil
test ikki joyda ikki xil ball berardi.

BUZILMAYDIGAN QOIDALAR:

1. BALL FAQAT SHU YERDA, SERVERDA hisoblanadi. Klientdan kelgan har
   qanday "score" e'tiborsiz qoldiriladi.
2. To'g'ri javoblar klientga HECH QACHON yuborilmaydi — na HTML da,
   na API javobida.
3. Eng yaxshi natija saqlanadi, urinishlar soni oshib boradi.
4. Sertifikat tranzaksiyadan TASHQARIDA beriladi: sertifikat
   berilmasa ham o'quvchining natijasi yo'qolmasligi kerak.
"""

import logging

from django.db import transaction

from . import certificates
from .models import Choice, Profile, QuizResult

logger = logging.getLogger(__name__)

#: Level hisoblash chegarasi: shu balldan yuqori natija "o'tgan" deb
#: hisoblanadi. Sertifikat chegarasi BOSHQA (`certificates.PASS_SCORE`).
LEVEL_PASS_SCORE = 50


class ScoringError(Exception):
    """Foydalanuvchiga ko'rsatiladigan xato."""


def score_quiz(user, quiz, answers) -> dict:
    """
    Testni tekshiradi, natijani saqlaydi va sertifikat beradi.

    `answers` — `{savol_id: tanlov_id}`. Kalitlar satr ham, son ham
    bo'lishi mumkin: JSON dan kelganda ular satr bo'ladi, formadan
    kelganda son. Ikkalasi ham qabul qilinadi.

    Qaytaradi: ball, to'g'ri javoblar soni, yangi level va sertifikat.
    """
    question_ids = list(quiz.questions.values_list('id', flat=True))
    total_questions = len(question_ids)

    if total_questions == 0:
        raise ScoringError("Testda savol yo'q")

    # FAQAT SHU TESTGA tegishli to'g'ri variantlar. Butun bazadan
    # olinsa, boshqa testning tanlov id si ham "to'g'ri" bo'lib
    # hisoblanardi.
    correct_choice_ids = set(
        Choice.objects.filter(question__quiz=quiz, is_correct=True).values_list('id', flat=True)
    )

    correct_count = 0
    for qid in question_ids:
        chosen = answers.get(str(qid), answers.get(qid))
        if chosen is None:
            continue
        try:
            chosen = int(chosen)
        except (TypeError, ValueError):
            continue
        if chosen in correct_choice_ids:
            correct_count += 1

    score_percentage = round((correct_count / total_questions) * 100)

    with transaction.atomic():
        result = QuizResult.objects.select_for_update().filter(user=user, quiz=quiz).first()

        if result is None:
            result = QuizResult.objects.create(
                user=user,
                quiz=quiz,
                score_percentage=score_percentage,
                correct_count=correct_count,
                total_questions=total_questions,
                attempts=1,
            )
        else:
            result.attempts += 1
            # ENG YAXSHI natija saqlanadi — qayta topshirish
            # o'quvchining oldingi yutug'ini yo'qotmasligi kerak
            if score_percentage > result.score_percentage:
                result.score_percentage = score_percentage
                result.correct_count = correct_count
                result.total_questions = total_questions
            result.save()

        profile, _ = Profile.objects.get_or_create(user=user)
        old_level = profile.level
        passed_exams = QuizResult.objects.filter(
            user=user, score_percentage__gte=LEVEL_PASS_SCORE
        ).count()
        new_level = 1 + passed_exams

        if new_level != old_level:
            profile.level = new_level
            profile.save(update_fields=['level'])

    logger.info(
        "Quiz submit: user=%s quiz=%s score=%s%%", user.username, quiz.id, score_percentage
    )

    # TRANZAKSIYADAN TASHQARIDA: sertifikat berishda xato chiqsa ham
    # o'quvchining natijasi bazada qolishi kerak.
    certificate = certificates.issue_for_result(result)

    return {
        'score': score_percentage,
        'correct': correct_count,
        'total': total_questions,
        'attempts': result.attempts,
        'new_level': new_level,
        'leveled_up': new_level > old_level,
        'certificate': certificate,
    }
