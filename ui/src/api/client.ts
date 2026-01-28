// API client for Extraction QA Console

import type {
  ClaimSummary,
  DocSummary,
  DocPayload,
  BatchSummary,
  FieldLabel,
  DocLabels,
  ClaimReviewPayload,
  DocReviewRequest,
  TemplateSpec,
  TruthListResponse,
} from "../types";

const API_BASE = "/api";

// Get auth token from localStorage
function getAuthToken(): string | null {
  return localStorage.getItem("auth_token");
}

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const token = getAuthToken();
  const headers = new Headers(options?.headers);

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  // Handle 401 Unauthorized - redirect to login
  if (response.status === 401) {
    localStorage.removeItem("auth_token");
    localStorage.removeItem("auth_user");
    window.location.href = "/login";
    throw new Error("Session expired");
  }

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

export async function getDoc(docId: string, claimId?: string, runId?: string): Promise<DocPayload> {
  const params = new URLSearchParams();
  if (claimId) params.set("claim_id", claimId);
  if (runId) params.set("run_id", runId);
  const queryString = params.toString();
  const url = queryString
    ? `${API_BASE}/docs/${docId}?${queryString}`
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

export async function getBatchSummary(): Promise<BatchSummary> {
  return fetchJson<BatchSummary>(`${API_BASE}/runs/latest`);
}

/** @deprecated Use getBatchSummary instead */
export const getRunSummary = getBatchSummary;

// New API functions for claim-level review

export async function getClaimReview(claimId: string): Promise<ClaimReviewPayload> {
  return fetchJson<ClaimReviewPayload>(`${API_BASE}/claims/${claimId}/review`);
}

import type { ClaimFacts, ClaimRunManifest, ReconciliationReport } from "../types";

/**
 * Get aggregated claim facts from the context folder.
 * Returns null if no facts have been aggregated for this claim.
 */
export async function getClaimFacts(claimId: string): Promise<ClaimFacts | null> {
  return fetchJson<ClaimFacts | null>(`${API_BASE}/claims/${encodeURIComponent(claimId)}/facts`);
}

/**
 * Get all claim runs for a claim.
 * Returns a list of claim run manifests sorted by date (newest first).
 */
export async function getClaimRunsForClaim(claimId: string): Promise<ClaimRunManifest[]> {
  return fetchJson<ClaimRunManifest[]>(
    `${API_BASE}/claims/${encodeURIComponent(claimId)}/claim-runs`
  );
}

/**
 * Get claim facts for a specific claim run.
 * Returns null if no facts exist for this run.
 */
export async function getClaimFactsByRun(
  claimId: string,
  claimRunId: string
): Promise<ClaimFacts | null> {
  try {
    return await fetchJson<ClaimFacts>(
      `${API_BASE}/claims/${encodeURIComponent(claimId)}/claim-runs/${encodeURIComponent(claimRunId)}/facts`
    );
  } catch {
    return null;
  }
}

/**
 * Get reconciliation report for a specific claim run.
 * Returns null if no report exists for this run.
 */
export async function getReconciliationReport(
  claimId: string,
  claimRunId: string
): Promise<ReconciliationReport | null> {
  try {
    return await fetchJson<ReconciliationReport>(
      `${API_BASE}/claims/${encodeURIComponent(claimId)}/claim-runs/${encodeURIComponent(claimRunId)}/reconciliation-report`
    );
  } catch {
    return null;
  }
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

export async function getTruthEntries(params: {
  file_md5?: string;
  doc_type?: string;
  claim_id?: string;
  reviewer?: string;
  reviewed_after?: string;
  reviewed_before?: string;
  field_name?: string;
  state?: string;
  outcome?: string;
  run_id?: string;
  filename?: string;
  search?: string;
} = {}): Promise<TruthListResponse> {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value) {
      query.set(key, value);
    }
  });
  const suffix = query.toString();
  return fetchJson<TruthListResponse>(
    `${API_BASE}/truth${suffix ? `?${suffix}` : ""}`
  );
}

