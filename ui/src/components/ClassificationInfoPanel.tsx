import { cn } from "../lib/utils";
import { formatDocType } from "../lib/formatters";
import { ScoreBadge } from "./shared";
import type { ClassificationDetail, DocTypeCatalogEntry } from "../types";

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
  "damage_evidence",
];

interface ClassificationInfoPanelProps {
  detail: ClassificationDetail;
  docTypeInfo: DocTypeCatalogEntry | null;
  reviewAction: "confirm" | "change";
  newDocType: string;
  notes: string;
  saving: boolean;
  onReviewActionChange: (action: "confirm" | "change") => void;
  onNewDocTypeChange: (type: string) => void;
  onNotesChange: (notes: string) => void;
  onSave: () => void;
}

export function ClassificationInfoPanel({
  detail,
  docTypeInfo,
  reviewAction,
  newDocType,
  notes,
  saving,
  onReviewActionChange,
  onNewDocTypeChange,
  onNotesChange,
  onSave,
}: ClassificationInfoPanelProps) {
  const canSave = reviewAction === "confirm" || (reviewAction === "change" && newDocType);

  return (
    <div className="flex flex-col h-full">
      {/* Header with doc name and confidence */}
      <div className="px-4 py-3 border-b bg-card flex-shrink-0">
        <h3 className="font-medium text-foreground truncate" title={detail.filename}>
          {detail.filename}
        </h3>
        <div className="flex items-center gap-2 mt-1">
          <ScoreBadge value={Math.round(detail.confidence * 100)} />
          {detail.language && detail.language !== "unknown" && (
            <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded">
              {detail.language.toUpperCase()}
            </span>
          )}
          <span className="text-xs text-muted-foreground">{detail.claim_id}</span>
        </div>
      </div>

      {/* Scrollable content area */}
      <div className="flex-1 overflow-auto p-4 space-y-4 min-h-0">
        {/* Section 1: Classification Result */}
        <div className="bg-card rounded-lg p-4 shadow-sm">
          <h4 className="text-sm font-semibold text-foreground mb-2">
            Classification Result
          </h4>
          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Predicted Type</span>
              <span className="text-sm font-medium text-foreground">
                {formatDocType(detail.predicted_type)}
              </span>
            </div>
            {detail.summary && (
              <p className="text-xs text-muted-foreground border-t pt-2 mt-2">
                {detail.summary}
              </p>
            )}
          </div>
        </div>

        {/* Section 2: Key Hints (if present) */}
        {detail.key_hints && Object.keys(detail.key_hints).length > 0 && (
          <div className="bg-card rounded-lg p-4 shadow-sm">
            <h4 className="text-sm font-semibold text-foreground mb-2">
              Key Hints
            </h4>
            <div className="space-y-1.5">
              {Object.entries(detail.key_hints).map(([key, value]) => (
                <div key={key} className="flex justify-between text-sm gap-2">
                  <span className="text-muted-foreground capitalize">
                    {key.replace(/_/g, " ")}
                  </span>
                  <span className="font-mono text-foreground text-right truncate max-w-[180px]" title={value}>
                    {value}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Section 3: Signals (ALL of them) */}
        {detail.signals && detail.signals.length > 0 && (
          <div className="bg-card rounded-lg p-4 shadow-sm">
            <h4 className="text-sm font-semibold text-foreground mb-2">
              Classification Signals
            </h4>
            <ul className="space-y-1">
              {detail.signals.map((signal, i) => (
                <li
                  key={i}
                  className="text-sm text-muted-foreground flex items-start gap-2"
                >
                  <span className="text-success mt-0.5 flex-shrink-0">•</span>
                  <span>{signal}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Section 4: Doc Type Template Info */}
        {docTypeInfo && (
          <div className="bg-card rounded-lg p-4 shadow-sm">
            <h4 className="text-sm font-semibold text-foreground mb-2">
              Template: {formatDocType(docTypeInfo.doc_type)}
            </h4>
            <p className="text-sm text-muted-foreground mb-3">
              {docTypeInfo.description}
            </p>
            {docTypeInfo.cues.length > 0 && (
              <div>
                <span className="text-xs font-medium text-muted-foreground">
                  Expected Cues:
                </span>
                <div className="flex flex-wrap gap-1 mt-1">
                  {docTypeInfo.cues.slice(0, 8).map((cue, i) => (
                    <span
                      key={i}
                      className="px-2 py-0.5 bg-muted rounded text-xs text-muted-foreground"
                    >
                      {cue}
                    </span>
                  ))}
                  {docTypeInfo.cues.length > 8 && (
                    <span className="text-xs text-muted-foreground px-1">
                      +{docTypeInfo.cues.length - 8} more
                    </span>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Review Actions (sticky bottom) */}
      <div className="border-t bg-gradient-to-b from-card to-muted/30 flex-shrink-0">
        {/* Step 1: Classification Decision */}
        <div className="px-4 pt-4 pb-3">
          <div className="flex items-center gap-2 mb-2.5">
            <span className="flex items-center justify-center w-5 h-5 rounded-full bg-muted text-[10px] font-bold text-muted-foreground">
              1
            </span>
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              Classification Decision
            </span>
          </div>

          {/* Toggle buttons styled as segmented control */}
          <div className="flex p-1 bg-muted rounded-lg">
            <button
              onClick={() => onReviewActionChange("confirm")}
              className={cn(
                "flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-md text-sm font-medium transition-all duration-200",
                reviewAction === "confirm"
                  ? "bg-white dark:bg-card text-green-700 dark:text-green-400 shadow-sm ring-1 ring-green-200 dark:ring-green-800"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {reviewAction === "confirm" && (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                </svg>
              )}
              Confirm
            </button>
            <button
              onClick={() => onReviewActionChange("change")}
              className={cn(
                "flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-md text-sm font-medium transition-all duration-200",
                reviewAction === "change"
                  ? "bg-white dark:bg-card text-amber-700 dark:text-amber-400 shadow-sm ring-1 ring-amber-200 dark:ring-amber-800"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {reviewAction === "change" && (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
                </svg>
              )}
              Override
            </button>
          </div>

          {/* Doc type selector (when changing) */}
          {reviewAction === "change" && (
            <div className="mt-3 animate-in slide-in-from-top-2 duration-200">
              <label className="block text-xs font-medium text-muted-foreground mb-1.5">
                Select correct document type
              </label>
              <select
                value={newDocType}
                onChange={(e) => onNewDocTypeChange(e.target.value)}
                className={cn(
                  "w-full border-2 rounded-lg px-3 py-2 text-sm bg-background transition-colors",
                  newDocType
                    ? "border-amber-300 dark:border-amber-700"
                    : "border-amber-200 dark:border-amber-800"
                )}
              >
                <option value="">Select correct type...</option>
                {DOC_TYPES.filter((t) => t !== detail.predicted_type).map((type) => (
                  <option key={type} value={type}>
                    {formatDocType(type)}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        {/* Divider */}
        <div className="mx-4 border-t border-dashed" />

        {/* Step 2: Notes & Save */}
        <div className="px-4 pt-3 pb-4">
          <div className="flex items-center gap-2 mb-2.5">
            <span className="flex items-center justify-center w-5 h-5 rounded-full bg-muted text-[10px] font-bold text-muted-foreground">
              2
            </span>
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              Save Review
            </span>
          </div>

          {/* Notes */}
          <textarea
            value={notes}
            onChange={(e) => onNotesChange(e.target.value)}
            className="w-full border rounded-lg px-3 py-2 text-sm bg-background placeholder:text-muted-foreground/60 focus:ring-2 focus:ring-primary/20 focus:border-primary transition-shadow"
            rows={2}
            placeholder="Add notes (optional)..."
          />

          {/* Save button - prominent and distinct */}
          <button
            onClick={onSave}
            disabled={saving || !canSave}
            className={cn(
              "w-full mt-3 px-4 py-2.5 rounded-lg text-sm font-semibold transition-all duration-200",
              saving || !canSave
                ? "bg-muted text-muted-foreground cursor-not-allowed"
                : "bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white shadow-md hover:shadow-lg hover:-translate-y-0.5 active:translate-y-0"
            )}
          >
            {saving ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Saving...
              </span>
            ) : (
              <span className="flex items-center justify-center gap-2">
                Save & Continue
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
              </span>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
