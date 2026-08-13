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
