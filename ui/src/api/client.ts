// API client for Extraction QA Console

import type {
  ClaimSummary,
  DocSummary,
  DocPayload,
  RunSummary,
  FieldLabel,
  DocLabels,
  ClaimReviewPayload,
  DocReviewRequest,
  TemplateSpec,
} from "../types";

const API_BASE = "/api";

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

export async function listClaims(runId?: string): Promise<ClaimSummary[]> {
  const url = runId
    ? `${API_BASE}/claims?run_id=${encodeURIComponent(runId)}`
    : `${API_BASE}/claims`;
  return fetchJson<ClaimSummary[]>(url);
}

export async function listDocs(claimId: string, runId?: string): Promise<DocSummary[]> {
  const url = runId
    ? `${API_BASE}/claims/${claimId}/docs?run_id=${encodeURIComponent(runId)}`
    : `${API_BASE}/claims/${claimId}/docs`;
  return fetchJson<DocSummary[]>(url);
}

// Run info for claims view
export interface ClaimRunInfo {
  run_id: string;
  timestamp: string | null;
  model: string | null;
  claims_count?: number;  // Only present for global (workspace-scoped) runs
}

export async function listClaimRuns(): Promise<ClaimRunInfo[]> {
  return fetchJson<ClaimRunInfo[]>(`${API_BASE}/claims/runs`);
}

export async function getDoc(docId: string, claimId?: string): Promise<DocPayload> {
  const url = claimId
    ? `${API_BASE}/docs/${docId}?claim_id=${claimId}`
    : `${API_BASE}/docs/${docId}`;
  return fetchJson<DocPayload>(url);
}

export async function saveLabels(
  docId: string,
  reviewer: string,
  notes: string,
  fieldLabels: FieldLabel[],
  docLabels: DocLabels
): Promise<{ status: string; path: string }> {
  return fetchJson(`${API_BASE}/docs/${docId}/labels`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      reviewer,
      notes,
      field_labels: fieldLabels,
      doc_labels: docLabels,
    }),
  });
}

export async function getRunSummary(): Promise<RunSummary> {
  return fetchJson<RunSummary>(`${API_BASE}/runs/latest`);
}

// New API functions for claim-level review

export async function getClaimReview(claimId: string): Promise<ClaimReviewPayload> {
  return fetchJson<ClaimReviewPayload>(`${API_BASE}/claims/${claimId}/review`);
}

