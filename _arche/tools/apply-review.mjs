// レビューの修正案（merged.json）を src/cases/case-studies-data.ts に当てる。
// 2026-10-17 本人「修正案を全部反映して」。fact / stale / ja だけを当て、unverified / note は当てない。
// 使い方: node tools/apply-review.mjs <merged.json> [--dry]
// 文字列置換を全文にかけず、TypeScript の構文木で「何番目の会社の・どの項目の」文字列かを特定してから直す。
import ts from "typescript";
import { readFileSync, writeFileSync } from "node:fs";

const FILE = "src/cases/case-studies-data.ts";
const [, , mergedPath, flag] = process.argv;
const dry = flag === "--dry";
const items = JSON.parse(readFileSync(mergedPath, "utf-8")).filter((i) => ["fact", "stale", "ja"].includes(i.kind));

const src = readFileSync(FILE, "utf-8");
const sf = ts.createSourceFile(FILE, src, ts.ScriptTarget.Latest, true);

function findVar(name) {
  let found;
  sf.forEachChild(function walk(n) {
    if (ts.isVariableDeclaration(n) && n.name.getText(sf) === name) found = n.initializer;
    n.forEachChild(walk);
  });
  return found;
}
const propName = (p) => (p.name && (ts.isIdentifier(p.name) || ts.isStringLiteral(p.name)) ? p.name.text : undefined);
function prop(obj, name) {
  return obj.properties.find((p) => ts.isPropertyAssignment(p) && propName(p) === name);
}

const cases = findVar("CASE_STUDIES").elements;
const bonus = findVar("BONUS_MAP");

// 文字列リテラルの位置を特定する
function locate(it) {
  const c = cases[it.idx];
  if (!c) throw new Error(`idx ${it.idx} が無い`);
  if (it.field === "bonusReason" || it.field === "bonusReasonEn") {
    const name = prop(c, "name").initializer.text;
    const year = prop(c, "year").initializer.text;
    const tier = prop(c, "tier").initializer.text;
    const entry = prop(bonus, `${name}|${year}|${tier}`);
    if (!entry) throw new Error(`BONUS_MAP に ${name}|${year}|${tier} が無い`);
    return prop(entry.initializer, it.field === "bonusReason" ? "reason" : "reasonEn").initializer;
  }
  const m = it.field.match(/^(reasons|reasonsEn)\.(\w+)$/);
  if (m) return prop(prop(c, m[1]).initializer, m[2]).initializer;
  const p = prop(c, it.field);
  if (!p) throw new Error(`idx ${it.idx} に ${it.field} が無い`);
  return p.initializer;
}

// 同じ文字列への修正をまとめ、順に当てる
const byNode = new Map();
for (const it of items) {
  const node = locate(it);
  if (!ts.isStringLiteral(node) && !ts.isNoSubstitutionTemplateLiteral(node)) throw new Error(`${it.idx} ${it.field} が文字列でない`);
  const key = node.getStart(sf);
  if (!byNode.has(key)) byNode.set(key, { node, value: node.text, its: [] });
  byNode.get(key).its.push(it);
}

const problems = [];
const splices = [];
for (const { node, value, its } of byNode.values()) {
  let v = value;
  for (const it of its) {
    const n = v.split(it.old).length - 1;
    if (n !== 1) { problems.push(`${it.idx} ${it.field}: old が ${n} 回（「${it.old.slice(0, 30)}」）`); continue; }
    v = v.replace(it.old, () => it.new ?? "");
  }
  if (v !== value) splices.push({ start: node.getStart(sf), end: node.getEnd(), text: JSON.stringify(v) });
}

console.log(`修正案 ${items.length} 件 → 文字列 ${splices.length} 個を書き換え、当たらなかった ${problems.length} 件`);
for (const p of problems) console.log("  -", p);
if (!dry && problems.length === 0) {
  let out = src;
  for (const s of splices.sort((a, b) => b.start - a.start)) out = out.slice(0, s.start) + s.text + out.slice(s.end);
  writeFileSync(FILE, out);
  console.log("書き込みました");
}
if (problems.length) process.exit(1);
