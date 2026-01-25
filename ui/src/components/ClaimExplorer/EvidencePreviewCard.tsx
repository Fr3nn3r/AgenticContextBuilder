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
        "bg-white dark:bg-slate-900 rounded-lg border border-dashed border-slate-300 dark:border-slate-700 overflow-hidden",
        className
      )}>
        <div className="p-6 text-center">
          <FileText className="h-8 w-8 text-slate-300 dark:text-slate-600 mx-auto mb-2" />
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Select evidence to preview
          </p>
          <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">
            Click an evidence link to see the source
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className={cn(
      "bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden",
      className
    )}>
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 flex items-center justify-between">
        <div className="flex items-center gap-2 min-w-0">
          <FileText className="h-4 w-4 text-slate-500 flex-shrink-0" />
          <div className="min-w-0">
            <span className="text-sm font-semibold text-slate-700 dark:text-slate-200 truncate block">
              {document.filename}
            </span>
            <span className="text-xs text-slate-400">
              {formatDocType(document.doc_type)}
              {document.page_count > 0 && ` · ${document.page_count} pages`}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-1">
          {onViewFull && (
            <button
              onClick={onViewFull}
              className="p-1.5 rounded hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
              title="View full document"
            >
              <ExternalLink className="h-4 w-4" />
            </button>
          )}
          {onClose && (
            <button
              onClick={onClose}
              className="p-1.5 rounded hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
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
        <div className="aspect-[4/3] bg-slate-100 dark:bg-slate-800 rounded-lg flex items-center justify-center mb-3">
          <div className="text-center">
            <FileText className="h-12 w-12 text-slate-300 dark:text-slate-600 mx-auto mb-2" />
            <span className="text-xs text-slate-400 dark:text-slate-500">
              Document Preview
            </span>
          </div>
        </div>

        {/* Highlighted text (if any) */}
        {highlightText && (
          <div className="mt-3 p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg">
            <span className="text-[10px] uppercase tracking-wider text-amber-600 dark:text-amber-400 font-semibold block mb-1">
              Highlighted Evidence
            </span>
            <p className="text-sm text-amber-800 dark:text-amber-200 line-clamp-3">
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
              "bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700",
              "text-slate-700 dark:text-slate-200"
            )}
          >
            Open Full Document
          </button>
        )}
      </div>
    </div>
  );
}
