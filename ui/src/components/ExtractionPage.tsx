import { useState, useMemo } from "react";
import { cn } from "../lib/utils";
import { formatDocType, formatRelativeTime, formatTimestamp } from "../lib/formatters";
import {
  ScoreBadge,
  CompleteBadge,
  PartialBadge,
  FailBadge,
  PageLoadingSkeleton,
  SelectToViewEmptyState,
} from "./shared";
import type { DetailedRunInfo, InsightsOverview, DocTypeMetrics } from "../api/client";

const SIDEBAR_COLLAPSED_KEY = "batch_history_collapsed";

interface ExtractionPageProps {
  batches: DetailedRunInfo[];
  selectedBatchId: string | null;
  onBatchChange: (batchId: string) => void;
  selectedBatch: DetailedRunInfo | null;
  overview: InsightsOverview | null;
  docTypes: DocTypeMetrics[];
  loading?: boolean;
}

export function ExtractionPage({
  batches,
  selectedBatchId,
  onBatchChange,
  selectedBatch,
  overview,
  docTypes,
  loading,
}: ExtractionPageProps) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "true";
    }
    return false;
  });

  const toggleSidebar = () => {
    const newValue = !sidebarCollapsed;
    setSidebarCollapsed(newValue);
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(newValue));
  };

  // Sort batches by batch_id (descending - most recent first)
  const sortedBatches = useMemo(() => {
    return [...batches].sort((a, b) => b.run_id.localeCompare(a.run_id));
  }, [batches]);

  return (
    <div className="flex h-full" data-testid="extraction-page">
      {/* Left Panel: Batch History */}
      <div
        className={cn(
          "border-r bg-muted/50 flex flex-col transition-all duration-200",
          sidebarCollapsed ? "w-14" : "w-72"
        )}
      >
        <div className={cn("border-b bg-card flex items-center", sidebarCollapsed ? "p-2 justify-center" : "p-4 justify-between")}>
          {!sidebarCollapsed && (
            <div>
              <h3 className="font-semibold text-foreground">Batch History</h3>
              <p className="text-xs text-muted-foreground mt-1">{batches.length} batches</p>
            </div>
          )}
          <button
            onClick={toggleSidebar}
            className="p-1.5 rounded hover:bg-muted transition-colors text-muted-foreground hover:text-foreground"
            title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            <ChevronIcon className={cn("w-4 h-4 transition-transform", sidebarCollapsed && "rotate-180")} />
          </button>
        </div>
        <div className={cn("flex-1 overflow-y-auto", sidebarCollapsed ? "p-1" : "p-2")}>
          {sidebarCollapsed ? (
            // Collapsed view: status dots
            <>
              {sortedBatches.map((batch) => (
                <button
                  key={batch.run_id}
                  onClick={() => onBatchChange(batch.run_id)}
                  className={cn(
                    "w-10 h-10 rounded flex items-center justify-center mb-1 transition-colors",
                    selectedBatchId === batch.run_id
                      ? "bg-accent/10 ring-2 ring-accent/50"
                      : "hover:bg-muted"
                  )}
                  title={`${batch.run_id}\n${formatRelativeTime(batch.timestamp)} • ${batch.docs_total} docs`}
                >
                  <span
                    className={cn(
                      "w-3 h-3 rounded-full",
                      batch.status === "complete" && "bg-success",
                      batch.status === "partial" && "bg-warning",
                      batch.status === "failed" && "bg-destructive"
                    )}
                  />
                </button>
              ))}
            </>
          ) : (
            // Expanded view: full batch items
            <>
              {sortedBatches.map((batch) => (
                <button
                  key={batch.run_id}
                  data-testid={`batch-item-${batch.run_id}`}
                  onClick={() => onBatchChange(batch.run_id)}
                  className={cn(
                    "w-full text-left px-3 py-2 rounded-md mb-1 transition-colors",
                    selectedBatchId === batch.run_id
                      ? "bg-accent/10 border border-accent/50"
                      : "hover:bg-muted"
                  )}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-foreground truncate" title={batch.run_id}>
                      {batch.run_id}
                    </span>
                    <BatchStatusBadge status={batch.status} />
                  </div>
                  <div className="text-xs text-muted-foreground/70 mt-0.5">
                    <span title={batch.timestamp ? formatTimestamp(batch.timestamp) : undefined}>
                      {formatRelativeTime(batch.timestamp)}
                    </span>
                    {" "}&bull; {batch.docs_total} docs
                  </div>
                </button>
              ))}
            </>
          )}
          {batches.length === 0 && !sidebarCollapsed && (
            <div className="text-center py-8 text-muted-foreground/70 text-sm">No batches found</div>
          )}
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto">
        <div className="p-6">
          {loading ? (
            <PageLoadingSkeleton message="Loading extraction data..." />
          ) : !selectedBatch ? (
            <div className="flex items-center justify-center h-64">
              <SelectToViewEmptyState itemType="batch" />
            </div>
          ) : (
            <>
              {/* Health Summary Banner */}
              <HealthSummaryBanner batch={selectedBatch} />

              {/* Phase Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                {/* Ingestion Card */}
                <PhaseCard
                  title="Ingestion"
                  icon={<DownloadIcon />}
                  color="blue"
                  healthStatus={selectedBatch.phases.ingestion.failed > 0 ? "error" : "healthy"}
                  testId="phase-ingestion"
                  metrics={[
                    { label: "Discovered", value: selectedBatch.phases.ingestion.discovered },
                    { label: "Ingested", value: selectedBatch.phases.ingestion.ingested },
                    {
                      label: "Skipped",
                      value: selectedBatch.phases.ingestion.skipped,
                      muted: true,
                    },
                    {
                      label: "Failed",
                      value: selectedBatch.phases.ingestion.failed,
                      alert: selectedBatch.phases.ingestion.failed > 0,
                    },
                  ]}
                  duration={selectedBatch.phases.ingestion.duration_ms}
                />

                {/* Classification Card */}
                <PhaseCard
                  title="Classification"
                  icon={<TagIcon />}
                  color="purple"
                  healthStatus={selectedBatch.phases.classification.low_confidence > 0 ? "warning" : "healthy"}
                  testId="phase-classification"
                  metrics={[
                    {
                      label: "Classified",
                      value: selectedBatch.phases.classification.classified,
                    },
                    {
                      label: "Low confidence",
                      value: selectedBatch.phases.classification.low_confidence,
                      alert: selectedBatch.phases.classification.low_confidence > 0,
                    },
                  ]}
                  duration={selectedBatch.phases.classification.duration_ms}
                >
                  {Object.keys(selectedBatch.phases.classification.distribution).length > 0 && (
                    <div className="mt-2 pt-2 border-t space-y-1">
                      {Object.entries(selectedBatch.phases.classification.distribution)
                        .sort((a, b) => b[1] - a[1])
                        .slice(0, 4)
                        .map(([type, count]) => (
                          <div
                            key={type}
                            className="flex justify-between text-xs text-muted-foreground"
                          >
                            <span>{formatDocType(type)}</span>
                            <span>{count}</span>
                          </div>
                        ))}
                    </div>
                  )}
                </PhaseCard>

                {/* Extraction Card */}
                <PhaseCard
                  title="Extraction"
                  icon={<ExtractIcon />}
                  color="green"
                  healthStatus={
                    selectedBatch.phases.extraction.failed > 0
                      ? "error"
                      : selectedBatch.phases.extraction.attempted !== selectedBatch.phases.extraction.succeeded
                        ? "warning"
                        : "healthy"
                  }
                  testId="phase-extraction"
                  metrics={[
                    { label: "Attempted", value: selectedBatch.phases.extraction.attempted },
                    {
                      label: "Succeeded",
                      value: selectedBatch.phases.extraction.succeeded,
                      success: true,
                    },
                    {
                      label: "Failed",
                      value: selectedBatch.phases.extraction.failed,
                      alert: selectedBatch.phases.extraction.failed > 0,
                    },
                  ]}
                  duration={selectedBatch.phases.extraction.duration_ms}
                />

                {/* Quality Gate Card */}
                <PhaseCard
                  title="Quality Gate"
                  icon={<ShieldIcon />}
                  color="amber"
                  healthStatus={
                    selectedBatch.phases.quality_gate.fail > 0
                      ? "error"
                      : selectedBatch.phases.quality_gate.warn > 0
                        ? "warning"
                        : "healthy"
                  }
                  testId="phase-quality-gate"
                  metrics={[
                    {
                      label: "Pass",
                      value: selectedBatch.phases.quality_gate.pass,
                      success: true,
                    },
                    {
                      label: "Warn",
                      value: selectedBatch.phases.quality_gate.warn,
                      warning: selectedBatch.phases.quality_gate.warn > 0,
                    },
                    {
                      label: "Fail",
                      value: selectedBatch.phases.quality_gate.fail,
                      alert: selectedBatch.phases.quality_gate.fail > 0,
                    },
                  ]}
                >
                  {overview && (
                    <div className="mt-2 pt-2 border-t">
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-muted-foreground">Evidence rate</span>
                        <span
                          className={cn(
                            "text-lg font-bold px-2 py-0.5 rounded",
                            overview.evidence_rate === 0 && "text-destructive bg-destructive/10",
                            overview.evidence_rate > 0 && overview.evidence_rate < 50 && "text-warning-foreground bg-warning/10",
                            overview.evidence_rate >= 50 && overview.evidence_rate < 80 && "text-foreground",
                            overview.evidence_rate >= 80 && "text-success bg-success/10"
                          )}
                        >
                          {overview.evidence_rate}%
                        </span>
                      </div>
                      {overview.evidence_rate === 0 && (
                        <div className="mt-2 p-2 rounded bg-muted/50 text-xs text-muted-foreground">
                          <p>No documents labeled yet. Label documents to see accuracy metrics.</p>
                        </div>
                      )}
                    </div>
                  )}
                </PhaseCard>
              </div>

              {/* Coverage + Doc Type Scoreboard */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Coverage Section */}
                <div className="bg-card rounded-lg border p-6" data-testid="coverage-section">
                  <h3 className="text-lg font-medium text-foreground mb-4">Coverage</h3>
                  <div className="space-y-4">
                    <ProgressBar
                      testId="label-coverage"
                      label="Label Coverage (truth)"
                      description="Labeled docs / total docs in run"
                      value={overview?.docs_reviewed || 0}
                      total={selectedBatch.docs_total}
                      percentage={selectedBatch.docs_total > 0 ? Math.round((overview?.docs_reviewed || 0) / selectedBatch.docs_total * 100) : 0}
                      color="green"
                      emptyMessage="Review documents to add truth labels for accuracy metrics."
                    />
                    <ProgressBar
                      testId="extraction-coverage"
                      label="Extraction Coverage"
                      description="Docs with extraction / total docs in run"
                      value={overview?.docs_with_extraction || 0}
                      total={selectedBatch.docs_total}
                      percentage={selectedBatch.docs_total > 0 ? Math.round((overview?.docs_with_extraction || 0) / selectedBatch.docs_total * 100) : 0}
                      color="blue"
                      emptyMessage="Run extraction pipeline to process documents."
                    />
                  </div>
                </div>

                {/* Doc Type Scoreboard */}
                <div className="bg-card rounded-lg border p-6" data-testid="doc-type-scoreboard">
                  <h3 className="text-lg font-medium text-foreground mb-4">
                    Doc Type Scoreboard
                  </h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm" data-testid="scoreboard-table">
                      <thead>
                        <tr className="border-b">
                          <th className="text-left py-2 font-medium text-muted-foreground">Type</th>
                          <th className="text-right py-2 font-medium text-muted-foreground">Classified</th>
                          <th className="text-right py-2 font-medium text-muted-foreground">Extracted</th>
                          <th className="text-right py-2 font-medium text-muted-foreground">
                            Presence
                          </th>
                          <th className="text-right py-2 font-medium text-muted-foreground">
                            Evidence
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.keys(selectedBatch.phases.classification.distribution).length === 0 ? (
                          <tr>
                            <td colSpan={5} className="py-4 text-center text-muted-foreground/70">
                              No doc types classified yet
                            </td>
                          </tr>
                        ) : (
                          Object.entries(selectedBatch.phases.classification.distribution)
                            .sort((a, b) => {
                              // Sort by "needs attention": lowest evidence_rate first, then lowest presence
                              const metricsA = docTypes.find((dt) => dt.doc_type === a[0]);
                              const metricsB = docTypes.find((dt) => dt.doc_type === b[0]);
                              const evidenceA = metricsA?.evidence_rate_pct ?? 100;
                              const evidenceB = metricsB?.evidence_rate_pct ?? 100;
                              if (evidenceA !== evidenceB) return evidenceA - evidenceB;
                              const presenceA = metricsA?.required_field_presence_pct ?? 100;
                              const presenceB = metricsB?.required_field_presence_pct ?? 100;
                              return presenceA - presenceB;
                            })
                            .map(([docType, classifiedCount]) => {
                              const extractionMetrics = docTypes.find((dt) => dt.doc_type === docType);
                              const evidenceRate = extractionMetrics?.evidence_rate_pct ?? null;
                              const presenceRate = extractionMetrics?.required_field_presence_pct ?? null;
                              const needsAttention = (evidenceRate !== null && evidenceRate < 50) || (presenceRate !== null && presenceRate < 50);
                              return (
                                <tr
                                  key={docType}
                                  className={cn(
                                    "border-b last:border-0",
                                    needsAttention && "bg-warning/5"
                                  )}
                                >
                                  <td className="py-2 text-foreground">
                                    {formatDocType(docType)}
                                  </td>
                                  <td className="py-2 text-right text-muted-foreground">
                                    {classifiedCount}
                                  </td>
                                  <td className="py-2 text-right text-muted-foreground">
                                    {extractionMetrics?.docs_total || 0}
                                  </td>
                                  <td className="py-2 text-right">
                                    {extractionMetrics ? (
                                      <ScoreBadge value={extractionMetrics.required_field_presence_pct} />
                                    ) : (
                                      <span className="text-xs text-muted-foreground/50">No data</span>
                                    )}
                                  </td>
                                  <td className="py-2 text-right">
                                    {extractionMetrics ? (
                                      <ScoreBadge value={extractionMetrics.evidence_rate_pct} />
                                    ) : (
                                      <span className="text-xs text-muted-foreground/50">No data</span>
                                    )}
                                  </td>
                                </tr>
                              );
                            })
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// Helper Components

function BatchStatusBadge({ status }: { status: "complete" | "partial" | "failed" }) {
  if (status === "complete") return <CompleteBadge />;
  if (status === "partial") return <PartialBadge />;
  return <FailBadge />;
}

function HealthSummaryBanner({ batch }: { batch: DetailedRunInfo }) {
  const { ingestion, classification, extraction, quality_gate } = batch.phases;

  const items = [
    {
      label: "ingested",
      value: ingestion.ingested,
      total: ingestion.discovered,
      ok: ingestion.failed === 0,
    },
    {
      label: "classified",
      value: classification.classified,
      total: ingestion.ingested,
      ok: classification.low_confidence === 0,
    },
    {
      label: "extracted",
      value: extraction.succeeded,
      total: extraction.attempted,
      ok: extraction.failed === 0,
    },
    {
      label: "pass",
      value: quality_gate.pass,
      total: quality_gate.pass + quality_gate.warn + quality_gate.fail,
      ok: quality_gate.fail === 0,
    },
  ];

  return (
    <div className="flex flex-wrap items-center gap-x-1 gap-y-2 mb-4 p-3 bg-muted/50 rounded-lg text-sm" data-testid="health-summary-banner">
      {items.map((item, idx) => (
        <div key={item.label} className="flex items-center">
          {idx > 0 && <span className="text-muted-foreground/50 mx-2">|</span>}
          <span className={cn("mr-1", item.ok ? "text-success" : "text-warning-foreground")}>
            {item.ok ? "✓" : "⚠"}
          </span>
          <span className="text-muted-foreground">
            {item.value}/{item.total} {item.label}
          </span>
        </div>
      ))}
    </div>
  );
}

interface PhaseCardProps {
  title: string;
  icon: React.ReactNode;
  color: "blue" | "purple" | "green" | "amber";
  healthStatus?: "healthy" | "warning" | "error";
  metrics: Array<{
    label: string;
    value: number;
    muted?: boolean;
    alert?: boolean;
    warning?: boolean;
    success?: boolean;
  }>;
  duration?: number | null;
  children?: React.ReactNode;
  testId?: string;
}

function PhaseCard({ title, icon, color, healthStatus, metrics, duration, children, testId }: PhaseCardProps) {
  const colorClasses = {
    blue: "bg-info/10 text-info",
    purple: "bg-secondary/10 text-secondary",
    green: "bg-success/10 text-success",
    amber: "bg-warning/10 text-warning-foreground",
  };

  const healthBorderClasses = {
    healthy: "border-t-4 border-t-success",
    warning: "border-t-4 border-t-warning",
    error: "border-t-4 border-t-destructive",
  };

  return (
    <div
      className={cn(
        "bg-card rounded-lg border p-4 h-full",
        healthStatus && healthBorderClasses[healthStatus]
      )}
      data-testid={testId}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div
            className={cn(
              "w-8 h-8 rounded-lg flex items-center justify-center",
              colorClasses[color]
            )}
          >
            {icon}
          </div>
          <h4 className="font-medium text-foreground">{title}</h4>
          {healthStatus && (
            <span
              className={cn(
                "w-2 h-2 rounded-full",
                healthStatus === "healthy" && "bg-success",
                healthStatus === "warning" && "bg-warning",
                healthStatus === "error" && "bg-destructive"
              )}
              title={healthStatus === "healthy" ? "All good" : healthStatus === "warning" ? "Needs attention" : "Has failures"}
            />
          )}
        </div>
        {duration !== undefined && duration !== null && (
          <span className="text-xs text-muted-foreground/70">{Math.round(duration / 1000)}s</span>
        )}
        {duration === null && (
          <span className="text-xs text-muted-foreground/50">—</span>
        )}
      </div>
      <div className="space-y-1">
        {metrics.map((m) => (
          <div
            key={m.label}
            className={cn(
              "flex justify-between text-sm px-1 -mx-1 rounded",
              m.alert && m.value > 0 && "bg-destructive/5"
            )}
          >
            <span className={cn("text-muted-foreground", m.muted && "text-muted-foreground/70")}>
              {m.label}
            </span>
            <span
              className={cn(
                "font-medium",
                m.alert && "text-destructive",
                m.warning && "text-warning-foreground",
                m.success && "text-success",
                !m.alert && !m.warning && !m.success && "text-foreground"
              )}
            >
              {m.value}
            </span>
          </div>
        ))}
      </div>
      {children}
    </div>
  );
}

interface ProgressBarProps {
  label: string;
  description?: string;
  value: number;
  total: number;
  percentage: number;
  color: "green" | "blue";
  testId?: string;
  alertThreshold?: number;
  emptyMessage?: string;
}

function ProgressBar({ label, description, value, total, percentage, color, testId, alertThreshold = 25, emptyMessage }: ProgressBarProps) {
  const colorClasses = {
    green: "bg-success",
    blue: "bg-accent",
  };

  const isLow = percentage < alertThreshold && percentage > 0;
  const isEmpty = percentage === 0;

  return (
    <div data-testid={testId}>
      <div className="flex justify-between text-sm mb-1">
        <div className="flex items-center gap-2">
          <span className={cn("font-medium", isEmpty || isLow ? "text-destructive" : "text-foreground")}>
            {label}
          </span>
          {isEmpty && (
            <span className="text-xs px-1.5 py-0.5 rounded bg-destructive/10 text-destructive">
              Needs Review
            </span>
          )}
          {isLow && (
            <WarningIcon className="w-4 h-4 text-warning" />
          )}
        </div>
        <span
          className={cn(isEmpty || isLow ? "text-destructive" : "text-muted-foreground")}
          data-testid={testId ? `${testId}-value` : undefined}
        >
          {value} / {total} ({percentage}%)
        </span>
      </div>
      {description && (
        <span className="text-muted-foreground/70 text-xs block mb-1">{description}</span>
      )}
      <div className="h-2 bg-muted rounded-full overflow-hidden">
        <div
          className={cn(
            "h-full rounded-full transition-all",
            isEmpty || isLow ? "bg-destructive/50" : colorClasses[color]
          )}
          style={{ width: `${Math.min(percentage, 100)}%` }}
        />
      </div>
      {isEmpty && emptyMessage && (
        <p className="mt-1 text-xs text-muted-foreground">{emptyMessage}</p>
      )}
    </div>
  );
}

function WarningIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
    </svg>
  );
}

// Icons
function ChevronIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
    </svg>
  );
}

function DownloadIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
      />
    </svg>
  );
}

function TagIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"
      />
    </svg>
  );
}

function ExtractIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"
      />
    </svg>
  );
}

function ShieldIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
      />
    </svg>
  );
}
