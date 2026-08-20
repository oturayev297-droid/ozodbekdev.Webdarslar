'use client';

import { useCallback, useLayoutEffect, useRef } from 'react';
import { tokenize, type TokenType } from '@/lib/highlight';

/**
 * Kod muharriri.
 *
 * ODDIY `textarea` USTIGA QURILGAN va bu ATAYLAB shunday. Tayyor
 * muharrirlar (CodeMirror, Monaco) yuzlab kilobayt qo'shadi va
 * o'zining butun dunyosini olib keladi. O'quvchiga kerak bo'lgani
 * esa kam: qator raqamlari, Tab bilan chekinish, ranglar va
 * Ctrl+Enter.
 *
 * `textarea` yana bitta narsani BEPUL beradi — telefondagi
 * klaviatura, nusxa ko'chirish, bekor qilish (Ctrl+Z) va ekran
 * o'qigichlar. Ularning har biri o'z muharririda qaytadan yozilishi
 * kerak bo'lardi.
 *
 * QANDAY ISHLAYDI: matn SHAFFOF `textarea` da turadi, ranglangan
 * nusxa esa uning ORTIDAGI `<pre>` da. Ikkalasining shrifti,
 * chekinishi va qator balandligi bir xil — shuning uchun harflar
 * aniq ustma-ust tushadi. Kursor va tanlash `textarea` niki, ya'ni
 * ular ham odatdagidek ishlaydi.
 */

const TOKEN_CLASS: Record<TokenType, string> = {
  plain: 'text-slate-200',
  comment: 'text-slate-500 italic',
  string: 'text-emerald-300',
  number: 'text-amber-300',
  keyword: 'text-sky-400',
  builtin: 'text-violet-300',
};

/** Bitta chekinish. Python uchun 4 ta bo'sh joy — PEP 8 shunday deydi. */
const INDENT = '    ';

/** Qator balandligi (px). Qator raqamlari shunga qarab joylashadi. */
const LINE_HEIGHT = 20;

/** Shrift o'lchamlari IKKALA QATLAMDA bir xil bo'lishi SHART. */
const FONT = 'font-mono text-[13px] leading-[20px]';

interface Props {
  value: string;
  onChange: (value: string) => void;
  language: string;
  /** Ctrl+Enter (yoki Cmd+Enter) bosilganda. */
  onRun?: () => void;
  rows?: number;
}

/**
 * Matn kiritadi va BEKOR QILISH TARIXINI saqlaydi.
 *
 * `execCommand` eskirgan deb belgilangan, lekin uning o'rnini
 * bosadigan narsa yo'q: qiymatni to'g'ridan-to'g'ri o'zgartirsak,
 * brauzerning Ctrl+Z tarixi UZILADI va o'quvchi Tab bosgandan keyin
 * oldingi holatga qaytolmay qoladi. Ishlamagan holat uchun chaqiruvchi
 * tomonda oddiy yo'l ham bor.
 */
function insertText(textarea: HTMLTextAreaElement, text: string): boolean {
  textarea.focus();
  try {
    return document.execCommand('insertText', false, text);
  } catch {
    return false;
  }
}

