import { useState, useEffect, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { cn } from "../lib/utils";
import {
  getInsightsOverview,
  getInsightsDocTypes,
  getInsightsPriorities,
  getInsightsFieldDetails,
  getInsightsExamples,
  type InsightsOverview,
  type DocTypeMetrics,
  type PriorityItem,
  type FieldDetails,
  type InsightExample,
} from "../api/client";

// Human-readable doc type names
const docTypeNames: Record<string, string> = {
  loss_notice: "Loss Notice",
  police_report: "Police Report",
  insurance_policy: "Insurance Policy",
};

// Human-readable field names
const fieldDisplayNames: Record<string, string> = {
  incident_date: "Incident Date",
  incident_location: "Incident Location",
  policy_number: "Policy Number",
  claimant_name: "Claimant Name",
  vehicle_plate: "Vehicle Plate",
  vehicle_make: "Vehicle Make",
  vehicle_model: "Vehicle Model",
  vehicle_year: "Vehicle Year",
  loss_description: "Loss Description",
  reported_date: "Report Date",
  report_date: "Report Date",
  report_number: "Report Number",
  officer_name: "Officer Name",
  badge_number: "Badge Number",
  location: "Location",
  claim_number: "Claim Number",
  coverage_start: "Coverage Start",
};

function getDocTypeName(docType: string): string {
  return docTypeNames[docType] || docType.replace(/_/g, " ");
}

function getFieldName(field: string): string {
  return fieldDisplayNames[field] || field.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

export function InsightsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const drilldownRef = useRef<HTMLDivElement>(null);

  // Data state
  const [overview, setOverview] = useState<InsightsOverview | null>(null);
  const [docTypes, setDocTypes] = useState<DocTypeMetrics[]>([]);
  const [priorities, setPriorities] = useState<PriorityItem[]>([]);
  const [fieldDetails, setFieldDetails] = useState<FieldDetails | null>(null);
  const [examples, setExamples] = useState<InsightExample[]>([]);

  // UI state
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters from URL params
  const selectedDocType = searchParams.get("doc_type") || null;
  const selectedField = searchParams.get("field") || null;
  const selectedOutcome = searchParams.get("outcome") || null;

  // Load initial data
  useEffect(() => {
    loadData();
  }, []);

  // Load field details and examples when selection changes
  useEffect(() => {
    if (selectedDocType && selectedField) {
      loadFieldDetails(selectedDocType, selectedField);
      loadExamples({ doc_type: selectedDocType, field: selectedField, outcome: selectedOutcome || undefined });
      // Scroll to drilldown
      setTimeout(() => {
        drilldownRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 100);
    } else if (selectedDocType) {
      loadExamples({ doc_type: selectedDocType, outcome: selectedOutcome || undefined });
      setFieldDetails(null);
    } else {
      setFieldDetails(null);
      setExamples([]);
    }
  }, [selectedDocType, selectedField, selectedOutcome]);

  async function loadData() {
    try {
      setLoading(true);
      setError(null);
      const [overviewData, docTypesData, prioritiesData] = await Promise.all([
        getInsightsOverview(),
        getInsightsDocTypes(),
        getInsightsPriorities(10),
      ]);
      setOverview(overviewData);
      setDocTypes(docTypesData);
      setPriorities(prioritiesData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load insights");
    } finally {
      setLoading(false);
    }
  }

  async function loadFieldDetails(docType: string, field: string) {
    try {
      const data = await getInsightsFieldDetails(docType, field);
      setFieldDetails(data);
    } catch {
      setFieldDetails(null);
    }
  }

  async function loadExamples(params: { doc_type?: string; field?: string; outcome?: string }) {
    try {
      const data = await getInsightsExamples({ ...params, limit: 30 });
      setExamples(data);
    } catch {
      setExamples([]);
    }
  }

  function handleDocTypeClick(docType: string) {
    if (selectedDocType === docType) {
      searchParams.delete("doc_type");
      searchParams.delete("field");
    } else {
      searchParams.set("doc_type", docType);
      searchParams.delete("field");
    }
    searchParams.delete("outcome");
    setSearchParams(searchParams);
  }

  function handlePriorityClick(item: PriorityItem) {
    searchParams.set("doc_type", item.doc_type);
    searchParams.set("field", item.field_name);
    searchParams.delete("outcome");
    setSearchParams(searchParams);
  }

  function handleOutcomeFilter(outcome: string | null) {
    if (outcome) {
      searchParams.set("outcome", outcome);
    } else {
      searchParams.delete("outcome");
    }
    setSearchParams(searchParams);
  }

  function handleOpenReview(example: InsightExample) {
    navigate(example.review_url);
  }

  function handleCopyLink() {
    navigator.clipboard.writeText(window.location.href);
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-gray-500">Loading insights...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full">
        <p className="text-red-600 mb-4">{error}</p>
        <button
          onClick={loadData}
          className="px-4 py-2 bg-gray-900 text-white rounded-md hover:bg-gray-800"
        >
          Retry
        </button>
      </div>
    );
  }

  // Calculate additional metrics
  const labelCompleteness = overview?.docs_total
    ? Math.round((overview.docs_reviewed / overview.docs_total) * 100)
    : 0;

  return (
    <div className="p-4 space-y-4 max-w-[1600px] mx-auto">
      {/* Section A: Overview KPIs - compact row */}
      <section className="grid grid-cols-3 md:grid-cols-6 gap-3">
        <KPICard
          label="Reviewed"
          value={`${overview?.docs_reviewed || 0}/${overview?.docs_total || 0}`}
          subtext={`${labelCompleteness}% complete`}
        />
        <KPICard
          label="Doc Type Wrong"
          value={overview?.docs_doc_type_wrong || 0}
          variant={overview?.docs_doc_type_wrong ? "warning" : "default"}
        />
        <KPICard
          label="Field Presence"
          value={`${overview?.required_field_presence_rate || 0}%`}
          variant={getScoreVariant(overview?.required_field_presence_rate || 0)}
        />
        <KPICard
          label="Field Accuracy"
          value={`${overview?.required_field_accuracy || 0}%`}
          variant={getScoreVariant(overview?.required_field_accuracy || 0)}
        />
        <KPICard
          label="Evidence Rate"
          value={`${overview?.evidence_rate || 0}%`}
          variant={getScoreVariant(overview?.evidence_rate || 0)}
        />
        <KPICard
          label="Needs Vision"
          value={overview?.docs_needs_vision || 0}
          subtext="candidates"
          variant="neutral"
        />
      </section>

      {/* Main row: Priorities (left) + Scoreboard (right) */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        {/* Calibration Priorities - takes 3 columns */}
        <section className="lg:col-span-3">
          <h2 className="text-sm font-semibold text-gray-700 mb-2">Calibration Priorities</h2>
          <div className="bg-white rounded-lg border shadow-sm max-h-[400px] overflow-y-auto">
            {priorities.length === 0 ? (
              <div className="p-4 text-gray-500 text-center text-sm">
                No priorities found. Review more documents to see insights.
              </div>
            ) : (
              <div className="divide-y">
                {priorities.map((item, idx) => (
                  <button
                    key={`${item.doc_type}-${item.field_name}`}
                    onClick={() => handlePriorityClick(item)}
                    className={cn(
                      "w-full text-left px-3 py-2 hover:bg-gray-50 transition-colors",
                      selectedDocType === item.doc_type && selectedField === item.field_name && "bg-blue-50 border-l-2 border-blue-500"
                    )}
                  >
                    {/* Line 1: DocType · Field + Required badge */}
                    <div className="flex items-center gap-1.5 text-sm">
                      <span className="text-gray-400 font-mono w-5">{idx + 1}.</span>
                      <span className="font-medium text-gray-900">{getDocTypeName(item.doc_type)}</span>
                      <span className="text-gray-400">·</span>
                      <span className="text-gray-700">{getFieldName(item.field_name)}</span>
                      {item.is_required && (
                        <span className="text-[10px] px-1 py-0.5 bg-red-100 text-red-600 rounded font-medium">REQ</span>
                      )}
                    </div>
                    {/* Line 2: Stats + action chip */}
                    <div className="flex items-center gap-2 mt-0.5 ml-5 text-xs">
                      <span className="text-gray-500">{item.affected_docs}/{item.total_labeled} affected</span>
                      <span className="text-gray-300">·</span>
                      {item.extractor_miss > 0 && <span className="text-yellow-600">{item.extractor_miss} miss</span>}
                      {item.incorrect > 0 && <span className="text-red-600">{item.incorrect} wrong</span>}
                      {item.evidence_missing > 0 && <span className="text-orange-500">{item.evidence_missing} no ev</span>}
                      <span className="ml-auto text-blue-600 truncate max-w-[140px]">{item.fix_bucket.replace("Improve ", "")}</span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </section>

        {/* Doc Type Scoreboard - takes 2 columns */}
        <section className="lg:col-span-2">
          <h2 className="text-sm font-semibold text-gray-700 mb-2">Doc Type Scoreboard</h2>
          <div className="bg-white rounded-lg border shadow-sm overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b bg-gray-50">
                  <th className="text-left p-2 font-medium">Type</th>
                  <th className="text-right p-2 font-medium w-12">Rev</th>
                  <th className="text-right p-2 font-medium w-14">Pres</th>
                  <th className="text-right p-2 font-medium w-14">Acc</th>
                  <th className="text-right p-2 font-medium w-14">Evid</th>
                  <th className="text-left p-2 font-medium">Top Issue</th>
                </tr>
              </thead>
              <tbody>
                {docTypes.map((dt) => (
                  <tr
                    key={dt.doc_type}
                    onClick={() => handleDocTypeClick(dt.doc_type)}
                    className={cn(
                      "border-b cursor-pointer hover:bg-gray-50 transition-colors",
                      selectedDocType === dt.doc_type && "bg-blue-50"
                    )}
                  >
                    <td className="p-2 font-medium">
                      {getDocTypeName(dt.doc_type)}
                      {dt.docs_needs_vision > 0 && (
                        <span className="ml-1 text-purple-500" title={`${dt.docs_needs_vision} need vision`}>
                          <VisionIcon className="w-3 h-3 inline" />
                        </span>
                      )}
                    </td>
                    <td className="p-2 text-right text-gray-600">{dt.docs_reviewed}</td>
                    <td className="p-2 text-right">
                      <ScoreBadge value={dt.required_field_presence_pct} />
                    </td>
                    <td className="p-2 text-right">
                      <ScoreBadge value={dt.required_field_accuracy_pct} />
                    </td>
                    <td className="p-2 text-right">
                      <ScoreBadge value={dt.evidence_rate_pct} />
                    </td>
                    <td className="p-2 text-gray-600 truncate max-w-[80px]" title={dt.top_failing_field || ""}>
                      {dt.top_failing_field ? getFieldName(dt.top_failing_field) : "-"}
                    </td>
                  </tr>
                ))}
                {docTypes.length === 0 && (
                  <tr>
                    <td colSpan={6} className="p-3 text-center text-gray-500">
                      No data
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      {/* Section D: Drilldown - full width */}
      {(selectedDocType || fieldDetails) && (
        <section ref={drilldownRef} className="bg-white rounded-lg border shadow-sm">
          {/* Header with title + metrics + actions */}
          <div className="flex items-center justify-between p-3 border-b bg-gray-50">
            <div className="flex items-center gap-3">
              <h2 className="text-sm font-semibold">
                {fieldDetails
                  ? `${getDocTypeName(fieldDetails.doc_type)} · ${getFieldName(fieldDetails.field_name)}`
                  : selectedDocType
                  ? `${getDocTypeName(selectedDocType)} Examples`
                  : "Details"}
              </h2>
              {fieldDetails && (
                <div className="flex items-center gap-2 text-xs">
                  <span className="px-1.5 py-0.5 bg-gray-100 rounded">
                    Pres: <strong>{fieldDetails.rates.presence_pct}%</strong>
                  </span>
                  <span className="px-1.5 py-0.5 bg-gray-100 rounded">
                    Acc: <strong>{fieldDetails.rates.accuracy_pct}%</strong>
                  </span>
                  <span className="px-1.5 py-0.5 bg-gray-100 rounded">
                    Evid: <strong>{fieldDetails.rates.evidence_pct}%</strong>
                  </span>
                </div>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleCopyLink}
                className="text-xs text-gray-500 hover:text-gray-700 px-2 py-1 rounded hover:bg-gray-100"
                title="Copy link to this view"
              >
                Copy link
              </button>
              <button
                onClick={() => {
                  searchParams.delete("doc_type");
                  searchParams.delete("field");
                  searchParams.delete("outcome");
                  setSearchParams(searchParams);
                }}
                className="text-xs text-gray-500 hover:text-gray-700 px-2 py-1 rounded hover:bg-gray-100"
              >
                Clear
              </button>
            </div>
          </div>

          {/* Compact outcome filters */}
          {fieldDetails && (
            <div className="flex items-center gap-2 p-3 border-b">
              <OutcomeChip
                label="Correct"
                count={fieldDetails.breakdown.correct}
                variant="success"
                selected={selectedOutcome === "correct"}
                onClick={() => handleOutcomeFilter(selectedOutcome === "correct" ? null : "correct")}
              />
              <OutcomeChip
                label="Incorrect"
                count={fieldDetails.breakdown.incorrect}
                variant="error"
                selected={selectedOutcome === "incorrect"}
                onClick={() => handleOutcomeFilter(selectedOutcome === "incorrect" ? null : "incorrect")}
              />
              <OutcomeChip
                label="Miss"
                count={fieldDetails.breakdown.extractor_miss}
                variant="warning"
                selected={selectedOutcome === "extractor_miss"}
                onClick={() => handleOutcomeFilter(selectedOutcome === "extractor_miss" ? null : "extractor_miss")}
              />
              <OutcomeChip
                label="No Evidence"
                count={fieldDetails.breakdown.evidence_missing}
                variant="info"
                selected={selectedOutcome === "evidence_missing"}
                onClick={() => handleOutcomeFilter(selectedOutcome === "evidence_missing" ? null : "evidence_missing")}
              />
              <OutcomeChip
                label="Unknown"
                count={fieldDetails.breakdown.cannot_verify}
                variant="neutral"
                selected={selectedOutcome === "cannot_verify"}
                onClick={() => handleOutcomeFilter(selectedOutcome === "cannot_verify" ? null : "cannot_verify")}
              />
            </div>
          )}

          {/* Examples table */}
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b bg-gray-50">
                  <th className="text-left p-2 font-medium">Claim</th>
                  <th className="text-left p-2 font-medium">Filename</th>
                  {!selectedField && <th className="text-left p-2 font-medium">Field</th>}
                  <th className="text-left p-2 font-medium">Extracted</th>
                  <th className="text-center p-2 font-medium">Label</th>
                  <th className="text-center p-2 font-medium">Evid</th>
                  <th className="text-center p-2 font-medium">Outcome</th>
                  <th className="text-left p-2 font-medium w-12"></th>
                </tr>
              </thead>
              <tbody>
                {examples.map((ex, idx) => (
                  <tr key={`${ex.doc_id}-${ex.field_name}-${idx}`} className="border-b hover:bg-gray-50">
                    <td className="p-2 font-mono text-[10px]">{ex.claim_id}</td>
                    <td className="p-2 truncate max-w-[140px]" title={ex.filename}>
                      {ex.filename}
                    </td>
                    {!selectedField && (
                      <td className="p-2">{getFieldName(ex.field_name)}</td>
                    )}
                    <td className="p-2 font-mono text-[10px] truncate max-w-[120px]" title={ex.normalized_value || ex.predicted_value || ""}>
                      {ex.normalized_value || ex.predicted_value || <span className="text-gray-400">-</span>}
                    </td>
                    <td className="p-2 text-center">
                      <JudgementBadge judgement={ex.judgement} />
                    </td>
                    <td className="p-2 text-center">
                      {ex.has_evidence ? (
                        <span className="text-green-600">Y</span>
                      ) : (
                        <span className="text-gray-300">-</span>
                      )}
                      {ex.needs_vision && (
                        <VisionIcon className="w-3 h-3 inline ml-1 text-purple-500" />
                      )}
                    </td>
                    <td className="p-2 text-center">
                      <OutcomeBadge outcome={ex.outcome} />
                    </td>
                    <td className="p-2">
                      <button
                        onClick={() => handleOpenReview(ex)}
                        className="text-blue-600 hover:text-blue-800 hover:underline"
                      >
                        Open
                      </button>
                    </td>
                  </tr>
                ))}
                {examples.length === 0 && (
                  <tr>
                    <td colSpan={selectedField ? 7 : 8} className="p-4 text-center text-gray-500">
                      No examples found
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}

// Helper components

function getScoreVariant(score: number): "success" | "warning" | "error" | "default" | "neutral" {
  if (score >= 80) return "success";
  if (score >= 60) return "warning";
  if (score > 0) return "error";
  return "default";
}

interface KPICardProps {
  label: string;
  value: string | number;
  subtext?: string;
  variant?: "default" | "success" | "warning" | "error" | "neutral";
}

function KPICard({ label, value, subtext, variant = "default" }: KPICardProps) {
  const variants = {
    default: "bg-white",
    success: "bg-green-50 border-green-200",
    warning: "bg-yellow-50 border-yellow-200",
    error: "bg-red-50 border-red-200",
    neutral: "bg-gray-50",
  };

  return (
    <div className={cn("rounded-lg border p-3 shadow-sm", variants[variant])}>
      <div className="text-xl font-bold">{value}</div>
      <div className="text-xs text-gray-600">{label}</div>
      {subtext && <div className="text-[10px] text-gray-400">{subtext}</div>}
    </div>
  );
}

function ScoreBadge({ value }: { value: number }) {
  const color =
    value >= 80 ? "text-green-600" : value >= 60 ? "text-yellow-600" : "text-red-600";
  return <span className={cn("font-medium", color)}>{value}%</span>;
}

interface OutcomeChipProps {
  label: string;
  count: number;
  variant: "success" | "error" | "warning" | "info" | "neutral";
  selected: boolean;
  onClick: () => void;
}

function OutcomeChip({ label, count, variant, selected, onClick }: OutcomeChipProps) {
  const variants = {
    success: "border-green-300 bg-green-50 text-green-700",
    error: "border-red-300 bg-red-50 text-red-700",
    warning: "border-yellow-300 bg-yellow-50 text-yellow-700",
    info: "border-orange-300 bg-orange-50 text-orange-700",
    neutral: "border-gray-300 bg-gray-50 text-gray-700",
  };

  return (
    <button
      onClick={onClick}
      className={cn(
        "px-2 py-1 rounded border text-xs font-medium transition-all",
        variants[variant],
        selected && "ring-2 ring-blue-500 ring-offset-1"
      )}
    >
      {label}: {count}
    </button>
  );
}

function JudgementBadge({ judgement }: { judgement: string | null }) {
  if (!judgement) return <span className="text-gray-300">-</span>;

  const styles: Record<string, string> = {
    correct: "bg-green-100 text-green-700",
    incorrect: "bg-red-100 text-red-700",
    unknown: "bg-gray-100 text-gray-600",
  };

  const labels: Record<string, string> = {
    correct: "OK",
    incorrect: "ERR",
    unknown: "?",
  };

  return (
    <span className={cn("text-[10px] px-1 py-0.5 rounded font-medium", styles[judgement] || styles.unknown)}>
      {labels[judgement] || judgement}
    </span>
  );
}

function OutcomeBadge({ outcome }: { outcome: string | null }) {
  if (!outcome) return <span className="text-gray-300">-</span>;

  const styles: Record<string, string> = {
    correct: "bg-green-100 text-green-700",
    incorrect: "bg-red-100 text-red-700",
    extractor_miss: "bg-yellow-100 text-yellow-700",
    cannot_verify: "bg-gray-100 text-gray-600",
    correct_absent: "bg-gray-100 text-gray-600",
  };

  const labels: Record<string, string> = {
    correct: "OK",
    incorrect: "ERR",
    extractor_miss: "MISS",
    cannot_verify: "?",
    correct_absent: "OK-",
  };

  return (
    <span className={cn("text-[10px] px-1 py-0.5 rounded font-medium", styles[outcome] || "bg-gray-100 text-gray-600")}>
      {labels[outcome] || outcome}
    </span>
  );
}

function VisionIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
    </svg>
  );
}
