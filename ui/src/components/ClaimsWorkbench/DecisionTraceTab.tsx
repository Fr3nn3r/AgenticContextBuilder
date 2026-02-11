import { useState, useMemo, Fragment } from "react";
import { cn } from "../../lib/utils";
import {
  ChevronRight,
} from "lucide-react";
import { NoDataEmptyState } from "../shared";
import type {
  TraceStep,
  TraceAction,
} from "../../types";

// =============================================================================
// ACTION BADGE COLORS
// =============================================================================

const ACTION_STYLES: Record<string, string> = {
  matched: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300",
  validated: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300",
  promoted: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300",
  excluded: "bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300",
  demoted: "bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300",
  skipped: "bg-gray-100 text-gray-600 dark:bg-gray-800/40 dark:text-gray-400",
  deferred: "bg-gray-100 text-gray-600 dark:bg-gray-800/40 dark:text-gray-400",
  overridden: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
};

function ActionBadge({ action }: { action: TraceAction }) {
  return (
    <span
      className={cn(
        "inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide",
        ACTION_STYLES[action] ?? "bg-gray-100 text-gray-600 dark:bg-gray-800/40 dark:text-gray-400"
      )}
    >
      {action}
    </span>
  );
}

// =============================================================================
// STATUS DOT
// =============================================================================

function StatusDot({ status }: { status: string }) {
  const color =
    status === "covered"
      ? "bg-success"
      : status === "not_covered"
        ? "bg-destructive"
        : "bg-warning";
  return <span className={cn("block h-2 w-2 rounded-full flex-shrink-0", color)} />;
}

// =============================================================================
// MAIN TAB COMPONENT
// =============================================================================

interface DecisionTraceTabProps {
  data: any;
}

