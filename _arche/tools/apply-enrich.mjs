// 加筆案（enrich-merged.json）を src/cases/case-studies-data.ts に当てる。
// 2026-10-18 本人「薄い会社の12項目の理由・当時の状況・テレスの所感を…書き足して」。
// 各フィールドを丸ごと置き換える。書いた時点の元の文（thin-*.json）と今の文が違えば当てずに止める（後から別の修正が入った場合）。
// 使い方: node tools/apply-enrich.mjs <enrich-merged.json> <thin-*.json があるフォルダ> [--dry]
import ts from "typescript";
import { readFileSync, writeFileSync, readdirSync } from "node:fs";

const FILE = "src/cases/case-studies-data.ts";
const [, , mergedPath, thinDir, flag] = process.argv;
const dry = flag === "--dry";
const items = JSON.parse(readFileSync(mergedPath, "utf-8"));
const base = {};
for (const f of readdirSync(thinDir).filter((f) => /^thin-\d+\.json$/.test(f))) {
  for (const r of JSON.parse(readFileSync(`${thinDir}/${f}`, "utf-8"))) base[r.idx] = r;
}

const src = readFileSync(FILE, "utf-8");
const sf = ts.createSourceFile(FILE, src, ts.ScriptTarget.Latest, true);
const findVar = (name) => { let f; sf.forEachChild(function w(n) { if (ts.isVariableDeclaration(n) && n.name.getText(sf) === name) f = n.initializer; n.forEachChild(w); }); return f; };
const propName = (p) => (p.name && (ts.isIdentifier(p.name) || ts.isStringLiteral(p.name)) ? p.name.text : undefined);
const prop = (o, k) => o.properties.find((p) => ts.isPropertyAssignment(p) && propName(p) === k);
const cases = findVar("CASE_STUDIES").elements;

const splices = [];
const problems = [];
for (const it of items) {
  const c = cases[it.idx];
  const b = base[it.idx];
  const key = `${prop(c, "name").initializer.text}|${prop(c, "year").initializer.text}|${prop(c, "tier").initializer.text}`;
  if (!b || key !== it.key) { problems.push(`idx ${it.idx}: 会社が一致しない（${key} / ${it.key}）`); continue; }
  for (const [fld, v] of Object.entries(it.fields ?? {})) {
    const m = fld.match(/^reasons\.(\w+)$/);
    const node = m ? prop(prop(c, "reasons").initializer, m[1]).initializer : prop(c, fld).initializer;
    const was = m ? b.reasons[m[1]] : b[fld];
    if (node.text !== was) { problems.push(`${it.key} ${fld}: 書いた後に元の文が変わっている`); continue; }
    splices.push({ start: node.getStart(sf), end: node.getEnd(), text: JSON.stringify(v.new) });
  }
}
console.log(`加筆 ${splices.length} 項目、止めたもの ${problems.length}`);
for (const p of problems) console.log("  -", p);
if (!dry && problems.length === 0) {
  let out = src;
  for (const s of splices.sort((a, b) => b.start - a.start)) out = out.slice(0, s.start) + s.text + out.slice(s.end);
  writeFileSync(FILE, out);
  console.log("書き込みました");
}
if (problems.length) process.exit(1);
