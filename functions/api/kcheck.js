// 企業調査API（Cloudflare Pages Function）
// 原則: 判定しない。確認できた事実・確認できなかった項目（原因分類つき）だけを返す。
// 入力qの自動判別: 13桁数字=法人番号 / URLらしき文字列=サイト / それ以外=企業名

import {
  addressMatches,
  extractSiteIdentity,
  identityValues,
  normalizeCompanyName,
  resolveCorporateCandidate,
} from '../lib/identity.js';
import { lookupInvoiceRegistration } from '../lib/invoice.js';
import { safeFetch } from '../lib/safe-fetch.js';
import { discoverSite } from '../lib/site-discovery.js';

export { extractSiteIdentity, normalizeCompanyName, resolveCorporateCandidate } from '../lib/identity.js';

const DOH = 'https://cloudflare-dns.com/dns-query';
const GBIZ = 'https://info.gbiz.go.jp/hojin/v1/hojin';

const ok = (label, value, source) => ({ label, value, status: '確認済', source });
const none = (label, source) => ({ label, value: null, status: '情報なし', source });
const fail = (label, source) => ({ label, value: null, status: '取得失敗', source });
const unconfirmed = (label, value, source, details = {}) =>
  ({ label, value, status: '未確認', source, ...details });

const GBIZ_SEARCH_LIMIT = 1000;

async function dns(name, type) {
  const r = await fetch(`${DOH}?name=${encodeURIComponent(name)}&type=${type}`,
    { headers: { accept: 'application/dns-json' } });
  if (!r.ok) throw new Error('doh ' + r.status);
  return (await r.json()).Answer || [];
}

async function fetchText(url, maxBytes = 400000, options = {}) {
  return safeFetch(url, {
    deadlineMs: options.deadlineMs || 6000,
    maxBytes,
    maxRedirects: 3,
    fetchImpl: options.fetchImpl,
    resolveHost: options.resolveHost,
  });
}

export async function siteChecks(rawUrl, options = {}) {
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

  // サイト本体。未検出を不存在へ変換せず、探索範囲と停止理由を残す。
  let nameGuess = null, identity = { names: [], addresses: [], corporateNumbers: [], phones: [] };
  let siteCoverage = { status: 'blocked', stop_reason: 'root_fetch_failed' };
  const maxBytesFor = (url, kind) => kind === 'page' ? 400000
    : /robots\.txt(?:$|\?)/i.test(url) ? 50000 : 200000;
  const discovery = await discoverSite({
    origin: u.origin,
    maxPages: 5,
    maxSitemaps: 3,
    fetchPage: (url, kind) => fetchText(url, maxBytesFor(url, kind), options),
  });
  siteCoverage = discovery.coverage;
  if (!discovery.ok) {
    facts.push(fail('サイト本体の取得', `サイト実測（${discovery.rootFailure}）`));
  } else {
    identity = discovery.identity;
    nameGuess = identity.primaryName;
    const paths = discovery.pages.map(url => {
      try { return new URL(url).pathname || '/'; } catch { return url; }
    });
    const source = `サイト実測（取得${discovery.pages.length}ページ: ${paths.join(', ')}／停止: ${siteCoverage.stop_reason}）`;
    facts.push(ok('サイト内の確認範囲', `${discovery.pages.length}ページを取得して確認`, source));

    if (discovery.phones.length) {
      facts.push(ok('電話番号（サイト記載）', discovery.phones.slice(0, 3).join(' / '), source));
    } else {
      facts.push(unconfirmed('電話番号（サイト内確認）',
        `確認した${discovery.pages.length}ページ内では検出できず。電話番号が存在しないとは判断していません。`, source,
        { coverage_status: siteCoverage.status, stop_reason: siteCoverage.stop_reason }));
    }

    if (discovery.socialLinks.length) {
      facts.push(ok('SNSリンク（サイト内で確認）', discovery.socialLinks
        .map(item => `${item.platform}: ${item.url}`).join(' / '), source));
    } else {
      facts.push(unconfirmed('SNSリンク（サイト内確認）',
        `確認した${discovery.pages.length}ページ内では公式リンクを検出できず。SNSアカウントが存在しないとは判断していません。`, source,
        { coverage_status: siteCoverage.status, stop_reason: siteCoverage.stop_reason }));
    }
    facts.push(unconfirmed('SNSアカウント（サイト外Web検索）',
      '未実施。公式サイトからリンクされていないアカウントは、この確認だけでは有無を判断できません。',
      '外部検索provider未接続', { coverage_status: 'blocked', stop_reason: 'provider_not_connected' }));

    const blogUrl = discovery.blogLinks[0] || discovery.feedLinks[0];
    if (blogUrl) {
      facts.push(ok('ブログ・お知らせ', `あり（${blogUrl}）`, source));
    } else {
      facts.push(unconfirmed('ブログ・お知らせ',
        `確認した${discovery.pages.length}ページとサイトマップ内では導線を検出できず。存在しないとは判断していません。`, source,
        { coverage_status: siteCoverage.status, stop_reason: siteCoverage.stop_reason }));
    }
    if (discovery.staff) facts.push(ok('従業員数（サイト自称）', discovery.staff, 'サイト記載＝自己申告'));
    if (discovery.placeholder) facts.push(ok('テンプレートの置換漏れ', '本文に例示用ドメイン（example.jp等）が残存', source));
  }

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
  return { facts, host, nameGuess, identity, siteCoverage };
}

