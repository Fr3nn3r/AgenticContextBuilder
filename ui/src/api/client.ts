// API client for Extraction QA Console

import type {
  ClaimSummary,
  DocSummary,
  DocPayload,
  RunSummary,
  FieldLabel,
  DocLabels,
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

export async function getDoc(docId: string): Promise<DocPayload> {
  return fetchJson<DocPayload>(`${API_BASE}/docs/${docId}`);
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
