import { useState, useMemo } from "react";
import { cn } from "../../lib/utils";
import { StatusBadge } from "../shared";
import type { LineItemDecision, LineItemVerdictType } from "../../types";

interface LineItemDecisionsTableProps {
  items: LineItemDecision[];
}

type SortField = "description" | "item_type" | "claimed_amount";
type SortDir = "asc" | "desc";

const verdictConfig: Record<
  LineItemVerdictType,
  { variant: "success" | "error" | "warning"; bg: string }
> = {
  COVERED: { variant: "success", bg: "bg-success/5" },
  DENIED: { variant: "error", bg: "bg-destructive/5" },
  PARTIAL: { variant: "warning", bg: "bg-warning/5" },
  REFER: { variant: "warning", bg: "bg-warning/5" },
};

function formatCurrency(amount: number): string {
  return amount.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function LineItemDecisionsTable({ items }: LineItemDecisionsTableProps) {
  const [sortField, setSortField] = useState<SortField>("description");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const sorted = useMemo(() => {
    const copy = [...items];
    copy.sort((a, b) => {
      let cmp = 0;
      switch (sortField) {
        case "description":
          cmp = a.description.localeCompare(b.description);
          break;
        case "item_type":
          cmp = a.item_type.localeCompare(b.item_type);
          break;
        case "claimed_amount":
          cmp = a.claimed_amount - b.claimed_amount;
          break;
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return copy;
  }, [items, sortField, sortDir]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortDir("asc");
    }
  };

  const SortIndicator = ({ field }: { field: SortField }) => {
    if (sortField !== field) return null;
    return (
      <span className="ml-1 text-muted-foreground">
        {sortDir === "asc" ? "\u2191" : "\u2193"}
      </span>
    );
  };

  if (items.length === 0) {
    return (
      <div className="py-8 text-center text-sm text-muted-foreground">
        No line item decisions available.
      </div>
    );
  }

  return (
    <div className="bg-card border border-border rounded-lg shadow-sm overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/50">
              <th
                className="text-left px-3 py-2 text-xs font-medium text-muted-foreground cursor-pointer hover:text-foreground"
                onClick={() => handleSort("description")}
              >
                Description
                <SortIndicator field="description" />
              </th>
              <th
                className="text-left px-3 py-2 text-xs font-medium text-muted-foreground cursor-pointer hover:text-foreground"
                onClick={() => handleSort("item_type")}
              >
                Type
                <SortIndicator field="item_type" />
              </th>
              <th
                className="text-right px-3 py-2 text-xs font-medium text-muted-foreground cursor-pointer hover:text-foreground"
                onClick={() => handleSort("claimed_amount")}
              >
                Claimed
                <SortIndicator field="claimed_amount" />
              </th>
              <th className="text-right px-3 py-2 text-xs font-medium text-muted-foreground">
                Approved
              </th>
              <th className="text-right px-3 py-2 text-xs font-medium text-muted-foreground">
                Denied
              </th>
              <th className="text-right px-3 py-2 text-xs font-medium text-muted-foreground">
                Adjusted
              </th>
              <th className="text-center px-3 py-2 text-xs font-medium text-muted-foreground">
                Verdict
              </th>
              <th className="text-left px-3 py-2 text-xs font-medium text-muted-foreground">
                Clause Refs
              </th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((item) => {
              const config = verdictConfig[item.verdict];
              return (
                <tr
                  key={item.item_id}
                  className={cn(
                    "border-b border-border transition-colors",
                    config.bg
                  )}
                >
                  <td className="px-3 py-2 text-foreground max-w-[240px] truncate">
                    {item.description}
                  </td>
                  <td className="px-3 py-2 text-muted-foreground">
                    {item.item_type}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-foreground">
                    {formatCurrency(item.claimed_amount)}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-success">
                    {formatCurrency(item.approved_amount)}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-destructive">
                    {formatCurrency(item.denied_amount)}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-muted-foreground">
                    {item.adjusted_amount !== 0
                      ? formatCurrency(item.adjusted_amount)
                      : "-"}
                  </td>
                  <td className="px-3 py-2 text-center">
                    <StatusBadge variant={config.variant} size="sm">
                      {item.verdict}
                    </StatusBadge>
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap gap-1">
                      {item.applicable_clauses.map((ref) => (
                        <span
                          key={ref}
                          className="text-[10px] font-mono px-1 py-0.5 bg-muted rounded text-muted-foreground"
                        >
                          {ref}
                        </span>
                      ))}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
