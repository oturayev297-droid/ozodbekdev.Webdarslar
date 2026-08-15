/**
 * Kodni BRAUZERDA ishga tushirish.
 *
 * SERVER UMUMAN QATNASHMAYDI. Bu xavfsizlik qarori: begona kodni
 * serverda ijro etish — bu serverni begona odamga topshirish demak.
 * Sandbox, timeout, resurs cheklovi — hammasini to'g'ri qilish qiyin
 * va bitta xato butun tizimni ochib beradi.
 *
 * Brauzerda esa kod foydalanuvchining O'Z mashinasida, o'z tabida
 * ishlaydi. Eng yomoni — o'sha tab osilib qoladi.
 *
 * PYTHON — Pyodide (CPython WebAssembly ga kompilyatsiya qilingan).
 * ~10 MB, shuning uchun sahifa ochilganda emas, faqat BIRINCHI
 * "Ishga tushirish" bosilganda yuklanadi.
 *
 * JAVASCRIPT — `new Function`, `eval` emas. Farqi: `Function`
 * atrofdagi o'zgaruvchilarga (masalan `token`, `apiKey`) yeta
 * olmaydi, `eval` esa yetadi.
 */

const PYODIDE_VERSION = 'v0.26.4';
const PYODIDE_URL = `https://cdn.jsdelivr.net/pyodide/${PYODIDE_VERSION}/full/`;

let pyodidePromise: Promise<any> | null = null;

declare global {
  interface Window {
    loadPyodide?: (config: { indexURL: string }) => Promise<any>;
  }
}

function loadScript(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) return resolve();
    const script = document.createElement('script');
    script.src = src;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error('Pyodide yuklanmadi'));
    document.head.appendChild(script);
  });
}

/**
 * Pyodide ni yuklaydi — BIR MARTA.
 *
 * Promise saqlanadi, natija emas: bir vaqtda ikki marta chaqirilsa
 * ikkalasi ham bitta yuklashni kutadi va 10 MB ikki marta
 * yuklanmaydi.
 */
async function getPyodide() {
  if (!pyodidePromise) {
    pyodidePromise = (async () => {
      await loadScript(`${PYODIDE_URL}pyodide.js`);
      if (!window.loadPyodide) throw new Error('Pyodide topilmadi');
      return window.loadPyodide({ indexURL: PYODIDE_URL });
    })();
  }
  return pyodidePromise;
}

export interface RunResult {
  output: string;
  error: string;
}

async function runPython(code: string): Promise<RunResult> {
  const pyodide = await getPyodide();

  // `print` chiqishini ushlaymiz. Busiz kod ishlaydi-yu, o'quvchi
  // hech narsa ko'rmaydi — natija brauzer konsoliga ketardi.
  let output = '';
  pyodide.setStdout({ batched: (line: string) => (output += line + '\n') });
  pyodide.setStderr({ batched: (line: string) => (output += line + '\n') });

  try {
    await pyodide.runPythonAsync(code);
    return { output, error: '' };
  } catch (err) {
    // Pyodide xatoni Python traceback bilan beradi — uni
    // o'zgartirmasdan ko'rsatamiz, o'quvchi haqiqiy xabarni o'qisin.
    return { output, error: String(err) };
  }
}

function runJavaScript(code: string): RunResult {
  let output = '';
  const originalLog = console.log;

  // `console.log` vaqtincha almashtiriladi
  console.log = (...args: unknown[]) => {
    output += args
      .map((a) => {
        if (typeof a === 'string') return a;
        try {
          return JSON.stringify(a);
        } catch {
          return String(a);
        }
      })
      .join(' ') + '\n';
  };

  try {
    // `new Function` — `eval` EMAS: u atrofdagi o'zgaruvchilarni
    // ko'rmaydi, ya'ni sahifadagi maxfiy qiymatlarga yeta olmaydi.
    new Function(code)();
    return { output, error: '' };
  } catch (err) {
    return { output, error: String(err) };
  } finally {
    // `finally` MAJBURIY: kod xato bersa ham konsol qaytarilishi
    // kerak, aks holda butun sahifaning loglari buzilib qolardi.
    console.log = originalLog;
  }
}

export async function run(code: string, language: string): Promise<RunResult> {
  if (language === 'python') return runPython(code);
  return runJavaScript(code);
}

export function isPythonReady(): boolean {
  return pyodidePromise !== null;
}
