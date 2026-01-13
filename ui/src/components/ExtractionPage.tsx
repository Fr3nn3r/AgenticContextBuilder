import { useState, useMemo } from "react";
import { cn } from "../lib/utils";
import { formatDocType } from "../lib/formatters";
import {
  ScoreBadge,
  CompleteBadge,
  PartialBadge,
  FailBadge,
  PageLoadingSkeleton,
  SelectToViewEmptyState,
} from "./shared";
import type { DetailedRunInfo, InsightsOverview, DocTypeMetrics } from "../api/client";

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
  const [copiedBatchId, setCopiedBatchId] = useState(false);

  // Sort batches alphabetically by batch_id
  const sortedBatches = useMemo(() => {
    return [...batches].sort((a, b) => a.run_id.localeCompare(b.run_id));
  }, [batches]);

  const copyBatchId = () => {
    if (selectedBatch) {
      navigator.clipboard.writeText(selectedBatch.run_id);
      setCopiedBatchId(true);
      setTimeout(() => setCopiedBatchId(false), 2000);
    }
  };

  // Get doc types from classification distribution
  const docTypesInBatch = selectedBatch
    ? Object.keys(selectedBatch.phases.classification.distribution)
    : [];

  return (
    <div className="flex h-full" data-testid="extraction-page">
      {/* Left Panel: Batch History */}
      <div className="w-72 border-r bg-gray-50 flex flex-col">
        <div className="p-4 border-b bg-white">
          <h3 className="font-semibold text-gray-900">Batch History</h3>
          <p className="text-xs text-gray-500 mt-1">{batches.length} batches</p>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {sortedBatches.map((batch) => (
            <button
              key={batch.run_id}
              data-testid={`batch-item-${batch.run_id}`}
              onClick={() => onBatchChange(batch.run_id)}
              className={cn(
                "w-full text-left px-3 py-2 rounded-md mb-1 transition-colors",
                selectedBatchId === batch.run_id
                  ? "bg-blue-100 border border-blue-300"
                  : "hover:bg-gray-100"
              )}
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-900 truncate" title={batch.run_id}>
                  {batch.run_id}
                </span>
                <BatchStatusBadge status={batch.status} />
              </div>
              <div className="text-xs text-gray-400 mt-0.5">
                {batch.model || "Unknown model"} &bull; {batch.docs_total} docs
              </div>
            </button>
          ))}
          {batches.length === 0 && (
            <div className="text-center py-8 text-gray-400 text-sm">No batches found</div>
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
              {/* Batch Context Header */}
              <div className="bg-white rounded-lg border p-4 mb-6">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-500">Batch ID:</span>
                      <code className="text-sm bg-gray-100 px-2 py-0.5 rounded">
                        {selectedBatch.run_id}
                      </code>
                      <button
                        onClick={copyBatchId}
                        className="text-gray-400 hover:text-gray-600"
                        title="Copy batch ID"
                      >
                        {copiedBatchId ? (
                          <CheckIcon className="w-4 h-4 text-green-500" />
                        ) : (
                          <CopyIcon className="w-4 h-4" />
                        )}
                      </button>
                    </div>
                    <div className="flex items-center gap-4 mt-2 text-sm text-gray-600">
                      <span>
                        {selectedBatch.timestamp
                          ? new Date(selectedBatch.timestamp).toLocaleString()
                          : "Unknown time"}
                      </span>
                      <BatchStatusBadge status={selectedBatch.status} />
                      <span>
                        Duration:{" "}
                        {selectedBatch.duration_seconds
                          ? `${selectedBatch.duration_seconds}s`
                          : "—"}
                      </span>
                    </div>
                  </div>
                </div>
                <div className="flex flex-wrap gap-x-6 gap-y-2 mt-4 pt-4 border-t text-sm">
                  <div>
                    <span className="text-gray-500">Claims:</span>{" "}
                    <span className="font-medium">{selectedBatch.claims_count}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Docs:</span>{" "}
                    <span className="font-medium">{selectedBatch.docs_total}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Doc types:</span>{" "}
                    <span className="font-medium">
                      {docTypesInBatch.length > 0 ? docTypesInBatch.join(", ") : "—"}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500">Model:</span>{" "}
                    <span className="font-medium">{selectedBatch.model || "—"}</span>
                  </div>
                </div>
              </div>

              {/* Phase Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                {/* Ingestion Card */}
                <PhaseCard
                  title="Ingestion"
                  icon={<DownloadIcon />}
                  color="blue"
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
                            className="flex justify-between text-xs text-gray-500"
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
                      <div className="flex justify-between text-xs">
                        <span className="text-gray-500">Evidence rate</span>
                        <span className="font-medium">{overview.evidence_rate}%</span>
                      </div>
                    </div>
                  )}
                </PhaseCard>
              </div>

              {/* Coverage + Doc Type Scoreboard */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Coverage Section */}
                <div className="bg-white rounded-lg border p-6" data-testid="coverage-section">
                  <h3 className="text-lg font-medium text-gray-900 mb-4">Coverage</h3>
                  <div className="space-y-4">
                    <ProgressBar
                      testId="label-coverage"
                      label="Label Coverage (truth)"
                      description="Labeled docs / total docs in run"
                      value={overview?.docs_reviewed || 0}
                      total={selectedBatch.docs_total}
                      percentage={selectedBatch.docs_total > 0 ? Math.round((overview?.docs_reviewed || 0) / selectedBatch.docs_total * 100) : 0}
                      color="green"
                    />
                    <ProgressBar
                      testId="extraction-coverage"
                      label="Extraction Coverage"
                      description="Docs with extraction / total docs in run"
                      value={overview?.docs_with_extraction || 0}
                      total={selectedBatch.docs_total}
                      percentage={selectedBatch.docs_total > 0 ? Math.round((overview?.docs_with_extraction || 0) / selectedBatch.docs_total * 100) : 0}
                      color="blue"
                    />
                  </div>
                </div>

                {/* Doc Type Scoreboard */}
                <div className="bg-white rounded-lg border p-6" data-testid="doc-type-scoreboard">
                  <h3 className="text-lg font-medium text-gray-900 mb-4">
                    Doc Type Scoreboard
                  </h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm" data-testid="scoreboard-table">
                      <thead>
                        <tr className="border-b">
                          <th className="text-left py-2 font-medium text-gray-600">Type</th>
                          <th className="text-right py-2 font-medium text-gray-600">Classified</th>
                          <th className="text-right py-2 font-medium text-gray-600">Extracted</th>
                          <th className="text-right py-2 font-medium text-gray-600">
                            Presence
                          </th>
                          <th className="text-right py-2 font-medium text-gray-600">
                            Evidence
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.keys(selectedBatch.phases.classification.distribution).length === 0 ? (
                          <tr>
                            <td colSpan={5} className="py-4 text-center text-gray-400">
                              No doc types classified yet
                            </td>
                          </tr>
                        ) : (
                          Object.entries(selectedBatch.phases.classification.distribution)
                            .sort((a, b) => b[1] - a[1])
                            .map(([docType, classifiedCount]) => {
                              const extractionMetrics = docTypes.find((dt) => dt.doc_type === docType);
                              return (
                                <tr key={docType} className="border-b last:border-0">
                                  <td className="py-2 text-gray-900">
                                    {formatDocType(docType)}
                                  </td>
                                  <td className="py-2 text-right text-gray-600">
                                    {classifiedCount}
                                  </td>
                                  <td className="py-2 text-right text-gray-600">
                                    {extractionMetrics?.docs_total || 0}
                                  </td>
                                  <td className="py-2 text-right">
                                    {extractionMetrics ? (
                                      <ScoreBadge value={extractionMetrics.required_field_presence_pct} />
                                    ) : (
                                      <span className="text-gray-400">—</span>
                                    )}
                                  </td>
                                  <td className="py-2 text-right">
                                    {extractionMetrics ? (
                                      <ScoreBadge value={extractionMetrics.evidence_rate_pct} />
                                    ) : (
                                      <span className="text-gray-400">—</span>
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

interface PhaseCardProps {
  title: string;
  icon: React.ReactNode;
  color: "blue" | "purple" | "green" | "amber";
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

function PhaseCard({ title, icon, color, metrics, duration, children, testId }: PhaseCardProps) {
  const colorClasses = {
    blue: "bg-blue-50 text-blue-600",
    purple: "bg-purple-50 text-purple-600",
    green: "bg-green-50 text-green-600",
    amber: "bg-amber-50 text-amber-600",
  };

  return (
    <div className="bg-white rounded-lg border p-4" data-testid={testId}>
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
          <h4 className="font-medium text-gray-900">{title}</h4>
        </div>
        {duration !== undefined && duration !== null && (
          <span className="text-xs text-gray-400">{Math.round(duration / 1000)}s</span>
        )}
        {duration === null && (
          <span className="text-xs text-gray-300">—</span>
        )}
      </div>
      <div className="space-y-1">
        {metrics.map((m) => (
          <div key={m.label} className="flex justify-between text-sm">
            <span className={cn("text-gray-500", m.muted && "text-gray-400")}>
              {m.label}
            </span>
            <span
              className={cn(
                "font-medium",
                m.alert && "text-red-600",
                m.warning && "text-amber-600",
                m.success && "text-green-600",
                !m.alert && !m.warning && !m.success && "text-gray-900"
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
}

function ProgressBar({ label, description, value, total, percentage, color, testId }: ProgressBarProps) {
  const colorClasses = {
    green: "bg-green-500",
    blue: "bg-blue-500",
  };

  return (
    <div data-testid={testId}>
      <div className="flex justify-between text-sm mb-1">
        <div>
          <span className="text-gray-700 font-medium">{label}</span>
          {description && (
            <span className="text-gray-400 text-xs block">{description}</span>
          )}
        </div>
        <span className="text-gray-600" data-testid={testId ? `${testId}-value` : undefined}>
          {value} / {total} ({percentage}%)
        </span>
      </div>
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all", colorClasses[color])}
          style={{ width: `${Math.min(percentage, 100)}%` }}
        />
      </div>
    </div>
  );
}

// Icons
function CopyIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
      />
    </svg>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M5 13l4 4L19 7"
      />
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
