'use client';

import { useEffect, useState } from 'react';
import { Guard } from '@/components/Guard';
import { subscription, ApiError, type SubscriptionInfo } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';

function Subscription() {
  const { refresh } = useAuth();
  const [info, setInfo] = useState<SubscriptionInfo | null>(null);
  const [card, setCard] = useState<any>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const load = () =>
    subscription
      .info()
      .then(setInfo)
      .catch(() => setError('Ma’lumotni yuklab bo‘lmadi'));

  useEffect(() => {
    load();
  }, []);

  // Karta rekvizitlari FAQAT so'rov «Karta berildi» holatiga
  // o'tgandan keyin so'raladi. Oldin so'ralsa server baribir
  // bermaydi — bu shart `billing.payment_requests` da.
  useEffect(() => {
    if (info?.open_request?.status === 'CARD_ISSUED') {
      subscription.card().then(setCard).catch(() => setCard(null));
    }
  }, [info?.open_request?.status]);

  async function createRequest(months: number) {
    setBusy(true);
    setError('');
    try {
      await subscription.createRequest(months);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Xatolik yuz berdi');
    } finally {
      setBusy(false);
    }
  }

  async function markReceipt() {
    setBusy(true);
    try {
      await subscription.markReceipt('TELEGRAM');
      await load();
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Xatolik yuz berdi');
    } finally {
      setBusy(false);
    }
  }

  if (!info) {
    return <p className="text-slate-500 py-12 text-center">{error || 'Yuklanmoqda...'}</p>;
  }

  const { state, plan, options, open_request: openRequest } = info;

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-3xl font-extrabold mb-8">Obuna</h1>

      {error && (
        <p className="px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 text-sm mb-6">
          {error}
        </p>
      )}

      {/* Joriy holat */}
      <div
        className={`rounded-2xl p-6 mb-6 ${
          state.active ? 'bg-emerald-500/10' : 'bg-amber-500/10'
        }`}
      >
        <p className={`font-bold ${state.active ? 'text-emerald-400' : 'text-amber-400'}`}>
          {state.status_label}
        </p>
        {state.current_period_end && (
          <p className="text-sm text-slate-400 mt-1">
            {new Date(state.current_period_end).toLocaleDateString('uz-UZ')} gacha
            {state.days_left >= 0 && ` · ${state.days_left} kun qoldi`}
          </p>
        )}
      </div>

      {/* Ochiq so'rov bo'lsa — oqimni ko'rsatamiz */}
      {openRequest ? (
        <div className="glass rounded-2xl p-6">
          <h2 className="font-bold mb-1">To&apos;lov so&apos;rovi #{openRequest.id}</h2>
          <p className="text-sm text-slate-400 mb-5">
            {openRequest.amount_display} · {openRequest.status_label}
          </p>

          {openRequest.status === 'REQUESTED' && (
            <p className="text-sm text-slate-400 leading-relaxed">
              So&apos;rovingiz qabul qilindi. Administrator karta rekvizitlarini
              beradi — shu sahifani yangilab turing.
            </p>
          )}

          {openRequest.status === 'CARD_ISSUED' && (
            <>
              {card?.cards?.length ? (
                <div className="space-y-3 mb-5">
                  {card.cards.map((item: any, index: number) => (
                    <div key={index} className="p-4 rounded-xl bg-slate-900/60">
                      <p className="font-mono text-lg">{item.number}</p>
                      <p className="text-sm text-slate-400 mt-1">
                        {item.holder}
                        {item.bank && ` · ${item.bank}`}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-slate-500 mb-5">
                  Karta rekvizitlari yuklanmoqda...
                </p>
              )}

              <button onClick={markReceipt} disabled={busy} className="btn w-full">
                {busy ? 'Kutilmoqda...' : 'Chekni yubordim'}
              </button>
              <p className="text-xs text-slate-600 mt-3 leading-relaxed">
                Chekni Telegram orqali yuboring va shu tugmani bosing.
                Administrator tasdiqlagach obuna ochiladi.
              </p>
            </>
          )}

          {openRequest.status === 'RECEIPT_UPLOADED' && (
            <p className="text-sm text-slate-400 leading-relaxed">
              Chekingiz qabul qilindi. Administrator tekshirmoqda — tasdiqlangach
              barcha darslar ochiladi.
            </p>
          )}
        </div>
      ) : (
        <div className="glass rounded-2xl p-6">
          <h2 className="font-bold mb-1">{plan.name}</h2>
          <p className="text-sm text-slate-400 mb-6">
            {plan.price_display} / oy · barcha darslar, testlar va sertifikatlar
          </p>

          <div className="space-y-2">
            {options.map((option) => (
              <button
                key={option.months}
                onClick={() => createRequest(option.months)}
                disabled={busy}
                className="w-full flex items-center justify-between px-5 py-4 rounded-xl bg-slate-900/60 border border-white/5 hover:border-primary/40 transition"
              >
                <span className="font-semibold">{option.months} oy</span>
                <span className="text-primary font-bold">{option.amount_display}</span>
              </button>
            ))}
          </div>

          <p className="text-xs text-slate-600 mt-4 leading-relaxed">
            So&apos;rov yuborganingizdan keyin administrator karta rekvizitlarini
            beradi. To&apos;lov tasdiqlangach obuna darhol ochiladi.
          </p>
        </div>
      )}
    </div>
  );
}

export default function SubscriptionPage() {
  return (
    <Guard>
      <Subscription />
    </Guard>
  );
}
