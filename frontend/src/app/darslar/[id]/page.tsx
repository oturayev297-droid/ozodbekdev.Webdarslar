'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { Guard } from '@/components/Guard';
import { MentorChat } from '@/components/MentorChat';
import { lessons, ApiError, type LessonDetail } from '@/lib/api';

function Lesson({ id }: { id: number }) {
  const [lesson, setLesson] = useState<LessonDetail | null>(null);
  const [locked, setLocked] = useState(false);
  const [error, setError] = useState('');
  const [completing, setCompleting] = useState(false);

  useEffect(() => {
    lessons
      .detail(id)
      .then((data) => {
        setLesson(data);
        setLocked(false);
      })
      .catch((err) => {
        if (err instanceof ApiError && err.needsSubscription) {
          // 402 javobida SARLAVHA bor, mazmun yo'q — shuni
          // ko'rsatamiz, o'quvchi nima sotib olayotganini bilsin
          setLesson(err.data);
          setLocked(true);
        } else {
          setError('Darsni yuklab bo‘lmadi');
        }
      });
  }, [id]);

  async function markComplete() {
    setCompleting(true);
    try {
      await lessons.complete(id);
      setLesson((prev) => (prev ? { ...prev, completed: true } : prev));
    } catch {
      // Jimgina o'tkazamiz: tugatishni belgilay olmaslik darsni
      // o'qishga xalaqit bermasligi kerak
    } finally {
      setCompleting(false);
    }
  }

  if (error) return <p className="text-red-400 py-12 text-center">{error}</p>;
  if (!lesson) return <p className="text-slate-500 py-12 text-center">Yuklanmoqda...</p>;

  return (
    <article className="max-w-3xl mx-auto">
      <Link
        href={`/kurslar/${lesson.category_slug}`}
        className="text-sm text-slate-500 hover:text-slate-300"
      >
        ← {lesson.category}
      </Link>

      <h1 className="text-3xl sm:text-4xl font-black tracking-tight mt-4 mb-8">
        {lesson.title}
      </h1>

      {locked ? (
        <div className="glass lift rounded-2xl p-8 text-center">
          <p className="text-lg font-bold mb-2">Bu dars obuna bilan ochiladi</p>
          <p className="text-sm text-slate-500 mb-6 max-w-sm mx-auto leading-relaxed">
            Tanishtiruv darslari sizga ochiq. Qolgan darslar, videolar va testlar
            uchun obuna kerak.
          </p>
          <Link href="/obuna" className="btn inline-block">
            Obuna rasmiylashtirish
          </Link>
        </div>
      ) : (
        <>
          {lesson.video_url && (
            <video controls className="w-full rounded-2xl mb-8 bg-black" preload="metadata">
              <source src={lesson.video_url} type="video/mp4" />
            </video>
          )}

          {lesson.theory_html && (
            <div className="glass lift rounded-2xl p-6 sm:p-8 mb-8">
              {/*
                HTML SERVERDA qurilgan (`core/richtext.py`): matn to'liq
                ekranlangan va faqat ruxsat etilgan teglar qo'yilgan.
                Shu sabab bu yerda xavfsiz. Boshqa manbadan kelgan HTML
                bu yerga TUSHMASLIGI kerak.
              */}
              <div
                className="lesson-prose"
                dangerouslySetInnerHTML={{ __html: lesson.theory_html }}
              />

              {lesson.images?.map((image) => (
                <figure key={image.id} className="my-8">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={image.url}
                    alt={image.alt}
                    loading="lazy"
                    className="w-full rounded-2xl border border-white/10 bg-slate-950"
                  />
                  {image.caption && (
                    <figcaption className="mt-3 text-center text-sm text-slate-500">
                      {image.caption}
                    </figcaption>
                  )}
                </figure>
              ))}
            </div>
          )}

          {lesson.practice_code && (
            <pre className="glass lift rounded-2xl p-6 mb-8 overflow-x-auto text-sm">
              <code>{lesson.practice_code}</code>
            </pre>
          )}

          <div className="flex flex-wrap gap-3">
            <button
              onClick={markComplete}
              disabled={completing || lesson.completed}
              className={`btn ${lesson.completed ? 'bg-emerald-500' : ''}`}
            >
              {lesson.completed ? '✓ Tugatilgan' : completing ? 'Saqlanmoqda...' : 'Darsni tugatdim'}
            </button>

            {lesson.quiz_id && (
              <Link
                href={`/testlar/${lesson.quiz_id}`}
                className="px-6 py-3 rounded-xl bg-white/5 font-semibold hover:bg-white/10 transition"
              >
                Testni yechish
              </Link>
            )}
          </div>
        </>
      )}
    </article>
  );
}

export default function LessonPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  return (
    <Guard>
      <Lesson id={id} />
      {/* Mentor dars kontekstini oladi — "bu yerda nima deyilgan?"
          degan savolga model qaysi dars haqida gapirayotganini biladi.
          Qulflangan dars konteksti SERVERDA rad etiladi. */}
      <MentorChat lessonId={id} />
    </Guard>
  );
}
