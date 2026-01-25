import { FileText, FileImage, File } from "lucide-react";
import type { DocSummary } from "../../types";
import { cn } from "../../lib/utils";

interface DocumentsTrayProps {
  documents: DocSummary[];
  onDocumentClick?: (docId: string) => void;
}

const formatDocType = (docType: string) => {
  return docType
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
};

function getFileIcon(filename: string, sourceType: string) {
  const ext = filename.split(".").pop()?.toLowerCase();

  if (ext === "pdf" || sourceType === "pdf") {
    return FileText;
  }
  if (["jpg", "jpeg", "png", "gif", "bmp", "tiff", "webp"].includes(ext || "")) {
    return FileImage;
  }
  return File;
}

export function DocumentsTray({ documents, onDocumentClick }: DocumentsTrayProps) {
  if (!documents || documents.length === 0) {
    return (
      <div className="bg-card rounded-lg border border-border shadow-sm">
        <div className="px-4 py-3 border-b border-border">
          <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Source Documents
          </h3>
        </div>
        <div className="p-4 text-center">
          <p className="text-sm text-muted-foreground">No documents</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-card rounded-lg border border-border shadow-sm hover:shadow-md transition-shadow">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border flex items-center justify-between">
        <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
          Source Documents
        </h3>
        <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
          {documents.length}
        </span>
      </div>

      {/* Document list */}
      <div className="divide-y divide-border">
        {documents.map((doc) => {
          const Icon = getFileIcon(doc.filename, doc.source_type);

          return (
            <div
              key={doc.doc_id}
              className={cn(
                "flex items-start gap-3 px-4 py-3",
                onDocumentClick &&
                  "cursor-pointer hover:bg-muted/30 transition-colors"
              )}
              onClick={() => onDocumentClick?.(doc.doc_id)}
            >
              <Icon className="h-4 w-4 flex-shrink-0 text-muted-foreground mt-0.5" />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-foreground truncate">
                  {doc.filename}
                </p>
                <p className="text-xs text-muted-foreground">
                  {formatDocType(doc.doc_type)}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
