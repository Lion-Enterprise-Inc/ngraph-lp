// 創業からの年数を 2026年基準に揃える（2026-10-18 本人「年数は2026年基準に揃えて」）。
// 対象は「時間12年」「188年+」「152年存続」「140 years」「135-year」のような年数の言い方で、
// 2026−創業年 から ±2 以内でずれているものだけ。創業年数ではない数字の会社・言い方は SKIP で外す。
// 使い方: node tools/fix-ages.mjs [--dry]
import ts from "typescript";
import { readFileSync, writeFileSync } from "node:fs";

const FILE = "src/cases/case-studies-data.ts";
const BASE = 2026;
// idx: 理由
const SKIP = {
  4: "Zoom の14年は創業者の WebEx 在籍年数",
  31: "マッカランの200年はシェリー樽の伝統のきりのよい言い方",
  33: "Meta の20年は「20年先」の意味",
  131: "東芝の150年は「150年企業」のきりのよい言い方",
};
const dry = process.argv[2] === "--dry";
const src = readFileSync(FILE, "utf-8");
const sf = ts.createSourceFile(FILE, src, ts.ScriptTarget.Latest, true);
const findVar = (name) => { let f; sf.forEachChild(function w(n) { if (ts.isVariableDeclaration(n) && n.name.getText(sf) === name) f = n.initializer; n.forEachChild(w); }); return f; };
const propName = (p) => (p.name && (ts.isIdentifier(p.name) || ts.isStringLiteral(p.name)) ? p.name.text : undefined);
const prop = (o, k) => o.properties.find((p) => ts.isPropertyAssignment(p) && propName(p) === k);

const AGE = /(?<![\d,.$])(\d{1,3}(?:,\d{3})*)(\s*)(年|yr|years?(?= old| of| in|\b)|-year|周年)/g;

const cases = findVar("CASE_STUDIES").elements;
const bonus = findVar("BONUS_MAP");
const splices = [];
const log = [];
cases.forEach((c, idx) => {
  if (SKIP[idx]) return;
  const yNode = prop(c, "year").initializer;
  const y = parseInt(String(yNode.text).match(/\d{3,4}/)?.[0] ?? "0", 10);
  if (!y) return;
  const exp = BASE - y;
  const lits = [];
  const collect = (n) => { if (ts.isStringLiteral(n)) lits.push(n); n.forEachChild(collect); };
  collect(c);
  const b = prop(bonus, `${prop(c, "name").initializer.text}|${yNode.text}|${prop(c, "tier").initializer.text}`);
  if (b) collect(b.initializer);
  for (const lit of lits) {
    const v = lit.text;
    const nv = v.replace(AGE, (m, num, sp, unit) => {
      const n = parseInt(num.replace(/,/g, ""), 10);
      if (n < 10 || n === exp || Math.abs(n - exp) > 2) return m;
      const out = num.includes(",") ? exp.toLocaleString("en-US") : String(exp);
      log.push(`${idx} ${prop(c, "name").initializer.text}: ${num}${sp}${unit} → ${out}${sp}${unit}`);
      return `${out}${sp}${unit}`;
    });
    if (nv !== v) splices.push({ start: lit.getStart(sf), end: lit.getEnd(), text: JSON.stringify(nv) });
  }
});
console.log(`年数 ${log.length} 箇所（文字列 ${splices.length} 個）`);
if (dry) console.log(log.join("\n"));
else {
  let out = src;
  for (const s of splices.sort((a, b) => b.start - a.start)) out = out.slice(0, s.start) + s.text + out.slice(s.end);
  writeFileSync(FILE, out);
  console.log("書き込みました");
}
