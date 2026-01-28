import { useState } from "react";
import { AlertTriangle, ExternalLink, ChevronDown, ChevronRight, Check } from "lucide-react";
import type { FactConflict, ConflictSource } from "../../types";
import { cn, formatFieldName } from "../../lib/utils";

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

  // Normalize sources to handle both old (string[]) and new (ConflictSource[]) formats
  // Old format: ["doc_id1", "doc_id2"] - just doc IDs
  // New format: [{doc_id, doc_type, filename}, ...] - full source objects
  const normalizeSources = (rawSources: unknown[]): ConflictSource[] => {
    if (!rawSources || rawSources.length === 0) {
      return [];
    }
    // Check if first element is a string (old format) or object (new format)
    const first = rawSources[0];
    if (typeof first === "string") {
      // Old format - convert strings to minimal ConflictSource
      return rawSources.map((docId) => ({
        doc_id: docId as string,
        doc_type: "unknown",
        filename: `${(docId as string).slice(0, 12)}...`,
      }));
    }
    // New format - already ConflictSource objects
    return rawSources as ConflictSource[];
  };

  // Get first doc_id from sources array for the View button
  const getFirstDocId = (sources: ConflictSource[]): string | null => {
    if (sources.length > 0) {
      return sources[0].doc_id;
    }
    return null;
  };

  // Format a single source for display: "filename (doc_type)"
  const formatSingleSource = (source: ConflictSource): string => {
    const docType = source.doc_type.replace(/_/g, " ");
    return `${source.filename} (${docType})`;
  };

  // Format sources array for display
  const formatSources = (sources: ConflictSource[]): string => {
    if (sources.length === 0) {
      return "unknown";
    }
    if (sources.length === 1) {
      return formatSingleSource(sources[0]);
    }
    // Multiple sources - show count
    return `${formatSingleSource(sources[0])} +${sources.length - 1} more`;
  };

  return (
    <div className="rounded-lg border border-warning/30 overflow-hidden shadow-sm relative">
      {/* Left accent bar */}
      <div className="absolute left-0 top-0 bottom-0 w-1 bg-warning" />

      {/* Header with gradient */}
      <div className="px-4 py-3 pl-5 flex items-center gap-2 border-b border-warning/30 gradient-warning">
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
                  {formatFieldName(conflict.fact_name)}
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
                      const rawSources = conflict.sources[idx] || [];
                      const sources = normalizeSources(rawSources as unknown[]);
                      const docId = getFirstDocId(sources);
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
                              from {formatSources(sources)}
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
