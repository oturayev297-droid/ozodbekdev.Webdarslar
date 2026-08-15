'use client';

/**
 * Ota-ona paneli.
 *
 * `Guard` ISHLATILMAYDI: u `is_approved` talab qiladi, ota-ona esa
 * o'quvchi emas — unga dars ruxsati kerak emas. Uning huquqi
 * `ParentLink` bilan belgilanadi va u SERVERDA har so'rovda
 * tekshiriladi.
 */

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { parent, type Child, type ChildReport } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';

function Bar({ day, peak }: { day: ChildReport['study']['series'][0]; peak: number }) {
  const height = peak ? Math.round((day.seconds / peak) * 100) : 0;

  return (
    <div className="flex-1 flex flex-col items-center gap-2 group min-w-0">
      <span className="text-[10px] text-slate-400 opacity-0 group-hover:opacity-100 transition whitespace-nowrap">
        {day.minutes} daq
      </span>
      <div className="w-full bg-slate-800/50 rounded-t relative flex-1">
        <div
          className="absolute bottom-0 w-full rounded-t bg-gradient-to-t from-primary to-secondary"
          style={{ height: `${height}%` }}
        />
      </div>
      <span className="text-[9px] text-slate-500 whitespace-nowrap">{day.label}</span>
    </div>
  );
}

