'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Guard } from '@/components/Guard';
import { dashboard, type DashboardData } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';

function Dashboard() {
  const { user, subscription } = useAuth();
  const [data, setData] = useState<DashboardData | null>(null);

  useEffect(() => {
    dashboard.get().then(setData).catch(() => setData(null));
  }, []);

  return (
    <>
      <h1 className="text-3xl font-extrabold mb-2">
        Salom, {user?.full_name || user?.username}
      </h1>
      <p className="text-slate-500 mb-8">{user?.level}-daraja</p>

      {/* Obuna tugayotgan bo'lsa ogohlantiramiz — o'quvchi kirish
          yopilishidan xabardor bo'lsin */}
      {subscription && !subscription.active && (
        <Link
          href="/obuna"
          className="flex items-center gap-4 mb-6 p-4 rounded-2xl bg-amber-500/10 border border-amber-500/30 hover:bg-amber-500/15 transition"
        >
          <span className="min-w-0">
            <span className="block font-bold text-amber-300">
              {subscription.status_label}
            </span>
            <span className="block text-sm text-amber-200/60">
              Barcha darslarni ochish uchun obuna rasmiylashtiring
            </span>
          </span>
          <span className="ml-auto text-amber-400">→</span>
        </Link>
      )}

      {data && (
        <>
          <div className="grid stagger grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            <div className="glass lift rounded-2xl p-5">
              <p className="text-xs uppercase tracking-wider text-slate-500 mb-2">
                Darslar
              </p>
              <p className="text-3xl font-extrabold">{data.lessons.percent}%</p>
              <p className="text-xs text-slate-500 mt-2">
                {data.lessons.completed}/{data.lessons.total}
              </p>
            </div>

            <div className="glass lift rounded-2xl p-5">
              <p className="text-xs uppercase tracking-wider text-slate-500 mb-2">
                Testlar
              </p>
              <p className="text-3xl font-extrabold">{data.quizzes.taken}</p>
              <p className="text-xs text-slate-500 mt-2">
                o&apos;rtacha {data.quizzes.average_score}%
              </p>
            </div>

            <div className="glass lift rounded-2xl p-5">
              <p className="text-xs uppercase tracking-wider text-slate-500 mb-2">
                Sertifikat
              </p>
              <p className="text-3xl font-extrabold text-emerald-400">
                {data.certificates}
              </p>
            </div>

            <div className="glass lift rounded-2xl p-5">
              <p className="text-xs uppercase tracking-wider text-slate-500 mb-2">
                Daraja
              </p>
              <p className="text-3xl font-extrabold text-primary">{data.level}</p>
            </div>
          </div>

          <div className="grid stagger sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { href: '/kurslar', title: 'Kurslar', text: 'Darslarni davom ettiring' },
              { href: '/testlar', title: 'Testlar', text: 'Bilimingizni sinang' },
              { href: '/muharrir', title: 'Kod muharriri', text: 'Amaliy topshiriqlar' },
              { href: '/sertifikatlar', title: 'Sertifikatlar', text: 'Yutuqlaringiz' },
            ].map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="glass lift rounded-2xl p-5 hover:bg-white/5 transition"
              >
                <p className="font-bold mb-1">{item.title}</p>
                <p className="text-sm text-slate-500">{item.text}</p>
              </Link>
            ))}
          </div>
        </>
      )}
    </>
  );
}

export default function DashboardPage() {
  return (
    <Guard>
      <Dashboard />
    </Guard>
  );
}
