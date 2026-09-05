// ngraph.jp Worker: /api/* をFunctionsへ、その他は静的アセットへ
import { onRequestPost as kcheck } from './functions/api/kcheck.js';
import { onRequestPost as lead } from './functions/api/lead.js';
import { onRequestPost as ask } from './functions/api/ask.js';

export default {
  async fetch(request, env, ctx) {
    const { pathname } = new URL(request.url);
    if (pathname === '/api/kcheck') {
      if (request.method === 'POST') return kcheck({ request, env, waitUntil: ctx.waitUntil.bind(ctx) });
      return methodNotAllowed();
    }
    if (pathname === '/api/ask') {
      if (request.method === 'POST') return ask({ request, env });
      return methodNotAllowed();
    }
    if (pathname === '/api/lead') {
      if (request.method === 'POST') return lead({ request, env, waitUntil: ctx.waitUntil.bind(ctx) });
      return methodNotAllowed();
    }
    return injectJpWrap(await env.ASSETS.fetch(request));
  },
};

// 日本語の折返し（js/jp-wrap.js）を全HTMLの <head> 末尾に差し込む。
// 記事97本＋今後の記事にタグを書かずに済ませるため、配信時に付ける（2026-09-05）
const injectJpWrap = (res) => {
  const ct = res.headers.get('content-type') || '';
  if (!ct.includes('text/html')) return res;
  return new HTMLRewriter()
    .on('head', { element(el) { el.append('<script defer src="/js/jp-wrap.js?v=1"></script>', { html: true }); } })
    .transform(res);
};

const methodNotAllowed = () => new Response(JSON.stringify({ error: 'POSTのみ利用できます' }), {
  status: 405,
  headers: { 'content-type': 'application/json; charset=utf-8', allow: 'POST', 'cache-control': 'no-store' },
});
