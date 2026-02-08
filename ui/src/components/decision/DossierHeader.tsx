import { cn } from "../../lib/utils";
import { StatusBadge } from "../shared";
import { VersionHistory } from "./VersionHistory";
import type {
  DecisionDossier,
  DossierVersionMeta,
  ClaimVerdictType,
} from "../../types";

interface DossierHeaderProps {
  dossier: DecisionDossier;
  versions: DossierVersionMeta[];
  onVersionChange: (v: number) => void;
  onRerun: () => void;
  loading?: boolean;
}

const verdictConfig: Record<
  ClaimVerdictType,
  { label: string; variant: "success" | "error" | "warning" }
> = {
  APPROVE: { label: "APPROVE", variant: "success" },
  DENY: { label: "DENY", variant: "error" },
  REFER: { label: "REFER", variant: "warning" },
};

export function DossierHeader({
  dossier,
  versions,
  onVersionChange,
  onRerun,
  loading,
}: DossierHeaderProps) {
  const verdict = verdictConfig[dossier.claim_verdict];
  const timestamp = dossier.evaluation_timestamp
    ? new Date(dossier.evaluation_timestamp).toLocaleString()
    : "N/A";

  return (
    <div className="bg-card border border-border rounded-lg p-4 shadow-sm">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        {/* Left: Claim ID + Verdict */}
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-foreground">
            {dossier.claim_id}
          </h2>
          <StatusBadge variant={verdict.variant} size="md">
            {verdict.label}
          </StatusBadge>
          <span className="text-sm text-muted-foreground">
            v{dossier.version}
          </span>
        </div>

        {/* Right: Version picker + Re-run */}
        <div className="flex items-center gap-3">
          {versions.length > 1 && (
            <VersionHistory
              versions={versions}
              currentVersion={dossier.version}
              onSelect={onVersionChange}
            />
          )}
          <button
            onClick={onRerun}
            disabled={loading}
            className={cn(
              "px-3 py-1.5 text-sm font-medium rounded-md border transition-colors",
              loading
                ? "opacity-50 cursor-not-allowed border-border text-muted-foreground"
                : "border-primary/30 text-primary bg-primary/10 hover:bg-primary/20"
            )}
          >
            {loading ? "Evaluating..." : "Re-run"}
          </button>
        </div>
      </div>

      {/* Second row: metadata */}
      <div className="mt-3 flex items-center gap-4 text-xs text-muted-foreground flex-wrap">
        <span>Evaluated: {timestamp}</span>
        <span className="text-border">|</span>
        <span>
          Engine: {dossier.engine_id} v{dossier.engine_version}
        </span>
        {dossier.failed_clauses.length > 0 && (
          <>
            <span className="text-border">|</span>
            <span className="text-destructive">
              {dossier.failed_clauses.length} failed clause
              {dossier.failed_clauses.length !== 1 ? "s" : ""}
            </span>
          </>
        )}
        {dossier.unresolved_assumptions.length > 0 && (
          <>
            <span className="text-border">|</span>
            <span className="text-warning-foreground">
              {dossier.unresolved_assumptions.length} unresolved assumption
              {dossier.unresolved_assumptions.length !== 1 ? "s" : ""}
            </span>
          </>
        )}
      </div>

      {/* Verdict reason */}
      {dossier.verdict_reason && (
        <p className="mt-2 text-sm text-muted-foreground italic">
          {dossier.verdict_reason}
        </p>
      )}
    </div>
  );
}
