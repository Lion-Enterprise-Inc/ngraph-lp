// URL入力・検索結果の取得を1か所で防御する。
// private/loopback/link-local/metadata IP、危険なredirect、無期限body読み取りを拒否する。

const DOH = 'https://cloudflare-dns.com/dns-query';
const DEFAULT_UA = 'Mozilla/5.0 (compatible; NGraphCheck/2.0; +https://ngraph.jp/check/)';

export class SafeFetchError extends Error {
  constructor(code, message, details = {}) {
    super(message);
    this.name = 'SafeFetchError';
    this.code = code;
    this.details = details;
  }
}

function ipv4Parts(value) {
  const parts = String(value || '').split('.');
  if (parts.length !== 4 || parts.some(part => !/^\d{1,3}$/.test(part))) return null;
  const numbers = parts.map(Number);
  return numbers.every(part => part >= 0 && part <= 255) ? numbers : null;
}

function isBlockedIpv4(value) {
  const parts = ipv4Parts(value);
  if (!parts) return false;
  const [a, b, c] = parts;
  return a === 0
    || a === 10
    || a === 127
    || (a === 100 && b >= 64 && b <= 127)
    || (a === 169 && b === 254)
    || (a === 172 && b >= 16 && b <= 31)
    || (a === 192 && b === 0 && c === 0)
    || (a === 192 && b === 0 && c === 2)
    || (a === 192 && b === 168)
    || (a === 198 && (b === 18 || b === 19))
    || (a === 198 && b === 51 && c === 100)
    || (a === 203 && b === 0 && c === 113)
    || a >= 224;
}

function isBlockedIpv6(value) {
  const address = String(value || '').toLowerCase().replace(/^\[|\]$/g, '').split('%')[0];
  if (!address.includes(':')) return false;
  if (address === '::' || address === '::1') return true;
  const mapped = address.match(/(?:^|:)ffff:(\d+\.\d+\.\d+\.\d+)$/);
  if (mapped) return isBlockedIpv4(mapped[1]);
  const groups = expandIpv6(address);
  if (groups) {
    // IPv4-mapped/compatible IPv6は末尾32bitをIPv4として再判定する。
    // 例: ::ffff:7f00:1 / ::ffff:127.0.0.1 / ::7f00:1
    const mappedPrefix = groups.slice(0, 5).every(group => group === 0) && groups[5] === 0xffff;
    const compatiblePrefix = groups.slice(0, 6).every(group => group === 0);
    if (mappedPrefix || compatiblePrefix) {
      const ipv4 = `${groups[6] >> 8}.${groups[6] & 0xff}.${groups[7] >> 8}.${groups[7] & 0xff}`;
      if (isBlockedIpv4(ipv4)) return true;
    }
  }
  const first = Number.parseInt(address.split(':')[0] || '0', 16);
  return (first & 0xfe00) === 0xfc00 // unique local fc00::/7
    || (first & 0xffc0) === 0xfe80 // link-local fe80::/10
    || (first & 0xff00) === 0xff00 // multicast ff00::/8
    || address.startsWith('2001:db8:'); // documentation range
}

function expandIpv6(value) {
  let address = value;
  const dotted = address.match(/(\d+\.\d+\.\d+\.\d+)$/);
  if (dotted) {
    const parts = ipv4Parts(dotted[1]);
    if (!parts) return null;
    address = address.slice(0, -dotted[1].length)
      + `${((parts[0] << 8) | parts[1]).toString(16)}:${((parts[2] << 8) | parts[3]).toString(16)}`;
  }
  if ((address.match(/::/g) || []).length > 1) return null;
  const [leftRaw, rightRaw] = address.split('::');
  const left = leftRaw ? leftRaw.split(':') : [];
  const right = rightRaw ? rightRaw.split(':') : [];
  if ([...left, ...right].some(group => !/^[0-9a-f]{1,4}$/.test(group))) return null;
  const missing = 8 - left.length - right.length;
  if (address.includes('::') ? missing < 1 : missing !== 0) return null;
  return [...left, ...Array(missing).fill('0'), ...right].map(group => Number.parseInt(group, 16));
}

export function isBlockedAddress(value) {
  return isBlockedIpv4(value) || isBlockedIpv6(value);
}

function isIpLiteral(value) {
  return Boolean(ipv4Parts(value) || String(value || '').includes(':'));
}

async function parseDoh(response) {
  if (!response.ok) throw new SafeFetchError('dns_resolution_failed', `DNS lookup failed (${response.status})`);
  const payload = await response.json();
  return (payload.Answer || [])
    .filter(answer => answer.type === 1 || answer.type === 28)
    .map(answer => String(answer.data || '').replace(/^\[|\]$/g, ''))
    .filter(Boolean);
}

export async function resolveHostWithDoh(hostname, options = {}) {
  const fetchImpl = options.fetchImpl || globalThis.fetch;
  const headers = { accept: 'application/dns-json' };
  const request = type => fetchImpl(`${DOH}?name=${encodeURIComponent(hostname)}&type=${type}`,
    { headers, signal: options.signal });
  const settled = await Promise.allSettled([request('A'), request('AAAA')]);
  const addresses = [];
  for (const item of settled) {
    if (item.status === 'fulfilled') {
      try { addresses.push(...await parseDoh(item.value)); } catch { /* 片方が失敗しても他方を検査する */ }
    }
  }
  if (!addresses.length) throw new SafeFetchError('dns_resolution_failed', 'DNS returned no public address');
  return [...new Set(addresses)];
}

