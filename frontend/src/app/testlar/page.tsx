'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Guard } from '@/components/Guard';
import { quizzes, type Quiz } from '@/lib/api';

function QuizList() {
  const [items, setItems] = useState<Quiz[] | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    quizzes
      .list()
      .then(setItems)
      .catch(() => setError('Testlarni yuklab bo‘lmadi'));
  }, []);

  if (error) return <p className="text-red-400 py-12 text-center">{error}</p>;
  if (!items) return <p className="text-slate-500 py-12 text-center">Yuklanmoqda...</p>;

  if (items.length === 0) {
    return (
      <>
        <h1 className="text-3xl font-extrabold mb-8 gradient-text">Testlar</h1>
        <p className="text-slate-500 text-center py-12">Hozircha test yo&apos;q.</p>
      </>
    );
  }

  return (
    <>
      <h1 className="text-3xl font-extrabold mb-8">Testlar</h1>

      <div className="space-y-2">
        {items.map((quiz) => (
          <Link
            key={quiz.id}
            href={`/testlar/${quiz.id}`}
            className="flex items-center gap-4 glass rounded-xl p-4 hover:bg-white/5 transition"
          >
            <div className="min-w-0 flex-1">
              <p className="font-semibold truncate">{quiz.title}</p>
              <p className="text-xs text-slate-500 mt-0.5">
                {quiz.category} · {quiz.question_count} savol · {quiz.time_limit} daqiqa
              </p>
            </div>

            <div className="shrink-0 text-right">
              {!quiz.unlocked ? (
                <span className="text-xs text-slate-600">🔒 obuna</span>
              ) : quiz.best_score !== null && quiz.best_score !== undefined ? (
                <span
                  className={`text-sm font-bold ${
                    quiz.best_score >= 80 ? 'text-emerald-400' : 'text-amber-400'
                  }`}
                >
                  {quiz.best_score}%
                </span>
              ) : (
                <span className="text-xs text-slate-500">yechilmagan</span>
              )}
            </div>
          </Link>
        ))}
      </div>
    </>
  );
}

export default function QuizzesPage() {
  return (
    <Guard>
      <QuizList />
    </Guard>
  );
}
