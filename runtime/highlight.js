// Tiny syntax highlighter for the code scene: enough to colour Python/JS/Go-ish snippets
// convincingly. Colours are deliberately quiet — amber stays reserved for "look here".
const KEYWORDS = new Set(
  ("def return if elif else for while in not and or is None True False class import from as with try except " +
    "finally raise async await lambda yield pass break continue const let var function new this null undefined " +
    "true false func go chan select defer type struct interface package map range nil switch case default").split(" ")
);

const TOKEN = /(#.*$|\/\/.*$)|([fb]?"(?:[^"\\]|\\.)*"|[fb]?'(?:[^'\\]|\\.)*'|`(?:[^`\\]|\\.)*`)|(\b\d+(?:\.\d+)?\b)|([A-Za-z_][A-Za-z0-9_]*)|(\s+)|(.)/gm;

const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

export function highlightLine(line) {
  let out = "";
  let m;
  TOKEN.lastIndex = 0;
  while ((m = TOKEN.exec(line)) !== null) {
    const [tok, comment, str, num, ident] = m;
    if (comment) out += `<span class="tk-com">${esc(tok)}</span>`;
    else if (str) out += `<span class="tk-str">${esc(tok)}</span>`;
    else if (num) out += `<span class="tk-num">${esc(tok)}</span>`;
    else if (ident) {
      const rest = line.slice(TOKEN.lastIndex);
      if (KEYWORDS.has(tok)) out += `<span class="tk-kw">${tok}</span>`;
      else if (/^\s*\(/.test(rest)) out += `<span class="tk-fn">${tok}</span>`;
      else out += tok;
    } else out += esc(tok);
    if (TOKEN.lastIndex === m.index) TOKEN.lastIndex++;
  }
  return out;
}
