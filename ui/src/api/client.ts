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

export async function listClaims(): Promise<ClaimSummary[]> {
  return fetchJson<ClaimSummary[]>(`${API_BASE}/claims`);
}

export async function listDocs(claimId: string): Promise<DocSummary[]> {
  return fetchJson<DocSummary[]>(`${API_BASE}/claims/${claimId}/docs`);
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
  docs_needs_vision: number;
  docs_text_good: number;
  docs_text_warn: number;
  docs_text_poor: number;
  required_field_presence_rate: number;
  required_field_accuracy: number;
  evidence_rate: number;
}

export interface DocTypeMetrics {
  doc_type: string;
  docs_reviewed: number;
  docs_doc_type_wrong: number;
  docs_doc_type_wrong_pct: number;
  docs_needs_vision: number;
  docs_needs_vision_pct: number;
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
  needs_vision: boolean;
  gate_status: string | null;
  text_readable: string | null;
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
