import assert from 'node:assert/strict';

import { onRequestPost } from '../functions/api/kcheck.js';

const token = process.env.GBIZINFO_TOKEN;
if (!token) throw new Error('GBIZINFO_TOKEN is required');

const cases = [
  { q: 'https://jcs-company.com/', corporateNumber: '6220001027097', addressMatch: true, auto: true },
  // 同名法人16社かつサイト所在地と登記所在地が不一致。誤確定せず候補UIへ落とすのが正解。
  { q: 'https://k-stem.jp/', corporateNumber: '9230001020874', auto: false },
];

for (const expected of cases) {
  const request = new Request('https://ngraph.jp/api/kcheck', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ q: expected.q }),
  });
  const response = await onRequestPost({ request, env: { GBIZINFO_TOKEN: token } });
  assert.equal(response.status, 200);
  const result = await response.json();
  console.log(JSON.stringify({
    q: expected.q,
    name_guess: result.nameGuess,
    resolved_corporate_number: result.resolvedCorporate?.corporate_number || null,
    candidate_count: (result.candidates || []).length,
    target_in_candidates: (result.candidates || []).some(candidate =>
      candidate.corporate_number === expected.corporateNumber),
  }));
  if (expected.auto) {
    assert.equal(result.resolvedCorporate?.corporate_number, expected.corporateNumber, expected.q);
    assert.equal(result.resolvedCorporate?.address_match, expected.addressMatch, expected.q);
    assert.equal(result.candidates.length, 0, expected.q);
  } else {
    assert.equal(result.resolvedCorporate, undefined, expected.q);
    assert.ok(result.candidates.some(candidate => candidate.corporate_number === expected.corporateNumber), expected.q);
  }
  console.log(JSON.stringify({
    q: expected.q,
    corporate_number: result.resolvedCorporate?.corporate_number || null,
    address_match: result.resolvedCorporate?.address_match ?? null,
    candidate_ui_required: result.candidates.length > 0,
  }));
}

// v4（2026-10-19）の回帰。PRODUCT-SPEC-v4 §4 の不具合が戻っていないかを実データで見る。
const post = async q => {
  const request = new Request('https://ngraph.jp/api/kcheck', {
    method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ q }),
  });
  const response = await onRequestPost({ request, env: { GBIZINFO_TOKEN: token, INVOICE_API_ID: process.env.INVOICE_API_ID } });
  assert.equal(response.status, 200, q);
  return response.json();
};
const labels = result => (result.facts || []).map(fact => fact.label);

{
  // サービス欄の「対象 従業員20名ほどまで」を会社の人数にしない。ブログ・事例の個別ページを読まない。
  const result = await post('https://ngraph.jp/');
  assert.equal(result.resolvedCorporate?.corporate_number, '5210001020418');
  assert.ok(!labels(result).some(label => label.startsWith('従業員数（サイト')), 'ngraph.jp: 自称従業員数を拾った');
  const scope = result.facts.find(fact => fact.label === 'サイト内の確認範囲')?.source || '';
  assert.doesNotMatch(scope, /\/blog\/[^,／]+|\/cases\//, 'ngraph.jp: 記事・事例ページを読んだ');
  assert.ok(result.summary?.got?.length && result.summary?.actions?.length, 'ngraph.jp: 結論の行がない');
  console.log(JSON.stringify({ q: 'ngraph.jp', ok: true }));
}
{
  // title の「公式企業サイト」を社名に含めない。gBizINFO の 404（0件）を取得失敗にしない。
  const result = await post('https://www.toyota.co.jp/');
  assert.ok((result.candidates || []).some(candidate => candidate.corporate_number === '1180301018771')
    || result.resolvedCorporate?.corporate_number === '1180301018771', 'toyota: 登記の候補に出ない');
  assert.ok(!labels(result).includes('法人候補の照会'), 'toyota: 照会失敗になった');
  console.log(JSON.stringify({ q: 'toyota.co.jp', ok: true }));
}
{
  // 社名で候補が1社なら、選ばせずにそのまま調べる。
  const result = await post('株式会社勝木書店');
  assert.equal(result.mode, 'corp');
  assert.equal(result.corporate_number, '9210001000894');
  console.log(JSON.stringify({ q: '株式会社勝木書店', ok: true }));
}
{
  // 開けないサイトを「電話番号が無い」と言わない。
  const result = await post('https://no-such-company-zzqx.jp/');
  assert.ok(result.summary.missing.some(item => item.startsWith('サイトを開けなかった')));
  assert.ok(!result.summary.missing.some(item => item.includes('電話番号')));
  console.log(JSON.stringify({ q: 'no-such-company-zzqx.jp', ok: true }));
}
