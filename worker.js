// ngraph.jp Worker: /api/* をFunctionsへ、その他は静的アセットへ
import { onRequestPost as kcheck } from './functions/api/kcheck.js';
import { onRequestPost as lead } from './functions/api/lead.js';

export default {
  async fetch(request, env) {
    const { pathname } = new URL(request.url);
    if (request.method === 'POST' && pathname === '/api/kcheck') return kcheck({ request, env });
    if (request.method === 'POST' && pathname === '/api/lead') return lead({ request, env });
    return env.ASSETS.fetch(request);
  },
};
