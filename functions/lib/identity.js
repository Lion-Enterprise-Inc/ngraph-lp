// 取引先チェックの対象法人同定。
// Web本文に現れた第三者名を調査対象へ昇格させず、独立したアンカー2点以上でのみ自動確定する。

const LEGAL_FORM_SOURCE = '(?:株式会社|合同会社|有限会社|一般社団法人|一般財団法人|特定非営利活動法人|\\(株\\)|\\(有\\))';
const LEGAL_FORMS = new RegExp(LEGAL_FORM_SOURCE, 'gi');
const LEGAL_FORM_TEST = new RegExp(LEGAL_FORM_SOURCE, 'i');
const TRUSTED_NAME_ORIGINS = new Set(['jsonld', 'og', 'definition_list', 'title']);
const ORIGIN_WEIGHT = Object.freeze({
  jsonld: 100,
  definition_list: 95,
  og: 85,
  title: 70,
  body_regex: 10,
});

const KANJI_VARIANTS = Object.freeze({
  '髙': '高',
  '﨑': '崎',
  '邊': '辺',
  '邉': '辺',
  '齋': '斎',
  '齊': '斎',
  '斉': '斎',
  '澤': '沢',
  '嶋': '島',
  '冨': '富',
});

function foldKatakana(value) {
  return value.replace(/[ァ-ヶ]/g, char =>
    String.fromCharCode(char.charCodeAt(0) - 0x60));
}

function foldKanjiVariants(value) {
  return [...value].map(char => KANJI_VARIANTS[char] || char).join('');
}

export function normalizeCompanyName(value) {
  const normalized = foldKanjiVariants(foldKatakana(String(value || '').normalize('NFKC')));
  return normalized.toLowerCase()
    .replace(LEGAL_FORMS, '')
    .replace(/[^0-9a-z\p{L}]/gu, '');
}

function decodeHtml(value) {
  const entities = { amp: '&', quot: '"', apos: "'", lt: '<', gt: '>', nbsp: ' ' };
  return String(value || '').replace(/&(#x?[0-9a-f]+|amp|quot|apos|lt|gt|nbsp);/gi, (_, entity) => {
    if (entity[0] === '#') {
      const hex = entity[1].toLowerCase() === 'x';
      const code = Number.parseInt(entity.slice(hex ? 2 : 1), hex ? 16 : 10);
      return Number.isFinite(code) && code >= 0 && code <= 0x10ffff ? String.fromCodePoint(code) : '';
    }
    return entities[entity.toLowerCase()] || '';
  });
}

function signalValue(signal) {
  return typeof signal === 'string' ? signal : String(signal?.value || '');
}

function addSignal(list, value, origin, weight = ORIGIN_WEIGHT[origin] || 0) {
  const clean = decodeHtml(value).replace(/\s+/g, ' ').trim();
  if (!clean) return;
  const normalized = clean.normalize('NFKC');
  const existing = list.find(item => item.value.normalize('NFKC') === normalized);
  if (!existing) {
    list.push({ value: clean, origin, weight });
  } else if (weight > existing.weight) {
    existing.origin = origin;
    existing.weight = weight;
  }
}

function jsonLdTypes(value) {
  return (Array.isArray(value?.['@type']) ? value['@type'] : [value?.['@type']])
    .filter(Boolean).join(' ');
}

function sameSite(value, pageUrl) {
  if (!value || !pageUrl) return null;
  try {
    return new URL(value, pageUrl).hostname.replace(/^www\./, '')
      === new URL(pageUrl).hostname.replace(/^www\./, '');
  } catch {
    return false;
  }
}

