// 最低賃金記事の計算機（build_minwage_calc.py が埋め込む <script>）を、記事から抜き出して
// そのまま node で動かす試験。DOMは最小のスタブ。ロジックを書き写さず本物を叩く。
//   node scripts/test_minwage_calc.js            → 全ケース検査（NGなら exit 1）
//   node scripts/test_minwage_calc.js --break    → わざと壊した期待値で落ちることを確認（検査の自己テスト）
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ART = path.join(__dirname, '..', 'blog', '20260803-saitei-chingin-2026.html');
const html = fs.readFileSync(ART, 'utf8');
const m = html.match(/<!-- calc:start -->[\s\S]*?<script>([\s\S]*?)<\/script>/);
if (!m) { console.error('計算機の<script>が記事に無い'); process.exit(2); }
const js = m[1];

// ---- 最小DOMスタブ ----
const els = {};
function el(id) {
  if (!els[id]) els[id] = { id, value: '', innerHTML: '', href: '', options: [], handlers: {}, children: [],
    appendChild(c) { this.children.push(c); this.options.push(c); },
    addEventListener(ev, fn) { (this.handlers[ev] = this.handlers[ev] || []).push(fn); },
    fire(ev) { (this.handlers[ev] || []).forEach(f => f()); } };
  return els[id];
}
const document = {
  getElementById: el,
  createElement() { return { value: '', textContent: '' }; },
};
const sandbox = { document, window: {}, console };
vm.createContext(sandbox);
vm.runInContext(js, sandbox);

const P = JSON.parse(js.match(/var P=(\[[\s\S]*?\]);\r?\nvar C=/)[1]);
const C = JSON.parse(js.match(/var C=(\[[\s\S]*?\]);\r?\n/)[1]);
const idx = name => P.findIndex(p => p[0] === name);

function run(pref, now, n, h, size, inv) {
  el('c-pref').value = String(idx(pref));
  el('c-now').value = String(now); el('c-n').value = String(n); el('c-h').value = String(h);
  el('c-size').value = size; el('c-inv').value = String(inv);
  el('c-inv').fire('input');
  const text = el('c-out').innerHTML.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ');
  return { text, href: decodeURIComponent(el('c-cta').href) };
}
const yen = n => n.toLocaleString('ja-JP') + '円';
const capOf = (course, bracket, size) => { const r = C.find(r => r[0] === course && r[1] === bracket); return size === 's' ? r[2] : r[3]; };

const BREAK = process.argv.includes('--break');
let fails = 0;
function expect(label, cond, detail) {
  if (cond) { console.log('  OK', label); } else { fails++; console.log('  NG', label, detail ? '\n     ' + detail : ''); }
}

