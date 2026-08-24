import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import {
  discoverSite,
  inspectHtml,
  robotsAllows,
} from '../functions/lib/site-discovery.js';

const result = (text, { status = 200, type = 'text/html; charset=utf-8', truncated = false } = {}) => ({
  status,
  text,
  truncated,
  headers: new Headers({ 'content-type': type }),
});

test('本番配信元のトップページからブログ導線を検出する', async () => {
  const [home, robots, sitemap] = await Promise.all([
    readFile(new URL('../index.html', import.meta.url), 'utf8'),
    readFile(new URL('../robots.txt', import.meta.url), 'utf8'),
    readFile(new URL('../sitemap.xml', import.meta.url), 'utf8'),
  ]);
  const fetched = await discoverSite({
    origin: 'https://ngraph.jp',
    maxPages: 2,
    fetchPage: async (url, kind) => {
      const path = new URL(url).pathname;
      if (path === '/') return result(home);
      if (path === '/robots.txt') return result(robots, { type: 'text/plain' });
      if (path === '/sitemap.xml') return result(sitemap, { type: 'application/xml' });
      return result('', { status: 404 });
    },
  });
  assert.equal(fetched.ok, true);
  assert.ok(fetched.blogLinks.some(url => new URL(url).pathname.startsWith('/blog')));
  assert.deepEqual(fetched.socialLinks, []);
});

test('HTTP 403本文をサイト本文として解析しない', async () => {
  const fetched = await discoverSite({
    origin: 'https://blocked.example',
    fetchPage: async () => result('<a href="/blog/">blog</a>', { status: 403 }),
  });
  assert.equal(fetched.ok, false);
  assert.equal(fetched.rootFailure, 'http_403');
  assert.deepEqual(fetched.blogLinks, []);
  assert.equal(fetched.coverage.status, 'blocked');
});

test('会社情報ページのJSON-LD sameAsと引用形式の違うSNSリンクを検出する', async () => {
  const pages = new Map([
    ['/', '<a href="/company/">会社概要</a>'],
    ['/robots.txt', 'User-agent: *\nAllow: /'],
    ['/sitemap.xml', '<urlset><url><loc>https://corp.example/company/</loc></url></urlset>'],
    ['/company/', `<script type="application/ld+json">{
      "@type":"Organization","url":"https://corp.example/",
      "sameAs":["https://x.com/corp_example","https://www.facebook.com/corp.example"]
    }</script><a href='https://instagram.com/corp.example'>Instagram</a>`],
  ]);
  const fetched = await discoverSite({
    origin: 'https://corp.example',
    fetchPage: async url => result(pages.get(new URL(url).pathname) || '', {
      status: pages.has(new URL(url).pathname) ? 200 : 404,
      type: new URL(url).pathname.endsWith('.xml') ? 'application/xml' : 'text/html',
    }),
  });
  assert.deepEqual(new Set(fetched.socialLinks.map(item => item.platform)),
    new Set(['X', 'Facebook', 'Instagram']));
});

test('外部リンクやシェア用URLを公式SNSとして採用しない', () => {
  const inspected = inspectHtml(`
    <a href="https://twitter.com/intent/tweet?url=https://corp.example">share</a>
    <a href="https://other.example/blog/">external blog</a>
  `, 'https://corp.example/');
  assert.deepEqual(inspected.socialLinks, []);
  assert.deepEqual(inspected.blogLinks, []);
});

test('TELで始まる一般文字列を電話番号にしない', () => {
  const inspected = inspectHtml('<p>TELes 偉人に相談</p><p>電話番号</p><p>NHG</p>', 'https://corp.example/');
  assert.deepEqual(inspected.phones, []);
});

test('ブログ本文で引用された第三者電話番号を会社の電話にしない', async () => {
  const pages = new Map([
    ['/', '<a href="/blog/report">記事</a>'],
    ['/robots.txt', 'User-agent: *\nAllow: /'],
    ['/sitemap.xml', '<urlset></urlset>'],
    ['/blog/report', '<p>取材先の電話番号</p><p>03-1234-5678</p>'],
  ]);
  const fetched = await discoverSite({
    origin: 'https://corp.example', maxPages: 2,
    fetchPage: async url => result(pages.get(new URL(url).pathname) || '', {
      status: pages.has(new URL(url).pathname) ? 200 : 404,
      type: new URL(url).pathname.endsWith('.xml') ? 'application/xml' : 'text/html',
    }),
  });
  assert.deepEqual(fetched.phones, []);
});

test('robotsのDisallowと、より具体的なAllowを適用する', () => {
  const robots = 'User-agent: *\nDisallow: /private/\nAllow: /private/public/';
  assert.equal(robotsAllows(robots, new URL('https://corp.example/private/report')), false);
  assert.equal(robotsAllows(robots, new URL('https://corp.example/private/public/info')), true);
});

test('画面の所感が未検出を不存在や取引忌避へ変換しない', async () => {
  const html = await readFile(new URL('../check/index.html', import.meta.url), 'utf8');
  assert.doesNotMatch(html, /電話番号を公開していない/);
  assert.doesNotMatch(html, /発信の導線が一切ない/);
  assert.match(html, /未検出は「存在しない」「安全」のどちらも意味しません/);
});

// 髙橋さんの明示決定（バッサリ書け・知らせなければ意味がない）。取得できた事実が3件重なった
// ときだけ出る助言で、未検出を取引忌避へ変換したものではない。文言を消す変更を通さない。
test('確認できた事実が重なったときの契約行動への助言は断言のまま残す', async () => {
  const html = await readFile(new URL('../check/index.html', import.meta.url), 'utf8');
  assert.match(html, /前払い・中途解約不可の契約に進むことは推奨できません/);
  assert.match(html, /sig\.length>=3/);
});
