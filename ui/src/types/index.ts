// API Types for Extraction QA Console

export interface ClaimSummary {
  claim_id: string;
  doc_count: number;
  doc_types: string[];
  extracted_count: number;
  labeled_count: number;
  // ClaimEval-style fields (kept for backwards compatibility)
  lob: string;
  risk_score: number;
  loss_type: string;
  amount: number | null;
  currency: string;
  flags_count: number;
  status: string;
  closed_date: string | null;
  // Extraction-centric fields (run-dependent)
  gate_pass_count: number;
  gate_warn_count: number;
  gate_fail_count: number;
  last_processed: string | null;
  // Run context
  in_run: boolean;
}

export interface DocSummary {
  doc_id: string;
  filename: string;
  doc_type: string;
  language: string;
  has_extraction: boolean;
  has_labels: boolean;
  quality_status: string | null;
  confidence: number;
  // Extraction-centric fields
  missing_required_fields: string[];
}

export interface PageContent {
  page: number;
  text: string;
  text_md5: string;
}

export interface FieldProvenance {
  page: number;
  method: string;
  text_quote: string;
  char_start: number;
  char_end: number;
}

export interface ExtractedField {
  name: string;
  value: string | null;
  normalized_value: string | null;
  confidence: number;
  status: "present" | "missing" | "uncertain";
  provenance: FieldProvenance[];
  value_is_placeholder: boolean;
}

export interface QualityGate {
  status: "pass" | "warn" | "fail";
  reasons: string[];
  missing_required_fields: string[];
}

export interface ExtractionResult {
  schema_version: string;
  run: {
    run_id: string;
    extractor_version: string;
    model: string;
    prompt_version: string;
    input_hashes: Record<string, string>;
  };
  doc: {
    doc_id: string;
    claim_id: string;
    doc_type: string;
    doc_type_confidence: number;
    language: string;
    page_count: number;
  };
  pages: PageContent[];
  fields: ExtractedField[];
  quality_gate: QualityGate;
}

// Truth Label Types (label_v3, with legacy CONFIRMED support)

export type FieldState = "LABELED" | "UNVERIFIABLE" | "UNLABELED" | "CONFIRMED";

export type UnverifiableReason =
  | "not_present_in_doc"
  | "unreadable_text"
  | "wrong_doc_type"
  | "cannot_verify"
  | "other";

export interface FieldLabel {
  field_name: string;
  state: FieldState;
  truth_value?: string;
  unverifiable_reason?: UnverifiableReason;
  notes: string;
  updated_at?: string;
}

export interface DocLabels {
  doc_type_correct: boolean;
  doc_type_truth?: string | null;  // Corrected doc type when doc_type_correct=false
}

export interface LabelResult {
  schema_version: string;
  doc_id: string;
  claim_id: string;
  review: {
    reviewed_at: string;
    reviewer: string;
    notes: string;
  };
  field_labels: FieldLabel[];
  doc_labels: DocLabels;
}

export interface DocPayload {
  doc_id: string;
  claim_id: string;
  filename: string;
  doc_type: string;
  language: string;
  pages: PageContent[];
  extraction: ExtractionResult | null;
  labels: LabelResult | null;
  // Source file info
  has_pdf: boolean;
  has_image: boolean;
}

export interface BatchSummary {
  batch_dir: string;
  total_claims: number;
  total_docs: number;
  extracted_count: number;
  labeled_count: number;
  quality_gate: Record<string, number>;
}

/** @deprecated Use BatchSummary instead */
export type RunSummary = BatchSummary;

// New types for claim-level review

export interface ClaimReviewPayload {
  claim_id: string;
  lob: string;
  doc_count: number;
  unlabeled_count: number;
  gate_counts: {
    pass: number;
    warn: number;
    fail: number;
  };
  run_metadata: {
    run_id: string;
    model: string;
  } | null;
  prev_claim_id: string | null;
  next_claim_id: string | null;
  docs: DocSummary[];
  default_doc_id: string | null;
}

export interface DocReviewRequest {
  doc_type_correct: boolean;
  notes: string;
}

// Extraction template types

export interface FieldRule {
  normalize?: string;
  validate?: string;
  hints?: string[];
}

export interface QualityGateRules {
  pass_if?: string[];
  warn_if?: string[];
  fail_if?: string[];
}

export interface TemplateSpec {
  doc_type: string;
  version: string;
  required_fields: string[];
  optional_fields: string[];
  field_rules: Record<string, FieldRule>;
  quality_gate: QualityGateRules;
}

// Comparison result for truth vs extraction
export type ComparisonResult = "correct" | "incorrect" | "missing" | "unlabeled" | "unverifiable";

