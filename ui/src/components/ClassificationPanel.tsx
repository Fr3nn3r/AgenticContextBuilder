import { useState, useEffect, useRef } from "react";
import { cn } from "../lib/utils";
import { formatDocType } from "../lib/formatters";
import { HelpIcon } from "./shared";

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
  isConfirmed,
  isOverridden,
  overriddenType,
  onConfirm,
  onOverride,
}: ClassificationPanelProps) {
  const [showDropdown, setShowDropdown] = useState(false);
  const [selectedNewType, setSelectedNewType] = useState(overriddenType || "");
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Sync selectedNewType when overriddenType changes (e.g., when switching docs)
  useEffect(() => {
    setSelectedNewType(overriddenType || "");
  }, [overriddenType]);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowDropdown(false);
      }
    }
    if (showDropdown) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [showDropdown]);

  const confidencePercent = Math.round(confidence * 100);
  const displayType = isOverridden && overriddenType ? overriddenType : predictedType;

  // Determine status indicator color
  const statusDot = isOverridden
    ? "bg-amber-500"
    : isConfirmed
    ? "bg-green-500"
    : "bg-muted-foreground/30";

  // Determine border color based on state
  const borderColor = isOverridden
    ? "border-l-amber-500 dark:border-l-amber-400"
    : isConfirmed
    ? "border-l-green-500 dark:border-l-green-400"
    : "border-l-blue-400 dark:border-l-blue-300";

  function handleOverrideSelect(e: React.ChangeEvent<HTMLSelectElement>) {
    const newType = e.target.value;
    if (newType) {
      setSelectedNewType(newType);
      onOverride(newType);
      setShowDropdown(false);
    }
  }

  function handleConfirmClick() {
    if (!isConfirmed || isOverridden) {
      onConfirm();
    }
  }

  return (
    <div className={cn("border-l-4 bg-card px-4 py-2.5", borderColor)}>
      <div className="flex items-center justify-between">
        {/* Left side: status, type, confidence */}
        <div className="flex items-center gap-3">
          <div className={cn("w-2 h-2 rounded-full", statusDot)} />
          <span className="px-2 py-0.5 bg-muted rounded text-sm font-medium text-foreground">
            {formatDocType(displayType)}
          </span>
          <span className={cn(
            "text-sm font-medium flex items-center gap-1",
            confidencePercent >= 90 ? "text-green-600 dark:text-green-400" :
            confidencePercent >= 70 ? "text-amber-600 dark:text-amber-400" :
            "text-red-600 dark:text-red-400"
          )}>
            {confidencePercent}%
            <HelpIcon term="classificationConfidence" />
          </span>
          {isConfirmed && !isOverridden && (
            <span className="text-green-600 dark:text-green-400 text-sm">✓</span>
          )}
          {isOverridden && (
            <span className="text-xs text-muted-foreground">
              ← {formatDocType(predictedType)}
            </span>
          )}
        </div>

        {/* Right side: actions */}
        <div className="flex items-center gap-2 relative" ref={dropdownRef}>
          {/* Confirm button - only show if not confirmed */}
          {(!isConfirmed || isOverridden) && (
            <button
              onClick={handleConfirmClick}
              className="text-sm text-green-600 dark:text-green-400 hover:text-green-700 dark:hover:text-green-300 font-medium"
            >
              Confirm
            </button>
          )}

          {/* Separator */}
          {(!isConfirmed || isOverridden) && (
            <span className="text-muted-foreground/50">·</span>
          )}

          {/* Change dropdown trigger */}
          <button
            onClick={() => setShowDropdown(!showDropdown)}
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            Change
          </button>

          {/* Dropdown */}
          {showDropdown && (
            <div className="absolute right-0 top-full mt-1 z-50 bg-popover border border-border rounded-md shadow-lg py-1 min-w-[180px]">
              <select
                value={selectedNewType}
                onChange={handleOverrideSelect}
                autoFocus
                className="w-full border-0 bg-transparent text-foreground px-3 py-1.5 text-sm focus:outline-none"
                size={Math.min(DOC_TYPES.length, 8)}
              >
                {DOC_TYPES.filter((t) => t !== displayType).map((type) => (
                  <option key={type} value={type} className="py-1">
                    {formatDocType(type)}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
