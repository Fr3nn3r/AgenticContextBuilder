import { useState } from "react";
import type { ExtractedField, FieldLabel } from "../types";
import { cn } from "../lib/utils";

interface FieldsTableProps {
  fields: ExtractedField[];
  labels: FieldLabel[];
  onLabelChange: (fieldName: string, judgement: "correct" | "incorrect" | "unknown") => void;
  onQuoteClick: (quote: string, page: number, charStart?: number, charEnd?: number, extractedValue?: string) => void;
  readOnly?: boolean;
  docType?: string;
  runId?: string;
}

// Human-readable field names mapping
const fieldDisplayNames: Record<string, string> = {
  incident_date: "Incident date",
  incident_location: "Incident location",
  policy_number: "Policy number",
  claimant_name: "Claimant name",
  vehicle_plate: "Vehicle plate",
  vehicle_make: "Vehicle make",
  vehicle_model: "Vehicle model",
  vehicle_year: "Vehicle year",
  loss_description: "Loss description",
  reported_date: "Report date",
  officer_name: "Officer name",
  badge_number: "Badge number",
};

function getDisplayName(fieldName: string): string {
  return fieldDisplayNames[fieldName] || fieldName.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

export function FieldsTable({
  fields,
  labels,
  onLabelChange,
  onQuoteClick,
  readOnly = false,
  docType,
  runId,
}: FieldsTableProps) {
  const [focusedFieldIndex, setFocusedFieldIndex] = useState(0);

  function getLabel(fieldName: string): FieldLabel | undefined {
    return labels.find((l) => l.field_name === fieldName);
  }

  // Focus state for visual indication (no keyboard shortcuts)
  void focusedFieldIndex; // Kept for potential future use

  // Fields that are typically expected per doc type
  const expectedFieldsByDocType: Record<string, string[]> = {
    loss_notice: ["incident_date", "incident_location", "policy_number", "claimant_name", "vehicle_plate", "loss_description"],
    police_report: ["incident_date", "incident_location", "officer_name", "badge_number", "vehicle_plate"],
    insurance_policy: ["policy_number", "claimant_name", "vehicle_plate", "vehicle_make", "vehicle_model", "vehicle_year"],
    id_document: ["claimant_name"],
    vehicle_registration: ["vehicle_plate", "vehicle_make", "vehicle_model", "vehicle_year"],
  };

  const expectedFields = docType ? expectedFieldsByDocType[docType] || [] : [];

  return (
    <div className="divide-y">
      {fields.map((field, index) => {
        const label = getLabel(field.name);
        const provenance = field.provenance[0];
        const isFocused = index === focusedFieldIndex;
        const isExpectedForDocType = expectedFields.length === 0 || expectedFields.includes(field.name);
        const isNotExpected = !isExpectedForDocType && field.status === "missing";

        return (
          <div
            key={field.name}
            className={cn(
              "p-3",
              isFocused && "bg-blue-50 ring-2 ring-blue-200 ring-inset",
              isNotExpected && "opacity-50"
            )}
            onClick={() => setFocusedFieldIndex(index)}
          >
            {/* Field header with human label + technical key */}
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="font-medium">{getDisplayName(field.name)}</span>
                <code className="text-xs text-gray-400 bg-gray-100 px-1 rounded">{field.name}</code>
              </div>
              <div className="text-sm text-muted-foreground">
                {(field.confidence * 100).toFixed(0)}%
              </div>
            </div>

            {/* PREDICTION SECTION */}
            <div className="mb-3 p-2 bg-slate-50 rounded border border-slate-200">
              <div className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-2">
                Prediction {runId && <span className="font-normal normal-case">({runId.slice(0, 20)}...)</span>}
              </div>

              <div className="flex items-center gap-2 mb-2">
                {isNotExpected ? (
                  <span className="text-xs px-1.5 py-0.5 bg-gray-100 text-gray-500 rounded">
                    Not expected for {docType}
                  </span>
                ) : (
                  <StatusBadge status={field.status} />
                )}
                {field.value_is_placeholder && (
                  <span className="text-xs px-1.5 py-0.5 bg-purple-100 text-purple-700 rounded">
                    Placeholder
                  </span>
                )}
              </div>

              {/* Value */}
              <div className="mb-2">
                {field.value ? (
                  <div className="font-mono text-sm bg-white px-2 py-1 rounded border">
                    {field.normalized_value || field.value}
                    {field.normalized_value &&
                      field.normalized_value !== field.value && (
                        <span className="text-muted-foreground ml-2">
                          (raw: {field.value})
                        </span>
                      )}
                  </div>
                ) : (
                  <span className="text-muted-foreground italic text-sm">
                    Not found
                  </span>
                )}
              </div>

              {/* Evidence quote */}
              {provenance && (
                <button
                  data-testid="evidence-link"
                  onClick={() => onQuoteClick(
                    provenance.text_quote,
                    provenance.page,
                    provenance.char_start,
                    provenance.char_end,
                    field.normalized_value || field.value || undefined
                  )}
                  className="text-left w-full"
                >
                  <div className="text-xs text-muted-foreground mb-1">
                    Evidence (Page {provenance.page}
                    {provenance.char_start !== undefined && `, chars ${provenance.char_start}-${provenance.char_end}`}):
                  </div>
                  <div className="text-sm bg-yellow-50 border-l-2 border-yellow-400 px-2 py-1 hover:bg-yellow-100 transition-colors">
                    "{provenance.text_quote}"
                  </div>
                </button>
              )}
            </div>

            {/* LABEL SECTION */}
            {!readOnly && (
              <div className="p-2 bg-blue-50 rounded border border-blue-200">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium text-blue-600 uppercase tracking-wide">
                    Label (Truth)
                  </span>
                  {label?.judgement && label.judgement !== "unknown" && (
                    <span className={cn(
                      "text-xs px-1.5 py-0.5 rounded",
                      label.judgement === "correct" ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"
                    )}>
                      Current: {label.judgement}
                    </span>
                  )}
                </div>
                <div className="flex gap-2">
                  <LabelButton
                    label="correct"
                    selected={label?.judgement === "correct"}
                    onClick={() => onLabelChange(field.name, "correct")}
                    color="green"
                  />
                  <LabelButton
                    label="wrong"
                    selected={label?.judgement === "incorrect"}
                    onClick={() => onLabelChange(field.name, "incorrect")}
                    color="red"
                  />
                  <LabelButton
                    label="cannot verify"
                    selected={label?.judgement === "unknown"}
                    onClick={() => onLabelChange(field.name, "unknown")}
                    color="gray"
                  />
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function StatusBadge({ status }: { status: "present" | "missing" | "uncertain" }) {
  const styles: Record<string, string> = {
    present: "bg-green-100 text-green-700",
    missing: "bg-red-100 text-red-700",
    uncertain: "bg-yellow-100 text-yellow-700",
  };

  const labels: Record<string, string> = {
    present: "Extracted",
    missing: "Missing",
    uncertain: "Uncertain",
  };

  return (
    <span className={cn("text-xs px-1.5 py-0.5 rounded", styles[status])}>
      {labels[status]}
    </span>
  );
}

interface LabelButtonProps {
  label: string;
  selected: boolean;
  onClick: () => void;
  color: "green" | "red" | "gray";
}

function LabelButton({ label, selected, onClick, color }: LabelButtonProps) {
  const colors = {
    green: selected
      ? "bg-green-500 text-white"
      : "bg-green-100 text-green-700 hover:bg-green-200",
    red: selected
      ? "bg-red-500 text-white"
      : "bg-red-100 text-red-700 hover:bg-red-200",
    gray: selected
      ? "bg-gray-500 text-white"
      : "bg-gray-100 text-gray-700 hover:bg-gray-200",
  };

  const icons: Record<string, string> = {
    correct: "✓",
    wrong: "✗",
    "cannot verify": "?",
  };

  return (
    <button
      onClick={onClick}
      className={cn(
        "px-3 py-1 rounded text-sm font-medium transition-colors flex items-center gap-1",
        colors[color]
      )}
    >
      {icons[label]} {label}
    </button>
  );
}