export interface FieldComparison {
  field_name: string;
  extracted_value: string | null;
  truth_value: string | null;
  state: FieldState;
  result: ComparisonResult;
}

export interface TruthRunValue {
  value: string | null;
  normalized_value: string | null;
  outcome: "correct" | "incorrect" | "missing" | "unverifiable" | "unlabeled" | null;
}

export interface TruthFieldComparison {
  field_name: string;
  state: FieldState | null;
  truth_value: string | null;
  runs: Record<string, TruthRunValue | null>;
}

export interface TruthDocInstance {
  doc_id: string;
  claim_id: string;
  doc_type: string;
  original_filename: string;
}

export interface TruthEntry {
  file_md5: string;
  content_md5: string;
  review: {
    reviewed_at?: string;
    reviewer?: string;
    notes?: string;
  };
  doc_labels: DocLabels;
  source_doc_ref: {
    claim_id?: string;
    doc_id?: string;
    original_filename?: string;
  };
  doc_instances: TruthDocInstance[];
  fields: TruthFieldComparison[];
}

export interface TruthListResponse {
  runs: string[];
  entries: TruthEntry[];
}

// Azure DI types for bounding box highlighting

export interface AzureDIWord {
  content: string;
  polygon: number[];  // 8 elements: [x1, y1, x2, y2, x3, y3, x4, y4] in inches
  confidence: number;
  span: {
    offset: number;
    length: number;
  };
}

export interface AzureDIPage {
  pageNumber: number;
  width: number;   // in inches
  height: number;  // in inches
  unit: string;
  words: AzureDIWord[];
}

export interface AzureDIOutput {
  raw_azure_di_output: {
    pages: AzureDIPage[];
    content: string;
  };
}

export interface BoundingBox {
  pageNumber: number;
  polygon: number[];  // 8 elements in inches
  pageWidthInches: number;
  pageHeightInches: number;
}

// =============================================================================
// CLASSIFICATION REVIEW TYPES
// =============================================================================

export type ClassificationReviewStatus = "pending" | "confirmed" | "overridden";

export interface ClassificationDoc {
  doc_id: string;
  claim_id: string;
  filename: string;
  predicted_type: string;
  confidence: number;
  signals: string[];
  review_status: ClassificationReviewStatus;
  doc_type_truth: string | null;
}

export interface ClassificationDetail {
  doc_id: string;
  claim_id: string;
  filename: string;
  predicted_type: string;
  confidence: number;
  signals: string[];
  summary: string;
  key_hints: Record<string, string> | null;
  language: string;
  pages_preview: string;
  has_pdf: boolean;
  has_image: boolean;
  existing_label: {
    doc_type_correct: boolean;
    doc_type_truth: string | null;
    notes: string;
  } | null;
}

export interface DocTypeCatalogEntry {
  doc_type: string;
  description: string;
  cues: string[];
}

export interface ClassificationLabelRequest {
  claim_id: string;
  doc_type_correct: boolean;
  doc_type_truth?: string | null;
  notes?: string;
}

export interface ConfusionMatrixEntry {
  predicted: string;
  truth: string;
  count: number;
}

export interface ClassificationStats {
  docs_total: number;
  docs_reviewed: number;
  overrides_count: number;
  avg_confidence: number;
  by_predicted_type: Record<string, { count: number; override_count: number }>;
  confusion_matrix: ConfusionMatrixEntry[];
}

// =============================================================================
// UPLOAD & PIPELINE TYPES
// =============================================================================

export interface PendingDocument {
  doc_id: string;
  original_filename: string;
  file_size: number;
  content_type: string;
  upload_time: string;
}

export interface PendingClaim {
  claim_id: string;
  created_at: string;
  documents: PendingDocument[];
}

export type DocPipelinePhase =
  | "pending"
  | "ingesting"
  | "classifying"
  | "extracting"
  | "done"
  | "failed";

export interface DocProgress {
  doc_id: string;
  claim_id: string;
  filename: string;
  phase: DocPipelinePhase;
  failed_at_stage?: DocPipelinePhase;  // Which stage failed (ingesting/classifying/extracting)
  error?: string;
}

export type PipelineBatchStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

/** @deprecated Use PipelineBatchStatus instead */
export type PipelineRunStatus = PipelineBatchStatus;

export interface PipelineBatch {
  batch_id: string;
  status: PipelineBatchStatus;
  claim_ids: string[];
  started_at?: string;
  completed_at?: string;
  doc_count?: number;
  summary?: {
    total: number;
    success: number;
    failed: number;
  };
  docs?: Record<string, DocProgress>;
}

/** @deprecated Use PipelineBatch instead */
export type PipelineRun = PipelineBatch;

