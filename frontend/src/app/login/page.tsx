'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import { ApiError } from '@/lib/api';

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError('');

    const form = new FormData(event.currentTarget);
    try {
      const me = await login(
        String(form.get('username') || ''),
        String(form.get('password') || ''),
      );
      // Ruxsatsiz odamni DARHOL kutish sahifasiga yuboramiz —
      // kurslarga borsa u yerda baribir qaytarilardi va ikki marta
      // sahifa almashishi ko'rinardi.
      router.push(me.user.is_approved ? '/kurslar' : '/kutish');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Xatolik yuz berdi');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-md mx-auto py-12">
      <h1 className="text-2xl font-extrabold mb-6 text-center">Tizimga kirish</h1>

      <form onSubmit={handleSubmit} className="glass rounded-2xl p-6 space-y-4">
        {error && (
          <p className="px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 text-sm">
            {error}
          </p>
        )}

        <div>
          <label className="block text-sm text-slate-400 mb-1.5">Login</label>
          <input name="username" className="field" required autoFocus autoComplete="username" />
        </div>
        <div>
          <label className="block text-sm text-slate-400 mb-1.5">Parol</label>
          <input
            name="password"
            type="password"
            className="field"
            required
            autoComplete="current-password"
          />
        </div>

        <button className="btn w-full" disabled={busy}>
          {busy ? 'Kutilmoqda...' : 'Kirish'}
        </button>
      </form>

      <p className="text-center text-sm text-slate-500 mt-5">
        <Link href="/parolni-tiklash" className="text-primary hover:underline">
          Parolni unutdingizmi?
        </Link>
      </p>

      <p className="text-center text-sm text-slate-500 mt-3">
        Hisobingiz yo&apos;qmi?{' '}
        <Link href="/register" className="text-primary hover:underline">
          Ro&apos;yxatdan o&apos;ting
        </Link>
      </p>
    </div>
  );
}
