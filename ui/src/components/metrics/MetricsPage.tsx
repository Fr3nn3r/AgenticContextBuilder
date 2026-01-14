import { useState, useEffect, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { cn } from "../../lib/utils";
import { formatDocType, formatFieldName } from "../../lib/formatters";
import { transformOutcomeData, transformDocTypeData } from "../../lib/chartUtils";
import {
  MetricCard,
  MetricCardRow,
  getScoreVariant,
  ScoreBadge,
  PageLoadingSkeleton,
  NoLabelsEmptyState,
  OutcomeBadge,
} from "../shared";
import { ChartCard, DonutChart, ConfigurableMetricsChart, RadialGauge } from "../charts";
import {
  getInsightsFieldDetails,
  getInsightsExamples,
  getRunOverview,
  getRunDocTypes,
  getRunPriorities,
  getDetailedRuns,
  type InsightsOverview,
  type DocTypeMetrics,
  type PriorityItem,
  type FieldDetails,
  type InsightExample,
  type DetailedRunInfo,
} from "../../api/client";

interface MetricsPageProps {
  selectedBatchId: string | null;
  onBatchChange: (batchId: string) => void;
}

export function MetricsPage({ selectedBatchId, onBatchChange: _onBatchChange }: MetricsPageProps) {
  // Note: _onBatchChange kept for API compatibility with App.tsx
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const drilldownRef = useRef<HTMLDivElement>(null);

  // Run state
  const [detailedRuns, setDetailedRuns] = useState<DetailedRunInfo[]>([]);
  const [selectedDetailedRun, setSelectedDetailedRun] = useState<DetailedRunInfo | null>(null);
  const [runMetadata, setRunMetadata] = useState<Record<string, unknown> | null>(null);

  // Insights data state
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

  // Load runs on mount
  useEffect(() => {
    loadDetailedRuns();
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

  async function loadDetailedRuns() {
    try {
      const detailedData = await getDetailedRuns();
      setDetailedRuns(detailedData);
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
      setError(err instanceof Error ? err.message : "Failed to load metrics");
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
    return <PageLoadingSkeleton message="Loading metrics..." />;
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

  // Transform data for charts
  const outcomeData = transformOutcomeData(overview);
  const docTypeChartData = transformDocTypeData(docTypes);

  return (
    <div className="p-4 space-y-4">
      {/* Run Metadata (if available) */}
      {runMetadata && Boolean(runMetadata.extractor_version) && (
        <div data-testid="run-metadata" className="text-xs text-muted-foreground">
          <strong>Extractor:</strong> {String(runMetadata.extractor_version)}
        </div>
      )}

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

      {/* Charts Row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <ChartCard title="Accuracy" height="h-[160px]">
          <RadialGauge value={overview?.accuracy_rate || 0} label="Accuracy" size="md" />
        </ChartCard>
        <ChartCard title="Evidence Rate" height="h-[160px]">
          <RadialGauge value={overview?.evidence_rate || 0} label="Evidence" size="md" />
        </ChartCard>
        <ChartCard title="Outcome Distribution" height="h-[160px]">
          <DonutChart data={outcomeData} innerRadius={35} outerRadius={55} showLegend={false} />
        </ChartCard>
      </div>

      {/* Doc Type Performance Chart (Configurable) */}
      {docTypeChartData.length > 0 && (
        <ConfigurableMetricsChart data={docTypeChartData} title="Doc Type Performance" />
      )}

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
                    onClick={() => handlePriorityClick(item)}
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
                          onClick={() => extractionMetrics && handleDocTypeClick(docType)}
                          className={cn(
                            "border-b transition-colors",
                            extractionMetrics && "cursor-pointer hover:bg-muted/50",
                            selectedDocType === docType && "bg-accent/10"
                          )}
                        >
                          <td className="p-2 font-medium">{formatDocType(docType)}</td>
                          <td className="p-2 text-right text-muted-foreground">{classifiedCount}</td>
                          <td className="p-2 text-right text-muted-foreground">{extractionMetrics?.docs_total || 0}</td>
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
                      onClick={() => handleDocTypeClick(dt.doc_type)}
                      className={cn(
                        "border-b cursor-pointer hover:bg-muted/50 transition-colors",
                        selectedDocType === dt.doc_type && "bg-accent/10"
                      )}
                    >
                      <td className="p-2 font-medium">{formatDocType(dt.doc_type)}</td>
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
              <button onClick={handleCopyLink} className="text-xs text-muted-foreground hover:text-foreground px-2 py-1 rounded hover:bg-muted">
                Copy link
              </button>
              <button
                onClick={() => {
                  searchParams.delete("doc_type");
                  searchParams.delete("field");
                  searchParams.delete("outcome");
                  setSearchParams(searchParams);
                }}
                className="text-xs text-muted-foreground hover:text-foreground px-2 py-1 rounded hover:bg-muted"
              >
                Clear
              </button>
            </div>
          </div>

          {fieldDetails && (
            <div className="flex items-center gap-2 p-3 border-b">
              <OutcomeChip label="Correct" count={fieldDetails.breakdown.correct} variant="success" selected={selectedOutcome === "correct"} onClick={() => handleOutcomeFilter(selectedOutcome === "correct" ? null : "correct")} />
              <OutcomeChip label="Incorrect" count={fieldDetails.breakdown.incorrect} variant="error" selected={selectedOutcome === "incorrect"} onClick={() => handleOutcomeFilter(selectedOutcome === "incorrect" ? null : "incorrect")} />
              <OutcomeChip label="Missing" count={fieldDetails.breakdown.extractor_miss} variant="warning" selected={selectedOutcome === "missing"} onClick={() => handleOutcomeFilter(selectedOutcome === "missing" ? null : "missing")} />
            </div>
          )}

          <ExamplesTable examples={examples} selectedField={selectedField} onOpenReview={handleOpenReview} />
        </section>
      )}
    </div>
  );
}

// =============================================================================
// Helper Components
// =============================================================================

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
