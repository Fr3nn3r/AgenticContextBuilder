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
          ? "bg-primary text-primary-foreground"
          : "bg-muted text-muted-foreground hover:bg-muted/80"
      )}
    >
      {label}
      {count > 0 && (
        <span className={cn(
          "ml-1",
          isActive ? "opacity-70" : "text-muted-foreground"
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
        "group flex items-center gap-3 px-3 py-2.5 border-b border-border last:border-b-0",
        "transition-all hover:bg-muted/50",
        onClick && "cursor-pointer"
      )}
      onClick={onClick}
    >
      {/* Icon with type indicator */}
      <div className={cn(
        "w-8 h-8 rounded flex items-center justify-center flex-shrink-0",
        type === "pdf" && "bg-destructive/10",
        type === "image" && "bg-info/10",
        type === "other" && "bg-muted"
      )}>
        <Icon className={cn(
          "h-4 w-4",
          type === "pdf" && "text-destructive",
          type === "image" && "text-info",
          type === "other" && "text-muted-foreground"
        )} />
      </div>

      {/* File info */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-foreground truncate group-hover:text-foreground transition-colors">
          {doc.filename}
        </p>
        <p className="text-xs text-muted-foreground">
          {formatDocType(doc.doc_type)}
          {doc.page_count > 0 && (
            <span className="ml-1.5 opacity-70">
              · {doc.page_count} page{doc.page_count !== 1 ? "s" : ""}
            </span>
          )}
        </p>
      </div>

      {/* Hover arrow */}
      <div className="opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground">
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
      <div className="bg-card rounded-lg border border-border p-4">
        <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-2">
          Source Documents
        </h3>
        <p className="text-sm text-muted-foreground">No documents</p>
      </div>
    );
  }

  return (
    <div className="bg-card rounded-lg border border-border overflow-hidden">
      {/* Header with filters */}
      <div className="px-3 py-2.5 border-b border-border bg-muted/50">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <Filter className="h-3.5 w-3.5 text-muted-foreground" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
              Documents
            </h3>
          </div>
          <span className="text-xs text-muted-foreground font-mono">
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
          <div className="p-4 text-center text-sm text-muted-foreground">
            No {filter} documents
          </div>
        )}
      </div>
    </div>
  );
}
