'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Guard } from '@/components/Guard';
import { CodeEditor } from '@/components/CodeEditor';
import {
  challenges,
  ApiError,
  type Challenge,
  type ChallengeDetail,
  type CheckResult,
} from '@/lib/api';
import { run } from '@/lib/runner';

/**
 * Kod muharriri.
 *
 * KOD BRAUZERDA ishlaydi (`lib/runner.ts`), NATIJA esa serverda
 * tekshiriladi (`/challenges/<id>/check/`). Ikkiga bo'linishning
 * sababi oddiy: begona kodni serverda ijro etib bo'lmaydi, kutilgan
 * javobni esa brauzerga berib bo'lmaydi — berilsa, topshiriqni
 * yechmasdan ko'chirib qo'yish mumkin bo'lardi.
 */

/** Yozilayotgan kod shu kalit bilan saqlanadi. */
const DRAFT_KEY = (id: number) => `muharrir:kod:${id}`;

const DIFFICULTY_STYLE: Record<string, string> = {
  Oson: 'text-emerald-400',
  "O'rtacha": 'text-amber-400',
  Qiyin: 'text-red-400',
};

const LANGUAGE_LABEL: Record<string, string> = {
  python: 'Python',
  javascript: 'JavaScript',
};

type Filter = 'all' | 'python' | 'javascript';

/**
 * Qoralamani saqlash va o'qish.
 *
 * NEGA KERAK: o'quvchi yarim yozilgan kodni qoldirib boshqa
 * topshiriqqa o'tadi yoki sahifani tasodifan yopadi. Saqlanmasa,
 * yozilgan hamma narsa yo'qolar va qaytib kelganda bo'sh maydon
 * kutib turardi.
 *
 * `localStorage` yo'q bo'lishi mumkin (maxfiylik rejimi, eski
 * brauzer) — shuning uchun har chaqiruv himoyalangan. Qoralama
 * yo'qolishi noqulaylik, sahifaning yiqilishi esa umuman boshqa
 * darajadagi muammo.
 */
function readDraft(id: number): string | null {
  try {
    return window.localStorage.getItem(DRAFT_KEY(id));
  } catch {
    return null;
  }
}

function writeDraft(id: number, code: string) {
  try {
    window.localStorage.setItem(DRAFT_KEY(id), code);
  } catch {
    // Saqlanmadi — kod baribir ekranda turibdi
  }
}

function clearDraft(id: number) {
  try {
    window.localStorage.removeItem(DRAFT_KEY(id));
  } catch {
    // e'tiborsiz
  }
}

