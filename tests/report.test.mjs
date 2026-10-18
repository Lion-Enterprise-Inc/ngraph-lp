import assert from 'node:assert/strict';
import test from 'node:test';

import { cleanSiteName, extractSiteIdentity } from '../functions/lib/identity.js';
import { buildSummary, sectionsOf } from '../functions/lib/report.js';
import { isArticlePage, pageScore } from '../functions/lib/site-discovery.js';
import { registrableDomain } from '../functions/api/kcheck.js';

// 2026-10-19 実害：ngraph.jp のサービス欄「対象 従業員20名ほどまで」を自社の人数として確認済にした。
test('対象顧客の規模を会社の従業員数にしない', () => {
  assert.equal(extractSiteIdentity('<span><i>対象</i>従業員20名ほどまで</span>').staff ?? null, null);
  assert.equal(extractSiteIdentity('<p>従業員100名以上の企業に</p>').staff ?? null, null);
  assert.equal(extractSiteIdentity('<dl><dt>従業員数</dt><dd>35名（2026年4月現在）</dd></dl>').staff, '35名(2026年4月現在)');
});

test('サイト名の「公式企業サイト」を社名から落とす', () => {
  assert.equal(cleanSiteName('トヨタ自動車株式会社 公式企業サイト'), 'トヨタ自動車株式会社');
  assert.equal(cleanSiteName('株式会社サンプル オフィシャルサイト'), '株式会社サンプル');
  assert.equal(cleanSiteName('株式会社サンプル'), '株式会社サンプル');
});

test('記事・事例の個別ページを読まず、会社概要を優先する', () => {
  assert.equal(isArticlePage(new URL('https://a.jp/blog/20260804-company-brain')), true);
  assert.equal(isArticlePage(new URL('https://a.jp/cases/the-coca-cola-company/')), true);
  assert.equal(isArticlePage(new URL('https://a.jp/company/profile/')), false);
  assert.ok(pageScore(new URL('https://a.jp/company')) > pageScore(new URL('https://a.jp/en/company')));
  assert.equal(pageScore(new URL('https://a.jp/company-brain-abc')), 0);
});

test('DNS は登録ドメインで引く', () => {
  assert.equal(registrableDomain('www.toyota.co.jp'), 'toyota.co.jp');
  assert.equal(registrableDomain('www.example.com'), 'example.com');
  assert.equal(registrableDomain('ngraph.jp'), 'ngraph.jp');
});

test('取得を断られたサイトを「無いサイト」や「電話番号なし」と書かない', () => {
  const refused = buildSummary([], { mode: 'site', siteFailed: true, siteFailReason: 'http_403' });
  assert.match(refused.missing[0], /自動の取得を断った/);
  assert.ok(!refused.missing.some(item => item.includes('電話番号')));
  assert.match(refused.actions[0], /ブラウザで/);
  const gone = buildSummary([], { mode: 'site', siteFailed: true, siteFailReason: 'dns_failed' });
  assert.match(gone.missing[0], /サイトを開けなかった/);
});

test('公的な活動が全部0件なら1行にまとめる', () => {
  const zero = label => ({ label, value: '0件', status: '確認済', source: 'gBizINFO' });
  const sections = sectionsOf(['届出・認定', '補助金交付', '公共調達', '表彰'].map(zero));
  assert.equal(sections[0].rows.length, 1);
});