function collectOrganizationNode(value, result, pageUrl) {
  if (!value || typeof value !== 'object') return;
  if (!/organization|corporation|localbusiness/i.test(jsonLdTypes(value))) return;

  // URLが明示された別サイトのOrganizationは、顧客・取引先など第三者である可能性が高い。
  if (value.url && sameSite(value.url, pageUrl) === false) return;
  addSignal(result.names, value.name, 'jsonld');
  if (typeof value.address === 'string') addSignal(result.addresses, value.address, 'jsonld');
  else if (value.address && typeof value.address === 'object') {
    addSignal(result.addresses, [value.address.addressRegion, value.address.addressLocality,
      value.address.streetAddress].filter(Boolean).join(''), 'jsonld');
  }
  addSignal(result.phones, value.telephone, 'jsonld');
  addCorporateNumber(result.corporateNumbers, value.identifier, 'jsonld');
}

function collectJsonLdRoot(value, result, pageUrl) {
  if (!value || typeof value !== 'object') return;
  if (Array.isArray(value)) {
    for (const item of value) collectOrganizationNode(item, result, pageUrl);
    return;
  }
  collectOrganizationNode(value, result, pageUrl);
  if (Array.isArray(value['@graph'])) {
    for (const item of value['@graph']) collectOrganizationNode(item, result, pageUrl);
  }
}

function addCorporateNumber(list, value, origin) {
  const source = value && typeof value === 'object'
    ? [value.value, value.name, value.identifier].filter(Boolean).join(' ')
    : value;
  const match = String(source || '').normalize('NFKC').match(/(?:^|[^0-9])T?(\d{13})(?:[^0-9]|$)/i);
  if (match) addSignal(list, match[1], origin);
}

function visibleText(html) {
  return decodeHtml(String(html || '')
    .replace(/<(script|style|noscript)[^>]*>[\s\S]*?<\/\1>/gi, ' ')
    .replace(/<!--([\s\S]*?)-->/g, ' ')
    .replace(/<br\s*\/?>|<\/p>|<\/div>|<\/tr>|<\/li>|<\/dd>|<\/dt>|<\/th>|<\/td>/gi, '\n')
    .replace(/<[^>]+>/g, ' '));
}

function trustedNameSignals(identity) {
  return (identity?.names || []).filter(signal => {
    const origin = typeof signal === 'string' ? 'legacy' : signal.origin;
    if (origin === 'legacy') return true;
    if (!TRUSTED_NAME_ORIGINS.has(origin)) return false;
    // titleの一般的なサービス文言は対象法人名として扱わない。
    return origin !== 'title' || LEGAL_FORM_TEST.test(signalValue(signal));
  });
}

export function selectPrimarySiteName(identity) {
  return trustedNameSignals(identity)
    .slice()
    .sort((a, b) => (b.weight || 0) - (a.weight || 0))
    .map(signalValue)
    .find(value => normalizeCompanyName(value)) || null;
}

