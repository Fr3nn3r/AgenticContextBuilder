import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { verifyDecisionLedger, listDecisions, listVersionBundles } from "../../api/client";
import type { VerificationResult, DecisionRecord, VersionBundleSummary } from "../../types";

export function ComplianceOverview() {
  const [verification, setVerification] = useState<VerificationResult | null>(null);
  const [recentDecisions, setRecentDecisions] = useState<DecisionRecord[]>([]);
  const [bundles, setBundles] = useState<VersionBundleSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    try {
      setLoading(true);
      setError(null);
      const [verifyResult, decisions, bundleList] = await Promise.all([
        verifyDecisionLedger(),
        listDecisions({ limit: 5 }),
        listVersionBundles(),
      ]);
      setVerification(verifyResult);
      setRecentDecisions(decisions);
      setBundles(bundleList.slice(0, 5));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load compliance data");
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted-foreground">Loading compliance overview...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-destructive/10 text-destructive p-4 rounded-lg">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold text-foreground">Compliance Dashboard</h1>
        <p className="text-muted-foreground mt-1">
          Monitor audit trail integrity and compliance posture
        </p>
      </div>

      {/* Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Hash Chain Status */}
        <div className="bg-card border border-border rounded-lg p-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-muted-foreground">Hash Chain Integrity</h3>
            {verification?.valid ? (
              <span className="flex items-center gap-1 text-green-500">
                <CheckIcon className="w-5 h-5" />
                Valid
              </span>
            ) : (
              <span className="flex items-center gap-1 text-red-500">
                <XIcon className="w-5 h-5" />
                Invalid
              </span>
            )}
          </div>
          <div className="mt-2">
            <span className="text-2xl font-bold text-foreground">
              {verification?.total_records ?? 0}
            </span>
            <span className="text-sm text-muted-foreground ml-2">records</span>
          </div>
          <Link
            to="/compliance/verification"
            className="mt-3 text-sm text-primary hover:underline block"
          >
            View verification details →
          </Link>
        </div>

        {/* Decision Records */}
        <div className="bg-card border border-border rounded-lg p-4">
          <h3 className="text-sm font-medium text-muted-foreground">Decision Records</h3>
          <div className="mt-2">
            <span className="text-2xl font-bold text-foreground">
              {verification?.total_records ?? 0}
            </span>
            <span className="text-sm text-muted-foreground ml-2">total logged</span>
          </div>
          <Link
            to="/compliance/ledger"
            className="mt-3 text-sm text-primary hover:underline block"
          >
            Browse ledger →
          </Link>
        </div>

        {/* Version Bundles */}
        <div className="bg-card border border-border rounded-lg p-4">
          <h3 className="text-sm font-medium text-muted-foreground">Version Bundles</h3>
          <div className="mt-2">
            <span className="text-2xl font-bold text-foreground">{bundles.length}</span>
            <span className="text-sm text-muted-foreground ml-2">snapshots</span>
          </div>
          <Link
            to="/compliance/version-bundles"
            className="mt-3 text-sm text-primary hover:underline block"
          >
            View bundles →
          </Link>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Decisions */}
        <div className="bg-card border border-border rounded-lg">
          <div className="p-4 border-b border-border flex items-center justify-between">
            <h3 className="font-medium text-foreground">Recent Decisions</h3>
            <Link to="/compliance/ledger" className="text-sm text-primary hover:underline">
              View all
            </Link>
          </div>
          <div className="divide-y divide-border">
            {recentDecisions.length === 0 ? (
              <div className="p-4 text-muted-foreground text-sm">No decisions recorded yet</div>
            ) : (
              recentDecisions.map((decision) => (
                <div key={decision.decision_id} className="p-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-foreground capitalize">
                      {decision.decision_type.replace("_", " ")}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {formatTimestamp(decision.timestamp)}
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {decision.doc_id && <span>Doc: {decision.doc_id.slice(0, 12)}...</span>}
                    {decision.claim_id && <span className="ml-2">Claim: {decision.claim_id}</span>}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Quick Links */}
        <div className="bg-card border border-border rounded-lg">
          <div className="p-4 border-b border-border">
            <h3 className="font-medium text-foreground">Compliance Controls</h3>
          </div>
          <div className="p-4 space-y-3">
            <Link
              to="/compliance/verification"
              className="flex items-center gap-3 p-3 rounded-lg hover:bg-accent/50 transition-colors"
            >
              <div className="w-10 h-10 rounded-lg bg-green-500/10 flex items-center justify-center">
                <ShieldIcon className="w-5 h-5 text-green-500" />
              </div>
              <div>
                <div className="font-medium text-foreground">Verification Center</div>
                <div className="text-sm text-muted-foreground">Verify hash chain integrity</div>
              </div>
            </Link>
            <Link
              to="/compliance/version-bundles"
              className="flex items-center gap-3 p-3 rounded-lg hover:bg-accent/50 transition-colors"
            >
              <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
                <GitIcon className="w-5 h-5 text-blue-500" />
              </div>
              <div>
                <div className="font-medium text-foreground">Version Bundles</div>
                <div className="text-sm text-muted-foreground">Track model/prompt versions</div>
              </div>
            </Link>
            <Link
              to="/compliance/controls"
              className="flex items-center gap-3 p-3 rounded-lg hover:bg-accent/50 transition-colors"
            >
              <div className="w-10 h-10 rounded-lg bg-purple-500/10 flex items-center justify-center">
                <ClipboardIcon className="w-5 h-5 text-purple-500" />
              </div>
              <div>
                <div className="font-medium text-foreground">Control Mapping</div>
                <div className="text-sm text-muted-foreground">Framework compliance status</div>
              </div>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

function formatTimestamp(ts: string): string {
  const date = new Date(ts);
  return date.toLocaleString();
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
    </svg>
  );
}

function XIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
}

function ShieldIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
      />
    </svg>
  );
}

function GitIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M13 10V3L4 14h7v7l9-11h-7z"
      />
    </svg>
  );
}

function ClipboardIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"
      />
    </svg>
  );
}

export default ComplianceOverview;
