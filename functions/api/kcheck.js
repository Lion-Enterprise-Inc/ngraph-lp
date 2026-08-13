// 企業調査API（Cloudflare Pages Function）
// 原則: 判定しない。確認できた事実・確認できなかった項目（原因分類つき）だけを返す。
// 入力qの自動判別: 13桁数字=法人番号 / URLらしき文字列=サイト / それ以外=企業名

const DOH = 'https://cloudflare-dns.com/dns-query';
const GBIZ = 'https://info.gbiz.go.jp/hojin/v1/hojin';
const UA = { 'User-Agent': 'Mozilla/5.0 (compatible; NGraphCheck/1.0; +https://ngraph.jp/check/)' };

const ok = (label, value, source) => ({ label, value, status: '確認済', source });
const none = (label, source) => ({ label, value: null, status: '情報なし', source });
const fail = (label, source) => ({ label, value: null, status: '取得失敗', source });

async function dns(name, type) {
  const r = await fetch(`${DOH}?name=${encodeURIComponent(name)}&type=${type}`,
    { headers: { accept: 'application/dns-json' } });
  if (!r.ok) throw new Error('doh ' + r.status);
  return (await r.json()).Answer || [];
}

async function fetchText(url, maxBytes = 400000) {
  const r = await fetch(url, { headers: UA, redirect: 'follow', signal: AbortSignal.timeout(8000) });
  const reader = r.body.getReader();
  let got = 0, chunks = [];
  while (got < maxBytes) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value); got += value.length;
  }
  reader.cancel().catch(() => {});
  return { status: r.status, text: new TextDecoder('utf-8', { fatal: false }).decode(concat(chunks)) };
}
function concat(chunks) {
  const out = new Uint8Array(chunks.reduce((n, c) => n + c.length, 0));
  let o = 0; for (const c of chunks) { out.set(c, o); o += c.length; }
  return out;
}

