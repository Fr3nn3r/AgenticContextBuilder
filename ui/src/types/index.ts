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
  // Display fields
  source_type: string;
  page_count: number;
}

export interface PageContent {
  page: number;
  text: string;
  text_md5: string;
}

/** Reference to a specific table cell */
export interface CellReference {
  tableIndex: number;
  rowIndex: number;
  columnIndex: number;
}

export interface FieldProvenance {
  page: number;
  method: string;
  text_quote: string;
  char_start: number;
  char_end: number;
  /** Reference to specific table cell when value comes from a table (P1.1) */
  cell_ref?: CellReference | null;
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
  /** Complex structured data (line_items, nested objects) that cannot be represented as simple field values */
  structured_data?: Record<string, unknown>;
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
  validation?: string;
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
  polygon: number[];  // 8 elements (in inches for PDFs, pixels for images)
  pageWidthInches: number;   // Page width (inches for PDFs, pixels for images)
  pageHeightInches: number;  // Page height (inches for PDFs, pixels for images)
  unit?: "inch" | "pixel";   // Coordinate unit from Azure DI (defaults to "inch")
}

// =============================================================================
// SMART HIGHLIGHTING TYPES (Extended Azure DI)
// =============================================================================

/** A text span in the document content */
export interface AzureDISpan {
  offset: number;
  length: number;
}

/** A line detected by Azure DI with polygon bounds */
export interface AzureDILine {
  content: string;
  polygon: number[];  // 8-element array in inches
  spans: AzureDISpan[];
}

/** A bounding region with page number and polygon */
export interface AzureDIBoundingRegion {
  pageNumber: number;
  polygon: number[];  // 8-element array in inches
}

/** A paragraph detected by Azure DI */
export interface AzureDIParagraph {
  content: string;
  spans: AzureDISpan[];
  boundingRegions: AzureDIBoundingRegion[];
}

/** A table cell detected by Azure DI */
export interface AzureDITableCell {
  rowIndex: number;
  columnIndex: number;
  rowSpan?: number;
  columnSpan?: number;
  content: string;
  boundingRegions: AzureDIBoundingRegion[];
  spans: AzureDISpan[];
  kind?: "columnHeader" | "rowHeader" | "stubHead" | "description";
}

/** A table detected by Azure DI */
export interface AzureDITable {
  rowCount: number;
  columnCount: number;
  cells: AzureDITableCell[];
  boundingRegions?: AzureDIBoundingRegion[];
  spans?: AzureDISpan[];
}

/** Extended page with lines array */
export interface AzureDIPageExtended extends AzureDIPage {
  lines?: AzureDILine[];
}

/** Extended Azure DI output with full structure */
export interface AzureDIOutputExtended {
  raw_azure_di_output: {
    pages: AzureDIPageExtended[];
    content: string;
    paragraphs?: AzureDIParagraph[];
    tables?: AzureDITable[];
  };
}

/** Highlight source type for visual distinction */
export type HighlightSource = "word" | "line" | "cell" | "merged";

/** Extended bounding box with source metadata */
export interface SmartBoundingBox extends BoundingBox {
  source: HighlightSource;
  confidence?: number;
  cellRef?: {
    tableIndex: number;
    rowIndex: number;
    columnIndex: number;
  };
}

/** Options for smart highlight computation */
export interface SmartHighlightOptions {
  lineCoverageThreshold?: number;  // default: 0.80
  wordGapThreshold?: number;       // default: 0.3 inches
  lineYThreshold?: number;         // default: 0.05 inches
  enableTableDetection?: boolean;  // default: true
  enableLinePreference?: boolean;  // default: true
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
  file_md5?: string;
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
  file_md5?: string;  // MD5 hash of file content
}

export type PipelineBatchStatus =
  | "pending"
  | "running"
  | "assessing"
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
  | "assessment_starting"
  | "assessment_stage"
  | "assessment_complete"
  | "assessment_error"
  | "all_assessments_complete"
  | "error"
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
  // Assessment fields (auto-assess via pipeline WS)
  claim_ids?: string[];
  claim_id?: string;
  stage?: string;
  decision?: string;
  assessment_id?: string;
  results?: Array<{ claim_id: string; decision: string; assessment_id: string }>;
  message?: string;  // Error message from server
}

