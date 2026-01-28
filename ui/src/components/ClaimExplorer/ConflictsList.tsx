import { useState } from "react";
import { AlertTriangle, ExternalLink, ChevronDown, ChevronRight, Check } from "lucide-react";
import type { FactConflict } from "../../types";
import { cn } from "../../lib/utils";

interface ConflictsListProps {
  conflicts: FactConflict[];
  onViewSource?: (docId: string) => void;
}

/**
 * List of fact conflicts with expandable details and source document links.
 */
export function ConflictsList({ conflicts, onViewSource }: ConflictsListProps) {
  const [expandedConflicts, setExpandedConflicts] = useState<Set<string>>(
    new Set(conflicts.length > 0 ? [conflicts[0].fact_name] : [])
  );

  if (conflicts.length === 0) {
    return null;
  }

  const toggleExpanded = (factName: string) => {
    setExpandedConflicts((prev) => {
      const next = new Set(prev);
      if (next.has(factName)) {
        next.delete(factName);
      } else {
        next.add(factName);
      }
      return next;
    });
  };

  // Extract doc_id from source array (format varies, typically ["doc_id", "doc_type", ...])
  const getDocIdFromSource = (source: string[]): string | null => {
    if (source.length > 0) {
      // First element is typically the doc_id
      return source[0];
    }
    return null;
  };

  // Format source for display
  const formatSource = (source: string[]): string => {
    if (source.length >= 2) {
      const docId = source[0];
      const docType = source[1];
      // Shorten doc_id if too long
      const shortId = docId.length > 8 ? `${docId.slice(0, 4)}...${docId.slice(-4)}` : docId;
      return `${docType} (${shortId})`;
    }
    return source.join(" / ");
  };

  return (
    <div className="rounded-lg border border-warning/30 bg-warning/10 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 flex items-center gap-2 border-b border-warning/30">
        <AlertTriangle className="h-4 w-4 text-warning" />
        <h3 className="font-semibold text-foreground">
          Conflicts ({conflicts.length})
        </h3>
      </div>

      {/* Conflict Items */}
      <div className="divide-y divide-warning/20">
        {conflicts.map((conflict) => {
          const isExpanded = expandedConflicts.has(conflict.fact_name);

          return (
            <div key={conflict.fact_name} className="bg-card">
              {/* Conflict Header */}
              <button
                onClick={() => toggleExpanded(conflict.fact_name)}
                className="w-full px-4 py-3 flex items-center gap-3 hover:bg-muted transition-colors"
              >
                {isExpanded ? (
                  <ChevronDown className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                )}
                <AlertTriangle className="h-4 w-4 text-warning flex-shrink-0" />
                <span className="font-medium text-foreground">
                  {conflict.fact_name.replace(/_/g, " ")}
                </span>
                <span className="text-xs text-muted-foreground ml-auto">
                  {conflict.values.length} values
                </span>
              </button>

              {/* Conflict Details */}
              {isExpanded && (
                <div className="px-4 pb-4 pl-11 space-y-3">
                  {/* Conflicting Values */}
                  <div className="space-y-2">
                    {conflict.values.map((value, idx) => {
                      const source = conflict.sources[idx];
                      const docId = source ? getDocIdFromSource(source) : null;
                      const isSelected = value === conflict.selected_value;

                      return (
                        <div
                          key={idx}
                          className={cn(
                            "flex items-start gap-2 p-2 rounded-md",
                            isSelected
                              ? "bg-info/10 border border-info/30"
                              : "bg-muted/50"
                          )}
                        >
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span
                                className={cn(
                                  "font-mono text-sm",
                                  isSelected
                                    ? "text-info font-semibold"
                                    : "text-foreground"
                                )}
                              >
                                "{value}"
                              </span>
                              {isSelected && (
                                <Check className="h-3.5 w-3.5 text-info flex-shrink-0" />
                              )}
                            </div>
                            <div className="text-xs text-muted-foreground mt-0.5">
                              from {source ? formatSource(source) : "unknown"}
                            </div>
                          </div>
                          {docId && onViewSource && (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                onViewSource(docId);
                              }}
                              className={cn(
                                "flex-shrink-0 px-2 py-1 text-xs rounded",
                                "bg-muted hover:bg-muted/80",
                                "text-foreground",
                                "flex items-center gap-1 transition-colors"
                              )}
                            >
                              <ExternalLink className="h-3 w-3" />
                              View
                            </button>
                          )}
                        </div>
                      );
                    })}
                  </div>

                  {/* Selection Reason */}
                  <div className="pt-2 border-t border-border">
                    <div className="flex items-start gap-2">
                      <span className="text-xs font-medium text-muted-foreground">
                        Selected:
                      </span>
                      <span className="text-sm text-info font-medium">
                        "{conflict.selected_value}"
                      </span>
                      <span className="text-xs text-muted-foreground">
                        ({Math.round(conflict.selected_confidence * 100)}% confidence)
                      </span>
                    </div>
                    {conflict.selection_reason && (
                      <p className="text-xs text-muted-foreground mt-1">
                        {conflict.selection_reason}
                      </p>
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