export async function saveDocReview(
  docId: string,
  claimId: string,
  data: DocReviewRequest
): Promise<{ status: string }> {
  return fetchJson(`${API_BASE}/docs/${docId}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      claim_id: claimId,
      ...data,
    }),
  });
}

export async function getTemplates(): Promise<TemplateSpec[]> {
  return fetchJson<TemplateSpec[]>(`${API_BASE}/templates`);
}

// Get URL for document source file (PDF/image)
export function getDocSourceUrl(docId: string, claimId: string): string {
  return `${API_BASE}/docs/${docId}/source?claim_id=${claimId}`;
}

// Insights API

export interface InsightsOverview {
  docs_total: number;
  docs_reviewed: number;
  docs_doc_type_wrong: number;
  required_field_presence_rate: number;
  required_field_accuracy: number;
  evidence_rate: number;
  run_coverage: number;
  docs_with_extraction: number;
}

export interface DocTypeMetrics {
  doc_type: string;
  docs_reviewed: number;
  docs_doc_type_wrong: number;
  docs_doc_type_wrong_pct: number;
  required_field_presence_pct: number;
  required_field_accuracy_pct: number;
  evidence_rate_pct: number;
  top_failing_field: string | null;
}

export interface PriorityItem {
  doc_type: string;
  field_name: string;
  is_required: boolean;
  affected_docs: number;
  total_labeled: number;
  extractor_miss: number;
  incorrect: number;
  evidence_missing: number;
  cannot_verify: number;
  priority_score: number;
  fix_bucket: string;
}

export interface FieldDetails {
  doc_type: string;
  field_name: string;
  is_required: boolean;
  total_docs: number;
  labeled_docs: number;
  with_prediction: number;
  with_evidence: number;
  breakdown: {
    correct: number;
    incorrect: number;
    extractor_miss: number;
    cannot_verify: number;
    evidence_missing: number;
  };
  rates: {
    presence_pct: number;
    evidence_pct: number;
    accuracy_pct: number;
  };
}

export interface InsightExample {
  claim_id: string;
  doc_id: string;
  filename: string;
  doc_type: string;
  field_name: string;
  predicted_value: string | null;
  normalized_value: string | null;
  judgement: string | null;
  has_evidence: boolean;
  gate_status: string | null;
  outcome: string | null;
  doc_type_correct: boolean | null;
  review_url: string;
}

export async function getInsightsOverview(): Promise<InsightsOverview> {
  return fetchJson<InsightsOverview>(`${API_BASE}/insights/overview`);
}

export async function getInsightsDocTypes(): Promise<DocTypeMetrics[]> {
  return fetchJson<DocTypeMetrics[]>(`${API_BASE}/insights/doc-types`);
}

export async function getInsightsPriorities(limit = 10): Promise<PriorityItem[]> {
  return fetchJson<PriorityItem[]>(`${API_BASE}/insights/priorities?limit=${limit}`);
}

export async function getInsightsFieldDetails(docType: string, field: string): Promise<FieldDetails> {
  return fetchJson<FieldDetails>(`${API_BASE}/insights/field-details?doc_type=${encodeURIComponent(docType)}&field=${encodeURIComponent(field)}`);
}

export async function getInsightsExamples(params: {
  doc_type?: string;
  field?: string;
  outcome?: string;
  limit?: number;
}): Promise<InsightExample[]> {
  const query = new URLSearchParams();
  if (params.doc_type) query.set("doc_type", params.doc_type);
  if (params.field) query.set("field", params.field);
  if (params.outcome) query.set("outcome", params.outcome);
  if (params.limit) query.set("limit", params.limit.toString());
  return fetchJson<InsightExample[]>(`${API_BASE}/insights/examples?${query.toString()}`);
}

// Run management

export interface RunInfo {
  run_id: string;
  timestamp: string | null;
  model: string;
  extractor_version: string;
  prompt_version: string;
  claims_count: number;
  docs_count: number;
  extracted_count: number;
  labeled_count: number;
  presence_rate: number;
  accuracy_rate: number;
  evidence_rate: number;
}

export interface RunOverview {
  run_metadata: {
    run_id: string;
    timestamp: string | null;
    model: string;
    extractor_version: string;
    prompt_version: string;
    docs_processed: number;
    docs_total: number;
    docs_reviewed: number;
  };
  overview: InsightsOverview;
}

export interface RunComparison {
  baseline_run_id: string;
  current_run_id: string;
  baseline_metadata: Record<string, unknown>;
  current_metadata: Record<string, unknown>;
  overview_deltas: Record<string, { baseline: number; current: number; delta: number }>;
  priority_changes: Array<{ doc_type: string; field_name: string; status: string; delta?: number }>;
  doc_type_deltas: Array<{ doc_type: string; presence_delta: number; accuracy_delta: number; evidence_delta: number }>;
}

// Detailed run info with phase metrics for Extraction page
export interface PhaseMetrics {
  ingestion: {
    discovered: number;
    ingested: number;
    skipped: number;
    failed: number;
    duration_ms?: number | null;
  };
  classification: {
    classified: number;
    low_confidence: number;
    distribution: Record<string, number>;
    duration_ms?: number | null;
  };
  extraction: {
    attempted: number;
    succeeded: number;
    failed: number;
    skipped_unsupported?: number;
    duration_ms?: number | null;
  };
  quality_gate: {
    pass: number;
    warn: number;
    fail: number;
  };
}

export interface DetailedRunInfo {
  run_id: string;
  timestamp: string | null;
  model: string;
  status: "complete" | "partial" | "failed";
  duration_seconds: number | null;
  claims_count: number;
  docs_total: number;
  docs_success: number;
  docs_failed: number;
  phases: PhaseMetrics;
}

export async function getDetailedRuns(): Promise<DetailedRunInfo[]> {
  return fetchJson<DetailedRunInfo[]>(`${API_BASE}/insights/runs/detailed`);
}

export async function getInsightsRuns(): Promise<RunInfo[]> {
  return fetchJson<RunInfo[]>(`${API_BASE}/insights/runs`);
}

export async function getRunOverview(runId: string): Promise<RunOverview> {
  return fetchJson<RunOverview>(`${API_BASE}/insights/run/${runId}/overview`);
}

export async function getRunDocTypes(runId: string): Promise<DocTypeMetrics[]> {
  return fetchJson<DocTypeMetrics[]>(`${API_BASE}/insights/run/${runId}/doc-types`);
}

export async function getRunPriorities(runId: string, limit = 10): Promise<PriorityItem[]> {
  return fetchJson<PriorityItem[]>(`${API_BASE}/insights/run/${runId}/priorities?limit=${limit}`);
}

export async function compareRuns(baselineId: string, currentId: string): Promise<RunComparison> {
  return fetchJson<RunComparison>(`${API_BASE}/insights/compare?baseline=${baselineId}&current=${currentId}`);
}

export async function getBaseline(): Promise<{ baseline_run_id: string | null }> {
  return fetchJson<{ baseline_run_id: string | null }>(`${API_BASE}/insights/baseline`);
}

export async function setBaseline(runId: string): Promise<{ status: string }> {
  return fetchJson<{ status: string }>(`${API_BASE}/insights/baseline?run_id=${runId}`, { method: "POST" });
}

export async function clearBaseline(): Promise<{ status: string }> {
  return fetchJson<{ status: string }>(`${API_BASE}/insights/baseline`, { method: "DELETE" });
}

// Azure DI API for bounding box highlighting

import type { AzureDIOutput } from "../types";

// Cache for Azure DI data to avoid repeated fetches
const azureDICache = new Map<string, AzureDIOutput | null>();

export async function getAzureDI(docId: string, claimId: string): Promise<AzureDIOutput | null> {
  const cacheKey = `${claimId}/${docId}`;
  if (azureDICache.has(cacheKey)) {
    return azureDICache.get(cacheKey) || null;
  }

  try {
    const data = await fetchJson<AzureDIOutput>(
      `${API_BASE}/docs/${docId}/azure-di?claim_id=${claimId}`
    );
    azureDICache.set(cacheKey, data);
    return data;
  } catch {
    // Not available - cache the null result to avoid repeated 404s
    azureDICache.set(cacheKey, null);
    return null;
  }
}
