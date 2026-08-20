/**
 * Kodni BRAUZERDA ishga tushirish.
 *
 * SERVER UMUMAN QATNASHMAYDI. Bu xavfsizlik qarori: begona kodni
 * serverda ijro etish — bu serverni begona odamga topshirish demak.
 * Sandbox, timeout, resurs cheklovi — hammasini to'g'ri qilish qiyin
 * va bitta xato butun tizimni ochib beradi.
 *
 * KOD ALOHIDA OQIMDA (Web Worker) ISHLAYDI.
 *
 * Ilgari u to'g'ridan-to'g'ri sahifada ishlardi va `while (true)`
 * yozgan o'quvchi butun tabni MUZLATIB qo'yardi: tugmalar bosilmasdi,
 * kodni tuzatib bo'lmasdi, brauzerni majburan yopishdan boshqa yo'l
 * qolmasdi. O'rganayotgan odam esa cheksiz siklni ATAYLAB emas,
 * tasodifan yozadi — ya'ni bu kamdan-kam emas, odatiy hol.
 *
 * Worker'ni esa TO'XTATIB bo'ladi: `terminate()` uni o'sha zahoti
 * o'ldiradi va sahifa umuman sezmaydi.
 *
 * PYTHON — Pyodide (CPython WebAssembly ga kompilyatsiya qilingan).
 * ~10 MB, shuning uchun sahifa ochilganda emas, faqat BIRINCHI
 * "Ishga tushirish" bosilganda yuklanadi.
 *
 * JAVASCRIPT — `new Function`, `eval` emas. Farqi: `Function`
 * atrofdagi o'zgaruvchilarga yeta olmaydi, `eval` esa yetadi.
 */

const PYODIDE_VERSION = 'v0.26.4';
const PYODIDE_URL = `https://cdn.jsdelivr.net/pyodide/${PYODIDE_VERSION}/full/`;

/**
 * Kod shuncha millisekunddan ko'p ishlasa to'xtatiladi.
 *
 * Pyodide YUKLANISHI bu vaqtga KIRMAYDI — u sekin internetda bir
 * necha o'n soniya olishi mumkin va uni "cheksiz sikl" deb
 * o'ldirish noto'g'ri bo'lardi. Hisob faqat kod ishga tushgandan
 * keyin boshlanadi.
 */
const TIME_LIMIT_MS = 10_000;

/** Chiqishning maksimal hajmi. Cheksiz sikl xotirani yeb qo'ymasin. */
const MAX_OUTPUT_CHARS = 100_000;

export interface RunResult {
  output: string;
  error: string;
  /** Kod vaqt chegarasidan oshib to'xtatildimi. */
  timedOut: boolean;
  /** Ijro necha millisekund davom etdi. */
  durationMs: number;
}

export interface RunOptions {
  /** Chiqish qatorlari kelib turganda chaqiriladi (oqim). */
  onOutput?: (chunk: string) => void;
  /** Pyodide yuklanib, kod ishga tushganda chaqiriladi. */
  onStart?: () => void;
}

/*
 * ─────────────────────── Worker kodi ───────────────────────
 *
 * SATR KO'RINISHIDA, alohida fayl emas: alohida fayl bo'lsa uni
 * bundler chiqishiga qo'shish, yo'lini topish va deploy paytida
 * saqlanib qolishini ta'minlash kerak bo'lardi. Blob esa hech
 * qanday sozlamaga bog'liq emas va har muhitda bir xil ishlaydi.
 */
const WORKER_SOURCE = `
let pyodide = null;

function post(type, payload) {
  self.postMessage({ type, ...payload });
}

function stringify(value) {
  if (typeof value === 'string') return value;
  try {
    return JSON.stringify(value);
  } catch (err) {
    return String(value);
  }
}

async function getPyodide(indexURL) {
  if (pyodide) return pyodide;
  // importScripts BLOKLAYDI — shuning uchun u worker ichida
  // chaqiriladi. Sahifada bo'lsa, 10 MB yuklanguncha interfeys
  // qotib turardi.
  self.importScripts(indexURL + 'pyodide.js');
  pyodide = await self.loadPyodide({ indexURL: indexURL });
  return pyodide;
}

async function runPython(code, indexURL) {
  const py = await getPyodide(indexURL);

  // print() chiqishini ushlaymiz. Busiz kod ishlaydi-yu, o'quvchi
  // hech narsa ko'rmaydi.
  py.setStdout({ batched: (line) => post('output', { chunk: line + '\n' }) });
  py.setStderr({ batched: (line) => post('output', { chunk: line + '\n' }) });

  post('started', {});
  await py.runPythonAsync(code);
}

function runJavaScript(code) {
  const original = console.log;
  console.log = (...args) => {
    post('output', { chunk: args.map(stringify).join(' ') + '\n' });
  };

  try {
    post('started', {});
    // \`new Function\` — \`eval\` EMAS: u atrofdagi o'zgaruvchilarni
    // ko'rmaydi.
    new Function(code)();
  } finally {
    // finally MAJBURIY: kod xato bersa ham konsol qaytarilishi kerak.
    console.log = original;
  }
}

self.onmessage = async (event) => {
  const { code, language, indexURL } = event.data;
  try {
    if (language === 'python') {
      await runPython(code, indexURL);
    } else {
      runJavaScript(code);
    }
    post('done', { error: '' });
  } catch (err) {
    // Xato MATNI o'zgartirilmaydi: Python traceback va JS xatosi
    // o'quvchiga aynan qanday bo'lsa shunday kerak.
    post('done', { error: String((err && err.message) || err) });
  }
};
`;

