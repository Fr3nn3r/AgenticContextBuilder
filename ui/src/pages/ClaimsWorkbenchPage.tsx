import { useState, useEffect, useCallback, useMemo, Fragment } from "react";
import { cn } from "../lib/utils";
import { formatEventDate } from "../lib/formatters";
import {
  CheckCircle2,
  XCircle,
  ArrowRightCircle,
  AlertTriangle,
  Wrench,
  ExternalLink,
  RefreshCw,
  Loader2,
  Search,
  ChevronDown,
  ChevronRight,
  Copy,
  Check,
  RotateCcw,
  Pencil,
  FileText,
} from "lucide-react";
import {
  getDashboardClaims,
  listDocs,
  getWorkbenchData,
  evaluateDecision,
} from "../api/client";
import {
  PageLoadingSkeleton,
  NoDataEmptyState,
  ErrorEmptyState,
} from "../components/shared";
import { DocumentSlidePanel } from "../components/ClaimExplorer/DocumentSlidePanel";
import type { EvidenceLocation } from "../components/ClaimExplorer/DocumentSlidePanel";
import type { DashboardClaim, DocSummary } from "../types";
import { ConfidenceBadge } from "../components/ClaimsWorkbench/ConfidenceBadge";
import { DecisionTraceTab } from "../components/ClaimsWorkbench/DecisionTraceTab";
import { GroundTruthTab } from "../components/ClaimsWorkbench/GroundTruthTab";
import { CCISummaryCard } from "../components/ClaimsWorkbench/CCISummaryCard";
import { NotesTab } from "../components/ClaimsWorkbench/NotesTab";

// =============================================================================
// HELPERS
// =============================================================================

function getFact(facts: any, name: string): any | null {
  if (!facts?.facts) return null;
  return facts.facts.find((f: any) => f.name === name) ?? null;
}

function getFactValue(facts: any, name: string): string | null {
  const fact = getFact(facts, name);
  return fact?.value ?? fact?.normalized_value ?? null;
}

