import { useState, useEffect } from "react";
import { getRunSummary } from "../api/client";
import type { RunSummary as RunSummaryType } from "../types";

export function RunSummary() {
  const [summary, setSummary] = useState<RunSummaryType | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const data = await getRunSummary();
        setSummary(data);
      } catch (err) {
        console.error("Failed to load run summary:", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="bg-card rounded-lg border p-6">
        <div className="text-muted-foreground">Loading summary...</div>
      </div>
    );
  }

  if (!summary) {
    return (
      <div className="bg-card rounded-lg border p-6">
        <div className="text-muted-foreground">No summary available</div>
      </div>
    );
  }

  const passRate =
    summary.extracted_count > 0
      ? ((summary.quality_gate.pass || 0) / summary.extracted_count) * 100
      : 0;

  return (
    <div className="bg-card rounded-lg border p-6">
      <h2 className="text-lg font-semibold mb-4">Run Summary</h2>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {/* Total Claims */}
        <div className="bg-secondary/50 rounded-lg p-4">
          <div className="text-2xl font-bold">{summary.total_claims}</div>
          <div className="text-sm text-muted-foreground">Claims</div>
        </div>

        {/* Total Docs */}
        <div className="bg-secondary/50 rounded-lg p-4">
          <div className="text-2xl font-bold">{summary.total_docs}</div>
          <div className="text-sm text-muted-foreground">Documents</div>
        </div>

        {/* Extracted */}
        <div className="bg-secondary/50 rounded-lg p-4">
          <div className="text-2xl font-bold">{summary.extracted_count}</div>
          <div className="text-sm text-muted-foreground">Extracted</div>
        </div>

        {/* Labeled */}
        <div className="bg-secondary/50 rounded-lg p-4">
          <div className="text-2xl font-bold">{summary.labeled_count}</div>
          <div className="text-sm text-muted-foreground">Labeled</div>
        </div>
      </div>

      {/* Quality Gate */}
      <div className="mt-6">
        <h3 className="text-sm font-medium mb-2">Quality Gate Results</h3>
        <div className="flex gap-4">
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-green-500"></span>
            <span className="text-sm">Pass: {summary.quality_gate.pass || 0}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-yellow-500"></span>
            <span className="text-sm">Warn: {summary.quality_gate.warn || 0}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-red-500"></span>
            <span className="text-sm">Fail: {summary.quality_gate.fail || 0}</span>
          </div>
        </div>

        {/* Pass rate bar */}
        <div className="mt-3">
          <div className="flex justify-between text-sm mb-1">
            <span className="text-muted-foreground">Pass Rate</span>
            <span>{passRate.toFixed(0)}%</span>
          </div>
          <div className="h-2 bg-secondary rounded-full overflow-hidden">
            <div
              className="h-full bg-green-500 transition-all"
              style={{ width: `${passRate}%` }}
            ></div>
          </div>
        </div>
      </div>
    </div>
  );
}