/**
 * Til bo'yicha saqlanadigan worker.
 *
 * NEGA SAQLANADI: Pyodide 10 MB va uni har "Ishga tushirish" da
 * qaytadan yuklash mumkin emas. Ikkinchi ishga tushirish shu sabab
 * bir zumda bo'ladi.
 *
 * TO'XTATILGANDA TOZALANADI: `terminate()` dan keyin worker o'lik,
 * uni qayta ishlatib bo'lmaydi.
 */
const workers = new Map<string, Worker>();

/**
 * Pyodide YUKLANIB BO'LDIMI.
 *
 * Worker mavjudligining o'zi yetmaydi: u yaratiladi-yu, 10 MB
 * hali yuklanayotgan bo'lishi mumkin. Bayroq aynan kod ishga
 * tushganda qo'yiladi — ya'ni Pyodide tayyor bo'lganda.
 */
let pythonReady = false;

function getWorker(language: string): Worker {
  const existing = workers.get(language);
  if (existing) return existing;

  const blob = new Blob([WORKER_SOURCE], { type: 'text/javascript' });
  const worker = new Worker(URL.createObjectURL(blob));
  workers.set(language, worker);
  return worker;
}

function killWorker(language: string) {
  workers.get(language)?.terminate();
  workers.delete(language);
  // To'xtatilgan worker bilan birga Pyodide ham o'ladi: keyingi
  // ishga tushirish uni QAYTADAN yuklaydi va interfeys buni
  // aytishi kerak.
  if (language === 'python') pythonReady = false;
}

export function run(
  code: string,
  language: string,
  options: RunOptions = {},
): Promise<RunResult> {
  return new Promise((resolve) => {
    const worker = getWorker(language);

    let output = '';
    let timer: ReturnType<typeof setTimeout> | null = null;
    let startedAt = performance.now();
    let finished = false;

    const finish = (error: string, timedOut: boolean) => {
      if (finished) return;
      finished = true;
      if (timer) clearTimeout(timer);
      worker.onmessage = null;
      worker.onerror = null;
      resolve({ output, error, timedOut, durationMs: performance.now() - startedAt });
    };

    worker.onmessage = (event: MessageEvent) => {
      const data = event.data;

      if (data.type === 'started') {
        // VAQT HISOBI SHU YERDA BOSHLANADI — Pyodide yuklanishi
        // kirmaydi, aks holda sekin internetda har Python kodi
        // "cheksiz sikl" deb o'ldirilardi.
        startedAt = performance.now();
        if (language === 'python') pythonReady = true;
        options.onStart?.();
        timer = setTimeout(() => {
          killWorker(language);
          finish(
            `Kod ${TIME_LIMIT_MS / 1000} soniyadan ko'p ishladi va to'xtatildi. ` +
              "Cheksiz sikl (masalan tugamaydigan while) bo'lmasin?",
            true,
          );
        }, TIME_LIMIT_MS);
        return;
      }

      if (data.type === 'output') {
        if (output.length < MAX_OUTPUT_CHARS) {
          output += data.chunk;
          options.onOutput?.(data.chunk);
        }
        return;
      }

      if (data.type === 'done') finish(data.error, false);
    };

    worker.onerror = (event: ErrorEvent) => {
      // Worker'ning o'zi yiqildi (masalan Pyodide yuklanmadi).
      // Uni tashlab yuboramiz: keyingi urinish tozasidan boshlanadi.
      killWorker(language);
      finish(event.message || "Kodni ishga tushirib bo'lmadi", false);
    };

    worker.postMessage({ code, language, indexURL: PYODIDE_URL });
  });
}

/** Python allaqachon yuklanganmi (interfeys "yuklanmoqda" deb yozmasligi uchun). */
export function isPythonReady(): boolean {
  return pythonReady;
}
