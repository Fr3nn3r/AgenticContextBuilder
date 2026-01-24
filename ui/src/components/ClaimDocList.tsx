import { cn } from "../lib/utils";
import type { DocSummary } from "../types";

interface ClaimDocListProps {
  documents: DocSummary[];
  selectedDocId: string | null;
  onSelectDoc: (docId: string) => void;
}

function getDocTypeBadgeColor(docType: string): string {
  // Consistent color mapping based on doc type hash
  const hash = docType.split("").reduce((acc, char) => acc + char.charCodeAt(0), 0);
  const colors = [
    "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
    "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400",
    "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
    "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400",
    "bg-pink-100 text-pink-800 dark:bg-pink-900/30 dark:text-pink-400",
    "bg-cyan-100 text-cyan-800 dark:bg-cyan-900/30 dark:text-cyan-400",
  ];
  return colors[hash % colors.length];
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
      {documents.map((doc) => (
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
          <div
            className="text-sm font-medium text-foreground truncate"
            title={doc.filename}
          >
            {doc.filename}
          </div>
          <div className="mt-1">
            <span
              className={cn(
                "inline-block text-xs px-1.5 py-0.5 rounded font-medium",
                getDocTypeBadgeColor(doc.doc_type)
              )}
            >
              {doc.doc_type}
            </span>
          </div>
        </button>
      ))}
    </div>
  );
}
