// Evidence / Coverage の決定的な契約。
// LLMの自己申告ではなく、取得台帳と保存原文に照らして証拠の真正性を検証する。

export const RESEARCH_AREAS = Object.freeze([
  'identity', 'people', 'contact', 'public', 'operations', 'workforce',
  'social', 'domain', 'activity', 'reputation', 'history', 'contract',
]);

export const EVIDENCE_STATUSES = Object.freeze([
  'verified', 'self_claimed', 'conflicting', 'not_found',
  'retrieval_failed', 'not_applicable', 'human_required',
]);

export const COVERAGE_STATUSES = Object.freeze([
  'pending', 'covered', 'partial', 'blocked', 'not_applicable',
]);

const SOURCE_TYPES = new Set([
  'official_api', 'official_site', 'government', 'news', 'social',
  'directory', 'submitted_document', 'other',
]);
const IDENTITY_MATCHES = new Set(['exact', 'strong', 'weak', 'unknown']);
const CONFIDENCE = new Set(['high', 'medium', 'low']);
const EVIDENCE_GRADES = new Set(['fetched', 'snippet_only']);
const EVIDENCE_REQUIRED_STATUSES = new Set(['verified', 'self_claimed', 'conflicting']);
const TERMINAL_SOURCE_STATES = new Set([
  'covered', 'not_found', 'blocked', 'not_applicable', 'human_required', 'retrieval_failed',
]);

function canonicalUrl(value) {
  try {
    const url = new URL(value);
    url.hash = '';
    if (url.protocol !== 'http:' && url.protocol !== 'https:' && url.protocol !== 'urn:') return null;
    return url.toString();
  } catch {
    return null;
  }
}

export function normalizeEvidenceText(value) {
  return String(value || '').normalize('NFKC').replace(/\s+/g, ' ').trim();
}

function ledgerByUrl(fetchLedger) {
  const output = new Map();
  const entries = fetchLedger instanceof Map ? [...fetchLedger.values()] : (fetchLedger || []);
  for (const entry of entries) {
    const url = canonicalUrl(entry?.url || entry?.source_url);
    if (url) output.set(url, entry);
  }
  return output;
}

function requiredString(item, key, errors) {
  if (!String(item?.[key] || '').trim()) errors.push(`${key}:required`);
}

export function validateEvidence(item, fetchLedger = []) {
  const errors = [];
  requiredString(item, 'id', errors);
  requiredString(item, 'subject_id', errors);
  requiredString(item, 'claim', errors);
  if (!RESEARCH_AREAS.includes(item?.area)) errors.push('area:invalid');
  if (!EVIDENCE_STATUSES.includes(item?.status)) errors.push('status:invalid');
  if (!SOURCE_TYPES.has(item?.source_type)) errors.push('source_type:invalid');
  if (!IDENTITY_MATCHES.has(item?.identity_match)) errors.push('identity_match:invalid');
  if (!CONFIDENCE.has(item?.confidence)) errors.push('confidence:invalid');
  if (!EVIDENCE_GRADES.has(item?.evidence_grade)) errors.push('evidence_grade:invalid');
  if (!Array.isArray(item?.contradicts)) errors.push('contradicts:array_required');
  requiredString(item, 'retrieved_at', errors);
  if (item?.retrieved_at && Number.isNaN(Date.parse(item.retrieved_at))) errors.push('retrieved_at:invalid');
  if (item?.published_at != null && Number.isNaN(Date.parse(item.published_at))) errors.push('published_at:invalid');

  const sourceUrl = canonicalUrl(item?.source_url);
  const ledger = ledgerByUrl(fetchLedger);
  const snapshot = sourceUrl ? ledger.get(sourceUrl) : null;
  if (EVIDENCE_REQUIRED_STATUSES.has(item?.status) && !sourceUrl) errors.push('source_url:required');
  if (sourceUrl && !snapshot) errors.push('source_url:not_in_fetch_ledger');

  if (item?.evidence_grade === 'fetched') {
    requiredString(item, 'raw_snapshot_key', errors);
    if (snapshot && !String(snapshot.raw_snapshot_key || '').trim()) {
      errors.push('fetch_ledger:raw_snapshot_key_required');
    }
    if (snapshot?.raw_snapshot_key && snapshot.raw_snapshot_key !== item.raw_snapshot_key) {
      errors.push('raw_snapshot_key:mismatch');
    }
  }

  if (item?.status === 'verified') {
    if (item?.evidence_grade !== 'fetched') errors.push('verified:fetched_grade_required');
    requiredString(item, 'quote', errors);
    const quote = normalizeEvidenceText(item?.quote);
    const rawText = normalizeEvidenceText(snapshot?.raw_text ?? snapshot?.rawText);
    if (quote && (!rawText || !rawText.includes(quote))) errors.push('quote:not_in_snapshot');
  }

  // 検索スニペットは取得候補のポインタであり、確認済み証拠にはしない。
  if (item?.evidence_grade === 'snippet_only' && item?.status === 'verified') {
    errors.push('snippet_only:cannot_be_verified');
  }

  return { ok: errors.length === 0, errors };
}

