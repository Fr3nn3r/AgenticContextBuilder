import { useState, useEffect, useCallback, useMemo } from "react";
import {
  ChevronDown,
  ChevronRight,
  FileText,
  ExternalLink,
  Database,
} from "lucide-react";
import { getDashboardClaimDetail, getClaimFacts, listDocs } from "../../api/client";
import { DocumentSlidePanel } from "../ClaimExplorer/DocumentSlidePanel";
import type { EvidenceLocation } from "../ClaimExplorer/DocumentSlidePanel";
import { cn } from "../../lib/utils";
import type {
  DashboardClaimDetail as DetailType,
  DashboardClaimDoc,
  ClaimFacts,
  AggregatedFact,
  DocSummary,
} from "../../types";

interface DashboardClaimDetailProps {
  claimId: string;
  documents: DashboardClaimDoc[];
}

type Tab = "checks" | "coverage" | "payout" | "facts";

const CHECK_LABELS: Record<string, string> = {
  policy_enforcement: "Policy Enforcement",
  policy_validity: "Policy Validity",
  damage_date: "Damage Date",
  damage_date_validity: "Damage Date",
  vin_consistency: "VIN Consistency",
  vehicle_id: "VIN Consistency",
  vehicle_id_consistency: "VIN Consistency",
  owner_match: "Owner / Policyholder Match",
  owner_policyholder_match: "Owner / Policyholder Match",
  mileage: "Mileage Compliance",
  mileage_compliance: "Mileage Compliance",
  shop_authorization: "Shop Authorization",
  service_compliance: "Service Compliance",
  component_coverage: "Component Coverage",
  assistance_items: "Assistance Items",
  assistance_package_items: "Assistance Items",
  hybrid_exclusion: "Hybrid / EV Exclusion",
  payout_calculation: "Payout Calculation",
  final_decision: "Final Decision",
};

function getCheckLabel(checkName: string): string {
  return (
    CHECK_LABELS[checkName] ||
    checkName
      .split("_")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ")
  );
}