function normalizeUrl(rawUrl) {
  let url;
  try {
    url = new URL(rawUrl);
  } catch {
    throw new SafeFetchError('invalid_url', 'URLを解釈できません');
  }
  if (url.protocol !== 'http:' && url.protocol !== 'https:') {
    throw new SafeFetchError('invalid_protocol', 'HTTP/HTTPS以外は取得できません');
  }
  if (url.username || url.password) {
    throw new SafeFetchError('credentials_forbidden', '認証情報を含むURLは取得できません');
  }
  url.hash = '';
  return url;
}

async function withDeadline(promise, deadlineAt, controller) {
  const remaining = deadlineAt - Date.now();
  if (remaining <= 0) {
    controller.abort();
    throw new SafeFetchError('deadline_exceeded', '取得期限を超えました');
  }
  let timer;
  try {
    return await Promise.race([
      promise,
      new Promise((_, reject) => {
        timer = setTimeout(() => {
          controller.abort();
          reject(new SafeFetchError('deadline_exceeded', '取得期限を超えました'));
        }, remaining);
      }),
    ]);
  } finally {
    clearTimeout(timer);
  }
}

async function assertPublicDestination(url, options) {
  const hostname = url.hostname.toLowerCase().replace(/^\[|\]$/g, '').replace(/\.$/, '');
  if (!hostname || hostname === 'localhost' || hostname.endsWith('.localhost') || !hostname.includes('.') && !hostname.includes(':')) {
    throw new SafeFetchError('private_destination', '公開ホストではありません', { hostname });
  }
  if (isIpLiteral(hostname)) {
    if (isBlockedAddress(hostname)) {
      throw new SafeFetchError('private_destination', '非公開IPへの接続を拒否しました', { hostname });
    }
    return [hostname];
  }

  const addresses = await withDeadline(
    Promise.resolve(options.resolveHost(hostname, { signal: options.controller.signal })),
    options.deadlineAt,
    options.controller,
  );
  if (!Array.isArray(addresses) || !addresses.length) {
    throw new SafeFetchError('dns_resolution_failed', 'DNSで接続先を確認できません', { hostname });
  }
  const blocked = addresses.find(isBlockedAddress);
  if (blocked) {
    throw new SafeFetchError('private_destination', 'DNSが非公開IPを返したため接続を拒否しました',
      { hostname, address: blocked });
  }
  return addresses;
}

function concat(chunks, total) {
  const output = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    output.set(chunk, offset);
    offset += chunk.length;
  }
  return output;
}

async function readBody(response, options) {
  if (!response.body) return { text: '', bytes: 0, truncated: false };
  const reader = response.body.getReader();
  const chunks = [];
  let total = 0;
  let truncated = false;
  try {
    while (true) {
      const { done, value } = await withDeadline(reader.read(), options.deadlineAt, options.controller);
      if (done) break;
      const bytes = value instanceof Uint8Array ? value : new Uint8Array(value);
      const remaining = options.maxBytes - total;
      if (bytes.length > remaining) {
        if (remaining > 0) chunks.push(bytes.slice(0, remaining));
        total += Math.max(remaining, 0);
        truncated = true;
        break;
      }
      chunks.push(bytes);
      total += bytes.length;
      if (total === options.maxBytes) {
        truncated = true;
        break;
      }
    }
  } finally {
    if (truncated || options.controller.signal.aborted) await reader.cancel().catch(() => {});
  }
  return {
    text: new TextDecoder('utf-8', { fatal: false }).decode(concat(chunks, total)),
    bytes: total,
    truncated,
  };
}

export async function safeFetch(rawUrl, options = {}) {
  const fetchImpl = options.fetchImpl || globalThis.fetch;
  const controller = new AbortController();
  const deadlineMs = Math.max(1, Number(options.deadlineMs || 8000));
  const maxBytes = Math.max(1, Number(options.maxBytes || 400000));
  const maxRedirects = Math.max(0, Number(options.maxRedirects ?? 3));
  const deadlineAt = Date.now() + deadlineMs;
  const resolveHost = options.resolveHost
    || ((hostname, resolverOptions) => resolveHostWithDoh(hostname, resolverOptions));
  const common = { controller, deadlineAt, maxBytes, resolveHost };
  const fetchedUrls = [];
  let url = normalizeUrl(rawUrl);

  for (let redirects = 0; ; redirects++) {
    await assertPublicDestination(url, common);
    fetchedUrls.push(url.toString());
    let response;
    try {
      response = await withDeadline(fetchImpl(url.toString(), {
        headers: { 'User-Agent': options.userAgent || DEFAULT_UA },
        redirect: 'manual',
        signal: controller.signal,
      }), deadlineAt, controller);
    } catch (error) {
      if (error instanceof SafeFetchError) throw error;
      throw new SafeFetchError('fetch_failed', 'URLの取得に失敗しました', { cause: String(error) });
    }

    if ([301, 302, 303, 307, 308].includes(response.status)) {
      if (redirects >= maxRedirects) {
        throw new SafeFetchError('too_many_redirects', 'redirect上限を超えました');
      }
      const location = response.headers.get('location');
      if (!location) throw new SafeFetchError('invalid_redirect', 'redirect先がありません');
      url = normalizeUrl(new URL(location, url).toString());
      continue;
    }

    const body = await readBody(response, common);
    return {
      status: response.status,
      url: url.toString(),
      headers: response.headers,
      fetchedUrls,
      ...body,
    };
  }
}
