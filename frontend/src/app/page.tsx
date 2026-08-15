'use client';

import Link from 'next/link';
import { useAuth } from '@/lib/auth-context';

export default function Home() {
  const { user, loading } = useAuth();

  return (
    <div className="py-16 text-center">
      <h1 className="text-4xl sm:text-6xl font-black tracking-tight mb-6">
        Dasturlashni <span className="text-primary">noldan</span> o&apos;rganing
      </h1>
      <p className="text-lg text-slate-400 max-w-2xl mx-auto mb-10 leading-relaxed">
        Python, Django, React, JavaScript va sun&apos;iy intellekt bo&apos;yicha video
        hamda yozma darslar. Har bir mavzudan keyin test va sertifikat.
      </p>

      {!loading && (
        <div className="flex flex-wrap gap-3 justify-center">
          {user ? (
            <Link href={user.is_approved ? '/kurslar' : '/kutish'} className="btn">
              {user.is_approved ? 'Darslarga o’tish' : 'Holatni ko’rish'}
            </Link>
          ) : (
            <>
              <Link href="/register" className="btn">
                Ro&apos;yxatdan o&apos;tish
              </Link>
              <Link href="/login" className="px-6 py-3 rounded-xl bg-white/5 font-semibold">
                Kirish
              </Link>
            </>
          )}
        </div>
      )}
    </div>
  );
}
