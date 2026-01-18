/**
 * Centralized terminology definitions for contextual help tooltips.
 * These definitions surface documentation to users directly in the UI.
 */

export interface TermDefinition {
  /** Display name of the term */
  term: string;
  /** Brief definition shown in tooltip */
  definition: string;
  /** Category for potential grouping/filtering */
  category: "pipeline" | "quality" | "field" | "labeling" | "compliance";
}

export const terminology: Record<string, TermDefinition> = {
  // ============================================
  // PIPELINE STAGES
  // ============================================
  ingestion: {
    term: "Ingestion",
    definition:
      "Extract text from raw documents (PDFs, images) into machine-readable format using OCR or document intelligence.",
    category: "pipeline",
  },
  classification: {
    term: "Classification",
    definition:
      "Determine document type (e.g., FNOL, invoice, police report) using LLM-based routing to apply correct extraction rules.",
    category: "pipeline",
  },
  extraction: {
    term: "Extraction",
    definition:
      "Extract structured fields from classified documents and track their source locations (provenance) for verification.",
    category: "pipeline",
  },
  qualityGate: {
    term: "Quality Gate",
    definition:
      "Automated assessment of extraction results. PASS = all required fields found. WARN = some issues. FAIL = critical gaps.",
    category: "pipeline",
  },

  // ============================================
  // QUALITY GATE STATUSES
  // ============================================
  pass: {
    term: "PASS",
    definition:
      "All required fields were successfully extracted with acceptable confidence levels.",
    category: "quality",
  },
  warn: {
    term: "WARN",
    definition:
      "Some issues detected (missing optional fields or low confidence) but processing can continue.",
    category: "quality",
  },
  fail: {
    term: "FAIL",
    definition:
      "Critical required fields are missing or extraction quality is below acceptable thresholds.",
    category: "quality",
  },

  // ============================================
  // QUALITY METRICS
  // ============================================
  evidenceRate: {
    term: "Evidence Rate",
    definition:
      "Percentage of extracted fields that have verifiable source locations (provenance) in the original document.",
    category: "quality",
  },
  confidence: {
    term: "Confidence",
    definition:
      "Score (0-100%) indicating extraction certainty. Green: 90%+, Amber: 70-89%, Red: below 70%.",
    category: "quality",
  },
  classificationConfidence: {
    term: "Classification Confidence",
    definition:
      "How certain the model is about the document type. Green (90%+): high, Amber (70-89%): moderate, Red (<70%): low.",
    category: "quality",
  },
  extractionConfidence: {
    term: "Extraction Confidence",
    definition:
      "How certain the model is about this extracted field value. Higher values indicate more reliable extraction.",
    category: "quality",
  },
  labelCoverage: {
    term: "Label Coverage",
    definition:
      "Ratio of documents with human-verified labels to total documents in the run.",
    category: "quality",
  },
  extractionCoverage: {
    term: "Extraction Coverage",
    definition:
      "Ratio of documents with completed extraction to total documents in the run.",
    category: "quality",
  },

  // ============================================
  // FIELD-LEVEL CONCEPTS
  // ============================================
  presence: {
    term: "Presence",
    definition:
      "Whether a field was found in the document. Values: present (found), missing (not found), or uncertain (unclear).",
    category: "field",
  },
  provenance: {
    term: "Provenance",
    definition:
      "The source location of an extracted value: page number, character position, and exact text quote from the document.",
    category: "field",
  },
  extractedValue: {
    term: "Extracted Value",
    definition:
      "The value automatically extracted by the system from the document for this field.",
    category: "field",
  },
  truthValue: {
    term: "Truth Value",
    definition:
      "The correct value for a field as verified by a human reviewer, used to evaluate extraction accuracy.",
    category: "field",
  },
  requiredField: {
    term: "Required Field",
    definition:
      "A field that must be present for the document to pass the quality gate. Missing required fields cause FAIL status.",
    category: "field",
  },

  // ============================================
  // LABELING STATES
  // ============================================
  labeled: {
    term: "Labeled",
    definition:
      "A field or document that has been reviewed and assigned a verified truth value by a human.",
    category: "labeling",
  },
  unlabeled: {
    term: "Unlabeled",
    definition:
      "A field or document that has not yet been reviewed or assigned a truth value.",
    category: "labeling",
  },
  unverifiable: {
    term: "Unverifiable",
    definition:
      "A field that cannot be verified due to document quality, wrong doc type, or the field not being present.",
    category: "labeling",
  },
  confirmed: {
    term: "Confirmed",
    definition:
      "The extracted value has been verified as correct by a human reviewer.",
    category: "labeling",
  },
  overridden: {
    term: "Overridden",
    definition:
      "The system's classification or extraction was corrected by a human reviewer.",
    category: "labeling",
  },

  // ============================================
  // LABELING OUTCOMES
  // ============================================
  correct: {
    term: "Correct",
    definition:
      "The extracted value exactly matches the human-verified truth value.",
    category: "labeling",
  },
  incorrect: {
    term: "Incorrect",
    definition:
      "The extracted value differs from the human-verified truth value.",
    category: "labeling",
  },
  missing: {
    term: "Missing",
    definition:
      "The system failed to extract a value that exists in the document.",
    category: "labeling",
  },

  // ============================================
  // COMPLIANCE & TRACEABILITY
  // ============================================
  decisionLedger: {
    term: "Decision Ledger",
    definition:
      "Tamper-evident audit log of all system decisions (classifications, extractions, human reviews) for compliance.",
    category: "compliance",
  },
  llmAudit: {
    term: "LLM Audit",
    definition:
      "Complete capture of all API calls to language models, including prompts, responses, and token usage.",
    category: "compliance",
  },
  versionBundle: {
    term: "Version Bundle",
    definition:
      "Reproducibility snapshot linking extraction results to their code version, model, and configuration state.",
    category: "compliance",
  },

  // ============================================
  // DOCUMENT TYPES
  // ============================================
  fnolForm: {
    term: "FNOL Form",
    definition:
      "First Notice of Loss - the initial claim report or incident notification filed by the policyholder.",
    category: "pipeline",
  },
  insurancePolicy: {
    term: "Insurance Policy",
    definition:
      "Document showing coverage details, terms, conditions, and policy limits.",
    category: "pipeline",
  },
  policeReport: {
    term: "Police Report",
    definition:
      "Official law enforcement report documenting an incident or accident.",
    category: "pipeline",
  },
  medicalReport: {
    term: "Medical Report",
    definition:
      "Medical documentation including doctor's reports, diagnoses, and hospital records.",
    category: "pipeline",
  },
  damageEvidence: {
    term: "Damage Evidence",
    definition:
      "Photographic evidence of damage to property or vehicles supporting the claim.",
    category: "pipeline",
  },
} as const;

/**
 * Type for valid terminology keys
 */
export type TermKey = keyof typeof terminology;

/**
 * Helper to get a term definition safely
 */
export function getTerm(key: string): TermDefinition | undefined {
  return terminology[key as TermKey];
}
