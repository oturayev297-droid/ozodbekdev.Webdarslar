'use client';

/**
 * Kontent sahifalarini himoyalaydi.
 *
 * UCHTA HOLAT, UCHTA JAVOB — ular aralashtirilmaydi:
 *
 *   kirmagan   -> /login
 *   ruxsatsiz  -> /kutish
 *   ruxsatli   -> sahifa ochiladi
 *
 * Backenddagi `core.approval.approval_required` bilan bir xil mantiq.
 *
 * DIQQAT: bu yerdagi tekshiruv faqat QULAYLIK uchun. Haqiqiy himoya
 * SERVERDA — frontend tekshiruvini chetlab o'tgan odam API dan
 * baribir 403 oladi va mazmun unga umuman yuborilmaydi.
 */

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import { useStudyTimer } from '@/lib/use-study-timer';

export function Guard({ children }: { children: React.ReactNode }) {
  const { loading, user } = useAuth();
  const router = useRouter();

  // O'quv vaqti FAQAT ruxsatli o'quvchi kontent sahifasida
  // turganda yoziladi. `Guard` barcha shunday sahifalarda
  // ishlatilgani uchun hisoblagich shu yerda — har sahifaga alohida
  // qo'shilsa, biri unutilib qolardi.
  useStudyTimer(Boolean(user?.is_approved));

  useEffect(() => {
    if (loading) return;
    if (!user) router.replace('/login');
    else if (!user.is_approved) router.replace('/kutish');
  }, [loading, user, router]);

  if (loading) {
    return <p className="text-slate-500 py-12 text-center">Yuklanmoqda...</p>;
  }
  if (!user || !user.is_approved) return null;

  return <>{children}</>;
}