function formatDocType(docType: string): string {
  return docType
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export function DashboardClaimDetail({ claimId, documents }: DashboardClaimDetailProps) {
  const [detail, setDetail] = useState<DetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>("checks");

  // Shared document slide panel state (same pattern as ClaimSummaryTab)
  const [selectedEvidence, setSelectedEvidence] = useState<EvidenceLocation | null>(null);
  const [docSummaries, setDocSummaries] = useState<DocSummary[]>([]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getDashboardClaimDetail(claimId)
      .then((d) => {
        if (!cancelled) setDetail(d);
      })
      .catch(() => {
        if (!cancelled) setDetail(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [claimId]);

  // Load full DocSummary[] for the slide panel navigation
  useEffect(() => {
    let cancelled = false;
    listDocs(claimId)
      .then((docs) => {
        if (!cancelled) setDocSummaries(docs);
      })
      .catch(() => {
        if (!cancelled) setDocSummaries([]);
      });
    return () => {
      cancelled = true;
    };
  }, [claimId]);

  const handleViewSource = useCallback(
    (
      docId: string,
      page: number | null,
      charStart: number | null,
      charEnd: number | null
    ) => {
      setSelectedEvidence({ docId, page, charStart, charEnd });
    },
    []
  );

  const handleClosePanel = useCallback(() => {
    setSelectedEvidence(null);
  }, []);

  if (loading) {
    return (
      <div className="p-4 text-sm text-slate-500 dark:text-slate-400">
        Loading details...
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="p-4 text-sm text-slate-500 dark:text-slate-400">
        No detail data available.
      </div>
    );
  }

  const tabClass = (t: Tab) =>
    `px-4 py-2 text-sm font-medium rounded-t-md transition-colors ${
      tab === t
        ? "bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 border-b-2 border-primary"
        : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
    }`;

  return (
    <div className="border border-slate-200 dark:border-slate-700 rounded-lg bg-slate-50 dark:bg-slate-800/50 mt-1">
      {/* Tabs */}
      <div className="flex gap-1 px-4 pt-3 border-b border-slate-200 dark:border-slate-700">
        <button onClick={() => setTab("checks")} className={tabClass("checks")}>
          Assessment Checks
        </button>
        <button onClick={() => setTab("coverage")} className={tabClass("coverage")}>
          Coverage Details
        </button>
        <button onClick={() => setTab("payout")} className={tabClass("payout")}>
          Payout Comparison
        </button>
        <button onClick={() => setTab("facts")} className={tabClass("facts")}>
          Facts
        </button>
      </div>

      <div className="p-4">
        {tab === "checks" && (
          <ChecksTab
            detail={detail}
            documents={documents}
            onViewSource={handleViewSource}
          />
        )}
        {tab === "coverage" && <CoverageTab detail={detail} />}
        {tab === "payout" && <PayoutTab detail={detail} />}
        {tab === "facts" && (
          <FactsTab claimId={claimId} onViewSource={handleViewSource} />
        )}
      </div>

      {/* Shared slide panel for document viewing (same pattern as ClaimSummaryTab) */}
      <DocumentSlidePanel
        claimId={claimId}
        evidence={selectedEvidence}
        documents={docSummaries}
        onClose={handleClosePanel}
      />
    </div>
  );
}

/* ============================================================
   Assessment Checks Tab — two-column layout (checks + documents)
   ============================================================ */
function ChecksTab({
  detail,
  documents,
  onViewSource,
}: {
  detail: DetailType;
  documents: DashboardClaimDoc[];
  onViewSource: (
    docId: string,
    page: number | null,
    charStart: number | null,
    charEnd: number | null
  ) => void;
}) {
  const checks = detail.assessment_checks;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Left: Assessment Checks */}
      <div>
        <h4 className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-2">
          Assessment Checks
        </h4>
        {checks.length === 0 ? (
          <p className="text-sm text-slate-500 dark:text-slate-400">
            No check data.
          </p>
        ) : (
          <div className="space-y-0.5">
            {checks.map((check, i) => {
              const result = String(
                check.result || check.verdict || ""
              ).toUpperCase();
              const badgeColor =
                result === "PASS"
                  ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400"
                  : result === "FAIL"
                    ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
                    : result === "SKIPPED" || result === "NOT_CHECKED"
                      ? "bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400"
                      : "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400";
              const rawName = String(
                check.check_name || check.check_id || `check_${i + 1}`
              );
              const checkNum =
                check.check_number != null ? `${check.check_number}. ` : "";

              return (
                <div
                  key={i}
                  className="flex items-start gap-3 py-2.5 px-3 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800/30 transition-colors"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-slate-800 dark:text-slate-100">
                        {checkNum}
                        {getCheckLabel(rawName)}
                      </span>
                      <span
                        className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide flex-shrink-0 ${badgeColor}`}
                      >
                        {result === "NOT_CHECKED"
                          ? "SKIPPED"
                          : result || "N/A"}
                      </span>
                    </div>
                    {(check.details || check.reason) && (
                      <p className="text-slate-500 dark:text-slate-400 text-xs mt-1 leading-relaxed">
                        {String(check.details || check.reason || "")}
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Right: Documents */}
      <div>
        <h4 className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-2">
          Documents
        </h4>
        {documents.length === 0 ? (
          <p className="text-sm text-slate-500 dark:text-slate-400">
            No documents.
          </p>
        ) : (
          <div className="space-y-1">
            {documents.map((doc) => (
              <button
                key={doc.doc_id}
                onClick={() => onViewSource(doc.doc_id, null, null, null)}
                className="w-full flex items-center gap-3 px-3 py-2 rounded-md text-left transition-colors hover:bg-slate-100 dark:hover:bg-slate-700/50"
              >
                <span className="text-slate-400 dark:text-slate-500">
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                  >
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <polyline points="14 2 14 8 20 8" />
                  </svg>
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-700 dark:text-slate-200 truncate">
                    {doc.filename}
                  </p>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    {formatDocType(doc.doc_type)}
                  </p>
                </div>
                <span className="text-xs text-primary">View</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/* ============================================================
   Coverage Details Tab — with sortable columns
   ============================================================ */
type CoverageSortKey =
  | "item_code"
  | "description"
  | "item_type"
  | "total_price"
  | "coverage_status"
  | "matched_component"
  | "match_reasoning";

function CoverageTab({ detail }: { detail: DetailType }) {
  const [sortCol, setSortCol] = useState<CoverageSortKey | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  const handleSort = (col: CoverageSortKey) => {
    if (sortCol === col) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortCol(col);
      setSortDir("asc");
    }
  };

  const sortedItems = useMemo(() => {
    if (!sortCol) return detail.coverage_items;
    return [...detail.coverage_items].sort((a, b) => {
      const va = a[sortCol];
      const vb = b[sortCol];
      if (va === vb) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      const cmp =
        typeof va === "number" && typeof vb === "number"
          ? va - vb
          : String(va).localeCompare(String(vb));
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [detail.coverage_items, sortCol, sortDir]);

  if (detail.coverage_items.length === 0) {
    return (
      <p className="text-sm text-slate-500 dark:text-slate-400">
        No coverage data.
      </p>
    );
  }

  const SortableTh = ({
    label,
    colKey,
    className = "",
  }: {
    label: string;
    colKey: CoverageSortKey;
    className?: string;
  }) => (
    <th
      onClick={() => handleSort(colKey)}
      className={`py-2 px-2 font-medium text-slate-600 dark:text-slate-300 cursor-pointer hover:text-slate-900 dark:hover:text-slate-100 select-none ${className}`}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        {sortCol === colKey && (
          <span className="text-primary">
            {sortDir === "asc" ? "\u2191" : "\u2193"}
          </span>
        )}
      </span>
    </th>
  );

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-slate-200 dark:border-slate-700">
            <SortableTh label="Code" colKey="item_code" className="text-left" />
            <SortableTh
              label="Description"
              colKey="description"
              className="text-left"
            />
            <SortableTh label="Type" colKey="item_type" className="text-left" />
            <SortableTh
              label="Price"
              colKey="total_price"
              className="text-right"
            />
            <SortableTh
              label="Status"
              colKey="coverage_status"
              className="text-center"
            />
            <SortableTh
              label="Component"
              colKey="matched_component"
              className="text-left"
            />
            <SortableTh
              label="Reasoning"
              colKey="match_reasoning"
              className="text-left"
            />
          </tr>
        </thead>
        <tbody>
          {sortedItems.map((item, i) => {
            const status = String(item.coverage_status || "");
            const statusColor =
              status === "covered"
                ? "text-emerald-600 dark:text-emerald-400"
                : status === "not_covered"
                  ? "text-red-500 dark:text-red-400"
                  : "text-amber-500 dark:text-amber-400";
            return (
              <tr
                key={i}
                className="border-b border-slate-100 dark:border-slate-700/50"
              >
                <td className="py-1.5 px-2 text-slate-600 dark:text-slate-300 font-mono">
                  {String(item.item_code || "")}
                </td>
                <td className="py-1.5 px-2 text-slate-700 dark:text-slate-200 max-w-xs truncate">
                  {String(item.description || "")}
                </td>
                <td className="py-1.5 px-2 text-slate-500 dark:text-slate-400">
                  {String(item.item_type || "")}
                </td>
                <td className="py-1.5 px-2 text-right text-slate-700 dark:text-slate-200 font-mono">
                  {typeof item.total_price === "number"
                    ? item.total_price.toFixed(2)
                    : ""}
                </td>
                <td
                  className={`py-1.5 px-2 text-center font-medium ${statusColor}`}
                >
                  {status === "covered"
                    ? "Covered"
                    : status === "not_covered"
                      ? "Not Covered"
                      : status}
                </td>
                <td className="py-1.5 px-2 text-slate-600 dark:text-slate-300 max-w-[120px] truncate">
                  {String(item.matched_component || "")}
                </td>
                <td className="py-1.5 px-2 text-slate-500 dark:text-slate-400 max-w-xs truncate">
                  {String(item.match_reasoning || "")}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/* ============================================================
   Payout Comparison Tab
   ============================================================ */
function PayoutTab({ detail }: { detail: DetailType }) {
  const pc = detail.payout_calculation as Record<string, unknown> | null;
  const fmt = (v: unknown) =>
    typeof v === "number" ? v.toFixed(2) : v != null ? String(v) : "-";

  const coveragePctFmt =
    pc?.coverage_percent != null ? `${pc.coverage_percent}%` : "-";
  const gtCoveragePctFmt =
    detail.gt_reimbursement_rate_pct != null
      ? `${detail.gt_reimbursement_rate_pct}%`
      : "-";

  const rows: Array<{ label: string; system: unknown; gt: unknown }> = [
    {
      label: "Parts",
      system: detail.sys_parts_adjusted,
      gt: detail.gt_parts_approved,
    },
    {
      label: "Labor",
      system: detail.sys_labor_adjusted,
      gt: detail.gt_labor_approved,
    },
    {
      label: "Subtotal (Parts + Labor)",
      system: detail.sys_total_adjusted,
      gt: detail.gt_total_material_labor,
    },
    {
      label: "Coverage %",
      system: coveragePctFmt,
      gt: gtCoveragePctFmt,
    },
    {
      label: "VAT %",
      system:
        detail.sys_vat_rate_pct != null
          ? `${detail.sys_vat_rate_pct}%`
          : "-",
      gt: detail.gt_vat_rate_pct != null ? `${detail.gt_vat_rate_pct}%` : "-",
    },
    {
      label: "Deductible",
      system: pc?.deductible,
      gt: detail.gt_deductible,
    },
    {
      label: "Final Payout",
      system: pc?.final_payout,
      gt: detail.gt_total_approved,
    },
  ];

  // Compute diff and color for numeric rows
  const getDiff = (
    sys: unknown,
    gt: unknown
  ): { text: string; color: string } => {
    if (typeof sys !== "number" || typeof gt !== "number")
      return { text: "", color: "" };
    const diff = sys - gt;
    const abs = Math.abs(diff);
    const color =
      abs <= 1
        ? "text-emerald-600 dark:text-emerald-400"
        : abs <= 10
          ? "text-amber-500 dark:text-amber-400"
          : "text-red-500 dark:text-red-400";
    const sign = diff > 0 ? "+" : "";
    return { text: `${sign}${diff.toFixed(2)}`, color };
  };

  return (
    <div className="max-w-2xl">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-200 dark:border-slate-700">
            <th className="text-left py-2 px-2 font-medium text-slate-600 dark:text-slate-300">
              Field
            </th>
            <th className="text-right py-2 px-2 font-medium text-slate-600 dark:text-slate-300">
              System
            </th>
            <th className="text-right py-2 px-2 font-medium text-slate-600 dark:text-slate-300">
              Ground Truth
            </th>
            <th className="text-right py-2 px-2 font-medium text-slate-600 dark:text-slate-300">
              Diff
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const diff = getDiff(r.system, r.gt);
            return (
              <tr
                key={r.label}
                className="border-b border-slate-100 dark:border-slate-700/50"
              >
                <td className="py-1.5 px-2 text-slate-700 dark:text-slate-200">
                  {r.label}
                </td>
                <td className="py-1.5 px-2 text-right font-mono text-slate-700 dark:text-slate-200">
                  {fmt(r.system)}
                </td>
                <td className="py-1.5 px-2 text-right font-mono text-slate-700 dark:text-slate-200">
                  {fmt(r.gt)}
                </td>
                <td
                  className={`py-1.5 px-2 text-right font-mono ${diff.color}`}
                >
                  {diff.text}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/* ============================================================
   Facts Tab — matches ClaimExplorer Data tab style exactly
   ============================================================ */

function formatFieldName(name: string): string {
  return name
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function FactsTab({
  claimId,
  onViewSource,
}: {
  claimId: string;
  onViewSource: (
    docId: string,
    page: number | null,
    charStart: number | null,
    charEnd: number | null
  ) => void;
}) {
  const [facts, setFacts] = useState<ClaimFacts | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(
    new Set(["all"])
  );

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getClaimFacts(claimId)
      .then((d) => {
        if (!cancelled) setFacts(d);
      })
      .catch(() => {
        if (!cancelled) setFacts(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [claimId]);

  if (loading) {
    return (
      <p className="text-sm text-muted-foreground">Loading facts...</p>
    );
  }

  if (!facts || facts.facts.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No facts aggregated for this claim.
      </p>
    );
  }

  // Group facts by source doc_type
  const factsByDocType = new Map<string, AggregatedFact[]>();
  for (const fact of facts.facts) {
    const docType = fact.selected_from?.doc_type || "unknown";
    if (!factsByDocType.has(docType)) factsByDocType.set(docType, []);
    factsByDocType.get(docType)!.push(fact);
  }

  const groups = Array.from(factsByDocType.entries()).sort(([a], [b]) =>
    a.localeCompare(b)
  );

  const toggleGroup = (docType: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has("all")) {
        // First toggle: collapse "all" and expand everything except the clicked one
        next.delete("all");
        for (const [dt] of groups) {
          if (dt !== docType) next.add(dt);
        }
      } else if (next.has(docType)) {
        next.delete(docType);
      } else {
        next.add(docType);
      }
      return next;
    });
  };

  return (
    <div className="bg-card rounded-lg border border-border overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border bg-muted/50">
        <div className="flex items-center gap-2">
          <Database className="h-4 w-4 text-muted-foreground" />
          <h3 className="font-semibold text-foreground">All Facts</h3>
          <span className="text-xs text-muted-foreground">
            ({facts.facts.length} facts from {groups.length} document types)
          </span>
        </div>
      </div>

      {/* Groups */}
      <div className="divide-y divide-border">
        {groups.map(([docType, groupFacts]) => {
          const isExpanded =
            expandedGroups.has(docType) || expandedGroups.has("all");
          const source = facts.sources.find((s) => s.doc_type === docType);

          return (
            <div key={docType}>
              {/* Group Header */}
              <button
                onClick={() => toggleGroup(docType)}
                className="w-full px-4 py-2 flex items-center gap-2 hover:bg-muted transition-colors"
              >
                {isExpanded ? (
                  <ChevronDown className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                )}
                <FileText className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                <span className="font-medium text-sm text-foreground">
                  {docType.replace(/_/g, " ")}
                </span>
                <span className="text-xs text-muted-foreground">
                  ({groupFacts.length} facts)
                </span>
                {source && (
                  <span className="text-xs text-muted-foreground/70 ml-auto truncate max-w-[200px]">
                    {source.filename}
                  </span>
                )}
              </button>

              {/* Facts in 2-column grid */}
              {isExpanded && (
                <div className="px-4 pb-3 pl-10">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1">
                    {groupFacts.map((fact) => (
                      <FactRow
                        key={fact.name}
                        fact={fact}
                        onViewSource={onViewSource}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Footer */}
      <div className="text-[10px] text-muted-foreground px-4 py-2 border-t border-border">
        Generated {new Date(facts.generated_at).toLocaleString()} from{" "}
        {facts.sources.length} source{facts.sources.length !== 1 ? "s" : ""}
      </div>
    </div>
  );
}

/** Single fact row — matches ClaimExplorer FactRow pattern */
function FactRow({
  fact,
  onViewSource,
}: {
  fact: AggregatedFact;
  onViewSource: (
    docId: string,
    page: number | null,
    charStart: number | null,
    charEnd: number | null
  ) => void;
}) {
  const hasSource = !!fact.selected_from?.doc_id;

  const displayValue = Array.isArray(fact.value)
    ? fact.value.join(", ")
    : fact.value !== null && fact.value !== undefined
      ? String(fact.value)
      : "\u2014";

  const truncatedValue =
    displayValue.length > 50 ? displayValue.slice(0, 47) + "..." : displayValue;

  const handleClick = () => {
    if (onViewSource && fact.selected_from) {
      onViewSource(
        fact.selected_from.doc_id,
        fact.selected_from.page,
        fact.selected_from.char_start,
        fact.selected_from.char_end
      );
    }
  };

  return (
    <div
      className={cn(
        "flex items-center gap-2 py-1 px-2 rounded transition-colors",
        hasSource && onViewSource ? "hover:bg-muted cursor-pointer" : ""
      )}
      onClick={hasSource ? handleClick : undefined}
      title={displayValue}
    >
      <span className="text-xs text-muted-foreground min-w-[120px] flex-shrink-0">
        {formatFieldName(fact.name)}
      </span>
      <span className="text-sm text-foreground truncate flex-1">
        {truncatedValue}
      </span>
      {hasSource && onViewSource && (
        <ExternalLink className="h-3 w-3 text-muted-foreground/50 flex-shrink-0" />
      )}
    </div>
  );
}