// =============================================================================
// ASSESSMENT PROGRESS TYPES (Auto-assess via pipeline WebSocket)
// =============================================================================

export type AssessmentPhase =
  | "pending"
  | "reconciliation"
  | "enrichment"
  | "screening"
  | "processing"
  | "decision"
  | "complete"
  | "error";

export interface ClaimAssessmentProgress {
  claim_id: string;
  phase: AssessmentPhase;
  decision?: string;
  assessment_id?: string;
  error?: string;
  failed_at_stage?: AssessmentPhase;
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
  auto_assess?: boolean;
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

// =============================================================================
// EVOLUTION TYPES
// =============================================================================

/** Single point in the pipeline evolution timeline */
export interface EvolutionDataPoint {
  spec_hash: string;
  first_seen: string;
  last_seen: string;
  bundle_count: number;

  // Scope metrics
  doc_types_count: number;
  doc_types_list: string[];
  total_fields: number;
  fields_by_type: Record<string, number>;

  // Accuracy metrics
  representative_run_id: string;
  accuracy_rate: number | null;
  correct_count: number;
  incorrect_count: number;
  missing_count: number;
  docs_evaluated: number;

  // Version info
  model_name: string;
  contextbuilder_version: string;
  git_commit: string | null;
}

/** Scope growth metrics */
export interface ScopeGrowth {
  start_doc_types: number;
  end_doc_types: number;
  start_fields: number;
  end_fields: number;
  doc_types_added: string[];
  fields_delta: number;
}

/** Accuracy trend metrics */
export interface AccuracyTrend {
  start_accuracy: number | null;
  end_accuracy: number | null;
  delta: number | null;
  trend: "improving" | "stable" | "regressing" | "no_data";
}

/** A doc type's appearance at a specific spec version */
export interface DocTypeAppearance {
  spec_hash: string;
  field_count: number;
  accuracy_rate: number | null;
}

/** Evolution of a single doc type across versions */
export interface DocTypeEvolution {
  doc_type: string;
  first_version: string;
  current_fields: number;
  appearances: DocTypeAppearance[];
}

/** Complete evolution summary for the dashboard */
export interface EvolutionSummary {
  timeline: EvolutionDataPoint[];
  spec_versions: string[];
  scope_growth: ScopeGrowth;
  accuracy_trend: AccuracyTrend;
  doc_type_matrix: DocTypeEvolution[];
}

/** Doc type matrix response */
export interface DocTypeMatrixResponse {
  doc_types: DocTypeEvolution[];
  spec_versions: string[];
}

// =============================================================================
// CLAIM FACTS TYPES (Aggregated Facts from Context Folder)
// =============================================================================

/** Provenance info for where a fact was extracted from */
export interface FactProvenance {
  doc_id: string;
  doc_type: string;
  page: number | null;
  text_quote: string | null;
  char_start: number | null;
  char_end: number | null;
}

/** A single aggregated fact for a claim */
export interface AggregatedFact {
  name: string;
  value: string | string[] | null;
  confidence: number;
  selected_from: FactProvenance;
  /** Complex structured data like service_entries, line_items arrays */
  structured_value?: unknown;
}

/** Source document reference in claim facts */
export interface ClaimFactSource {
  doc_id: string;
  filename: string;
  doc_type: string;
}

/** Complete claim facts response from context folder */
export interface ClaimFacts {
  schema_version: string;
  claim_id: string;
  generated_at: string;
  /** Claim run ID that produced these facts (e.g., clm_20260127_154350_b84503) */
  claim_run_id?: string;
  /** Extraction runs used to aggregate these facts */
  extraction_runs_used?: string[];
  facts: AggregatedFact[];
  sources: ClaimFactSource[];
}

// =============================================================================
// CLAIM RUN & RECONCILIATION TYPES
// =============================================================================

/** Manifest for a claim run (reconciliation version) */
export interface ClaimRunManifest {
  claim_run_id: string;
  created_at: string;
  stages_completed: string[];
  extraction_runs_considered: string[];
  contextbuilder_version?: string;
}

/** Gate status from reconciliation */
export interface ReconciliationGate {
  status: "pass" | "warn" | "fail";
  missing_critical_facts: string[];
  conflict_count: number;
  provenance_coverage: number;
  estimated_tokens: number;
  reasons: string[];
}

/** Source document info for a conflicting value */
export interface ConflictSource {
  doc_id: string;
  doc_type: string;
  filename: string;
}

/** A conflict between values from different sources */
export interface FactConflict {
  fact_name: string;
  values: string[];
  sources: ConflictSource[][];
  selected_value: string;
  selected_confidence: number;
  selection_reason: string;
}

/** Full reconciliation report for a claim run */
export interface ReconciliationReport {
  schema_version: string;
  claim_id: string;
  claim_run_id: string;
  generated_at: string;
  gate: ReconciliationGate;
  conflicts: FactConflict[];
  fact_count: number;
  critical_facts_spec: string[];
  critical_facts_present: string[];
}

/** Provenance for a service entry with row-level positioning (P0.1) */
export interface ServiceEntryProvenance {
  doc_id: string;
  doc_type: string;
  filename: string;
  run_id: string;
  /** Page number where item was found */
  page?: number | null;
  /** Character start offset in page text */
  char_start?: number | null;
  /** Character end offset in page text */
  char_end?: number | null;
  /** Text snippet containing the value */
  text_quote?: string | null;
  /** Index of the table on the page */
  table_index?: number | null;
  /** Row index within the table */
  row_index?: number | null;
}

/** Service entry from structured_value */
export interface ServiceEntry {
  date?: string | null;
  mileage?: string | number | null;
  service_type?: string | null;
  provider?: string | null;
  work_performed?: string | null;
  cost?: string | number | null;
  /** Row-level provenance for this service entry (P0.1) */
  provenance?: ServiceEntryProvenance | null;
  [key: string]: unknown;
}

// =============================================================================
// COVERAGE ANALYSIS TYPES
// =============================================================================

export type CoverageStatus = "covered" | "not_covered" | "review_needed";
export type MatchMethod = "rule" | "part_number" | "keyword" | "llm" | "manual";
export type TraceAction =
  | "matched"
  | "skipped"
  | "deferred"
  | "overridden"
  | "promoted"
  | "demoted"
  | "excluded"
  | "validated";

export interface TraceStep {
  stage: string;
  action: TraceAction;
  verdict?: CoverageStatus | null;
  confidence?: number | null;
  reasoning: string;
  detail?: Record<string, unknown> | null;
}

export interface LineItemCoverage {
  item_code: string | null;
  description: string;
  item_type: string;
  total_price: number;
  coverage_status: CoverageStatus;
  coverage_category: string | null;
  matched_component: string | null;
  match_method: MatchMethod;
  match_confidence: number;
  match_reasoning: string;
  exclusion_reason: string | null;
  decision_trace?: TraceStep[] | null;
  covered_amount: number;
  not_covered_amount: number;
}

export interface CoverageSummary {
  total_claimed: number;
  total_covered_before_excess: number;
  total_not_covered: number;
  excess_amount: number;
  total_payable: number;
  items_covered: number;
  items_not_covered: number;
  items_review_needed: number;
  coverage_percent: number | null;
}

export interface NonCoveredExplanation {
  exclusion_reason: string;
  items: string[];
  item_codes: (string | null)[];
  category: string | null;
  total_amount: number;
  explanation: string;
  policy_reference: string | null;
  match_confidence: number;
}

export interface PrimaryRepairResult {
  component: string | null;
  category: string | null;
  description: string | null;
  is_covered: boolean | null;
  confidence: number;
  determination_method: "deterministic" | "repair_context" | "llm" | "none";
}

export interface CoverageAnalysisResult {
  schema_version: string;
  claim_id: string;
  claim_run_id: string | null;
  generated_at: string;
  line_items: LineItemCoverage[];
  summary: CoverageSummary;
  primary_repair: PrimaryRepairResult | null;
  repair_context: PrimaryRepairResult | null;
  non_covered_explanations: NonCoveredExplanation[] | null;
  non_covered_summary: string | null;
}

// =============================================================================
// ASSESSMENT TYPES
// =============================================================================

/** Assessment check result status */
export type CheckResult = "PASS" | "FAIL" | "INCONCLUSIVE";

/** Assessment decision outcome */
export type AssessmentDecision = "APPROVE" | "REJECT" | "REFER_TO_HUMAN";

/** Assumption impact level */
export type AssumptionImpact = "high" | "medium" | "low";

/** Payout breakdown showing step-by-step calculation */
export interface PayoutBreakdown {
  total_claimed: number | null;
  non_covered_deductions: number | null;
  covered_subtotal: number | null;
  coverage_percent: number | null;
  after_coverage: number | null;
  deductible: number | null;
  final_payout: number | null;
  currency: string | null;
}

/** Single assessment check */
export interface AssessmentCheck {
  check_number: number;
  check_name: string;
  result: CheckResult;
  details: string;
  evidence_refs: string[];
}

/** Assumption made during assessment */
export interface AssessmentAssumption {
  check_number: number;
  field: string;
  assumed_value: string;
  reason: string;
  impact: AssumptionImpact;
}

/** Fraud indicator detected */
export interface FraudIndicator {
  indicator: string;
  severity: "high" | "medium" | "low";
  details: string;
}

/** Full claim assessment data */
export interface ClaimAssessment {
  claim_id: string;
  decision: AssessmentDecision;
  confidence_score: number;
  checks: AssessmentCheck[];
  assumptions: AssessmentAssumption[];
  payout?: number;
  currency?: string | null;
  payout_breakdown?: PayoutBreakdown | null;
  decision_rationale?: string | null;
  fraud_indicators: FraudIndicator[];
  recommendations: string[];
  assessed_at?: string;
}

/** Assessment evaluation confusion matrix */
export interface AssessmentConfusionMatrix {
  matrix: Record<string, Record<string, number>>;
  total_evaluated: number;
  decision_accuracy: number;
}

/** Per-claim evaluation result */
export interface AssessmentEvalResult {
  claim_id: string;
  predicted: AssessmentDecision;
  actual: AssessmentDecision;
  is_correct: boolean;
  confidence_score: number;
  assumption_count: number;
}

/** Summary metrics for assessment evaluation */
export interface AssessmentEvalSummary {
  total_claims: number;
  correct_count?: number;
  accuracy_rate: number;
  approve_precision: number;
  reject_precision: number;
  refer_rate: number;
  avg_confidence?: number;
}

/** Full assessment evaluation response */
export interface AssessmentEvaluation {
  eval_id: string;
  timestamp: string;
  run_id?: string;
  confusion_matrix: AssessmentConfusionMatrix;
  results: AssessmentEvalResult[];
  summary: AssessmentEvalSummary;
}

// =============================================================================
// RECONCILIATION EVALUATION TYPES
// =============================================================================

/** Gate status for reconciliation */
export type ReconciliationGateStatus = "pass" | "warn" | "fail";

/** Per-claim result in reconciliation evaluation */
export interface ReconciliationClaimResult {
  claim_id: string;
  gate_status: ReconciliationGateStatus;
  fact_count: number;
  conflict_count: number;
  missing_critical_count: number;
  missing_critical_facts: string[];
  provenance_coverage: number;
  reasons: string[];
}

/** Frequency count for a fact (missing or conflicting) */
export interface FactFrequency {
  fact_name: string;
  count: number;
  claim_ids: string[];
}

/** Summary statistics for reconciliation evaluation */
export interface ReconciliationEvalSummary {
  total_claims: number;
  passed: number;
  warned: number;
  failed: number;
  pass_rate: number;
  pass_rate_percent: string;
  avg_fact_count: number;
  avg_conflicts: number;
  avg_missing_critical: number;
  total_conflicts: number;
}

/** Full reconciliation evaluation response */
export interface ReconciliationEvaluation {
  schema_version: string;
  evaluated_at: string;
  run_id?: string;
  summary: ReconciliationEvalSummary;
  top_missing_facts: FactFrequency[];
  top_conflicts: FactFrequency[];
  results: ReconciliationClaimResult[];
}

/** Triage queue priority level */
export type TriagePriority = "critical" | "high" | "medium" | "low";

/** Triage reason category */
export type TriageReason =
  | "low_confidence"
  | "high_impact_assumption"
  | "fraud_indicator"
  | "inconclusive_check"
  | "conflicting_evidence";

/** Item in the triage queue */
export interface TriageQueueItem {
  claim_id: string;
  priority: TriagePriority;
  reasons: TriageReason[];
  confidence_score: number;
  assumption_count: number;
  decision: AssessmentDecision;
  fraud_indicator_count: number;
  created_at: string;
}

/** Filters for triage queue */
export interface TriageQueueFilters {
  priority?: TriagePriority[];
  reasons?: TriageReason[];
  decision?: AssessmentDecision[];
  min_confidence?: number;
  max_confidence?: number;
}

// =============================================================================
// TOKEN COST TYPES
// =============================================================================

/** Overall token usage and cost summary */
export interface CostOverview {
  total_cost_usd: number;
  total_tokens: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_calls: number;
  docs_processed: number;
  avg_cost_per_doc: number;
  avg_cost_per_call: number;
  primary_model: string;
}

/** Token usage and costs by operation type */
export interface CostByOperation {
  operation: string;  // "classification" | "extraction" | "vision_ocr" | etc.
  tokens: number;
  prompt_tokens: number;
  completion_tokens: number;
  cost_usd: number;
  call_count: number;
  percentage: number;
}

/** Token usage and costs per pipeline run */
export interface CostByRun {
  run_id: string;
  timestamp: string | null;
  model: string | null;
  claims_count: number;
  docs_count: number;
  tokens: number;
  cost_usd: number;
  avg_cost_per_doc: number;
}

/** Token costs per claim */
export interface CostByClaim {
  claim_id: string;
  docs_count: number;
  tokens: number;
  cost_usd: number;
}

/** Token costs per document */
export interface CostByDoc {
  doc_id: string;
  claim_id: string | null;
  tokens: number;
  cost_usd: number;
  operations: string[];
}

/** Daily token costs for trend chart */
export interface CostByDay {
  date: string;  // YYYY-MM-DD
  tokens: number;
  cost_usd: number;
  call_count: number;
}

/** Token usage and costs by model */
export interface CostByModel {
  model: string;
  tokens: number;
  cost_usd: number;
  call_count: number;
  percentage: number;
}

// =============================================================================
// DASHBOARD TYPES
// =============================================================================

export interface DashboardClaimDoc {
  doc_id: string;
  filename: string;
  doc_type: string;
  extraction_run_id: string | null;
}

export interface DashboardClaim {
  claim_id: string;
  folder_name: string;
  claim_date: string | null;
  doc_count: number;
  // Assessment
  decision: string | null;
  confidence: number | null;
  result_code: string | null;
  inconclusive_warnings: string[];
  checks_passed: number;
  checks_failed: number;
  checks_inconclusive: number;
  payout: number | null;
  currency: string;
  assessment_method: string | null;
  claim_run_id: string | null;
  // Ground truth
  gt_decision: string | null;
  gt_payout: number | null;
  gt_denial_reason: string | null;
  gt_vehicle: string | null;
  gt_coverage_notes: string | null;
  decision_match: boolean | null;
  payout_diff: number | null;
  has_ground_truth_doc: boolean;
  // Dataset
  dataset_id: string | null;
  dataset_label: string | null;
  // Documents
  documents: DashboardClaimDoc[];
}

export interface DashboardClaimDetail {
  claim_id: string;
  coverage_items: Array<Record<string, unknown>>;
  coverage_summary: Record<string, unknown> | null;
  payout_calculation: Record<string, unknown> | null;
  gt_parts_approved: number | null;
  gt_labor_approved: number | null;
  gt_total_material_labor: number | null;
  gt_vat_rate_pct: number | null;
  gt_deductible: number | null;
  gt_total_approved: number | null;
  gt_reimbursement_rate_pct: number | null;
  screening_checks: Array<Record<string, unknown>>;
  assessment_checks: Array<Record<string, unknown>>;
  // Parts/labor breakdown (computed at read time)
  sys_parts_gross: number | null;
  sys_labor_gross: number | null;
  sys_parts_adjusted: number | null;
  sys_labor_adjusted: number | null;
  sys_total_adjusted: number | null;
  sys_vat_rate_pct: number | null;
  sys_vat_amount: number | null;
  gt_vat_amount: number | null;
  screening_payout: Record<string, unknown> | null;
}

// ── Decision Dossier Types ────────────────────────────────────────

export type ClaimVerdictType = "APPROVE" | "DENY" | "REFER";
export type LineItemVerdictType = "COVERED" | "DENIED" | "PARTIAL" | "REFER";
export type EvaluabilityTierType = 1 | 2 | 3;
export type ClauseEvaluationLevelType = "claim" | "line_item" | "claim_with_item_consequence";

export interface DenialClauseDefinition {
  reference: string;
  text: string;
  short_name: string;
  category: string;
  evaluation_level: ClauseEvaluationLevelType;
  evaluability_tier: EvaluabilityTierType;
  default_assumption: boolean;
  assumption_question: string | null;
}

export interface ClauseEvidence {
  fact_name: string;
  fact_value: string | null;
  source_doc_id: string | null;
  screening_check_id: string | null;
  description: string | null;
}

export interface ClauseEvaluation {
  clause_reference: string;
  clause_short_name: string;
  category: string;
  evaluation_level: ClauseEvaluationLevelType;
  evaluability_tier: EvaluabilityTierType;
  verdict: string;
  assumption_used: boolean | null;
  evidence: ClauseEvidence[];
  reason: string;
  affected_line_items: string[];
}

export interface LineItemDecision {
  item_id: string;
  description: string;
  item_type: string;
  verdict: LineItemVerdictType;
  applicable_clauses: string[];
  denial_reasons: string[];
  claimed_amount: number;
  approved_amount: number;
  denied_amount: number;
  adjusted_amount: number;
  adjustment_reason: string | null;
}

export interface AssumptionRecord {
  clause_reference: string;
  question: string;
  assumed_value: boolean;
  adjuster_confirmed: boolean;
  tier: EvaluabilityTierType;
}

export interface FinancialSummary {
  total_claimed: number;
  total_covered: number;
  total_denied: number;
  total_adjusted: number;
  net_payout: number;
  currency: string;
  parts_total: number;
  labor_total: number;
  fees_total: number;
  other_total: number;
}

// =============================================================================
// CONFIDENCE INDEX TYPES (CCI)
// =============================================================================

export type ConfidenceBand = "high" | "moderate" | "low";

export interface ConfidenceIndex {
  composite_score: number;
  band: ConfidenceBand;
  components: Record<string, number>;
}

export interface SignalSnapshot {
  signal_name: string;
  raw_value: number | null;
  normalized_value: number;
  source_stage: string;
  description: string;
}

export interface ComponentScore {
  component: string;
  score: number;
  weight: number;
  weighted_contribution: number;
  signals_used: SignalSnapshot[];
  notes: string;
}

export interface ConfidenceSummary {
  schema_version: string;
  claim_id: string;
  claim_run_id: string;
  composite_score: number;
  band: ConfidenceBand;
  component_scores: ComponentScore[];
  weights_used: Record<string, number>;
  signals_collected: SignalSnapshot[];
  stages_available: string[];
  stages_missing: string[];
  flags: string[];
}

export interface DecisionDossier {
  schema_version: string;
  claim_id: string;
  version: number;
  claim_verdict: ClaimVerdictType;
  verdict_reason: string;
  clause_evaluations: ClauseEvaluation[];
  line_item_decisions: LineItemDecision[];
  assumptions_used: AssumptionRecord[];
  financial_summary: FinancialSummary | null;
  engine_id: string;
  engine_version: string;
  evaluation_timestamp: string;
  input_refs: Record<string, unknown>;
  failed_clauses: string[];
  unresolved_assumptions: string[];
  coverage_overrides?: Record<string, boolean>;
  confidence_index?: ConfidenceIndex | null;
}

export interface DossierVersionMeta {
  version: number;
  claim_verdict: ClaimVerdictType | null;
  evaluation_timestamp: string | null;
  engine_id: string | null;
  failed_clauses_count: number;
  unresolved_count: number;
  claim_run_id: string | null;
  filename: string;
}
