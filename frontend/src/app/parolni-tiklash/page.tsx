'use client';

/**
 * Parolni tiklash — bitta sahifada ikki qadam.
 *
 * NEGA BITTA SAHIFADA: kod emailga keladi va odam uni darhol
 * kiritadi. Ikkinchi sahifaga o'tkazilsa, u yerda emailni QAYTA
 * yozishga to'g'ri kelardi yoki manzilga yozib qo'yish kerak bo'lardi.
 */

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { auth, ApiError } from '@/lib/api';

export default function PasswordResetPage() {
  const router = useRouter();
  const [step, setStep] = useState<'request' | 'confirm'>('request');
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function requestCode(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError('');

    const value = String(new FormData(event.currentTarget).get('email') || '').trim();
    try {
      const result = await auth.requestPasswordReset(value);
      setEmail(value);
      setMessage(result.detail);
      setStep('confirm');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Xatolik yuz berdi');
    } finally {
      setBusy(false);
    }
  }

  async function confirmCode(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError('');

    const form = new FormData(event.currentTarget);
    const password = String(form.get('new_password') || '');
    const repeat = String(form.get('repeat_password') || '');

    if (password !== repeat) {
      setError('Parollar bir-biriga mos kelmadi.');
      setBusy(false);
      return;
    }

    try {
      await auth.confirmPasswordReset(email, String(form.get('code') || ''), password);
      router.push('/login');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Xatolik yuz berdi');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-md mx-auto py-12">
      <h1 className="text-2xl font-extrabold mb-2 text-center">Parolni tiklash</h1>
      <p className="text-sm text-slate-500 text-center mb-8">
        {step === 'request'
          ? 'Emailingizga 6 xonali kod yuboriladi'
          : 'Emailga kelgan kodni kiriting'}
      </p>

      {message && (
        <p className="px-4 py-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-sm mb-5">
          {message}
        </p>
      )}
      {error && (
        <p className="px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 text-sm mb-5">
          {error}
        </p>
      )}

      {step === 'request' ? (
        <>
          <form onSubmit={requestCode} className="glass rounded-2xl p-6 space-y-4">
            <div>
              <label className="block text-sm text-slate-400 mb-1.5">Email</label>
              <input
                name="email"
                type="email"
                className="field"
                required
                autoFocus
                autoComplete="email"
              />
            </div>
            <button className="btn w-full" disabled={busy}>
              {busy ? 'Yuborilmoqda...' : 'Kod yuborish'}
            </button>
          </form>

          {/*
            Bu matn ATAYLAB: tizim email ro'yxatda bor-yo'qligini
            aytmaydi. Buni oldindan tushuntirmasak, kod kelmaganda
            odam emailni noto'g'ri yozdim deb o'ylab, qayta-qayta
            urinardi.
          */}
          <p className="text-xs text-slate-600 mt-5 leading-relaxed">
            Xavfsizlik uchun tizim emailning ro&apos;yxatda bor-yo&apos;qligini
            aytmaydi — javob har doim bir xil. Kod kelmasa spam papkasini
            tekshiring.
          </p>
        </>
      ) : (
        <form onSubmit={confirmCode} className="glass rounded-2xl p-6 space-y-4">
          <div>
            <label className="block text-sm text-slate-400 mb-1.5">Tiklash kodi</label>
            <input
              name="code"
              className="field text-center text-2xl tracking-[.5em] font-bold"
              required
              autoFocus
              inputMode="numeric"
              pattern="[0-9]*"
              maxLength={6}
              placeholder="000000"
              autoComplete="one-time-code"
            />
          </div>
          <div>
            <label className="block text-sm text-slate-400 mb-1.5">Yangi parol</label>
            <input
              name="new_password"
              type="password"
              className="field"
              required
              minLength={8}
              autoComplete="new-password"
            />
          </div>
          <div>
            <label className="block text-sm text-slate-400 mb-1.5">Parolni takrorlang</label>
            <input
              name="repeat_password"
              type="password"
              className="field"
              required
              minLength={8}
              autoComplete="new-password"
            />
          </div>

          <button className="btn w-full" disabled={busy}>
            {busy ? 'Saqlanmoqda...' : 'Parolni yangilash'}
          </button>

          <p className="text-xs text-slate-600 leading-relaxed">
            Kod 15 daqiqa amal qiladi. Noto&apos;g&apos;ri kod bir necha marta
            kiritilsa u bekor qilinadi.
          </p>
        </form>
      )}

      <p className="text-center text-sm text-slate-500 mt-6">
        <Link href="/login" className="hover:text-slate-300">
          ← Kirishga qaytish
        </Link>
      </p>
    </div>
  );
}
