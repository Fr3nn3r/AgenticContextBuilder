// API Types for Extraction QA Console

export interface ClaimSummary {
  claim_id: string;
  folder_name: string;
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
  // Extraction-centric fields
  gate_pass_count: number;
  gate_warn_count: number;
  gate_fail_count: number;
  needs_vision_count: number;
  last_processed: string | null;
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
  text_quality: "good" | "warn" | "poor" | null;
  missing_required_fields: string[];
  needs_vision: boolean;
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
  needs_vision_fallback: boolean;
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

export interface FieldLabel {
  field_name: string;
  judgement: "correct" | "incorrect" | "unknown";
  correct_value?: string;
  notes: string;
}

export interface DocLabels {
  doc_type_correct: boolean;
  text_readable: "good" | "warn" | "poor";
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
}

export interface RunSummary {
  run_dir: string;
  total_claims: number;
  total_docs: number;
  extracted_count: number;
  labeled_count: number;
  quality_gate: Record<string, number>;
}
