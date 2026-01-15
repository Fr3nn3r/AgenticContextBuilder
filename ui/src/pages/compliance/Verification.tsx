import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { verifyDecisionLedger } from "../../api/client";
import type { VerificationResult } from "../../types";

export function ComplianceVerification() {
  const [result, setResult] = useState<VerificationResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [, setError] = useState<string | null>(null);

  useEffect(() => {
    runVerification();
  }, []);

  async function runVerification() {
    try {
      setLoading(true);
      setError(null);
      const data = await verifyDecisionLedger();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Verification failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Verification Center</h1>
          <p className="text-muted-foreground mt-1">
            Verify the integrity of the audit trail hash chain
          </p>
        </div>
        <Link
          to="/compliance"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← Back to Overview
        </Link>
      </div>

      {/* Main verification card */}
      <div className="bg-card border border-border rounded-lg overflow-hidden">
        {/* Status header */}
        <div
          className={`p-6 ${
            loading
              ? "bg-muted/50"
              : result?.valid
              ? "bg-green-500/10"
              : "bg-red-500/10"
          }`}
        >
          <div className="flex items-center gap-4">
            {loading ? (
              <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center">
                <div className="w-8 h-8 border-2 border-muted-foreground border-t-transparent rounded-full animate-spin" />
              </div>
            ) : result?.valid ? (
              <div className="w-16 h-16 rounded-full bg-green-500/20 flex items-center justify-center">
                <CheckIcon className="w-8 h-8 text-green-500" />
              </div>
            ) : (
              <div className="w-16 h-16 rounded-full bg-red-500/20 flex items-center justify-center">
                <XIcon className="w-8 h-8 text-red-500" />
              </div>
            )}
            <div>
              <h2 className="text-xl font-semibold text-foreground">
                {loading
                  ? "Verifying..."
                  : result?.valid
                  ? "Hash Chain Valid"
                  : "Hash Chain Invalid"}
              </h2>
              {!loading && (
                <p className="text-muted-foreground">
                  {result?.valid
                    ? "All decision records are intact and have not been tampered with."
                    : result?.error_details || "The hash chain has been compromised."}
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Details */}
        <div className="p-6 border-t border-border">
          <h3 className="text-sm font-medium text-muted-foreground mb-4">
            Verification Details
          </h3>
          <dl className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-muted/30 rounded-lg p-4">
              <dt className="text-sm text-muted-foreground">Total Records</dt>
              <dd className="text-2xl font-bold text-foreground mt-1">
                {loading ? "—" : result?.total_records ?? 0}
              </dd>
            </div>
            <div className="bg-muted/30 rounded-lg p-4">
              <dt className="text-sm text-muted-foreground">Last Verified</dt>
              <dd className="text-lg font-medium text-foreground mt-1">
                {result?.verified_at ? new Date(result.verified_at).toLocaleString() : "Never"}
              </dd>
            </div>
            {!result?.valid && result?.break_at_index != null && (
              <div className="bg-red-500/10 rounded-lg p-4 md:col-span-2">
                <dt className="text-sm text-red-500">Chain Break Location</dt>
                <dd className="text-lg font-medium text-foreground mt-1">
                  Record #{result.break_at_index}
                  {result.break_at_decision_id && ` (${result.break_at_decision_id})`}
                </dd>
                {result.error_details && (
                  <dd className="text-sm text-muted-foreground mt-2">
                    {result.error_type}: {result.error_details}
                  </dd>
                )}
              </div>
            )}
          </dl>
        </div>

        {/* Actions */}
        <div className="p-6 border-t border-border bg-muted/30">
          <button
            onClick={runVerification}
            disabled={loading}
            className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "Verifying..." : "Re-run Verification"}
          </button>
        </div>
      </div>

      {/* Explanation */}
      <div className="bg-card border border-border rounded-lg p-6">
        <h3 className="font-medium text-foreground mb-4">How Hash Chain Verification Works</h3>
        <div className="space-y-4 text-sm text-muted-foreground">
          <p>
            Every decision record in the compliance ledger contains a cryptographic hash of
            the previous record. This creates an immutable chain where any modification to
            a past record would break the chain.
          </p>
          <div className="bg-muted/30 rounded-lg p-4 font-mono text-xs">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-3 h-3 rounded bg-blue-500" />
              <span>Record N-1</span>
              <span className="text-muted-foreground">(hash: abc123...)</span>
            </div>
            <div className="ml-1.5 w-0.5 h-4 bg-border" />
            <div className="flex items-center gap-2 mb-2">
              <div className="w-3 h-3 rounded bg-blue-500" />
              <span>Record N</span>
              <span className="text-muted-foreground">(prev_hash: abc123...)</span>
            </div>
            <div className="ml-1.5 w-0.5 h-4 bg-border" />
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded bg-blue-500" />
              <span>Record N+1</span>
              <span className="text-muted-foreground">(prev_hash: def456...)</span>
            </div>
          </div>
          <p>
            The verification process walks through all records and confirms that each
            record's <code className="bg-muted px-1 py-0.5 rounded">prev_hash</code> matches
            the computed hash of the previous record.
          </p>
        </div>
      </div>

      {/* Security note */}
      <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-4">
        <div className="flex gap-3">
          <ShieldIcon className="w-5 h-5 text-blue-500 flex-shrink-0 mt-0.5" />
          <div>
            <h4 className="font-medium text-foreground">Security Note</h4>
            <p className="text-sm text-muted-foreground mt-1">
              All audit records are encrypted at rest with AES-256-GCM when encryption is
              enabled. Only users with the <code className="bg-muted px-1 py-0.5 rounded">admin</code> or{" "}
              <code className="bg-muted px-1 py-0.5 rounded">auditor</code> role can access
              compliance data.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
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

export default ComplianceVerification;
