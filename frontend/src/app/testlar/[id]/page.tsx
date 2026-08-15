'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { Guard } from '@/components/Guard';
import { quizzes, ApiError, type QuizDetail, type QuizOutcome } from '@/lib/api';

function Quiz({ id }: { id: number }) {
  const [quiz, setQuiz] = useState<QuizDetail | null>(null);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [outcome, setOutcome] = useState<QuizOutcome | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    quizzes
      .detail(id)
      .then(setQuiz)
      .catch((err) => {
        if (err instanceof ApiError && err.needsSubscription) {
          setError('Bu test obuna bilan ochiladi.');
        } else {
          setError('Testni yuklab bo‘lmadi');
        }
      });
  }, [id]);

  async function submit() {
    if (!quiz) return;
    setBusy(true);
    try {
      // FAQAT tanlov id lari yuboriladi. Ball serverda hisoblanadi —
      // bu yerda hech qanday hisob-kitob yo'q va bo'lmasligi kerak.
      setOutcome(await quizzes.submit(id, answers));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Xatolik yuz berdi');
    } finally {
      setBusy(false);
    }
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-slate-400 mb-6">{error}</p>
        <Link href="/obuna" className="btn inline-block">
          Obuna rasmiylashtirish
        </Link>
      </div>
    );
  }
  if (!quiz) return <p className="text-slate-500 py-12 text-center">Yuklanmoqda...</p>;

  if (outcome) {
    const passed = outcome.score >= 80;
    return (
      <div className="max-w-lg mx-auto py-12 text-center">
        <p className="text-sm text-slate-500 uppercase tracking-widest mb-3">Natija</p>
        <p className={`text-6xl font-black mb-4 ${passed ? 'text-emerald-400' : 'text-amber-400'}`}>
          {outcome.score}%
        </p>
        <p className="text-slate-400 mb-8">
          {outcome.total} savoldan {outcome.correct} tasi to&apos;g&apos;ri
          {outcome.attempts > 1 && ` · ${outcome.attempts}-urinish`}
        </p>

        {outcome.leveled_up && (
          <p className="px-4 py-3 rounded-xl bg-primary/10 border border-primary/30 text-primary mb-4">
            Yangi daraja: {outcome.new_level}
          </p>
        )}

        {outcome.certificate && (
          <a
            href={outcome.certificate.pdf_url}
            className="btn inline-block mb-4"
            target="_blank"
            rel="noopener noreferrer"
          >
            Sertifikatni yuklab olish
          </a>
        )}

        <div className="flex gap-3 justify-center mt-6">
          <button
            onClick={() => {
              setOutcome(null);
              setAnswers({});
            }}
            className="px-6 py-3 rounded-xl bg-white/5 font-semibold"
          >
            Qayta yechish
          </button>
          <Link href="/testlar" className="px-6 py-3 rounded-xl bg-white/5 font-semibold">
            Testlar
          </Link>
        </div>
      </div>
    );
  }

  const answered = Object.keys(answers).length;

  return (
    <div className="max-w-2xl mx-auto">
      <Link href="/testlar" className="text-sm text-slate-500 hover:text-slate-300">
        ← Testlar
      </Link>

      <h1 className="text-2xl font-extrabold mt-4 mb-1">{quiz.title}</h1>
      <p className="text-sm text-slate-500 mb-8">
        {quiz.question_count} savol · {quiz.time_limit} daqiqa
      </p>

      <div className="space-y-5">
        {quiz.questions.map((question, index) => (
          <div key={question.id} className="glass rounded-2xl p-5">
            <p className="font-semibold mb-4">
              <span className="text-slate-600 mr-2">{index + 1}.</span>
              {question.text}
            </p>

            <div className="space-y-2">
              {question.choices.map((choice) => (
                <label
                  key={choice.id}
                  className={`flex items-center gap-3 px-4 py-3 rounded-xl border cursor-pointer transition ${
                    answers[question.id] === choice.id
                      ? 'bg-primary/10 border-primary/40'
                      : 'bg-slate-900/50 border-white/5 hover:border-white/15'
                  }`}
                >
                  <input
                    type="radio"
                    name={`q${question.id}`}
                    checked={answers[question.id] === choice.id}
                    onChange={() =>
                      setAnswers((prev) => ({ ...prev, [question.id]: choice.id }))
                    }
                    className="w-4 h-4"
                  />
                  <span className="text-sm">{choice.text}</span>
                </label>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-8 flex items-center gap-4">
        <button onClick={submit} disabled={busy || answered === 0} className="btn">
          {busy ? 'Tekshirilmoqda...' : 'Topshirish'}
        </button>
        <span className="text-sm text-slate-500">
          {answered}/{quiz.questions.length} belgilandi
        </span>
      </div>
    </div>
  );
}

export default function QuizPage() {
  const params = useParams<{ id: string }>();
  return (
    <Guard>
      <Quiz id={Number(params.id)} />
    </Guard>
  );
}
