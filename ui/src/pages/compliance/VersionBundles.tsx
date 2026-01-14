import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { listVersionBundles, getVersionBundle } from "../../api/client";
import type { VersionBundleSummary, VersionBundle } from "../../types";

export function ComplianceVersionBundles() {
  const [bundles, setBundles] = useState<VersionBundleSummary[]>([]);
  const [selectedBundle, setSelectedBundle] = useState<VersionBundle | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadBundles();
  }, []);

  async function loadBundles() {
    try {
      setLoading(true);
      setError(null);
      const data = await listVersionBundles();
      setBundles(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load version bundles");
    } finally {
      setLoading(false);
    }
  }

  async function loadBundleDetail(runId: string) {
    try {
      setDetailLoading(true);
      const data = await getVersionBundle(runId);
      setSelectedBundle(data);
    } catch (err) {
      console.error("Failed to load bundle detail:", err);
    } finally {
      setDetailLoading(false);
    }
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Version Bundles</h1>
          <p className="text-muted-foreground mt-1">
            Track exact versions of models, prompts, and extraction specs for each pipeline run
          </p>
        </div>
        <Link
          to="/compliance"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← Back to Overview
        </Link>
      </div>

      {error ? (
        <div className="bg-destructive/10 text-destructive p-4 rounded-lg">{error}</div>
      ) : loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="text-muted-foreground">Loading version bundles...</div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Bundle list */}
          <div className="bg-card border border-border rounded-lg overflow-hidden">
            <div className="p-4 border-b border-border">
              <h3 className="font-medium text-foreground">Pipeline Runs</h3>
              <p className="text-sm text-muted-foreground mt-1">
                {bundles.length} version snapshots captured
              </p>
            </div>
            <div className="divide-y divide-border max-h-[600px] overflow-y-auto">
              {bundles.length === 0 ? (
                <div className="p-4 text-muted-foreground text-sm">
                  No version bundles recorded yet
                </div>
              ) : (
                bundles.map((bundle) => (
                  <button
                    key={bundle.run_id}
                    onClick={() => loadBundleDetail(bundle.run_id)}
                    className={`w-full p-4 text-left hover:bg-muted/30 transition-colors ${
                      selectedBundle?.run_id === bundle.run_id ? "bg-muted/50" : ""
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-sm text-foreground">
                        {bundle.run_id}
                      </span>
                      {bundle.git_dirty && (
                        <span className="text-xs px-2 py-0.5 rounded bg-yellow-500/10 text-yellow-500">
                          dirty
                        </span>
                      )}
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">
                      {bundle.model_name} • {bundle.extractor_version}
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">
                      {bundle.created_at ? formatTimestamp(bundle.created_at) : "Unknown date"}
                    </div>
                  </button>
                ))
              )}
            </div>
          </div>

          {/* Bundle detail */}
          <div className="bg-card border border-border rounded-lg overflow-hidden">
            <div className="p-4 border-b border-border">
              <h3 className="font-medium text-foreground">Bundle Details</h3>
            </div>
            {detailLoading ? (
              <div className="p-8 text-center text-muted-foreground">Loading...</div>
            ) : selectedBundle ? (
              <div className="p-4 space-y-4">
                <DetailRow label="Bundle ID" value={selectedBundle.bundle_id} mono />
                <DetailRow label="Run ID" value={selectedBundle.run_id} mono />
                <DetailRow
                  label="Created"
                  value={
                    selectedBundle.created_at
                      ? formatTimestamp(selectedBundle.created_at)
                      : "Unknown"
                  }
                />

                <div className="border-t border-border pt-4">
                  <h4 className="text-sm font-medium text-muted-foreground mb-3">
                    Git Information
                  </h4>
                  <DetailRow
                    label="Commit"
                    value={selectedBundle.git_commit || "Not captured"}
                    mono
                  />
                  <DetailRow
                    label="Working Tree"
                    value={
                      selectedBundle.git_dirty == null
                        ? "Unknown"
                        : selectedBundle.git_dirty
                        ? "Dirty (uncommitted changes)"
                        : "Clean"
                    }
                    highlight={selectedBundle.git_dirty ? "yellow" : "green"}
                  />
                </div>

                <div className="border-t border-border pt-4">
                  <h4 className="text-sm font-medium text-muted-foreground mb-3">
                    Model Configuration
                  </h4>
                  <DetailRow label="Model" value={selectedBundle.model_name} />
                  <DetailRow
                    label="Model Version"
                    value={selectedBundle.model_version || "Not specified"}
                  />
                  <DetailRow label="Extractor" value={selectedBundle.extractor_version} />
                  <DetailRow
                    label="ContextBuilder"
                    value={selectedBundle.contextbuilder_version}
                  />
                </div>

                <div className="border-t border-border pt-4">
                  <h4 className="text-sm font-medium text-muted-foreground mb-3">
                    Content Hashes
                  </h4>
                  <DetailRow
                    label="Prompt Template Hash"
                    value={selectedBundle.prompt_template_hash || "Not computed"}
                    mono
                    highlight={selectedBundle.prompt_template_hash ? "green" : "red"}
                  />
                  <DetailRow
                    label="Extraction Spec Hash"
                    value={selectedBundle.extraction_spec_hash || "Not computed"}
                    mono
                    highlight={selectedBundle.extraction_spec_hash ? "green" : "red"}
                  />
                </div>
              </div>
            ) : (
              <div className="p-8 text-center text-muted-foreground">
                Select a run to view version details
              </div>
            )}
          </div>
        </div>
      )}

      {/* Explanation */}
      <div className="bg-card border border-border rounded-lg p-6">
        <h3 className="font-medium text-foreground mb-4">Why Version Bundles Matter</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 bg-muted/30 rounded-lg">
            <h4 className="font-medium text-foreground mb-2">Reproducibility</h4>
            <p className="text-sm text-muted-foreground">
              Know exactly which model, prompts, and extraction specs produced each result.
              Essential for debugging and auditing.
            </p>
          </div>
          <div className="p-4 bg-muted/30 rounded-lg">
            <h4 className="font-medium text-foreground mb-2">Accountability</h4>
            <p className="text-sm text-muted-foreground">
              Track changes over time. If results differ between runs, you can identify
              exactly what changed.
            </p>
          </div>
          <div className="p-4 bg-muted/30 rounded-lg">
            <h4 className="font-medium text-foreground mb-2">Compliance</h4>
            <p className="text-sm text-muted-foreground">
              Demonstrate to auditors that you have full traceability of AI system
              configurations at decision time.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function DetailRow({
  label,
  value,
  mono,
  highlight,
}: {
  label: string;
  value: string;
  mono?: boolean;
  highlight?: "green" | "yellow" | "red";
}) {
  const highlightClasses = {
    green: "text-green-500",
    yellow: "text-yellow-500",
    red: "text-red-500",
  };

  return (
    <div className="flex justify-between items-start py-2">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span
        className={`text-sm text-right ${mono ? "font-mono" : ""} ${
          highlight ? highlightClasses[highlight] : "text-foreground"
        }`}
      >
        {value}
      </span>
    </div>
  );
}

function formatTimestamp(ts: string): string {
  const date = new Date(ts);
  return date.toLocaleString();
}

export default ComplianceVersionBundles;
