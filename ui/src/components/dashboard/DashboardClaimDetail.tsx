import { useState, useEffect, useCallback } from "react";
import { getDashboardClaimDetail, getClaimFacts, listDocs } from "../../api/client";
import { DocumentSlidePanel } from "../ClaimExplorer/DocumentSlidePanel";
import type { EvidenceLocation } from "../ClaimExplorer/DocumentSlidePanel";
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

type Tab = "checks" | "coverage" | "payout" | "documents" | "facts";

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
        <button onClick={() => setTab("documents")} className={tabClass("documents")}>
          Documents ({documents.length})
        </button>
        <button onClick={() => setTab("facts")} className={tabClass("facts")}>
          Facts
        </button>
      </div>

      <div className="p-4">
        {tab === "checks" && <ChecksTab detail={detail} />}
        {tab === "coverage" && <CoverageTab detail={detail} />}
        {tab === "payout" && <PayoutTab detail={detail} />}
        {tab === "documents" && (
          <DocumentsTab documents={documents} onViewSource={handleViewSource} />
        )}
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
   Assessment Checks Tab
   ============================================================ */
function ChecksTab({ detail }: { detail: DetailType }) {
  const checks = [
    ...(detail.screening_checks.length > 0
      ? [{ section: "Screening Checks", items: detail.screening_checks }]
      : []),
    ...(detail.assessment_checks.length > 0
      ? [{ section: "Assessment Checks", items: detail.assessment_checks }]
      : []),
  ];

  if (checks.length === 0) {
    return <p className="text-sm text-slate-500 dark:text-slate-400">No check data.</p>;
  }

  return (
    <div className="space-y-4">
      {checks.map((group) => (
        <div key={group.section}>
          <h4 className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-2">
            {group.section}
          </h4>
          <div className="space-y-1">
            {group.items.map((check, i) => {
              const result = String(
                check.result || check.verdict || ""
              ).toUpperCase();
              const badgeColor =
                result === "PASS"
                  ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400"
                  : result === "FAIL"
                    ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
                    : result === "SKIPPED"
                      ? "bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400"
                      : "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400";
              return (
                <div
                  key={i}
                  className="flex items-start gap-2 py-1.5 text-sm"
                >
                  <span
                    className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium ${badgeColor}`}
                  >
                    {result || "N/A"}
                  </span>
                  <span className="text-slate-700 dark:text-slate-200 font-medium">
                    {String(check.check_name || check.check_id || `Check ${i + 1}`)}
                  </span>
                  <span className="text-slate-500 dark:text-slate-400 text-xs">
                    {String(check.details || check.reason || "")}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

/* ============================================================
   Coverage Details Tab
   ============================================================ */
function CoverageTab({ detail }: { detail: DetailType }) {
  if (detail.coverage_items.length === 0) {
    return <p className="text-sm text-slate-500 dark:text-slate-400">No coverage data.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-slate-200 dark:border-slate-700">
            <th className="text-left py-2 px-2 font-medium text-slate-600 dark:text-slate-300">
              Code
            </th>
            <th className="text-left py-2 px-2 font-medium text-slate-600 dark:text-slate-300">
              Description
            </th>
            <th className="text-left py-2 px-2 font-medium text-slate-600 dark:text-slate-300">
              Type
            </th>
            <th className="text-right py-2 px-2 font-medium text-slate-600 dark:text-slate-300">
              Price
            </th>
            <th className="text-center py-2 px-2 font-medium text-slate-600 dark:text-slate-300">
              Status
            </th>
            <th className="text-left py-2 px-2 font-medium text-slate-600 dark:text-slate-300">
              Component
            </th>
            <th className="text-left py-2 px-2 font-medium text-slate-600 dark:text-slate-300">
              Reasoning
            </th>
          </tr>
        </thead>
        <tbody>
          {detail.coverage_items.map((item, i) => {
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
                <td className={`py-1.5 px-2 text-center font-medium ${statusColor}`}>
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
  const getDiff = (sys: unknown, gt: unknown): { text: string; color: string } => {
    if (typeof sys !== "number" || typeof gt !== "number") return { text: "", color: "" };
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
                <td className={`py-1.5 px-2 text-right font-mono ${diff.color}`}>
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
   Documents Tab — just a list, clicking opens the shared slide panel
   ============================================================ */
function DocumentsTab({
  documents,
  onViewSource,
}: {
  documents: DashboardClaimDoc[];
  onViewSource: (docId: string, page: number | null, charStart: number | null, charEnd: number | null) => void;
}) {
  if (documents.length === 0) {
    return (
      <p className="text-sm text-slate-500 dark:text-slate-400">
        No documents for this claim.
      </p>
    );
  }

  return (
    <div className="space-y-1">
      {documents.map((doc) => (
        <button
          key={doc.doc_id}
          onClick={() => onViewSource(doc.doc_id, null, null, null)}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-md text-left transition-colors hover:bg-slate-100 dark:hover:bg-slate-700/50"
        >
          <span className="text-slate-400 dark:text-slate-500">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
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
  );
}

/* ============================================================
   Facts Tab — with onViewSource for evidence highlighting
   ============================================================ */

const DOC_TYPE_LABELS: Record<string, string> = {
  vehicle_registration: "Vehicle Information",
  service_history: "Service History",
  nsa_guarantee: "Policy Details",
  cost_estimate: "Cost Estimate",
  fnol_form: "First Notice of Loss",
  police_report: "Police Report",
  damage_assessment: "Damage Assessment",
  invoice: "Invoice",
  unknown: "Other",
};

function getDocTypeLabel(docType: string): string {
  return DOC_TYPE_LABELS[docType] || formatDocType(docType);
}

function formatFieldName(name: string): string {
  return name
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function formatValue(value: string | string[] | null): string {
  if (value === null || value === undefined) return "\u2014";
  if (Array.isArray(value)) return value.join(", ");
  return value;
}

function FactsTab({
  claimId,
  onViewSource,
}: {
  claimId: string;
  onViewSource: (docId: string, page: number | null, charStart: number | null, charEnd: number | null) => void;
}) {
  const [facts, setFacts] = useState<ClaimFacts | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getClaimFacts(claimId)
      .then((d) => {
        if (!cancelled) {
          setFacts(d);
          if (d && d.facts.length > 0) {
            const docTypes = new Set<string>();
            for (const fact of d.facts) {
              docTypes.add(fact.selected_from?.doc_type || "unknown");
            }
            const sorted = [...docTypes];
            setExpandedGroups(new Set(sorted.slice(0, 3)));
          }
        }
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
      <p className="text-sm text-slate-500 dark:text-slate-400">Loading facts...</p>
    );
  }

  if (!facts || facts.facts.length === 0) {
    return (
      <p className="text-sm text-slate-500 dark:text-slate-400">
        No facts aggregated for this claim.
      </p>
    );
  }

  // Group facts by source doc_type
  const grouped: Record<string, AggregatedFact[]> = {};
  for (const fact of facts.facts) {
    const docType = fact.selected_from?.doc_type || "unknown";
    if (!grouped[docType]) grouped[docType] = [];
    grouped[docType].push(fact);
  }

  const docTypePriority = [
    "vehicle_registration",
    "nsa_guarantee",
    "service_history",
    "cost_estimate",
    "fnol_form",
    "police_report",
    "damage_assessment",
    "invoice",
  ];

  const sortedDocTypes = Object.keys(grouped).sort((a, b) => {
    const aIndex = docTypePriority.indexOf(a);
    const bIndex = docTypePriority.indexOf(b);
    if (aIndex === -1 && bIndex === -1) return a.localeCompare(b);
    if (aIndex === -1) return 1;
    if (bIndex === -1) return -1;
    return aIndex - bIndex;
  });

  const toggleGroup = (docType: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(docType)) {
        next.delete(docType);
      } else {
        next.add(docType);
      }
      return next;
    });
  };

  return (
    <div>
      {sortedDocTypes.map((docType) => {
        const isExpanded = expandedGroups.has(docType);
        const groupFacts = grouped[docType];
        return (
          <div key={docType} className="mb-3 last:mb-0">
            <button
              onClick={() => toggleGroup(docType)}
              className="flex items-center gap-2 w-full text-left py-1.5 hover:bg-slate-100 dark:hover:bg-slate-700/30 rounded -mx-1 px-1 transition-colors"
            >
              <span className="text-xs text-slate-400">
                {isExpanded ? "\u25BC" : "\u25B6"}
              </span>
              <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">
                {getDocTypeLabel(docType)}
              </span>
              <span className="text-[10px] text-slate-400">
                ({groupFacts.length})
              </span>
            </button>
            {isExpanded && (
              <div className="ml-5 mt-1 border-l-2 border-slate-200 dark:border-slate-700/50 pl-3">
                {groupFacts.map((fact) => (
                  <FactRow
                    key={fact.name}
                    fact={fact}
                    onViewSource={onViewSource}
                  />
                ))}
              </div>
            )}
          </div>
        );
      })}
      <div className="text-[10px] text-slate-400 mt-4 pt-3 border-t border-slate-200 dark:border-slate-700">
        Generated {new Date(facts.generated_at).toLocaleString()} from{" "}
        {facts.sources.length} source{facts.sources.length !== 1 ? "s" : ""}
      </div>
    </div>
  );
}

/** Single fact row with optional "view source" button */
function FactRow({
  fact,
  onViewSource,
}: {
  fact: AggregatedFact;
  onViewSource: (docId: string, page: number | null, charStart: number | null, charEnd: number | null) => void;
}) {
  const hasProvenance = !!fact.selected_from?.doc_id;

  const handleViewSource = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (fact.selected_from) {
      onViewSource(
        fact.selected_from.doc_id,
        fact.selected_from.page,
        fact.selected_from.char_start,
        fact.selected_from.char_end
      );
    }
  };

  const hasStructured =
    fact.structured_value !== undefined && fact.structured_value !== null;

  if (hasStructured) {
    return (
      <div className="py-2">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-slate-700 dark:text-slate-200">
            {formatFieldName(fact.name)}
          </span>
          {hasProvenance && (
            <button
              onClick={handleViewSource}
              className="text-slate-400 hover:text-primary transition-colors"
              title="View source document"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                <polyline points="15 3 21 3 21 9" />
                <line x1="10" y1="14" x2="21" y2="3" />
              </svg>
            </button>
          )}
        </div>
        <div className="text-[10px] text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-slate-800 p-2 rounded overflow-x-auto ml-3 mt-1">
          <pre className="whitespace-pre-wrap">
            {JSON.stringify(fact.structured_value, null, 2)}
          </pre>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 py-1.5 group">
      <span className="text-xs text-slate-500 dark:text-slate-400 min-w-[100px] flex-shrink-0">
        {formatFieldName(fact.name)}
      </span>
      <span className="text-xs font-medium text-slate-700 dark:text-slate-200 flex-1 truncate">
        {formatValue(fact.value)}
      </span>
      {hasProvenance && (
        <button
          onClick={handleViewSource}
          className="opacity-0 group-hover:opacity-100 transition-opacity text-slate-400 hover:text-primary flex-shrink-0"
          title="View source document"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
            <polyline points="15 3 21 3 21 9" />
            <line x1="10" y1="14" x2="21" y2="3" />
          </svg>
        </button>
      )}
    </div>
  );
}
