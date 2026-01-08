import { useState, useEffect, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { cn } from "../lib/utils";
import {
  getInsightsFieldDetails,
  getInsightsExamples,
  getInsightsRuns,
  getRunOverview,
  getRunDocTypes,
  getRunPriorities,
  getDetailedRuns,
  compareRuns,
  getBaseline,
  setBaseline,
  clearBaseline,
  type InsightsOverview,
  type DocTypeMetrics,
  type PriorityItem,
  type FieldDetails,
  type InsightExample,
  type RunInfo,
  type RunComparison,
  type DetailedRunInfo,
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

function formatTimestamp(ts: string | null): string {
  if (!ts) return "Unknown";
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

type ViewTab = "insights" | "history" | "compare";

export function InsightsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const drilldownRef = useRef<HTMLDivElement>(null);

  // View state
  const [activeTab, setActiveTab] = useState<ViewTab>("insights");

  // Run state
  const [runs, setRuns] = useState<RunInfo[]>([]);
  const [detailedRuns, setDetailedRuns] = useState<DetailedRunInfo[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedDetailedRun, setSelectedDetailedRun] = useState<DetailedRunInfo | null>(null);
  const [baselineRunId, setBaselineRunId] = useState<string | null>(null);
  const [runMetadata, setRunMetadata] = useState<Record<string, unknown> | null>(null);

  // Insights data state
  const [overview, setOverview] = useState<InsightsOverview | null>(null);
  const [docTypes, setDocTypes] = useState<DocTypeMetrics[]>([]);
  const [priorities, setPriorities] = useState<PriorityItem[]>([]);
  const [fieldDetails, setFieldDetails] = useState<FieldDetails | null>(null);
  const [examples, setExamples] = useState<InsightExample[]>([]);

  // Comparison state
  const [comparison, setComparison] = useState<RunComparison | null>(null);
  const [compareBaselineId, setCompareBaselineId] = useState<string | null>(null);
  const [compareCurrentId, setCompareCurrentId] = useState<string | null>(null);

  // UI state
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters from URL params
  const selectedDocType = searchParams.get("doc_type") || null;
  const selectedField = searchParams.get("field") || null;
  const selectedOutcome = searchParams.get("outcome") || null;

  // Load runs and baseline on mount
  useEffect(() => {
    loadRuns();
    loadBaseline();
  }, []);

  // Load data when run selection changes
  useEffect(() => {
    if (selectedRunId) {
      loadRunData(selectedRunId);
    }
  }, [selectedRunId]);

  // Load field details and examples when selection changes
  useEffect(() => {
    if (selectedDocType && selectedField) {
      loadFieldDetails(selectedDocType, selectedField);
      loadExamples({ doc_type: selectedDocType, field: selectedField, outcome: selectedOutcome || undefined });
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

  // Load comparison when both runs selected
  useEffect(() => {
    if (compareBaselineId && compareCurrentId && compareBaselineId !== compareCurrentId) {
      loadComparison(compareBaselineId, compareCurrentId);
    } else {
      setComparison(null);
    }
  }, [compareBaselineId, compareCurrentId]);

  async function loadRuns() {
    try {
      const [runsData, detailedData] = await Promise.all([
        getInsightsRuns(),
        getDetailedRuns(),
      ]);
      setRuns(runsData);
      setDetailedRuns(detailedData);
      // Auto-select latest run if none selected
      if (runsData.length > 0 && !selectedRunId) {
        setSelectedRunId(runsData[0].run_id);
        const detailed = detailedData.find((r) => r.run_id === runsData[0].run_id);
        setSelectedDetailedRun(detailed || null);
      }
    } catch (err) {
      console.error("Failed to load runs:", err);
    }
  }

  async function loadBaseline() {
    try {
      const data = await getBaseline();
      setBaselineRunId(data.baseline_run_id);
      setCompareBaselineId(data.baseline_run_id);
    } catch {
      // Ignore
    }
  }

  async function loadRunData(runId: string) {
    try {
      setLoading(true);
      setError(null);

      const [overviewData, docTypesData, prioritiesData] = await Promise.all([
        getRunOverview(runId),
        getRunDocTypes(runId),
        getRunPriorities(runId, 10),
      ]);

      setRunMetadata(overviewData.run_metadata);
      setOverview(overviewData.overview);
      setDocTypes(docTypesData);
      setPriorities(prioritiesData);

      // Update selected detailed run for classification distribution
      const detailed = detailedRuns.find((r) => r.run_id === runId);
      setSelectedDetailedRun(detailed || null);
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

  async function loadComparison(baselineId: string, currentId: string) {
    try {
      const data = await compareRuns(baselineId, currentId);
      setComparison(data);
    } catch (err) {
      console.error("Failed to compare runs:", err);
      setComparison(null);
    }
  }

  async function handleSetBaseline(runId: string) {
    try {
      await setBaseline(runId);
      setBaselineRunId(runId);
      setCompareBaselineId(runId);
    } catch (err) {
      console.error("Failed to set baseline:", err);
    }
  }

  async function handleClearBaseline() {
    try {
      await clearBaseline();
      setBaselineRunId(null);
    } catch (err) {
      console.error("Failed to clear baseline:", err);
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

  if (loading && !overview) {
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
          onClick={() => selectedRunId && loadRunData(selectedRunId)}
          className="px-4 py-2 bg-gray-900 text-white rounded-md hover:bg-gray-800"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="p-4 space-y-4 max-w-[1600px] mx-auto">
      {/* Run Context Header */}
      <div className="bg-white rounded-lg border shadow-sm p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            {/* Run Selector */}
            <div className="flex items-center gap-2">
              <label className="text-sm font-medium text-gray-700">Run:</label>
              <select
                data-testid="run-selector"
                value={selectedRunId || ""}
                onChange={(e) => setSelectedRunId(e.target.value)}
                className="border rounded px-2 py-1 text-sm min-w-[180px]"
              >
                {runs.map((run) => (
                  <option key={run.run_id} value={run.run_id}>
                    {run.run_id} {run.run_id === runs[0]?.run_id ? "(Latest)" : ""}
                  </option>
                ))}
              </select>
            </div>

            {/* Run Metadata */}
            {runMetadata && (
              <div data-testid="run-metadata" className="flex items-center gap-4 text-xs text-gray-500 border-l pl-4">
                <span>
                  <strong>Time:</strong> {formatTimestamp(String(runMetadata.timestamp || ""))}
                </span>
                {Boolean(runMetadata.model) && (
                  <span>
                    <strong>Model:</strong> {String(runMetadata.model)}
                  </span>
                )}
                {Boolean(runMetadata.extractor_version) && (
                  <span>
                    <strong>Extractor:</strong> {String(runMetadata.extractor_version)}
                  </span>
                )}
                <span>
                  <strong>Docs:</strong> {Number(runMetadata.docs_total) || 0}
                </span>
              </div>
            )}
          </div>

          {/* Baseline Controls */}
          <div className="flex items-center gap-2">
            {baselineRunId && (
              <span className="text-xs text-green-600 bg-green-50 px-2 py-1 rounded">
                Baseline: {baselineRunId}
              </span>
            )}
            {selectedRunId && selectedRunId !== baselineRunId && (
              <button
                onClick={() => handleSetBaseline(selectedRunId)}
                className="text-xs px-2 py-1 bg-blue-100 text-blue-700 rounded hover:bg-blue-200"
              >
                Set as Baseline
              </button>
            )}
            {baselineRunId && (
              <button
                onClick={handleClearBaseline}
                className="text-xs px-2 py-1 text-gray-500 hover:text-gray-700"
              >
                Clear
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-1 border-b">
        <button
          onClick={() => setActiveTab("insights")}
          className={cn(
            "px-4 py-2 text-sm font-medium border-b-2 -mb-px",
            activeTab === "insights"
              ? "border-blue-500 text-blue-600"
              : "border-transparent text-gray-500 hover:text-gray-700"
          )}
        >
          Insights
        </button>
        <button
          onClick={() => setActiveTab("history")}
          className={cn(
            "px-4 py-2 text-sm font-medium border-b-2 -mb-px",
            activeTab === "history"
              ? "border-blue-500 text-blue-600"
              : "border-transparent text-gray-500 hover:text-gray-700"
          )}
        >
          Run History
        </button>
        <button
          onClick={() => setActiveTab("compare")}
          className={cn(
            "px-4 py-2 text-sm font-medium border-b-2 -mb-px",
            activeTab === "compare"
              ? "border-blue-500 text-blue-600"
              : "border-transparent text-gray-500 hover:text-gray-700"
          )}
        >
          Compare Runs
        </button>
      </div>

      {/* Tab Content */}
      {activeTab === "insights" && (
        <InsightsTab
          overview={overview}
          docTypes={docTypes}
          priorities={priorities}
          fieldDetails={fieldDetails}
          examples={examples}
          selectedDocType={selectedDocType}
          selectedField={selectedField}
          selectedOutcome={selectedOutcome}
          baselineRunId={baselineRunId}
          selectedDetailedRun={selectedDetailedRun}
          onDocTypeClick={handleDocTypeClick}
          onPriorityClick={handlePriorityClick}
          onOutcomeFilter={handleOutcomeFilter}
          onOpenReview={handleOpenReview}
          onCopyLink={handleCopyLink}
          onClearSelection={() => {
            searchParams.delete("doc_type");
            searchParams.delete("field");
            searchParams.delete("outcome");
            setSearchParams(searchParams);
          }}
          drilldownRef={drilldownRef}
        />
      )}

      {activeTab === "history" && (
        <RunHistoryTab
          runs={runs}
          baselineRunId={baselineRunId}
          selectedRunId={selectedRunId}
          onSelectRun={setSelectedRunId}
          onSetBaseline={handleSetBaseline}
        />
      )}

      {activeTab === "compare" && (
        <CompareRunsTab
          runs={runs}
          baselineId={compareBaselineId}
          currentId={compareCurrentId}
          comparison={comparison}
          onBaselineChange={setCompareBaselineId}
          onCurrentChange={setCompareCurrentId}
        />
      )}
    </div>
  );
}

// =============================================================================
// Insights Tab
// =============================================================================

interface InsightsTabProps {
  overview: InsightsOverview | null;
  docTypes: DocTypeMetrics[];
  priorities: PriorityItem[];
  fieldDetails: FieldDetails | null;
  examples: InsightExample[];
  selectedDocType: string | null;
  selectedField: string | null;
  selectedOutcome: string | null;
  baselineRunId: string | null;
  selectedDetailedRun: DetailedRunInfo | null;
  onDocTypeClick: (docType: string) => void;
  onPriorityClick: (item: PriorityItem) => void;
  onOutcomeFilter: (outcome: string | null) => void;
  onOpenReview: (example: InsightExample) => void;
  onCopyLink: () => void;
  onClearSelection: () => void;
  drilldownRef: React.RefObject<HTMLDivElement>;
}

function InsightsTab({
  overview,
  docTypes,
  priorities,
  fieldDetails,
  examples,
  selectedDocType,
  selectedField,
  selectedOutcome,
  selectedDetailedRun,
  onDocTypeClick,
  onPriorityClick,
  onOutcomeFilter,
  onOpenReview,
  onCopyLink,
  onClearSelection,
  drilldownRef,
}: InsightsTabProps) {
  return (
    <div className="space-y-4">
      {/* Overview KPIs */}
      <section className="grid grid-cols-3 md:grid-cols-5 gap-3">
        <KPICard
          label="Doc Coverage"
          value={`${overview?.docs_with_truth || 0}/${overview?.docs_total || 0}`}
          subtext="docs with truth labels"
        />
        <KPICard
          label="Field Coverage"
          value={`${overview?.labeled_fields || overview?.confirmed_fields || 0}/${overview?.total_fields || 0}`}
          subtext="labeled fields"
        />
        <KPICard
          label="Accuracy"
          value={`${overview?.accuracy_rate || 0}%`}
          subtext={`${overview?.correct_count || overview?.match_count || 0} correct / ${(overview?.correct_count || overview?.match_count || 0) + (overview?.incorrect_count || overview?.mismatch_count || 0) + (overview?.missing_count || overview?.miss_count || 0)} total`}
          variant={getScoreVariant(overview?.accuracy_rate || 0)}
        />
        <KPICard
          label="Evidence Rate"
          value={`${overview?.evidence_rate || 0}%`}
          variant={getScoreVariant(overview?.evidence_rate || 0)}
        />
        <KPICard
          label="Doc Type Wrong"
          value={overview?.docs_doc_type_wrong || 0}
          variant={overview?.docs_doc_type_wrong ? "warning" : "default"}
        />
      </section>

      {/* Main row: Priorities + Scoreboard */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        {/* Top Error Drivers */}
        <section className="lg:col-span-3">
          <h2 className="text-sm font-semibold text-gray-700 mb-2">Top Error Drivers</h2>
          <div className="bg-white rounded-lg border shadow-sm max-h-[400px] overflow-y-auto">
            {priorities.length === 0 ? (
              <div className="p-4 text-gray-500 text-center text-sm">
                No error drivers found. Add truth labels to see insights.
              </div>
            ) : (
              <div className="divide-y">
                {priorities.map((item, idx) => (
                  <button
                    key={`${item.doc_type}-${item.field_name}`}
                    onClick={() => onPriorityClick(item)}
                    className={cn(
                      "w-full text-left px-3 py-2 hover:bg-gray-50 transition-colors",
                      selectedDocType === item.doc_type && selectedField === item.field_name && "bg-blue-50 border-l-2 border-blue-500"
                    )}
                  >
                    <div className="flex items-center gap-1.5 text-sm">
                      <span className="text-gray-400 font-mono w-5">{idx + 1}.</span>
                      <span className="font-medium text-gray-900">{getDocTypeName(item.doc_type)}</span>
                      <span className="text-gray-400">·</span>
                      <span className="text-gray-700">{getFieldName(item.field_name)}</span>
                      {item.is_required && (
                        <span className="text-[10px] px-1.5 py-0.5 bg-red-100 text-red-600 rounded font-medium">Required</span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 mt-0.5 ml-5 text-xs">
                      <span className="text-gray-500">{item.error_rate}% error rate</span>
                      <span className="text-gray-300">·</span>
                      {(item.incorrect_count ?? item.mismatch_count ?? 0) > 0 && <span className="text-red-600">{item.incorrect_count ?? item.mismatch_count ?? 0} incorrect</span>}
                      {(item.missing_count ?? item.miss_count ?? 0) > 0 && <span className="text-yellow-600">{item.missing_count ?? item.miss_count ?? 0} missing</span>}
                      <span className="ml-auto text-gray-500">{item.total_labeled ?? item.total_confirmed ?? 0} labeled</span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </section>

        {/* Doc Type Scoreboard */}
        <section className="lg:col-span-2">
          <h2 className="text-sm font-semibold text-gray-700 mb-2">Doc Type Scoreboard</h2>
          <div className="bg-white rounded-lg border shadow-sm overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b bg-gray-50">
                  <th className="text-left p-2 font-medium">Type</th>
                  <th className="text-right p-2 font-medium">Classified</th>
                  <th className="text-right p-2 font-medium">Extracted</th>
                  <th className="text-right p-2 font-medium">Presence</th>
                  <th className="text-right p-2 font-medium">Accuracy</th>
                  <th className="text-right p-2 font-medium">Evidence</th>
                  <th className="text-left p-2 font-medium">Top Issue</th>
                </tr>
              </thead>
              <tbody>
                {selectedDetailedRun && Object.keys(selectedDetailedRun.phases.classification.distribution).length > 0 ? (
                  Object.entries(selectedDetailedRun.phases.classification.distribution)
                    .sort((a, b) => b[1] - a[1])
                    .map(([docType, classifiedCount]) => {
                      const extractionMetrics = docTypes.find((dt) => dt.doc_type === docType);
                      return (
                        <tr
                          key={docType}
                          onClick={() => extractionMetrics && onDocTypeClick(docType)}
                          className={cn(
                            "border-b transition-colors",
                            extractionMetrics && "cursor-pointer hover:bg-gray-50",
                            selectedDocType === docType && "bg-blue-50"
                          )}
                        >
                          <td className="p-2 font-medium">
                            {getDocTypeName(docType)}
                          </td>
                          <td className="p-2 text-right text-gray-600">{classifiedCount}</td>
                          <td className="p-2 text-right text-gray-600">
                            {extractionMetrics?.docs_total || 0}
                          </td>
                          <td className="p-2 text-right">
                            {extractionMetrics ? (
                              <ScoreBadge value={extractionMetrics.required_field_presence_pct} />
                            ) : (
                              <span className="text-gray-400">—</span>
                            )}
                          </td>
                          <td className="p-2 text-right">
                            {extractionMetrics ? (
                              <ScoreBadge value={extractionMetrics.required_field_accuracy_pct} />
                            ) : (
                              <span className="text-gray-400">—</span>
                            )}
                          </td>
                          <td className="p-2 text-right">
                            {extractionMetrics ? (
                              <ScoreBadge value={extractionMetrics.evidence_rate_pct} />
                            ) : (
                              <span className="text-gray-400">—</span>
                            )}
                          </td>
                          <td className="p-2 text-gray-600 truncate max-w-[80px]" title={extractionMetrics?.top_failing_field || ""}>
                            {extractionMetrics?.top_failing_field ? getFieldName(extractionMetrics.top_failing_field) : "-"}
                          </td>
                        </tr>
                      );
                    })
                ) : docTypes.length > 0 ? (
                  docTypes.map((dt) => (
                    <tr
                      key={dt.doc_type}
                      onClick={() => onDocTypeClick(dt.doc_type)}
                      className={cn(
                        "border-b cursor-pointer hover:bg-gray-50 transition-colors",
                        selectedDocType === dt.doc_type && "bg-blue-50"
                      )}
                    >
                      <td className="p-2 font-medium">
                        {getDocTypeName(dt.doc_type)}
                      </td>
                      <td className="p-2 text-right text-gray-600">—</td>
                      <td className="p-2 text-right text-gray-600">{dt.docs_total}</td>
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
                  ))
                ) : (
                  <tr>
                    <td colSpan={7} className="p-3 text-center text-gray-500">
                      No data
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      {/* Drilldown */}
      {(selectedDocType || fieldDetails) && (
        <section ref={drilldownRef} className="bg-white rounded-lg border shadow-sm">
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
                    Presence: <strong>{fieldDetails.rates.presence_pct}%</strong>
                  </span>
                  <span className="px-1.5 py-0.5 bg-gray-100 rounded">
                    Accuracy: <strong>{fieldDetails.rates.accuracy_pct}%</strong>
                  </span>
                  <span className="px-1.5 py-0.5 bg-gray-100 rounded">
                    Evidence: <strong>{fieldDetails.rates.evidence_pct}%</strong>
                  </span>
                </div>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button onClick={onCopyLink} className="text-xs text-gray-500 hover:text-gray-700 px-2 py-1 rounded hover:bg-gray-100">
                Copy link
              </button>
              <button onClick={onClearSelection} className="text-xs text-gray-500 hover:text-gray-700 px-2 py-1 rounded hover:bg-gray-100">
                Clear
              </button>
            </div>
          </div>

          {fieldDetails && (
            <div className="flex items-center gap-2 p-3 border-b">
              <OutcomeChip label="Correct" count={fieldDetails.breakdown.correct} variant="success" selected={selectedOutcome === "correct"} onClick={() => onOutcomeFilter(selectedOutcome === "correct" ? null : "correct")} />
              <OutcomeChip label="Incorrect" count={fieldDetails.breakdown.incorrect} variant="error" selected={selectedOutcome === "incorrect"} onClick={() => onOutcomeFilter(selectedOutcome === "incorrect" ? null : "incorrect")} />
              <OutcomeChip label="Missing" count={fieldDetails.breakdown.extractor_miss} variant="warning" selected={selectedOutcome === "missing"} onClick={() => onOutcomeFilter(selectedOutcome === "missing" ? null : "missing")} />
            </div>
          )}

          <ExamplesTable examples={examples} selectedField={selectedField} onOpenReview={onOpenReview} />
        </section>
      )}
    </div>
  );
}

// =============================================================================
// Run History Tab
// =============================================================================

interface RunHistoryTabProps {
  runs: RunInfo[];
  baselineRunId: string | null;
  selectedRunId: string | null;
  onSelectRun: (runId: string) => void;
  onSetBaseline: (runId: string) => void;
}

function RunHistoryTab({ runs, baselineRunId, selectedRunId, onSelectRun, onSetBaseline }: RunHistoryTabProps) {
  return (
    <div className="bg-white rounded-lg border shadow-sm">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-gray-50">
            <th className="text-left p-3 font-medium">Run ID</th>
            <th className="text-left p-3 font-medium">Timestamp</th>
            <th className="text-left p-3 font-medium">Model</th>
            <th className="text-right p-3 font-medium">Docs</th>
            <th className="text-right p-3 font-medium">Labeled</th>
            <th className="text-right p-3 font-medium">Presence</th>
            <th className="text-right p-3 font-medium">Accuracy</th>
            <th className="text-right p-3 font-medium">Evidence</th>
            <th className="text-left p-3 font-medium">Actions</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run, idx) => (
            <tr
              key={run.run_id}
              className={cn(
                "border-b hover:bg-gray-50",
                selectedRunId === run.run_id && "bg-blue-50"
              )}
            >
              <td className="p-3 font-mono text-xs">
                {run.run_id}
                {idx === 0 && <span className="ml-2 text-[10px] px-1 py-0.5 bg-blue-100 text-blue-700 rounded">Latest</span>}
                {run.run_id === baselineRunId && <span className="ml-2 text-[10px] px-1 py-0.5 bg-green-100 text-green-700 rounded">Baseline</span>}
              </td>
              <td className="p-3 text-gray-600">{formatTimestamp(run.timestamp)}</td>
              <td className="p-3 text-gray-600">{run.model || "-"}</td>
              <td className="p-3 text-right">{run.docs_count}</td>
              <td className="p-3 text-right">{run.labeled_count}</td>
              <td className="p-3 text-right"><ScoreBadge value={run.presence_rate} /></td>
              <td className="p-3 text-right"><ScoreBadge value={run.accuracy_rate} /></td>
              <td className="p-3 text-right"><ScoreBadge value={run.evidence_rate} /></td>
              <td className="p-3">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => onSelectRun(run.run_id)}
                    className="text-xs text-blue-600 hover:text-blue-800"
                  >
                    View
                  </button>
                  {run.run_id !== baselineRunId && (
                    <button
                      onClick={() => onSetBaseline(run.run_id)}
                      className="text-xs text-gray-500 hover:text-gray-700"
                    >
                      Set Baseline
                    </button>
                  )}
                </div>
              </td>
            </tr>
          ))}
          {runs.length === 0 && (
            <tr>
              <td colSpan={9} className="p-4 text-center text-gray-500">
                No runs found
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

// =============================================================================
// Compare Runs Tab
// =============================================================================

interface CompareRunsTabProps {
  runs: RunInfo[];
  baselineId: string | null;
  currentId: string | null;
  comparison: RunComparison | null;
  onBaselineChange: (id: string | null) => void;
  onCurrentChange: (id: string | null) => void;
}

function CompareRunsTab({ runs, baselineId, currentId, comparison, onBaselineChange, onCurrentChange }: CompareRunsTabProps) {
  return (
    <div className="space-y-4">
      {/* Run selectors */}
      <div className="bg-white rounded-lg border shadow-sm p-4">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-gray-700">Baseline:</label>
            <select
              value={baselineId || ""}
              onChange={(e) => onBaselineChange(e.target.value || null)}
              className="border rounded px-2 py-1 text-sm min-w-[180px]"
            >
              <option value="">Select baseline...</option>
              {runs.map((run) => (
                <option key={run.run_id} value={run.run_id}>{run.run_id}</option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-gray-700">Current:</label>
            <select
              value={currentId || ""}
              onChange={(e) => onCurrentChange(e.target.value || null)}
              className="border rounded px-2 py-1 text-sm min-w-[180px]"
            >
              <option value="">Select current...</option>
              {runs.map((run) => (
                <option key={run.run_id} value={run.run_id}>{run.run_id}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {comparison && (
        <>
          {/* Overview Deltas */}
          <div className="bg-white rounded-lg border shadow-sm p-4">
            <h3 className="text-sm font-semibold mb-3">KPI Changes</h3>
            <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
              {Object.entries(comparison.overview_deltas).map(([key, val]) => (
                <DeltaCard key={key} label={formatKpiLabel(key)} baseline={val.baseline} current={val.current} delta={val.delta} />
              ))}
            </div>
          </div>

          {/* Doc Type Deltas */}
          <div className="bg-white rounded-lg border shadow-sm p-4">
            <h3 className="text-sm font-semibold mb-3">Doc Type Changes</h3>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50">
                  <th className="text-left p-2 font-medium">Doc Type</th>
                  <th className="text-right p-2 font-medium">Presence Change</th>
                  <th className="text-right p-2 font-medium">Accuracy Change</th>
                  <th className="text-right p-2 font-medium">Evidence Change</th>
                </tr>
              </thead>
              <tbody>
                {comparison.doc_type_deltas.map((dt) => (
                  <tr key={dt.doc_type} className="border-b">
                    <td className="p-2 font-medium">{getDocTypeName(dt.doc_type)}</td>
                    <td className="p-2 text-right"><DeltaBadge delta={dt.presence_delta} /></td>
                    <td className="p-2 text-right"><DeltaBadge delta={dt.accuracy_delta} /></td>
                    <td className="p-2 text-right"><DeltaBadge delta={dt.evidence_delta} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Priority Changes */}
          {comparison.priority_changes.length > 0 && (
            <div className="bg-white rounded-lg border shadow-sm p-4">
              <h3 className="text-sm font-semibold mb-3">Priority List Changes</h3>
              <div className="space-y-2">
                {comparison.priority_changes.map((change, idx) => (
                  <div key={idx} className={cn(
                    "flex items-center gap-2 text-sm px-3 py-2 rounded",
                    change.status === "improved" ? "bg-green-50" : "bg-red-50"
                  )}>
                    <span className={change.status === "improved" ? "text-green-600" : "text-red-600"}>
                      {change.status === "improved" ? "↑" : "↓"}
                    </span>
                    <span className="font-medium">{getDocTypeName(change.doc_type)}</span>
                    <span className="text-gray-400">·</span>
                    <span>{getFieldName(change.field_name)}</span>
                    {change.delta !== undefined && (
                      <span className="text-gray-500 ml-auto">
                        {change.delta > 0 ? `+${change.delta}` : change.delta} affected
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {!comparison && baselineId && currentId && baselineId !== currentId && (
        <div className="text-center text-gray-500 py-8">Loading comparison...</div>
      )}

      {(!baselineId || !currentId || baselineId === currentId) && (
        <div className="text-center text-gray-500 py-8">
          Select two different runs to compare
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Helper Components
// =============================================================================

function formatKpiLabel(key: string): string {
  const labels: Record<string, string> = {
    required_field_presence_rate: "Presence",
    required_field_accuracy: "Accuracy",
    evidence_rate: "Evidence",
    docs_reviewed: "Reviewed",
    docs_doc_type_wrong: "Type Wrong",
  };
  return labels[key] || key;
}

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

interface DeltaCardProps {
  label: string;
  baseline: number;
  current: number;
  delta: number;
}

function DeltaCard({ label, baseline, current, delta }: DeltaCardProps) {
  const isPositive = delta > 0;
  const isNegative = delta < 0;
  const isPercent = label.includes("Presence") || label.includes("Accuracy") || label.includes("Evidence");

  return (
    <div className="rounded-lg border p-3 shadow-sm bg-white">
      <div className="text-lg font-bold">
        {current}{isPercent ? "%" : ""}
        {delta !== 0 && (
          <span className={cn("ml-2 text-sm", isPositive ? "text-green-600" : isNegative ? "text-red-600" : "text-gray-400")}>
            {isPositive ? "+" : ""}{delta}{isPercent ? "%" : ""}
          </span>
        )}
      </div>
      <div className="text-xs text-gray-600">{label}</div>
      <div className="text-[10px] text-gray-400">was {baseline}{isPercent ? "%" : ""}</div>
    </div>
  );
}

function DeltaBadge({ delta }: { delta: number }) {
  if (delta === 0) return <span className="text-gray-400">-</span>;
  const isPositive = delta > 0;
  return (
    <span className={cn("font-medium", isPositive ? "text-green-600" : "text-red-600")}>
      {isPositive ? "+" : ""}{delta}%
    </span>
  );
}

function ScoreBadge({ value }: { value: number }) {
  const color = value >= 80 ? "text-green-600" : value >= 60 ? "text-yellow-600" : "text-red-600";
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

interface ExamplesTableProps {
  examples: InsightExample[];
  selectedField: string | null;
  onOpenReview: (example: InsightExample) => void;
}

function ExamplesTable({ examples, selectedField, onOpenReview }: ExamplesTableProps) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b bg-gray-50">
            <th className="text-left p-2 font-medium">Claim</th>
            <th className="text-left p-2 font-medium">Filename</th>
            {!selectedField && <th className="text-left p-2 font-medium">Field</th>}
            <th className="text-left p-2 font-medium">Extracted</th>
            <th className="text-left p-2 font-medium">Truth</th>
            <th className="text-center p-2 font-medium">Evidence</th>
            <th className="text-center p-2 font-medium">Outcome</th>
            <th className="text-left p-2 font-medium w-12"></th>
          </tr>
        </thead>
        <tbody>
          {examples.map((ex, idx) => (
            <tr key={`${ex.doc_id}-${ex.field_name}-${idx}`} className="border-b hover:bg-gray-50">
              <td className="p-2 font-mono text-[10px]">{ex.claim_id}</td>
              <td className="p-2 truncate max-w-[140px]" title={ex.filename}>{ex.filename}</td>
              {!selectedField && <td className="p-2">{getFieldName(ex.field_name)}</td>}
              <td className="p-2 font-mono text-[10px] truncate max-w-[120px]" title={ex.normalized_value || ex.predicted_value || ""}>
                {ex.normalized_value || ex.predicted_value || <span className="text-gray-400">-</span>}
              </td>
              <td className="p-2 font-mono text-[10px] truncate max-w-[120px]" title={ex.truth_value || ""}>
                {ex.state === "CONFIRMED" ? (
                  ex.truth_value || <span className="text-gray-400">-</span>
                ) : ex.state === "UNVERIFIABLE" ? (
                  <span className="text-[10px] px-1 py-0.5 bg-gray-100 text-gray-600 rounded">Unverifiable</span>
                ) : (
                  <span className="text-gray-300">-</span>
                )}
              </td>
              <td className="p-2 text-center">
                {ex.has_evidence ? <span className="text-green-600">Yes</span> : <span className="text-gray-300">-</span>}
              </td>
              <td className="p-2 text-center"><OutcomeBadge outcome={ex.outcome} /></td>
              <td className="p-2">
                <button onClick={() => onOpenReview(ex)} className="text-blue-600 hover:text-blue-800 hover:underline">Open</button>
              </td>
            </tr>
          ))}
          {examples.length === 0 && (
            <tr><td colSpan={selectedField ? 7 : 8} className="p-4 text-center text-gray-500">No examples found</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function OutcomeBadge({ outcome }: { outcome: string | null }) {
  if (!outcome) return <span className="text-gray-300">-</span>;
  const styles: Record<string, string> = {
    // Truth-based outcomes (v3)
    correct: "bg-green-100 text-green-700",
    incorrect: "bg-red-100 text-red-700",
    missing: "bg-yellow-100 text-yellow-700",
    unverifiable: "bg-gray-100 text-gray-600",
    // Legacy outcomes (backwards compatibility)
    match: "bg-green-100 text-green-700",
    mismatch: "bg-red-100 text-red-700",
    miss: "bg-yellow-100 text-yellow-700",
    extractor_miss: "bg-yellow-100 text-yellow-700",
    cannot_verify: "bg-gray-100 text-gray-600",
    correct_absent: "bg-gray-100 text-gray-600",
  };
  const labels: Record<string, string> = {
    // Truth-based labels (v3)
    correct: "Correct",
    incorrect: "Incorrect",
    missing: "Missing",
    unverifiable: "Unverifiable",
    // Legacy labels (backwards compatibility)
    match: "Correct",
    mismatch: "Incorrect",
    miss: "Missing",
    extractor_miss: "Missing",
    cannot_verify: "Unknown",
    correct_absent: "Correct",
  };
  return <span className={cn("text-[10px] px-1 py-0.5 rounded font-medium", styles[outcome] || "bg-gray-100 text-gray-600")}>{labels[outcome] || outcome}</span>;
}
