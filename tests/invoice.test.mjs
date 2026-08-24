import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import { invoiceChecks } from '../functions/api/kcheck.js';
import { lookupInvoiceRegistration, registrationNumberFor } from '../functions/lib/invoice.js';

// 仕様書（適格請求書発行事業者公表システムWeb-API機能 Ver.1.0）の例示データ。
const SAMPLE = '8040001999011';
const APP_ID = 'test-app-id';

const respond = (body, init = {}) => async () => ({
  ok: init.ok ?? true,
  status: init.status ?? 200,
  json: async () => body,
});

const announcement = (over = {}) => ({
  sequenceNumber: '1',
  registratedNumber: `T${SAMPLE}`,
  process: '01',
  correct: '0',
  kind: '2',
  country: '1',
  latest: '1',
  registrationDate: '2023-10-01',
  updateDate: '2021-11-01',
  disposalDate: '',
  expireDate: '',
  address: '北海道札幌市北区北七条西１０丁目',
  kana: '',
  name: '国税インボイス公表',
  tradeName: '',
  ...over,
});

const payload = (list, lastUpdateDate = '2026-08-21') => ({
  lastUpdateDate, count: String(list.length), divideNumber: '1', divideSize: '1', announcement: list,
});

test('法人番号13桁から登録番号を組み立て、それ以外は組み立てない', () => {
  assert.equal(registrationNumberFor(SAMPLE), `T${SAMPLE}`);
  assert.equal(registrationNumberFor(`T${SAMPLE}`), `T${SAMPLE}`);
  assert.equal(registrationNumberFor('123'), null);
  assert.equal(registrationNumberFor(null), null);
});

test('登録番号・登録年月日・公表名称・所在地を事実にする', async () => {
  const { facts, result } = await invoiceChecks(SAMPLE, APP_ID, null,
    respond(payload([announcement()])));
  assert.equal(result.registered, true);
  assert.equal(result.entry.active, true);
  const registration = facts.find(f => f.label === 'インボイス登録（適格請求書発行事業者）');
  assert.equal(registration.status, '確認済');
  assert.match(registration.value, /登録あり.*T8040001999011/);
  assert.match(registration.source, /2026-08-21 時点/);
  assert.equal(facts.find(f => f.label === 'インボイス登録年月日').value, '2023-10-01');
  assert.equal(facts.find(f => f.label === '公表されている名称（インボイス）').value, '国税インボイス公表');
});

test('失効・取消の年月日を状態として出す', async () => {
  const expired = await invoiceChecks(SAMPLE, APP_ID, null,
    respond(payload([announcement({ expireDate: '2024-11-01' })])));
  assert.match(expired.facts[0].value, /登録失効（失効年月日 2024-11-01）/);
  assert.equal(expired.result.entry.active, false);

  const disposed = await invoiceChecks(SAMPLE, APP_ID, null,
    respond(payload([announcement({ disposalDate: '2025-03-31' })])));
  assert.match(disposed.facts[0].value, /登録取消（取消年月日 2025-03-31）/);
  assert.equal(disposed.result.entry.active, false);
});

test('件数0は「登録なし」として確定し、免税事業者があり得ることを添える', async () => {
  const { facts, result } = await invoiceChecks(SAMPLE, APP_ID, null, respond(payload([])));
  assert.equal(result.registered, false);
  assert.equal(facts[0].status, '確認済');
  assert.match(facts[0].value, /登録なし/);
  assert.match(facts[0].value, /免税事業者/);
});

test('アプリケーションID未設定を「登録なし」に変換しない', async () => {
  const { facts, result } = await invoiceChecks(SAMPLE, '', null,
    async () => { throw new Error('must not call'); });
  assert.equal(result.status, 'blocked');
  assert.equal(result.stop_reason, 'app_id_not_configured');
  assert.equal(result.registered, null);
  assert.equal(facts[0].status, '取得失敗');
  assert.match(facts[0].value, /登録が無いとは判断していません/);
});

