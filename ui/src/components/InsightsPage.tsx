import { useState, useEffect, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { cn } from "../lib/utils";
import { formatDocType, formatFieldName, formatTimestamp } from "../lib/formatters";
import {
  MetricCard,
  MetricCardRow,
  DeltaMetricCard,
  getScoreVariant,
  ScoreBadge,
  BaselineBadge,
  OutcomeBadge,
  PageLoadingSkeleton,
  NoLabelsEmptyState,
} from "./shared";
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

type ViewTab = "insights" | "history" | "compare";

interface InsightsPageProps {
  selectedBatchId: string | null;
  onBatchChange: (batchId: string) => void;
}

export function InsightsPage({
  selectedBatchId,
  onBatchChange,
}: InsightsPageProps) {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const drilldownRef = useRef<HTMLDivElement>(null);

  // View state
  const [activeTab, setActiveTab] = useState<ViewTab>("insights");

  // Run state (local for this page's run list with metrics)
  const [runs, setRuns] = useState<RunInfo[]>([]);
  const [detailedRuns, setDetailedRuns] = useState<DetailedRunInfo[]>([]);
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

  // Sync selectedDetailedRun when selectedBatchId or detailedRuns change
  useEffect(() => {
    if (selectedBatchId && detailedRuns.length > 0) {
      const detailed = detailedRuns.find((r) => r.run_id === selectedBatchId);
      setSelectedDetailedRun(detailed || null);
    }
  }, [selectedBatchId, detailedRuns]);

  // Load data when run selection changes
  useEffect(() => {
    if (selectedBatchId) {
      loadRunData(selectedBatchId);
    }
  }, [selectedBatchId]);

  async function loadRuns() {
    try {
      const [runsData, detailedData] = await Promise.all([
        getInsightsRuns(),
        getDetailedRuns(),
      ]);
      setRuns(runsData);
      setDetailedRuns(detailedData);
      // If no run selected yet, select latest and notify parent
      if (runsData.length > 0 && !selectedBatchId) {
        onBatchChange(runsData[0].run_id);
      }
    } catch (err) {
      console.error("Failed to load runs:", err);
    }
  }

  // Load field details and examples when selection or run changes
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
  }, [selectedDocType, selectedField, selectedOutcome, selectedBatchId]);

  // Load comparison when both runs selected
  useEffect(() => {
    if (compareBaselineId && compareCurrentId && compareBaselineId !== compareCurrentId) {
      loadComparison(compareBaselineId, compareCurrentId);
    } else {
      setComparison(null);
    }
  }, [compareBaselineId, compareCurrentId]);

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
      const data = await getInsightsFieldDetails(docType, field, selectedBatchId || undefined);
      setFieldDetails(data);
    } catch {
      setFieldDetails(null);
    }
  }

  async function loadExamples(params: { doc_type?: string; field?: string; outcome?: string }) {
    try {
      const data = await getInsightsExamples({ ...params, run_id: selectedBatchId || undefined, limit: 30 });
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
    return <PageLoadingSkeleton message="Loading benchmark data..." />;
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full">
        <p className="text-destructive mb-4">{error}</p>
        <button
          onClick={() => selectedBatchId && loadRunData(selectedBatchId)}
          className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="p-4 space-y-4">
      {/* Baseline Controls */}
      <div className="bg-card rounded-lg border shadow-sm p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            {/* Run Metadata */}
            {runMetadata && (
              <div data-testid="run-metadata" className="flex items-center gap-4 text-xs text-muted-foreground">
                {Boolean(runMetadata.extractor_version) && (
                  <span>
                    <strong>Extractor:</strong> {String(runMetadata.extractor_version)}
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Baseline Controls */}
          <div className="flex items-center gap-2">
            {baselineRunId && (
              <span className="text-xs text-success bg-success/10 px-2 py-1 rounded">
                Baseline: {baselineRunId}
              </span>
            )}
            {selectedBatchId && selectedBatchId !== baselineRunId && (
              <button
                onClick={() => handleSetBaseline(selectedBatchId)}
                className="text-xs px-2 py-1 bg-accent/10 text-accent-foreground rounded hover:bg-accent/20"
              >
                Set as Baseline
              </button>
            )}
            {baselineRunId && (
              <button
                onClick={handleClearBaseline}
                className="text-xs px-2 py-1 text-muted-foreground hover:text-foreground"
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
              ? "border-accent text-accent-foreground"
              : "border-transparent text-muted-foreground hover:text-foreground"
          )}
        >
          Insights
        </button>
        <button
          onClick={() => setActiveTab("history")}
          className={cn(
            "px-4 py-2 text-sm font-medium border-b-2 -mb-px",
            activeTab === "history"
              ? "border-accent text-accent-foreground"
              : "border-transparent text-muted-foreground hover:text-foreground"
          )}
        >
          Batch History
        </button>
        <button
          onClick={() => setActiveTab("compare")}
          className={cn(
            "px-4 py-2 text-sm font-medium border-b-2 -mb-px",
            activeTab === "compare"
              ? "border-accent text-accent-foreground"
              : "border-transparent text-muted-foreground hover:text-foreground"
          )}
        >
          Compare Batches
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
          selectedBatchId={selectedBatchId}
          onSelectRun={onBatchChange}
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
      <MetricCardRow columns={5} testId="kpi-row">
        <MetricCard
          testId="kpi-doc-coverage"
          label="Doc Coverage"
          value={`${overview?.docs_with_truth || 0}/${overview?.docs_total || 0}`}
          subtext="docs with truth labels"
        />
        <MetricCard
          testId="kpi-field-coverage"
          label="Field Coverage"
          value={`${overview?.labeled_fields || overview?.confirmed_fields || 0}/${overview?.total_fields || 0}`}
          subtext="labeled fields"
        />
        <MetricCard
          testId="kpi-accuracy"
          label="Accuracy"
          value={`${overview?.accuracy_rate || 0}%`}
          subtext={`${overview?.correct_count || overview?.match_count || 0} correct / ${(overview?.correct_count || overview?.match_count || 0) + (overview?.incorrect_count || overview?.mismatch_count || 0) + (overview?.missing_count || overview?.miss_count || 0)} total`}
          variant={getScoreVariant(overview?.accuracy_rate || 0)}
        />
        <MetricCard
          testId="kpi-evidence-rate"
          label="Evidence Rate"
          value={`${overview?.evidence_rate || 0}%`}
          variant={getScoreVariant(overview?.evidence_rate || 0)}
        />
        <MetricCard
          testId="kpi-doc-type-wrong"
          label="Doc Type Wrong"
          value={overview?.docs_doc_type_wrong || 0}
          variant={overview?.docs_doc_type_wrong ? "warning" : "default"}
        />
      </MetricCardRow>

      {/* Main row: Priorities + Scoreboard */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        {/* Top Error Drivers */}
        <section className="lg:col-span-3">
          <h2 className="text-sm font-semibold text-foreground mb-2">Top Error Drivers</h2>
          <div className="bg-card rounded-lg border shadow-sm max-h-[400px] overflow-y-auto">
            {priorities.length === 0 ? (
              <NoLabelsEmptyState />
            ) : (
              <div className="divide-y">
                {priorities.map((item, idx) => (
                  <button
                    key={`${item.doc_type}-${item.field_name}`}
                    onClick={() => onPriorityClick(item)}
                    className={cn(
                      "w-full text-left px-3 py-2 hover:bg-muted/50 transition-colors",
                      selectedDocType === item.doc_type && selectedField === item.field_name && "bg-accent/10 border-l-2 border-accent"
                    )}
                  >
                    <div className="flex items-center gap-1.5 text-sm">
                      <span className="text-muted-foreground/70 font-mono w-5">{idx + 1}.</span>
                      <span className="font-medium text-foreground">{formatDocType(item.doc_type)}</span>
                      <span className="text-muted-foreground/70">·</span>
                      <span className="text-foreground">{formatFieldName(item.field_name)}</span>
                      {item.is_required && (
                        <span className="text-[10px] px-1.5 py-0.5 bg-destructive/10 text-destructive rounded font-medium">Required</span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 mt-0.5 ml-5 text-xs">
                      <span className="text-muted-foreground">{item.error_rate}% error rate</span>
                      <span className="text-muted-foreground/50">·</span>
                      {(item.incorrect_count ?? item.mismatch_count ?? 0) > 0 && <span className="text-destructive">{item.incorrect_count ?? item.mismatch_count ?? 0} incorrect</span>}
                      {(item.missing_count ?? item.miss_count ?? 0) > 0 && <span className="text-warning-foreground">{item.missing_count ?? item.miss_count ?? 0} missing</span>}
                      <span className="ml-auto text-muted-foreground">{item.total_labeled ?? item.total_confirmed ?? 0} labeled</span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </section>

        {/* Doc Type Scoreboard */}
        <section className="lg:col-span-2" data-testid="doc-type-scoreboard">
          <h2 className="text-sm font-semibold text-foreground mb-2">Doc Type Scoreboard</h2>
          <div className="bg-card rounded-lg border shadow-sm overflow-hidden">
            <table className="w-full text-xs" data-testid="scoreboard-table">
              <thead>
                <tr className="border-b bg-muted/50">
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
                            extractionMetrics && "cursor-pointer hover:bg-muted/50",
                            selectedDocType === docType && "bg-accent/10"
                          )}
                        >
                          <td className="p-2 font-medium">
                            {formatDocType(docType)}
                          </td>
                          <td className="p-2 text-right text-muted-foreground">{classifiedCount}</td>
                          <td className="p-2 text-right text-muted-foreground">
                            {extractionMetrics?.docs_total || 0}
                          </td>
                          <td className="p-2 text-right">
                            {extractionMetrics ? (
                              <ScoreBadge value={extractionMetrics.required_field_presence_pct} />
                            ) : (
                              <span className="text-muted-foreground/70">—</span>
                            )}
                          </td>
                          <td className="p-2 text-right">
                            {extractionMetrics ? (
                              <ScoreBadge value={extractionMetrics.required_field_accuracy_pct} />
                            ) : (
                              <span className="text-muted-foreground/70">—</span>
                            )}
                          </td>
                          <td className="p-2 text-right">
                            {extractionMetrics ? (
                              <ScoreBadge value={extractionMetrics.evidence_rate_pct} />
                            ) : (
                              <span className="text-muted-foreground/70">—</span>
                            )}
                          </td>
                          <td className="p-2 text-muted-foreground truncate max-w-[80px]" title={extractionMetrics?.top_failing_field || ""}>
                            {extractionMetrics?.top_failing_field ? formatFieldName(extractionMetrics.top_failing_field) : "-"}
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
                        "border-b cursor-pointer hover:bg-muted/50 transition-colors",
                        selectedDocType === dt.doc_type && "bg-accent/10"
                      )}
                    >
                      <td className="p-2 font-medium">
                        {formatDocType(dt.doc_type)}
                      </td>
                      <td className="p-2 text-right text-muted-foreground">—</td>
                      <td className="p-2 text-right text-muted-foreground">{dt.docs_total}</td>
                      <td className="p-2 text-right">
                        <ScoreBadge value={dt.required_field_presence_pct} />
                      </td>
                      <td className="p-2 text-right">
                        <ScoreBadge value={dt.required_field_accuracy_pct} />
                      </td>
                      <td className="p-2 text-right">
                        <ScoreBadge value={dt.evidence_rate_pct} />
                      </td>
                      <td className="p-2 text-muted-foreground truncate max-w-[80px]" title={dt.top_failing_field || ""}>
                        {dt.top_failing_field ? formatFieldName(dt.top_failing_field) : "-"}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={7} className="p-3 text-center text-muted-foreground">
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
        <section ref={drilldownRef} className="bg-card rounded-lg border shadow-sm">
          <div className="flex items-center justify-between p-3 border-b bg-muted/50">
            <div className="flex items-center gap-3">
              <h2 className="text-sm font-semibold">
                {fieldDetails
                  ? `${formatDocType(fieldDetails.doc_type)} · ${formatFieldName(fieldDetails.field_name)}`
                  : selectedDocType
                  ? `${formatDocType(selectedDocType)} Examples`
                  : "Details"}
              </h2>
              {fieldDetails && (
                <div className="flex items-center gap-2 text-xs">
                  <span className="px-1.5 py-0.5 bg-muted rounded">
                    Presence: <strong>{fieldDetails.rates.presence_pct}%</strong>
                  </span>
                  <span className="px-1.5 py-0.5 bg-muted rounded">
                    Accuracy: <strong>{fieldDetails.rates.accuracy_pct}%</strong>
                  </span>
                  <span className="px-1.5 py-0.5 bg-muted rounded">
                    Evidence: <strong>{fieldDetails.rates.evidence_pct}%</strong>
                  </span>
                </div>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button onClick={onCopyLink} className="text-xs text-muted-foreground hover:text-foreground px-2 py-1 rounded hover:bg-muted">
                Copy link
              </button>
              <button onClick={onClearSelection} className="text-xs text-muted-foreground hover:text-foreground px-2 py-1 rounded hover:bg-muted">
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
  selectedBatchId: string | null;
  onSelectRun: (runId: string) => void;
  onSetBaseline: (runId: string) => void;
}

function RunHistoryTab({ runs, baselineRunId, selectedBatchId, onSelectRun, onSetBaseline }: RunHistoryTabProps) {
  return (
    <div className="bg-card rounded-lg border shadow-sm">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="text-left p-3 font-medium">Batch ID</th>
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
          {runs.map((run) => (
            <tr
              key={run.run_id}
              className={cn(
                "border-b hover:bg-muted/50",
                selectedBatchId === run.run_id && "bg-accent/10"
              )}
            >
              <td className="p-3 font-mono text-xs">
                {run.run_id}
                {run.run_id === baselineRunId && <span className="ml-2"><BaselineBadge /></span>}
              </td>
              <td className="p-3 text-muted-foreground">{formatTimestamp(run.timestamp)}</td>
              <td className="p-3 text-muted-foreground">{run.model || "-"}</td>
              <td className="p-3 text-right">{run.docs_count}</td>
              <td className="p-3 text-right">{run.labeled_count}</td>
              <td className="p-3 text-right"><ScoreBadge value={run.presence_rate} /></td>
              <td className="p-3 text-right"><ScoreBadge value={run.accuracy_rate} /></td>
              <td className="p-3 text-right"><ScoreBadge value={run.evidence_rate} /></td>
              <td className="p-3">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => onSelectRun(run.run_id)}
                    className="text-xs text-accent-foreground hover:text-accent"
                  >
                    View
                  </button>
                  {run.run_id !== baselineRunId && (
                    <button
                      onClick={() => onSetBaseline(run.run_id)}
                      className="text-xs text-muted-foreground hover:text-foreground"
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
              <td colSpan={9} className="p-4 text-center text-muted-foreground">
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
      <div className="bg-card rounded-lg border shadow-sm p-4">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-foreground">Baseline:</label>
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
            <label className="text-sm font-medium text-foreground">Current:</label>
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
          <div className="bg-card rounded-lg border shadow-sm p-4">
            <h3 className="text-sm font-semibold mb-3">KPI Changes</h3>
            <MetricCardRow columns={6}>
              {Object.entries(comparison.overview_deltas).map(([key, val]) => (
                <DeltaMetricCard
                  key={key}
                  label={formatKpiLabel(key)}
                  baseline={val.baseline}
                  current={val.current}
                  delta={val.delta}
                  isPercent={key.includes("presence") || key.includes("accuracy") || key.includes("evidence")}
                />
              ))}
            </MetricCardRow>
          </div>

          {/* Doc Type Deltas */}
          <div className="bg-card rounded-lg border shadow-sm p-4">
            <h3 className="text-sm font-semibold mb-3">Doc Type Changes</h3>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="text-left p-2 font-medium">Doc Type</th>
                  <th className="text-right p-2 font-medium">Presence Change</th>
                  <th className="text-right p-2 font-medium">Accuracy Change</th>
                  <th className="text-right p-2 font-medium">Evidence Change</th>
                </tr>
              </thead>
              <tbody>
                {comparison.doc_type_deltas.map((dt) => (
                  <tr key={dt.doc_type} className="border-b">
                    <td className="p-2 font-medium">{formatDocType(dt.doc_type)}</td>
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
            <div className="bg-card rounded-lg border shadow-sm p-4">
              <h3 className="text-sm font-semibold mb-3">Priority List Changes</h3>
              <div className="space-y-2">
                {comparison.priority_changes.map((change, idx) => (
                  <div key={idx} className={cn(
                    "flex items-center gap-2 text-sm px-3 py-2 rounded",
                    change.status === "improved" ? "bg-success/10" : "bg-destructive/10"
                  )}>
                    <span className={change.status === "improved" ? "text-success" : "text-destructive"}>
                      {change.status === "improved" ? "↑" : "↓"}
                    </span>
                    <span className="font-medium">{formatDocType(change.doc_type)}</span>
                    <span className="text-muted-foreground/70">·</span>
                    <span>{formatFieldName(change.field_name)}</span>
                    {change.delta !== undefined && (
                      <span className="text-muted-foreground ml-auto">
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
        <div className="text-center text-muted-foreground py-8">Loading comparison...</div>
      )}

      {(!baselineId || !currentId || baselineId === currentId) && (
        <div className="text-center text-muted-foreground py-8">
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

function DeltaBadge({ delta }: { delta: number }) {
  if (delta === 0) return <span className="text-muted-foreground/70">-</span>;
  const isPositive = delta > 0;
  return (
    <span className={cn("font-medium", isPositive ? "text-success" : "text-destructive")}>
      {isPositive ? "+" : ""}{delta}%
    </span>
  );
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
    success: "border-success/30 bg-success/10 text-success",
    error: "border-destructive/30 bg-destructive/10 text-destructive",
    warning: "border-warning/30 bg-warning/10 text-warning-foreground",
    info: "border-info/30 bg-info/10 text-info",
    neutral: "border-border bg-muted/50 text-foreground",
  };

  return (
    <button
      onClick={onClick}
      className={cn(
        "px-2 py-1 rounded border text-xs font-medium transition-all",
        variants[variant],
        selected && "ring-2 ring-accent ring-offset-1"
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
          <tr className="border-b bg-muted/50">
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
            <tr key={`${ex.doc_id}-${ex.field_name}-${idx}`} className="border-b hover:bg-muted/50">
              <td className="p-2 font-mono text-[10px]">{ex.claim_id}</td>
              <td className="p-2 truncate max-w-[140px]" title={ex.filename}>{ex.filename}</td>
              {!selectedField && <td className="p-2">{formatFieldName(ex.field_name)}</td>}
              <td className="p-2 font-mono text-[10px] truncate max-w-[120px]" title={ex.normalized_value || ex.predicted_value || ""}>
                {ex.normalized_value || ex.predicted_value || <span className="text-muted-foreground/70">-</span>}
              </td>
              <td className="p-2 font-mono text-[10px] truncate max-w-[120px]" title={ex.truth_value || ""}>
                {ex.state === "CONFIRMED" ? (
                  ex.truth_value || <span className="text-muted-foreground/70">-</span>
                ) : ex.state === "UNVERIFIABLE" ? (
                  <span className="text-[10px] px-1 py-0.5 bg-muted text-muted-foreground rounded">Unverifiable</span>
                ) : (
                  <span className="text-muted-foreground/50">-</span>
                )}
              </td>
              <td className="p-2 text-center">
                {ex.has_evidence ? <span className="text-success">Yes</span> : <span className="text-muted-foreground/50">-</span>}
              </td>
              <td className="p-2 text-center"><OutcomeBadge outcome={ex.outcome} /></td>
              <td className="p-2">
                <button onClick={() => onOpenReview(ex)} className="text-accent-foreground hover:text-accent hover:underline">Open</button>
              </td>
            </tr>
          ))}
          {examples.length === 0 && (
            <tr><td colSpan={selectedField ? 7 : 8} className="p-4 text-center text-muted-foreground">No examples found</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
