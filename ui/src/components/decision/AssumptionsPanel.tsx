import { useState, useMemo } from "react";
import { cn } from "../../lib/utils";
import { StatusBadge } from "../shared";
import type {
  AssumptionRecord,
  DenialClauseDefinition,
} from "../../types";

interface AssumptionsPanelProps {
  assumptions: AssumptionRecord[];
  clauses: DenialClauseDefinition[];
  onAssumptionChange: (clauseRef: string, value: boolean) => void;
}

export function AssumptionsPanel({
  assumptions,
  clauses,
  onAssumptionChange,
}: AssumptionsPanelProps) {
  const [isOpen, setIsOpen] = useState(false);

  // Build a lookup from clause reference to clause definition
  const clauseMap = useMemo(() => {
    const map = new Map<string, DenialClauseDefinition>();
    for (const c of clauses) {
      map.set(c.reference, c);
    }
    return map;
  }, [clauses]);

  // Filter only tier 2 and 3 assumptions
  const relevantAssumptions = useMemo(
    () => assumptions.filter((a) => a.tier === 2 || a.tier === 3),
    [assumptions]
  );

  // Group by category
  const groupedByCategory = useMemo(() => {
    const groups = new Map<string, AssumptionRecord[]>();
    for (const a of relevantAssumptions) {
      const clause = clauseMap.get(a.clause_reference);
      const category = clause?.category || "Other";
      const list = groups.get(category) || [];
      list.push(a);
      groups.set(category, list);
    }
    return groups;
  }, [relevantAssumptions, clauseMap]);

  if (relevantAssumptions.length === 0) {
    return null;
  }

  return (
    <div className="bg-card border border-border rounded-lg shadow-sm">
      {/* Collapse header */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-foreground hover:bg-muted/50 transition-colors rounded-lg"
      >
        <div className="flex items-center gap-2">
          <svg
            className={cn(
              "w-4 h-4 transition-transform text-muted-foreground",
              isOpen && "rotate-90"
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
          <span>Assumptions</span>
          <StatusBadge variant="neutral" size="sm">
            {relevantAssumptions.length}
          </StatusBadge>
        </div>
        <span className="text-xs text-muted-foreground">
          Toggle to re-evaluate
        </span>
      </button>

      {/* Collapsible body */}
      {isOpen && (
        <div className="px-4 pb-4 space-y-4">
          {Array.from(groupedByCategory.entries()).map(
            ([category, items]) => (
              <div key={category}>
                <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                  {category}
                </h4>
                <div className="space-y-2">
                  {items.map((a) => (
                    <div
                      key={a.clause_reference}
                      className="flex items-center justify-between gap-3 py-1.5"
                    >
                      <div className="flex items-center gap-2 min-w-0 flex-1">
                        <StatusBadge
                          variant={a.tier === 2 ? "info" : "warning"}
                          size="sm"
                        >
                          T{a.tier}
                        </StatusBadge>
                        <span className="text-sm text-foreground truncate">
                          {a.question}
                        </span>
                      </div>
                      {/* Toggle switch */}
                      <button
                        role="switch"
                        aria-checked={a.assumed_value}
                        onClick={() =>
                          onAssumptionChange(
                            a.clause_reference,
                            !a.assumed_value
                          )
                        }
                        className={cn(
                          "relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors",
                          a.assumed_value
                            ? "bg-success"
                            : "bg-muted-foreground/30"
                        )}
                      >
                        <span
                          className={cn(
                            "pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-sm transition-transform",
                            a.assumed_value
                              ? "translate-x-4"
                              : "translate-x-0"
                          )}
                        />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )
          )}
        </div>
      )}
    </div>
  );
}
