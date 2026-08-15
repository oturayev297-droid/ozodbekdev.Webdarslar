'use client';

import { useCallback, useEffect, useState } from 'react';
import { Guard } from '@/components/Guard';
import { challenges, type Challenge, type ChallengeDetail } from '@/lib/api';
import { run } from '@/lib/runner';

function Editor() {
  const [list, setList] = useState<Challenge[]>([]);
  const [current, setCurrent] = useState<ChallengeDetail | null>(null);
  const [code, setCode] = useState('');
  const [output, setOutput] = useState('');
  const [error, setError] = useState('');
  const [running, setRunning] = useState(false);
  const [loadingPython, setLoadingPython] = useState(false);

  const load = useCallback(async (id: number) => {
    const detail = await challenges.detail(id);
    setCurrent(detail);
    setCode(detail.initial_code);
    setOutput('');
    setError('');
  }, []);

  useEffect(() => {
    challenges.list().then((items) => {
      setList(items);
      if (items.length) load(items[0].id);
    });
  }, [load]);

  async function execute() {
    if (!current) return;
    setRunning(true);
    setError('');
    setOutput('');

    // Python birinchi marta ~10 MB yuklaydi. Buni aytmasak,
    // o'quvchi sahifa qotib qolgan deb o'ylardi.
    const needsDownload = current.language === 'python';
    if (needsDownload) setLoadingPython(true);

    try {
      const result = await run(code, current.language);
      setOutput(result.output);
      setError(result.error);
    } catch (err) {
      setError(String(err));
    } finally {
      setRunning(false);
      setLoadingPython(false);
    }
  }

  async function showSolution() {
    if (!current) return;
    // Yechim ALOHIDA so'raladi — u topshiriq ma'lumotida yo'q
    const { solution } = await challenges.solution(current.id);
    setCode(solution);
  }

  return (
    <div className="grid lg:grid-cols-[260px_1fr] gap-6">
      {/* Topshiriqlar ro'yxati */}
      <aside className="lg:h-[calc(100vh-8rem)] lg:overflow-y-auto">
        <h2 className="font-bold mb-3">Topshiriqlar</h2>
        <div className="space-y-1.5">
          {list.map((item) => (
            <button
              key={item.id}
              onClick={() => load(item.id)}
              className={`w-full text-left px-3 py-2.5 rounded-xl text-sm transition ${
                current?.id === item.id
                  ? 'bg-primary/15 text-primary border border-primary/30'
                  : 'glass hover:bg-white/5'
              }`}
            >
              <span className="block truncate">{item.title}</span>
              <span className="block text-[11px] text-slate-500 mt-0.5">
                {item.language} · {item.difficulty}
              </span>
            </button>
          ))}
        </div>
      </aside>

      {/* Muharrir */}
      <div className="min-w-0">
        {current ? (
          <>
            <h1 className="text-2xl font-extrabold mb-1">{current.title}</h1>
            <p className="text-xs text-slate-500 mb-5">
              {current.language} · {current.difficulty}
            </p>

            <div
              className="lesson-prose glass rounded-2xl p-5 mb-5 text-sm"
              dangerouslySetInnerHTML={{ __html: current.description_html }}
            />

            <textarea
              value={code}
              onChange={(event) => setCode(event.target.value)}
              spellCheck={false}
              rows={14}
              className="w-full font-mono text-sm bg-slate-950 border border-white/10 rounded-2xl p-4 outline-none focus:border-primary resize-y"
            />

            <div className="flex flex-wrap items-center gap-3 mt-4">
              <button onClick={execute} disabled={running} className="btn">
                {loadingPython
                  ? 'Python yuklanmoqda (~10 MB)...'
                  : running
                    ? 'Bajarilmoqda...'
                    : 'Ishga tushirish'}
              </button>

              <button
                onClick={() => setCode(current.initial_code)}
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

            {(output || error) && (
              <div className="mt-5">
                <p className="text-xs uppercase tracking-widest text-slate-500 mb-2">
                  Natija
                </p>
                <pre className="bg-slate-950 border border-white/10 rounded-2xl p-4 text-sm overflow-x-auto whitespace-pre-wrap">
                  {output}
                  {error && <span className="text-red-400">{error}</span>}
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
