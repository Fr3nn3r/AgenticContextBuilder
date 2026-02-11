import { useState } from "react";
import { cn } from "../../lib/utils";
import {
  ChevronRight,
  AlertTriangle,
  Info,
} from "lucide-react";
import type {
  ConfidenceSummary,
  ComponentScore,
  ConfidenceBand,
} from "../../types";

// =============================================================================
// HUMAN-READABLE HELPERS
// =============================================================================

const COMPONENT_DESCRIPTIONS: Record<string, string> = {
  document_quality: "How reliably documents were read and classified",
  data_completeness: "Whether all critical claim information was found",
  consistency: "How well facts from different sources agree",
  coverage_reliability: "How confidently coverage was matched to the policy",
  decision_clarity: "How clear-cut the approval or denial decision was",
};

const BAND_EXPLANATIONS: Record<ConfidenceBand, string> = {
  high: "Strong supporting evidence across all dimensions",
  moderate: "Adequate evidence with some gaps or uncertainties",
  low: "Significant gaps or inconsistencies requiring manual review",
};

function qualitativeLabel(value: number): { text: string; className: string } {
  if (value >= 0.9) return { text: "Strong", className: "text-emerald-600 dark:text-emerald-400" };
  if (value >= 0.7) return { text: "Good", className: "text-emerald-500 dark:text-emerald-400" };
  if (value >= 0.5) return { text: "Fair", className: "text-amber-500 dark:text-amber-400" };
  return { text: "Weak", className: "text-rose-500 dark:text-rose-400" };
}

function scoreLabel(score: number): { text: string; className: string } {
  if (score >= 0.8) return { text: "Strong", className: "text-emerald-600 dark:text-emerald-400" };
  if (score >= 0.65) return { text: "Adequate", className: "text-amber-600 dark:text-amber-400" };
  return { text: "Needs review", className: "text-rose-500 dark:text-rose-400" };
}

// =============================================================================
// CCI COMPONENT BAR
// =============================================================================

function barColor(score: number): string {
  if (score >= 0.80) return "bg-emerald-500 dark:bg-emerald-400";
  if (score >= 0.65) return "bg-amber-500 dark:bg-amber-400";
  return "bg-rose-500 dark:bg-rose-400";
}

