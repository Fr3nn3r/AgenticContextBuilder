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
      <div className="border-t bg-card p-4 space-y-3 flex-shrink-0">
        {/* Confirm/Change toggle */}
        <div className="flex gap-2">
          <button
            onClick={() => onReviewActionChange("confirm")}
            className={cn(
              "flex-1 px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
              reviewAction === "confirm"
                ? "bg-success text-white"
                : "bg-muted text-foreground hover:bg-muted/80"
            )}
          >
            Confirm
          </button>
          <button
            onClick={() => onReviewActionChange("change")}
            className={cn(
              "flex-1 px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
              reviewAction === "change"
                ? "bg-warning text-white"
                : "bg-muted text-foreground hover:bg-muted/80"
            )}
          >
            Change Type
          </button>
        </div>

        {/* Doc type selector (when changing) */}
        {reviewAction === "change" && (
          <select
            value={newDocType}
            onChange={(e) => onNewDocTypeChange(e.target.value)}
            className="w-full border rounded-md px-2 py-1.5 text-sm bg-background"
          >
            <option value="">Select correct type...</option>
            {DOC_TYPES.filter((t) => t !== detail.predicted_type).map((type) => (
              <option key={type} value={type}>
                {formatDocType(type)}
              </option>
            ))}
          </select>
        )}

        {/* Notes */}
        <textarea
          value={notes}
          onChange={(e) => onNotesChange(e.target.value)}
          className="w-full border rounded-md px-2 py-1.5 text-sm bg-background"
          rows={2}
          placeholder="Notes (optional)..."
        />

        {/* Save button */}
        <button
          onClick={onSave}
          disabled={saving || !canSave}
          className={cn(
            "w-full px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
            saving || !canSave
              ? "bg-muted text-muted-foreground cursor-not-allowed"
              : "bg-primary text-white hover:bg-primary/90"
          )}
        >
          {saving ? "Saving..." : "Save Review"}
        </button>
      </div>
    </div>
  );
}
