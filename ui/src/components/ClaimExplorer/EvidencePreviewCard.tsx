import { FileText, ExternalLink, X } from "lucide-react";
import { cn } from "../../lib/utils";
import type { DocSummary } from "../../types";

interface EvidencePreviewCardProps {
  document: DocSummary | null;
  highlightText?: string;
  onViewFull?: () => void;
  onClose?: () => void;
  className?: string;
}

function formatDocType(docType: string): string {
  return docType
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

/**
 * Mini document preview card with optional text highlight.
 * Used in the right column to show selected evidence.
 */
export function EvidencePreviewCard({
  document,
  highlightText,
  onViewFull,
  onClose,
  className,
}: EvidencePreviewCardProps) {
  if (!document) {
    return (
      <div className={cn(
        "bg-card rounded-lg border border-dashed border-border overflow-hidden",
        className
      )}>
        <div className="p-6 text-center">
          <FileText className="h-8 w-8 text-muted-foreground/30 mx-auto mb-2" />
          <p className="text-sm text-muted-foreground">
            Select evidence to preview
          </p>
          <p className="text-xs text-muted-foreground/70 mt-1">
            Click an evidence link to see the source
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className={cn(
      "bg-card rounded-lg border border-border overflow-hidden",
      className
    )}>
      {/* Header */}
      <div className="px-4 py-3 border-b border-border bg-muted/50 flex items-center justify-between">
        <div className="flex items-center gap-2 min-w-0">
          <FileText className="h-4 w-4 text-muted-foreground flex-shrink-0" />
          <div className="min-w-0">
            <span className="text-sm font-semibold text-foreground truncate block">
              {document.filename}
            </span>
            <span className="text-xs text-muted-foreground">
              {formatDocType(document.doc_type)}
              {document.page_count > 0 && ` · ${document.page_count} pages`}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-1">
          {onViewFull && (
            <button
              onClick={onViewFull}
              className="p-1.5 rounded hover:bg-muted text-muted-foreground hover:text-foreground"
              title="View full document"
            >
              <ExternalLink className="h-4 w-4" />
            </button>
          )}
          {onClose && (
            <button
              onClick={onClose}
              className="p-1.5 rounded hover:bg-muted text-muted-foreground hover:text-foreground"
              title="Close preview"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {/* Preview area */}
      <div className="p-4">
        {/* Document thumbnail placeholder */}
        <div className="aspect-[4/3] bg-muted rounded-lg flex items-center justify-center mb-3">
          <div className="text-center">
            <FileText className="h-12 w-12 text-muted-foreground/30 mx-auto mb-2" />
            <span className="text-xs text-muted-foreground">
              Document Preview
            </span>
          </div>
        </div>

        {/* Highlighted text (if any) */}
        {highlightText && (
          <div className="mt-3 p-3 bg-warning/10 border border-warning/30 rounded-lg">
            <span className="text-[10px] uppercase tracking-wider text-warning font-semibold block mb-1">
              Highlighted Evidence
            </span>
            <p className="text-sm text-foreground line-clamp-3">
              "{highlightText}"
            </p>
          </div>
        )}

        {/* View full button */}
        {onViewFull && (
          <button
            onClick={onViewFull}
            className={cn(
              "w-full mt-3 py-2 px-4 rounded-lg text-sm font-medium transition-colors",
              "bg-muted hover:bg-muted/80",
              "text-foreground"
            )}
          >
            Open Full Document
          </button>
        )}
      </div>
    </div>
  );
}
