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
