'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Guard } from '@/components/Guard';
import { courses, type Course } from '@/lib/api';

function CourseGrid() {
  const [items, setItems] = useState<Course[] | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    courses
      .list()
      .then(setItems)
      .catch(() => setError('Kurslarni yuklab bo‘lmadi'));
  }, []);

  if (error) return <p className="text-red-400 py-12 text-center">{error}</p>;
  if (!items) return <p className="text-slate-500 py-12 text-center">Yuklanmoqda...</p>;

  return (
    <>
      <h1 className="text-3xl font-extrabold mb-8">Kurslar</h1>

      <div className="grid sm:grid-cols-2 gap-5">
        {items.map((course) => {
          const percent = course.total_lessons
            ? Math.round((course.completed_lessons / course.total_lessons) * 100)
            : 0;

          return (
            <Link
              key={course.slug}
              href={`/kurslar/${course.slug}`}
              className="glass rounded-2xl p-6 hover:bg-white/5 transition"
            >
              <h2 className="text-xl font-extrabold mb-2">{course.name}</h2>
              <p className="text-sm text-slate-400 mb-5 leading-relaxed line-clamp-3">
                {course.description}
              </p>

              <div className="flex items-center justify-between text-xs mb-2">
                <span className="text-slate-500 uppercase tracking-wider font-bold">
                  Jarayon
                </span>
                <span className="text-primary font-bold">{percent}%</span>
              </div>
              <div className="h-2 rounded-full bg-white/5 overflow-hidden">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-primary to-secondary transition-all"
                  style={{ width: `${percent}%` }}
                />
              </div>

              <div className="flex items-center gap-3 mt-4 text-xs text-slate-500">
                <span className="font-bold">
                  {course.completed_lessons}/{course.total_lessons} dars
                </span>
                {course.free_lessons > 0 && (
                  <span className="ml-auto px-2 py-1 rounded bg-emerald-500/10 text-emerald-400 font-bold uppercase tracking-wider">
                    {course.free_lessons} ta bepul
                  </span>
                )}
              </div>
            </Link>
          );
        })}
      </div>
    </>
  );
}

export default function CoursesPage() {
  return (
    <Guard>
      <CourseGrid />
    </Guard>
  );
}