// 1) 福井の既定: 1,053→1,112 (+59) 5人×132h・30人未満・150万
{
  const p = P[idx('福井')]; const r = run('福井', 1053, 5, 132, 's', 1500000);
  const diff = p[2] - 1053, month = diff * 5 * 132;
  expect('福井: 差が+' + diff, r.text.includes('+' + diff + '円'));
  expect('福井: 月増加額 ' + yen(month), r.text.includes('月 ' + yen(month)));
  expect('福井: 年増加額 ' + yen(month * 12), r.text.includes('年 ' + yen(month * 12)));
  expect('福井: 1,053≥1,050 → 助成率3/4', r.text.includes('／3/4／'));
  expect('福井: 4〜5人・30人未満の上限 ' + yen(capOf('50円', '4〜5人', 's')), r.text.includes(yen(capOf('50円', '4〜5人', 's'))));
  expect('福井: 助成額は上限（150万×3/4=112.5万 > 70万）', r.text.includes('助成額（目安） ' + yen(capOf('50円', '4〜5人', 's'))));
  expect('福井: 実質負担 = 150万−70万', r.text.includes('実質負担（目安） ' + yen(1500000 - capOf('50円', '4〜5人', 's'))));
  expect('福井: CTAに結果が入る', r.href.includes('memo=【賃上げ・助成金の試算】福井') && r.href.includes('type=業務改善助成金'));
}
// 2) 助成率の境界: 1,049円=4/5・1,050円=3/4
expect('境界: 1,049円は4/5', run('福井', 1049, 1, 100, 's', 100000).text.includes('／4/5／'));
expect('境界: 1,050円は3/4', run('福井', 1050, 1, 100, 's', 100000).text.includes('／3/4／'));
// 3) コース境界（差ちょうど 50/70/90）: 目標額から逆算した now を入れる
{
  const t = P[idx('福井')][2];
  expect('コース: 差49円 → 50円コースに届かない', run('福井', t - 49, 1, 100, 's', 100000).text.includes('届きません'));
  expect('コース: 差50円 → 50円コース', run('福井', t - 50, 1, 100, 's', 100000).text.includes('50円コース'));
  expect('コース: 差69円 → 50円コース', run('福井', t - 69, 1, 100, 's', 100000).text.includes('50円コース'));
  expect('コース: 差70円 → 70円コース', run('福井', t - 70, 1, 100, 's', 100000).text.includes('70円コース'));
  expect('コース: 差90円 → 90円コース', run('福井', t - 90, 1, 100, 's', 100000).text.includes('90円コース'));
}
// 4) 人数区分（now=1,000 → 特例（賃金要件）／now=1,053 → 通常）
{
  const t = P[idx('福井')][2];
  const cases = [[1, '1人'], [2, '2〜3人'], [3, '2〜3人'], [4, '4〜5人'], [5, '4〜5人'], [6, '6〜7人'], [7, '6〜7人'], [8, '8人以上'], [9, '8人以上'], [10, '8人以上'], [30, '8人以上']];
  for (const [n, b] of cases) expect('区分（通常）: ' + n + '人 → ' + b, run('福井', 1053, n, 100, 's', 100000).text.includes('（' + b + '・'));
  expect('区分（特例・賃金要件）: 10人 → 10人以上', run('福井', 1000, 10, 100, 's', 100000).text.includes('（10人以上・'));
  expect('区分（特例・賃金要件）: 9人 → 8人以上', run('福井', 1000, 9, 100, 's', 100000).text.includes('（8人以上・'));
  expect('通常の10人には特例の注記が出る', run('福井', 1053, 12, 100, 's', 100000).text.includes('特例事業者だけ'));
  expect('特例の10人には注記が出ない', !run('福井', 1000, 12, 100, 's', 100000).text.includes('特例事業者だけ'));
}
// 5) 事業場規模: 50円・1人 は 30人未満40万／以外30万
expect('規模: 30人未満 40万', run('福井', 1053, 1, 100, 's', 1000000).text.includes(yen(capOf('50円', '1人', 's'))));
expect('規模: 30人以上 30万', run('福井', 1053, 1, 100, 'l', 1000000).text.includes(yen(capOf('50円', '1人', 'l'))));
// 6) 上限に当たらないとき: 助成額 = 投資×率（切り捨て）
{
  const r = run('福井', 1053, 5, 100, 's', 400000); // 40万×3/4=30万 < 70万
  expect('上限未満: 助成額=300,000円', r.text.includes('助成額（目安） 300,000円'));
  expect('上限未満: 「上限に当たっています」が出ない', !r.text.includes('上限に当たって'));
  const r2 = run('福井', 1000, 5, 100, 's', 1000001); // 4/5 → 800,000.8 → 切り捨て
  expect('切り捨て: 1,000,001×4/5=800,000円', r2.text.includes('助成額（目安） 800,000円'));
}
// 6') 交付要綱: 1,000円未満切り捨て／助成対象経費の下限10万円
{
  const r = run('福井', 1053, 5, 100, 's', 401300); // 401,300×3/4=300,975 → 300,000
  expect('切り捨て: 300,975→300,000円（1,000円未満）', r.text.includes('助成額（目安） 300,000円'));
  expect('切り捨て: 実質負担は 401,300−300,000', r.text.includes('実質負担（目安） 101,300円'));
  const r2 = run('福井', 1053, 5, 100, 's', 99999);
  expect('下限: 10万円未満は対象外の案内', r2.text.includes('下限は10万円'));
  expect('下限: 10万円未満では助成額の行を出さない', !r2.text.includes('助成額（目安）'));
  expect('下限: 10万円ちょうどは計算する', run('福井', 1053, 5, 100, 's', 100000).text.includes('助成額（目安） 75,000円'));
}
// 7) 対象外: いまの時給が2026年度額以上
{
  const t = P[idx('東京')][2];
  const r = run('東京', t, 3, 100, 's', 500000);
  expect('対象外: 差なし', r.text.includes('差なし'));
  expect('対象外: 助成金は対象外の見込み', r.text.includes('対象外の見込み'));
  expect('対象外: 人件費 年0円', r.text.includes('年 0円'));
  expect('対象外: CTAは「助成: 要確認」', r.href.includes('助成: 要確認'));
}
// 8) ラベル: 決定／答申／試算がそのまま出る
const shisan = P.find(p => p[3] === '試算'); expect('試算の県が1つ以上ある', !!shisan);
for (const [pref, kind] of [['東京', '決定'], ['福井', '答申'], [shisan ? shisan[0] : '福井', shisan ? '試算' : '答申']]) {
  const p = P[idx(pref)];
  expect('ラベル: ' + pref + ' は' + kind + '（データ側）', p[3] === kind);
  expect('ラベル: ' + pref + ' の表示に（' + kind, run(pref, p[1], 1, 100, 's', 100000).text.includes('（' + kind));
}
// 8') 申請締切: 発効日あり→前日／11月30日超→上限／未公表→前年の発効日を手がかり
{
  expect('締切: 東京（10/1発効）→ 9月30日', run('東京', 1226, 1, 100, 's', 100000).text.includes('申請締切（東京） 9月30日'));
  const late = P.find(p => p[4] && p[4] > '2026-12-01');
  if (late) expect('締切: ' + late[0] + '（' + late[4] + '発効）→ 11月30日の上限', run(late[0], late[1], 1, 100, 's', 100000).text.includes('申請締切（' + late[0] + '） 11月30日'));
  const unk = P.find(p => !p[4] && p[5]);
  if (unk) expect('締切: ' + unk[0] + '（発効日未公表）→ 未公表＋前年の手がかり', run(unk[0], unk[1], 1, 100, 's', 100000).text.includes('未公表') && run(unk[0], unk[1], 1, 100, 's', 100000).text.includes('前年は'));
  expect('データ: 全県に前年の発効日がある', P.every(p => p[5]), P.filter(p => !p[5]).map(p => p[0]).join(','));
}
// 9) 発効日: 東京 2026-10-01 → 10月1日発効
expect('発効日: 東京 10月1日発効', run('東京', 1226, 1, 100, 's', 100000).text.includes('10月1日発効'));
// 10) データの整合: 47県・new>now・答申/決定の県は now+目安 と別物でよい・試算の県は now+54or56
{
  expect('47県', P.length === 47);
  expect('全県 new > now', P.every(p => p[2] > p[1]), P.filter(p => !(p[2] > p[1])).map(p => p[0]).join(','));
  const A = ['埼玉', '千葉', '東京', '神奈川', '愛知', '大阪'];
  const bad = P.filter(p => p[3] === '試算' && p[2] - p[1] !== (A.includes(p[0]) ? 54 : 56));
  expect('試算の県は now+目安（A=54/他=56）', bad.length === 0, bad.map(p => p[0] + ':' + (p[2] - p[1])).join(','));
  expect('上限表18行・各コース6区分', C.length === 18 && ['50円', '70円', '90円'].every(c => C.filter(r => r[0] === c).length === 6));
  expect('上限は人数区分で単調非減少（30人未満）', ['50円', '70円', '90円'].every(c => { const v = C.filter(r => r[0] === c).map(r => r[2]); return v.every((x, i) => i === 0 || x >= v[i - 1]); }));
}
// 11) 自己テスト: --break で期待値を壊す
if (BREAK) expect('（自己テスト）わざと壊した期待', run('福井', 1053, 5, 132, 's', 1500000).text.includes('存在しない文字列'));

console.log(fails ? `\nNG ${fails}件` : '\n全通過');
process.exit(fails ? 1 : 0);
