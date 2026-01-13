import type { ExtractedField, FieldLabel } from "../types";

export function makeExtractedField(overrides: Partial<ExtractedField> = {}): ExtractedField {
  return {
    name: "policy_number",
    value: "PN123",
    normalized_value: "PN123",
    confidence: 0.9,
    status: "present",
    provenance: [
      {
        page: 1,
        method: "ocr",
        text_quote: "Policy Number: PN123",
        char_start: 0,
        char_end: 10,
      },
    ],
    value_is_placeholder: false,
    ...overrides,
  };
}

export function makeFieldLabel(overrides: Partial<FieldLabel> = {}): FieldLabel {
  return {
    field_name: "policy_number",
    state: "UNLABELED",
    notes: "",
    ...overrides,
  };
}
