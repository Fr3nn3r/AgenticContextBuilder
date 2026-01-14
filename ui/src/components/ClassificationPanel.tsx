import { useState, useEffect } from "react";
import { cn } from "../lib/utils";
import { formatDocType } from "../lib/formatters";

// Document type options from the catalog
const DOC_TYPES = [
  "fnol_form",
  "insurance_policy",
  "police_report",
  "invoice",
  "id_document",
  "vehicle_registration",
  "certificate",
  "medical_report",
  "travel_itinerary",
  "customer_comm",
  "supporting_document",
];

interface ClassificationPanelProps {
  predictedType: string;
  confidence: number;
  signals?: string[];
  // Current label state (managed by parent)
  isConfirmed: boolean;
  isOverridden: boolean;
  overriddenType: string | null;
  // Callbacks to update parent state (triggers unsaved changes)
  onConfirm: () => void;
  onOverride: (newType: string) => void;
}

export function ClassificationPanel({
  predictedType,
  confidence,
  signals,
  isConfirmed,
  isOverridden,
  overriddenType,
  onConfirm,
  onOverride,
}: ClassificationPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [selectedNewType, setSelectedNewType] = useState(overriddenType || "");

  // Sync selectedNewType when overriddenType changes (e.g., when switching docs)
  useEffect(() => {
    setSelectedNewType(overriddenType || "");
  }, [overriddenType]);

  const confidencePercent = Math.round(confidence * 100);

  // Determine border color based on state
  const borderColor = isOverridden
    ? "border-l-amber-500 dark:border-l-amber-400"
    : isConfirmed
    ? "border-l-green-500 dark:border-l-green-400"
    : "border-l-blue-400 dark:border-l-blue-300";

  // Determine status indicator
  const statusDot = isOverridden
    ? "bg-amber-500"
    : isConfirmed
    ? "bg-green-500"
    : "bg-muted-foreground/30";

  function handleConfirmClick(e: React.MouseEvent) {
    e.stopPropagation();
    onConfirm();
  }

  function handleOverrideSelect(e: React.ChangeEvent<HTMLSelectElement>) {
    const newType = e.target.value;
    setSelectedNewType(newType);
    if (newType) {
      onOverride(newType);
    }
  }

  return (
    <div className={cn("border-l-4 bg-card", borderColor)}>
      {/* Collapsed Row */}
      <div
        className="px-4 py-2.5 cursor-pointer hover:bg-muted/50 transition-colors flex items-center justify-between"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-3">
          {/* Status dot */}
          <div className={cn("w-2 h-2 rounded-full", statusDot)} />
          <span className="text-sm font-medium text-foreground">Classification</span>
          <span className="px-2 py-0.5 bg-muted rounded text-sm text-foreground">
            {formatDocType(isOverridden && overriddenType ? overriddenType : predictedType)}
          </span>
          <span className={cn(
            "text-xs font-medium",
            confidencePercent >= 90 ? "text-green-600 dark:text-green-400" :
            confidencePercent >= 70 ? "text-amber-600 dark:text-amber-400" : "text-red-600 dark:text-red-400"
          )}>
            {confidencePercent}%
          </span>
          {isConfirmed && !isOverridden && (
            <span className="text-green-600 dark:text-green-400 text-xs">✓</span>
          )}
          {isOverridden && (
            <span className="px-2 py-0.5 bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400 rounded text-xs">
              Changed from {formatDocType(predictedType)}
            </span>
          )}
        </div>
        <svg
          className={cn(
            "w-5 h-5 text-muted-foreground transition-transform",
            isExpanded && "rotate-180"
          )}
          fill="none" stroke="currentColor" viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </div>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="px-4 pb-3 bg-muted/50 border-t border-border">
          {/* Classification Details */}
          <div className="py-3 space-y-1.5 text-sm">
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground w-32">Extraction Template:</span>
              <span className="font-mono text-foreground">{predictedType}</span>
            </div>
            {signals && signals.length > 0 && (
              <div className="flex items-start gap-2">
                <span className="text-muted-foreground w-32">Signals:</span>
                <span className="text-muted-foreground text-xs">
                  {signals.slice(0, 3).join(", ")}
                  {signals.length > 3 && ` +${signals.length - 3} more`}
                </span>
              </div>
            )}
          </div>

          {/* Review Actions */}
          <div className="pt-3 border-t border-border flex items-center gap-3">
            <button
              onClick={handleConfirmClick}
              disabled={isConfirmed && !isOverridden}
              className={cn(
                "px-4 py-1.5 rounded-md text-sm font-medium transition-colors",
                isConfirmed && !isOverridden
                  ? "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 cursor-default"
                  : "bg-green-600 text-white hover:bg-green-700"
              )}
            >
              {isConfirmed && !isOverridden ? "Confirmed ✓" : "Confirm"}
            </button>

            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">or change to:</span>
              <select
                value={selectedNewType}
                onChange={handleOverrideSelect}
                onClick={(e) => e.stopPropagation()}
                className="border border-input bg-background text-foreground rounded-md px-2 py-1.5 text-sm min-w-[160px]"
              >
                <option value="">Select type...</option>
                {DOC_TYPES.filter((t) => t !== predictedType).map((type) => (
                  <option key={type} value={type}>
                    {formatDocType(type)}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
