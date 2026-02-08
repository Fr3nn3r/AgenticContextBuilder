import { useState, useMemo, Fragment } from "react";
import { cn } from "../../lib/utils";
import { StatusBadge } from "../shared";
import type { ClauseEvaluation } from "../../types";

interface ClauseEvaluationTableProps {
  evaluations: ClauseEvaluation[];
  onFilter?: (category: string) => void;
}

export function ClauseEvaluationTable({
  evaluations,
  onFilter,
}: ClauseEvaluationTableProps) {
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [verdictFilter, setVerdictFilter] = useState<string>("all");
  const [expandedRef, setExpandedRef] = useState<string | null>(null);

  // Unique categories
  const categories = useMemo(() => {
    const cats = new Set(evaluations.map((e) => e.category));
    return ["all", ...Array.from(cats).sort()];
  }, [evaluations]);

  // Unique verdicts
  const verdicts = useMemo(() => {
    const vds = new Set(evaluations.map((e) => e.verdict));
    return ["all", ...Array.from(vds).sort()];
  }, [evaluations]);

  // Filtered evaluations
  const filtered = useMemo(() => {
    return evaluations.filter((e) => {
      if (categoryFilter !== "all" && e.category !== categoryFilter)
        return false;
      if (verdictFilter !== "all" && e.verdict !== verdictFilter) return false;
      return true;
    });
  }, [evaluations, categoryFilter, verdictFilter]);

  const handleCategoryChange = (cat: string) => {
    setCategoryFilter(cat);
    if (onFilter && cat !== "all") {
      onFilter(cat);
    }
  };

  const toggleExpand = (ref: string) => {
    setExpandedRef(expandedRef === ref ? null : ref);
  };

  return (
    <div className="space-y-3">
      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <label className="text-xs text-muted-foreground">Category:</label>
          <select
            value={categoryFilter}
            onChange={(e) => handleCategoryChange(e.target.value)}
            className="text-sm border border-border rounded-md px-2 py-1 bg-background text-foreground"
          >
            {categories.map((cat) => (
              <option key={cat} value={cat}>
                {cat === "all" ? "All Categories" : cat}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs text-muted-foreground">Verdict:</label>
          <select
            value={verdictFilter}
            onChange={(e) => setVerdictFilter(e.target.value)}
            className="text-sm border border-border rounded-md px-2 py-1 bg-background text-foreground"
          >
            {verdicts.map((v) => (
              <option key={v} value={v}>
                {v === "all" ? "All Verdicts" : v}
              </option>
            ))}
          </select>
        </div>
        <span className="text-xs text-muted-foreground">
          {filtered.length} of {evaluations.length} clauses
        </span>
      </div>

      {/* Table */}
      <div className="bg-card border border-border rounded-lg shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/50">
              <th className="text-left px-3 py-2 text-xs font-medium text-muted-foreground">
                Reference
              </th>
              <th className="text-left px-3 py-2 text-xs font-medium text-muted-foreground">
                Name
              </th>
              <th className="text-left px-3 py-2 text-xs font-medium text-muted-foreground">
                Category
              </th>
              <th className="text-center px-3 py-2 text-xs font-medium text-muted-foreground">
                Tier
              </th>
              <th className="text-center px-3 py-2 text-xs font-medium text-muted-foreground">
                Verdict
              </th>
              <th className="text-center px-3 py-2 text-xs font-medium text-muted-foreground">
                Assumed
              </th>
              <th className="text-center px-3 py-2 text-xs font-medium text-muted-foreground">
                Evidence
              </th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((ev) => {
              const isPass = ev.verdict === "PASS";
              const isFail = ev.verdict === "FAIL";
              const isExpanded = expandedRef === ev.clause_reference;

              return (
                <Fragment key={ev.clause_reference}>
                  <tr
                    onClick={() => toggleExpand(ev.clause_reference)}
                    className={cn(
                      "border-b border-border cursor-pointer hover:bg-muted/30 transition-colors",
                      isPass && "bg-success/5",
                      isFail && "bg-destructive/5"
                    )}
                  >
                    <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
                      {ev.clause_reference}
                    </td>
                    <td className="px-3 py-2 text-foreground">
                      <div className="flex items-center gap-1">
                        <svg
                          className={cn(
                            "w-3 h-3 transition-transform text-muted-foreground flex-shrink-0",
                            isExpanded && "rotate-90"
                          )}
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M9 5l7 7-7 7"
                          />
                        </svg>
                        <span className="truncate">
                          {ev.clause_short_name}
                        </span>
                      </div>
                    </td>
                    <td className="px-3 py-2 text-muted-foreground">
                      {ev.category}
                    </td>
                    <td className="px-3 py-2 text-center">
                      <StatusBadge
                        variant={
                          ev.evaluability_tier === 1
                            ? "success"
                            : ev.evaluability_tier === 2
                            ? "info"
                            : "warning"
                        }
                        size="sm"
                      >
                        T{ev.evaluability_tier}
                      </StatusBadge>
                    </td>
                    <td className="px-3 py-2 text-center">
                      <StatusBadge
                        variant={isPass ? "success" : isFail ? "error" : "neutral"}
                        size="sm"
                      >
                        {ev.verdict}
                      </StatusBadge>
                    </td>
                    <td className="px-3 py-2 text-center">
                      {ev.assumption_used ? (
                        <span title="Assumption used">
                          <svg
                            className="w-4 h-4 text-warning-foreground inline-block"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                            />
                          </svg>
                        </span>
                      ) : (
                        <span className="text-muted-foreground/30">-</span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-center text-muted-foreground">
                      {ev.evidence.length}
                    </td>
                  </tr>
                  {/* Expanded details */}
                  {isExpanded && (
                    <tr>
                      <td
                        colSpan={7}
                        className="px-6 py-3 bg-muted/20 border-b border-border"
                      >
                        {/* Reason */}
                        <div className="mb-3">
                          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                            Reason
                          </span>
                          <p className="text-sm text-foreground mt-1">
                            {ev.reason || "No reason provided."}
                          </p>
                        </div>

                        {/* Evidence */}
                        {ev.evidence.length > 0 && (
                          <div className="mb-3">
                            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                              Evidence ({ev.evidence.length})
                            </span>
                            <div className="mt-1 space-y-1.5">
                              {ev.evidence.map((e, idx) => (
                                <div
                                  key={idx}
                                  className="text-xs border border-border rounded px-2 py-1.5 bg-background"
                                >
                                  <span className="font-medium text-foreground">
                                    {e.fact_name}
                                  </span>
                                  {e.fact_value && (
                                    <span className="text-muted-foreground">
                                      {" "}
                                      = {e.fact_value}
                                    </span>
                                  )}
                                  {e.description && (
                                    <p className="text-muted-foreground mt-0.5">
                                      {e.description}
                                    </p>
                                  )}
                                  {e.source_doc_id && (
                                    <span className="text-muted-foreground/70 ml-2">
                                      [doc: {e.source_doc_id}]
                                    </span>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Affected line items */}
                        {ev.affected_line_items.length > 0 && (
                          <div>
                            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                              Affected Line Items
                            </span>
                            <div className="mt-1 flex flex-wrap gap-1">
                              {ev.affected_line_items.map((item) => (
                                <StatusBadge
                                  key={item}
                                  variant="neutral"
                                  size="sm"
                                >
                                  {item}
                                </StatusBadge>
                              ))}
                            </div>
                          </div>
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>

        {filtered.length === 0 && (
          <div className="py-8 text-center text-sm text-muted-foreground">
            No clause evaluations match the current filters.
          </div>
        )}
      </div>
    </div>
  );
}