function fmt(n: number | null | undefined, decimals = 2): string {
  if (n == null) return "-";
  return n.toLocaleString("de-CH", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function pct(n: number | null | undefined): string {
  if (n == null) return "-";
  return `${fmt(n, 1)}%`;
}

function formatCHF(value: number, currency = "CHF"): string {
  return new Intl.NumberFormat("de-CH", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function componentLabel(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}


/** Convert clause data into a human-readable YES/NO question.
 *  Looks up the proper question from the assumptions_used map first,
 *  then falls back to assumption_question on the clause definition,
 *  then builds a natural-sounding question from the short name. */
function clauseToQuestion(
  clause: any,
  assumptionQuestions?: Record<string, string>
): string {
  const ref = clause.clause_reference;
  // 1. Best source: the question stored in assumptions_used (from engine)
  if (assumptionQuestions?.[ref]) {
    const q = assumptionQuestions[ref].trim();
    return q.endsWith("?") ? q : q + "?";
  }
  // 2. assumption_question on the clause definition (from registry)
  if (clause.assumption_question) {
    const q = clause.assumption_question.trim();
    return q.endsWith("?") ? q : q + "?";
  }
  // 3. Fallback: build from short name
  const name = clause.clause_short_name || ref;
  if (name.endsWith("?")) return name;
  return `Does "${name}" apply to this claim?`;
}

// =============================================================================
// TYPES & CONFIG
// =============================================================================

type TabId = "costs" | "coverage-checks" | "documents" | "decisions" | "confidence" | "ground-truth" | "notes";
type ClaimVerdict = "APPROVE" | "DENY" | "REFER";

const VERDICT_CONFIG: Record<
  ClaimVerdict,
  {
    icon: typeof CheckCircle2;
    label: string;
    description: string;
    iconBg: string;
    textColor: string;
    borderColor: string;
    gradient: string;
    accentBar: string;
  }
> = {
  APPROVE: {
    icon: CheckCircle2,
    label: "Approved",
    description: "Claim approved for payment",
    iconBg: "bg-success/20",
    textColor: "text-success",
    borderColor: "border-success/30",
    gradient: "gradient-success",
    accentBar: "bg-success",
  },
  DENY: {
    icon: XCircle,
    label: "Denied",
    description: "Claim has been denied",
    iconBg: "bg-destructive/20",
    textColor: "text-destructive",
    borderColor: "border-destructive/30",
    gradient: "gradient-destructive",
    accentBar: "bg-destructive",
  },
  REFER: {
    icon: ArrowRightCircle,
    label: "Referred",
    description: "Claim requires manual review",
    iconBg: "bg-warning/20",
    textColor: "text-warning",
    borderColor: "border-warning/30",
    gradient: "gradient-warning",
    accentBar: "bg-warning",
  },
};

// =============================================================================
// BADGES
// =============================================================================

function VerdictBadge({ verdict }: { verdict: string | null }) {
  if (!verdict) return <span className="text-muted-foreground text-xs">-</span>;
  const v = verdict.toUpperCase();
  const color =
    v === "APPROVE"
      ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300"
      : v === "DENY"
        ? "bg-rose-50 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300"
        : "bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300";
  const label =
    v === "APPROVE" ? "APPROVE" : v === "DENY" ? "DENY" : "REFER";
  return (
    <span
      className={cn(
        "inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium",
        color
      )}
    >
      {label}
    </span>
  );
}

// =============================================================================
// FACT FIELD (clickable for evidence)
// =============================================================================

function FactField({
  label,
  value,
  source,
  onViewSource,
}: {
  label: string;
  value: string | null;
  source?: {
    doc_id: string;
    page?: number;
    char_start?: number;
    char_end?: number;
    text_quote?: string;
  } | null;
  onViewSource?: (evidence: EvidenceLocation) => void;
}) {
  if (!value) return null;

  const hasSource = source?.doc_id;

  const handleClick = () => {
    if (hasSource && onViewSource) {
      onViewSource({
        docId: source!.doc_id,
        page: source!.page ?? null,
        charStart: source!.char_start ?? null,
        charEnd: source!.char_end ?? null,
        highlightText: source!.text_quote,
        highlightValue: value,
      });
    }
  };

  return (
    <div className="text-sm">
      <span className="text-muted-foreground">{label}:</span>{" "}
      {hasSource ? (
        <button
          onClick={handleClick}
          className="text-foreground font-medium hover:text-primary hover:underline transition-colors inline-flex items-center gap-1 group"
          title="View source document"
        >
          {value}
          <ExternalLink className="h-3 w-3 opacity-0 group-hover:opacity-100 text-primary transition-opacity" />
        </button>
      ) : (
        <span className="text-foreground font-medium">{value}</span>
      )}
    </div>
  );
}

// =============================================================================
// DECISION BANNER (styled like Assessment tab)
// =============================================================================

function DecisionBanner({ data, claimId }: { data: any; claimId: string }) {
  const dossier = data.dossier;
  const verdict = (dossier?.claim_verdict?.toUpperCase() ?? "REFER") as ClaimVerdict;
  const config = VERDICT_CONFIG[verdict] || VERDICT_CONFIG.REFER;
  const VerdictIcon = config.icon;
  const cci = data.dossier?.confidence_index;
  const rawConf = cci?.composite_score ?? data.assessment?.confidence_score ?? null;
  const confidence = rawConf != null ? (rawConf <= 1 ? Math.round(rawConf * 100) : rawConf) : null;
  const cciBand = cci?.band ?? null;
  const isDenied = verdict === "DENY";

  // Build reason text — strip redundant "Claim approved/denied." prefix
  const stripVerdictPrefix = (s: string) =>
    s.replace(/^Claim\s+(approved|denied)\.?\s*/i, "");

  let reason = config.description;
  if (isDenied) {
    const clauseEvals: any[] = dossier?.clause_evaluations ?? [];
    const failedEvals = clauseEvals.filter(
      (c: any) => c.verdict?.toUpperCase() === "FAIL"
    );
    if (dossier?.verdict_reason) {
      reason = stripVerdictPrefix(dossier.verdict_reason);
    } else if (failedEvals.length > 0) {
      const explanations = failedEvals.map((c: any) => {
        const name = c.clause_short_name || c.clause_reference;
        const detail = c.reason ? `: ${c.reason}` : "";
        return `${name} (${c.clause_reference})${detail}`;
      });
      reason = explanations.join(". ") + ".";
    }
  } else if (dossier?.verdict_reason) {
    reason = stripVerdictPrefix(dossier.verdict_reason);
  }

  // For non-denied claims
  const primaryRepair = data.coverage?.primary_repair;
  const currency = getFactValue(data.facts, "currency") || "CHF";

  const bannerPayout = useMemo(
    () => isDenied ? 0 : (data.assessment?.payout?.final_payout ?? data.screening?.payout?.final_payout ?? 0),
    [data, isDenied]
  );

  return (
    <div
      className={cn(
        "rounded-lg border overflow-hidden shadow-sm relative",
        config.borderColor
      )}
    >
      <div
        className={cn("absolute left-0 top-0 bottom-0 w-1", config.accentBar)}
      />
      <div className={cn("p-6 pl-5", config.gradient)}>
        <div className="flex items-start gap-4">
          <div
            className={cn(
              "w-12 h-12 rounded-full flex items-center justify-center flex-shrink-0",
              config.iconBg
            )}
          >
            <VerdictIcon className={cn("h-7 w-7", config.textColor)} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-baseline gap-3">
              <h2 className={cn("text-xl font-bold", config.textColor)}>
                {config.label}
              </h2>
              <span className="text-lg font-semibold tabular-nums tracking-wide text-foreground/90 font-mono">
                #{claimId}
              </span>
            </div>
            <p className="text-sm text-muted-foreground mt-1">{reason}</p>
          </div>
          {confidence != null && (
            <div className="text-right flex-shrink-0">
              <div className="text-xs text-muted-foreground mb-0.5">Confidence</div>
              <ConfidenceBadge score={rawConf} band={cciBand} />
            </div>
          )}
        </div>
      </div>

      {isDenied ? (
        <div className="px-6 py-4 border-t border-border bg-muted/30">
          <div className="text-xs text-muted-foreground uppercase tracking-wide mb-2">
            Denial Clauses
          </div>
          <div className="space-y-2">
            {(dossier?.clause_evaluations ?? [])
              .filter((c: any) => c.verdict?.toUpperCase() === "FAIL")
              .map((clause: any, idx: number) => (
                <div key={idx} className="flex items-start gap-2">
                  <XCircle className="h-4 w-4 text-destructive flex-shrink-0 mt-0.5" />
                  <div>
                    <span className="text-sm font-medium text-foreground">
                      {clause.clause_short_name || clause.clause_reference}
                    </span>
                    <span className="text-xs text-muted-foreground ml-2">
                      {clause.clause_reference}
                    </span>
                    {clause.reason && (
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {clause.reason}
                      </p>
                    )}
                  </div>
                </div>
              ))}
          </div>
        </div>
      ) : (
        <div className="px-6 py-4 border-t border-border bg-muted/30">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-2 min-w-0">
              <Wrench className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />
              {primaryRepair?.component ? (
                <span className="text-sm font-medium text-foreground truncate">
                  {componentLabel(primaryRepair.component)}
                </span>
              ) : (
                <span className="text-sm text-muted-foreground">No primary repair</span>
              )}
              {primaryRepair?.component && (
                <span
                  className={cn(
                    "text-[10px] px-1.5 py-0.5 rounded-full font-medium flex-shrink-0",
                    primaryRepair.is_covered
                      ? "bg-success/15 text-success"
                      : "bg-destructive/15 text-destructive"
                  )}
                >
                  {primaryRepair.is_covered ? "Covered" : "Not Covered"}
                </span>
              )}
            </div>
            <div className="text-right flex-shrink-0">
              <span className="text-xs text-muted-foreground mr-2">Payout</span>
              <span className="text-sm font-semibold text-foreground">
                {bannerPayout > 0 ? formatCHF(bannerPayout, currency) : "Pending"}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// TAB: COST BREAKDOWN
// =============================================================================

function CostBreakdownTab({
  data,
  coverageOverrides,
  setCoverageOverrides,
  documents,
  onViewDocument,
}: {
  data: any;
  coverageOverrides: Record<string, boolean>;
  setCoverageOverrides: React.Dispatch<React.SetStateAction<Record<string, boolean>>>;
  documents?: DocSummary[];
  onViewDocument?: (evidence: EvidenceLocation) => void;
}) {
  const lineItems: any[] = data.coverage?.line_items ?? [];
  const summary = data.coverage?.summary;
  const dossier = data.dossier;
  const verdict = (dossier?.claim_verdict ?? "").toUpperCase();
  const isDenied = verdict === "DENY";
  const sp = data.screening?.payout;
  const coveragePct: number | null = summary?.coverage_percent ?? data.coverage?.inputs?.coverage_percent ?? null;
  const vehicleKm = getFactValue(data.facts, "vehicle_km") || data.coverage?.inputs?.vehicle_km;

  const [expandedTypes, setExpandedTypes] = useState<Set<string>>(new Set());
  const toggleType = (type: string) =>
    setExpandedTypes((prev) => {
      const next = new Set(prev);
      next.has(type) ? next.delete(type) : next.add(type);
      return next;
    });
  const [expandedItem, setExpandedItem] = useState<string | null>(null);
  const toggleItem = (key: string) =>
    setExpandedItem((prev) => (prev === key ? null : key));

  const hasOverrides = Object.keys(coverageOverrides).length > 0;

  const toggleCoverageOverride = (itemKey: string, currentlyCovered: boolean) => {
    setCoverageOverrides(prev => {
      const next = { ...prev };
      if (itemKey in next) {
        delete next[itemKey];
      } else {
        next[itemKey] = !currentlyCovered;
      }
      return next;
    });
  };

  /** Returns the effective covered amount for an item, ALREADY adjusted by coveragePct. */
  const getEffectiveCovered = (item: any, itemKey: string): number => {
    if (isDenied) return 0;
    const originalCovered = item.coverage_status === "covered";
    const isOverridden = itemKey in coverageOverrides;
    const effectivelyCovered = isOverridden ? coverageOverrides[itemKey] : originalCovered;
    if (!effectivelyCovered) return 0;
    if (originalCovered) return parseFloat(item.covered_amount || 0);
    const price = parseFloat(item.total_price || 0);
    return coveragePct != null ? price * (coveragePct / 100) : price;
  };

  if (lineItems.length === 0) return <NoDataEmptyState />;

  // Find first cost estimate document (if any)
  const costEstimateDoc = documents?.find((d) => d.doc_type === "cost_estimate");

  // Aggregate by item type (use flat index for override keys to match engine item_ids)
  const typeOrder = ["parts", "labor", "fee", "other"];
  const byType: Record<string, { claimed: number; subtotal: number; covered: number; items: any[] }> = {};
  let flatIdx = 0;
  for (const item of lineItems) {
    const type = item.item_type === "fees" ? "fee" : (item.item_type || "other");
    if (!byType[type]) byType[type] = { claimed: 0, subtotal: 0, covered: 0, items: [] };
    const key = `item_${flatIdx}`;
    flatIdx++;
    const price = parseFloat(item.total_price || 0);
    const covAmt = getEffectiveCovered(item, key);
    byType[type].claimed += price;
    byType[type].subtotal += covAmt > 0 ? price : 0;
    byType[type].covered += covAmt;
    byType[type].items.push({ ...item, _key: key });
  }

  const rows = typeOrder.filter((t) => byType[t]);
  const totalClaimed = Object.values(byType).reduce((s, v) => s + v.claimed, 0);
  const totalSubtotal = Object.values(byType).reduce((s, v) => s + v.subtotal, 0);
  const totalCovered = isDenied ? 0 : Object.values(byType).reduce((s, v) => s + v.covered, 0);
  const vatRate = sp?.vat_rate_pct ?? 0;
  const maxCoverage: number | null = sp?.max_coverage ?? null;
  let afterCap: number;
  let capApplied: boolean;
  let vatAmount: number;
  let excess: number;
  let payable: number;
  if (hasOverrides && !isDenied) {
    // totalCovered is already rate-adjusted per item (getEffectiveCovered applies
    // coveragePct for overridden items; backend covered_amount is pre-adjusted).
    // Do NOT apply coveragePct again here — that would double-count the rate.
    capApplied = maxCoverage != null && totalCovered > maxCoverage;
    afterCap = capApplied ? maxCoverage! : totalCovered;
    // When cap is applied, it is the VAT-inclusive ceiling — no VAT on top.
    // Matches screener._calculate_payout() logic (see DEEP-EVAL claim 65056).
    vatAmount = capApplied ? 0 : afterCap * (vatRate / 100);
    const subtotalWithVat = afterCap + vatAmount;
    const deductPct = sp?.deductible_percent ?? 0;
    const deductMin = sp?.deductible_minimum ?? 0;
    excess = subtotalWithVat > 0 ? Math.max(subtotalWithVat * (deductPct / 100), deductMin) : 0;
    payable = Math.max(0, subtotalWithVat - excess);
  } else {
    capApplied = sp?.max_coverage_applied ?? false;
    afterCap = sp?.capped_amount ?? totalCovered;
    vatAmount = sp?.vat_amount ?? 0;
    excess = isDenied ? 0 : (sp?.deductible_amount ?? 0);
    payable = isDenied ? 0 : (sp?.final_payout ?? 0);
  }

  const typeLabel: Record<string, string> = {
    parts: "Parts",
    labor: "Labor",
    fee: "Fees",
    other: "Other",
  };

  return (
    <div className="space-y-4">
      {/* Cost summary table */}
      <div className="bg-card border border-border rounded-lg overflow-hidden">
        <table className="w-full text-sm table-fixed">
          <colgroup>
            <col className="w-7" />
            <col />
            <col className="w-28" />
            <col className="w-28" />
            <col className="w-28" />
          </colgroup>
          <thead>
            <tr className="border-b border-border bg-muted/50 text-xs text-muted-foreground">
              <th />
              <th className="px-3 py-2 text-left font-medium" />
              <th className="px-3 py-2 text-right font-medium">Claimed</th>
              <th className="px-3 py-2 text-right font-medium">Subtotal</th>
              <th className="px-3 py-2 text-right font-medium">Covered</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((type, typeIdx) => {
              const isOpen = expandedTypes.has(type);
              const group = byType[type];
              const bandBg = typeIdx % 2 === 0 ? "bg-black/[0.025] dark:bg-white/[0.04]" : "";
              return (
                <Fragment key={type}>
                  <tr
                    className={cn(
                      "border-b border-border cursor-pointer select-none hover:bg-muted/30 transition-colors",
                      bandBg
                    )}
                    onClick={() => toggleType(type)}
                  >
                    <td className="pl-2.5 py-2 text-muted-foreground">
                      <ChevronRight className={cn(
                        "h-3.5 w-3.5 transition-transform duration-150",
                        isOpen && "rotate-90"
                      )} />
                    </td>
                    <td className="px-3 py-2 text-[13px] text-foreground font-medium">
                      {typeLabel[type] || type}
                      <span className="ml-1.5 text-[11px] text-muted-foreground font-normal">
                        ({group.items.length})
                      </span>
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-[13px] text-muted-foreground">
                      {fmt(group.claimed)}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-[13px] text-muted-foreground">
                      {fmt(group.subtotal)}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-[13px] font-semibold text-foreground">
                      {fmt(group.covered)}
                    </td>
                  </tr>
                  {isOpen &&
                    group.items.map((item: any) => {
                      const originalCovered = item.coverage_status === "covered";
                      const originalDenied = item.coverage_status === "not_covered" || item.coverage_status === "denied";
                      const itemKey = item._key as string;
                      const isOverridden = itemKey in coverageOverrides;
                      const effectivelyCovered = isOverridden ? coverageOverrides[itemKey] : originalCovered;
                      const effectivelyDenied = isOverridden ? !coverageOverrides[itemKey] : originalDenied;
                      const coveredAmt = getEffectiveCovered(item, itemKey);
                      const isItemOpen = expandedItem === itemKey;
                      const hasReason = item.match_reasoning || item.exclusion_reason || item.matched_component;
                      return (
                        <Fragment key={itemKey}>
                          <tr
                            className={cn(
                              "border-b border-border text-xs",
                              bandBg,
                              isOverridden && "bg-primary/[0.03] dark:bg-primary/[0.06]",
                              hasReason && "cursor-pointer hover:bg-black/[0.015] dark:hover:bg-white/[0.02]"
                            )}
                            onClick={() => hasReason && toggleItem(itemKey)}
                          >
                            <td />
                            <td className="pl-8 pr-3 py-1.5 overflow-hidden">
                              <div className="flex items-center gap-2 min-w-0">
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    toggleCoverageOverride(itemKey, effectivelyCovered);
                                  }}
                                  className="group/dot p-1 -m-1 shrink-0"
                                  title={isOverridden ? "Click to reset override" : "Click to toggle coverage"}
                                >
                                  <span
                                    className={cn(
                                      "block h-2 w-2 rounded-full transition-all",
                                      effectivelyCovered
                                        ? "bg-success"
                                        : effectivelyDenied
                                          ? "bg-destructive"
                                          : "bg-warning",
                                      isOverridden && "ring-[3px] ring-offset-1 ring-primary/60",
                                      "group-hover/dot:ring-2 group-hover/dot:ring-offset-1 group-hover/dot:ring-primary/40"
                                    )}
                                  />
                                </button>
                                <span className={cn("truncate", isOverridden ? "text-foreground" : "text-muted-foreground")}>
                                  {item.description || "-"}
                                </span>
                                {item.item_code && (
                                  <span className="shrink-0 font-mono text-[10px] text-muted-foreground/50">
                                    {item.item_code}
                                  </span>
                                )}
                                {isOverridden && (
                                  <span className="shrink-0 inline-flex items-center gap-0.5 bg-primary/10 text-primary px-1.5 py-0.5 rounded text-[10px] font-semibold">
                                    <Pencil className="h-2.5 w-2.5" />
                                    Override
                                  </span>
                                )}
                              </div>
                            </td>
                            <td className="px-3 py-1.5 text-right tabular-nums text-muted-foreground">
                              {fmt(parseFloat(item.total_price || 0))}
                            </td>
                            <td className={cn(
                              "px-3 py-1.5 text-right tabular-nums",
                              coveredAmt > 0 ? "text-muted-foreground" : "text-muted-foreground/50"
                            )}>
                              {coveredAmt > 0 ? fmt(parseFloat(item.total_price || 0)) : "-"}
                            </td>
                            <td className={cn(
                              "px-3 py-1.5 text-right tabular-nums",
                              coveredAmt > 0 ? "text-foreground" : "text-muted-foreground/50"
                            )}>
                              {fmt(coveredAmt)}
                            </td>
                          </tr>
                          {isItemOpen && hasReason && (
                            <tr className={cn("border-b border-border", bandBg)}>
                              <td />
                              <td colSpan={4} className="pl-12 pr-4 py-2">
                                <div className="text-xs space-y-1 text-muted-foreground">
                                  {item.match_reasoning && (
                                    <p>{item.match_reasoning}</p>
                                  )}
                                  {item.exclusion_reason && (
                                    <p>
                                      <span className="font-medium text-destructive">Exclusion:</span>{" "}
                                      {item.exclusion_reason.replace(/_/g, " ")}
                                    </p>
                                  )}
                                  {(item.matched_component || item.coverage_category) && (
                                    <p className="text-muted-foreground/70">
                                      {item.matched_component && (
                                        <span>Component: {item.matched_component}</span>
                                      )}
                                      {item.matched_component && item.coverage_category && " · "}
                                      {item.coverage_category && (
                                        <span>Category: {item.coverage_category}</span>
                                      )}
                                      {item.match_method && (
                                        <span> · Match: {item.match_method}</span>
                                      )}
                                      {item.match_confidence != null && (
                                        <span> ({Math.round(item.match_confidence * 100)}%)</span>
                                      )}
                                    </p>
                                  )}
                                </div>
                              </td>
                            </tr>
                          )}
                        </Fragment>
                      );
                    })}
                </Fragment>
              );
            })}
            <tr className="border-t-2 border-border bg-muted/30">
              <td />
              <td className="px-3 py-2.5 text-[14px] font-bold text-foreground">Total</td>
              <td className="px-3 py-2.5 text-right tabular-nums text-[14px] font-bold text-muted-foreground">
                {fmt(totalClaimed)}
              </td>
              <td className="px-3 py-2.5 text-right tabular-nums text-[14px] font-bold text-muted-foreground">
                {fmt(totalSubtotal)}
              </td>
              <td className="px-3 py-2.5 text-right tabular-nums text-[14px] font-bold text-foreground">
                {fmt(totalCovered)}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* Payout summary (only if not denied) */}
      {!isDenied && (
        <div className={cn(
          "bg-card border rounded-lg p-3 max-w-xs ml-auto",
          hasOverrides ? "border-primary/40" : "border-border"
        )}>
          {hasOverrides && (
            <div className="flex items-center justify-between mb-2 pb-2 border-b border-primary/20">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-primary">
                What-if ({Object.keys(coverageOverrides).length} override{Object.keys(coverageOverrides).length !== 1 ? "s" : ""})
              </span>
              <button
                onClick={() => setCoverageOverrides({})}
                className="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground transition-colors"
              >
                <RotateCcw className="h-3 w-3" />
                Reset
              </button>
            </div>
          )}
          <div className="grid grid-cols-[1fr_auto] gap-x-6 gap-y-1 text-xs">
            {coveragePct != null && (
              <>
                <span className="text-muted-foreground">
                  Coverage rate{vehicleKm ? ` (${Number(vehicleKm).toLocaleString("de-CH")} km)` : ""}
                </span>
                <span className="text-right tabular-nums font-medium">{fmt(coveragePct, 0)}%</span>
              </>
            )}
            <span className="text-muted-foreground">Net (covered)</span>
            <span className="text-right tabular-nums">{fmt(totalCovered)}</span>
            {capApplied && maxCoverage != null && (
              <>
                <span className="text-muted-foreground">
                  Max coverage cap
                </span>
                <span className="text-right tabular-nums font-medium">
                  {fmt(maxCoverage)}
                </span>
              </>
            )}
            {vatRate > 0 && (
              <>
                <span className="text-muted-foreground">
                  VAT ({pct(vatRate)})
                </span>
                <span className="text-right tabular-nums">
                  {fmt(vatAmount)}
                </span>
              </>
            )}
            <span className="text-muted-foreground">
              Deductible
              {sp?.deductible_percent ? ` (${sp.deductible_percent}%` : ""}
              {sp?.deductible_minimum ? `, min ${sp.deductible_minimum}` : ""}
              {sp?.deductible_percent ? ")" : ""}
            </span>
            <span className="text-right tabular-nums">-{fmt(excess)}</span>
            <span className="text-sm font-bold text-foreground border-t border-border pt-1.5 mt-1">
              Payable
            </span>
            <span className="text-sm font-bold text-foreground text-right tabular-nums border-t border-border pt-1.5 mt-1">
              {fmt(payable)}
            </span>
          </div>
        </div>
      )}
      {costEstimateDoc && onViewDocument && (
        <div className="mt-3">
          <button
            onClick={() =>
              onViewDocument({
                docId: costEstimateDoc.doc_id,
                page: 1,
                charStart: null,
                charEnd: null,
              })
            }
            className="inline-flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-primary hover:text-primary/80 border border-primary/30 hover:border-primary/50 rounded-md transition-colors"
          >
            <FileText className="h-4 w-4" />
            View Cost Estimate
          </button>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// TAB: COVERAGE CHECKS (unified)
// =============================================================================

function CoverageChecksTab({
  data,
  assumptions,
  onToggle,
  onReEvaluate,
  evaluating,
}: {
  data: any;
  assumptions: Record<string, boolean>;
  onToggle: (clauseRef: string, value: boolean) => void;
  onReEvaluate: () => void;
  evaluating: boolean;
}) {
  const clauseEvals: any[] = data.dossier?.clause_evaluations ?? [];
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({
    "needs-review": true,
    "issues": true,
    "verified": false,
  });
  const [expandedItem, setExpandedItem] = useState<string | null>(null);
  const toggleItem = (key: string) =>
    setExpandedItem((prev) => (prev === key ? null : key));

  // Build lookup from assumptions_used (which has proper question text)
  const assumptionQuestions = useMemo(() => {
    const map: Record<string, string> = {};
    for (const a of data.dossier?.assumptions_used ?? []) {
      if (a.clause_reference && a.question) {
        map[a.clause_reference] = a.question;
      }
    }
    return map;
  }, [data]);

  // Route clauses into 3 buckets
  const { needsReview, issues, verified } = useMemo(() => {
    const nr: any[] = [];
    const iss: any[] = [];
    const ver: any[] = [];
    for (const clause of clauseEvals) {
      if (clause.assumption_used != null) {
        nr.push(clause);
      } else if (clause.verdict?.toUpperCase() === "FAIL") {
        iss.push(clause);
      } else {
        ver.push(clause);
      }
    }
    return { needsReview: nr, issues: iss, verified: ver };
  }, [clauseEvals]);

  const toggleSection = (key: string) =>
    setOpenSections((prev) => ({ ...prev, [key]: !prev[key] }));

  if (clauseEvals.length === 0) return <NoDataEmptyState />;

  return (
    <div className="space-y-4">
      {/* Section: Assumptions (amber) */}
      {needsReview.length > 0 && (
        <div className="border border-amber-200 dark:border-amber-800 rounded-lg overflow-hidden">
          <div
            onClick={() => toggleSection("needs-review")}
            className="w-full flex items-center justify-between px-4 py-3 bg-amber-50/50 dark:bg-amber-950/20 hover:bg-amber-50 dark:hover:bg-amber-950/30 transition-colors cursor-pointer select-none"
          >
            <span className="flex items-center gap-2">
              {openSections["needs-review"] ? (
                <ChevronDown className="h-4 w-4 text-amber-600 dark:text-amber-400" />
              ) : (
                <ChevronRight className="h-4 w-4 text-amber-600 dark:text-amber-400" />
              )}
              <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400" />
              <span className="text-sm font-medium text-amber-800 dark:text-amber-300">
                Assumptions
              </span>
            </span>
            <span className="flex items-center gap-2">
              {data.dossier?.version != null && (
                <span className="text-xs text-muted-foreground/60 tabular-nums">
                  v{data.dossier.version}
                </span>
              )}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onReEvaluate();
                }}
                disabled={evaluating}
                className={cn(
                  "px-3 py-1 text-xs font-medium rounded-md transition-colors",
                  evaluating
                    ? "bg-muted text-muted-foreground cursor-not-allowed"
                    : "bg-primary text-primary-foreground hover:bg-primary/90"
                )}
              >
                {evaluating ? "Re-evaluating..." : "Re-evaluate"}
              </button>
            </span>
          </div>
          {openSections["needs-review"] && (
            <div className="px-4 py-3 space-y-2 border-t border-amber-200 dark:border-amber-800">
              {needsReview.map((clause: any) => {
                const ref = clause.clause_reference;
                const currentValue = assumptions[ref] ?? clause.assumption_used;
                const question = clauseToQuestion(clause, assumptionQuestions);
                const detail = clause.reason?.replace(/\s*\(assumed\)\.?/gi, "").trim() || null;
                return (
                  <div key={ref} className="group/arow flex items-center justify-between gap-3">
                    <span className="flex-1 min-w-0 text-sm text-foreground flex items-center gap-1">
                      <span className="font-mono text-xs text-muted-foreground mr-1.5 flex-shrink-0">{ref}</span>
                      <span className="truncate">{question}</span>
                      {detail && (
                        <span className="text-xs text-muted-foreground/60 truncate opacity-0 group-hover/arow:opacity-100 transition-opacity duration-150 flex-shrink-0">
                          -- {detail}
                        </span>
                      )}
                    </span>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <button
                        onClick={() => onToggle(ref, true)}
                        className={cn(
                          "px-3 py-1 text-xs rounded-md font-medium transition-colors",
                          currentValue === true
                            ? "bg-green-600 text-white"
                            : "bg-muted text-muted-foreground hover:bg-muted/80"
                        )}
                      >
                        YES
                      </button>
                      <button
                        onClick={() => onToggle(ref, false)}
                        className={cn(
                          "px-3 py-1 text-xs rounded-md font-medium transition-colors",
                          currentValue === false
                            ? "bg-red-600 text-white"
                            : "bg-muted text-muted-foreground hover:bg-muted/80"
                        )}
                      >
                        NO
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Section: Clauses Invoked (red) */}
      {issues.length > 0 && (
        <div className="border border-red-200 dark:border-red-800 rounded-lg overflow-hidden">
          <button
            onClick={() => toggleSection("issues")}
            className="w-full flex items-center gap-2 px-4 py-3 bg-red-50/50 dark:bg-red-950/20 hover:bg-red-50 dark:hover:bg-red-950/30 transition-colors"
          >
            {openSections["issues"] ? (
              <ChevronDown className="h-4 w-4 text-red-600 dark:text-red-400" />
            ) : (
              <ChevronRight className="h-4 w-4 text-red-600 dark:text-red-400" />
            )}
            <XCircle className="h-4 w-4 text-red-600 dark:text-red-400" />
            <span className="text-sm font-medium text-red-800 dark:text-red-300">
              Clauses Invoked ({issues.length})
            </span>
          </button>
          {openSections["issues"] && (
            <div className="px-4 py-3 space-y-1 border-t border-red-200 dark:border-red-800">
              {issues.map((clause: any, idx: number) => {
                const iKey = `i-${clause.clause_reference || idx}`;
                const hasDetail = clause.reason || clause.evidence?.length > 0 || clause.affected_line_items?.length > 0;
                return (
                  <div key={idx} className="group/irow">
                    <button
                      onClick={() => hasDetail && toggleItem(iKey)}
                      className={cn(
                        "flex items-center gap-2 py-0.5 w-full text-left",
                        hasDetail && "cursor-pointer"
                      )}
                    >
                      <XCircle className="h-3.5 w-3.5 text-destructive flex-shrink-0" />
                      <span className="text-sm text-foreground whitespace-nowrap">
                        <span className="font-mono text-xs text-muted-foreground mr-1.5">{clause.clause_reference}</span>
                        {clause.clause_short_name || clause.clause_reference}
                      </span>
                      {clause.reason && (
                        <span className="text-xs text-muted-foreground/60 truncate opacity-0 group-hover/irow:opacity-100 transition-opacity duration-150">
                          -- {clause.reason}
                        </span>
                      )}
                    </button>
                    {hasDetail && (
                      <div
                        className="grid transition-[grid-template-rows] duration-200 ease-out"
                        style={{ gridTemplateRows: expandedItem === iKey ? "1fr" : "0fr" }}
                      >
                        <div className="overflow-hidden">
                          <div className="pl-[22px] pt-0.5 pb-1 text-xs text-muted-foreground space-y-0.5">
                            {clause.reason && <p>{clause.reason}</p>}
                            {clause.evidence?.length > 0 &&
                              clause.evidence.map((ev: any, eidx: number) => (
                                <p key={eidx} className="italic">
                                  {ev.text_quote || ev.detail || ev.source}
                                </p>
                              ))}
                            {clause.affected_line_items?.length > 0 && (
                              <p>Affected items: {clause.affected_line_items.join(", ")}</p>
                            )}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Section: Verified (green, collapsed by default) */}
      {verified.length > 0 && (
        <div className="border border-green-200 dark:border-green-800 rounded-lg overflow-hidden">
          <button
            onClick={() => toggleSection("verified")}
            className="w-full flex items-center gap-2 px-4 py-3 bg-green-50/30 dark:bg-green-950/10 hover:bg-green-50/50 dark:hover:bg-green-950/20 transition-colors"
          >
            {openSections["verified"] ? (
              <ChevronDown className="h-4 w-4 text-green-600 dark:text-green-400" />
            ) : (
              <ChevronRight className="h-4 w-4 text-green-600 dark:text-green-400" />
            )}
            <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" />
            <span className="text-sm font-medium text-green-800 dark:text-green-300">
              Verified ({verified.length})
            </span>
          </button>
          {openSections["verified"] && (
            <div className="px-4 py-3 space-y-0.5 border-t border-green-200 dark:border-green-800">
              {verified.map((clause: any, idx: number) => {
                const detail = clause.reason?.replace(/\s*\(assumed\)\.?/gi, "").trim() || null;
                return (
                  <div key={idx} className="group/row flex items-center gap-2 py-0.5">
                    <CheckCircle2 className="h-3.5 w-3.5 text-green-600 dark:text-green-400 flex-shrink-0" />
                    <span className="text-sm text-foreground whitespace-nowrap">
                      <span className="font-mono text-xs text-muted-foreground mr-1.5">{clause.clause_reference}</span>
                      {clause.clause_short_name || clause.clause_reference}
                    </span>
                    {detail && (
                      <span className="text-xs text-muted-foreground/60 truncate opacity-0 group-hover/row:opacity-100 transition-opacity duration-150">
                        -- {detail}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// TAB: DOCUMENTS
// =============================================================================

function DocumentsTab({
  documents,
  onViewDocument,
}: {
  documents: DocSummary[];
  onViewDocument?: (evidence: EvidenceLocation) => void;
}) {
  if (documents.length === 0) return <NoDataEmptyState />;

  return (
    <div className="bg-card border border-border rounded-lg overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border bg-muted/50 text-left text-xs text-muted-foreground">
            <th className="px-4 py-2 font-medium">#</th>
            <th className="px-4 py-2 font-medium">Filename</th>
            <th className="px-4 py-2 font-medium">Type</th>
            <th className="px-4 py-2 font-medium text-right">Pages</th>
          </tr>
        </thead>
        <tbody>
          {documents.map((doc, idx) => (
            <tr
              key={doc.doc_id}
              onClick={() =>
                onViewDocument?.({
                  docId: doc.doc_id,
                  page: 1,
                  charStart: null,
                  charEnd: null,
                })
              }
              className="border-b border-border last:border-b-0 cursor-pointer hover:bg-muted/20 transition-colors"
            >
              <td className="px-4 py-2 text-muted-foreground text-xs">
                {idx + 1}
              </td>
              <td className="px-4 py-2 text-foreground">{doc.filename}</td>
              <td className="px-4 py-2 text-muted-foreground text-xs">
                {doc.doc_type?.replace(/_/g, " ") || "-"}
              </td>
              <td className="px-4 py-2 text-right text-muted-foreground text-xs tabular-nums">
                {doc.page_count > 0 ? doc.page_count : "-"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// =============================================================================
// EXPANDED CLAIM DETAIL (inline in table)
// =============================================================================

function ClaimDetail({
  claimId,
  onViewSource,
  onDossierUpdate,
  hasGroundTruth,
  hasGroundTruthDoc,
}: {
  claimId: string;
  onViewSource: (evidence: EvidenceLocation) => void;
  onDossierUpdate?: (claimId: string, data: any) => void;
  hasGroundTruth?: boolean;
  hasGroundTruthDoc?: boolean;
}) {
  const [data, setData] = useState<any>(null);
  const [documents, setDocuments] = useState<DocSummary[]>([]);
  const [assumptions, setAssumptions] = useState<Record<string, boolean>>({});
  const [coverageOverrides, setCoverageOverrides] = useState<Record<string, boolean>>({});
  const [activeTab, setActiveTab] = useState<TabId>("costs");
  const [loading, setLoading] = useState(true);
  const [evaluating, setEvaluating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [wb, docs] = await Promise.all([
        getWorkbenchData(claimId),
        listDocs(claimId).catch(() => [] as DocSummary[]),
      ]);
      setData(wb);
      setDocuments(docs);

      // Initialize assumptions from engine defaults (assumed_value)
      const newAssumptions: Record<string, boolean> = {};
      const assumptionsUsed: any[] = wb.dossier?.assumptions_used ?? [];
      const assumedValueMap: Record<string, boolean> = {};
      for (const a of assumptionsUsed) {
        if (a.clause_reference != null && a.assumed_value != null) {
          assumedValueMap[a.clause_reference] = a.assumed_value;
        }
      }
      for (const ce of wb.dossier?.clause_evaluations ?? []) {
        if (ce.assumption_used != null) {
          newAssumptions[ce.clause_reference] =
            assumedValueMap[ce.clause_reference] ?? ce.assumption_used;
        }
      }
      setAssumptions(newAssumptions);

      // Initialize coverage overrides from persisted dossier
      const savedOverrides = wb.dossier?.coverage_overrides ?? {};
      if (Object.keys(savedOverrides).length > 0) {
        setCoverageOverrides(savedOverrides);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, [claimId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleReEvaluate = useCallback(async () => {
    try {
      setEvaluating(true);
      setError(null);
      const newDossier = await evaluateDecision(claimId, assumptions, coverageOverrides);
      // Update dossier in-place — avoids full reload (spinner + assumption reset)
      setData((prev: any) => {
        const updated = prev ? { ...prev, dossier: newDossier } : prev;
        // Propagate to parent so enrichment cache + table row update
        if (updated && onDossierUpdate) onDossierUpdate(claimId, updated);
        return updated;
      });
      // Sync overrides from the persisted dossier (merged on server)
      if (newDossier?.coverage_overrides) {
        setCoverageOverrides(newDossier.coverage_overrides);
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to re-evaluate decision"
      );
    } finally {
      setEvaluating(false);
    }
  }, [claimId, assumptions, coverageOverrides, onDossierUpdate]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground mr-2" />
        <span className="text-sm text-muted-foreground">Loading claim data...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-4">
        <ErrorEmptyState message={error} onRetry={loadData} />
      </div>
    );
  }

  if (!data) return null;

  const facts = data.facts;
  const makeFact = getFact(facts, "vehicle_make") || getFact(facts, "make");
  const modelFact = getFact(facts, "vehicle_model") || getFact(facts, "model");
  const vehicleMake = makeFact?.value ?? makeFact?.normalized_value;
  const vehicleModel = modelFact?.value ?? modelFact?.normalized_value;
  const vehicleDisplay =
    [vehicleMake, vehicleModel].filter(Boolean).join(" ") || null;
  const vehicleSource = makeFact?.selected_from?.doc_id
    ? makeFact.selected_from
    : modelFact?.selected_from;
  const mileageFact = getFact(facts, "odometer_km");
  const mileageValue = mileageFact?.value ?? mileageFact?.normalized_value;

  const lineItemsWithTrace = (data.coverage?.line_items ?? []).filter(
    (i: any) => Array.isArray(i.decision_trace) && i.decision_trace.length > 0
  ).length;

  const tabs: { id: TabId; label: string; count?: number }[] = [
    {
      id: "costs",
      label: "Costs",
      count: data.coverage?.line_items?.length,
    },
    {
      id: "coverage-checks",
      label: "Coverage Checks",
      count: data.dossier?.clause_evaluations?.length,
    },
    {
      id: "decisions",
      label: "Decisions",
      count: lineItemsWithTrace || undefined,
    },
    {
      id: "documents",
      label: "Documents",
      count: documents.length || data.documents?.length,
    },
  ];

  const confidenceSummary = data.confidence_summary ?? null;
  if (confidenceSummary) {
    tabs.push({ id: "confidence", label: "Confidence" });
  }

  if (hasGroundTruth) {
    tabs.push({ id: "ground-truth", label: "Ground Truth" });
  }

  tabs.push({ id: "notes", label: "Notes" });

  return (
    <div className="space-y-4">
      {/* Decision banner */}
      <DecisionBanner data={data} claimId={claimId} />

      {/* Tabs */}
      <div className="border-b border-border">
        <nav className="flex gap-0">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "px-4 py-2 text-sm font-medium border-b-2 transition-colors",
                activeTab === tab.id
                  ? "border-primary text-primary"
                  : "border-transparent text-muted-foreground hover:text-foreground hover:border-border"
              )}
            >
              {tab.label}
              {tab.count != null && (
                <span className="ml-1.5 text-xs text-muted-foreground">
                  ({tab.count})
                </span>
              )}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab content */}
      <div>
        {activeTab === "costs" && (
          <CostBreakdownTab
            data={data}
            coverageOverrides={coverageOverrides}
            setCoverageOverrides={setCoverageOverrides}
            documents={documents}
            onViewDocument={onViewSource}
          />
        )}
        {activeTab === "coverage-checks" && (
          <CoverageChecksTab
            data={data}
            assumptions={assumptions}
            onToggle={(ref, val) =>
              setAssumptions((prev) => ({ ...prev, [ref]: val }))
            }
            onReEvaluate={handleReEvaluate}
            evaluating={evaluating}
          />
        )}
        {activeTab === "decisions" && (
          <DecisionTraceTab data={data} />
        )}
        {activeTab === "documents" && (
          <DocumentsTab
            documents={documents}
            onViewDocument={onViewSource}
          />
        )}
        {activeTab === "confidence" && confidenceSummary && (
          <CCISummaryCard summary={confidenceSummary} />
        )}
        {activeTab === "ground-truth" && (
          <GroundTruthTab
            claimId={claimId}
            hasGroundTruthDoc={!!hasGroundTruthDoc}
          />
        )}
        {activeTab === "notes" && (
          <NotesTab claimId={claimId} />
        )}
      </div>
    </div>
  );
}

// =============================================================================
// MAIN PAGE — TYPES & HELPERS
// =============================================================================

type SortKey =
  | "claim_id"
  | "decision"
  | "rationale"
  | "confidence"
  | "event_date"
  | "payout"
  | "diff"
  | "vehicle"
  | "dataset";

type SortDir = "asc" | "desc";

interface EffectiveValues {
  decision: string | null;
  rationale: string | null;
  confidence: number | null;
  eventDate: string | null;
  payout: number | null;
  diff: number | null;
  gtPayout: number | null;
  vehicle: string | null;
  dataset: string | null;
}

function SortHeader({
  label,
  sortKey: currentKey,
  sortDir,
  sortKeyName,
  onSort,
  className = "",
}: {
  label: string;
  sortKey: SortKey;
  sortDir: SortDir;
  sortKeyName: SortKey;
  onSort: (key: SortKey) => void;
  className?: string;
}) {
  return (
    <th
      onClick={() => onSort(sortKeyName)}
      className={cn(
        "py-2 px-2 font-medium text-muted-foreground cursor-pointer hover:text-foreground select-none text-xs whitespace-nowrap",
        className
      )}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        {currentKey === sortKeyName && (
          <span className="text-primary">
            {sortDir === "asc" ? "\u2191" : "\u2193"}
          </span>
        )}
      </span>
    </th>
  );
}

function parseDate(d: string | null): number {
  if (!d) return 0;
  // ISO format (new normalized data): YYYY-MM-DD
  const isoMatch = d.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (isoMatch) {
    return new Date(Number(isoMatch[1]), Number(isoMatch[2]) - 1, Number(isoMatch[3])).getTime();
  }
  // Legacy European formats: DD.MM.YYYY, DD/MM/YYYY, DD,MM,YYYY
  const parts = d.split(/[./,]/);
  if (parts.length === 3) {
    const [day, month, year] = parts;
    return new Date(Number(year), Number(month) - 1, Number(day)).getTime();
  }
  return new Date(d).getTime() || 0;
}

// =============================================================================
// MAIN PAGE
// =============================================================================

export function ClaimsWorkbenchPage() {
  const [claims, setClaims] = useState<DashboardClaim[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Sorting
  const [sortKey, setSortKey] = useState<SortKey>("claim_id");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  // Filters
  const [search, setSearch] = useState("");
  const [verdictFilter, setVerdictFilter] = useState<string>("all");
  const [datasetFilter, setDatasetFilter] = useState<string>("all");
  const [tierFilter, setTierFilter] = useState<string>("all");

  // Document slide panel
  const [selectedEvidence, setSelectedEvidence] =
    useState<EvidenceLocation | null>(null);
  const [slideClaimId, setSlideClaimId] = useState<string | null>(null);
  const [slideDocs, setSlideDocs] = useState<DocSummary[]>([]);

  const loadClaims = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const list = await getDashboardClaims();
      setClaims(list.filter((c) => c.has_dossier));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load claims");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadClaims();
  }, [loadClaims]);

  const handleSort = useCallback(
    (key: SortKey) => {
      if (sortKey === key) {
        setSortDir((d) => (d === "asc" ? "desc" : "asc"));
      } else {
        setSortKey(key);
        setSortDir("asc");
      }
    },
    [sortKey]
  );

  // Get effective display values for a claim
  const getEffective = useCallback(
    (claim: DashboardClaim): EffectiveValues => {
      // Normalize cci_score (0-1) to 0-100 for display; fall back to assessment confidence
      const rawConf = claim.cci_score ?? (claim.confidence != null ? claim.confidence / 100 : null);
      const confidence = rawConf != null ? (rawConf <= 1 ? Math.round(rawConf * 100) : rawConf) : null;

      return {
        decision: claim.verdict ?? claim.decision?.toUpperCase() ?? null,
        rationale: claim.verdict_reason ?? claim.result_code ?? null,
        confidence,
        eventDate: claim.event_date ?? claim.claim_date ?? null,
        payout: claim.screening_payout ?? claim.payout,
        diff: claim.payout_diff ?? null,
        gtPayout: claim.gt_payout ?? null,
        vehicle: claim.vehicle ?? null,
        dataset: claim.dataset_label ?? null,
      };
    },
    []
  );

  // Filter claims
  const filtered = useMemo(() => {
    return claims.filter((c) => {
      const eff = getEffective(c);
      if (search) {
        const s = search.toLowerCase();
        const matches =
          c.claim_id.toLowerCase().includes(s) ||
          (eff.vehicle?.toLowerCase().includes(s) ?? false);
        if (!matches) return false;
      }
      if (verdictFilter !== "all") {
        const d = eff.decision?.toUpperCase();
        if (!d || d !== verdictFilter) return false;
      }
      if (datasetFilter !== "all") {
        const ds = c.dataset_id ?? c.dataset_label ?? null;
        if (!ds || ds !== datasetFilter) return false;
      }
      if (tierFilter !== "all") {
        const tier = c.routing_tier ?? null;
        if (!tier || tier !== tierFilter) return false;
      }
      return true;
    });
  }, [claims, search, verdictFilter, datasetFilter, tierFilter, getEffective]);

  // Sort claims
  const sorted = useMemo(() => {
    const compare = (a: DashboardClaim, b: DashboardClaim): number => {
      const ea = getEffective(a);
      const eb = getEffective(b);
      let va: string | number | null;
      let vb: string | number | null;

      switch (sortKey) {
        case "claim_id":
          va = Number(a.claim_id) || a.claim_id;
          vb = Number(b.claim_id) || b.claim_id;
          break;
        case "decision":
          va = ea.decision || "";
          vb = eb.decision || "";
          break;
        case "rationale":
          va = ea.rationale || "";
          vb = eb.rationale || "";
          break;
        case "confidence":
          va = ea.confidence ?? -1;
          vb = eb.confidence ?? -1;
          break;
        case "event_date":
          va = parseDate(ea.eventDate);
          vb = parseDate(eb.eventDate);
          break;
        case "payout":
          va = ea.payout ?? -1;
          vb = eb.payout ?? -1;
          break;
        case "diff":
          va = ea.diff ?? -Infinity;
          vb = eb.diff ?? -Infinity;
          break;
        case "vehicle":
          va = ea.vehicle || "";
          vb = eb.vehicle || "";
          break;
        case "dataset":
          va = ea.dataset || "";
          vb = eb.dataset || "";
          break;
        default:
          return 0;
      }

      if (va === vb) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      if (va < vb) return sortDir === "asc" ? -1 : 1;
      return sortDir === "asc" ? 1 : -1;
    };

    return [...filtered].sort(compare);
  }, [filtered, sortKey, sortDir, getEffective]);

  // Expand/collapse handler
  const handleToggle = useCallback((claimId: string) => {
    setExpandedId((prev) => (prev === claimId ? null : claimId));
  }, []);

  // Re-sync claim row when dossier is re-evaluated
  const handleDossierUpdate = useCallback((claimId: string, wb: any) => {
    const dossier = wb?.dossier;
    if (!dossier) return;
    setClaims((prev) =>
      prev.map((c) =>
        c.claim_id === claimId
          ? {
              ...c,
              verdict: dossier.claim_verdict?.toUpperCase() ?? c.verdict,
              cci_score: dossier.confidence_index?.composite_score ?? c.cci_score,
              cci_band: dossier.confidence_index?.band ?? c.cci_band,
            }
          : c
      )
    );
  }, []);

  // View source handler — opens document slide panel
  const handleViewSource = useCallback(
    (claimId: string, evidence: EvidenceLocation) => {
      setSlideClaimId(claimId);
      setSelectedEvidence(evidence);
      listDocs(claimId)
        .then(setSlideDocs)
        .catch(() => setSlideDocs([]));
    },
    []
  );

  // Unique verdicts for filter dropdown
  const availableVerdicts = useMemo(() => {
    const set = new Set<string>();
    for (const claim of claims) {
      const v = claim.verdict ?? claim.decision?.toUpperCase();
      if (v) set.add(v);
    }
    return Array.from(set).sort();
  }, [claims]);

  // Unique datasets for filter dropdown
  const availableDatasets = useMemo(() => {
    const map = new Map<string, string>();
    for (const claim of claims) {
      const id = claim.dataset_id ?? claim.dataset_label;
      const label = claim.dataset_label ?? claim.dataset_id;
      if (id && label) map.set(id, label);
    }
    return Array.from(map.entries()).sort((a, b) => a[1].localeCompare(b[1]));
  }, [claims]);

  if (loading && claims.length === 0 && !error) {
    return <PageLoadingSkeleton message="Loading claims..." />;
  }

  const TOTAL_COLS = 10; // chevron + 9 data columns

  return (
    <div className="h-full flex flex-col">
      {/* Filter bar — no page title (already shown in app header) */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-border bg-background flex-shrink-0">
        <div className="flex items-center gap-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search claim, vehicle..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 pr-3 py-1.5 text-sm border border-border rounded-md bg-background text-foreground w-72 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
            />
          </div>
          <select
            value={verdictFilter}
            onChange={(e) => setVerdictFilter(e.target.value)}
            className="text-sm border border-border rounded-md px-2 py-1.5 bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
          >
            <option value="all">All decisions</option>
            {availableVerdicts.map((v) => (
              <option key={v} value={v}>
                {v.charAt(0) + v.slice(1).toLowerCase()}
              </option>
            ))}
          </select>
          <select
            value={datasetFilter}
            onChange={(e) => setDatasetFilter(e.target.value)}
            className="text-sm border border-border rounded-md px-2 py-1.5 bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
          >
            <option value="all">All datasets</option>
            {availableDatasets.map(([id, label]) => (
              <option key={id} value={id}>
                {label}
              </option>
            ))}
          </select>
          <select
            value={tierFilter}
            onChange={(e) => setTierFilter(e.target.value)}
            className="text-sm border border-border rounded-md px-2 py-1.5 bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
          >
            <option value="all">All tiers</option>
            <option value="GREEN">Green</option>
            <option value="YELLOW">Yellow</option>
            <option value="RED">Red</option>
          </select>
          <span className="text-sm text-muted-foreground">
            {sorted.length} claim{sorted.length !== 1 ? "s" : ""}
          </span>
        </div>
        <button
          onClick={loadClaims}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-muted rounded-md transition-colors disabled:opacity-50"
        >
          <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
          Refresh
        </button>
      </div>

      {/* Error banner */}
      {error && (
        <div className="mx-6 mt-3 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive flex items-center justify-between flex-shrink-0">
          <span>{error}</span>
          <button
            onClick={() => setError(null)}
            className="text-destructive hover:text-destructive/80 ml-2 text-lg leading-none"
          >
            &times;
          </button>
        </div>
      )}

      {/* Claims table */}
      <div className="flex-1 overflow-auto px-6 py-4">
        <div className="bg-card border border-border rounded-lg overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/50 text-xs">
                  <th className="py-2 px-2 w-8" />
                  <SortHeader label="Claim ID" sortKeyName="claim_id" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} className="text-left" />
                  <SortHeader label="Status" sortKeyName="decision" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} className="text-center" />
                  <SortHeader label="Rationale" sortKeyName="rationale" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} className="text-left" />
                  <SortHeader label="Conf." sortKeyName="confidence" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} className="text-right" />
                  <SortHeader label="Event Date" sortKeyName="event_date" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} className="text-left" />
                  <SortHeader label="Payout (CHF)" sortKeyName="payout" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} className="text-right" />
                  <SortHeader label="Diff" sortKeyName="diff" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} className="text-right" />
                  <SortHeader label="Vehicle" sortKeyName="vehicle" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} className="text-left" />
                  <SortHeader label="Dataset" sortKeyName="dataset" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} className="text-left" />
                </tr>
              </thead>
              <tbody>
                {sorted.map((claim) => {
                  const isExpanded = expandedId === claim.claim_id;
                  const eff = getEffective(claim);
                  return (
                    <ClaimRow
                      key={claim.claim_id}
                      claim={claim}
                      effective={eff}
                      isExpanded={isExpanded}
                      totalCols={TOTAL_COLS}
                      onToggle={() => handleToggle(claim.claim_id)}
                      onViewSource={(ev) =>
                        handleViewSource(claim.claim_id, ev)
                      }
                      onDossierUpdate={handleDossierUpdate}
                    />
                  );
                })}
              </tbody>
            </table>
          </div>
          {sorted.length === 0 && (
            <div className="flex items-center justify-center py-12 text-sm text-muted-foreground">
              {search || verdictFilter !== "all" || datasetFilter !== "all"
                ? "No claims match your filters."
                : "No claims found."}
            </div>
          )}
        </div>
      </div>

      {/* Document Slide Panel */}
      {slideClaimId && (
        <DocumentSlidePanel
          claimId={slideClaimId}
          evidence={selectedEvidence}
          documents={slideDocs}
          onClose={() => {
            setSelectedEvidence(null);
            setSlideClaimId(null);
          }}
        />
      )}
    </div>
  );
}

// =============================================================================
// CLAIM ROW (table row + expanded detail)
// =============================================================================

function ClaimRow({
  claim,
  effective,
  isExpanded,
  totalCols,
  onToggle,
  onViewSource,
  onDossierUpdate,
}: {
  claim: DashboardClaim;
  effective: EffectiveValues;
  isExpanded: boolean;
  totalCols: number;
  onToggle: () => void;
  onViewSource: (evidence: EvidenceLocation) => void;
  onDossierUpdate?: (claimId: string, data: any) => void;
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(claim.claim_id);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const tierStyle =
    claim.routing_tier === "GREEN"
      ? "bg-emerald-100 dark:bg-emerald-900/30 text-emerald-800 dark:text-emerald-300"
      : claim.routing_tier === "YELLOW"
        ? "bg-amber-100 dark:bg-amber-900/30 text-amber-800 dark:text-amber-300"
        : claim.routing_tier === "RED"
          ? "bg-rose-100 dark:bg-rose-900/30 text-rose-800 dark:text-rose-300"
          : "text-foreground";

  const isDenied = effective.decision === "DENY";

  return (
    <>
      <tr
        onClick={onToggle}
        className={cn(
          "border-b border-border cursor-pointer transition-colors group",
          isExpanded
            ? "bg-primary/5 dark:bg-primary/10"
            : "hover:bg-muted/50"
        )}
      >
        <td className="py-2 px-2">
          {isExpanded ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
        </td>
        {/* Claim ID (copyable) */}
        <td className="py-2 px-2">
          <span className="inline-flex items-center gap-1">
            <span className="font-semibold text-foreground font-mono tracking-tight text-sm">
              {claim.claim_id}
            </span>
            <button
              onClick={handleCopy}
              className="p-0.5 rounded hover:bg-muted text-muted-foreground hover:text-foreground flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
              title={copied ? "Copied!" : "Copy claim ID"}
            >
              {copied ? (
                <Check className="h-3 w-3 text-success" />
              ) : (
                <Copy className="h-3 w-3" />
              )}
            </button>
          </span>
        </td>
        {/* Status */}
        <td className="py-2 px-2 text-center">
          <VerdictBadge verdict={effective.decision} />
        </td>
        {/* Rationale */}
        <td
          className="py-2 px-2 text-xs max-w-[200px] truncate text-muted-foreground"
          title={effective.rationale ?? undefined}
        >
          {effective.rationale || "-"}
        </td>
        {/* Confidence */}
        <td
          className={cn(
            "py-2 px-2 text-right font-mono text-xs rounded-sm",
            tierStyle
          )}
          title={claim.routing_tier ? `Tier: ${claim.routing_tier}` : undefined}
        >
          {effective.confidence != null
            ? `${effective.confidence.toFixed(0)}%`
            : "-"}
        </td>
        {/* Event Date */}
        <td className="py-2 px-2 text-xs text-muted-foreground">
          {formatEventDate(effective.eventDate)}
        </td>
        {/* Payout */}
        <td className="py-2 px-2 text-right font-mono text-xs text-foreground">
          {isDenied
            ? "-"
            : effective.payout != null
              ? effective.payout.toFixed(2)
              : "-"}
        </td>
        {/* Diff (system payout - ground truth) */}
        <td className="py-2 px-2 text-right font-mono text-xs">
          {effective.diff != null ? (
            <span
              className={cn(
                "font-medium",
                effective.diff > 0
                  ? "text-rose-600 dark:text-rose-400"
                  : effective.diff < 0
                    ? "text-emerald-600 dark:text-emerald-400"
                    : "text-muted-foreground"
              )}
            >
              {effective.diff > 0 ? "+" : ""}
              {effective.diff.toFixed(2)}
            </span>
          ) : (
            <span className="text-muted-foreground">-</span>
          )}
        </td>
        {/* Vehicle */}
        <td
          className="py-2 px-2 text-xs text-muted-foreground max-w-[140px] truncate"
          title={effective.vehicle ?? undefined}
        >
          {effective.vehicle || "-"}
        </td>
        {/* Dataset */}
        <td className="py-2 px-2 text-xs text-muted-foreground">
          {effective.dataset || "-"}
        </td>
      </tr>
      {isExpanded && (
        <tr>
          <td colSpan={totalCols} className="p-0">
            <div className="px-6 py-4 border-b border-border bg-muted/10 overflow-hidden max-w-[calc(100vw-3.5rem)]">
              <ClaimDetail
                claimId={claim.claim_id}
                onViewSource={onViewSource}
                onDossierUpdate={onDossierUpdate}
                hasGroundTruth={!!(claim.gt_decision || claim.has_ground_truth_doc)}
                hasGroundTruthDoc={claim.has_ground_truth_doc}
              />
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
