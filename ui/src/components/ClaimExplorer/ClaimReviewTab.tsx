import { useState } from "react";
import {
  CheckCircle2,
  XCircle,
  ArrowRightCircle,
  Copy,
  Check,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  ShieldCheck,
  Loader2,
  FileWarning,
  Wrench,
  Bot,
  Ruler,
  Hash,
} from "lucide-react";
import { cn } from "../../lib/utils";
import type {
  ClaimAssessment,
  AssessmentDecision,
  CoverageAnalysisResult,
  NonCoveredExplanation,
  CoverageStatus,
  MatchMethod,
  LineItemCoverage,
} from "../../types";

interface ClaimReviewTabProps {
  claimId: string;
  assessment: ClaimAssessment | null;
  coverageAnalysis: CoverageAnalysisResult | null;
  loading: boolean;
  error: string | null;
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

function formatConfidence(score: number): string {
  const pct = score <= 1 ? score * 100 : score;
  return `${pct.toFixed(0)}%`;
}

/** Human-readable label for exclusion reason keys */
function exclusionLabel(reason: string): string {
  const map: Record<string, string> = {
    fee: "Fees & Surcharges",
    consumable: "Consumables / Wear Items",
    component_excluded: "Excluded Component",
    not_in_policy: "Not in Policy Scope",
    component_not_in_list: "Component Not In List",
    age_exclusion: "Age Exclusion",
    betterment: "Betterment Deduction",
    pre_existing: "Pre-existing Condition",
    cosmetic: "Cosmetic Damage",
    maintenance: "Regular Maintenance",
    category_not_covered: "Category Not Covered",
    uncovered_labor: "Uncovered Labor",
    not_covered_category: "Category Not Covered",
    other: "Other / Unclassified",
  };
  return map[reason] || reason.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Human-readable component name from snake_case */
function componentLabel(component: string): string {
  return component.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

const DECISION_STYLES: Record<AssessmentDecision, {
  icon: typeof CheckCircle2;
  label: string;
  bg: string;
  border: string;
  text: string;
  iconColor: string;
}> = {
  APPROVE: {
    icon: CheckCircle2,
    label: "Approved",
    bg: "bg-success/10",
    border: "border-success/30",
    text: "text-success",
    iconColor: "text-success",
  },
  REJECT: {
    icon: XCircle,
    label: "Rejected",
    bg: "bg-destructive/10",
    border: "border-destructive/30",
    text: "text-destructive",
    iconColor: "text-destructive",
  },
  REFER_TO_HUMAN: {
    icon: ArrowRightCircle,
    label: "Referred to Human",
    bg: "bg-warning/10",
    border: "border-warning/30",
    text: "text-warning",
    iconColor: "text-warning",
  },
};

const STATUS_BADGE: Record<CoverageStatus, { label: string; className: string }> = {
  covered: { label: "Covered", className: "bg-success/15 text-success" },
  not_covered: { label: "Not Covered", className: "bg-destructive/15 text-destructive" },
  review_needed: { label: "Review", className: "bg-warning/15 text-warning" },
};

const METHOD_CONFIG: Record<MatchMethod, { label: string; icon: typeof Ruler; className: string; trust: string }> = {
  rule: { label: "Rule", icon: Ruler, className: "text-success bg-success/10", trust: "high" },
  part_number: { label: "Part#", icon: Hash, className: "text-primary bg-primary/10", trust: "high" },
  keyword: { label: "Keyword", icon: Ruler, className: "text-blue-400 bg-blue-400/10", trust: "medium" },
  llm: { label: "LLM", icon: Bot, className: "text-warning bg-warning/10", trust: "low" },
  manual: { label: "Manual", icon: Check, className: "text-foreground bg-muted", trust: "high" },
};

// === Sub-components ===

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      const textarea = document.createElement("textarea");
      textarea.value = text;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <button
      onClick={handleCopy}
      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
      title="Copy to clipboard"
    >
      {copied ? (
        <Check className="h-3.5 w-3.5 text-success" />
      ) : (
        <Copy className="h-3.5 w-3.5" />
      )}
    </button>
  );
}

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

/** Compute match method distribution for a set of line items */
function computeMethodStats(items: LineItemCoverage[]) {
  const counts: Record<string, number> = {};
  for (const item of items) {
    counts[item.match_method] = (counts[item.match_method] || 0) + 1;
  }
  const total = items.length;
  const llmCount = counts["llm"] || 0;
  const ruleCount = (counts["rule"] || 0) + (counts["part_number"] || 0) + (counts["keyword"] || 0) + (counts["manual"] || 0);
  const llmPercent = total > 0 ? Math.round((llmCount / total) * 100) : 0;
  return { counts, total, llmCount, ruleCount, llmPercent };
}

function ExplanationCard({ group }: { group: NonCoveredExplanation }) {
  const [expanded, setExpanded] = useState(true);
  const needsVerification = group.match_confidence < 0.8;

  return (
    <div className="bg-card rounded-lg border border-border overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-muted/50 transition-colors"
      >
        <div className="flex items-center gap-3 min-w-0">
          {expanded ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground flex-shrink-0" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground flex-shrink-0" />
          )}
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-medium text-sm text-foreground">
                {exclusionLabel(group.exclusion_reason)}
              </span>
              {group.policy_reference && (
                <span className="text-xs px-2 py-0.5 rounded-full bg-primary/10 text-primary font-mono">
                  {group.policy_reference}
                </span>
              )}
              {needsVerification && (
                <span className="text-xs px-2 py-0.5 rounded-full bg-warning/15 text-warning flex items-center gap-1">
                  <AlertTriangle className="h-3 w-3" />
                  Needs verification
                </span>
              )}
            </div>
            <span className="text-xs text-muted-foreground">
              {group.items.length} item{group.items.length !== 1 ? "s" : ""}
            </span>
          </div>
        </div>
        <span className="text-sm font-mono font-medium text-destructive flex-shrink-0 ml-3">
          {formatCHF(group.total_amount)}
        </span>
      </button>

      {/* Body */}
      {expanded && (
        <div className="px-4 pb-4 border-t border-border">
          {/* Explanation text with copy */}
          <div className="mt-3 flex items-start gap-1">
            <p className="text-sm text-foreground leading-relaxed flex-1">
              {group.explanation}
            </p>
            <CopyButton text={group.explanation} />
          </div>

          {/* Items list */}
          <div className="mt-3 space-y-1">
            {group.items.map((item, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between text-xs text-muted-foreground py-1 px-2 rounded hover:bg-muted/50"
              >
                <span className="truncate flex-1 mr-2">
                  {group.item_codes[idx] && (
                    <span className="font-mono text-muted-foreground/70 mr-1.5">
                      {group.item_codes[idx]}
                    </span>
                  )}
                  {item}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/** Trust indicator bar showing rule vs LLM distribution */
function TrustBar({ items }: { items: LineItemCoverage[] }) {
  const stats = computeMethodStats(items);
  if (stats.total === 0) return null;

  return (
    <div className="bg-card rounded-lg border border-border p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-muted-foreground">Match Quality</span>
        {stats.llmPercent > 50 && (
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-warning/15 text-warning flex items-center gap-1">
            <AlertTriangle className="h-2.5 w-2.5" />
            {stats.llmPercent}% LLM-matched
          </span>
        )}
      </div>
      <div className="h-2 rounded-full bg-muted overflow-hidden flex">
        {(stats.counts["rule"] || 0) > 0 && (
          <div className="bg-success h-full" style={{ width: `${((stats.counts["rule"] || 0) / stats.total) * 100}%` }} title={`Rule: ${stats.counts["rule"]}`} />
        )}
        {(stats.counts["part_number"] || 0) > 0 && (
          <div className="bg-primary h-full" style={{ width: `${((stats.counts["part_number"] || 0) / stats.total) * 100}%` }} title={`Part#: ${stats.counts["part_number"]}`} />
        )}
        {(stats.counts["keyword"] || 0) > 0 && (
          <div className="bg-blue-400 h-full" style={{ width: `${((stats.counts["keyword"] || 0) / stats.total) * 100}%` }} title={`Keyword: ${stats.counts["keyword"]}`} />
        )}
        {(stats.counts["llm"] || 0) > 0 && (
          <div className="bg-warning h-full" style={{ width: `${((stats.counts["llm"] || 0) / stats.total) * 100}%` }} title={`LLM: ${stats.counts["llm"]}`} />
        )}
      </div>
      <div className="flex gap-3 mt-1.5 flex-wrap">
        {(stats.counts["rule"] || 0) > 0 && (
          <span className="text-[10px] text-muted-foreground flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-success inline-block" />
            Rule {stats.counts["rule"]}
          </span>
        )}
        {(stats.counts["part_number"] || 0) > 0 && (
          <span className="text-[10px] text-muted-foreground flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-primary inline-block" />
            Part# {stats.counts["part_number"]}
          </span>
        )}
        {(stats.counts["keyword"] || 0) > 0 && (
          <span className="text-[10px] text-muted-foreground flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-blue-400 inline-block" />
            Keyword {stats.counts["keyword"]}
          </span>
        )}
        {(stats.counts["llm"] || 0) > 0 && (
          <span className="text-[10px] text-muted-foreground flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-warning inline-block" />
            LLM {stats.counts["llm"]}
          </span>
        )}
      </div>
    </div>
  );
}

// === Main Component ===

export function ClaimReviewTab({
  claimId,
  assessment,
  coverageAnalysis,
  loading,
  error,
}: ClaimReviewTabProps) {
  const [lineItemsExpanded, setLineItemsExpanded] = useState(false);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        <span className="ml-2 text-sm text-muted-foreground">Loading review data...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center py-20 text-destructive">
        <FileWarning className="h-5 w-5 mr-2" />
        <span className="text-sm">{error}</span>
      </div>
    );
  }

  if (!assessment && !coverageAnalysis) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
        <ShieldCheck className="h-10 w-10 mb-3 opacity-40" />
        <p className="text-sm font-medium">No review data available</p>
        <p className="text-xs mt-1">Run an assessment to see coverage analysis and decision.</p>
      </div>
    );
  }

  const summary = coverageAnalysis?.summary;
  const explanations = coverageAnalysis?.non_covered_explanations;
  const nonCoveredCount = explanations?.length ?? 0;
  const totalNonCovered = summary?.total_not_covered ?? 0;
  const primaryRepair = coverageAnalysis?.primary_repair;

  // Sort line items: NOT_COVERED first, then REVIEW_NEEDED, then COVERED
  const sortedLineItems = [...(coverageAnalysis?.line_items ?? [])].sort((a, b) => {
    const order: Record<string, number> = { not_covered: 0, review_needed: 1, covered: 2 };
    return (order[a.coverage_status] ?? 3) - (order[b.coverage_status] ?? 3);
  });

  return (
    <div className="p-6 space-y-6 max-w-4xl mx-auto">
      {/* Section 1: Decision Banner + Primary Repair */}
      {assessment && (
        <DecisionBanner
          assessment={assessment}
          coverageAnalysis={coverageAnalysis}
        />
      )}

      {/* Primary Repair Component — the most important signal */}
      {primaryRepair && primaryRepair.component && (
        <div className="bg-card rounded-lg border border-border p-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center flex-shrink-0">
              <Wrench className="h-4 w-4 text-muted-foreground" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-medium text-foreground">
                  Primary Repair: {componentLabel(primaryRepair.component)}
                </span>
                {primaryRepair.category && (
                  <span className="text-xs px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
                    {componentLabel(primaryRepair.category)}
                  </span>
                )}
                <span className={cn(
                  "text-xs px-2 py-0.5 rounded-full font-medium",
                  primaryRepair.is_covered ? "bg-success/15 text-success" : "bg-destructive/15 text-destructive"
                )}>
                  {primaryRepair.is_covered ? "Covered" : "Not Covered"}
                </span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground font-mono">
                  {primaryRepair.determination_method}
                </span>
              </div>
              {primaryRepair.description && (
                <span className="text-xs text-muted-foreground">{primaryRepair.description}</span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Section 2: Match Quality Trust Bar */}
      {coverageAnalysis && coverageAnalysis.line_items.length > 0 && (
        <TrustBar items={coverageAnalysis.line_items} />
      )}

      {/* Section 3: Non-Covered Explanations */}
      {coverageAnalysis && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-foreground">
              Non-Covered Items
              {nonCoveredCount > 0 && (
                <span className="ml-2 text-sm font-normal text-muted-foreground">
                  ({nonCoveredCount} group{nonCoveredCount !== 1 ? "s" : ""})
                </span>
              )}
            </h2>
            {totalNonCovered > 0 && (
              <span className="text-sm font-mono font-medium text-destructive">
                {formatCHF(totalNonCovered)}
              </span>
            )}
          </div>

          {/* Explanation groups */}
          {explanations && explanations.length > 0 ? (
            <div className="space-y-2">
              {explanations.map((group, idx) => (
                <ExplanationCard key={idx} group={group} />
              ))}
            </div>
          ) : (
            <div className="text-sm text-muted-foreground bg-success/5 border border-success/20 rounded-lg p-4">
              All items are covered by the policy.
            </div>
          )}
        </div>
      )}

      {/* Section 4: Coverage & Payout Summary */}
      {(summary || assessment?.payout_breakdown) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Left: Coverage Breakdown */}
          {summary && (
            <div className="bg-card rounded-lg border border-border p-4">
              <h3 className="text-sm font-semibold text-foreground mb-3">Coverage Breakdown</h3>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Total Claimed</span>
                  <span className="font-mono">{formatCHF(summary.total_claimed)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Covered</span>
                  <span className="font-mono text-success">{formatCHF(summary.total_covered_before_excess)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Not Covered</span>
                  <span className="font-mono text-destructive">{formatCHF(summary.total_not_covered)}</span>
                </div>
                {summary.coverage_percent !== null && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground" title="Depreciation rate based on vehicle mileage/age">Depreciation Rate</span>
                    <span className="font-mono">{summary.coverage_percent}%</span>
                  </div>
                )}

                {/* Coverage bar */}
                <div className="pt-2">
                  <div className="h-2 rounded-full bg-muted overflow-hidden flex">
                    {summary.total_claimed > 0 && (
                      <>
                        <div
                          className="bg-success h-full"
                          style={{ width: `${(summary.total_covered_before_excess / summary.total_claimed) * 100}%` }}
                        />
                        <div
                          className="bg-destructive/60 h-full"
                          style={{ width: `${(summary.total_not_covered / summary.total_claimed) * 100}%` }}
                        />
                      </>
                    )}
                  </div>
                  <div className="flex justify-between text-xs text-muted-foreground mt-1">
                    <span>{summary.items_covered} covered</span>
                    <span>{summary.items_not_covered} not covered</span>
                    {summary.items_review_needed > 0 && (
                      <span>{summary.items_review_needed} review</span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Right: Payout Calculation */}
          <div className="bg-card rounded-lg border border-border p-4">
            <h3 className="text-sm font-semibold text-foreground mb-3">Payout Calculation</h3>
            {assessment?.payout_breakdown ? (
              <div className="space-y-2 text-sm font-mono">
                {assessment.payout_breakdown.covered_subtotal !== null && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground font-sans">Covered Subtotal</span>
                    <span>{formatCHF(assessment.payout_breakdown.covered_subtotal ?? 0)}</span>
                  </div>
                )}
                {assessment.payout_breakdown.coverage_percent !== null && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground font-sans" title="Depreciation rate based on vehicle mileage/age">Depreciation Rate</span>
                    <span>{assessment.payout_breakdown.coverage_percent}%</span>
                  </div>
                )}
                {assessment.payout_breakdown.after_coverage !== null && (
                  <div className="flex justify-between border-t border-border pt-2">
                    <span className="text-muted-foreground font-sans">After Depreciation</span>
                    <span>{formatCHF(assessment.payout_breakdown.after_coverage ?? 0)}</span>
                  </div>
                )}
                {assessment.payout_breakdown.deductible !== null && assessment.payout_breakdown.deductible !== 0 && (
                  <div className="flex justify-between text-destructive">
                    <span className="font-sans">- Excess/Deductible</span>
                    <span>{formatCHF(assessment.payout_breakdown.deductible ?? 0)}</span>
                  </div>
                )}
                <div className="flex justify-between border-t-2 border-primary/30 pt-2 text-success font-bold">
                  <span className="font-sans">Final Payout</span>
                  <span>{formatCHF(assessment.payout_breakdown.final_payout ?? 0)}</span>
                </div>
              </div>
            ) : summary ? (
              <div className="space-y-2 text-sm font-mono">
                <div className="flex justify-between">
                  <span className="text-muted-foreground font-sans">Covered Amount</span>
                  <span>{formatCHF(summary.total_covered_before_excess)}</span>
                </div>
                {summary.excess_amount > 0 && (
                  <div className="flex justify-between text-destructive">
                    <span className="font-sans">- Excess</span>
                    <span>{formatCHF(summary.excess_amount)}</span>
                  </div>
                )}
                <div className="flex justify-between border-t-2 border-primary/30 pt-2 text-success font-bold">
                  <span className="font-sans">Total Payable</span>
                  <span>{formatCHF(summary.total_payable)}</span>
                </div>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No payout data available.</p>
            )}
          </div>
        </div>
      )}

      {/* Section 5: Line Items Table (collapsed by default) */}
      {sortedLineItems.length > 0 && (
        <div className="bg-card rounded-lg border border-border overflow-hidden">
          <button
            onClick={() => setLineItemsExpanded(!lineItemsExpanded)}
            className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-muted/50 transition-colors"
          >
            <div className="flex items-center gap-2">
              {lineItemsExpanded ? (
                <ChevronDown className="h-4 w-4 text-muted-foreground" />
              ) : (
                <ChevronRight className="h-4 w-4 text-muted-foreground" />
              )}
              <span className="text-sm font-semibold text-foreground">
                All Line Items
              </span>
              <span className="text-xs text-muted-foreground">
                ({sortedLineItems.length} items)
              </span>
            </div>
          </button>

          {lineItemsExpanded && (
            <div className="border-t border-border overflow-x-auto">
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
                        <td className="px-3 py-2 max-w-[250px] truncate" title={item.description}>
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
          )}
        </div>
      )}
    </div>
  );
}

// === Decision Banner Sub-component ===

/**
 * Build an adjuster-friendly rationale from assessment + coverage data.
 * Falls back to raw rationale only if it looks readable.
 */
function buildRationale(
  assessment: ClaimAssessment,
  coverageAnalysis: CoverageAnalysisResult | null
): string | null {
  const raw = assessment.decision_rationale;
  const summary = coverageAnalysis?.summary;
  const payout = assessment.payout_breakdown;

  if (summary && assessment.decision === "REJECT") {
    const finalPayout = payout?.final_payout ?? summary.total_payable;
    if (finalPayout === 0) {
      if (summary.total_covered_before_excess === 0) {
        return `No items are covered under the policy. Total claimed: ${formatCHF(summary.total_claimed)}.`;
      }
      const deductible = payout?.deductible ?? summary.excess_amount;
      if (deductible > 0 && summary.total_covered_before_excess <= deductible) {
        return `The covered amount (${formatCHF(summary.total_covered_before_excess)}) does not exceed the deductible (${formatCHF(deductible)}). Final payout: ${formatCHF(0)}.`;
      }
      if (summary.total_not_covered > 0) {
        return `${formatCHF(summary.total_not_covered)} of ${formatCHF(summary.total_claimed)} is not covered. After applying depreciation and deductible, no amount is payable.`;
      }
    }
  }

  if (summary && assessment.decision === "APPROVE") {
    const finalPayout = payout?.final_payout ?? summary.total_payable;
    if (finalPayout > 0) {
      return `Claim approved. Payout of ${formatCHF(finalPayout)} after depreciation and deductible.`;
    }
  }

  // Filter out raw internal strings
  if (raw && /^Hard fail on check/i.test(raw)) {
    return null;
  }

  return raw || null;
}

function DecisionBanner({
  assessment,
  coverageAnalysis,
}: {
  assessment: ClaimAssessment;
  coverageAnalysis: CoverageAnalysisResult | null;
}) {
  const config = DECISION_STYLES[assessment.decision];
  const Icon = config.icon;
  const rationale = buildRationale(assessment, coverageAnalysis);

  return (
    <div className={cn("rounded-lg border p-4", config.bg, config.border)}>
      <div className="flex items-start gap-4">
        <div className={cn("w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0", config.bg)}>
          <Icon className={cn("h-5 w-5", config.iconColor)} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <h2 className={cn("text-lg font-bold", config.text)}>
              {config.label}
            </h2>
            <span className="text-xs font-mono bg-muted px-2 py-0.5 rounded text-muted-foreground">
              Confidence: {formatConfidence(assessment.confidence_score)}
            </span>
          </div>
          {rationale && (
            <p className="text-sm text-foreground/80 mt-1 leading-relaxed">
              {rationale}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
