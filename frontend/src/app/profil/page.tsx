'use client';

import { useEffect, useState } from 'react';
import { Guard } from '@/components/Guard';
import { profile as profileApi, ApiError, type User } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';

function ProfileForm() {
  const { refresh } = useAuth();
  const [me, setMe] = useState<User | null>(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    profileApi.get().then(setMe).catch(() => setError('Profilni yuklab bo‘lmadi'));
  }, []);

  async function saveDetails(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage('');
    setError('');

    const form = new FormData(event.currentTarget);
    try {
      setMe(
        await profileApi.update({
          full_name: String(form.get('full_name') || ''),
          bio: String(form.get('bio') || ''),
        }),
      );
      await refresh();
      setMessage('Saqlandi');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Xatolik yuz berdi');
    } finally {
      setBusy(false);
    }
  }

  async function uploadAvatar(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;

    setBusy(true);
    setError('');
    try {
      setMe(await profileApi.uploadAvatar(file));
      await refresh();
      setMessage('Rasm yangilandi');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Rasm yuklanmadi');
    } finally {
      setBusy(false);
      // Bir xil faylni qayta tanlash imkoni qolsin
      event.target.value = '';
    }
  }

  async function linkTelegram() {
    setError('');
    try {
      const { url } = await profileApi.linkTelegram();
      // Bir martalik havola — yangi oynada ochiladi
      window.open(url, '_blank', 'noopener,noreferrer');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Havola olinmadi');
    }
  }

  async function unlinkTelegram() {
    setBusy(true);
    try {
      await profileApi.unlinkTelegram();
      setMe(await profileApi.get());
      await refresh();
      setMessage('Telegram uzildi');
    } finally {
      setBusy(false);
    }
  }

  if (!me) {
    return <p className="text-slate-500 py-12 text-center">{error || 'Yuklanmoqda...'}</p>;
  }

  return (
    <div className="max-w-lg mx-auto">
      <h1 className="text-3xl font-extrabold mb-8">Profil</h1>

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

      {/* Rasm */}
      <div className="glass rounded-2xl p-6 mb-5 flex items-center gap-5">
        <span className="w-20 h-20 rounded-2xl bg-slate-800 overflow-hidden shrink-0 flex items-center justify-center text-2xl font-black text-slate-600">
          {me.avatar ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={me.avatar} alt="" className="w-full h-full object-cover" />
          ) : (
            me.username.charAt(0).toUpperCase()
          )}
        </span>

        <div className="min-w-0">
          <p className="font-bold truncate">{me.full_name || me.username}</p>
          <p className="text-sm text-slate-500 mb-3">{me.level}-daraja</p>

          <label className="text-sm text-primary hover:underline cursor-pointer">
            Rasmni almashtirish
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={uploadAvatar}
              className="hidden"
              disabled={busy}
            />
          </label>
          <p className="text-[11px] text-slate-600 mt-1">JPG, PNG yoki WEBP · 3 MB gacha</p>
        </div>
      </div>

      {/* Ma'lumotlar */}
      <form onSubmit={saveDetails} className="glass rounded-2xl p-6 space-y-4 mb-5">
        <div>
          <label className="block text-sm text-slate-400 mb-1.5">F.I.SH.</label>
          <input name="full_name" className="field" defaultValue={me.full_name} />
        </div>

        <div>
          <label className="block text-sm text-slate-400 mb-1.5">O&apos;zim haqimda</label>
          <textarea name="bio" rows={3} className="field resize-y" />
        </div>

        <div className="pt-2 border-t border-white/5 space-y-2 text-sm">
          <div className="flex justify-between gap-3">
            <span className="text-slate-500">Login</span>
            <span>{me.username}</span>
          </div>
          <div className="flex justify-between gap-3">
            <span className="text-slate-500">Email</span>
            <span className="truncate">{me.email}</span>
          </div>
        </div>

        <button className="btn w-full" disabled={busy}>
          {busy ? 'Saqlanmoqda...' : 'Saqlash'}
        </button>
      </form>

      {/* Telegram */}
      <div className="glass rounded-2xl p-6">
        <h2 className="font-bold mb-1">Telegram</h2>
        <p className="text-sm text-slate-500 mb-5 leading-relaxed">
          Ulansa to&apos;lov tasdig&apos;i va obuna muddati haqidagi xabarlarni
          Telegramda olasiz. Telefon raqami so&apos;ralmaydi.
        </p>

        {me.telegram_linked ? (
          <div className="flex items-center justify-between gap-3">
            <span className="text-emerald-400 text-sm">Ulangan</span>
            <button
              onClick={unlinkTelegram}
              disabled={busy}
              className="text-sm text-slate-500 hover:text-red-400"
            >
              Uzish
            </button>
          </div>
        ) : (
          <button onClick={linkTelegram} className="btn w-full">
            Telegramni ulash
          </button>
        )}
      </div>
    </div>
  );
}

export default function ProfilePage() {
  return (
    <Guard>
      <ProfileForm />
    </Guard>
  );
}