async function siteChecks(rawUrl) {
  const facts = [];
  let u;
  try { u = new URL(/^https?:\/\//.test(rawUrl) ? rawUrl : 'https://' + rawUrl); } catch { return { facts: [fail('URLの形式', 'input')], host: null, nameGuess: null }; }
  if (u.protocol !== 'https:' && u.protocol !== 'http:') return { facts: [fail('URLの形式', 'input')], host: null, nameGuess: null };
  const host = u.hostname;
  if (/^(localhost|127\.|0\.|10\.|192\.168\.|169\.254\.|100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.|198\.1[89]\.|172\.(1[6-9]|2\d|3[01])\.|\[)/.test(host) || !host.includes('.'))
    return { facts: [fail('URLの形式', 'input')], host: null, nameGuess: null };

  // DNS: MX / SPF / DMARC
  try {
    const mx = await dns(host, 'MX');
    facts.push(mx.length ? ok('メール受信設定（MX）', 'あり', 'DNS')
      : ok('メール受信設定（MX）', 'なし＝このドメイン宛のメールは受信できない設定', 'DNS'));
  } catch { facts.push(fail('メール受信設定（MX）', 'DNS')); }
  try {
    const txt = await dns(host, 'TXT');
    const spf = txt.some(a => /v=spf1/i.test(a.data));
    const dm = (await dns('_dmarc.' + host, 'TXT')).some(a => /v=dmarc1/i.test(a.data));
    facts.push(ok('送信ドメイン認証', `SPF ${spf ? 'あり' : '確認できず'} / DMARC ${dm ? 'あり' : '確認できず'}`, 'DNS'));
  } catch { facts.push(fail('送信ドメイン認証', 'DNS')); }

  // サイト本体
  let nameGuess = null;
  try {
    const { text } = await fetchText(u.origin + '/');
    const ph = /example\.(jp|com|net|org)/i.test(text);
    const tel = /(0\d{1,4}-\d{1,4}-\d{3,4}|tel:0\d{8,10})/.test(text);
    const blog = /href="[^"]*\/(blog|news|column|topics)(\/|\.html|")/i.test(text);
    const staff = text.match(/(従業員数?|社員数)[^0-9０-９]{0,12}([0-9０-９]{1,4})\s*名/);
    facts.push(ok('電話番号の記載', tel ? 'あり' : 'サイト上に確認できず', 'サイト実測'));
    const snsDefs = [['X（旧Twitter）', /href="(https?:\/\/(?:www\.)?(?:x|twitter)\.com\/[^"]{1,80})"/i],
      ['Facebook', /href="(https?:\/\/(?:www\.)?facebook\.com\/[^"]{1,80})"/i],
      ['LinkedIn', /href="(https?:\/\/(?:[a-z]{2}\.)?linkedin\.com\/[^"]{1,80})"/i],
      ['YouTube', /href="(https?:\/\/(?:www\.)?youtube\.com\/[^"]{1,80})"/i],
      ['Instagram', /href="(https?:\/\/(?:www\.)?instagram\.com\/[^"]{1,80})"/i]];
    const snsParts = snsDefs.map(([nm, re]) => { const m = text.match(re); return `${nm}: ${m ? 'あり' : '該当なし'}`; });
    facts.push(ok('SNSの導線（サイト上のリンク）', snsParts.join(' / '), 'サイト実測。サイトにリンクが無いだけでアカウントが存在する場合もある'));
    facts.push(ok('ブログ・お知らせ', blog ? 'あり' : 'サイト上に確認できず', 'サイト実測'));
    if (staff) facts.push(ok('従業員数（サイト自称）', staff[0].replace(/\s+/g, ''), 'サイト記載＝自己申告'));
    if (ph) facts.push(ok('テンプレートの置換漏れ', '本文に例示用ドメイン（example.jp等）が残存', 'サイト実測'));
    const t = text.match(/<title[^>]*>([^<]{1,80})/i);
    const ogs = text.match(/og:site_name"\s+content="([^"]{1,60})"/i);
    const corp = text.match(/(株式会社|合同会社|有限会社)[　-ヿ一-鿿Ａ-Ｚa-zA-Z0-9]{1,20}/);
    nameGuess = (ogs && ogs[1]) || (corp && corp[0]) || (t && t[1].split(/[|｜–—-]/)[0].trim()) || null;
  } catch { facts.push(fail('サイト本体の取得', 'サイト実測')); }
  try {
    const [rb, sm] = await Promise.all([fetchText(u.origin + '/robots.txt', 20000), fetchText(u.origin + '/sitemap.xml', 60000)]);
    if (/example\.(jp|com|net|org)/i.test(rb.text + sm.text))
      facts.push(ok('テンプレートの置換漏れ', 'robots.txt / sitemap.xml が例示用ドメインを参照', 'サイト実測'));
  } catch { /* 無くても正常 */ }

  // ドメイン登録日（.com/.netのみRDAP。他TLDは対象外として明示）
  try {
    const tld = host.split('.').pop();
    if (tld === 'com' || tld === 'net') {
      const r = await fetch(`https://rdap.verisign.com/${tld}/v1/domain/${host.replace(/^www\./, '')}`);
      if (r.ok) {
        const ev = (await r.json()).events || [];
        const reg = ev.find(e => e.eventAction === 'registration');
        if (reg) facts.push(ok('ドメイン登録日', reg.eventDate.slice(0, 10), 'RDAP'));
      } else facts.push(fail('ドメイン登録日', 'RDAP'));
    } else {
      facts.push({ label: 'ドメイン登録日', value: null, status: '対象外', source: `.${tld}は自動照会の対象外（WHOISで手動確認）` });
    }
  } catch { facts.push(fail('ドメイン登録日', 'RDAP')); }
  // Wayback（サイト履歴）はブラウザ側でCORS取得する（WorkersのIPはarchive.orgに遮断されるため）
  return { facts, host, nameGuess };
}

async function gbizByNumber(no, token) {
  const facts = [];
  if (!token) return [fail('登記系情報（gBizINFO）', '設定')];
  const get = async p => {
    const r = await fetch(`${GBIZ}/${p}`, { headers: { 'X-hojinInfo-api-token': token, Accept: 'application/json' } });
    if (!r.ok) throw new Error('gbiz ' + r.status);
    return (await r.json())['hojin-infos'] || [];
  };
  try {
    const h = (await get(no))[0] || {};
    facts.push(ok('商号（登記）', h.name || '該当なし', 'gBizINFO'));
    if (h.location) facts.push(ok('本店所在地（登記）', h.location, 'gBizINFO'));
    facts.push(h.capital_stock ? ok('資本金（届出）', h.capital_stock + '円', 'gBizINFO') : none('資本金（届出）', 'gBizINFO'));
    facts.push(h.employee_number ? ok('従業員数（届出）', h.employee_number + '名', 'gBizINFO') : none('従業員数（届出）', 'gBizINFO'));
    facts.push(h.date_of_establishment ? ok('設立（届出）', h.date_of_establishment, 'gBizINFO') : none('設立（届出）', 'gBizINFO'));
    const secs = { certification: '届出・認定', subsidy: '補助金交付', procurement: '公共調達', commendation: '表彰' };
    for (const [k, jp] of Object.entries(secs)) {
      try {
        const d = (await get(`${no}/${k}`))[0] || {};
        const items = Object.values(d).find(v => Array.isArray(v)) || [];
        facts.push(ok(jp, items.length + '件', 'gBizINFO'));
      } catch { facts.push(fail(jp, 'gBizINFO')); }
    }
  } catch (e) { facts.push(fail('登記系情報（gBizINFO）', 'gBizINFO')); }
  return facts;
}

async function gbizByName(name, token) {
  if (!token) return [];
  const r = await fetch(`${GBIZ}?name=${encodeURIComponent(name)}&limit=8`,
    { headers: { 'X-hojinInfo-api-token': token, Accept: 'application/json' } });
  if (!r.ok) return [];
  const list = ((await r.json())['hojin-infos'] || []).map(h => ({
    corporate_number: h.corporate_number, name: h.name, location: h.location || '',
  }));
  // 完全一致を先頭に（「ステム」で「ステムセル」等が上に来る事故を防ぐ）
  return list.sort((a, b) => (b.name === name) - (a.name === name));
}

async function rateLimit(env, request, bucket, limit) {
  if (!env.LEADS) return true;  // KV未設定時は通す（fail-open）
  const ip = request.headers.get('cf-connecting-ip') || 'x';
  const key = `rl_${bucket}_${ip}_${new Date().toISOString().slice(0, 13)}`;
  const n = parseInt(await env.LEADS.get(key) || '0', 10) + 1;
  await env.LEADS.put(key, String(n), { expirationTtl: 3900 });
  return n <= limit;
}

export async function onRequestPost(context) {
  const token = context.env.GBIZINFO_TOKEN;
  if (!(await rateLimit(context.env, context.request, 'kcheck', 20)))
    return json({ error: '照会の上限（1時間あたり）に達しました。時間をおいてお試しください。' }, 429);
  let body;
  try { body = await context.request.json(); } catch { return json({ error: '入力を読み取れませんでした' }, 400); }
  const q = String(body.q || '').trim().slice(0, 200);
  if (!q) return json({ error: '調査対象を入力してください' }, 400);

  const digits = q.replace(/[^0-9]/g, '');
  if (/^\d{13}$/.test(digits) && digits.length === q.replace(/[T\-\s]/g, '').length) {
    return json({ mode: 'corp', corporate_number: digits, facts: await gbizByNumber(digits, token) });
  }
  if (/^https?:\/\//.test(q) || (/\./.test(q) && !/[　-鿿]/.test(q))) {
    const site = await siteChecks(q);
    const candidates = site.nameGuess ? await gbizByName(site.nameGuess, token) : [];
    return json({ mode: 'site', host: site.host, facts: site.facts, nameGuess: site.nameGuess, candidates });
  }
  const candidates = await gbizByName(q, token);
  return json({ mode: 'name', candidates });
}

const json = (o, s = 200) => new Response(JSON.stringify(o), {
  status: s, headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' },
});