// Get URL for document source file (PDF/image)
export function getDocSourceUrl(docId: string, claimId: string): string {
  return `${API_BASE}/docs/${docId}/source?claim_id=${claimId}`;
}

// Document run history
export interface DocRunInfo {
  run_id: string;
  timestamp: string | null;
  model: string;
  status: "complete" | "partial" | "failed";
  extraction: {
    field_count: number;
    gate_status: "pass" | "warn" | "fail" | null;
  } | null;
}

export async function getDocRuns(docId: string, claimId: string): Promise<DocRunInfo[]> {
  return fetchJson<DocRunInfo[]>(
    `${API_BASE}/docs/${docId}/runs?claim_id=${encodeURIComponent(claimId)}`
  );
}

// All documents list (batch-independent)

export interface DocumentListItem {
  doc_id: string;
  claim_id: string;
  filename: string;
  doc_type: string;
  language: string;
  has_truth: boolean;
  last_reviewed: string | null;
  reviewer: string | null;
  quality_status: "pass" | "warn" | "fail" | null;
}

export interface DocumentListResponse {
  documents: DocumentListItem[];
  total: number;
}

export interface DocumentListParams {
  claim_id?: string;
  doc_type?: string;
  has_truth?: boolean;
  search?: string;
  limit?: number;
  offset?: number;
}

export async function listAllDocuments(
  params: DocumentListParams = {}
): Promise<DocumentListResponse> {
  const query = new URLSearchParams();
  if (params.claim_id) query.set("claim_id", params.claim_id);
  if (params.doc_type) query.set("doc_type", params.doc_type);
  if (params.has_truth !== undefined) query.set("has_truth", String(params.has_truth));
  if (params.search) query.set("search", params.search);
  if (params.limit) query.set("limit", String(params.limit));
  if (params.offset) query.set("offset", String(params.offset));

  const queryString = query.toString();
  const url = queryString
    ? `${API_BASE}/documents?${queryString}`
    : `${API_BASE}/documents`;

  return fetchJson<DocumentListResponse>(url);
}

// Insights API

export interface InsightsOverview {
  docs_total: number;
  docs_with_truth: number;        // Docs with ≥1 LABELED field
  labeled_fields: number;         // Total LABELED fields
  total_fields: number;           // Total fields across docs
  accuracy_rate: number;          // correct / (correct + incorrect + missing)
  evidence_rate: number;
  // Accuracy breakdown
  correct_count: number;
  incorrect_count: number;
  missing_count: number;
  // Legacy/deprecated fields (for backwards compatibility)
  confirmed_fields?: number;      // Deprecated: use labeled_fields
  match_count?: number;           // Deprecated: use correct_count
  mismatch_count?: number;        // Deprecated: use incorrect_count
  miss_count?: number;            // Deprecated: use missing_count
  docs_reviewed: number;
  docs_doc_type_wrong: number;
  required_field_presence_rate: number;
  required_field_accuracy: number;
  run_coverage?: number;           // Legacy
  docs_with_extraction?: number;   // Legacy
}

