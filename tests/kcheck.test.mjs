import assert from 'node:assert/strict';
import test from 'node:test';

import {
  extractSiteIdentity,
  gbizByName,
  normalizeCompanyName,
  resolveCorporateCandidate,
} from '../functions/api/kcheck.js';

test('gBizINFOの503を候補なしでなくprovider blockedとして返す', async () => {
  const result = await gbizByName('株式会社例示', 'test-token', async () => ({ status: 503, ok: false }));
  assert.deepEqual(result, {
    candidates: [], complete: false, status: 'blocked',
    stop_reason: 'provider_blocked', reason: 'http_503',
  });
});

test('gBizINFO token未設定を候補なしでなくprovider blockedとして返す', async () => {
  const result = await gbizByName('株式会社例示', '', async () => { throw new Error('must not call'); });
  assert.equal(result.status, 'blocked');
  assert.equal(result.reason, 'token_not_configured');
});

test('全角半角と法人格を除いて商号を照合する', () => {
  assert.equal(normalizeCompanyName('株式会社ＪＣＳ'), normalizeCompanyName('株式会社JCS'));
});

test('JCS型の会社名と所在地を抽出し、一意の法人へ自動確定する', () => {
  const identity = extractSiteIdentity(`
    <title>株式会社JCS｜中小企業の成長を支援</title>
    <dl><dt>会社名</dt><dd>株式会社JCS</dd>
    <dt>所在地</dt><dd>石川県金沢市西泉3-10 第一西田ビル2F</dd></dl>
  `);
  const resolved = resolveCorporateCandidate(identity, [
    { corporate_number: '1', name: '株式会社JCSコミュニケーションズ', location: '東京都千代田区1-1' },
    { corporate_number: '6220001027097', name: '株式会社ＪＣＳ', location: '石川県金沢市西泉3丁目10番地第一西田ビル201号室' },
  ]);
  assert.equal(resolved?.candidate.corporate_number, '6220001027097');
  assert.equal(resolved?.addressMatch, true);
  assert.deepEqual(resolved?.anchors, ['name', 'address']);
});

test('商号が一意でも所在地が違えば自動確定しない', () => {
  const identity = extractSiteIdentity(`
    <meta property="og:site_name" content="株式会社ステム">
    <p>所在地</p><p>石川県金沢市西泉3丁目54-1 2F</p>
  `);
  const resolved = resolveCorporateCandidate(identity, [
    { corporate_number: '9230001020874', name: '株式会社ステム', location: '富山県富山市奥田寿町21番6号' },
  ]);
  assert.equal(resolved, null);
});

test('同名法人が複数ある場合は所在地が一意に一致したときだけ自動確定する', () => {
  const identity = { names: ['株式会社同名'], addresses: ['東京都港区赤坂1-2-3'] };
  const candidates = [
    { corporate_number: '1', name: '株式会社同名', location: '大阪府大阪市北区1-2-3' },
    { corporate_number: '2', name: '株式会社同名', location: '東京都港区赤坂1丁目2番3号' },
  ];
  assert.equal(resolveCorporateCandidate(identity, candidates)?.candidate.corporate_number, '2');
  assert.equal(resolveCorporateCandidate({ ...identity, addresses: [] }, candidates), null);
});

test('部分一致候補だけでは自動確定しない', () => {
  const identity = { names: ['株式会社JCS'], addresses: [] };
  const candidates = [
    { corporate_number: '1', name: '株式会社JCSサービス', location: '東京都' },
  ];
  assert.equal(resolveCorporateCandidate(identity, candidates), null);
});

test('検索結果が上限で切れている場合は一意に見えても自動確定しない', () => {
  const identity = { names: ['株式会社JCS'], addresses: ['石川県金沢市西泉3-10'] };
  const candidates = [
    { corporate_number: '6220001027097', name: '株式会社JCS', location: '石川県金沢市西泉3丁目10番地' },
  ];
  assert.equal(resolveCorporateCandidate(identity, candidates, { complete: false }), null);
});
