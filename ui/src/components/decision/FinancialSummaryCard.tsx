import { useMemo } from "react";
import { cn } from "../../lib/utils";
import type { FinancialSummary } from "../../types";

interface FinancialSummaryCardProps {
  summary: FinancialSummary | null;
}

function formatCurrency(amount: number, currency?: string): string {
  try {
    return amount.toLocaleString(undefined, {
      style: "currency",
      currency: currency || "EUR",
      minimumFractionDigits: 2,
    });
  } catch {
    // Fallback if currency code is invalid
    return `${currency || "EUR"} ${amount.toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  }
}

export function FinancialSummaryCard({ summary }: FinancialSummaryCardProps) {
  if (!summary) {
    return (
      <div className="py-8 text-center text-sm text-muted-foreground">
        No financial summary available.
      </div>
    );
  }

  const currency = summary.currency;

  // Calculate percentages for the breakdown bar
  const categoryTotals = useMemo(() => {
    const total =
      summary.parts_total +
      summary.labor_total +
      summary.fees_total +
      summary.other_total;
    if (total === 0) return [];
    return [
      {
        label: "Parts",
        amount: summary.parts_total,
        pct: (summary.parts_total / total) * 100,
        color: "bg-blue-500",
      },
      {
        label: "Labor",
        amount: summary.labor_total,
        pct: (summary.labor_total / total) * 100,
        color: "bg-emerald-500",
      },
      {
        label: "Fees",
        amount: summary.fees_total,
        pct: (summary.fees_total / total) * 100,
        color: "bg-amber-500",
      },
      {
        label: "Other",
        amount: summary.other_total,
        pct: (summary.other_total / total) * 100,
        color: "bg-purple-500",
      },
    ].filter((c) => c.amount > 0);
  }, [summary]);

  return (
    <div className="space-y-4">
      {/* Flow: Claimed -> Covered -> Denied -> Adjusted -> Net Payout */}
      <div className="bg-card border border-border rounded-lg shadow-sm p-4">
        <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-3">
          Financial Summary
        </h4>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <SummaryCell
            label="Total Claimed"
            value={formatCurrency(summary.total_claimed, currency)}
            variant="neutral"
          />
          <SummaryCell
            label="Total Covered"
            value={formatCurrency(summary.total_covered, currency)}
            variant="success"
          />
          <SummaryCell
            label="Total Denied"
            value={formatCurrency(summary.total_denied, currency)}
            variant="error"
          />
          <SummaryCell
            label="Total Adjusted"
            value={formatCurrency(summary.total_adjusted, currency)}
            variant="warning"
          />
          <SummaryCell
            label="Net Payout"
            value={formatCurrency(summary.net_payout, currency)}
            variant="primary"
            highlight
          />
        </div>

        {/* Arrow flow */}
        <div className="hidden md:flex items-center justify-between px-8 mt-2">
          {["", "", "", ""].map((_, i) => (
            <svg
              key={i}
              className="w-5 h-5 text-muted-foreground/30"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M14 5l7 7m0 0l-7 7m7-7H3"
              />
            </svg>
          ))}
        </div>
      </div>

      {/* Category breakdown bar */}
      {categoryTotals.length > 0 && (
        <div className="bg-card border border-border rounded-lg shadow-sm p-4">
          <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-3">
            Breakdown by Category
          </h4>

          {/* Stacked bar */}
          <div className="h-6 flex rounded-lg overflow-hidden border border-border">
            {categoryTotals.map((cat) => (
              <div
                key={cat.label}
                className={cn("h-full transition-all", cat.color)}
                style={{ width: `${cat.pct}%` }}
                title={`${cat.label}: ${formatCurrency(cat.amount, currency)} (${cat.pct.toFixed(1)}%)`}
              />
            ))}
          </div>

          {/* Legend */}
          <div className="flex flex-wrap gap-4 mt-3">
            {categoryTotals.map((cat) => (
              <div key={cat.label} className="flex items-center gap-2">
                <div className={cn("w-3 h-3 rounded-sm", cat.color)} />
                <span className="text-xs text-muted-foreground">
                  {cat.label}
                </span>
                <span className="text-xs font-medium text-foreground">
                  {formatCurrency(cat.amount, currency)}
                </span>
                <span className="text-xs text-muted-foreground/70">
                  ({cat.pct.toFixed(1)}%)
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function SummaryCell({
  label,
  value,
  variant,
  highlight,
}: {
  label: string;
  value: string;
  variant: "neutral" | "success" | "error" | "warning" | "primary";
  highlight?: boolean;
}) {
  const colorMap = {
    neutral: "text-foreground",
    success: "text-success",
    error: "text-destructive",
    warning: "text-warning-foreground",
    primary: "text-primary",
  };

  return (
    <div
      className={cn(
        "text-center",
        highlight && "bg-primary/5 rounded-lg p-2 border border-primary/20"
      )}
    >
      <div className={cn("text-lg font-bold", colorMap[variant])}>{value}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </div>
  );
}
