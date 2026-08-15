'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';

export function Nav() {
  const { user, subscription, loading, logout } = useAuth();
  const router = useRouter();

  async function handleLogout() {
    await logout();
    router.push('/login');
  }

  return (
    <nav className="glass border-b border-white/5 sticky top-0 z-50">
      <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between gap-4">
        <Link href="/" className="font-extrabold text-lg tracking-tight">
          OZODBEK<span className="text-primary">.WEB</span>
        </Link>

        {/*
          Yuklanayotganda hech narsa ko'rsatmaymiz. Aks holda "Kirish"
          tugmasi bir lahzaga chaqnab, keyin foydalanuvchi nomiga
          almashardi — sahifa buzilgandek ko'rinardi.
        */}
        {loading ? null : user ? (
          <div className="flex items-center gap-4 text-sm">
            {user.is_approved && (
              <>
                <Link href="/kurslar" className="text-slate-300 hover:text-white">
                  Kurslar
                </Link>
                <Link href="/testlar" className="text-slate-300 hover:text-white">
                  Testlar
                </Link>
                <Link href="/obuna" className="text-slate-300 hover:text-white">
                  Obuna
                  {subscription && !subscription.active && (
                    <span className="ml-1.5 w-2 h-2 inline-block rounded-full bg-amber-400" />
                  )}
                </Link>
              </>
            )}
            <span className="text-slate-500">{user.username}</span>
            <button onClick={handleLogout} className="text-slate-400 hover:text-red-400">
              Chiqish
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-3 text-sm">
            <Link href="/login" className="text-slate-300 hover:text-white">
              Kirish
            </Link>
            <Link href="/register" className="btn text-sm py-2">
              Ro&apos;yxatdan o&apos;tish
            </Link>
          </div>
        )}
      </div>
    </nav>
  );
}