export function validateCoverage(item) {
  const errors = [];
  if (!RESEARCH_AREAS.includes(item?.area)) errors.push('area:invalid');
  if (typeof item?.required !== 'boolean') errors.push('required:boolean_required');
  if (!Array.isArray(item?.queries_attempted)) errors.push('queries_attempted:array_required');
  if (!Array.isArray(item?.sources_attempted)) errors.push('sources_attempted:array_required');
  if (!Array.isArray(item?.evidence_ids)) errors.push('evidence_ids:array_required');
  if (!COVERAGE_STATUSES.includes(item?.status)) errors.push('status:invalid');
  return { ok: errors.length === 0, errors };
}

export function createCoverageLedger(requiredAreas = RESEARCH_AREAS) {
  const required = new Set(requiredAreas);
  return RESEARCH_AREAS.map(area => ({
    area,
    required: required.has(area),
    queries_attempted: [],
    sources_attempted: [],
    evidence_ids: [],
    status: 'pending',
    stop_reason: null,
    remaining_action: null,
  }));
}

function hostOf(value) {
  try { return new URL(value).hostname.toLowerCase(); } catch { return null; }
}

// Coverage停止判断はLLMに委ねず、固定ソース・新規ホスト・領域予算・案件予算で決める。
export function evaluateCoverageStop(input) {
  const requiredSources = input?.required_sources || [];
  const sourceStates = input?.source_states || {};
  if (requiredSources.length && requiredSources.every(source => TERMINAL_SOURCE_STATES.has(sourceStates[source]))) {
    return { stop: true, reason: 'required_sources_exhausted' };
  }
  if (Number(input?.queries_used ?? 0) >= Number(input?.query_budget ?? Number.POSITIVE_INFINITY)) {
    return { stop: true, reason: 'area_budget_exhausted' };
  }
  if (Number(input?.job_cost_micros ?? 0) >= Number(input?.job_budget_micros ?? Number.POSITIVE_INFINITY)) {
    return { stop: true, reason: 'job_budget_reached' };
  }

  const rounds = input?.round_source_urls || [];
  const window = Math.max(1, Number(input?.stagnation_rounds || 2));
  if (rounds.length >= window + 1) {
    const priorHosts = new Set(rounds.slice(0, -window).flat().map(hostOf).filter(Boolean));
    const recent = rounds.slice(-window);
    const added = recent.some(urls => urls.map(hostOf).filter(Boolean).some(host => {
      if (priorHosts.has(host)) return false;
      priorHosts.add(host);
      return true;
    }));
    if (!added) return { stop: true, reason: 'no_new_source_hosts' };
  }
  return { stop: false, reason: null };
}
