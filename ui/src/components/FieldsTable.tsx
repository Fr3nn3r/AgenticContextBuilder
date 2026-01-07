import { useState } from "react";
import type { ExtractedField, FieldLabel, UnverifiableReason } from "../types";
import { cn } from "../lib/utils";

interface FieldsTableProps {
  fields: ExtractedField[];
  labels: FieldLabel[];
  onConfirm: (fieldName: string, truthValue: string) => void;
  onUnverifiable: (fieldName: string, reason: UnverifiableReason) => void;
  onEditTruth: (fieldName: string, newTruthValue: string) => void;
  onQuoteClick: (quote: string, page: number, charStart?: number, charEnd?: number, extractedValue?: string) => void;
  readOnly?: boolean;
  docType?: string;
  runId?: string;
  showOptionalFields?: boolean;
  onToggleOptionalFields?: () => void;
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

// Unverifiable reason labels
const unverifiableReasonLabels: Record<UnverifiableReason, string> = {
  not_present_in_doc: "Not present in doc",
  unreadable_text: "Unreadable text",
  wrong_doc_type: "Wrong doc type",
  cannot_verify: "Cannot verify",
  other: "Other",
};

// Compare extracted value to truth value (normalized comparison)
function compareValues(extracted: string | null, truth: string | null | undefined): "match" | "mismatch" | "missing" | "unlabeled" {
  if (truth === null || truth === undefined) return "unlabeled";
  if (extracted === null || extracted === "") return "missing";

  // Normalize both values for comparison
  const normExtracted = (extracted || "").trim().toLowerCase();
  const normTruth = (truth || "").trim().toLowerCase();

  return normExtracted === normTruth ? "match" : "mismatch";
}

export function FieldsTable({
  fields,
  labels,
  onConfirm,
  onUnverifiable,
  onEditTruth,
  onQuoteClick,
  readOnly = false,
  docType,
  runId,
  showOptionalFields = false,
  onToggleOptionalFields,
}: FieldsTableProps) {
  const [focusedFieldIndex, setFocusedFieldIndex] = useState(0);
  const [editingField, setEditingField] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [showUnverifiableDropdown, setShowUnverifiableDropdown] = useState<string | null>(null);
  const [settingTruthField, setSettingTruthField] = useState<string | null>(null);
  const [newTruthValue, setNewTruthValue] = useState("");
  const [hoveredEvidence, setHoveredEvidence] = useState<string | null>(null);

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

  function handleConfirmClick(fieldName: string, extractedValue: string | null) {
    // Use normalized value if available, otherwise raw value
    const field = fields.find(f => f.name === fieldName);
    const valueToConfirm = field?.normalized_value || extractedValue || "";
    onConfirm(fieldName, valueToConfirm);
  }

  function handleUnverifiableSelect(fieldName: string, reason: UnverifiableReason) {
    onUnverifiable(fieldName, reason);
    setShowUnverifiableDropdown(null);
  }

  function handleEditStart(fieldName: string, currentTruth: string | undefined) {
    setEditingField(fieldName);
    setEditValue(currentTruth || "");
  }

  function handleEditSave(fieldName: string) {
    onEditTruth(fieldName, editValue);
    setEditingField(null);
    setEditValue("");
  }

  function handleEditCancel() {
    setEditingField(null);
    setEditValue("");
  }

  return (
    <div className="divide-y">
      {fields.map((field, index) => {
        const label = getLabel(field.name);
        const provenance = field.provenance[0];
        const isFocused = index === focusedFieldIndex;
        const isExpectedForDocType = expectedFields.length === 0 || expectedFields.includes(field.name);
        const isNotExpected = !isExpectedForDocType && field.status === "missing";

        // Compute comparison result for CONFIRMED fields
        const comparisonResult = label?.state === "CONFIRMED"
          ? compareValues(field.normalized_value || field.value, label.truth_value)
          : "unlabeled";

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

            {/* EXTRACTED VALUE SECTION */}
            <div className="mb-3 p-2 bg-slate-50 rounded border border-slate-200">
              <div className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-2">
                Extracted {runId && <span className="font-normal normal-case">({runId.slice(0, 20)}...)</span>}
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

            {/* GROUND TRUTH SECTION */}
            {!readOnly && (
              <div className="p-2 bg-blue-50 rounded border border-blue-200">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium text-blue-600 uppercase tracking-wide">
                    Ground Truth
                  </span>
                  <StateBadge state={label?.state || "UNLABELED"} />
                </div>

                {/* UNLABELED state - show action buttons */}
                {(!label || label.state === "UNLABELED") && (
                  <div className="space-y-2">
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleConfirmClick(field.name, field.normalized_value || field.value)}
                        className="flex items-center gap-1 px-3 py-1.5 bg-green-500 text-white text-sm font-medium rounded hover:bg-green-600 transition-colors"
                      >
                        <span>✓</span> Confirm
                      </button>
                      <div className="relative">
                        <button
                          onClick={() => setShowUnverifiableDropdown(
                            showUnverifiableDropdown === field.name ? null : field.name
                          )}
                          className="flex items-center gap-1 px-3 py-1.5 bg-gray-500 text-white text-sm font-medium rounded hover:bg-gray-600 transition-colors"
                        >
                          <span>✗</span> Mark Unverifiable
                        </button>
                        {showUnverifiableDropdown === field.name && (
                          <div className="absolute top-full left-0 mt-1 bg-white border rounded-md shadow-lg z-10 min-w-[180px]">
                            {(Object.keys(unverifiableReasonLabels) as UnverifiableReason[]).map((reason) => (
                              <button
                                key={reason}
                                onClick={() => handleUnverifiableSelect(field.name, reason)}
                                className="block w-full text-left px-3 py-2 text-sm hover:bg-gray-100"
                              >
                                {unverifiableReasonLabels[reason]}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}

                {/* CONFIRMED state - show truth value and comparison */}
                {label?.state === "CONFIRMED" && (
                  <div className="space-y-2">
                    {editingField === field.name ? (
                      // Editing mode
                      <div className="flex gap-2">
                        <input
                          type="text"
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          className="flex-1 px-2 py-1 text-sm border rounded"
                          autoFocus
                        />
                        <button
                          onClick={() => handleEditSave(field.name)}
                          className="px-2 py-1 bg-blue-500 text-white text-sm rounded hover:bg-blue-600"
                        >
                          Save
                        </button>
                        <button
                          onClick={handleEditCancel}
                          className="px-2 py-1 bg-gray-200 text-gray-700 text-sm rounded hover:bg-gray-300"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      // Display mode
                      <>
                        <div className="flex items-center justify-between">
                          <div className="font-mono text-sm bg-white px-2 py-1 rounded border flex-1">
                            <span className="text-green-700">Truth:</span> {label.truth_value || "(empty)"}
                          </div>
                          <button
                            onClick={() => handleEditStart(field.name, label.truth_value)}
                            className="ml-2 text-xs text-gray-500 hover:text-gray-700 px-2 py-1 rounded hover:bg-gray-100"
                          >
                            Edit
                          </button>
                        </div>
                        <ComparisonBadge result={comparisonResult} />
                      </>
                    )}
                  </div>
                )}

                {/* UNVERIFIABLE state - show reason */}
                {label?.state === "UNVERIFIABLE" && (
                  <div className="space-y-2">
                    <div className="text-sm text-gray-600">
                      <span className="font-medium">Reason:</span>{" "}
                      {label.unverifiable_reason
                        ? unverifiableReasonLabels[label.unverifiable_reason]
                        : "Unknown"}
                    </div>
                    <button
                      onClick={() => handleConfirmClick(field.name, field.normalized_value || field.value)}
                      className="text-xs text-blue-600 hover:text-blue-800"
                    >
                      Change to Confirmed
                    </button>
                  </div>
                )}
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

function StateBadge({ state }: { state: "CONFIRMED" | "UNVERIFIABLE" | "UNLABELED" }) {
  const styles: Record<string, string> = {
    CONFIRMED: "bg-green-100 text-green-700",
    UNVERIFIABLE: "bg-gray-100 text-gray-600",
    UNLABELED: "bg-amber-100 text-amber-700",
  };

  return (
    <span className={cn("text-xs px-1.5 py-0.5 rounded font-medium", styles[state])}>
      {state}
    </span>
  );
}

function ComparisonBadge({ result }: { result: "match" | "mismatch" | "missing" | "unlabeled" }) {
  const config: Record<string, { bg: string; text: string; icon: string }> = {
    match: { bg: "bg-green-100", text: "text-green-700", icon: "✓" },
    mismatch: { bg: "bg-red-100", text: "text-red-700", icon: "✗" },
    missing: { bg: "bg-amber-100", text: "text-amber-700", icon: "?" },
    unlabeled: { bg: "bg-gray-100", text: "text-gray-500", icon: "-" },
  };

  const { bg, text, icon } = config[result];
  const labels: Record<string, string> = {
    match: "MATCH",
    mismatch: "MISMATCH",
    missing: "MISSING",
    unlabeled: "Not labeled",
  };

  return (
    <div className={cn("flex items-center gap-1 text-xs px-2 py-1 rounded", bg, text)}>
      <span>{icon}</span>
      <span className="font-medium">Result: {labels[result]}</span>
    </div>
  );
}
