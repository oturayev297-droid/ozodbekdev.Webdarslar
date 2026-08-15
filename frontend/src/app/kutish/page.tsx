'use client';

/**
 * Ruxsat kutayotgan o'quvchi sahifasi.
 *
 * Bu yerda `Guard` ISHLATILMAYDI — u aynan shu sahifaga yo'naltiradi
 * va o'zini chaqirsa cheksiz aylanish paydo bo'lardi.
 */

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';

export default function PendingPage() {
  const { loading, user, refresh } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (!user) router.replace('/login');
    // Ruxsat berilgan bo'lsa bu yerda turishning ma'nosi yo'q —
    // aks holda odam ruxsat olgandan keyin ham "kutmoqda" degan
    // yozuvni ko'rib turardi.
    else if (user.is_approved) router.replace('/kurslar');
  }, [loading, user, router]);

  if (loading || !user || user.is_approved) return null;

  const rejected = Boolean(user.rejection_reason);

  return (
    <div className="max-w-lg mx-auto py-12">
      <div className="text-center mb-8">
        <h1 className="text-2xl font-extrabold">
          {rejected ? 'Ruxsat berilmadi' : 'Ruxsat kutilmoqda'}
        </h1>
        <p className="text-slate-400 mt-2">
          Salom, {user.full_name || user.username}
        </p>
      </div>

      <div className="glass rounded-2xl p-6">
        {rejected ? (
          <>
            <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/25 mb-5">
              <p className="text-sm font-semibold text-red-300 mb-1">Sabab</p>
              <p className="text-sm text-red-200/80 leading-relaxed">
                {user.rejection_reason}
              </p>
            </div>
            <p className="text-sm text-slate-400 leading-relaxed mb-6">
              Bu xato deb hisoblasangiz biz bilan bog&apos;laning — hisobingiz
              qayta ko&apos;rib chiqiladi.
            </p>
          </>
        ) : (
          <>
            <p className="text-slate-300 leading-relaxed mb-6">
              Hisobingiz yaratildi. Endi administrator uni ko&apos;rib chiqadi va
              ruxsat beradi. Bu odatda uzoq davom etmaydi.
            </p>
            <ol className="space-y-3 text-sm mb-6">
              <li className="text-emerald-400">✓ Ro&apos;yxatdan o&apos;tdingiz</li>
              <li className="text-amber-300 font-semibold">
                → Administrator ruxsat beradi
              </li>
              <li className="text-slate-500">
                Darslar ochiladi — tanishtiruv darslari bepul
              </li>
            </ol>
          </>
        )}

        <button onClick={() => refresh()} className="btn w-full">
          Holatni yangilash
        </button>
      </div>
    </div>
  );
}