async function gbizByNumber(no, token) {
  const facts = [];
  let corporation = null;
  if (!token) return { facts: [fail('登記系情報（gBizINFO）', '設定')], corporation };
  const get = async p => {
    const r = await fetch(`${GBIZ}/${p}`, { headers: { 'X-hojinInfo-api-token': token, Accept: 'application/json' } });
    if (!r.ok) throw new Error('gbiz ' + r.status);
    return (await r.json())['hojin-infos'] || [];
  };
  try {
    const h = (await get(no))[0] || {};
    corporation = { corporate_number: no, name: h.name || null, location: h.location || null };
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
  return { facts, corporation };
}

const INVOICE_SOURCE = '国税庁 適格請求書発行事業者公表システム Web-API';
const INVOICE_LABEL = 'インボイス登録（適格請求書発行事業者）';

// 公表情報と登記の食い違いは、公表側の更新時期の差でも起きる。事実と両方の値だけを出す。
function invoiceMatchFact(entry, corporation) {
  if (!corporation) return null;
  const parts = [];
  if (entry.name && corporation.name) {
    parts.push(normalizeCompanyName(entry.name) === normalizeCompanyName(corporation.name)
      ? '商号は一致' : `商号は一致を確認できず（公表: ${entry.name} ／ 登記: ${corporation.name}）`);
  }
  if (entry.address && corporation.location) {
    parts.push(addressMatches(entry.address, corporation.location)
      ? '所在地は丁目・番地・号まで一致'
      : `所在地は一致を確認できず（公表: ${entry.address} ／ 登記: ${corporation.location}）`);
  }
  if (!parts.length) return null;
  return ok('インボイス公表情報と登記の照合', parts.join(' / '),
    `${INVOICE_SOURCE}とgBizINFO。公表情報の更新時期の差でも不一致は生じます`);
}

export const invoiceCoverage = result =>
  ({ status: result.status, stop_reason: result.stop_reason, registered: result.registered });

export async function invoiceChecks(corporateNumber, appId, corporation = null, fetchImpl) {
  const result = await lookupInvoiceRegistration(corporateNumber, appId, fetchImpl);
  if (result.status === 'blocked') {
    return { facts: [{ ...fail(INVOICE_LABEL, INVOICE_SOURCE), value:
      '照会できませんでした。登録が無いとは判断していません。',
    coverage_status: 'blocked', stop_reason: result.stop_reason }], result };
  }
  const asOf = result.lastUpdateDate ? `${INVOICE_SOURCE}（${result.lastUpdateDate} 時点）` : INVOICE_SOURCE;
  if (!result.registered) {
    return { facts: [ok(INVOICE_LABEL,
      `登録なし（${result.number} は公表システムに存在しない）。免税事業者など、登録していない事業者は普通にあります`,
      asOf)], result };
  }
  const entry = result.entry;
  const state = entry.disposalDate ? `登録取消（取消年月日 ${entry.disposalDate}）`
    : entry.expireDate ? `登録失効（失効年月日 ${entry.expireDate}）`
      : '登録あり（取消・失効の記載なし）';
  const facts = [ok(INVOICE_LABEL, `${state}／登録番号 ${result.number}`, asOf)];
  if (entry.registrationDate) facts.push(ok('インボイス登録年月日', entry.registrationDate, asOf));
  if (entry.name) facts.push(ok('公表されている名称（インボイス）', entry.name, asOf));
  if (entry.address) facts.push(ok('公表されている所在地（インボイス）', entry.address, asOf));
  const match = invoiceMatchFact(entry, corporation);
  if (match) facts.push(match);
  return { facts, result };
}

export async function gbizByName(name, token, fetchImpl = globalThis.fetch) {
  const blocked = reason => ({
    candidates: [], complete: false, status: 'blocked', stop_reason: 'provider_blocked', reason,
  });
  if (!token) return blocked('token_not_configured');
  // 同名法人が多い商号（例: JCS）は少数件だけでは所在地一致候補が落ちる。
  // 公式の既定件数まで取得し、上限到達時は未取得候補があり得るため自動確定しない。
  let r;
  try {
    r = await fetchImpl(`${GBIZ}?name=${encodeURIComponent(name)}&limit=${GBIZ_SEARCH_LIMIT}`,
      { headers: { 'X-hojinInfo-api-token': token, Accept: 'application/json' } });
  } catch {
    return blocked('network_error');
  }
  if (!r.ok) return blocked(`http_${r.status}`);
  let list;
  try {
    list = ((await r.json())['hojin-infos'] || []).map(h => ({
      corporate_number: h.corporate_number, name: h.name, location: h.location || '',
    }));
  } catch {
    return blocked('invalid_response');
  }
  // 完全一致を先頭に（「ステム」で「ステムセル」等が上に来る事故を防ぐ）
  const normalized = normalizeCompanyName(name);
  return {
    candidates: list.sort((a, b) =>
      Number(normalizeCompanyName(b.name) === normalized) - Number(normalizeCompanyName(a.name) === normalized)),
    complete: list.length < GBIZ_SEARCH_LIMIT,
    status: 'covered',
    stop_reason: list.length < GBIZ_SEARCH_LIMIT ? 'required_sources_exhausted' : 'provider_result_truncated',
  };
}

async function rateLimit(env, request, bucket, limit) {
  if (!env.LEADS) return true;  // KV未設定時は通す（fail-open）
  const ip = request.headers.get('cf-connecting-ip') || 'x';
  const key = `rl_${bucket}_${ip}_${new Date().toISOString().slice(0, 13)}`;
  const n = parseInt(await env.LEADS.get(key) || '0', 10) + 1;
  await env.LEADS.put(key, String(n), { expirationTtl: 3900 });
  return n <= limit;
}

// Worker自身の公開ホストを調べる場合は、公開URLへの自己subrequestではなく
// 同じデプロイの静的アセットbindingを使う。ホスト名のハードコードはしない。
export function createRuntimeSiteFetch(context) {
  const runtimeOrigin = new URL(context.request.url).origin;
  return async (resource, init = {}) => {
    const target = new URL(resource);
    if (context.env.ASSETS && target.origin === runtimeOrigin) {
      return context.env.ASSETS.fetch(new Request(target.toString(), init));
    }
    return globalThis.fetch(resource, init);
  };
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
    const gbiz = await gbizByNumber(digits, token);
    const invoice = await invoiceChecks(digits, context.env.INVOICE_API_ID, gbiz.corporation);
    return json({ mode: 'corp', corporate_number: digits,
      facts: [...gbiz.facts, ...invoice.facts], invoiceCoverage: invoiceCoverage(invoice.result) });
  }
  if (/^https?:\/\//.test(q) || (/\./.test(q) && !/[　-鿿]/.test(q))) {
    const site = await siteChecks(q, { fetchImpl: createRuntimeSiteFetch(context) });
    const search = site.nameGuess
      ? await gbizByName(site.nameGuess, token)
      : { candidates: [], complete: false, status: 'input_required', stop_reason: 'trusted_name_not_found' };
    const candidates = search.candidates;
    const resolved = resolveCorporateCandidate(site.identity, candidates, { complete: search.complete });
    if (resolved) {
      const corporation = resolved.candidate;
      const matchFacts = [ok('法人の自動特定', `${corporation.name}（法人番号 ${corporation.corporate_number}）`,
        `独立アンカー2点以上（${resolved.anchors.join(' + ')}）でサイト記載とgBizINFOを照合`)];
      const siteAddresses = identityValues(site.identity.addresses);
      if (site.identity.addresses.length && corporation.location) {
        matchFacts.push(ok('サイト所在地と登記所在地の照合', resolved.addressMatch
          ? '丁目・番地・号まで一致'
          : `一致を確認できず（サイト: ${siteAddresses[0]} / 登記: ${corporation.location}）`,
        'サイト記載とgBizINFO'));
      }
      const corporateFacts = (await gbizByNumber(corporation.corporate_number, token)).facts;
      const invoice = await invoiceChecks(corporation.corporate_number, context.env.INVOICE_API_ID, corporation);
      return json({ mode: 'site', host: site.host,
        facts: [...site.facts, ...matchFacts, ...corporateFacts, ...invoice.facts],
        invoiceCoverage: invoiceCoverage(invoice.result),
        nameGuess: corporation.name, candidates: [], siteCoverage: site.siteCoverage, resolvedCorporate: {
          ...corporation, name_match: resolved.nameMatch,
          address_match: resolved.addressMatch,
          anchors: resolved.anchors,
        } });
    }
    const resolutionFacts = search.status === 'blocked'
      ? [{ ...fail('法人候補の照会', 'gBizINFO'), coverage_status: 'blocked',
        stop_reason: search.stop_reason, reason: search.reason }]
      : [];
    const exactCandidates = candidates.filter(candidate =>
      normalizeCompanyName(candidate.name) === normalizeCompanyName(site.nameGuess));
    return json({ mode: 'site', host: site.host, facts: [...site.facts, ...resolutionFacts], nameGuess: site.nameGuess,
      siteCoverage: site.siteCoverage,
      resolutionCoverage: { status: search.status, stop_reason: search.stop_reason, reason: search.reason || null },
      candidates: (exactCandidates.length ? exactCandidates : candidates).slice(0, 20) });
  }
  const search = await gbizByName(q, token);
  if (search.status === 'blocked') {
    return json({ error: '法人データベースの照会に失敗しました。候補なしとは判定していません。',
      resolutionCoverage: { status: search.status, stop_reason: search.stop_reason, reason: search.reason } }, 502);
  }
  return json({ mode: 'name', candidates: search.candidates.slice(0, 20),
    resolutionCoverage: { status: search.status, stop_reason: search.stop_reason } });
}

const json = (o, s = 200) => new Response(JSON.stringify(o), {
  status: s, headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' },
});
