import { useState } from "react";
import { FileText, FileImage, File, Filter } from "lucide-react";
import type { DocSummary } from "../../types";
import { cn } from "../../lib/utils";

interface DocumentsPanelProps {
  documents: DocSummary[];
  onDocumentClick?: (docId: string) => void;
}

type FilterType = "all" | "pdf" | "image";

const formatDocType = (docType: string) => {
  return docType
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
};

function getFileInfo(filename: string, sourceType: string): { icon: typeof FileText; type: "pdf" | "image" | "other" } {
  const ext = filename.split(".").pop()?.toLowerCase();

  if (ext === "pdf" || sourceType === "pdf") {
    return { icon: FileText, type: "pdf" };
  }
  if (["jpg", "jpeg", "png", "gif", "bmp", "tiff", "webp"].includes(ext || "")) {
    return { icon: FileImage, type: "image" };
  }
  return { icon: File, type: "other" };
}

// Filter toggle button
function FilterButton({
  label,
  count,
  isActive,
  onClick
}: {
  label: string;
  count: number;
  isActive: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "px-2 py-0.5 rounded text-[10px] font-medium uppercase tracking-wide transition-all",
        isActive
          ? "bg-slate-800 dark:bg-slate-200 text-white dark:text-slate-900"
          : "bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700"
      )}
    >
      {label}
      {count > 0 && (
        <span className={cn(
          "ml-1",
          isActive ? "text-slate-300 dark:text-slate-600" : "text-slate-400"
        )}>
          {count}
        </span>
      )}
    </button>
  );
}

// Document row with hover effects
function DocumentRow({
  doc,
  onClick
}: {
  doc: DocSummary;
  onClick?: () => void;
}) {
  const { icon: Icon, type } = getFileInfo(doc.filename, doc.source_type);

  return (
    <div
      className={cn(
        "group flex items-center gap-3 px-3 py-2.5 border-b border-slate-100 dark:border-slate-800 last:border-b-0",
        "transition-all hover:bg-slate-50 dark:hover:bg-slate-800/50",
        onClick && "cursor-pointer"
      )}
      onClick={onClick}
    >
      {/* Icon with type indicator */}
      <div className={cn(
        "w-8 h-8 rounded flex items-center justify-center flex-shrink-0",
        type === "pdf" && "bg-red-100 dark:bg-red-900/30",
        type === "image" && "bg-blue-100 dark:bg-blue-900/30",
        type === "other" && "bg-slate-100 dark:bg-slate-800"
      )}>
        <Icon className={cn(
          "h-4 w-4",
          type === "pdf" && "text-red-600 dark:text-red-400",
          type === "image" && "text-blue-600 dark:text-blue-400",
          type === "other" && "text-slate-500"
        )} />
      </div>

      {/* File info */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-slate-700 dark:text-slate-200 truncate group-hover:text-slate-900 dark:group-hover:text-white transition-colors">
          {doc.filename}
        </p>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          {formatDocType(doc.doc_type)}
          {doc.page_count > 0 && (
            <span className="ml-1.5 text-slate-400">
              · {doc.page_count} page{doc.page_count !== 1 ? "s" : ""}
            </span>
          )}
        </p>
      </div>

      {/* Hover arrow */}
      <div className="opacity-0 group-hover:opacity-100 transition-opacity text-slate-400">
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
      </div>
    </div>
  );
}

export function DocumentsPanel({ documents, onDocumentClick }: DocumentsPanelProps) {
  const [filter, setFilter] = useState<FilterType>("all");

  // Count documents by type
  const counts = documents.reduce(
    (acc, doc) => {
      const { type } = getFileInfo(doc.filename, doc.source_type);
      if (type === "pdf") acc.pdf++;
      else if (type === "image") acc.image++;
      acc.all++;
      return acc;
    },
    { all: 0, pdf: 0, image: 0 }
  );

  // Filter documents
  const filteredDocs = documents.filter(doc => {
    if (filter === "all") return true;
    const { type } = getFileInfo(doc.filename, doc.source_type);
    return type === filter;
  });

  if (!documents || documents.length === 0) {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700 p-4">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-2">
          Source Documents
        </h3>
        <p className="text-sm text-slate-500">No documents</p>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
      {/* Header with filters */}
      <div className="px-3 py-2.5 border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <Filter className="h-3.5 w-3.5 text-slate-400" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Documents
            </h3>
          </div>
          <span className="text-xs text-slate-400 font-mono">
            {filteredDocs.length}/{documents.length}
          </span>
        </div>

        {/* Filter buttons */}
        <div className="flex items-center gap-1.5">
          <FilterButton
            label="All"
            count={counts.all}
            isActive={filter === "all"}
            onClick={() => setFilter("all")}
          />
          {counts.pdf > 0 && (
            <FilterButton
              label="PDF"
              count={counts.pdf}
              isActive={filter === "pdf"}
              onClick={() => setFilter("pdf")}
            />
          )}
          {counts.image > 0 && (
            <FilterButton
              label="Images"
              count={counts.image}
              isActive={filter === "image"}
              onClick={() => setFilter("image")}
            />
          )}
        </div>
      </div>

      {/* Document list */}
      <div className="max-h-[280px] overflow-y-auto">
        {filteredDocs.map(doc => (
          <DocumentRow
            key={doc.doc_id}
            doc={doc}
            onClick={onDocumentClick ? () => onDocumentClick(doc.doc_id) : undefined}
          />
        ))}

        {filteredDocs.length === 0 && (
          <div className="p-4 text-center text-sm text-slate-500">
            No {filter} documents
          </div>
        )}
      </div>
    </div>
  );
}
