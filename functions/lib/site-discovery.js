// 公開サイト内の連絡先・発信導線を、有限かつ再現可能な範囲で探索する。
// 未検出は不存在ではない。取得範囲と停止理由を必ず呼び出し側へ返す。

import { extractSiteIdentity, identityValues } from './identity.js';

const BLOG_SEGMENTS = new Set(['blog', 'news', 'column', 'topics', 'journal', 'press', 'media']);
const PAGE_TERMS = Object.freeze([
  ['company', 100], ['corporate', 100], ['profile', 100], ['about', 95],
  ['会社概要', 100], ['企業情報', 100], ['会社案内', 100],
  ['contact', 95], ['inquiry', 95], ['access', 90], ['お問い合わせ', 95], ['アクセス', 90],
  ['legal', 90], ['tokushoho', 90], ['privacy', 75], ['terms', 75], ['特定商取引', 90],
  ['blog', 80], ['news', 80], ['column', 75], ['topics', 75], ['press', 75],
  ['ブログ', 80], ['お知らせ', 80], ['新着', 75],
  ['recruit', 60], ['career', 60], ['jobs', 60], ['採用', 60],
]);
const SOCIALS = Object.freeze([
  { name: 'X', hosts: ['x.com', 'twitter.com'], blocked: /\/(?:intent|share|search|hashtag|i)(?:\/|$)/i },
  { name: 'Facebook', hosts: ['facebook.com', 'fb.com'], blocked: /\/(?:sharer|share|dialog|plugins)(?:\.php|\/|$)/i },
  { name: 'LinkedIn', hosts: ['linkedin.com'], blocked: /\/(?:sharearticle|sharing)(?:\/|$)/i },
  { name: 'YouTube', hosts: ['youtube.com', 'youtu.be'], blocked: null },
  { name: 'Instagram', hosts: ['instagram.com'], blocked: /\/(?:accounts|explore)(?:\/|$)/i },
]);