function ComponentBar({
  comp,
  onToggle,
  isOpen,
}: {
  comp: ComponentScore;
  onToggle: () => void;
  isOpen: boolean;
}) {
  const pct = Math.round(comp.score * 100);
  const label = comp.component.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  const description = COMPONENT_DESCRIPTIONS[comp.component];
  const sl = scoreLabel(comp.score);
  const hasDetail = comp.signals_used.length > 0 || comp.detail;

  return (
    <div>
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 py-1 hover:bg-muted/30 transition-colors rounded px-1 -mx-1"
      >
        <span className="text-xs text-muted-foreground w-40 text-left truncate flex-shrink-0">
          {label}
        </span>
        <div className="flex-1 h-2.5 bg-muted rounded-full overflow-hidden">
          <div
            className={cn("h-full rounded-full transition-all", barColor(comp.score))}
            style={{ width: `${pct}%` }}
          />
        </div>
        <span className={cn("text-xs font-medium w-16 text-right flex-shrink-0", sl.className)}>
          {sl.text}
        </span>
        <span className="text-xs tabular-nums font-medium w-10 text-right flex-shrink-0">
          {pct}%
        </span>
        {hasDetail && (
          <ChevronRight
            className={cn(
              "h-3 w-3 text-muted-foreground transition-transform flex-shrink-0",
              isOpen && "rotate-90"
            )}
          />
        )}
      </button>
      {isOpen && hasDetail && (
        <div className="ml-44 pl-3 border-l border-border mb-1 space-y-1">
          {/* Component description */}
          {description && (
            <p className="text-[11px] text-muted-foreground/70 italic">
              {description}
            </p>
          )}
          {/* Signals as qualitative rows */}
          {comp.signals_used.map((sig, idx) => {
            const q = qualitativeLabel(sig.normalized_value);
            const sigPct = Math.round(sig.normalized_value * 100);
            return (
              <div key={idx} className="flex items-center gap-2 text-[11px] text-muted-foreground">
                <span className="truncate flex-1">{sig.description || sig.signal_name}</span>
                <span className={cn("font-medium flex-shrink-0", q.className)}>
                  {q.text}
                </span>
                <span className="tabular-nums flex-shrink-0 w-8 text-right">
                  {sigPct}%
                </span>
              </div>
            );
          })}
          {comp.detail && <DataCompletenessDetail detail={comp.detail} />}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// DATA COMPLETENESS DETAIL
// =============================================================================

const IMPACT_STYLES: Record<string, string> = {
  HIGH: "bg-rose-100 text-rose-700 dark:bg-rose-900/20 dark:text-rose-300",
  MEDIUM: "bg-amber-100 text-amber-700 dark:bg-amber-900/20 dark:text-amber-300",
  LOW: "bg-muted text-muted-foreground",
};

function DataCompletenessDetail({
  detail,
}: {
  detail: NonNullable<ComponentScore["detail"]>;
}) {
  const missingFacts = detail.missing_critical_facts ?? [];
  const gaps = detail.data_gaps ?? [];
  const total = detail.critical_facts_total;
  const present = detail.critical_facts_present;

  if (missingFacts.length === 0 && gaps.length === 0) return null;

  return (
    <div className="mt-1 space-y-1.5">
      {missingFacts.length > 0 && (
        <div>
          <span className="text-[11px] text-muted-foreground">
            {missingFacts.length} of {total ?? "?"} critical facts missing
            {present != null && total != null && ` (${present} present)`}
          </span>
          <div className="flex flex-wrap gap-1 mt-0.5">
            {missingFacts.map((fact) => (
              <span
                key={fact}
                className="text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 dark:bg-amber-900/20 dark:text-amber-300"
              >
                {fact}
              </span>
            ))}
          </div>
        </div>
      )}
      {gaps.length > 0 && (
        <div>
          <span className="text-[11px] text-muted-foreground">
            {gaps.length} assessment data gap{gaps.length !== 1 ? "s" : ""}
          </span>
          <div className="space-y-0.5 mt-0.5">
            {gaps.map((gap, idx) => (
              <div key={idx} className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                <span className="truncate">{gap.field}</span>
                <span
                  className={cn(
                    "text-[10px] px-1 py-0 rounded uppercase",
                    IMPACT_STYLES[gap.impact.toUpperCase()] ?? IMPACT_STYLES.LOW
                  )}
                >
                  {gap.impact}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// CCI SUMMARY CARD
// =============================================================================

const BAND_STYLES: Record<ConfidenceBand, string> = {
  high: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300",
  moderate: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
  low: "bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300",
};

export function CCISummaryCard({ summary }: { summary: ConfidenceSummary }) {
  const [openComp, setOpenComp] = useState<string | null>(null);
  const pct = Math.round(summary.composite_score * 100);

  return (
    <div className="bg-card border border-border rounded-lg p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-foreground">Composite Confidence Index</span>
          <span
            className={cn(
              "text-[10px] px-1.5 py-0.5 rounded-full font-semibold uppercase tracking-wide",
              BAND_STYLES[summary.band]
            )}
          >
            {summary.band}
          </span>
        </div>
        <span className="text-lg font-bold tabular-nums text-foreground">{pct}%</span>
      </div>

      {/* Human-readable explanation */}
      <p className="text-xs text-muted-foreground leading-relaxed">
        {BAND_EXPLANATIONS[summary.band]}. This score reflects how much evidence
        supports the claim decision across document quality, data completeness,
        source consistency, coverage matching, and decision clarity.
      </p>

      {/* Component bars */}
      <div className="space-y-0.5">
        {summary.component_scores.map((comp) => (
          <ComponentBar
            key={comp.component}
            comp={comp}
            isOpen={openComp === comp.component}
            onToggle={() =>
              setOpenComp((prev) => (prev === comp.component ? null : comp.component))
            }
          />
        ))}
      </div>

      {/* Flags / warnings */}
      {summary.flags.length > 0 && (
        <div className="flex flex-wrap gap-1.5 pt-1">
          {summary.flags.map((flag, idx) => (
            <span
              key={idx}
              className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 dark:bg-amber-900/20 dark:text-amber-300"
            >
              <AlertTriangle className="h-2.5 w-2.5" />
              {flag}
            </span>
          ))}
        </div>
      )}

      {/* Missing stages */}
      {summary.stages_missing.length > 0 && (
        <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
          <Info className="h-3 w-3 flex-shrink-0" />
          <span>Missing stages: {summary.stages_missing.join(", ")}</span>
        </div>
      )}
    </div>
  );
}