export function CodeEditor({ value, onChange, language, onRun, rows = 16 }: Props) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const preRef = useRef<HTMLPreElement>(null);
  const gutterRef = useRef<HTMLDivElement>(null);

  /*
   * Uch qatlam BIR VAQTDA siljiydi. Bo'lmasa, uzun kodda ranglangan
   * matn kursordan orqada qolar va muharrir buzilgandek ko'rinardi.
   */
  const syncScroll = useCallback(() => {
    const area = textareaRef.current;
    if (!area) return;
    if (preRef.current) {
      preRef.current.scrollTop = area.scrollTop;
      preRef.current.scrollLeft = area.scrollLeft;
    }
    if (gutterRef.current) gutterRef.current.scrollTop = area.scrollTop;
  }, []);

  // Kod tashqaridan almashganda (boshqa topshiriq tanlanganda)
  // qatlamlar yana bir joyga kelishi kerak.
  useLayoutEffect(syncScroll, [value, syncScroll]);

  /** Qiymatni qo'lda almashtirish — `execCommand` ishlamagan holat uchun. */
  const replace = useCallback(
    (start: number, end: number, text: string, caret: number) => {
      onChange(value.slice(0, start) + text + value.slice(end));
      requestAnimationFrame(() => {
        textareaRef.current?.setSelectionRange(caret, caret);
      });
    },
    [onChange, value],
  );

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    const area = event.currentTarget;
    const start = area.selectionStart;
    const end = area.selectionEnd;

    // ── Ctrl+Enter — ishga tushirish ──
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      onRun?.();
      return;
    }

    // ── Tab — chekinish ──
    //
    // Standart holatda Tab kursorni KEYINGI ELEMENTGA olib o'tadi va
    // kod yozayotgan odam chekinish qo'ya olmasdi.
    if (event.key === 'Tab') {
      event.preventDefault();

      const lineStart = value.lastIndexOf('\n', start - 1) + 1;
      const multiline = value.slice(start, end).includes('\n');

      if (event.shiftKey || multiline) {
        // Butun blokni ichkariga/tashqariga surish
        const newlineAfter = value.indexOf('\n', end);
        const blockEnd = newlineAfter === -1 ? value.length : newlineAfter;
        const shifted = value
          .slice(lineStart, blockEnd)
          .split('\n')
          .map((line) =>
            event.shiftKey
              ? line.replace(new RegExp('^ {1,' + INDENT.length + '}'), '')
              : INDENT + line,
          )
          .join('\n');

        replace(lineStart, blockEnd, shifted, lineStart + shifted.length);
        return;
      }

      if (!insertText(area, INDENT)) {
        replace(start, end, INDENT, start + INDENT.length);
      }
      return;
    }

    // ── Enter — chekinishni saqlash ──
    //
    // Har qatorda qo'lda bo'sh joy terish o'rganishga xalaqit beradi,
    // Python da esa chekinish MA'NOGA ega: uni yo'qotgan o'quvchi
    // IndentationError bilan yolg'iz qolardi.
    if (event.key === 'Enter' && !event.shiftKey && start === end) {
      const lineStart = value.lastIndexOf('\n', start - 1) + 1;
      const line = value.slice(lineStart, start);
      const indent = /^[ \t]*/.exec(line)?.[0] ?? '';

      const opensBlock =
        language === 'python' ? /:\s*$/.test(line) : /[{([]\s*$/.test(line);

      // Chekinish ham, yangi blok ham yo'q bo'lsa — brauzerning o'zi
      // bajaraversin, bekor qilish tarixi shunda tozaroq qoladi.
      if (!indent && !opensBlock) return;

      const addition = '\n' + indent + (opensBlock ? INDENT : '');
      event.preventDefault();
      if (!insertText(area, addition)) {
        replace(start, end, addition, start + addition.length);
      }
    }
  }

  const lineCount = value.split('\n').length;
  const height = rows * LINE_HEIGHT + 32;

  return (
    <div className="relative rounded-2xl border border-white/10 bg-slate-950 overflow-hidden transition-colors focus-within:border-primary">
      <div className="flex">
        {/* Qator raqamlari */}
        <div
          ref={gutterRef}
          aria-hidden
          className={`${FONT} shrink-0 select-none overflow-hidden border-r border-white/5 py-4 pl-4 pr-3 text-right text-slate-600`}
          style={{ height }}
        >
          {Array.from({ length: lineCount }, (_, index) => (
            <div key={index}>{index + 1}</div>
          ))}
        </div>

        <div className="relative min-w-0 flex-1">
          {/* Ranglangan nusxa — ORTDA, faqat ko'rish uchun */}
          <pre
            ref={preRef}
            aria-hidden
            className={`${FONT} pointer-events-none absolute inset-0 m-0 overflow-auto whitespace-pre p-4`}
          >
            {tokenize(value, language).map((token, index) => (
              <span key={index} className={TOKEN_CLASS[token.type]}>
                {token.text}
              </span>
            ))}
            {'\n'}
          </pre>

          {/* Haqiqiy kiritish maydoni — TEPADA, matni shaffof */}
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(event) => onChange(event.target.value)}
            onKeyDown={handleKeyDown}
            onScroll={syncScroll}
            spellCheck={false}
            autoComplete="off"
            autoCorrect="off"
            autoCapitalize="off"
            aria-label="Kod muharriri"
            className={`${FONT} relative w-full resize-none overflow-auto whitespace-pre bg-transparent p-4 text-transparent caret-white outline-none`}
            style={{ height }}
          />
        </div>
      </div>
    </div>
  );
}
