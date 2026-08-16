'use client';

/**
 * Sertifikatni tekshirish — OCHIQ sahifa.
 *
 * `Guard` ATAYLAB ISHLATILMAYDI: bu sahifani ish beruvchi ochadi va
 * uning tizimda hisobi yo'q. Kirish talab qilinsa, tekshirish
 * imkoniyati amalda yo'qolardi.
 */

import { useState } from 'react';
import { certificates } from '@/lib/api';

interface VerifyResult {
  found: boolean;
  valid?: boolean;
  holder?: string;
  quiz_title?: string;
  category?: string;
  score?: number;
  issued_at?: string;
  revoke_reason?: string;
  detail?: string;
}

export default function VerifyPage() {
  const [result, setResult] = useState<VerifyResult | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setResult(null);

    const form = new FormData(event.currentTarget);
    try {
      setResult(await certificates.verify(String(form.get('code') || '')));
    } catch {
      setResult({ found: false, detail: 'Tekshirib bo‘lmadi' });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-lg mx-auto py-12">
      <h1 className="text-2xl font-extrabold mb-2 text-center">
        Sertifikatni tekshirish
      </h1>
      <p className="text-sm text-slate-500 text-center mb-8">
        Sertifikatdagi kodni kiriting — uning haqiqiyligini bilib olasiz
      </p>

      <form onSubmit={handleSubmit} className="glass lift rounded-2xl p-6 space-y-4">
        <input
          name="code"
          className="field font-mono text-center text-lg tracking-widest uppercase"
          placeholder="A1B2C3D4E5F6G7H8"
          required
          autoFocus
        />
        <button className="btn w-full" disabled={busy}>
          {busy ? 'Tekshirilmoqda...' : 'Tekshirish'}
        </button>
      </form>

      {result && (
        <div className="mt-6">
          {!result.found ? (
            <div className="glass lift rounded-2xl p-6 text-center">
              <p className="text-red-400 font-bold mb-1">Topilmadi</p>
              <p className="text-sm text-slate-500">
                {result.detail || 'Bunday kodli sertifikat mavjud emas.'}
              </p>
            </div>
          ) : (
            <div
              className={`rounded-2xl p-6 ${
                result.valid ? 'bg-emerald-500/10' : 'bg-red-500/10'
              }`}
            >
              <p
                className={`font-bold mb-4 ${
                  result.valid ? 'text-emerald-400' : 'text-red-400'
                }`}
              >
                {result.valid ? 'Sertifikat haqiqiy' : 'Sertifikat bekor qilingan'}
              </p>

              <dl className="space-y-2.5 text-sm">
                <div className="flex justify-between gap-3">
                  <dt className="text-slate-500">Egasi</dt>
                  <dd className="font-semibold text-right">{result.holder}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-slate-500">Test</dt>
                  <dd className="text-right">{result.quiz_title}</dd>
                </div>
                {result.category && (
                  <div className="flex justify-between gap-3">
                    <dt className="text-slate-500">Yo&apos;nalish</dt>
                    <dd className="text-right">{result.category}</dd>
                  </div>
                )}
                <div className="flex justify-between gap-3">
                  <dt className="text-slate-500">Ball</dt>
                  <dd className="font-bold">{result.score}%</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-slate-500">Berilgan</dt>
                  <dd>
                    {result.issued_at &&
                      new Date(result.issued_at).toLocaleDateString('uz-UZ')}
                  </dd>
                </div>
              </dl>

              {!result.valid && result.revoke_reason && (
                <p className="mt-4 pt-4 border-t border-white/10 text-sm text-red-300">
                  <b>Sabab:</b> {result.revoke_reason}
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
