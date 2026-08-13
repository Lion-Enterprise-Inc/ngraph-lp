// PDFダウンロード前のメールアドレス取得。KVバインディング「LEADS」に保存。
// KV未設定でも利用者を止めない（fail-open）が、stored:false を返して検知可能にする。
export async function onRequestPost(context) {
  let body;
  try { body = await context.request.json(); } catch { return json({ ok: false }, 400); }
  const email = String(body.email || '').trim().slice(0, 200);
  const q = String(body.q || '').trim().slice(0, 200);
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return json({ ok: false, error: 'メールアドレスの形式を確認してください' }, 400);
  let stored = false;
  if (context.env.LEADS) {
    const ip = context.request.headers.get('cf-connecting-ip') || 'x';
    const rk = `rl_lead_${ip}_${new Date().toISOString().slice(0, 13)}`;
    const n = parseInt(await context.env.LEADS.get(rk) || '0', 10) + 1;
    await context.env.LEADS.put(rk, String(n), { expirationTtl: 3900 });
    if (n > 5) return json({ ok: false, error: '送信回数の上限に達しました' }, 429);
    try {
      const key = `${new Date().toISOString()}_${crypto.randomUUID().slice(0, 8)}`;
      await context.env.LEADS.put(key, JSON.stringify({ email, q, ua: context.request.headers.get('user-agent') || '' }), { expirationTtl: 15552000 });  // 180日で自動削除
      stored = true;
    } catch { /* fail-open */ }
  }
  return json({ ok: true, stored });
}
const json = (o, s = 200) => new Response(JSON.stringify(o), {
  status: s, headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' },
});
