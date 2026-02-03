import { useState, useEffect } from "react";
import { X } from "lucide-react";
import { cn } from "../../lib/utils";
import { getGroundTruthDocUrl } from "../../api/client";
import { DocumentViewer } from "../DocumentViewer";

interface GroundTruthDocPanelProps {
  claimId: string;
  onClose: () => void;
}

export function GroundTruthDocPanel({ claimId, onClose }: GroundTruthDocPanelProps) {
  const [isOpen, setIsOpen] = useState(false);
  const pdfUrl = getGroundTruthDocUrl(claimId);

  useEffect(() => {
    requestAnimationFrame(() => setIsOpen(true));
  }, []);

  return (
    <>
      {/* Backdrop */}
      <div
        className={cn(
          "fixed inset-0 bg-black/30 z-40 transition-opacity duration-300",
          isOpen ? "opacity-100" : "opacity-0"
        )}
        onClick={onClose}
      />

      {/* Slide Panel */}
      <div
        className={cn(
          "fixed top-0 right-0 h-full w-full max-w-3xl bg-card shadow-2xl z-50",
          "transform transition-transform duration-300 ease-out",
          "flex flex-col",
          isOpen ? "translate-x-0" : "translate-x-full"
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-muted/50">
          <div className="min-w-0">
            <h2 className="text-sm font-semibold text-foreground">
              Ground Truth Decision
            </h2>
            <p className="text-xs text-muted-foreground">
              Claim {claimId}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* PDF content via DocumentViewer */}
        <div className="flex-1 overflow-hidden">
          <DocumentViewer
            pages={[]}
            sourceUrl={pdfUrl}
            hasPdf={true}
            hasImage={false}
            extraction={null}
          />
        </div>
      </div>
    </>
  );
}
