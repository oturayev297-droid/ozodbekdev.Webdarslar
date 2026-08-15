'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import { auth, ApiError } from '@/lib/api';

export default function RegisterPage() {
  const { refresh } = useAuth();
  const router = useRouter();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError('');

    const form = new FormData(event.currentTarget);
    try {
      await auth.register({
        username: String(form.get('username') || ''),
        email: String(form.get('email') || ''),
        password: String(form.get('password') || ''),
        full_name: String(form.get('full_name') || ''),
      });
      await refresh();
      // Yangi hisob HAR DOIM ruxsat kutadi — to'g'ridan-to'g'ri
      // kutish sahifasiga
      router.push('/kutish');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Xatolik yuz berdi');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-md mx-auto py-12">
      <h1 className="text-2xl font-extrabold mb-2 text-center">
        Ro&apos;yxatdan o&apos;tish
      </h1>
      <p className="text-sm text-slate-500 text-center mb-6">
        Hisobingiz administrator tasdiqlagach ochiladi
      </p>

      <form onSubmit={handleSubmit} className="glass rounded-2xl p-6 space-y-4">
        {error && (
          <p className="px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 text-sm">
            {error}
          </p>
        )}

        <div>
          <label className="block text-sm text-slate-400 mb-1.5">F.I.SH.</label>
          <input name="full_name" className="field" autoComplete="name" />
        </div>
        <div>
          <label className="block text-sm text-slate-400 mb-1.5">Login</label>
          <input
            name="username"
            className="field"
            required
            minLength={3}
            autoComplete="username"
          />
        </div>
        <div>
          <label className="block text-sm text-slate-400 mb-1.5">Email</label>
          <input name="email" type="email" className="field" required autoComplete="email" />
          <p className="text-xs text-slate-600 mt-1.5">Parolni tiklash uchun kerak</p>
        </div>
        <div>
          <label className="block text-sm text-slate-400 mb-1.5">Parol</label>
          <input
            name="password"
            type="password"
            className="field"
            required
            minLength={8}
            autoComplete="new-password"
          />
        </div>

        <button className="btn w-full" disabled={busy}>
          {busy ? 'Kutilmoqda...' : 'Ro’yxatdan o’tish'}
        </button>
      </form>

      <p className="text-center text-sm text-slate-500 mt-5">
        Hisobingiz bormi?{' '}
        <Link href="/login" className="text-primary hover:underline">
          Kiring
        </Link>
      </p>
    </div>
  );
}
