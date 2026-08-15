'use client';

/**
 * AI Mentor — suzuvchi chat oynasi.
 *
 * SUHBAT TARIXI SERVERDA saqlanadi va klientdan yuborilmaydi. Bu
 * `core/ai_mentor.py` dagi qoida: aks holda o'quvchi soxta "assistant"
 * javoblarini yuborib modelni boshqarib olardi (prompt injection).
 *
 * Bu yerdagi `messages` — faqat EKRAN uchun. Sahifa yangilansa u
 * yo'qoladi, lekin haqiqiy tarix serverda qoladi.
 */

import { useEffect, useRef, useState } from 'react';
import { mentor, mentorHistory, ApiError } from '@/lib/api';

interface Bubble {
  role: 'user' | 'assistant';
  html: string;
}

export function MentorChat({ lessonId }: { lessonId?: number }) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Bubble[]>([]);
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  // Tarix FAQAT chat birinchi marta ochilganda yuklanadi — har
  // sahifada bekorga so'rov ketmasin.
  useEffect(() => {
    if (!open || loaded) return;
    setLoaded(true);

    mentorHistory
      .list()
      .then((history) => {
        const bubbles: Bubble[] = [];
        // Server yangidan eskiga beradi — teskarisiga aylantiramiz
        [...history].reverse().forEach((item) => {
          bubbles.push({ role: 'user', html: escapeHtml(item.question) });
          if (item.answer) bubbles.push({ role: 'assistant', html: item.answer });
        });
        setMessages(bubbles);
      })
      .catch(() => {
        // Tarix kelmasa ham chat ishlayveradi
      });
  }, [open, loaded]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function send(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const input = event.currentTarget.elements.namedItem('question') as HTMLInputElement;
    const question = input.value.trim();
    if (!question || busy) return;

    input.value = '';
    setMessages((prev) => [...prev, { role: 'user', html: escapeHtml(question) }]);
    setBusy(true);

    try {
      const result = await mentor.ask(question, lessonId);
      setMessages((prev) => [...prev, { role: 'assistant', html: result.answer_html }]);
    } catch (err) {
      const text =
        err instanceof ApiError ? err.message : 'Javob olinmadi. Keyinroq urinib ko‘ring.';
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', html: `<p class="text-red-300">${escapeHtml(text)}</p>` },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button
        onClick={() => setOpen((v) => !v)}
        className="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-2xl bg-primary text-slate-950 font-black shadow-lg shadow-primary/20 hover:scale-105 transition"
        aria-label="AI Mentor"
      >
        AI
      </button>

      {open && (
        <div className="fixed bottom-24 right-6 z-50 w-[min(420px,calc(100vw-3rem))] h-[min(560px,calc(100vh-10rem))] glass rounded-2xl flex flex-col overflow-hidden shadow-2xl">
          <div className="px-5 py-4 border-b border-white/5 flex items-center justify-between">
            <div>
              <p className="font-bold text-sm">AI Mentor</p>
              <p className="text-[11px] text-slate-500">Dars bo&apos;yicha savol bering</p>
            </div>
            <button
              onClick={() => setOpen(false)}
              className="text-slate-500 hover:text-slate-300 text-xl leading-none"
            >
              ×
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {messages.length === 0 && (
              <p className="text-sm text-slate-600 text-center py-8 leading-relaxed">
                Tushunmagan joyingizni so&apos;rang.
                <br />
                Mentor uy vazifasini o&apos;rningizga bajarmaydi — tushuntiradi.
              </p>
            )}

            {messages.map((bubble, index) => (
              <div
                key={index}
                className={`max-w-[85%] px-4 py-2.5 rounded-2xl text-sm ${
                  bubble.role === 'user'
                    ? 'ml-auto bg-primary/15 text-slate-100'
                    : 'bg-slate-900/70'
                }`}
              >
                {/*
                  Javob HTML i SERVERDA tozalangan (`core/ai_mentor.py`
                  dagi `_to_html`): matn ekranlanadi va faqat bir necha
                  teg qoldiriladi. Savol esa bu yerda ekranlanadi.
                */}
                <div
                  className="mentor-bubble"
                  dangerouslySetInnerHTML={{ __html: bubble.html }}
                />
              </div>
            ))}

            {busy && (
              <div className="max-w-[85%] px-4 py-2.5 rounded-2xl bg-slate-900/70 text-sm text-slate-500">
                O&apos;ylanmoqda...
              </div>
            )}

            <div ref={endRef} />
          </div>

          <form onSubmit={send} className="p-3 border-t border-white/5 flex gap-2">
            <input
              name="question"
              className="field flex-1 py-2.5 text-sm"
              placeholder="Savolingiz..."
              maxLength={2000}
              autoComplete="off"
              disabled={busy}
            />
            <button
              className="btn px-4 py-2.5 text-sm shrink-0"
              disabled={busy}
              type="submit"
            >
              Yuborish
            </button>
          </form>
        </div>
      )}
    </>
  );
}

/**
 * Foydalanuvchi matnini ekranlaydi.
 *
 * Savol `dangerouslySetInnerHTML` ga tushadi (javob bilan bir xil
 * ko'rinish uchun), shuning uchun undagi `<` belgisi teg bo'lib
 * qolmasligi kerak.
 */
function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/\n/g, '<br>');
}
