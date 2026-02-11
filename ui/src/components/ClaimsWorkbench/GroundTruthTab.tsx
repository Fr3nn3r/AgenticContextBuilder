import { useState, useEffect } from "react";
import { cn } from "../../lib/utils";
import { FileText, Loader2 } from "lucide-react";
import { getDashboardClaimDetail } from "../../api/client";
import { GroundTruthDocPanel } from "../dashboard/GroundTruthDocPanel";
import type { DashboardClaimDetail } from "../../types";

// =============================================================================
// PAYOUT COMPARISON CARD (lazy-loaded)
// =============================================================================

function PayoutComparisonCard({ claimId }: { claimId: string }) {
  const [detail, setDetail] = useState<DashboardClaimDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getDashboardClaimDetail(claimId)
      .then((d) => {
        if (!cancelled) setDetail(d);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [claimId]);

  const fmt = (v: unknown) =>
    typeof v === "number" ? v.toFixed(2) : v != null ? String(v) : "-";

  const getDiff = (
    sys: unknown,
    gt: unknown,
  ): { text: string; color: string } => {
    if (typeof sys !== "number" || typeof gt !== "number")
      return { text: "", color: "" };
    const diff = sys - gt;
    const abs = Math.abs(diff);
    const color =
      abs <= 1
        ? "text-emerald-600 dark:text-emerald-400"
        : abs <= 10
          ? "text-amber-500 dark:text-amber-400"
          : "text-red-500 dark:text-red-400";
    const sign = diff > 0 ? "+" : "";
    return { text: `${sign}${diff.toFixed(2)}`, color };
  };

  if (loading) {
    return (
      <div className="bg-card border border-border rounded-lg p-4 flex items-center justify-center py-12">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground mr-2" />
        <span className="text-sm text-muted-foreground">Loading payout data...</span>
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="bg-card border border-border rounded-lg p-4 text-sm text-muted-foreground">
        {error || "No payout data available."}
      </div>
    );
  }

  const pc = detail.payout_calculation as Record<string, unknown> | null;

  const coveragePctFmt =
    pc?.coverage_percent != null ? `${pc.coverage_percent}%` : "-";
  const gtCoveragePctFmt =
    detail.gt_reimbursement_rate_pct != null
      ? `${detail.gt_reimbursement_rate_pct}%`
      : "-";

  const rows: Array<{ label: string; system: unknown; gt: unknown; bold?: boolean }> = [
    { label: "Parts", system: detail.sys_parts_adjusted, gt: detail.gt_parts_approved },
    { label: "Labor", system: detail.sys_labor_adjusted, gt: detail.gt_labor_approved },
    { label: "Subtotal", system: detail.sys_total_adjusted, gt: detail.gt_total_material_labor },
    { label: "Coverage %", system: coveragePctFmt, gt: gtCoveragePctFmt },
    {
      label: "VAT %",
      system: detail.sys_vat_rate_pct != null ? `${detail.sys_vat_rate_pct}%` : "-",
      gt: detail.gt_vat_rate_pct != null ? `${detail.gt_vat_rate_pct}%` : "-",
    },
    { label: "VAT Amount", system: detail.sys_vat_amount, gt: detail.gt_vat_amount },
    { label: "Deductible", system: pc?.deductible, gt: detail.gt_deductible },
    { label: "Final Payout", system: pc?.final_payout, gt: detail.gt_total_approved, bold: true },
  ];

  return (
    <div className="bg-card border border-border rounded-lg p-4 space-y-2">
      <h3 className="text-sm font-medium text-foreground">Payout Comparison</h3>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border">
            <th className="text-left py-1.5 px-2 text-xs font-medium text-muted-foreground">Field</th>
            <th className="text-right py-1.5 px-2 text-xs font-medium text-muted-foreground">System</th>
            <th className="text-right py-1.5 px-2 text-xs font-medium text-muted-foreground">Ground Truth</th>
            <th className="text-right py-1.5 px-2 text-xs font-medium text-muted-foreground">Diff</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const diff = getDiff(r.system, r.gt);
            return (
              <tr
                key={r.label}
                className={cn(
                  "border-b border-border/50",
                  r.bold && "border-t border-border"
                )}
              >
                <td className={cn("py-1.5 px-2 text-foreground", r.bold && "font-semibold")}>
                  {r.label}
                </td>
                <td className={cn("py-1.5 px-2 text-right font-mono text-foreground", r.bold && "font-semibold")}>
                  {fmt(r.system)}
                </td>
                <td className={cn("py-1.5 px-2 text-right font-mono text-foreground", r.bold && "font-semibold")}>
                  {fmt(r.gt)}
                </td>
                <td className={cn("py-1.5 px-2 text-right font-mono", diff.color, r.bold && "font-semibold")}>
                  {diff.text}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// =============================================================================
// GROUND TRUTH TAB
// =============================================================================

interface GroundTruthTabProps {
  claimId: string;
  hasGroundTruthDoc: boolean;
}

export function GroundTruthTab({
  claimId,
  hasGroundTruthDoc,
}: GroundTruthTabProps) {
  const [showDocPanel, setShowDocPanel] = useState(false);

  return (
    <div className="space-y-4">
      <PayoutComparisonCard claimId={claimId} />

      {/* Decision letter button */}
      {hasGroundTruthDoc && (
        <button
          onClick={() => setShowDocPanel(true)}
          className="inline-flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-primary hover:text-primary/80 border border-primary/30 hover:border-primary/50 rounded-md transition-colors"
        >
          <FileText className="h-4 w-4" />
          View Decision Letter
        </button>
      )}

      {/* Slide panel for decision letter PDF */}
      {showDocPanel && (
        <GroundTruthDocPanel
          claimId={claimId}
          onClose={() => setShowDocPanel(false)}
        />
      )}
    </div>
  );
}