function Report({ studentId }: { studentId: number }) {
  const [data, setData] = useState<ChildReport | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    setData(null);
    setError('');
    parent
      .report(studentId)
      .then(setData)
      .catch(() => setError('Hisobotni yuklab bo‘lmadi'));
  }, [studentId]);

  if (error) return <p className="text-red-400 py-12 text-center">{error}</p>;
  if (!data) return <p className="text-slate-500 py-12 text-center">Yuklanmoqda...</p>;

  const peak = Math.max(...data.study.series.map((d) => d.seconds), 1);
  const { summary } = data.study;

  return (
    <>
      {/* Asosiy raqamlar */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div className="glass rounded-2xl p-5">
          <p className="text-xs uppercase tracking-wider text-slate-500 mb-2">Bugun</p>
          <p className="text-3xl font-extrabold">{summary.today_minutes}</p>
          <p className="text-xs text-slate-500 mt-2">daqiqa</p>
        </div>
        <div className="glass rounded-2xl p-5">
          <p className="text-xs uppercase tracking-wider text-slate-500 mb-2">30 kun</p>
          <p className="text-3xl font-extrabold text-primary">{summary.total_hours}</p>
          <p className="text-xs text-slate-500 mt-2">soat</p>
        </div>
        <div className="glass rounded-2xl p-5">
          <p className="text-xs uppercase tracking-wider text-slate-500 mb-2">Faol kun</p>
          <p className="text-3xl font-extrabold">{summary.active_days}</p>
          <p className="text-xs text-slate-500 mt-2">30 kundan</p>
        </div>
        <div className="glass rounded-2xl p-5">
          <p className="text-xs uppercase tracking-wider text-slate-500 mb-2">
            Kunlik o&apos;rtacha
          </p>
          <p className="text-3xl font-extrabold text-secondary">{summary.average_minutes}</p>
          {/*
            Bu izoh muhim: o'rtacha FAQAT faol kunlar bo'yicha. Nol
            kunlarni qo'shsak, bir kun 3 soat o'qigan bola "kuniga
            6 daqiqa" bo'lib ko'rinardi va bu chalg'itardi.
          */}
          <p className="text-xs text-slate-500 mt-2">faol kunlarda, daqiqa</p>
        </div>
      </div>

      {/* Kunlik grafik */}
      <div className="glass rounded-2xl p-6 mb-6">
        <h2 className="font-bold mb-1">Oxirgi 14 kun</h2>
        <p className="text-xs text-slate-500 mb-6">
          Har kuni sahifada faol o&apos;tkazilgan vaqt
        </p>

        <div className="flex items-end gap-1.5 h-40">
          {data.study.series.map((day) => (
            <Bar key={day.date} day={day} peak={peak} />
          ))}
        </div>
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        {/* O'zlashtirish */}
        <div className="glass rounded-2xl p-6">
          <h2 className="font-bold mb-5">O&apos;zlashtirish</h2>

          <div className="flex items-center justify-between text-sm mb-2">
            <span className="text-slate-400">Darslar</span>
            <span className="font-bold">
              {data.lessons.completed}/{data.lessons.total}
            </span>
          </div>
          <div className="h-2 rounded-full bg-white/5 overflow-hidden mb-6">
            <div
              className="h-full rounded-full bg-gradient-to-r from-primary to-secondary"
              style={{ width: `${data.lessons.percent}%` }}
            />
          </div>

          <dl className="space-y-3 text-sm">
            <div className="flex justify-between">
              <dt className="text-slate-400">Topshirilgan testlar</dt>
              <dd className="font-bold">{data.quizzes.taken}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-400">O&apos;rtacha ball</dt>
              <dd
                className={`font-bold ${
                  data.quizzes.average_score >= 80 ? 'text-emerald-400' : 'text-amber-400'
                }`}
              >
                {data.quizzes.average_score}%
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-400">Sertifikatlar</dt>
              <dd className="font-bold text-emerald-400">{data.certificates.length}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-400">Daraja</dt>
              <dd className="font-bold">{data.student.level}</dd>
            </div>
            <div className="flex justify-between pt-3 border-t border-white/5">
              <dt className="text-slate-400">Obuna</dt>
              <dd className={data.subscription.active ? 'text-emerald-400' : 'text-amber-400'}>
                {data.subscription.status_label}
              </dd>
            </div>
          </dl>
        </div>

        {/* Test natijalari */}
        <div className="glass rounded-2xl p-6">
          <h2 className="font-bold mb-5">Oxirgi test natijalari</h2>

          {data.quizzes.recent.length === 0 ? (
            <p className="text-sm text-slate-500 py-6 text-center">
              Hozircha test topshirilmagan.
            </p>
          ) : (
            <div className="space-y-3">
              {data.quizzes.recent.slice(0, 8).map((result, index) => (
                <div key={index} className="flex items-center gap-3 text-sm">
                  <div className="min-w-0 flex-1">
                    <p className="truncate">{result.quiz}</p>
                    <p className="text-xs text-slate-500">
                      {result.category} · {result.correct}/{result.total} to&apos;g&apos;ri
                      {result.attempts > 1 && ` · ${result.attempts} urinish`}
                    </p>
                  </div>
                  <span
                    className={`font-bold shrink-0 ${
                      result.score >= 80 ? 'text-emerald-400' : 'text-amber-400'
                    }`}
                  >
                    {result.score}%
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

export default function ParentPage() {
  const { loading, user } = useAuth();
  const router = useRouter();
  const [children, setChildren] = useState<Child[] | null>(null);
  const [selected, setSelected] = useState<number | null>(null);

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace('/login');
      return;
    }
    parent
      .children()
      .then((items) => {
        setChildren(items);
        if (items.length) setSelected(items[0].student_id);
      })
      .catch(() => setChildren([]));
  }, [loading, user, router]);

  if (loading || !children) {
    return <p className="text-slate-500 py-12 text-center">Yuklanmoqda...</p>;
  }

  if (children.length === 0) {
    return (
      <div className="max-w-lg mx-auto py-12 text-center">
        <h1 className="text-2xl font-extrabold mb-3">Farzandlarim</h1>
        <div className="glass rounded-2xl p-8">
          <p className="text-slate-400 mb-3">
            Sizga hali biror o&apos;quvchi biriktirilmagan.
          </p>
          <p className="text-sm text-slate-600 leading-relaxed">
            Farzandingizning hisobotini ko&apos;rish uchun administrator sizni
            unga bog&apos;lashi kerak. Biz bilan bog&apos;laning.
          </p>
        </div>
      </div>
    );
  }

  const child = children.find((c) => c.student_id === selected);

  return (
    <>
      <h1 className="text-3xl font-extrabold mb-2">Farzandlarim</h1>
      <p className="text-slate-500 mb-8">
        {child?.full_name}
        {child?.relation && ` · ${child.relation}`}
      </p>

      {/* Bir necha farzand bo'lsa tanlash */}
      {children.length > 1 && (
        <div className="flex flex-wrap gap-2 mb-6">
          {children.map((item) => (
            <button
              key={item.student_id}
              onClick={() => setSelected(item.student_id)}
              className={`px-4 py-2 rounded-xl text-sm transition ${
                selected === item.student_id
                  ? 'bg-primary text-slate-950 font-bold'
                  : 'glass text-slate-400 hover:text-slate-100'
              }`}
            >
              {item.full_name}
            </button>
          ))}
        </div>
      )}

      {selected && <Report studentId={selected} />}
    </>
  );
}
