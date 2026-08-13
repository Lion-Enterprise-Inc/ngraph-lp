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
    try {
      const key = `${new Date().toISOString()}_${crypto.randomUUID().slice(0, 8)}`;
      await context.env.LEADS.put(key, JSON.stringify({ email, q, ua: context.request.headers.get('user-agent') || '' }));
      stored = true;
    } catch { /* fail-open */ }
  }
  return json({ ok: true, stored });
}
const json = (o, s = 200) => new Response(JSON.stringify(o), {
  status: s, headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' },
});