export function extractSiteIdentity(html, options = {}) {
  const result = { names: [], addresses: [], corporateNumbers: [], phones: [] };
  const source = String(html || '');
  for (const match of source.matchAll(/<script[^>]+type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi)) {
    try {
      collectJsonLdRoot(JSON.parse(decodeHtml(match[1])), result, options.pageUrl);
    } catch {
      // 壊れたJSON-LDは、ラベル付き本文の抽出へ任せる。
    }
  }

  const og = source.match(/(?:property|name)=["']og:site_name["'][^>]*content=["']([^"']{1,100})["']/i)
    || source.match(/content=["']([^"']{1,100})["'][^>]*(?:property|name)=["']og:site_name["']/i);
  if (og) addSignal(result.names, og[1], 'og');

  const title = source.match(/<title[^>]*>([^<]{1,200})/i);
  if (title) {
    const segments = decodeHtml(title[1]).split(/[|｜–—]/).map(value => value.trim()).filter(Boolean);
    for (const segment of segments.filter(value => LEGAL_FORM_TEST.test(value))) {
      addSignal(result.names, segment, 'title');
    }
  }

  const visible = visibleText(source);
  const lines = visible.split(/\r?\n/).map(line => line.replace(/\s+/g, ' ').trim()).filter(Boolean);
  for (let i = 0; i < lines.length; i++) {
    const nameLabel = lines[i].match(/^(?:会社名|商号)\s*[:：]?\s*(.*)$/);
    if (nameLabel) addSignal(result.names, nameLabel[1] || lines[i + 1], 'definition_list');
    const addressLabel = lines[i].match(/^(?:本社所在地|所在地|住所)\s*[:：]?\s*(.*)$/);
    if (addressLabel) addSignal(result.addresses, addressLabel[1] || lines[i + 1], 'definition_list');
    const numberLabel = lines[i].match(/^(?:法人番号|適格請求書発行事業者登録番号|登録番号)\s*[:：]?\s*(.*)$/);
    if (numberLabel) addCorporateNumber(result.corporateNumbers, numberLabel[1] || lines[i + 1], 'definition_list');
    const phoneLabel = lines[i].match(/^(?:電話番号|電話|TEL)\s*[:：]?\s*(.*)$/i);
    if (phoneLabel) addSignal(result.phones, phoneLabel[1] || lines[i + 1], 'definition_list');
  }

  // 本文の社名は導入事例・顧客名等を含む。弱シグナルとして記録するが、検索名や確定アンカーに使わない。
  for (const match of visible.matchAll(new RegExp(`${LEGAL_FORM_SOURCE}[\\p{L}\\p{N}・&＆.'’ー-]{1,40}`, 'gu'))) {
    addSignal(result.names, match[0].replace(/[はがをにでとの]$/u, ''), 'body_regex');
  }

  result.primaryName = selectPrimarySiteName(result);
  return result;
}

function normalizeAddress(value) {
  return String(value || '').normalize('NFKC').toLowerCase()
    .replace(/〒?\s*\d{3}[-ー−‐‑‒–—]?\d{4}/g, '')
    .replace(/[ー−‐‑‒–—]/g, '-')
    .replace(/(\d+)\s*丁目/g, '$1-')
    .replace(/(\d+)\s*番地?(?:の)?/g, '$1-')
    .replace(/(\d+)\s*号/g, '$1')
    .replace(/\s+/g, '')
    .replace(/[、,。]/g, '')
    .replace(/-+/g, '-')
    .replace(/-(?=[^0-9]|$)/g, '');
}

export function addressBlock(value) {
  const normalized = normalizeAddress(value);
  // 建物名・部屋番号は無視するが、丁目-番地-号の数列は省略せず完全一致させる。
  const block = normalized.match(/^(.+?\d+(?:-\d+){1,2})(?=$|[^0-9-])/);
  return block ? block[1] : '';
}

export function addressMatches(siteAddress, registeredAddress) {
  const site = addressBlock(siteAddress);
  const registered = addressBlock(registeredAddress);
  return Boolean(site && registered && site === registered);
}

export function resolveCorporateCandidate(identity, candidates, options = {}) {
  if (options.complete === false) return null;
  const trustedNames = trustedNameSignals(identity).map(signalValue)
    .map(normalizeCompanyName).filter(Boolean);
  const exactNames = (candidates || []).filter(candidate =>
    trustedNames.includes(normalizeCompanyName(candidate.name)));

  const numbers = new Set((identity?.corporateNumbers || []).map(signalValue)
    .map(value => value.replace(/\D/g, '')).filter(value => /^\d{13}$/.test(value)));
  const addresses = (identity?.addresses || []).map(signalValue).filter(Boolean);
  const resolved = [];

  for (const candidate of exactNames) {
    const anchors = ['name'];
    const numberMatch = numbers.has(String(candidate.corporate_number || '').replace(/\D/g, ''));
    const addressMatch = addresses.length && candidate.location
      ? addresses.some(address => addressMatches(address, candidate.location))
      : null;
    if (numberMatch) anchors.push('corporate_number');
    if (addressMatch) anchors.push('address');
    if (anchors.length >= 2) {
      resolved.push({ candidate, anchors, nameMatch: 'exact', addressMatch, numberMatch });
    }
  }

  return resolved.length === 1 ? resolved[0] : null;
}

export function identityValues(signals) {
  return (signals || []).map(signalValue).filter(Boolean);
}
