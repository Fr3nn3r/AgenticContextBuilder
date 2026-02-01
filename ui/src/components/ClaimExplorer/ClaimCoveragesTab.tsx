import { useState } from "react";
import {
  Loader2,
  Info,
  AlertTriangle,
  Copy,
  CheckCircle,
  Bot,
  Ruler,
  Hash,
  Check,
} from "lucide-react";
import { cn } from "../../lib/utils";
import type {
  CoverageAnalysisResult,
  CoverageStatus,
  MatchMethod,
  LineItemCoverage,
} from "../../types";

interface ClaimCoveragesTabProps {
  coverageAnalysis: CoverageAnalysisResult | null;
  loading: boolean;
}

// === Helpers ===

function formatCHF(value: number): string {
  return new Intl.NumberFormat("de-CH", {
    style: "currency",
    currency: "CHF",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function componentLabel(component: string): string {
  return component.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function humanizeReason(reason: string): string {
  const map: Record<string, string> = {
    fee: "Fees & Charges",
    consumable: "Consumable Parts",
    component_excluded: "Excluded Components",
    category_not_covered: "Uncovered Category",
    not_in_category: "Not in Covered Category",
    wear_and_tear: "Wear & Tear Items",
    accessory: "Accessories",
    maintenance: "Maintenance Items",
  };
  return map[reason] || reason.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

const STATUS_BADGE: Record<CoverageStatus, { label: string; className: string }> = {
  covered: { label: "Covered", className: "bg-success/15 text-success" },
  not_covered: { label: "Not Covered", className: "bg-destructive/15 text-destructive" },
  review_needed: { label: "Review", className: "bg-warning/15 text-warning" },
};

const METHOD_CONFIG: Record<MatchMethod, { label: string; icon: typeof Ruler; className: string }> = {
  rule: { label: "Rule", icon: Ruler, className: "text-success bg-success/10" },
  part_number: { label: "Part#", icon: Hash, className: "text-primary bg-primary/10" },
  keyword: { label: "Keyword", icon: Ruler, className: "text-blue-400 bg-blue-400/10" },
  llm: { label: "LLM", icon: Bot, className: "text-warning bg-warning/10" },
  manual: { label: "Manual", icon: Check, className: "text-foreground bg-muted" },
};

function MethodBadge({ method }: { method: MatchMethod }) {
  const config = METHOD_CONFIG[method];
  const Icon = config.icon;
  return (
    <span className={cn("inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium", config.className)}>
      <Icon className="h-2.5 w-2.5" />
      {config.label}
    </span>
  );
}

function TrustBar({ items }: { items: LineItemCoverage[] }) {
  const counts: Record<string, number> = {};
  for (const item of items) {
    counts[item.match_method] = (counts[item.match_method] || 0) + 1;
  }
  const total = items.length;
  const llmCount = counts["llm"] || 0;
  const llmPercent = total > 0 ? Math.round((llmCount / total) * 100) : 0;

  if (total === 0) return null;

  return (
    <div className="flex items-center gap-3">
      <div className="h-1.5 rounded-full bg-muted overflow-hidden flex flex-1">
        {(counts["rule"] || 0) > 0 && (
          <div className="bg-success h-full" style={{ width: `${((counts["rule"] || 0) / total) * 100}%` }} />
        )}
        {(counts["part_number"] || 0) > 0 && (
          <div className="bg-primary h-full" style={{ width: `${((counts["part_number"] || 0) / total) * 100}%` }} />
        )}
        {(counts["keyword"] || 0) > 0 && (
          <div className="bg-blue-400 h-full" style={{ width: `${((counts["keyword"] || 0) / total) * 100}%` }} />
        )}
        {(counts["llm"] || 0) > 0 && (
          <div className="bg-warning h-full" style={{ width: `${((counts["llm"] || 0) / total) * 100}%` }} />
        )}
      </div>
      <div className="flex gap-2 flex-shrink-0">
        {(counts["rule"] || 0) > 0 && (
          <span className="text-[10px] text-muted-foreground flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-success inline-block" />Rule {counts["rule"]}
          </span>
        )}
        {(counts["part_number"] || 0) > 0 && (
          <span className="text-[10px] text-muted-foreground flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-primary inline-block" />Part# {counts["part_number"]}
          </span>
        )}
        {(counts["keyword"] || 0) > 0 && (
          <span className="text-[10px] text-muted-foreground flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-400 inline-block" />Kw {counts["keyword"]}
          </span>
        )}
        {llmCount > 0 && (
          <span className={cn("text-[10px] flex items-center gap-1", llmPercent > 50 ? "text-warning" : "text-muted-foreground")}>
            <span className="w-1.5 h-1.5 rounded-full bg-warning inline-block" />LLM {llmCount}
          </span>
        )}
      </div>
    </div>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const textarea = document.createElement("textarea");
      textarea.value = text;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      onClick={handleCopy}
      className="p-1.5 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
      title={copied ? "Copied!" : "Copy to clipboard"}
    >
      {copied ? <CheckCircle className="h-3.5 w-3.5 text-success" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  );
}

function buildExplanationText(coverageAnalysis: CoverageAnalysisResult): string {
  const parts: string[] = [];

  const pr = coverageAnalysis.primary_repair;
  if (pr?.component && pr.is_covered === false) {
    parts.push(
      `Primary Repair: ${componentLabel(pr.component)} (${componentLabel(pr.category || "unknown")}) \u2014 Not Covered\n` +
      `The primary repair component "${componentLabel(pr.component)}" is not explicitly listed in the covered components of the policy.`
    );
  }

  if (coverageAnalysis.non_covered_explanations?.length) {
    for (const group of coverageAnalysis.non_covered_explanations) {
      parts.push(
        `${humanizeReason(group.exclusion_reason)} (${group.items.length} item${group.items.length !== 1 ? "s" : ""}, ${formatCHF(group.total_amount)}):\n${group.explanation}`
      );
    }
  }

  if (parts.length === 0) {
    const notCovered = coverageAnalysis.line_items.filter(
      (li) => li.coverage_status === "not_covered"
    );
    if (notCovered.length > 0) {
      for (const item of notCovered) {
        parts.push(`${item.description}: ${item.match_reasoning}`);
      }
    } else {
      parts.push("All line items are covered by the policy.");
    }
  }

  return parts.join("\n\n");
}

/**
 * Coverages tab: coverage explanation card and detailed line items table.
 */
export function ClaimCoveragesTab({ coverageAnalysis, loading }: ClaimCoveragesTabProps) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          <p className="text-sm text-muted-foreground">Loading coverage analysis...</p>
        </div>
      </div>
    );
  }

  if (!coverageAnalysis) {
    return (
      <div className="p-4">
        <div className="bg-card rounded-lg border border-border p-8 text-center">
          <p className="text-sm text-muted-foreground">
            No coverage analysis available for this claim.
          </p>
        </div>
      </div>
    );
  }

  const primaryRepair = coverageAnalysis.primary_repair;
  const nonCoveredExplanations = coverageAnalysis.non_covered_explanations ?? [];
  const notCoveredItems = coverageAnalysis.line_items.filter(
    (li) => li.coverage_status === "not_covered"
  );
  const hasNonCovered =
    (primaryRepair?.is_covered === false) ||
    nonCoveredExplanations.length > 0 ||
    notCoveredItems.length > 0;

  const explanationText = buildExplanationText(coverageAnalysis);

  const sortedLineItems = [...coverageAnalysis.line_items].sort((a, b) => {
    const order: Record<string, number> = { not_covered: 0, review_needed: 1, covered: 2 };
    return (order[a.coverage_status] ?? 3) - (order[b.coverage_status] ?? 3);
  });

  return (
    <div className="p-4 space-y-4">
      {/* Coverage Explanation Card */}
      <div className="bg-card rounded-lg border border-border overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <div className="flex items-center gap-2">
            <Info className="h-4 w-4 text-muted-foreground" />
            <h3 className="text-sm font-semibold text-foreground">Coverage Explanation</h3>
          </div>
          <CopyButton text={explanationText} />
        </div>
        <div className="p-4 space-y-3">
          {/* Primary repair explanation */}
          {primaryRepair?.component && primaryRepair.is_covered === false && (
            <div className="flex items-start gap-3 p-3 rounded-md bg-destructive/5 border border-destructive/20">
              <AlertTriangle className="h-4 w-4 text-destructive mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-sm font-medium text-destructive">Primary Repair Not Covered</p>
                <p className="text-sm text-muted-foreground mt-1">
                  The primary repair component &ldquo;{componentLabel(primaryRepair.component)}&rdquo;
                  ({componentLabel(primaryRepair.category || "unknown")}) is not explicitly listed
                  in the covered components of the policy.
                </p>
              </div>
            </div>
          )}

          {/* Non-covered explanation groups */}
          {nonCoveredExplanations.map((group, idx) => (
            <div key={idx} className="border border-border rounded-md p-3">
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-foreground">
                    {humanizeReason(group.exclusion_reason)}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    ({group.items.length} item{group.items.length !== 1 ? "s" : ""})
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-foreground">
                    {formatCHF(group.total_amount)}
                  </span>
                  <CopyButton text={group.explanation} />
                </div>
              </div>
              <p className="text-sm text-muted-foreground">{group.explanation}</p>
              {group.policy_reference && (
                <span className="inline-block mt-2 text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded">
                  {group.policy_reference}
                </span>
              )}
              {group.match_confidence < 0.8 && (
                <span className="inline-block mt-2 ml-2 text-xs text-warning bg-warning/10 px-2 py-0.5 rounded">
                  Needs verification
                </span>
              )}
            </div>
          ))}

          {/* Fallback: per-item reasons when no grouped explanations */}
          {nonCoveredExplanations.length === 0 &&
            notCoveredItems.length > 0 &&
            !(primaryRepair?.component && primaryRepair.is_covered === false) && (
              <div className="space-y-2">
                {notCoveredItems.slice(0, 5).map((item, idx) => (
                  <div key={idx} className="flex items-start gap-2 text-sm">
                    <span className="text-destructive mt-0.5">&bull;</span>
                    <div>
                      <span className="font-medium text-foreground">{item.description}</span>
                      <span className="text-muted-foreground">: {item.match_reasoning}</span>
                    </div>
                  </div>
                ))}
                {notCoveredItems.length > 5 && (
                  <p className="text-xs text-muted-foreground pl-4">
                    ...and {notCoveredItems.length - 5} more
                  </p>
                )}
              </div>
            )}

          {/* All covered message */}
          {!hasNonCovered && (
            <p className="text-sm text-success flex items-center gap-2">
              <CheckCircle className="h-4 w-4" />
              All line items are covered by the policy.
            </p>
          )}
        </div>
      </div>

      {/* Line Items Table */}
      {sortedLineItems.length > 0 && (
        <div className="bg-card rounded-lg border border-border overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-border">
            <h3 className="text-sm font-semibold text-foreground">
              Coverage Details
              <span className="ml-2 text-xs text-muted-foreground font-normal">
                ({sortedLineItems.length} items)
              </span>
            </h3>
          </div>

          {/* Trust bar */}
          <div className="px-4 py-2 bg-muted/20 border-b border-border">
            <TrustBar items={sortedLineItems} />
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-muted/50">
                  <th className="text-left px-3 py-2 font-medium text-muted-foreground">Description</th>
                  <th className="text-left px-3 py-2 font-medium text-muted-foreground">Code</th>
                  <th className="text-left px-3 py-2 font-medium text-muted-foreground">Type</th>
                  <th className="text-right px-3 py-2 font-medium text-muted-foreground">Amount</th>
                  <th className="text-center px-3 py-2 font-medium text-muted-foreground">Status</th>
                  <th className="text-left px-3 py-2 font-medium text-muted-foreground">Category</th>
                  <th className="text-center px-3 py-2 font-medium text-muted-foreground">Method</th>
                </tr>
              </thead>
              <tbody>
                {sortedLineItems.map((item, idx) => {
                  const badge = STATUS_BADGE[item.coverage_status];
                  return (
                    <tr key={idx} className="border-t border-border hover:bg-muted/30">
                      <td
                        className="px-3 py-2 max-w-[300px] truncate cursor-help"
                        title={item.match_reasoning || item.description}
                      >
                        {item.description}
                      </td>
                      <td className="px-3 py-2 font-mono text-muted-foreground">
                        {item.item_code ?? "-"}
                      </td>
                      <td className="px-3 py-2 text-muted-foreground capitalize">
                        {item.item_type}
                      </td>
                      <td className="px-3 py-2 text-right font-mono">
                        {formatCHF(item.total_price)}
                      </td>
                      <td className="px-3 py-2 text-center">
                        <span className={cn("inline-block px-2 py-0.5 rounded-full text-xs font-medium", badge.className)}>
                          {badge.label}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-muted-foreground">
                        {item.coverage_category ?? "-"}
                      </td>
                      <td className="px-3 py-2 text-center">
                        <MethodBadge method={item.match_method} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
