/**
 * Kodni bo'yash uchun ODDIY tokenizator.
 *
 * NEGA O'ZIMIZNIKI, tayyor kutubxona emas: CodeMirror yoki Monaco —
 * yuzlab kilobayt va butun boshqa dunyo (o'z holati, o'z DOM i, o'z
 * yangilanish sikli). Bu yerda kerak bo'lgani esa juda oz: o'quvchi
 * satrni koddan, izohni satrdan ajrata olsin. Shu maqsad uchun
 * bir necha o'nlab qator yetadi va u hech qanday bog'liqlik
 * qo'shmaydi.
 *
 * BU TO'LIQ PARSER EMAS va bo'lishi ham shart emas. Eng yomon holat —
 * biror so'z noto'g'ri rangda ko'rinadi. Kodning ISHLASHIGA esa
 * bo'yash umuman ta'sir qilmaydi: u faqat ko'rinish.
 *
 * MATN O'ZGARTIRILMAYDI. Tokenlar matnni BO'LAKLARGA ajratadi,
 * qo'shmaydi va tashlamaydi — birlashtirilganda aynan asl kod
 * qaytadi. Buni test tekshiradi: aks holda muharrirda ko'ringan kod
 * ishga tushadigan kod bilan bir xil bo'lmasdi.
 */

export type TokenType = 'plain' | 'comment' | 'string' | 'number' | 'keyword' | 'builtin';

export interface Token {
  text: string;
  type: TokenType;
}

const PYTHON_KEYWORDS = new Set([
  'and', 'as', 'assert', 'async', 'await', 'break', 'class', 'continue', 'def',
  'del', 'elif', 'else', 'except', 'finally', 'for', 'from', 'global', 'if',
  'import', 'in', 'is', 'lambda', 'nonlocal', 'not', 'or', 'pass', 'raise',
  'return', 'try', 'while', 'with', 'yield', 'True', 'False', 'None',
]);

const PYTHON_BUILTINS = new Set([
  'print', 'len', 'range', 'int', 'str', 'float', 'bool', 'list', 'dict', 'set',
  'tuple', 'sum', 'min', 'max', 'abs', 'round', 'sorted', 'enumerate', 'zip',
  'input', 'type', 'isinstance', 'open', 'self',
]);

const JS_KEYWORDS = new Set([
  'async', 'await', 'break', 'case', 'catch', 'class', 'const', 'continue',
  'default', 'delete', 'do', 'else', 'export', 'extends', 'finally', 'for',
  'function', 'if', 'import', 'in', 'instanceof', 'let', 'new', 'of', 'return',
  'super', 'switch', 'this', 'throw', 'try', 'typeof', 'var', 'void', 'while',
  'yield', 'true', 'false', 'null', 'undefined',
]);

const JS_BUILTINS = new Set([
  'console', 'Math', 'JSON', 'Object', 'Array', 'String', 'Number', 'Boolean',
  'Promise', 'Map', 'Set', 'Date', 'parseInt', 'parseFloat', 'isNaN',
]);

/*
 * Bitta katta ifoda, chunki tartib MUHIM: izoh satrdan, satr esa
 * sondan oldin tekshirilishi kerak. Alohida ifodalar bilan bu tartib
 * ko'zdan qochardi.
 *
 * `#` — Python izohi, `//` va `/* *\/` — JavaScript izohi. Ikkalasi
 * uchun bitta ifoda ishlatiladi: noto'g'ri tilda uchrasa ham eng
 * yomoni rang xato bo'ladi, xolos.
 */
const TOKEN_RE = new RegExp(
  [
    '(#[^\n]*)',                                   // Python izohi
    '(//[^\n]*)',                                  // JS izohi
    '(/\*[\s\S]*?\*/)',                         // JS blok izohi
    '("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\')',    // Python ko'p qatorli satri
    '(`(?:\\.|[^`\\])*`)',                      // JS shablon satri
    '("(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\')', // oddiy satr
    '(\b\d+(?:\.\d+)?\b)',                     // son
    '([A-Za-z_$][A-Za-z0-9_$]*)',                   // so'z
  ].join('|'),
  'g',
);

export function tokenize(code: string, language: string): Token[] {
  const keywords = language === 'python' ? PYTHON_KEYWORDS : JS_KEYWORDS;
  const builtins = language === 'python' ? PYTHON_BUILTINS : JS_BUILTINS;

  const tokens: Token[] = [];
  let lastIndex = 0;

  const push = (text: string, type: TokenType) => {
    if (text) tokens.push({ text, type });
  };

  for (const match of code.matchAll(TOKEN_RE)) {
    const index = match.index ?? 0;
    // Naqshga tushmagan bo'lak — qavslar, bo'sh joy, amallar.
    // U ham QO'SHILADI: tashlab ketilsa kod buzilib ko'rinardi.
    push(code.slice(lastIndex, index), 'plain');

    const [text, pyComment, jsComment, jsBlock, pyString, tpl, str, num, word] = match;

    if (pyComment || jsComment || jsBlock) push(text, 'comment');
    else if (pyString || tpl || str) push(text, 'string');
    else if (num) push(text, 'number');
    else if (word) {
      if (keywords.has(word)) push(text, 'keyword');
      else if (builtins.has(word)) push(text, 'builtin');
      else push(text, 'plain');
    } else push(text, 'plain');

    lastIndex = index + text.length;
  }

  push(code.slice(lastIndex), 'plain');
  return tokens;
}
