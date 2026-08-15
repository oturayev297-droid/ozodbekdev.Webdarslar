'use client';

/**
 * O'quv vaqtini o'lchash.
 *
 * Ochiq sahifadan har daqiqada bir marta "men shu yerdaman" signali
 * yuboriladi. Sana va qo'shiladigan miqdor SERVERDA belgilanadi —
 * bu yerdan faqat "hozir ochiqman" degan xabar ketadi.
 *
 * IKKI SHART TEKSHIRILADI:
 *
 * 1. TAB KO'RINIB TURIBDIMI (`document.hidden`). Fonda ochilib
 *    qolgan tab soatlab vaqt yozib ketmasligi kerak — bola darsni
 *    ochib qo'yib, boshqa ish qilayotgan bo'lishi mumkin.
 *
 * 2. ODAM HARAKAT QILYAPTIMI. Oxirgi harakatdan beri uzoq vaqt
 *    o'tgan bo'lsa signal to'xtaydi. Ochiq qoldirilgan noutbuk
 *    "5 soat o'qidi" degan yolg'on hisobot bermasin.
 *
 * Bularsiz raqam ota-onaga foydasiz bo'lardi: u vaqtni emas, tab
 * ochiq turgan muddatni ko'rsatardi.
 */

import { useEffect, useRef } from 'react';
import { study } from './api';

/** Signal oralig'i. Serverdagi `SECONDS_PER_PING` bilan mos. */
const PING_INTERVAL_MS = 60_000;

/** Harakatsizlik chegarasi: shundan keyin signal to'xtaydi. */
const IDLE_LIMIT_MS = 3 * 60_000;

const ACTIVITY_EVENTS = ['mousemove', 'keydown', 'click', 'scroll', 'touchstart'];

export function useStudyTimer(enabled: boolean) {
  const lastActivity = useRef(Date.now());

  useEffect(() => {
    if (!enabled) return;

    const markActive = () => {
      lastActivity.current = Date.now();
    };

    ACTIVITY_EVENTS.forEach((event) =>
      window.addEventListener(event, markActive, { passive: true }),
    );

    const timer = setInterval(() => {
      // Tab ko'rinmayapti — odam boshqa joyda
      if (document.hidden) return;

      // Uzoq vaqt harakat yo'q — sahifa ochiq qoldirilgan
      if (Date.now() - lastActivity.current > IDLE_LIMIT_MS) return;

      // Xato bo'lsa JIMGINA o'tkazamiz: vaqt yozilmasligi darsni
      // o'qishga xalaqit bermasligi kerak.
      study.ping().catch(() => {});
    }, PING_INTERVAL_MS);

    return () => {
      clearInterval(timer);
      ACTIVITY_EVENTS.forEach((event) => window.removeEventListener(event, markActive));
    };
  }, [enabled]);
}
