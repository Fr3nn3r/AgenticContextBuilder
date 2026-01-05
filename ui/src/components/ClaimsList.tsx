import type { ClaimSummary, DocSummary } from "../types";
import { cn } from "../lib/utils";

interface ClaimsListProps {
  claims: ClaimSummary[];
  selectedClaim: string | null;
  docs: DocSummary[];
  onSelectClaim: (claimId: string) => void;
  onSelectDoc: (docId: string) => void;
}

export function ClaimsList({
  claims,
  selectedClaim,
  docs,
  onSelectClaim,
  onSelectDoc,
}: ClaimsListProps) {
  return (
    <div className="bg-card rounded-lg border">
      <div className="p-4 border-b">
        <h2 className="text-lg font-semibold">Claims ({claims.length})</h2>
      </div>

      <div className="divide-y">
        {claims.map((claim) => (
          <div key={claim.claim_id}>
            {/* Claim header */}
            <button
              onClick={() => onSelectClaim(claim.claim_id)}
              className={cn(
                "w-full px-4 py-3 text-left hover:bg-secondary/50 transition-colors",
                selectedClaim === claim.claim_id && "bg-secondary"
              )}
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-medium">{claim.claim_id}</div>
                  <div className="text-sm text-muted-foreground">
                    {claim.doc_count} docs &middot;{" "}
                    {claim.extracted_count} extracted &middot;{" "}
                    {claim.labeled_count} labeled
                  </div>
                </div>
                <div className="flex gap-1">
                  {claim.doc_types.map((type) => (
                    <span
                      key={type}
                      className="text-xs px-2 py-0.5 bg-secondary rounded"
                    >
                      {type}
                    </span>
                  ))}
                </div>
              </div>
            </button>

            {/* Documents list (expanded) */}
            {selectedClaim === claim.claim_id && docs.length > 0 && (
              <div className="bg-secondary/30 border-t">
                {docs.map((doc) => (
                  <button
                    key={doc.doc_id}
                    onClick={() => onSelectDoc(doc.doc_id)}
                    className="w-full px-6 py-2 text-left hover:bg-secondary/50 transition-colors flex items-center justify-between"
                  >
                    <div className="flex items-center gap-3">
                      <QualityBadge status={doc.quality_status} />
                      <div>
                        <div className="text-sm font-medium">{doc.filename}</div>
                        <div className="text-xs text-muted-foreground">
                          {doc.doc_type} &middot; {doc.language}
                        </div>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      {doc.has_extraction && (
                        <span className="text-xs px-2 py-0.5 bg-blue-100 text-blue-700 rounded">
                          Extracted
                        </span>
                      )}
                      {doc.has_labels && (
                        <span className="text-xs px-2 py-0.5 bg-green-100 text-green-700 rounded">
                          Labeled
                        </span>
                      )}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function QualityBadge({ status }: { status: string | null }) {
  if (!status) {
    return <span className="w-2 h-2 rounded-full bg-gray-300"></span>;
  }

  const colors: Record<string, string> = {
    pass: "bg-green-500",
    warn: "bg-yellow-500",
    fail: "bg-red-500",
  };

  return (
    <span
      className={cn("w-2 h-2 rounded-full", colors[status] || "bg-gray-300")}
      title={status}
    ></span>
  );
}
