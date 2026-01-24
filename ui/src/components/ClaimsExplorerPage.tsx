import { useState, useEffect, useCallback } from "react";
import type { ClaimSummary } from "../types";
import { listClaims } from "../api/client";
import { ClaimTab } from "./ClaimTab";
import { cn } from "../lib/utils";
import { ThemePopover, HeaderUserMenu } from "./shared";

interface TabInfo {
  claimId: string;
  label: string;
}

export function ClaimsExplorerPage() {
  // Tab state
  const [openTabs, setOpenTabs] = useState<TabInfo[]>([]);
  const [activeTab, setActiveTab] = useState<string>("overview");

  // Claims data for overview
  const [claims, setClaims] = useState<ClaimSummary[]>([]);
  const [claimsLoading, setClaimsLoading] = useState(true);

  // Load claims for overview
  useEffect(() => {
    let cancelled = false;

    async function loadClaims() {
      setClaimsLoading(true);
      try {
        const data = await listClaims();
        if (!cancelled) {
          setClaims(data);
        }
      } catch (err) {
        console.error("Failed to load claims:", err);
      } finally {
        if (!cancelled) {
          setClaimsLoading(false);
        }
      }
    }

    loadClaims();

    return () => {
      cancelled = true;
    };
  }, []);

  // Open a claim in a new tab (or focus existing)
  const openClaimTab = useCallback((claimId: string) => {
    setOpenTabs((prev) => {
      const existing = prev.find((t) => t.claimId === claimId);
      if (existing) {
        // Tab already exists, just switch to it
        return prev;
      }
      // Add new tab
      return [...prev, { claimId, label: claimId }];
    });
    setActiveTab(claimId);
  }, []);

  // Close a tab
  const closeTab = useCallback(
    (claimId: string, e: React.MouseEvent) => {
      e.stopPropagation();
      setOpenTabs((prev) => prev.filter((t) => t.claimId !== claimId));

      // If closing the active tab, switch to overview or another tab
      if (activeTab === claimId) {
        const remainingTabs = openTabs.filter((t) => t.claimId !== claimId);
        if (remainingTabs.length > 0) {
          setActiveTab(remainingTabs[remainingTabs.length - 1].claimId);
        } else {
          setActiveTab("overview");
        }
      }
    },
    [activeTab, openTabs]
  );

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <header className="bg-card border-b border-border px-6 py-3 flex items-center justify-between flex-shrink-0">
        <h1 className="text-xl font-semibold text-foreground">Claim Explorer</h1>
        <div className="flex items-center gap-2">
          <ThemePopover />
          <HeaderUserMenu />
        </div>
      </header>

      {/* Tab bar */}
      <div className="flex items-center bg-muted/30 border-b border-border px-2 overflow-x-auto flex-shrink-0">
        {/* Overview tab (always present) */}
        <button
          onClick={() => setActiveTab("overview")}
          className={cn(
            "flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors whitespace-nowrap",
            activeTab === "overview"
              ? "border-primary text-foreground bg-card"
              : "border-transparent text-muted-foreground hover:text-foreground hover:bg-card/50"
          )}
        >
          <OverviewIcon className="w-4 h-4" />
          Overview
        </button>

        {/* Claim tabs */}
        {openTabs.map((tab) => (
          <button
            key={tab.claimId}
            onClick={() => setActiveTab(tab.claimId)}
            className={cn(
              "flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors whitespace-nowrap group",
              activeTab === tab.claimId
                ? "border-primary text-foreground bg-card"
                : "border-transparent text-muted-foreground hover:text-foreground hover:bg-card/50"
            )}
          >
            <span className="truncate max-w-[150px]" title={tab.label}>
              {tab.label}
            </span>
            <span
              onClick={(e) => closeTab(tab.claimId, e)}
              className="ml-1 p-0.5 rounded hover:bg-destructive/20 hover:text-destructive transition-colors"
              title="Close tab"
            >
              <CloseIcon className="w-3.5 h-3.5" />
            </span>
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-hidden">
        {activeTab === "overview" ? (
          <OverviewPanel
            claims={claims}
            loading={claimsLoading}
            onOpenClaim={openClaimTab}
          />
        ) : (
          <ClaimTab key={activeTab} claimId={activeTab} />
        )}
      </div>
    </div>
  );
}

// Overview panel showing all claims
interface OverviewPanelProps {
  claims: ClaimSummary[];
  loading: boolean;
  onOpenClaim: (claimId: string) => void;
}

function OverviewPanel({ claims, loading, onOpenClaim }: OverviewPanelProps) {
  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-muted-foreground">Loading claims...</div>
      </div>
    );
  }

  if (claims.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-muted-foreground">No claims found</div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto p-6">
      <div className="mb-4 text-sm text-muted-foreground">
        {claims.length} claim{claims.length !== 1 ? "s" : ""} found. Click a claim to open it in a new tab.
      </div>
      <div className="grid gap-3">
        {claims.map((claim) => (
          <button
            key={claim.claim_id}
            onClick={() => onOpenClaim(claim.claim_id)}
            className="w-full text-left p-4 bg-card border border-border rounded-lg hover:bg-muted/50 hover:border-primary/50 transition-colors"
          >
            <div className="flex items-center justify-between">
              <div className="font-medium text-foreground">{claim.claim_id}</div>
              <div className="text-sm text-muted-foreground">
                {claim.doc_count} document{claim.doc_count !== 1 ? "s" : ""}
              </div>
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {claim.doc_types.slice(0, 5).map((dt) => (
                <span
                  key={dt}
                  className="text-xs px-2 py-0.5 bg-muted rounded text-muted-foreground"
                >
                  {dt}
                </span>
              ))}
              {claim.doc_types.length > 5 && (
                <span className="text-xs px-2 py-0.5 bg-muted rounded text-muted-foreground">
                  +{claim.doc_types.length - 5} more
                </span>
              )}
            </div>
            <div className="mt-2 flex items-center gap-4 text-xs text-muted-foreground">
              <span>Extracted: {claim.extracted_count}</span>
              <span>Labeled: {claim.labeled_count}</span>
              {claim.gate_pass_count + claim.gate_warn_count + claim.gate_fail_count > 0 && (
                <span className="flex items-center gap-1">
                  <span className="text-green-600 dark:text-green-400">{claim.gate_pass_count}</span>
                  /
                  <span className="text-yellow-600 dark:text-yellow-400">{claim.gate_warn_count}</span>
                  /
                  <span className="text-red-600 dark:text-red-400">{claim.gate_fail_count}</span>
                </span>
              )}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

// Icon components
function OverviewIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"
      />
    </svg>
  );
}

function CloseIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
}
