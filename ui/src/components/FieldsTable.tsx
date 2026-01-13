import { useState } from "react";
import type { ExtractedField, FieldLabel, UnverifiableReason } from "../types";
import { cn } from "../lib/utils";
import {
  StatusBadge,
  UnverifiableBadge,
  CorrectBadge,
  IncorrectBadge,
  MissingBadge,
} from "./shared";

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
  not_present_in_doc: "Not in document",
  unreadable_text: "Unreadable text",
  wrong_doc_type: "Wrong doc type",
  cannot_verify: "Cannot verify",
  other: "Other reason",
};

// Compare extracted value to truth value (normalized comparison)
function compareValues(extracted: string | null, truth: string | null | undefined): "correct" | "incorrect" | "missing" | "unlabeled" {
  if (truth === null || truth === undefined) return "unlabeled";
  if (extracted === null || extracted === "") return "missing";

  const normExtracted = (extracted || "").trim().toLowerCase();
  const normTruth = (truth || "").trim().toLowerCase();

  return normExtracted === normTruth ? "correct" : "incorrect";
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
  const [expandedField, setExpandedField] = useState<string | null>(null);
  const [editingField, setEditingField] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [settingTruthField, setSettingTruthField] = useState<string | null>(null);
  const [newTruthValue, setNewTruthValue] = useState("");
  const [showUnverifiableMenu, setShowUnverifiableMenu] = useState<string | null>(null);

  function getLabel(fieldName: string): FieldLabel | undefined {
    return labels.find((l) => l.field_name === fieldName);
  }

  // Fields expected per doc type
  const expectedFieldsByDocType: Record<string, string[]> = {
    loss_notice: ["incident_date", "incident_location", "policy_number", "claimant_name", "vehicle_plate", "loss_description"],
    police_report: ["incident_date", "incident_location", "officer_name", "badge_number", "vehicle_plate"],
    insurance_policy: ["policy_number", "claimant_name", "vehicle_plate", "vehicle_make", "vehicle_model", "vehicle_year"],
    id_document: ["claimant_name"],
    vehicle_registration: ["vehicle_plate", "vehicle_make", "vehicle_model", "vehicle_year"],
  };

  // Filter fields
  const expectedFields = docType ? expectedFieldsByDocType[docType] || [] : [];
  const visibleFields = fields.filter(field => {
    const isExpectedForDocType = expectedFields.length === 0 || expectedFields.includes(field.name);
    const isNotExpected = !isExpectedForDocType && field.status === "missing";
    return !isNotExpected || showOptionalFields || field.value;
  });

  const hiddenFieldsCount = fields.length - visibleFields.length;

  // Calculate progress
  const labeledCount = visibleFields.filter(f => {
    const label = getLabel(f.name);
    return label?.state === "LABELED" || label?.state === "CONFIRMED" || label?.state === "UNVERIFIABLE";
  }).length;
  const totalCount = visibleFields.length;

  // Handlers
  function handleToggleExpand(fieldName: string) {
    setExpandedField(expandedField === fieldName ? null : fieldName);
    // Close any open menus
    setShowUnverifiableMenu(null);
    setSettingTruthField(null);
    setEditingField(null);
  }

  function handleConfirmClick(fieldName: string, extractedValue: string | null) {
    const field = fields.find(f => f.name === fieldName);
    const valueToConfirm = field?.normalized_value || extractedValue || "";
    onConfirm(fieldName, valueToConfirm);
  }

  function handleUnverifiableSelect(fieldName: string, reason: UnverifiableReason) {
    onUnverifiable(fieldName, reason);
    setShowUnverifiableMenu(null);
  }

  function handleSetTruthSave(fieldName: string) {
    if (newTruthValue.trim()) {
      onConfirm(fieldName, newTruthValue.trim());
    }
    setSettingTruthField(null);
    setNewTruthValue("");
  }

  function handleEditSave(fieldName: string) {
    onEditTruth(fieldName, editValue);
    setEditingField(null);
    setEditValue("");
  }

  return (
    <div className={cn(
      "flex flex-col h-full",
      readOnly && "opacity-50 pointer-events-none"
    )}>
      {/* Progress Header */}
      <div className="p-3 border-b bg-muted/50 flex-shrink-0">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-foreground">
            {labeledCount} of {totalCount} labeled
          </span>
          {hiddenFieldsCount > 0 && onToggleOptionalFields && (
            <button
              onClick={onToggleOptionalFields}
              className="text-xs text-accent-foreground hover:text-accent"
            >
              {showOptionalFields ? "Hide optional" : `+${hiddenFieldsCount} optional`}
            </button>
          )}
        </div>
        {/* Progress bar */}
        <div className="w-full h-1.5 bg-muted rounded-full overflow-hidden">
          <div
            className="h-full bg-success rounded-full transition-all duration-300"
            style={{ width: `${totalCount > 0 ? (labeledCount / totalCount) * 100 : 0}%` }}
          />
        </div>
      </div>

      {/* Field List */}
      <div className="flex-1 overflow-auto divide-y">
        {visibleFields.map((field) => {
          const label = getLabel(field.name);
          const provenance = field.provenance[0];
          const isExpanded = expandedField === field.name;

          const isLabeled = label?.state === "LABELED" || label?.state === "CONFIRMED";
          const isUnverifiable = label?.state === "UNVERIFIABLE";
          const isUnlabeled = !label || label.state === "UNLABELED";

          const comparisonResult = isLabeled
            ? compareValues(field.normalized_value || field.value, label?.truth_value)
            : "unlabeled";

          // Determine border color based on state
          const borderColor = isUnverifiable
            ? "border-l-muted-foreground/30"
            : isLabeled && comparisonResult === "correct"
            ? "border-l-success"
            : isLabeled && comparisonResult === "incorrect"
            ? "border-l-destructive"
            : isLabeled && comparisonResult === "missing"
            ? "border-l-warning"
            : "border-l-warning/70";

          const rowBg = isUnlabeled ? "bg-amber-50/40" : "";

          return (
            <div key={field.name} className={cn("border-l-4", borderColor, rowBg)}>
              {/* Collapsed Row */}
              <div
                className="px-3 py-2.5 cursor-pointer hover:bg-muted/50 transition-colors"
                onClick={() => handleToggleExpand(field.name)}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0 flex-1">
                    {/* Status dot */}
                    <span
                      className={cn(
                        "w-2 h-2 rounded-full flex-shrink-0",
                        isLabeled ? "bg-success" :
                        isUnverifiable ? "bg-muted-foreground/50" :
                        "bg-warning/70"
                      )}
                    />
                    {/* Field name */}
                    <span className="font-medium text-sm text-foreground truncate">
                      {getDisplayName(field.name)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    {/* Extracted value preview */}
                    <span className="font-mono text-xs text-muted-foreground truncate max-w-[120px]">
                      {field.value || "—"}
                    </span>
                    {/* Status indicator */}
                    {isLabeled && comparisonResult === "correct" && (
                      <span className="text-success text-xs">✓</span>
                    )}
                    {isLabeled && comparisonResult === "incorrect" && (
                      <span className="text-destructive text-xs">✗</span>
                    )}
                    {/* Chevron */}
                    <svg
                      className={cn(
                        "w-4 h-4 text-muted-foreground/70 transition-transform",
                        isExpanded && "rotate-180"
                      )}
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </div>
                </div>
              </div>

              {/* Expanded Content */}
              {isExpanded && (
                <div className="px-3 pb-3 bg-muted/30">
                  {/* Extracted Value */}
                  <div className="flex items-start gap-2 py-2">
                    <span className="text-xs text-muted-foreground w-16 flex-shrink-0 pt-0.5">Extracted</span>
                    <div className="flex-1 min-w-0">
                      {field.value ? (
                        <code className="text-sm bg-card px-2 py-1 rounded border border-border inline-block">
                          {field.normalized_value || field.value}
                        </code>
                      ) : (
                        <span className="text-sm text-muted-foreground/70 italic">No value extracted</span>
                      )}
                      {field.value_is_placeholder && (
                        <StatusBadge variant="info" size="sm" className="ml-2">Placeholder</StatusBadge>
                      )}
                    </div>
                  </div>

                  {/* Truth Value (if labeled) */}
                  {isLabeled && (
                    <div className="flex items-start gap-2 py-2 border-t border-border">
                      <span className="text-xs text-muted-foreground w-16 flex-shrink-0 pt-0.5">Truth</span>
                      <div className="flex-1 flex items-center gap-2 flex-wrap">
                        {editingField === field.name ? (
                          <div className="flex gap-2 items-center flex-1">
                            <input
                              type="text"
                              value={editValue}
                              onChange={(e) => setEditValue(e.target.value)}
                              className="flex-1 px-2 py-1 text-sm border rounded min-w-[100px]"
                              autoFocus
                              onKeyDown={(e) => {
                                if (e.key === "Enter") handleEditSave(field.name);
                                if (e.key === "Escape") setEditingField(null);
                              }}
                            />
                            <button
                              onClick={() => handleEditSave(field.name)}
                              className="px-2 py-1 text-xs bg-accent text-accent-foreground rounded hover:bg-accent/90"
                            >
                              Save
                            </button>
                            <button
                              onClick={() => setEditingField(null)}
                              className="px-2 py-1 text-xs text-muted-foreground hover:text-foreground"
                            >
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <>
                            <code className="text-sm text-success">{label?.truth_value || "(empty)"}</code>
                            {comparisonResult === "correct" && <CorrectBadge />}
                            {comparisonResult === "incorrect" && <IncorrectBadge />}
                            {comparisonResult === "missing" && <MissingBadge />}
                            {!readOnly && (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setEditingField(field.name);
                                  setEditValue(label?.truth_value || "");
                                }}
                                className="text-xs text-accent-foreground hover:underline"
                              >
                                Edit
                              </button>
                            )}
                          </>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Unverifiable Reason */}
                  {isUnverifiable && label?.unverifiable_reason && (
                    <div className="flex items-start gap-2 py-2 border-t border-border">
                      <span className="text-xs text-muted-foreground w-16 flex-shrink-0 pt-0.5">Reason</span>
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-muted-foreground">
                          {unverifiableReasonLabels[label.unverifiable_reason]}
                        </span>
                        <UnverifiableBadge />
                      </div>
                    </div>
                  )}

                  {/* Evidence Link */}
                  {provenance && (
                    <div className="flex items-start gap-2 py-2 border-t border-border">
                      <span className="text-xs text-muted-foreground w-16 flex-shrink-0 pt-0.5">Evidence</span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onQuoteClick(
                            provenance.text_quote,
                            provenance.page,
                            provenance.char_start,
                            provenance.char_end,
                            field.normalized_value || field.value || undefined
                          );
                        }}
                        className="text-sm text-accent-foreground hover:underline text-left"
                      >
                        Page {provenance.page}
                        <span className="text-muted-foreground/70 ml-1">·</span>
                        <span className="text-muted-foreground ml-1 italic truncate max-w-[200px] inline-block align-bottom">
                          "{provenance.text_quote.slice(0, 40)}..."
                        </span>
                      </button>
                    </div>
                  )}

                  {/* Action Buttons - Only for UNLABELED */}
                  {!readOnly && isUnlabeled && (
                    <div className="pt-3 mt-2 border-t border-border">
                      {settingTruthField === field.name ? (
                        <div className="space-y-2">
                          <input
                            type="text"
                            value={newTruthValue}
                            onChange={(e) => setNewTruthValue(e.target.value)}
                            placeholder="Enter the correct value..."
                            className="w-full px-3 py-2 text-sm border rounded focus:ring-2 focus:ring-accent focus:border-accent"
                            autoFocus
                            onKeyDown={(e) => {
                              if (e.key === "Enter" && newTruthValue.trim()) handleSetTruthSave(field.name);
                              if (e.key === "Escape") setSettingTruthField(null);
                            }}
                          />
                          <div className="flex gap-2">
                            <button
                              onClick={() => handleSetTruthSave(field.name)}
                              disabled={!newTruthValue.trim()}
                              className="px-3 py-1.5 text-sm bg-accent text-accent-foreground rounded hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              Save Truth
                            </button>
                            <button
                              onClick={() => setSettingTruthField(null)}
                              className="px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground"
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div className="flex flex-wrap gap-2">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleConfirmClick(field.name, field.normalized_value || field.value);
                            }}
                            disabled={!field.value}
                            title={!field.value ? "No extracted value to confirm" : "Accept extracted value as truth"}
                            className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium bg-success text-success-foreground rounded hover:bg-success/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                            Confirm
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setSettingTruthField(field.name);
                              setNewTruthValue(field.value || "");
                            }}
                            className="px-3 py-1.5 text-sm font-medium bg-accent text-accent-foreground rounded hover:bg-accent/90 transition-colors"
                          >
                            Set Value...
                          </button>
                          <div className="relative">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setShowUnverifiableMenu(
                                  showUnverifiableMenu === field.name ? null : field.name
                                );
                              }}
                              className="px-3 py-1.5 text-sm font-medium bg-muted text-foreground rounded hover:bg-muted/80 transition-colors"
                            >
                              Skip...
                            </button>
                            {showUnverifiableMenu === field.name && (
                              <div className="absolute top-full left-0 mt-1 bg-card border rounded-lg shadow-lg z-20 py-1 min-w-[160px]">
                                <div className="px-3 py-1 text-xs text-muted-foreground font-medium border-b">
                                  Mark as unverifiable
                                </div>
                                {(Object.keys(unverifiableReasonLabels) as UnverifiableReason[]).map((reason) => (
                                  <button
                                    key={reason}
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleUnverifiableSelect(field.name, reason);
                                    }}
                                    className="block w-full text-left px-3 py-2 text-sm hover:bg-muted"
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

                  {/* Change Decision for UNVERIFIABLE */}
                  {!readOnly && isUnverifiable && (
                    <div className="pt-3 mt-2 border-t border-border">
                      {settingTruthField === field.name ? (
                        <div className="space-y-2">
                          <input
                            type="text"
                            value={newTruthValue}
                            onChange={(e) => setNewTruthValue(e.target.value)}
                            placeholder="Enter the correct value..."
                            className="w-full px-3 py-2 text-sm border rounded"
                            autoFocus
                          />
                          <div className="flex gap-2">
                            <button
                              onClick={() => handleSetTruthSave(field.name)}
                              disabled={!newTruthValue.trim()}
                              className="px-3 py-1.5 text-sm bg-accent text-accent-foreground rounded hover:bg-accent/90 disabled:opacity-50"
                            >
                              Save
                            </button>
                            <button
                              onClick={() => setSettingTruthField(null)}
                              className="px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground"
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      ) : (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSettingTruthField(field.name);
                          }}
                          className="text-sm text-accent-foreground hover:underline"
                        >
                          Change decision...
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
    </div>
  );
}
