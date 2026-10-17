// 元のアルケー画面（autowrite）のソースを src/orig/ に複写する。
// 中身は直さない。ngraph.jp だけで変えたいところは patches.json に「なぜ」つきで書き、
// ここで当てる（当たらなかったら止まる＝元が変わったことに気づける）。
// 直すときは autowrite 側を直す → `npm run sync` → `npm run build`。
import { copyFileSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";

const SRC = "C:/dev/autowrite/src";
const FILES = {
  "app/(teles)/mr-otora/cases/page.tsx": "cases-page.tsx",
  "app/(teles)/mr-otora/cases/_components/case-detail-view.tsx": "case-detail-view.tsx",
  "app/(teles)/mr-otora/cases/_components/score-band-label.tsx": "score-band-label.tsx",
  "app/(teles)/mr-otora/_components/judgment-foundation.tsx": "judgment-foundation.tsx",
  "lib/case-studies-data.ts": "case-studies-data.ts",
};

const patches = JSON.parse(readFileSync("patches.json", "utf-8"));
mkdirSync("src/orig", { recursive: true });
for (const [from, to] of Object.entries(FILES)) {
  let text = readFileSync(`${SRC}/${from}`, "utf-8").replace(/\r\n/g, "\n");
  for (const p of patches.filter((p) => p.file === to)) {
    const i = text.indexOf(p.start);
    const j = i < 0 ? -1 : text.indexOf(p.end, i);
    if (i < 0 || j < 0) throw new Error(`patches.json が当たらない（元が変わった）: ${to} — ${p.why}`);
    text = text.slice(0, i) + p.replace + text.slice(j + p.end.length);
  }
  writeFileSync(`src/orig/${to}`, text);
  console.log(`copied ${from}`);
}
copyFileSync("C:/dev/autowrite/public/teles.png", "public/teles.png");
