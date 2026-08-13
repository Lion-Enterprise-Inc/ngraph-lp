import assert from 'node:assert/strict';
import test from 'node:test';

import {
  createCoverageLedger,
  evaluateCoverageStop,
  RESEARCH_AREAS,
  validateEvidence,
} from '../functions/lib/evidence.js';

const ledger = [{
  url: 'https://example.com/company',
  raw_snapshot_key: 'raw/job/page-1',
  raw_text: '会社概要 会社名 株式会社例示 所在地 東京都港区',
}];

const evidence = {
  id: 'e1',
  subject_id: 'subject-1',
  area: 'identity',
  claim: '商号',
  value: '株式会社例示',
  status: 'verified',
  source_url: 'https://example.com/company',
  source_type: 'official_site',
  source_title: '会社概要',
  publisher: '株式会社例示',
  retrieved_at: '2026-08-13T00:00:00.000Z',
  published_at: null,
  quote: '会社名 株式会社例示',
  identity_match: 'exact',
  confidence: 'high',
  contradicts: [],
  evidence_grade: 'fetched',
  raw_snapshot_key: 'raw/job/page-1',
};

test('取得台帳・保存原文・snapshot keyが一致する証拠だけverifiedにする', () => {
  assert.deepEqual(validateEvidence(evidence, ledger), { ok: true, errors: [] });
});

test('取得していないURLと原文にないquoteを拒否する', () => {
  assert.ok(validateEvidence({ ...evidence, source_url: 'https://fake.example/' }, ledger)
    .errors.includes('source_url:not_in_fetch_ledger'));
  assert.ok(validateEvidence({ ...evidence, quote: '存在しない引用' }, ledger)
    .errors.includes('quote:not_in_snapshot'));
});

test('検索snippetをverified証拠に昇格できない', () => {
  const result = validateEvidence({ ...evidence, evidence_grade: 'snippet_only' }, ledger);
  assert.equal(result.ok, false);
  assert.ok(result.errors.includes('verified:fetched_grade_required'));
  assert.ok(result.errors.includes('snippet_only:cannot_be_verified'));
});

test('retrieved_atと取得台帳側snapshot keyを必須にする', () => {
  assert.ok(validateEvidence({ ...evidence, retrieved_at: '' }, ledger).errors.includes('retrieved_at:required'));
  const withoutSnapshot = [{ ...ledger[0], raw_snapshot_key: '' }];
  assert.ok(validateEvidence(evidence, withoutSnapshot).errors.includes('fetch_ledger:raw_snapshot_key_required'));
});

test('Coverage台帳は12領域を一意に作る', () => {
  const coverage = createCoverageLedger();
  assert.equal(coverage.length, 12);
  assert.deepEqual(coverage.map(item => item.area), RESEARCH_AREAS);
  assert.ok(coverage.every(item => item.required && item.status === 'pending'));
});

test('必須ソース完了・予算0・新規host停滞を決定的に停止する', () => {
  assert.deepEqual(evaluateCoverageStop({
    required_sources: ['official', 'site'],
    source_states: { official: 'covered', site: 'not_found' },
  }), { stop: true, reason: 'required_sources_exhausted' });
  assert.deepEqual(evaluateCoverageStop({ queries_used: 0, query_budget: 0 }),
    { stop: true, reason: 'area_budget_exhausted' });
  assert.deepEqual(evaluateCoverageStop({
    round_source_urls: [
      ['https://a.example/1'],
      ['https://a.example/2'],
      ['https://a.example/3'],
    ],
    stagnation_rounds: 2,
  }), { stop: true, reason: 'no_new_source_hosts' });
});
