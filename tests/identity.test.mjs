import assert from 'node:assert/strict';
import test from 'node:test';

import {
  addressMatches,
  extractSiteIdentity,
  identityValues,
  normalizeCompanyName,
  resolveCorporateCandidate,
} from '../functions/lib/identity.js';

test('本文中の第三者名をprimaryNameや確定アンカーに昇格させない', () => {
  const customers = Array.from({ length: 10 }, (_, index) =>
    `<li>導入企業 株式会社顧客${index}</li>`).join('');
  const identity = extractSiteIdentity(`<title>AI導入支援サービス</title><ul>${customers}</ul>`);
  assert.equal(identity.primaryName, null);
  assert.equal(resolveCorporateCandidate(identity, [
    { corporate_number: '1234567890123', name: '株式会社顧客0', location: '東京都港区1-2-3' },
  ]), null);
});

test('titleはサービス名でなく法人格を含む社名をprimaryNameにする', () => {
  const identity = extractSiteIdentity('<title>AI導入支援 | 株式会社例示</title>');
  assert.equal(identity.primaryName, '株式会社例示');
});

test('丁目番地号の省略は所在地一致にしない', () => {
  assert.equal(addressMatches('東京都港区赤坂1-2', '東京都港区赤坂1丁目2番3号'), false);
});

test('商号と所在地の独立アンカー2点でのみ自動確定する', () => {
  const candidate = { corporate_number: '1234567890123', name: '株式会社例示', location: '東京都港区赤坂1丁目2番3号' };
  const identity = extractSiteIdentity(`
    <dl><dt>会社名</dt><dd>株式会社例示</dd><dt>所在地</dt><dd>東京都港区赤坂1-2-3</dd></dl>
  `);
  assert.deepEqual(resolveCorporateCandidate(identity, [candidate])?.anchors, ['name', 'address']);
  assert.equal(resolveCorporateCandidate({ ...identity, addresses: [] }, [candidate]), null);
});

test('サイト記載の法人番号と商号で自動確定する', () => {
  const identity = extractSiteIdentity(`
    <dl><dt>会社名</dt><dd>株式会社例示</dd><dt>法人番号</dt><dd>1234567890123</dd></dl>
  `);
  const resolved = resolveCorporateCandidate(identity, [
    { corporate_number: '1234567890123', name: '株式会社例示', location: '東京都港区' },
  ]);
  assert.deepEqual(resolved?.anchors, ['name', 'corporate_number']);
});

test('JSON-LD identifierオブジェクトから法人番号を抽出する', () => {
  const identity = extractSiteIdentity(`
    <script type="application/ld+json">{"@type":"Organization","name":"株式会社例示","url":"https://example.com/","identifier":{"name":"法人番号","value":"1234567890123"}}</script>
  `, { pageUrl: 'https://example.com/' });
  assert.deepEqual(identityValues(identity.corporateNumbers), ['1234567890123']);
});

test('全角半角・異体字・ひらがなカタカナを正規化する', () => {
  assert.equal(normalizeCompanyName('株式会社髙﨑 ＡＩ'), normalizeCompanyName('株式会社高崎 AI'));
  assert.equal(normalizeCompanyName('株式会社カタカナ'), normalizeCompanyName('株式会社かたかな'));
});

test('外部URLを持つ第三者Organization JSON-LDを除外する', () => {
  const identity = extractSiteIdentity(`
    <script type="application/ld+json">{"@type":"Organization","name":"株式会社第三者","url":"https://third.example/"}</script>
    <meta property="og:site_name" content="株式会社本人">
  `, { pageUrl: 'https://owner.example/' });
  assert.equal(identity.primaryName, '株式会社本人');
  assert.equal(identityValues(identity.names).includes('株式会社第三者'), false);
});
