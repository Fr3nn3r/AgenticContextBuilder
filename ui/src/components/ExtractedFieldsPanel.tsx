import { cn } from "../lib/utils";
import type { ExtractionResult, ExtractedField } from "../types";
import type { DocRunInfo } from "../api/client";

interface ExtractedFieldsPanelProps {
  extraction: ExtractionResult | null;
  runs: DocRunInfo[];
  selectedRunId: string | null;
  onRunChange: (runId: string) => void;
  onEvidenceClick: (
    page: number,
    charStart: number,
    charEnd: number,
    quote: string,
    value: string | null
  ) => void;
  hasSelectedDoc?: boolean;
}

function getConfidenceColor(confidence: number): string {
  if (confidence >= 0.9) return "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400";
  if (confidence >= 0.7) return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400";
  return "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400";
}

function FieldRow({
  field,
  onEvidenceClick,
}: {
  field: ExtractedField;
  onEvidenceClick: ExtractedFieldsPanelProps["onEvidenceClick"];
}) {
  const hasEvidence = field.provenance && field.provenance.length > 0;
  const firstProvenance = hasEvidence ? field.provenance[0] : null;

  const handleEvidenceClick = () => {
    if (firstProvenance) {
      onEvidenceClick(
        firstProvenance.page,
        firstProvenance.char_start,
        firstProvenance.char_end,
        firstProvenance.text_quote,
        field.value
      );
    }
  };

  return (
    <div className="py-2 px-3 border-b border-border last:border-b-0 hover:bg-muted/30">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-foreground truncate">
            {field.name}
          </div>
          <div className="text-sm text-muted-foreground mt-0.5 break-words">
            {field.value || <span className="italic">—</span>}
          </div>
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          <span
            className={cn(
              "text-xs px-1.5 py-0.5 rounded font-medium",
              getConfidenceColor(field.confidence)
            )}
          >
            {Math.round(field.confidence * 100)}%
          </span>
          {hasEvidence && (
            <button
              onClick={handleEvidenceClick}
              className="p-1 text-muted-foreground hover:text-foreground hover:bg-muted rounded transition-colors"
              title="Jump to evidence"
            >
              <MapPinIcon className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export function ExtractedFieldsPanel({
  extraction,
  runs,
  selectedRunId,
  onRunChange,
  onEvidenceClick,
  hasSelectedDoc = false,
}: ExtractedFieldsPanelProps) {
  const fields = extraction?.fields || [];

  return (
    <div className="flex flex-col h-full bg-card border-l border-border">
      {/* Run selector */}
      <div className="p-3 border-b border-border">
        <label className="text-xs font-medium text-muted-foreground block mb-1.5">
          Run
        </label>
        <select
          value={selectedRunId || ""}
          onChange={(e) => onRunChange(e.target.value)}
          className="w-full px-2 py-1.5 text-sm bg-background border border-border rounded-md focus:outline-none focus:ring-2 focus:ring-primary/50"
        >
          {runs.length === 0 && (
            <option value="">No runs available</option>
          )}
          {runs.map((run) => (
            <option key={run.run_id} value={run.run_id}>
              {run.run_id}
            </option>
          ))}
        </select>
      </div>

      {/* Fields list */}
      <div className="flex-1 overflow-y-auto">
        {extraction === null ? (
          <div className="p-4 text-sm text-muted-foreground text-center">
            {hasSelectedDoc
              ? "No extraction data available for this document"
              : "Select a document to view extracted fields"}
          </div>
        ) : fields.length === 0 ? (
          <div className="p-4 text-sm text-muted-foreground text-center">
            No fields extracted
          </div>
        ) : (
          <div>
            <div className="px-3 py-2 text-xs font-medium text-muted-foreground border-b border-border bg-muted/30">
              {fields.length} field{fields.length !== 1 ? "s" : ""}
            </div>
            {fields.map((field) => (
              <FieldRow
                key={field.name}
                field={field}
                onEvidenceClick={onEvidenceClick}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// Icon component
function MapPinIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"
      />
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"
      />
    </svg>
  );
}
