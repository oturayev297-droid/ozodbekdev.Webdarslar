'use client';

/**
 * Foydalanuvchi holati.
 *
 * NEGA KONTEKST: joriy foydalanuvchi va uning obunasi deyarli har
 * sahifada kerak. Har biri alohida so'rov yuborsa, bitta sahifa
 * ochilishida `/auth/me/` besh marta chaqirilardi.
 *
 * UCH HOLAT ARALASHTIRILMAYDI:
 *
 *   loading   -> hali bilmaymiz (birinchi so'rov ketyapti)
 *   user=null -> tizimga kirmagan
 *   user set  -> kirgan; `user.is_approved` alohida savol
 *
 * Ikkinchi va uchinchisi chalkashtirilsa, sahifa yuklanayotgan paytda
 * "tizimga kiring" degan xabar bir lahzaga chaqnab ketardi.
 */

import { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { auth, ApiError, type Me, type User, type SubscriptionState } from './api';

interface AuthValue {
  loading: boolean;
  user: User | null;
  subscription: SubscriptionState | null;
  refresh: () => Promise<void>;
  login: (username: string, password: string) => Promise<Me>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [me, setMe] = useState<Me | null>(null);

  const refresh = useCallback(async () => {
    try {
      setMe(await auth.me());
    } catch (error) {
      // 401/403 — bu XATO EMAS, shunchaki kirmagan. Konsolga
      // yozilsa, oddiy tashrif buzilgandek ko'rinardi.
      if (!(error instanceof ApiError)) console.error(error);
      setMe(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const value: AuthValue = {
    loading,
    user: me?.user ?? null,
    subscription: me?.subscription ?? null,
    refresh,
    login: async (username, password) => {
      const result = await auth.login(username, password);
      setMe(result);
      return result;
    },
    logout: async () => {
      await auth.logout();
      setMe(null);
    },
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth faqat AuthProvider ichida ishlaydi');
  return context;
}
