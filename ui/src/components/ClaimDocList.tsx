import { cn } from "../lib/utils";
import type { DocSummary } from "../types";

interface ClaimDocListProps {
  documents: DocSummary[];
  selectedDocId: string | null;
  onSelectDoc: (docId: string) => void;
}

function formatSourceType(sourceType: string): string {
  const labels: Record<string, string> = {
    pdf: "PDF",
    image: "Image",
    text: "Text",
  };
  return labels[sourceType] || sourceType;
}

export function ClaimDocList({
  documents,
  selectedDocId,
  onSelectDoc,
}: ClaimDocListProps) {
  if (documents.length === 0) {
    return (
      <div className="h-full flex items-center justify-center text-sm text-muted-foreground">
        No documents
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="px-3 py-2 text-xs font-medium text-muted-foreground border-b border-border bg-muted/30">
        {documents.length} document{documents.length !== 1 ? "s" : ""}
      </div>
      {documents.map((doc) => {
        // Build subtitle parts: doc_type · source_type · page_count pages
        const subtitleParts = [doc.doc_type];
        if (doc.source_type && doc.source_type !== "unknown") {
          subtitleParts.push(formatSourceType(doc.source_type));
        }
        if (doc.page_count > 0) {
          subtitleParts.push(`${doc.page_count} ${doc.page_count === 1 ? "page" : "pages"}`);
        }

        return (
          <button
            key={doc.doc_id}
            onClick={() => onSelectDoc(doc.doc_id)}
            className={cn(
              "w-full text-left px-3 py-2 border-b border-border transition-colors",
              selectedDocId === doc.doc_id
                ? "bg-primary/10 border-l-2 border-l-primary"
                : "hover:bg-muted/50"
            )}
          >
            {/* Line 1: Filename + checkmark if reviewed */}
            <div className="flex items-center gap-2">
              <span
                className="text-sm font-medium text-foreground truncate"
                title={doc.filename}
              >
                {doc.filename}
              </span>
              {doc.has_labels && (
                <svg className="w-3.5 h-3.5 text-green-600 dark:text-green-400 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                </svg>
              )}
            </div>
            {/* Line 2: doc_type · source_type · page_count */}
            <div className="text-xs text-muted-foreground truncate mt-0.5">
              {subtitleParts.join(" · ")}
            </div>
          </button>
        );
      })}
    </div>
  );
}
