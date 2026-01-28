import { DollarSign } from "lucide-react";
import { cn } from "../../lib/utils";
import type { PayoutBreakdown } from "../../types";

interface PayoutBreakdownCardProps {
  breakdown: PayoutBreakdown;
}

/**
 * Format a number as currency with Swiss locale
 */
function formatCurrency(value: number | null, currency: string | null): string {
  if (value === null || value === undefined) return "-";
  const curr = currency || "CHF";
  return new Intl.NumberFormat("de-CH", {
    style: "currency",
    currency: curr,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

/**
 * PayoutBreakdownCard shows step-by-step payout calculation.
 *
 * Layout:
 * Total Claimed        CHF 7,315.95
 * - Non-covered         CHF    0.00
 * ─────────────────────────────────
 * Covered Subtotal     CHF 5,642.52
 * × Coverage (40%)
 * ─────────────────────────────────
 * After Coverage       CHF 5,000.00
 * - Deductible          CHF   500.00
 * ═════════════════════════════════
 * Final Payout         CHF 4,500.00
 */
export function PayoutBreakdownCard({ breakdown }: PayoutBreakdownCardProps) {
  const currency = breakdown.currency || "CHF";
  const finalPayout = breakdown.final_payout ?? 0;

  // For rejected claims (final_payout = 0), show collapsed version
  if (finalPayout === 0) {
    return (
      <div className="bg-card rounded-lg border border-border p-4">
        <div className="flex items-center gap-2 mb-3">
          <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center">
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </div>
          <h3 className="font-semibold text-foreground">
            Payout Calculation
          </h3>
        </div>
        <div className="flex items-center justify-between py-2 px-3 bg-muted/50 rounded-lg">
          <span className="text-sm text-muted-foreground">Final Payout</span>
          <span className="text-lg font-bold text-foreground">
            {formatCurrency(0, currency)}
          </span>
        </div>
        {breakdown.total_claimed !== null && breakdown.total_claimed > 0 && (
          <p className="text-xs text-muted-foreground mt-3">
            Claimed amount of {formatCurrency(breakdown.total_claimed, currency)} was not covered
          </p>
        )}
      </div>
    );
  }

  // Full breakdown view
  const rows: { label: string; value: string; isDeduction?: boolean; isBold?: boolean; isSubtotal?: boolean }[] = [];

  // Total claimed
  if (breakdown.total_claimed !== null) {
    rows.push({ label: "Total Claimed", value: formatCurrency(breakdown.total_claimed, currency) });
  }

  // Non-covered deductions
  if (breakdown.non_covered_deductions !== null && breakdown.non_covered_deductions !== 0) {
    rows.push({
      label: "- Non-covered Items",
      value: formatCurrency(breakdown.non_covered_deductions, currency),
      isDeduction: true,
    });
  }

  // Add divider before covered subtotal
  const hasCoveredSubtotal = breakdown.covered_subtotal !== null;

  // Covered subtotal
  if (hasCoveredSubtotal) {
    rows.push({
      label: "Covered Subtotal",
      value: formatCurrency(breakdown.covered_subtotal, currency),
      isSubtotal: true,
    });
  }

  // Coverage percent
  if (breakdown.coverage_percent !== null) {
    rows.push({
      label: `x Coverage (${breakdown.coverage_percent}%)`,
      value: "",
    });
  }

  // After coverage
  if (breakdown.after_coverage !== null) {
    rows.push({
      label: "After Coverage",
      value: formatCurrency(breakdown.after_coverage, currency),
      isSubtotal: true,
    });
  }

  // Deductible
  if (breakdown.deductible !== null && breakdown.deductible !== 0) {
    rows.push({
      label: "- Deductible",
      value: formatCurrency(breakdown.deductible, currency),
      isDeduction: true,
    });
  }

  // Final payout (always shown)
  rows.push({
    label: "Final Payout",
    value: formatCurrency(breakdown.final_payout, currency),
    isBold: true,
  });

  return (
    <div className="bg-card rounded-lg border border-border p-4">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
          <DollarSign className="h-4 w-4 text-primary" />
        </div>
        <h3 className="font-semibold text-foreground">
          Payout Calculation
        </h3>
      </div>

      <div className="space-y-0 font-mono text-sm bg-muted/30 rounded-lg p-3">
        {rows.map((row, idx) => {
          const isLast = idx === rows.length - 1;
          const showDividerBefore = row.isSubtotal && idx > 0;
          const showDoubleDividerBefore = row.isBold && idx > 0;

          return (
            <div key={idx}>
              {showDividerBefore && !showDoubleDividerBefore && (
                <div className="border-t border-border my-2" />
              )}
              {showDoubleDividerBefore && (
                <div className="border-t-2 border-primary/30 my-2" />
              )}
              <div
                className={cn(
                  "flex items-center justify-between py-1",
                  row.isDeduction && "text-destructive",
                  row.isBold && "text-success font-bold text-base",
                  isLast && "pt-2"
                )}
              >
                <span className={cn(row.isBold ? "font-bold" : "text-muted-foreground")}>
                  {row.label}
                </span>
                <span className={cn(row.isBold ? "font-bold" : "text-foreground")}>
                  {row.value}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