function Editor() {
  const [list, setList] = useState<Challenge[]>([]);
  const [filter, setFilter] = useState<Filter>('all');
  const [current, setCurrent] = useState<ChallengeDetail | null>(null);

  const [code, setCode] = useState('');
  const [output, setOutput] = useState('');
  const [error, setError] = useState('');
  const [duration, setDuration] = useState<number | null>(null);

  const [running, setRunning] = useState(false);
  const [loadingPython, setLoadingPython] = useState(false);
  const [checking, setChecking] = useState(false);
  const [result, setResult] = useState<CheckResult | null>(null);

  const load = useCallback(async (id: number) => {
    const detail = await challenges.detail(id);
    setCurrent(detail);
    // Saqlangan qoralama BOR BO'LSA o'sha ochiladi — o'quvchi
    // qayerda to'xtagan bo'lsa, o'sha yerdan davom etadi.
    setCode(readDraft(id) ?? detail.initial_code);
    setOutput('');
    setError('');
    setResult(null);
    setDuration(null);
  }, []);

  useEffect(() => {
    challenges.list().then((items) => {
      setList(items);
      if (items.length) load(items[0].id);
    });
  }, [load]);

  const visible = useMemo(
    () => (filter === 'all' ? list : list.filter((item) => item.language === filter)),
    [list, filter],
  );

  const solvedCount = list.filter((item) => item.solved).length;

  function updateCode(next: string) {
    setCode(next);
    if (current) writeDraft(current.id, next);
  }

  /**
   * Kodni ishga tushiradi va CHIQQAN MATNNI qaytaradi.
   *
   * Natija qaytarilishi "Tekshirish" uchun kerak: u avval kodni
   * ishga tushiradi, so'ng o'sha matnni serverga yuboradi. Holatdan
   * (`output`) o'qib bo'lmasdi — React uni darhol yangilamaydi.
   */
  const execute = useCallback(async (): Promise<{ output: string; error: string } | null> => {
    if (!current || running) return null;

    setRunning(true);
    setError('');
    setOutput('');
    setResult(null);
    setDuration(null);

    // Python birinchi marta ~10 MB yuklaydi. Buni aytmasak,
    // o'quvchi sahifa qotib qolgan deb o'ylardi.
    if (current.language === 'python') setLoadingPython(true);

    try {
      const outcome = await run(code, current.language, {
        // Chiqish OQIM bilan keladi: uzoq ishlaydigan kodning
        // natijasi tugashini kutmasdan ko'rinadi.
        onOutput: (chunk) => setOutput((prev) => prev + chunk),
        onStart: () => setLoadingPython(false),
      });

      setOutput(outcome.output);
      setError(outcome.error);
      setDuration(outcome.durationMs);
      return { output: outcome.output, error: outcome.error };
    } catch (err) {
      setError(String(err));
      return null;
    } finally {
      setRunning(false);
      setLoadingPython(false);
    }
  }, [code, current, running]);

  async function check() {
    if (!current) return;

    const outcome = await execute();
    if (!outcome) return;

    setChecking(true);
    try {
      const checked = await challenges.check(current.id, outcome.output);
      setResult(checked);

      // Ro'yxatdagi belgi darhol yangilanadi — sahifani qayta
      // yuklash talab qilinmaydi.
      if (checked.correct) {
        setList((prev) =>
          prev.map((item) => (item.id === current.id ? { ...item, solved: true } : item)),
        );
        // Ochiq turgan topshiriq ham belgilanadi — aks holda
        // "Yechilgan" yorlig'i faqat boshqa topshiriqqa o'tib
        // qaytgandan keyin paydo bo'lardi.
        setCurrent((prev) => (prev ? { ...prev, solved: true } : prev));
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Tekshirib bo'lmadi");
    } finally {
      setChecking(false);
    }
  }

  function reset() {
    if (!current) return;
    setCode(current.initial_code);
    // Qoralama ham o'chadi: "Boshidan" tugmasi haqiqatan ham
    // boshidan boshlashi kerak.
    clearDraft(current.id);
    setResult(null);
  }

  async function showSolution() {
    if (!current) return;
    // Yechim ALOHIDA so'raladi — u topshiriq ma'lumotida yo'q
    const { solution } = await challenges.solution(current.id);
    updateCode(solution);
  }

  const busy = running || checking;

  return (
    <div className="grid stagger lg:grid-cols-[280px_1fr] gap-6">
      {/* ── Topshiriqlar ro'yxati ── */}
      <aside className="lg:h-[calc(100vh-8rem)] lg:overflow-y-auto">
        <div className="flex items-baseline justify-between mb-3">
          <h2 className="font-bold">Topshiriqlar</h2>
          <span className="text-xs text-slate-500">
            {solvedCount}/{list.length} yechildi
          </span>
        </div>

        {/* Yechilganlar ulushi */}
        {list.length > 0 && (
          <div className="h-1.5 rounded-full bg-white/5 mb-4 overflow-hidden">
            <div
              className="h-full bg-emerald-500 transition-all duration-500"
              style={{ width: `${(solvedCount / list.length) * 100}%` }}
            />
          </div>
        )}

        <div className="flex gap-1.5 mb-4">
          {(['all', 'python', 'javascript'] as Filter[]).map((value) => (
            <button
              key={value}
              onClick={() => setFilter(value)}
              className={`px-2.5 py-1.5 rounded-lg text-xs font-semibold transition ${
                filter === value
                  ? 'bg-primary/15 text-primary'
                  : 'bg-white/5 text-slate-400 hover:bg-white/10'
              }`}
            >
              {value === 'all' ? 'Hammasi' : LANGUAGE_LABEL[value]}
            </button>
          ))}
        </div>

        <div className="space-y-1.5">
          {visible.map((item) => (
            <button
              key={item.id}
              onClick={() => load(item.id)}
              className={`w-full text-left px-3 py-2.5 rounded-xl text-sm transition ${
                current?.id === item.id
                  ? 'bg-primary/15 text-primary border border-primary/30'
                  : 'glass hover:bg-white/5'
              }`}
            >
              <span className="flex items-center gap-2">
                <span
                  aria-hidden
                  className={`text-xs ${item.solved ? 'text-emerald-400' : 'text-slate-700'}`}
                >
                  {item.solved ? '✓' : '○'}
                </span>
                <span className="truncate">{item.title}</span>
              </span>
              <span className="block text-[11px] text-slate-500 mt-0.5 pl-5">
                {LANGUAGE_LABEL[item.language] ?? item.language} ·{' '}
                <span className={DIFFICULTY_STYLE[item.difficulty] ?? ''}>
                  {item.difficulty}
                </span>
              </span>
            </button>
          ))}

          {visible.length === 0 && (
            <p className="text-sm text-slate-500 py-6 text-center">
              Bu tilda topshiriq yo&apos;q.
            </p>
          )}
        </div>
      </aside>

      {/* ── Muharrir ── */}
      <div className="min-w-0">
        {current ? (
          <>
            <div className="flex items-start justify-between gap-4 mb-1">
              <h1 className="text-2xl font-extrabold">{current.title}</h1>
              {current.solved && (
                <span className="shrink-0 px-2.5 py-1 rounded-lg bg-emerald-500/15 text-emerald-400 text-xs font-bold">
                  ✓ Yechilgan
                </span>
              )}
            </div>
            <p className="text-xs text-slate-500 mb-5">
              {LANGUAGE_LABEL[current.language] ?? current.language} ·{' '}
              {current.difficulty}
            </p>

            <div
              className="lesson-prose glass rounded-2xl p-5 mb-5 text-sm"
              dangerouslySetInnerHTML={{ __html: current.description_html }}
            />

            <CodeEditor
              value={code}
              onChange={updateCode}
              language={current.language}
              onRun={execute}
              rows={16}
            />

            <div className="flex flex-wrap items-center gap-3 mt-4">
              <button onClick={execute} disabled={busy} className="btn">
                {loadingPython
                  ? 'Python yuklanmoqda (~10 MB)...'
                  : running
                    ? 'Bajarilmoqda...'
                    : 'Ishga tushirish'}
              </button>

              {current.has_check && (
                <button
                  onClick={check}
                  disabled={busy}
                  className="px-5 py-3 rounded-xl bg-emerald-500/15 text-emerald-400 text-sm font-semibold hover:bg-emerald-500/25 disabled:opacity-50"
                >
                  {checking ? 'Tekshirilmoqda...' : 'Tekshirish'}
                </button>
              )}

              <button
                onClick={reset}
                className="px-5 py-3 rounded-xl bg-white/5 text-sm font-semibold hover:bg-white/10"
              >
                Boshidan
              </button>

              {current.has_solution && (
                <button
                  onClick={showSolution}
                  className="px-5 py-3 rounded-xl bg-white/5 text-sm font-semibold hover:bg-white/10 text-slate-400"
                >
                  Yechimni ko&apos;rish
                </button>
              )}

              {current.next_id && (
                <button
                  onClick={() => load(current.next_id!)}
                  className="ml-auto px-5 py-3 rounded-xl bg-white/5 text-sm font-semibold hover:bg-white/10"
                >
                  Keyingisi →
                </button>
              )}
            </div>

            <p className="text-[11px] text-slate-600 mt-2.5">
              Ctrl+Enter — ishga tushirish · Tab — chekinish · kod
              o&apos;zi saqlanadi
            </p>

            {/* ── Tekshiruv natijasi ── */}
            {result && (
              <div
                className={`mt-5 rounded-2xl p-5 border ${
                  result.correct
                    ? 'bg-emerald-500/10 border-emerald-500/30'
                    : 'bg-amber-500/10 border-amber-500/30'
                }`}
              >
                <p
                  className={`font-bold mb-1 ${
                    result.correct ? 'text-emerald-400' : 'text-amber-400'
                  }`}
                >
                  {result.correct ? '✓ To’g’ri!' : result.detail}
                </p>

                {/*
                  Faqat BIRINCHI farq qilgan qator ko'rsatiladi.
                  Butun kutilgan natija berilsa, uni ko'chirib
                  qo'yish yetarli bo'lardi.
                */}
                {!result.correct && result.diff && (
                  <div className="mt-3 text-sm font-mono space-y-1">
                    <p className="text-xs text-slate-500 font-sans">
                      {result.diff.line}-qatorda farq bor:
                    </p>
                    <p className="text-emerald-300">
                      kutilgan: {result.diff.expected ?? '(qator yo’q)'}
                    </p>
                    <p className="text-red-300">
                      chiqdi: {result.diff.actual ?? '(qator yo’q)'}
                    </p>
                  </div>
                )}

                {result.correct && result.attempts > 1 && (
                  <p className="text-xs text-slate-500">
                    {result.attempts}-urinishda
                  </p>
                )}
              </div>
            )}

            {/* ── Chiqish ── */}
            {(output || error || running) && (
              <div className="mt-5">
                <div className="flex items-baseline justify-between mb-2">
                  <p className="text-xs uppercase tracking-widest text-slate-500">
                    Natija
                  </p>
                  {duration !== null && (
                    <p className="text-[11px] text-slate-600">
                      {duration < 1000
                        ? `${Math.round(duration)} ms`
                        : `${(duration / 1000).toFixed(1)} s`}
                    </p>
                  )}
                </div>
                <pre className="bg-slate-950 border border-white/10 rounded-2xl p-4 text-sm overflow-x-auto whitespace-pre-wrap min-h-[3rem]">
                  {output}
                  {error && <span className="text-red-400">{error}</span>}
                  {running && !output && !error && (
                    <span className="text-slate-600">...</span>
                  )}
                </pre>
              </div>
            )}
          </>
        ) : (
          <p className="text-slate-500 py-12 text-center">Yuklanmoqda...</p>
        )}
      </div>
    </div>
  );
}

export default function EditorPage() {
  return (
    <Guard>
      <Editor />
    </Guard>
  );
}