export type WebSocketMessageType =
  | "sync"
  | "doc_progress"
  | "batch_complete"
  | "batch_cancelled"
  | "run_complete"    // deprecated - use batch_complete
  | "run_cancelled"   // deprecated - use batch_cancelled
  | "ping";

export interface WebSocketMessage {
  type: WebSocketMessageType;
  batch_id?: string;
  run_id?: string;  // deprecated - use batch_id
  doc_id?: string;
  phase?: DocPipelinePhase;
  failed_at_stage?: DocPipelinePhase;
  error?: string;
  status?: PipelineBatchStatus;
  docs?: Record<string, DocProgress>;
  summary?: {
    total: number;
    success: number;
    failed: number;
  };
}

// =============================================================================
// PIPELINE CONTROL CENTER TYPES
// =============================================================================

export interface PipelineClaimOption {
  claim_id: string;
  doc_count: number;
  last_run?: string;
  last_run_id?: string;
  is_pending: boolean;
}

export interface PipelineRunError {
  doc: string;
  stage: string;
  message: string;
}

export interface EnhancedPipelineRun {
  run_id: string;
  friendly_name: string;
  status: PipelineBatchStatus;
  claim_ids: string[];
  claims_count: number;
  docs_total: number;
  docs_processed: number;
  started_at?: string;
  completed_at?: string;
  duration_seconds?: number;
  stage_progress: {
    ingest: number;
    classify: number;
    extract: number;
  };
  stage_timings: Record<string, string>;
  reuse: Record<string, number>;
  cost_estimate_usd?: number;
  prompt_config?: string;
  errors: PipelineRunError[];
  summary?: {
    total: number;
    success: number;
    failed: number;
  };
  model: string;
}

export interface PromptConfig {
  id: string;
  name: string;
  model: string;
  temperature: number;
  max_tokens: number;
  is_default: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface CreatePromptConfigRequest {
  name: string;
  model?: string;
  temperature?: number;
  max_tokens?: number;
}

export interface UpdatePromptConfigRequest {
  name?: string;
  model?: string;
  temperature?: number;
  max_tokens?: number;
}

export interface AuditEntry {
  timestamp: string;
  user: string;
  action: string;
  action_type: string;
  entity_type: string;
  entity_id: string;
}

export interface AuditListParams {
  action_type?: string;
  entity_type?: string;
  since?: string;
  limit?: number;
}

export interface StartPipelineRequest {
  claim_ids: string[];
  model?: string;
  stages?: string[];
  prompt_config_id?: string;
  force_overwrite?: boolean;
  compute_metrics?: boolean;
  dry_run?: boolean;
}

// =============================================================================
// COMPLIANCE TYPES
// =============================================================================

export type DecisionType = "classification" | "extraction" | "human_review" | "override";

export interface DecisionRationale {
  summary: string | null;
  confidence: number | null;
}

export interface DecisionRecord {
  decision_id: string;
  decision_type: DecisionType;
  timestamp: string;
  claim_id: string | null;
  doc_id: string | null;
  actor_type: string | null;
  actor_id: string | null;
  rationale: DecisionRationale;
  prev_hash: string | null;
}

export interface VerificationResult {
  valid: boolean;
  total_records: number;
  break_at_index: number | null;
  break_at_decision_id: string | null;
  error_type: string | null;
  error_details: string | null;
  verified_at: string;
}

export interface VersionBundle {
  bundle_id: string;
  run_id: string;
  created_at: string;
  git_commit: string | null;
  git_dirty: boolean | null;
  contextbuilder_version: string;
  extractor_version: string;
  model_name: string;
  model_version: string | null;
  prompt_template_hash: string | null;
  extraction_spec_hash: string | null;
}

export interface VersionBundleSummary {
  run_id: string;
  bundle_id: string;
  created_at: string;
  git_commit: string | null;
  git_dirty: boolean | null;
  model_name: string;
  extractor_version: string;
}

export interface ConfigHistoryEntry {
  timestamp: string;
  action: string;
  config_id: string;
  user?: string;
  changes?: Record<string, unknown>;
}

export interface TruthHistoryVersion {
  version_number: number | null;
  saved_at: string | null;
  reviewer: string | null;
  field_count: number;
}

export interface TruthHistory {
  file_md5: string;
  version_count: number;
  versions: TruthHistoryVersion[];
}

export interface LabelHistoryVersion {
  version_number: number | null;
  saved_at: string | null;
  reviewer: string | null;
  field_count: number;
}

export interface LabelHistory {
  doc_id: string;
  version_count: number;
  versions: LabelHistoryVersion[];
}

// =============================================================================
// APPLICATION VERSION
// =============================================================================

export interface VersionInfo {
  version: string;
  git_commit: string | null;
  display: string;
}
