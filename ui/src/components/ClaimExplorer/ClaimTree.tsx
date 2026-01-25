import { useState } from "react";
import { Loader2, Folder, FileText, AlertTriangle, ChevronRight, ChevronDown } from "lucide-react";
import type { ClaimSummary, DocSummary } from "../../types";
import { cn } from "../../lib/utils";

interface ClaimWithDocs extends ClaimSummary {
  documents?: DocSummary[];
  docsLoading?: boolean;
}

interface ClaimTreeProps {
  claims: ClaimWithDocs[];
  loading: boolean;
  error: string | null;
  selectedClaimId: string | null;
  selectedDocId?: string | null;
  onSelectClaim: (claimId: string) => void;
  onSelectDocument?: (claimId: string, docId: string) => void;
}

// Status indicator - only show for errors
function ClaimStatusIcon({ claim }: { claim: ClaimSummary }) {
  if (claim.gate_fail_count > 0) {
    return <AlertTriangle className="h-3.5 w-3.5 text-red-500 flex-shrink-0" />;
  }
  return null;
}

// Document status indicator - only show for errors
function DocStatusIcon({ doc }: { doc: DocSummary }) {
  if (doc.quality_status === "fail") {
    return <AlertTriangle className="h-3 w-3 text-red-500 flex-shrink-0" />;
  }
  return null;
}

/**
 * Claims tree with nested documents.
 * Clicking a claim expands it to show documents underneath.
 */
export function ClaimTree({
  claims,
  loading,
  error,
  selectedClaimId,
  selectedDocId,
  onSelectClaim,
  onSelectDocument,
}: ClaimTreeProps) {
  const [expandedClaims, setExpandedClaims] = useState<Set<string>>(new Set());

  const toggleExpand = (claimId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setExpandedClaims((prev) => {
      const next = new Set(prev);
      if (next.has(claimId)) {
        next.delete(claimId);
      } else {
        next.add(claimId);
      }
      return next;
    });
  };

  const handleClaimClick = (claimId: string) => {
    onSelectClaim(claimId);
    // Auto-expand when selecting a claim
    setExpandedClaims((prev) => new Set(prev).add(claimId));
  };

  if (loading && claims.length === 0) {
    return (
      <div className="flex flex-col h-full">
        <div className="px-4 py-3 border-b border-border">
          <h2 className="text-sm font-semibold text-foreground">Claims</h2>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col h-full">
        <div className="px-4 py-3 border-b border-border">
          <h2 className="text-sm font-semibold text-foreground">Claims</h2>
        </div>
        <div className="flex-1 flex items-center justify-center p-4">
          <p className="text-sm text-destructive text-center">{error}</p>
        </div>
      </div>
    );
  }

  if (claims.length === 0) {
    return (
      <div className="flex flex-col h-full">
        <div className="px-4 py-3 border-b border-border">
          <h2 className="text-sm font-semibold text-foreground">Claims</h2>
        </div>
        <div className="flex-1 flex items-center justify-center p-4">
          <p className="text-sm text-muted-foreground text-center">
            No claims found
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border">
        <h2 className="text-sm font-semibold text-foreground">Claims</h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          {claims.length} claim{claims.length !== 1 ? "s" : ""}
        </p>
      </div>

      {/* Claims list */}
      <div className="flex-1 overflow-y-auto py-1">
        {claims.map((claim) => {
          const isSelected = selectedClaimId === claim.claim_id;
          const isExpanded = expandedClaims.has(claim.claim_id);
          const hasDocuments = claim.documents && claim.documents.length > 0;
          const isLoadingDocs = claim.docsLoading;

          return (
            <div key={claim.claim_id}>
              {/* Claim row */}
              <div
                className={cn(
                  "flex items-center gap-1 px-2 py-2 mx-2 my-0.5 rounded-md cursor-pointer transition-colors",
                  isSelected
                    ? "bg-primary/10 text-primary"
                    : "hover:bg-muted text-foreground"
                )}
                onClick={() => handleClaimClick(claim.claim_id)}
              >
                {/* Expand/collapse button */}
                <button
                  onClick={(e) => toggleExpand(claim.claim_id, e)}
                  className="p-0.5 hover:bg-muted-foreground/20 rounded transition-colors"
                >
                  {isExpanded ? (
                    <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                  ) : (
                    <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
                  )}
                </button>

                <Folder className="h-4 w-4 text-amber-500 flex-shrink-0" />

                <div className="flex-1 min-w-0 ml-1">
                  <div className="text-sm font-medium truncate">
                    {claim.claim_id}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {claim.doc_count} doc{claim.doc_count !== 1 ? "s" : ""}
                  </div>
                </div>

                <ClaimStatusIcon claim={claim} />
              </div>

              {/* Documents (when expanded) */}
              {isExpanded && (
                <div className="ml-6 border-l border-border/50">
                  {isLoadingDocs ? (
                    <div className="flex items-center gap-2 px-3 py-2 text-xs text-muted-foreground">
                      <Loader2 className="h-3 w-3 animate-spin" />
                      Loading documents...
                    </div>
                  ) : hasDocuments ? (
                    claim.documents!.map((doc) => {
                      const isDocSelected = selectedDocId === doc.doc_id;
                      return (
                        <div
                          key={doc.doc_id}
                          className={cn(
                            "flex items-center gap-2 px-3 py-1.5 mx-1 my-0.5 rounded cursor-pointer transition-colors text-sm",
                            isDocSelected
                              ? "bg-primary/10 text-primary"
                              : "hover:bg-muted text-muted-foreground hover:text-foreground"
                          )}
                          onClick={(e) => {
                            e.stopPropagation();
                            onSelectDocument?.(claim.claim_id, doc.doc_id);
                          }}
                        >
                          <FileText className="h-3.5 w-3.5 flex-shrink-0" />
                          <span className="truncate flex-1" title={doc.filename}>
                            {doc.filename}
                          </span>
                          <DocStatusIcon doc={doc} />
                        </div>
                      );
                    })
                  ) : (
                    <div className="px-3 py-2 text-xs text-muted-foreground italic">
                      No documents
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
