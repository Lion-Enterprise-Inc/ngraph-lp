// 元のアルケー画面を ngraph.jp/cases/ に静的に書き出す。
//   1. vite build（ブラウザ用 JS/CSS）  2. vite build --ssr（HTML を作る用）
//   3. 一覧と各社のページを HTML にして ../cases/ に置く（ブラウザで同じ画面として動き出す）
// その後 ngraph-lp で `python scripts/sync_chrome.py` を流してヘッダー・フッターを入れる。
import { build } from "vite";
import { cpSync, mkdirSync, readdirSync, rmSync, writeFileSync, readFileSync, existsSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { createHash } from "node:crypto";

const OUT = "../cases";
const SITE = "https://ngraph.jp";

await build({ logLevel: "warn" });
await build({ logLevel: "warn", build: { ssr: "src/entry-server.tsx", outDir: "dist/server", emptyOutDir: true, rollupOptions: { input: "src/entry-server.tsx" } } });

const server = await import(pathToFileURL("dist/server/entry-server.js").href + `?t=${Date.now()}`);
const assets = readdirSync("dist/client");
const js = assets.find((f) => /^arche-.*\.js$/.test(f));
const css = assets.find((f) => /^arche-.*\.css$/.test(f));
if (!js || !css) throw new Error("ビルド結果に arche-*.js / arche-*.css が無い");

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

function page({ title, desc, path, body, slug }) {
  return `<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<script async src="https://www.googletagmanager.com/gtag/js?id=G-L96HMXRK1D"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-L96HMXRK1D');
</script>
<title>${esc(title)}</title>
<meta name="description" content="${esc(desc)}">
<meta property="og:title" content="${esc(title)}">
<meta property="og:description" content="${esc(desc)}">
<meta property="og:type" content="website">
<meta property="og:url" content="${SITE}${path}">
<meta property="og:site_name" content="株式会社NGraph">
<link rel="canonical" href="${SITE}${path}">
<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Zen+Old+Mincho:wght@400;600;700;900&family=Zen+Kaku+Gothic+New:wght@400;500;700&display=swap" rel="stylesheet">
<style>
/* ngraph.jp 共通CSSは「ngraph」層に入れる。元のアルケーの部品（utilities）より弱く、
   Tailwind の初期化（base）より強い。層に入れないと共通CSSの *{margin:0;padding:0} が
   元の画面の余白を全部消す（2026-10-17 実測）。 */
@layer theme, base, ngraph, components, utilities;
@import url("/css/ngraph-zen.css?v=12") layer(ngraph);
@import url("/css/sp.css?v=3") layer(ngraph);
</style>
<link rel="stylesheet" href="/cases/_assets/${css}">
</head>
<body>
<header class="header scrolled"></header>
<div class="arche-page bg-background"><div id="arche-root"${slug ? ` data-slug="${esc(slug)}"` : ""}>${body}</div></div>
<footer class="footer"></footer>
<script type="module" src="/cases/_assets/${js}"></script>
</body>
</html>
`;
}

rmSync(OUT, { recursive: true, force: true });
mkdirSync(`${OUT}/_assets`, { recursive: true });
cpSync("dist/client", `${OUT}/_assets`, { recursive: true });

const n = server.COUNT;
writeFileSync(`${OUT}/index.html`, page({
  title: "アルケー — 企業の構造分析 | 株式会社NGraph",
  desc: `アルケーが世界を変えた企業${n}社を12項目×3軸で採点。NCG（Nicomachos Company Graph）100点満点、存続ライン47点、卓越ライン75点。`,
  path: "/cases/",
  body: server.render({ kind: "list" }),
}));

const slugs = server.slugs();
for (const slug of slugs) {
  const m = server.meta(slug);
  mkdirSync(`${OUT}/${slug}`, { recursive: true });
  const d = `${m.name}（NCG ${m.score}/100点）${m.insight}`;
  writeFileSync(`${OUT}/${slug}/index.html`, page({
    title: `${m.name} | アルケー — 企業の構造分析 | 株式会社NGraph`,
    desc: d.length > 156 ? d.slice(0, 155) + "…" : d,
    path: `/cases/${slug}/`,
    body: server.render({ kind: "detail", slug }),
    slug,
  }));
}
// 元ソースの指紋を残す（scripts/arche_check.py が「複写を直したのに作り直していない」を止める）
const h = createHash("sha256");
// 改行は LF に揃えてから数える（git の autocrlf で CRLF に戻っても指紋が変わらないように）
for (const f of readdirSync("src/cases").sort()) h.update(f).update(readFileSync(`src/cases/${f}`, "utf-8").replace(/\r\n/g, "\n"));
writeFileSync(`${OUT}/_assets/build.json`, JSON.stringify({ orig_sha256: h.digest("hex"), pages: slugs.length }, null, 1));

// sitemap.xml の cases 区画を作り直す
const SM = "../sitemap.xml", A = "<!-- cases:start -->", B = "<!-- cases:end -->";
const today = new Date().toISOString().slice(0, 10);
const NL = "\n";
const block = A + NL + ["/cases/", ...slugs.map((s) => `/cases/${s}/`)]
  .map((u) => `  <url><loc>${SITE}${u}</loc><lastmod>${today}</lastmod></url>`).join(NL) + NL + "  " + B;
let sm = readFileSync(SM, "utf-8");
sm = sm.includes(A) ? sm.slice(0, sm.indexOf(A)) + block + sm.slice(sm.indexOf(B) + B.length) : sm.replace("</urlset>", "  " + block + NL + "</urlset>");
writeFileSync(SM, sm);
console.log(`cases/ に一覧1＋各社${slugs.length}ページ（データ${n}件）を書き出し、sitemap.xml を更新しました`);