export function DecisionTraceTab({ data }: DecisionTraceTabProps) {
  const lineItems: any[] = data.coverage?.line_items ?? [];
  const [expandedTypes, setExpandedTypes] = useState<Set<string>>(new Set());
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set());

  const toggleType = (type: string) =>
    setExpandedTypes((prev) => {
      const next = new Set(prev);
      next.has(type) ? next.delete(type) : next.add(type);
      return next;
    });

  const toggleItem = (key: string) =>
    setExpandedItems((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });

  // Group line items by type
  const typeOrder = ["parts", "labor", "fee", "other"];
  const typeLabel: Record<string, string> = {
    parts: "Parts",
    labor: "Labor",
    fee: "Fees",
    other: "Other",
  };

  const byType = useMemo(() => {
    const groups: Record<string, { items: any[]; traceCount: number }> = {};
    let flatIdx = 0;
    for (const item of lineItems) {
      const type = item.item_type === "fees" ? "fee" : (item.item_type || "other");
      if (!groups[type]) groups[type] = { items: [], traceCount: 0 };
      const key = `item_${flatIdx}`;
      flatIdx++;
      const hasTrace = Array.isArray(item.decision_trace) && item.decision_trace.length > 0;
      if (hasTrace) groups[type].traceCount++;
      groups[type].items.push({ ...item, _key: key, _hasTrace: hasTrace });
    }
    return groups;
  }, [lineItems]);

  const types = typeOrder.filter((t) => byType[t]);
  const totalItems = lineItems.length;
  const totalWithTrace = Object.values(byType).reduce((s, g) => s + g.traceCount, 0);

  if (totalItems === 0) {
    return <NoDataEmptyState />;
  }

  return (
    <div className="space-y-4">
      {/* Line items with trace */}
      {totalItems > 0 && (
        <div className="bg-card border border-border rounded-lg overflow-hidden">
          {/* Header */}
          <div className="px-4 py-2.5 border-b border-border bg-muted/30 flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">
              Decision Traces
            </span>
            <span className="text-[11px] text-muted-foreground tabular-nums">
              {totalWithTrace}/{totalItems} items with trace
            </span>
          </div>

          {types.map((type) => {
            const group = byType[type];
            const isTypeOpen = expandedTypes.has(type);

            return (
              <Fragment key={type}>
                {/* Type group header */}
                <div
                  onClick={() => toggleType(type)}
                  className="flex items-center gap-2 px-4 py-2 border-b border-border bg-muted/10 cursor-pointer select-none hover:bg-muted/20 transition-colors"
                >
                  <ChevronRight
                    className={cn(
                      "h-3.5 w-3.5 text-muted-foreground transition-transform",
                      isTypeOpen && "rotate-90"
                    )}
                  />
                  <span className="text-[13px] font-medium text-foreground">
                    {typeLabel[type] || type}
                  </span>
                  <span className="text-[11px] text-muted-foreground">
                    ({group.items.length} items, {group.traceCount} traced)
                  </span>
                </div>

                {/* Items */}
                {isTypeOpen &&
                  group.items.map((item: any) => {
                    const key = item._key as string;
                    const hasTrace = item._hasTrace as boolean;
                    const trace: TraceStep[] = item.decision_trace ?? [];
                    const isOpen = expandedItems.has(key);
                    const conf = item.match_confidence;

                    return (
                      <Fragment key={key}>
                        {/* Item row */}
                        <div
                          onClick={() => hasTrace && toggleItem(key)}
                          className={cn(
                            "flex items-center gap-3 px-4 py-1.5 border-b border-border text-xs",
                            hasTrace
                              ? "cursor-pointer hover:bg-muted/20 transition-colors"
                              : "opacity-60"
                          )}
                        >
                          {hasTrace ? (
                            <ChevronRight
                              className={cn(
                                "h-3 w-3 text-muted-foreground transition-transform flex-shrink-0",
                                isOpen && "rotate-90"
                              )}
                            />
                          ) : (
                            <span className="w-3 flex-shrink-0" />
                          )}
                          <StatusDot status={item.coverage_status} />
                          <span className="truncate flex-1 text-foreground">
                            {item.description || "-"}
                            {item.item_code && (
                              <span className="ml-1.5 font-mono text-[10px] text-muted-foreground/50">
                                {item.item_code}
                              </span>
                            )}
                          </span>
                          <span
                            className={cn(
                              "text-[10px] px-1.5 py-0.5 rounded font-medium flex-shrink-0",
                              item.coverage_status === "covered"
                                ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-300"
                                : item.coverage_status === "not_covered"
                                  ? "bg-rose-50 text-rose-700 dark:bg-rose-900/20 dark:text-rose-300"
                                  : "bg-amber-50 text-amber-700 dark:bg-amber-900/20 dark:text-amber-300"
                            )}
                          >
                            {item.coverage_status?.replace(/_/g, " ") || "-"}
                          </span>
                          <span className="text-[10px] text-muted-foreground w-14 text-right flex-shrink-0">
                            {item.match_method || "-"}
                          </span>
                          <span className="text-[10px] tabular-nums w-8 text-right flex-shrink-0 font-medium">
                            {conf != null ? `${Math.round(conf * 100)}%` : "-"}
                          </span>
                        </div>

                        {/* Expanded trace timeline */}
                        {isOpen && hasTrace && (
                          <div className="border-b border-border bg-muted/5">
                            <div className="px-4 py-2 space-y-0.5">
                              {trace.map((step: TraceStep, idx: number) => (
                                <TraceStepRow
                                  key={idx}
                                  step={step}
                                  index={idx + 1}
                                />
                              ))}
                            </div>
                          </div>
                        )}

                        {/* No trace message */}
                        {isOpen && !hasTrace && (
                          <div className="border-b border-border px-4 py-2 text-xs text-muted-foreground italic">
                            No trace available for this item.
                          </div>
                        )}
                      </Fragment>
                    );
                  })}
              </Fragment>
            );
          })}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// TRACE STEP ROW
// =============================================================================

function TraceStepRow({ step, index }: { step: TraceStep; index: number }) {
  const [detailOpen, setDetailOpen] = useState(false);
  const hasDetail = step.detail && Object.keys(step.detail).length > 0;

  return (
    <div>
      <div
        onClick={() => hasDetail && setDetailOpen((v) => !v)}
        className={cn(
          "flex items-start gap-2 text-[11px] py-0.5 rounded px-1 -mx-1 min-w-0",
          hasDetail && "cursor-pointer hover:bg-muted/30 transition-colors"
        )}
      >
        <span className="text-muted-foreground/50 w-5 text-right flex-shrink-0 tabular-nums">
          #{index}
        </span>
        <span className="text-muted-foreground w-28 truncate flex-shrink-0 font-mono text-[10px]">
          {step.stage}
        </span>
        <ActionBadge action={step.action} />
        {step.confidence != null && (
          <span className="tabular-nums text-muted-foreground flex-shrink-0">
            {Math.round(step.confidence * 100)}%
          </span>
        )}
        <span className="text-muted-foreground whitespace-normal break-words flex-1 min-w-0">
          {step.reasoning}
        </span>
        {hasDetail && (
          <ChevronRight
            className={cn(
              "h-2.5 w-2.5 text-muted-foreground/50 transition-transform flex-shrink-0",
              detailOpen && "rotate-90"
            )}
          />
        )}
      </div>
      {detailOpen && hasDetail && (
        <div className="ml-8 pl-3 border-l border-border py-1 space-y-0.5">
          {Object.entries(step.detail!).map(([k, v]) => (
            <div key={k} className="flex gap-2 text-[10px] text-muted-foreground min-w-0">
              <span className="font-medium flex-shrink-0">{k}:</span>
              <span className="truncate min-w-0">
                {typeof v === "object" ? JSON.stringify(v) : String(v)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