test('HTTPエラー・壊れた応答・ネットワーク断はいずれもblockedにする', async () => {
  const cases = [
    [respond({}, { ok: false, status: 503 }), 'http_503'],
    [respond({ count: '1' }), 'invalid_response'],
    [async () => { throw new Error('boom'); }, 'network_error'],
  ];
  for (const [fetchImpl, stop] of cases) {
    const result = await lookupInvoiceRegistration(SAMPLE, APP_ID, fetchImpl);
    assert.equal(result.status, 'blocked');
    assert.equal(result.stop_reason, stop);
    assert.equal(result.registered, null);
  }
});

test('照会した番号と違う登録番号だけが返った応答は採用しない', async () => {
  const result = await lookupInvoiceRegistration(SAMPLE, APP_ID,
    respond(payload([announcement({ registratedNumber: 'T9999999999999' })])));
  assert.equal(result.status, 'blocked');
  assert.equal(result.stop_reason, 'number_not_in_response');
  assert.equal(result.entry, null);
});

test('照会URLはJSON形式・履歴なしで、アプリケーションIDをクエリに載せる', async () => {
  let requested = null;
  await lookupInvoiceRegistration(SAMPLE, 'id with space', async url => {
    requested = url;
    return { ok: true, status: 200, json: async () => payload([]) };
  });
  assert.match(requested, /^https:\/\/web-api\.invoice-kohyo\.nta\.go\.jp\/1\/num\?/);
  assert.match(requested, /id=id%20with%20space/);
  assert.match(requested, /number=T8040001999011/);
  assert.match(requested, /type=21/);
  assert.match(requested, /history=0/);
});

// UAを付けずに投げると国税庁が403を返す。WorkersのfetchはUAを付けないので、
// これが抜けると本番だけが取得失敗になり、ローカルでは再現しない。
test('名乗り（User-Agent）を付けて照会する', async () => {
  let headers = null;
  await lookupInvoiceRegistration(SAMPLE, APP_ID, async (_url, init) => {
    headers = init.headers;
    return { ok: true, status: 200, json: async () => payload([]) };
  });
  assert.match(headers['User-Agent'], /^NGraph-vendor-check\/[\d.]+ \(\+https:\/\/ngraph\.jp\//);
});

test('公表情報と登記の照合は全角半角・住所表記の差を吸収する', async () => {
  const { facts } = await invoiceChecks(SAMPLE, APP_ID, {
    corporate_number: SAMPLE,
    name: '国税インボイス公表',
    location: '北海道札幌市北区北7丁目西10-1',
  }, respond(payload([announcement({
    name: '国税インボイス公表', address: '北海道札幌市北区北七条西１０丁目１番地',
  })])));
  const match = facts.find(f => f.label === 'インボイス公表情報と登記の照合');
  assert.equal(match.status, '確認済');
  assert.match(match.value, /商号は一致/);
});

test('照合できないときは断定せず、公表と登記の両方の値を並べる', async () => {
  const { facts } = await invoiceChecks(SAMPLE, APP_ID, {
    corporate_number: SAMPLE, name: '株式会社別名', location: '東京都千代田区1-1-1',
  }, respond(payload([announcement()])));
  const match = facts.find(f => f.label === 'インボイス公表情報と登記の照合');
  assert.match(match.value, /商号は一致を確認できず（公表: 国税インボイス公表 ／ 登記: 株式会社別名）/);
  assert.match(match.source, /更新時期の差でも不一致は生じます/);
});

test('画面は取消・失効を確認事項として拾い、手動確認の案内を原本確認へ置き換えている', async () => {
  const html = await readFile(new URL('../check/index.html', import.meta.url), 'utf8');
  assert.match(html, /登録取消\|登録失効/);
  assert.match(html, /インボイス登録の原本を国税庁の公表サイトで確認する/);
  assert.doesNotMatch(html, /インボイス登録を確認する（国税庁/);
});

test('登記情報が取れていないときは照合の事実を作らない', async () => {
  const { facts } = await invoiceChecks(SAMPLE, APP_ID, null, respond(payload([announcement()])));
  assert.equal(facts.find(f => f.label === 'インボイス公表情報と登記の照合'), undefined);
});
