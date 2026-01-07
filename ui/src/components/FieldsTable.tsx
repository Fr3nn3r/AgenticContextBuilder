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

  function handleSetTruthStart(fieldName: string) {
    setSettingTruthField(fieldName);
    setNewTruthValue("");
  }

  function handleSetTruthSave(fieldName: string) {
    if (newTruthValue.trim()) {
      onConfirm(fieldName, newTruthValue.trim());
    }
    setSettingTruthField(null);
    setNewTruthValue("");
  }

  function handleSetTruthCancel() {
    setSettingTruthField(null);
    setNewTruthValue("");
  }

  function handleUseExtractedValue(fieldName: string) {
    const field = fields.find(f => f.name === fieldName);
    if (field) {
      setEditValue(field.normalized_value || field.value || "");
    }
  }

  // Filter fields based on optional fields toggle
  const expectedFields = docType ? expectedFieldsByDocType[docType] || [] : [];
  const visibleFields = fields.filter(field => {
    const isExpectedForDocType = expectedFields.length === 0 || expectedFields.includes(field.name);
    const isNotExpected = !isExpectedForDocType && field.status === "missing";
    // Show if expected, or if showOptionalFields is true, or if has a value
    return !isNotExpected || showOptionalFields || field.value;
  });

  const hiddenFieldsCount = fields.length - visibleFields.length;

  return (
    <div className="divide-y">
      {/* Toggle for optional fields */}
      {hiddenFieldsCount > 0 && onToggleOptionalFields && (
        <div className="p-2 bg-gray-50 border-b flex items-center justify-between">
          <span className="text-sm text-gray-600">
            {hiddenFieldsCount} optional field{hiddenFieldsCount > 1 ? 's' : ''} hidden
          </span>
          <button
            onClick={onToggleOptionalFields}
            className="text-sm text-blue-600 hover:text-blue-800 underline"
          >
            {showOptionalFields ? 'Hide optional fields' : 'Show optional fields'}
          </button>
        </div>
      )}
      {visibleFields.map((field, index) => {
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
            {/* Field header with name + status badges */}
            <div className="flex items-center justify-between mb-2">
              <span className="font-semibold text-gray-900">{getDisplayName(field.name)}</span>
              <div className="flex items-center gap-2">
                <StateBadge state={label?.state || "UNLABELED"} />
                {label?.state === "CONFIRMED" && (
                  <ComparisonBadge result={comparisonResult} compact />
                )}
              </div>
            </div>

            {/* Extracted value - single line with highlighted value */}
            <div className="mb-2 flex items-center gap-2">
              <span className="text-sm text-gray-600">Extracted:</span>
              {field.value ? (
                <span className="font-mono text-sm font-medium text-gray-900 px-2 py-0.5 bg-amber-50 border-2 border-amber-300 rounded">
                  {field.normalized_value || field.value}
                  {field.value_is_placeholder && (
                    <span className="ml-2 text-xs px-1.5 py-0.5 bg-purple-100 text-purple-700 rounded font-normal">
                      Placeholder
                    </span>
                  )}
                </span>
              ) : (
                <span className="text-sm px-2 py-0.5 bg-red-100 text-red-700 rounded">
                  Missing
                </span>
              )}
            </div>

            {/* Evidence link with hover preview */}
            {provenance && (
              <div
                className="relative mb-3"
                onMouseEnter={() => setHoveredEvidence(field.name)}
                onMouseLeave={() => setHoveredEvidence(null)}
              >
                <button
                  data-testid="evidence-link"
                  onClick={() => onQuoteClick(
                    provenance.text_quote,
                    provenance.page,
                    provenance.char_start,
                    provenance.char_end,
                    field.normalized_value || field.value || undefined
                  )}
                  className="text-sm text-blue-600 hover:text-blue-800 hover:underline"
                >
                  Evidence: Page {provenance.page}
                </button>
                {/* Hover preview tooltip */}
                {hoveredEvidence === field.name && (
                  <div className="absolute bottom-full left-0 mb-1 p-2 bg-white border rounded shadow-lg z-20 max-w-xs">
                    <div className="text-xs text-gray-500 mb-1">Quote:</div>
                    <div className="text-sm text-gray-700 italic">"{provenance.text_quote}"</div>
                  </div>
                )}
              </div>
            )}

            {/* Ground truth actions (no title) */}
            {!readOnly && (
              <div>
                {/* UNLABELED state - show action buttons */}
                {(!label || label.state === "UNLABELED") && (
                  <div className="space-y-2">
                    {settingTruthField === field.name ? (
                      // Set truth value inline input
                      <div className="space-y-2">
                        <input
                          type="text"
                          value={newTruthValue}
                          onChange={(e) => setNewTruthValue(e.target.value)}
                          placeholder="Enter ground truth value"
                          className="w-full px-2 py-1 text-sm border rounded"
                          autoFocus
                        />
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleSetTruthSave(field.name)}
                            disabled={!newTruthValue.trim()}
                            className="px-3 py-1 bg-blue-500 text-white text-sm rounded hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            Save
                          </button>
                          <button
                            onClick={handleSetTruthCancel}
                            className="px-3 py-1 bg-gray-200 text-gray-700 text-sm rounded hover:bg-gray-300"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      // Action buttons
                      <div className="flex flex-wrap gap-2">
                        <button
                          onClick={() => handleConfirmClick(field.name, field.normalized_value || field.value)}
                          disabled={!field.value}
                          title={!field.value ? "Cannot confirm - no extracted value" : "Confirm extracted value as truth"}
                          className="flex items-center gap-1 px-3 py-1.5 bg-green-500 text-white text-sm font-medium rounded hover:bg-green-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          <span>✓</span> Confirm as truth
                        </button>
                        <button
                          onClick={() => handleSetTruthStart(field.name)}
                          className="flex items-center gap-1 px-3 py-1.5 bg-blue-500 text-white text-sm font-medium rounded hover:bg-blue-600 transition-colors"
                        >
                          Set truth value…
                        </button>
                        <div className="relative">
                          <button
                            onClick={() => setShowUnverifiableDropdown(
                              showUnverifiableDropdown === field.name ? null : field.name
                            )}
                            className="flex items-center gap-1 px-3 py-1.5 bg-gray-500 text-white text-sm font-medium rounded hover:bg-gray-600 transition-colors"
                          >
                            Mark unverifiable…
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
                    )}
                  </div>
                )}

                {/* CONFIRMED state - show truth value */}
                {label?.state === "CONFIRMED" && (
                  <div>
                    {editingField === field.name ? (
                      // Editing mode
                      <div className="space-y-2">
                        <input
                          type="text"
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          className="w-full px-2 py-1 text-sm border rounded"
                          autoFocus
                        />
                        <div className="flex gap-2 flex-wrap">
                          {field.value && (
                            <button
                              onClick={() => handleUseExtractedValue(field.name)}
                              className="px-2 py-1 bg-slate-100 text-slate-700 text-sm rounded hover:bg-slate-200 border"
                            >
                              Use extracted value
                            </button>
                          )}
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
                      </div>
                    ) : (
                      // Display mode - single line
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-gray-600">Truth:</span>
                        <span className="font-mono text-sm text-green-700">{label.truth_value || "(empty)"}</span>
                        <button
                          onClick={() => handleEditStart(field.name, label.truth_value)}
                          className="text-xs text-blue-600 hover:text-blue-800 hover:underline"
                        >
                          Edit
                        </button>
                        <ComparisonBadge result={comparisonResult} compact />
                      </div>
                    )}
                  </div>
                )}

                {/* UNVERIFIABLE state - show reason and change option */}
                {label?.state === "UNVERIFIABLE" && (
                  <div className="space-y-2">
                    <div className="text-sm text-gray-600 bg-gray-50 px-2 py-1 rounded">
                      <span className="font-medium">Reason:</span>{" "}
                      {label.unverifiable_reason
                        ? unverifiableReasonLabels[label.unverifiable_reason]
                        : "Unknown"}
                      {label.notes && (
                        <div className="text-xs text-gray-500 mt-1">Note: {label.notes}</div>
                      )}
                    </div>
                    {settingTruthField === field.name ? (
                      // Set truth value inline input
                      <div className="space-y-2">
                        <input
                          type="text"
                          value={newTruthValue}
                          onChange={(e) => setNewTruthValue(e.target.value)}
                          placeholder="Enter ground truth value"
                          className="w-full px-2 py-1 text-sm border rounded"
                          autoFocus
                        />
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleSetTruthSave(field.name)}
                            disabled={!newTruthValue.trim()}
                            className="px-3 py-1 bg-blue-500 text-white text-sm rounded hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            Save
                          </button>
                          <button
                            onClick={handleSetTruthCancel}
                            className="px-3 py-1 bg-gray-200 text-gray-700 text-sm rounded hover:bg-gray-300"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <button
                        onClick={() => handleSetTruthStart(field.name)}
                        className="text-sm text-blue-600 hover:text-blue-800 hover:underline"
                      >
                        Change decision
                      </button>
                    )}
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

function ComparisonBadge({ result, compact = false }: { result: "match" | "mismatch" | "missing" | "unlabeled"; compact?: boolean }) {
  const config: Record<string, { bg: string; text: string; icon: string }> = {
    match: { bg: "bg-green-100", text: "text-green-700", icon: "✓" },
    mismatch: { bg: "bg-red-100", text: "text-red-700", icon: "✗" },
    missing: { bg: "bg-amber-100", text: "text-amber-700", icon: "?" },
    unlabeled: { bg: "bg-gray-100", text: "text-gray-500", icon: "-" },
  };

  const { bg, text, icon } = config[result];
  const labels: Record<string, string> = {
    match: "Match",
    mismatch: "Mismatch",
    missing: "Missing",
    unlabeled: "Not labeled",
  };

  if (compact) {
    return (
      <span className={cn("text-xs px-1.5 py-0.5 rounded", bg, text)}>
        {icon} {labels[result]}
      </span>
    );
  }

  return (
    <div className={cn("flex items-center gap-1 text-xs px-2 py-1 rounded", bg, text)}>
      <span>{icon}</span>
      <span className="font-medium">Result: {labels[result]}</span>
    </div>
  );
}
