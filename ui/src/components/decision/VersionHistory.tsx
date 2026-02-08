import { cn } from "../../lib/utils";
import { StatusBadge } from "../shared";
import type { DossierVersionMeta, ClaimVerdictType } from "../../types";

interface VersionHistoryProps {
  versions: DossierVersionMeta[];
  currentVersion: number;
  onSelect: (version: number) => void;
}

const verdictVariant: Record<ClaimVerdictType, "success" | "error" | "warning"> = {
  APPROVE: "success",
  DENY: "error",
  REFER: "warning",
};

export function VersionHistory({
  versions,
  currentVersion,
  onSelect,
}: VersionHistoryProps) {
  return (
    <div className="relative inline-block">
      <select
        value={currentVersion}
        onChange={(e) => onSelect(Number(e.target.value))}
        className={cn(
          "text-sm border border-border rounded-md px-2 py-1.5 bg-background text-foreground",
          "appearance-none pr-7 cursor-pointer"
        )}
      >
        {versions.map((v) => {
          const ts = v.evaluation_timestamp
            ? new Date(v.evaluation_timestamp).toLocaleString(undefined, {
                month: "short",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              })
            : "N/A";
          const verdictLabel = v.claim_verdict || "?";
          return (
            <option key={v.version} value={v.version}>
              v{v.version} - {verdictLabel} - {ts}
            </option>
          );
        })}
      </select>
      {/* Dropdown chevron */}
      <svg
        className="w-4 h-4 absolute right-1.5 top-1/2 -translate-y-1/2 pointer-events-none text-muted-foreground"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M19 9l-7 7-7-7"
        />
      </svg>
    </div>
  );
}

/**
 * Expanded version history list for sidebar or panel display.
 * Shows versions as clickable cards with verdict badges.
 */
export function VersionHistoryList({
  versions,
  currentVersion,
  onSelect,
}: VersionHistoryProps) {
  return (
    <div className="space-y-1.5">
      {versions.map((v) => {
        const isCurrent = v.version === currentVersion;
        const ts = v.evaluation_timestamp
          ? new Date(v.evaluation_timestamp).toLocaleString()
          : "N/A";

        return (
          <button
            key={v.version}
            onClick={() => onSelect(v.version)}
            className={cn(
              "w-full text-left px-3 py-2 rounded-md text-sm transition-colors border",
              isCurrent
                ? "bg-accent/10 border-accent text-foreground"
                : "bg-card border-border text-muted-foreground hover:bg-muted/50"
            )}
          >
            <div className="flex items-center justify-between">
              <span className="font-medium">
                Version {v.version}
                {isCurrent && (
                  <span className="ml-1 text-xs text-accent">(current)</span>
                )}
              </span>
              {v.claim_verdict && (
                <StatusBadge
                  variant={verdictVariant[v.claim_verdict]}
                  size="sm"
                >
                  {v.claim_verdict}
                </StatusBadge>
              )}
            </div>
            <div className="text-xs text-muted-foreground mt-0.5">{ts}</div>
            {(v.failed_clauses_count > 0 || v.unresolved_count > 0) && (
              <div className="flex gap-2 mt-1 text-xs">
                {v.failed_clauses_count > 0 && (
                  <span className="text-destructive">
                    {v.failed_clauses_count} failed
                  </span>
                )}
                {v.unresolved_count > 0 && (
                  <span className="text-warning-foreground">
                    {v.unresolved_count} unresolved
                  </span>
                )}
              </div>
            )}
          </button>
        );
      })}
    </div>
  );
}