export interface DocTypeMetrics {
  doc_type: string;
  docs_total: number;  // Total docs of this type in run
  docs_reviewed: number;  // Docs with labels (for benchmark)
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
  // Truth-based metrics
  incorrect_count: number;        // Truth differs from extraction
  missing_count: number;          // No extraction for labeled truth
  total_labeled: number;          // Total LABELED fields
  error_rate: number;             // (incorrect + missing) / total_labeled
  // Legacy/deprecated fields (for backwards compatibility)
  mismatch_count?: number;        // Deprecated: use incorrect_count
  miss_count?: number;            // Deprecated: use missing_count
  total_confirmed?: number;       // Deprecated: use total_labeled
  affected_docs: number;
  priority_score: number;
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
  truth_value: string | null;                              // NEW: ground truth value
  state: "CONFIRMED" | "UNVERIFIABLE" | "UNLABELED" | null; // NEW: label state
  has_evidence: boolean;
  gate_status: string | null;
  outcome: "match" | "mismatch" | "miss" | "unverifiable" | string | null;  // NEW outcomes
  doc_type_correct: boolean | null;
  review_url: string;
  // Legacy field for backwards compatibility
  judgement: string | null;
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

export async function getInsightsFieldDetails(docType: string, field: string, runId?: string): Promise<FieldDetails> {
  const params = new URLSearchParams();
  params.set("doc_type", docType);
  params.set("field", field);
  if (runId) params.set("run_id", runId);
  return fetchJson<FieldDetails>(`${API_BASE}/insights/field-details?${params.toString()}`);
}

export async function getInsightsExamples(params: {
  doc_type?: string;
  field?: string;
  outcome?: string;
  run_id?: string;
  limit?: number;
}): Promise<InsightExample[]> {
  const query = new URLSearchParams();
  if (params.doc_type) query.set("doc_type", params.doc_type);
  if (params.field) query.set("field", params.field);
  if (params.outcome) query.set("outcome", params.outcome);
  if (params.run_id) query.set("run_id", params.run_id);
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

// =============================================================================
// EVOLUTION API
// =============================================================================

import type { EvolutionSummary, DocTypeMatrixResponse } from "../types";

/**
 * Get pipeline evolution timeline with scope and accuracy metrics.
 * Shows how the pipeline has evolved over time across version bundles.
 */
export async function getEvolutionTimeline(): Promise<EvolutionSummary> {
  return fetchJson<EvolutionSummary>(`${API_BASE}/evolution/timeline`);
}

/**
 * Get doc type evolution matrix.
 * Shows per-doc-type field counts and accuracy across spec versions.
 */
export async function getEvolutionDocTypes(): Promise<DocTypeMatrixResponse> {
  return fetchJson<DocTypeMatrixResponse>(`${API_BASE}/evolution/doc-types`);
}

// Azure DI API for bounding box highlighting

import type { AzureDIOutputExtended } from "../types";

// Cache for Azure DI data to avoid repeated fetches
const azureDICache = new Map<string, AzureDIOutputExtended | null>();

export async function getAzureDI(docId: string, claimId: string): Promise<AzureDIOutputExtended | null> {
  const cacheKey = `${claimId}/${docId}`;
  if (azureDICache.has(cacheKey)) {
    return azureDICache.get(cacheKey) || null;
  }

  try {
    const data = await fetchJson<AzureDIOutputExtended>(
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

// =============================================================================
// CLASSIFICATION REVIEW API
// =============================================================================

import type {
  ClassificationDoc,
  ClassificationDetail,
  ClassificationLabelRequest,
  ClassificationStats,
  DocTypeCatalogEntry,
} from "../types";

export async function listClassificationDocs(runId: string): Promise<ClassificationDoc[]> {
  return fetchJson<ClassificationDoc[]>(
    `${API_BASE}/classification/docs?run_id=${encodeURIComponent(runId)}`
  );
}

export async function getClassificationDetail(
  docId: string,
  runId: string,
  claimId: string
): Promise<ClassificationDetail> {
  return fetchJson<ClassificationDetail>(
    `${API_BASE}/classification/doc/${docId}?run_id=${encodeURIComponent(runId)}&claim_id=${encodeURIComponent(claimId)}`
  );
}

export async function getDocTypeCatalog(): Promise<DocTypeCatalogEntry[]> {
  return fetchJson<DocTypeCatalogEntry[]>(`${API_BASE}/classification/doc-types`);
}

export async function saveClassificationLabel(
  docId: string,
  data: ClassificationLabelRequest
): Promise<{ status: string; doc_id: string }> {
  return fetchJson(`${API_BASE}/classification/doc/${docId}/label`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function getClassificationStats(runId: string): Promise<ClassificationStats> {
  return fetchJson<ClassificationStats>(
    `${API_BASE}/classification/stats?run_id=${encodeURIComponent(runId)}`
  );
}

// =============================================================================
// UPLOAD API
// =============================================================================

import type {
  AuditEntry,
  AuditListParams,
  CreatePromptConfigRequest,
  EnhancedPipelineRun,
  PendingClaim,
  PendingDocument,
  PipelineBatch,
  PipelineClaimOption,
  PromptConfig,
  StartPipelineRequest,
  UpdatePromptConfigRequest,
} from "../types";

export interface UploadResult {
  claim_id: string;
  documents: PendingDocument[];
}

export async function uploadDocuments(
  claimId: string,
  files: File[],
  onProgress?: (progress: number) => void
): Promise<UploadResult> {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/upload/claim/${encodeURIComponent(claimId)}`);

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        const progress = Math.round((event.loaded / event.total) * 100);
        onProgress(progress);
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText));
      } else {
        try {
          const error = JSON.parse(xhr.responseText);
          reject(new Error(error.detail || `HTTP ${xhr.status}`));
        } catch {
          reject(new Error(`HTTP ${xhr.status}`));
        }
      }
    };

    xhr.onerror = () => reject(new Error("Network error"));
    xhr.send(formData);
  });
}

export async function listPendingClaims(): Promise<PendingClaim[]> {
  return fetchJson<PendingClaim[]>(`${API_BASE}/upload/pending`);
}

export async function getPendingClaim(claimId: string): Promise<PendingClaim> {
  return fetchJson<PendingClaim>(`${API_BASE}/upload/claim/${encodeURIComponent(claimId)}`);
}

export async function deletePendingClaim(claimId: string): Promise<{ status: string }> {
  return fetchJson<{ status: string }>(
    `${API_BASE}/upload/claim/${encodeURIComponent(claimId)}`,
    { method: "DELETE" }
  );
}

export async function deletePendingDocument(
  claimId: string,
  docId: string
): Promise<{ status: string }> {
  return fetchJson<{ status: string }>(
    `${API_BASE}/upload/claim/${encodeURIComponent(claimId)}/doc/${encodeURIComponent(docId)}`,
    { method: "DELETE" }
  );
}

export async function reorderDocuments(
  claimId: string,
  docIds: string[]
): Promise<{ status: string }> {
  return fetchJson<{ status: string }>(
    `${API_BASE}/upload/claim/${encodeURIComponent(claimId)}/reorder`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(docIds),
    }
  );
}

export async function validateClaimId(
  claimId: string
): Promise<{ status: string; claim_id: string }> {
  return fetchJson<{ status: string; claim_id: string }>(
    `${API_BASE}/upload/claim/${encodeURIComponent(claimId)}/validate`,
    { method: "POST" }
  );
}

export async function generateClaimId(): Promise<{ claim_id: string }> {
  return fetchJson<{ claim_id: string }>(`${API_BASE}/upload/generate-claim-id`, {
    method: "POST",
  });
}

// =============================================================================
// PIPELINE API
// =============================================================================

export async function startPipeline(
  claimIds: string[],
  model: string = "gpt-4o"
): Promise<{ batch_id: string; status: string }> {
  const result = await fetchJson<{ run_id: string; status: string }>(`${API_BASE}/pipeline/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ claim_ids: claimIds, model }),
  });
  return { batch_id: result.run_id, status: result.status };
}

export async function cancelPipeline(batchId: string): Promise<{ status: string }> {
  return fetchJson<{ status: string }>(
    `${API_BASE}/pipeline/cancel/${encodeURIComponent(batchId)}`,
    { method: "POST" }
  );
}

export async function getPipelineStatus(batchId: string): Promise<PipelineBatch> {
  const result = await fetchJson<{ run_id: string } & Omit<PipelineBatch, 'batch_id'>>(`${API_BASE}/pipeline/status/${encodeURIComponent(batchId)}`);
  return { ...result, batch_id: result.run_id };
}

export async function listPipelineBatches(): Promise<PipelineBatch[]> {
  const results = await fetchJson<Array<{ run_id: string } & Omit<PipelineBatch, 'batch_id'>>>(`${API_BASE}/pipeline/runs`);
  return results.map(r => ({ ...r, batch_id: r.run_id }));
}

/** @deprecated Use listPipelineBatches instead */
export const listPipelineRuns = listPipelineBatches;

// =============================================================================
// PIPELINE CONTROL CENTER API
// =============================================================================

export async function listPipelineClaims(): Promise<PipelineClaimOption[]> {
  return fetchJson<PipelineClaimOption[]>(`${API_BASE}/pipeline/claims`);
}

export async function listEnhancedPipelineRuns(): Promise<EnhancedPipelineRun[]> {
  return fetchJson<EnhancedPipelineRun[]>(`${API_BASE}/pipeline/runs`);
}

export async function startPipelineEnhanced(
  request: StartPipelineRequest
): Promise<{ run_id: string; status: string }> {
  return fetchJson<{ run_id: string; status: string }>(`${API_BASE}/pipeline/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

export async function deletePipelineRun(runId: string): Promise<{ status: string }> {
  return fetchJson<{ status: string }>(
    `${API_BASE}/pipeline/runs/${encodeURIComponent(runId)}`,
    { method: "DELETE" }
  );
}

// =============================================================================
// PROMPT CONFIG API
// =============================================================================

export async function listPromptConfigs(): Promise<PromptConfig[]> {
  return fetchJson<PromptConfig[]>(`${API_BASE}/pipeline/configs`);
}

export async function getPromptConfig(configId: string): Promise<PromptConfig> {
  return fetchJson<PromptConfig>(`${API_BASE}/pipeline/configs/${encodeURIComponent(configId)}`);
}

export async function createPromptConfig(
  request: CreatePromptConfigRequest
): Promise<PromptConfig> {
  return fetchJson<PromptConfig>(`${API_BASE}/pipeline/configs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

export async function updatePromptConfig(
  configId: string,
  request: UpdatePromptConfigRequest
): Promise<PromptConfig> {
  return fetchJson<PromptConfig>(
    `${API_BASE}/pipeline/configs/${encodeURIComponent(configId)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    }
  );
}

export async function deletePromptConfig(configId: string): Promise<{ status: string }> {
  return fetchJson<{ status: string }>(
    `${API_BASE}/pipeline/configs/${encodeURIComponent(configId)}`,
    { method: "DELETE" }
  );
}

export async function setDefaultPromptConfig(configId: string): Promise<PromptConfig> {
  return fetchJson<PromptConfig>(
    `${API_BASE}/pipeline/configs/${encodeURIComponent(configId)}/set-default`,
    { method: "POST" }
  );
}

// =============================================================================
// AUDIT LOG API
// =============================================================================

export async function listAuditEntries(params?: AuditListParams): Promise<AuditEntry[]> {
  const searchParams = new URLSearchParams();
  if (params?.action_type) searchParams.set("action_type", params.action_type);
  if (params?.entity_type) searchParams.set("entity_type", params.entity_type);
  if (params?.since) searchParams.set("since", params.since);
  if (params?.limit) searchParams.set("limit", String(params.limit));

  const queryString = searchParams.toString();
  const url = queryString
    ? `${API_BASE}/pipeline/audit?${queryString}`
    : `${API_BASE}/pipeline/audit`;

  return fetchJson<AuditEntry[]>(url);
}

// =============================================================================
// ADMIN API (User Management)
// =============================================================================

export interface UserResponse {
  username: string;
  role: string;
  created_at: string;
  updated_at: string;
}

export async function listUsers(): Promise<UserResponse[]> {
  return fetchJson<UserResponse[]>(`${API_BASE}/admin/users`);
}

export async function createUser(
  username: string,
  password: string,
  role: string
): Promise<UserResponse> {
  return fetchJson<UserResponse>(`${API_BASE}/admin/users`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password, role }),
  });
}

export async function updateUser(
  username: string,
  data: { password?: string; role?: string }
): Promise<UserResponse> {
  return fetchJson<UserResponse>(
    `${API_BASE}/admin/users/${encodeURIComponent(username)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }
  );
}

export async function deleteUser(username: string): Promise<{ success: boolean }> {
  return fetchJson<{ success: boolean }>(
    `${API_BASE}/admin/users/${encodeURIComponent(username)}`,
    { method: "DELETE" }
  );
}

// =============================================================================
// WORKSPACE API
// =============================================================================

export interface WorkspaceResponse {
  workspace_id: string;
  name: string;
  path: string;
  status: string;
  created_at: string;
  last_accessed_at: string | null;
  description: string | null;
  is_active: boolean;
}

export interface CreateWorkspaceRequest {
  name: string;
  path?: string;  // Auto-generated server-side if not provided
  description?: string;
}

export interface ActivateWorkspaceResponse {
  status: string;
  workspace_id: string;
  sessions_cleared: number;
  previous_workspace_id: string | null;
}

export async function listWorkspaces(): Promise<WorkspaceResponse[]> {
  return fetchJson<WorkspaceResponse[]>(`${API_BASE}/admin/workspaces`);
}

export async function getActiveWorkspace(): Promise<WorkspaceResponse> {
  return fetchJson<WorkspaceResponse>(`${API_BASE}/admin/workspaces/active`);
}

export async function createWorkspace(
  request: CreateWorkspaceRequest
): Promise<WorkspaceResponse> {
  return fetchJson<WorkspaceResponse>(`${API_BASE}/admin/workspaces`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

export async function activateWorkspace(
  workspaceId: string
): Promise<ActivateWorkspaceResponse> {
  return fetchJson<ActivateWorkspaceResponse>(
    `${API_BASE}/admin/workspaces/${encodeURIComponent(workspaceId)}/activate`,
    { method: "POST" }
  );
}

export async function deleteWorkspace(
  workspaceId: string
): Promise<{ status: string; workspace_id: string }> {
  return fetchJson<{ status: string; workspace_id: string }>(
    `${API_BASE}/admin/workspaces/${encodeURIComponent(workspaceId)}`,
    { method: "DELETE" }
  );
}

export interface RebuildIndexResponse {
  status: string;
  workspace_id: string;
  stats: {
    built_at: string;
    doc_count: number;
    label_count: number;
    run_count: number;
    claim_count: number;
  };
}

export async function rebuildIndex(): Promise<RebuildIndexResponse> {
  return fetchJson<RebuildIndexResponse>(`${API_BASE}/admin/index/rebuild`, {
    method: "POST",
  });
}

// =============================================================================
// COMPLIANCE API
// =============================================================================

import type {
  DecisionRecord,
  VerificationResult,
  VersionBundle,
  VersionBundleSummary,
  ConfigHistoryEntry,
  TruthHistory,
  LabelHistory,
  DecisionType,
} from "../types";

export interface DecisionQueryParams {
  decision_type?: DecisionType;
  doc_id?: string;
  claim_id?: string;
  since?: string;
  limit?: number;
}

export async function verifyDecisionLedger(): Promise<VerificationResult> {
  return fetchJson<VerificationResult>(`${API_BASE}/compliance/ledger/verify`);
}

export async function resetDecisionLedger(): Promise<{ status: string; records_deleted: number }> {
  return fetchJson<{ status: string; records_deleted: number }>(
    `${API_BASE}/compliance/ledger/reset`,
    { method: "DELETE" }
  );
}

export async function listDecisions(
  params: DecisionQueryParams = {}
): Promise<DecisionRecord[]> {
  const query = new URLSearchParams();
  if (params.decision_type) query.set("decision_type", params.decision_type);
  if (params.doc_id) query.set("doc_id", params.doc_id);
  if (params.claim_id) query.set("claim_id", params.claim_id);
  if (params.since) query.set("since", params.since);
  if (params.limit) query.set("limit", String(params.limit));

  const queryString = query.toString();
  const url = queryString
    ? `${API_BASE}/compliance/ledger/decisions?${queryString}`
    : `${API_BASE}/compliance/ledger/decisions`;

  return fetchJson<DecisionRecord[]>(url);
}

export async function listVersionBundles(): Promise<VersionBundleSummary[]> {
  return fetchJson<VersionBundleSummary[]>(`${API_BASE}/compliance/version-bundles`);
}

export async function getVersionBundle(runId: string): Promise<VersionBundle> {
  return fetchJson<VersionBundle>(
    `${API_BASE}/compliance/version-bundles/${encodeURIComponent(runId)}`
  );
}

export async function getConfigHistory(
  limit: number = 100
): Promise<ConfigHistoryEntry[]> {
  return fetchJson<ConfigHistoryEntry[]>(
    `${API_BASE}/compliance/config-history?limit=${limit}`
  );
}

export async function getTruthHistory(fileMd5: string): Promise<TruthHistory> {
  return fetchJson<TruthHistory>(
    `${API_BASE}/compliance/truth-history/${encodeURIComponent(fileMd5)}`
  );
}

export async function getLabelHistory(docId: string): Promise<LabelHistory> {
  return fetchJson<LabelHistory>(
    `${API_BASE}/compliance/label-history/${encodeURIComponent(docId)}`
  );
}

// =============================================================================
// VERSION API
// =============================================================================

import type { VersionInfo } from "../types";

export async function getAppVersion(): Promise<VersionInfo> {
  return fetchJson<VersionInfo>(`${API_BASE}/version`);
}

// =============================================================================
// TOKEN COST API
// =============================================================================

import type {
  CostOverview,
  CostByOperation,
  CostByRun,
  CostByClaim,
  CostByDoc,
  CostByDay,
  CostByModel,
} from "../types";

/**
 * Get overall token usage and cost summary.
 */
export async function getCostOverview(): Promise<CostOverview> {
  return fetchJson<CostOverview>(`${API_BASE}/insights/costs/overview`);
}

/**
 * Get token usage and costs broken down by operation type.
 */
export async function getCostByOperation(): Promise<CostByOperation[]> {
  return fetchJson<CostByOperation[]>(`${API_BASE}/insights/costs/by-operation`);
}

/**
 * Get token usage and costs per pipeline run.
 */
export async function getCostByRun(limit: number = 20): Promise<CostByRun[]> {
  return fetchJson<CostByRun[]>(`${API_BASE}/insights/costs/by-run?limit=${limit}`);
}

/**
 * Get token costs per claim.
 */
export async function getCostByClaim(runId?: string): Promise<CostByClaim[]> {
  const params = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
  return fetchJson<CostByClaim[]>(`${API_BASE}/insights/costs/by-claim${params}`);
}

/**
 * Get token costs per document.
 */
export async function getCostByDoc(claimId?: string, runId?: string): Promise<CostByDoc[]> {
  const query = new URLSearchParams();
  if (claimId) query.set("claim_id", claimId);
  if (runId) query.set("run_id", runId);
  const queryString = query.toString();
  return fetchJson<CostByDoc[]>(
    `${API_BASE}/insights/costs/by-doc${queryString ? `?${queryString}` : ""}`
  );
}

/**
 * Get daily token costs for trend chart.
 */
export async function getCostByDay(days: number = 30): Promise<CostByDay[]> {
  return fetchJson<CostByDay[]>(`${API_BASE}/insights/costs/daily-trend?days=${days}`);
}

/**
 * Get token usage and costs broken down by model.
 */
export async function getCostByModel(): Promise<CostByModel[]> {
  return fetchJson<CostByModel[]>(`${API_BASE}/insights/costs/by-model`);
}

// =============================================================================
// ASSESSMENT API
// =============================================================================

import type {
  ClaimAssessment,
  AssessmentEvaluation,
  ReconciliationEvaluation,
  TriageQueueItem,
  TriageQueueFilters,
} from "../types";

/**
 * Get assessment data for a specific claim.
 * Returns null if no assessment exists for this claim.
 */
export async function getClaimAssessment(claimId: string): Promise<ClaimAssessment | null> {
  try {
    return await fetchJson<ClaimAssessment>(
      `${API_BASE}/claims/${encodeURIComponent(claimId)}/assessment`
    );
  } catch {
    return null;
  }
}

/**
 * Get the latest assessment evaluation results.
 * Returns null if no evaluation has been run.
 */
export async function getLatestAssessmentEval(): Promise<AssessmentEvaluation | null> {
  try {
    return await fetchJson<AssessmentEvaluation>(`${API_BASE}/assessment/evals/latest`);
  } catch {
    return null;
  }
}

/**
 * Get the latest reconciliation gate evaluation results.
 * Returns null if no evaluation has been run.
 */
export async function getLatestReconciliationEval(): Promise<ReconciliationEvaluation | null> {
  try {
    return await fetchJson<ReconciliationEvaluation>(`${API_BASE}/reconciliation/evals/latest`);
  } catch {
    return null;
  }
}

/**
 * Get the triage queue with optional filters.
 */
export async function getTriageQueue(filters?: TriageQueueFilters): Promise<TriageQueueItem[]> {
  const query = new URLSearchParams();
  if (filters?.priority?.length) {
    query.set("priority", filters.priority.join(","));
  }
  if (filters?.reasons?.length) {
    query.set("reasons", filters.reasons.join(","));
  }
  if (filters?.decision?.length) {
    query.set("decision", filters.decision.join(","));
  }
  if (filters?.min_confidence !== undefined) {
    query.set("min_confidence", String(filters.min_confidence));
  }
  if (filters?.max_confidence !== undefined) {
    query.set("max_confidence", String(filters.max_confidence));
  }
  const queryString = query.toString();
  return fetchJson<TriageQueueItem[]>(
    `${API_BASE}/assessment/triage${queryString ? `?${queryString}` : ""}`
  );
}

/**
 * Mark a triage item as reviewed.
 */
export async function reviewTriageItem(
  claimId: string,
  action: "approve" | "reject" | "escalate"
): Promise<{ status: string }> {
  return fetchJson<{ status: string }>(
    `${API_BASE}/assessment/triage/${encodeURIComponent(claimId)}/review`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    }
  );
}

/**
 * Run assessment for a single claim.
 */
export async function runClaimAssessment(claimId: string): Promise<ClaimAssessment> {
  return fetchJson<ClaimAssessment>(
    `${API_BASE}/claims/${encodeURIComponent(claimId)}/assessment/run`,
    { method: "POST" }
  );
}

/**
 * Run assessment for multiple claims (batch).
 */
export async function runBatchAssessment(
  claimIds: string[]
): Promise<{ run_id: string; status: string; claims_count: number }> {
  return fetchJson<{ run_id: string; status: string; claims_count: number }>(
    `${API_BASE}/assessment/run`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ claim_ids: claimIds }),
    }
  );
}

/**
 * Get assessment history for a claim.
 */
export async function getAssessmentHistory(
  claimId: string
): Promise<Array<{
  run_id: string;
  timestamp: string;
  decision: "APPROVE" | "REJECT" | "REFER_TO_HUMAN";
  confidence_score: number;
  check_count: number;
  pass_count: number;
  fail_count: number;
  assumption_count: number;
  is_current: boolean;
}>> {
  return fetchJson(`${API_BASE}/claims/${encodeURIComponent(claimId)}/assessment/history`);
}

/**
 * Get a specific historical assessment by run ID.
 * Returns null if the assessment doesn't exist.
 */
export async function getHistoricalAssessment(
  claimId: string,
  assessmentId: string
): Promise<ClaimAssessment | null> {
  try {
    return await fetchJson<ClaimAssessment>(
      `${API_BASE}/claims/${encodeURIComponent(claimId)}/assessment/${encodeURIComponent(assessmentId)}`
    );
  } catch {
    return null;
  }
}

// =============================================================================
// CUSTOMER COMMUNICATION
// =============================================================================

export interface CustomerDraftResponse {
  subject: string;
  body: string;
  language: string;
  claim_id: string;
  tokens_used: number;
}

/**
 * Generate a customer communication draft email for a claim assessment.
 */
export async function generateCustomerDraft(
  claimId: string,
  language: "en" | "de" = "en"
): Promise<CustomerDraftResponse> {
  return fetchJson<CustomerDraftResponse>(
    `${API_BASE}/claims/${encodeURIComponent(claimId)}/communication/draft`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ language }),
    }
  );
}