function decodeEntities(value) {
  return String(value || '')
    .replace(/&amp;/gi, '&').replace(/&quot;/gi, '"').replace(/&apos;|&#39;/gi, "'")
    .replace(/&lt;/gi, '<').replace(/&gt;/gi, '>');
}

function safeDecode(value) {
  try { return decodeURIComponent(value); } catch { return String(value || ''); }
}

function attribute(tag, name) {
  const match = String(tag || '').match(new RegExp(`\\b${name}\\s*=\\s*(?:"([^"]*)"|'([^']*)'|([^\\s"'=<>]+))`, 'i'));
  return decodeEntities(match ? (match[1] ?? match[2] ?? match[3] ?? '') : '');
}

function canonicalHost(value) {
  return String(value || '').toLowerCase().replace(/\.$/, '').replace(/^www\./, '');
}

export function isSameSite(first, second) {
  try {
    return canonicalHost(new URL(first).hostname) === canonicalHost(new URL(second).hostname);
  } catch {
    return false;
  }
}

function normalizedUrl(raw, base) {
  try {
    const url = new URL(raw, base);
    if (url.protocol !== 'http:' && url.protocol !== 'https:') return null;
    url.hash = '';
    return url;
  } catch {
    return null;
  }
}

function socialPlatform(url) {
  const host = canonicalHost(url.hostname);
  const definition = SOCIALS.find(item => item.hosts.some(domain => host === domain || host.endsWith(`.${domain}`)));
  if (!definition || definition.blocked?.test(url.pathname)) return null;
  if (!url.pathname.replace(/\/+$/, '')) return null;
  return definition.name;
}

function addSocial(list, raw, base, source, method = 'link') {
  const url = normalizedUrl(raw, base);
  if (!url) return;
  const platform = socialPlatform(url);
  if (!platform) return;
  for (const key of [...url.searchParams.keys()]) {
    if (/^(?:utm_|ref$|ref_|source$)/i.test(key)) url.searchParams.delete(key);
  }
  const value = url.toString();
  const existing = list.find(item => item.platform === platform && item.url === value);
  if (!existing) list.push({ platform, url: value, sources: [source], methods: [method] });
  else {
    if (!existing.sources.includes(source)) existing.sources.push(source);
    if (!existing.methods.includes(method)) existing.methods.push(method);
  }
}

function isBlogUrl(url) {
  return url.pathname.toLowerCase().split('/').filter(Boolean).some(segment => BLOG_SEGMENTS.has(segment));
}

function inspectJsonLd(html, pageUrl, socialLinks) {
  for (const match of String(html || '').matchAll(/<script[^>]+type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi)) {
    let root;
    try { root = JSON.parse(decodeEntities(match[1])); } catch { continue; }
    const visit = value => {
      if (Array.isArray(value)) { value.forEach(visit); return; }
      if (!value || typeof value !== 'object') return;
      const types = (Array.isArray(value['@type']) ? value['@type'] : [value['@type']]).filter(Boolean).join(' ');
      const nodeUrl = value.url ? normalizedUrl(value.url, pageUrl) : null;
      if (/organization|corporation|localbusiness/i.test(types)
          && (!value.url || (nodeUrl && isSameSite(nodeUrl.toString(), pageUrl)))) {
        const sameAs = Array.isArray(value.sameAs) ? value.sameAs : [value.sameAs];
        sameAs.filter(Boolean).forEach(url => addSocial(socialLinks, url, pageUrl, pageUrl, 'same_as'));
      }
      if (Array.isArray(value['@graph'])) value['@graph'].forEach(visit);
    };
    visit(root);
  }
}

export function inspectHtml(html, pageUrl) {
  const source = String(html || '');
  const internalLinks = [];
  const blogLinks = [];
  const feedLinks = [];
  const socialLinks = [];
  const phones = [];

  for (const match of source.matchAll(/<(?:a|link)\b[^>]*>/gi)) {
    const tag = match[0];
    const href = attribute(tag, 'href');
    if (!href) continue;
    if (/^tel:/i.test(href)) {
      const phone = normalizePhone(safeDecode(href.slice(4)));
      if (phone && !phones.includes(phone)) phones.push(phone);
      continue;
    }
    const url = normalizedUrl(href, pageUrl);
    if (!url) continue;
    const rel = attribute(tag, 'rel').toLowerCase().split(/\s+/);
    const platform = socialPlatform(url);
    if (platform) addSocial(socialLinks, url.toString(), pageUrl, pageUrl, rel.includes('me') ? 'rel_me' : 'link');
    if (!isSameSite(url.toString(), pageUrl)) continue;
    const value = url.toString();
    if (!internalLinks.includes(value)) internalLinks.push(value);
    const type = attribute(tag, 'type').toLowerCase();
    if (rel.includes('alternate') && /rss|atom/.test(type)) {
      if (!feedLinks.includes(value)) feedLinks.push(value);
    }
    if (isBlogUrl(url) && !blogLinks.includes(value)) blogLinks.push(value);
  }

  for (const match of source.matchAll(/<meta\b[^>]*>/gi)) {
    const name = attribute(match[0], 'name').toLowerCase();
    const content = attribute(match[0], 'content').trim();
    if (name === 'twitter:site' && /^@[a-z0-9_]{1,30}$/i.test(content)) {
      addSocial(socialLinks, `https://x.com/${content.slice(1)}`, pageUrl, pageUrl, 'twitter_site');
    }
  }
  inspectJsonLd(source, pageUrl, socialLinks);

  const identity = extractSiteIdentity(source, { pageUrl });
  for (const value of identityValues(identity.phones)) {
    const phone = normalizePhone(value);
    if (phone && !phones.includes(phone)) phones.push(phone);
  }
  const staff = source.match(/(従業員数?|社員数)[^0-9０-９]{0,12}([0-9０-９]{1,4})\s*名/);
  return {
    pageUrl,
    internalLinks,
    blogLinks,
    feedLinks,
    socialLinks,
    phones,
    identity,
    staff: staff ? staff[0].replace(/\s+/g, '') : null,
    placeholder: /example\.(?:jp|com|net|org)/i.test(source),
  };
}

function normalizePhone(value) {
  const normalized = String(value || '').normalize('NFKC');
  const matches = normalized.match(/\+?\d[\d\s().-]{7,}\d/g) || [];
  return matches.map(item => item.trim()).find(item => {
    const digits = item.replace(/\D/g, '');
    return digits.length >= 9 && digits.length <= 15;
  }) || null;
}

function xmlLocations(xml) {
  return [...String(xml || '').matchAll(/<loc\b[^>]*>([\s\S]*?)<\/loc>/gi)]
    .map(match => decodeEntities(match[1]).trim()).filter(Boolean);
}

function robotsSitemaps(text, origin) {
  return String(text || '').split(/\r?\n/).map(line => line.replace(/#.*$/, '').trim())
    .map(line => line.match(/^sitemap\s*:\s*(.+)$/i)?.[1]).filter(Boolean)
    .map(value => normalizedUrl(value, origin)?.toString()).filter(Boolean);
}

function ruleRegex(pattern) {
  const end = pattern.endsWith('$');
  const body = (end ? pattern.slice(0, -1) : pattern)
    .replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*');
  return new RegExp(`^${body}${end ? '$' : ''}`);
}

export function robotsAllows(text, url, userAgent = 'NGraphCheck') {
  if (!text) return true;
  const groups = [];
  let group = { agents: [], rules: [] };
  let hasRules = false;
  const flush = () => {
    if (group.agents.length) groups.push(group);
    group = { agents: [], rules: [] };
    hasRules = false;
  };
  for (const raw of String(text).split(/\r?\n/)) {
    const line = raw.replace(/#.*$/, '').trim();
    if (!line) continue;
    const agent = line.match(/^user-agent\s*:\s*(.+)$/i);
    if (agent) {
      if (hasRules) flush();
      group.agents.push(agent[1].trim().toLowerCase());
      continue;
    }
    const rule = line.match(/^(allow|disallow)\s*:\s*(.*)$/i);
    if (rule && group.agents.length) {
      group.rules.push({ allow: rule[1].toLowerCase() === 'allow', pattern: rule[2].trim() });
      hasRules = true;
    }
  }
  flush();
  const ua = userAgent.toLowerCase();
  const exact = groups.filter(item => item.agents.some(agent => agent !== '*' && ua.includes(agent)));
  const applicable = exact.length ? exact : groups.filter(item => item.agents.includes('*'));
  let best = null;
  const target = `${url.pathname}${url.search}`;
  for (const item of applicable) {
    for (const rule of item.rules) {
      if (!rule.pattern || !ruleRegex(rule.pattern).test(target)) continue;
      if (!best || rule.pattern.length > best.pattern.length
          || (rule.pattern.length === best.pattern.length && rule.allow)) best = rule;
    }
  }
  return best ? best.allow : true;
}

function pageScore(url) {
  const haystack = safeDecode(`${url.pathname} ${url.search}`).toLowerCase();
  return PAGE_TERMS.reduce((best, [term, score]) => haystack.includes(term.toLowerCase()) ? Math.max(best, score) : best, 0);
}

function isPageCandidate(url) {
  const path = url.pathname.toLowerCase();
  return path.endsWith('/') || !/\.[a-z0-9]{1,8}$/.test(path) || /\.(?:html?|xhtml)$/.test(path);
}

async function mapLimited(values, limit, fn) {
  const output = new Array(values.length);
  let next = 0;
  const worker = async () => {
    while (next < values.length) {
      const index = next++;
      output[index] = await fn(values[index], index);
    }
  };
  await Promise.all(Array.from({ length: Math.min(limit, values.length) }, worker));
  return output;
}

function mergeIdentity(inspections) {
  const merged = { names: [], addresses: [], corporateNumbers: [], phones: [] };
  for (const inspection of inspections) {
    for (const key of Object.keys(merged)) {
      for (const signal of inspection.identity[key] || []) {
        const value = typeof signal === 'string' ? signal : signal.value;
        if (!merged[key].some(existing => (typeof existing === 'string' ? existing : existing.value) === value)) {
          merged[key].push(signal);
        }
      }
    }
  }
  merged.primaryName = inspections.map(item => item.identity.primaryName).find(Boolean) || null;
  return merged;
}

function isIdentityPage(source, includeRoot = true) {
  try {
    const path = new URL(source).pathname.toLowerCase();
    return (includeRoot && path === '/')
      || /\/(?:company|corporate|profile|about|contact|access|legal|tokushoho)(?:\/|$)/.test(path);
  } catch { return false; }
}

function contentTypeAllowed(result, kind) {
  const type = String(result.headers?.get?.('content-type') || '').toLowerCase();
  if (!type) return true;
  return kind === 'page'
    ? /text\/html|application\/xhtml\+xml/.test(type)
    : /xml|text\/plain|text\/html/.test(type);
}

export async function discoverSite(options) {
  const origin = new URL(options.origin).origin;
  const maxPages = Math.max(1, Number(options.maxPages || 5));
  const maxSitemaps = Math.max(1, Number(options.maxSitemaps || 3));
  const fetchPage = options.fetchPage;
  const failures = [];
  const attempted = [];
  const fetchChecked = async (url, kind) => {
    attempted.push(url);
    try {
      const result = await fetchPage(url, kind);
      if (result.status < 200 || result.status >= 300) {
        failures.push({ url, reason: `http_${result.status}` });
        return null;
      }
      if (!contentTypeAllowed(result, kind)) {
        failures.push({ url, reason: 'unsupported_content_type' });
        return null;
      }
      if (result.truncated) failures.push({ url, reason: 'body_truncated' });
      return result;
    } catch (error) {
      failures.push({ url, reason: error?.code || 'fetch_failed' });
      return null;
    }
  };

  const rootUrl = `${origin}/`;
  const root = await fetchChecked(rootUrl, 'page');
  if (!root) {
    return {
      ok: false, rootFailure: failures[0]?.reason || 'fetch_failed', attempted, failures,
      pages: [], identity: { names: [], addresses: [], corporateNumbers: [], phones: [], primaryName: null },
      socialLinks: [], blogLinks: [], feedLinks: [], phones: [], coverage: { status: 'blocked', stop_reason: 'root_fetch_failed' },
    };
  }

  const inspections = [inspectHtml(root.text, rootUrl)];
  const [robots, defaultSitemap] = await Promise.all([
    fetchChecked(`${origin}/robots.txt`, 'support'),
    fetchChecked(`${origin}/sitemap.xml`, 'support'),
  ]);
  const robotsText = robots?.text || '';
  const sitemapQueue = robotsSitemaps(robotsText, origin)
    .filter(url => url !== `${origin}/sitemap.xml`).slice(0, maxSitemaps - 1);
  const sitemapTexts = defaultSitemap ? [defaultSitemap.text] : [];
  for (const sitemapUrl of sitemapQueue) {
    const result = await fetchChecked(sitemapUrl, 'support');
    if (result) sitemapTexts.push(result.text);
  }
  const childSitemaps = sitemapTexts.filter(text => /<sitemapindex\b/i.test(text))
    .flatMap(xmlLocations).filter(url => isSameSite(url, origin));
  for (const child of childSitemaps.slice(0, Math.max(0, maxSitemaps - sitemapTexts.length))) {
    const result = await fetchChecked(child, 'support');
    if (result) sitemapTexts.push(result.text);
  }
  const sitemapUrls = sitemapTexts.filter(text => /<urlset\b/i.test(text)).flatMap(xmlLocations)
    .map(value => normalizedUrl(value, origin)).filter(url => url && isSameSite(url.toString(), origin));

  const discovered = new Map();
  const addCandidate = (raw, source) => {
    const url = normalizedUrl(raw, origin);
    if (!url || !isSameSite(url.toString(), origin) || url.toString() === rootUrl || !isPageCandidate(url)) return;
    if (!robotsAllows(robotsText, url)) return;
    const key = url.toString();
    if (!discovered.has(key)) discovered.set(key, { url, source });
  };
  inspections[0].internalLinks.forEach(url => addCandidate(url, 'homepage'));
  sitemapUrls.forEach(url => addCandidate(url.toString(), 'sitemap'));
  ['/company/', '/about/', '/contact/', '/blog/', '/news/'].forEach(url => addCandidate(url, 'fallback'));

  const candidates = [...discovered.values()].sort((a, b) => {
    const score = item => pageScore(item.url) + (item.source === 'homepage' ? 15 : item.source === 'sitemap' ? 5 : -20);
    return score(b) - score(a) || a.url.toString().localeCompare(b.url.toString());
  });
  const selected = candidates.slice(0, maxPages - 1);
  const secondary = await mapLimited(selected, 3, async item => {
    const result = await fetchChecked(item.url.toString(), 'page');
    return result ? inspectHtml(result.text, item.url.toString()) : null;
  });
  inspections.push(...secondary.filter(Boolean));

  const unique = values => [...new Set(values)];
  const socialCandidates = [];
  inspections.flatMap(item => item.socialLinks).forEach(item => {
    const existing = socialCandidates.find(candidate => candidate.platform === item.platform && candidate.url === item.url);
    if (!existing) socialCandidates.push({ ...item, sources: [...item.sources], methods: [...item.methods] });
    else {
      item.sources.forEach(source => { if (!existing.sources.includes(source)) existing.sources.push(source); });
      item.methods.forEach(method => { if (!existing.methods.includes(method)) existing.methods.push(method); });
    }
  });
  const socialLinks = socialCandidates.filter(item =>
    item.methods.some(method => ['same_as', 'rel_me', 'twitter_site'].includes(method))
    || item.sources.some(source => isIdentityPage(source, false))
    || (item.sources.includes(rootUrl) && item.sources.length >= 2));
  const blogLinks = unique([
    ...inspections.flatMap(item => item.blogLinks),
    ...sitemapUrls.filter(isBlogUrl).map(url => url.toString()),
  ]);
  const feedLinks = unique(inspections.flatMap(item => item.feedLinks));
  const pages = inspections.map(item => item.pageUrl);
  const trustedInspections = inspections.filter(item => isIdentityPage(item.pageUrl));
  const phoneSources = new Map();
  for (const inspection of inspections) {
    for (const phone of inspection.phones) {
      const sources = phoneSources.get(phone) || [];
      if (!sources.includes(inspection.pageUrl)) sources.push(inspection.pageUrl);
      phoneSources.set(phone, sources);
    }
  }
  const phones = [...phoneSources].filter(([, sources]) =>
    sources.some(source => isIdentityPage(source)) || (sources.includes(rootUrl) && sources.length >= 2))
    .map(([phone]) => phone);
  const budgetExhausted = candidates.length > selected.length;
  const partial = failures.length > 0 || budgetExhausted;
  return {
    ok: true,
    attempted,
    failures,
    pages,
    identity: mergeIdentity(trustedInspections),
    socialLinks,
    blogLinks,
    feedLinks,
    phones,
    staff: trustedInspections.map(item => item.staff).find(Boolean) || null,
    placeholder: trustedInspections.some(item => item.placeholder),
    coverage: {
      status: partial ? 'partial' : 'covered',
      stop_reason: budgetExhausted ? 'page_budget_exhausted'
        : failures.length ? 'retrieval_failed' : 'required_sources_exhausted',
      pages_fetched: pages.length,
      pages_attempted: attempted.filter(url => !/\/(?:robots\.txt|sitemap[^/]*)$/i.test(new URL(url).pathname)).length,
      sitemap_checked: sitemapTexts.length > 0,
      failures,
    },
  };
}
