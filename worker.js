// ngraph.jp Worker: /api/* をFunctionsへ、その他は静的アセットへ
import { onRequestPost as kcheck } from './functions/api/kcheck.js';
import { onRequestPost as lead } from './functions/api/lead.js';

export default {
  async fetch(request, env, ctx) {
    const { pathname } = new URL(request.url);
    if (pathname === '/api/kcheck') {
      if (request.method === 'POST') return kcheck({ request, env, waitUntil: ctx.waitUntil.bind(ctx) });
      return methodNotAllowed();
    }
    if (pathname === '/api/lead') {
      if (request.method === 'POST') return lead({ request, env, waitUntil: ctx.waitUntil.bind(ctx) });
      return methodNotAllowed();
    }
    return env.ASSETS.fetch(request);
  },
};

const methodNotAllowed = () => new Response(JSON.stringify({ error: 'POSTのみ利用できます' }), {
  status: 405,
  headers: { 'content-type': 'application/json; charset=utf-8', allow: 'POST', 'cache-control': 'no-store' },
});
