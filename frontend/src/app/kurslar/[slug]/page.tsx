'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { Guard } from '@/components/Guard';
import { courses, type Course, type Module } from '@/lib/api';

function CourseDetail({ slug }: { slug: string }) {
  const [data, setData] = useState<{ category: Course; modules: Module[] } | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    courses
      .detail(slug)
      .then(setData)
      .catch(() => setError('Kursni yuklab bo‘lmadi'));
  }, [slug]);

  if (error) return <p className="text-red-400 py-12 text-center">{error}</p>;
  if (!data) return <p className="text-slate-500 py-12 text-center">Yuklanmoqda...</p>;

  return (
    <>
      <Link href="/kurslar" className="text-sm text-slate-500 hover:text-slate-300">
        ← Kurslar
      </Link>

      <h1 className="text-3xl font-extrabold mt-4 mb-2">{data.category.name}</h1>
      <p className="text-slate-400 mb-8 max-w-2xl leading-relaxed">
        {data.category.description}
      </p>

      {data.modules.map((module) => (
        <section key={module.id} className="mb-8">
          <h2 className="font-bold text-slate-300 mb-3 pb-2 border-b border-white/5">
            <span className="text-slate-600 mr-2">{module.order}.</span>
            {module.title}
          </h2>

          <div className="space-y-1.5">
            {module.lessons.map((lesson, index) => (
              <Link
                key={lesson.id}
                href={`/darslar/${lesson.id}`}
                className="flex items-center gap-3 px-4 py-3 rounded-xl glass hover:bg-white/5 transition group"
              >
                <span
                  className={`w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold shrink-0 ${
                    !lesson.unlocked
                      ? 'bg-slate-800 text-slate-600'
                      : lesson.completed
                        ? 'bg-emerald-500 text-slate-950'
                        : 'bg-slate-800 text-slate-400'
                  }`}
                >
                  {!lesson.unlocked ? '🔒' : lesson.completed ? '✓' : index + 1}
                </span>

                <span className="flex-1 min-w-0 truncate group-hover:text-primary transition">
                  {lesson.title}
                </span>

                <span className="flex items-center gap-2 shrink-0 text-xs">
                  {lesson.is_free && (
                    <span className="px-2 py-0.5 rounded bg-secondary/15 text-secondary font-bold uppercase tracking-wider">
                      Bepul
                    </span>
                  )}
                  {lesson.has_video && <span className="text-slate-600">video</span>}
                  {lesson.has_text && <span className="text-slate-600">matn</span>}
                </span>
              </Link>
            ))}
          </div>
        </section>
      ))}
    </>
  );
}

export default function CourseDetailPage() {
  const params = useParams<{ slug: string }>();
  return (
    <Guard>
      <CourseDetail slug={params.slug} />
    </Guard>
  );
}
