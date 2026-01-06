import { cn } from "../lib/utils";
import type { ClaimRunInfo, InsightsOverview, DocTypeMetrics } from "../api/client";

// Human-readable doc type names
const docTypeNames: Record<string, string> = {
  loss_notice: "Loss Notice",
  police_report: "Police Report",
  insurance_policy: "Insurance Policy",
};

function getDocTypeName(docType: string): string {
  return docTypeNames[docType] || docType.replace(/_/g, " ");
}

interface DashboardProps {
  runs: ClaimRunInfo[];
  selectedRunId: string | null;
  onRunChange: (runId: string) => void;
  overview: InsightsOverview | null;
  docTypes: DocTypeMetrics[];
  loading?: boolean;
}

export function Dashboard({
  runs,
  selectedRunId,
  onRunChange,
  overview,
  docTypes,
  loading,
}: DashboardProps) {
  // Calculate coverage metrics
  const labelCoverage = overview && overview.docs_total > 0
    ? Math.round((overview.docs_reviewed / overview.docs_total) * 100)
    : 0;

  // Get selected run info
  const selectedRun = runs.find(r => r.run_id === selectedRunId);

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <h2 className="text-2xl font-semibold text-gray-900 mb-6">Calibration Home</h2>

      {/* Run Selector + Metadata */}
      <div className="bg-white rounded-lg border p-4 mb-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <label className="text-sm font-medium text-gray-700">Run:</label>
            <select
              value={selectedRunId || ""}
              onChange={(e) => onRunChange(e.target.value)}
              className="px-3 py-1.5 text-sm border rounded-md bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {runs.map((run, idx) => (
                <option key={run.run_id} value={run.run_id}>
                  {run.run_id} {idx === 0 ? "(Latest)" : ""}
                </option>
              ))}
            </select>
          </div>
          {selectedRun && (
            <div className="flex items-center gap-6 text-sm text-gray-600">
              <div>
                <span className="text-gray-400">Model:</span>{" "}
                <span className="font-medium">{selectedRun.model || "Unknown"}</span>
              </div>
              <div>
                <span className="text-gray-400">Date:</span>{" "}
                <span className="font-medium">
                  {selectedRun.timestamp
                    ? new Date(selectedRun.timestamp).toLocaleDateString()
                    : "Unknown"}
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="text-gray-500">Loading calibration data...</div>
        </div>
      ) : (
        <>
          {/* Calibration Metrics Grid */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
            <MetricCard
              label="Docs Labeled"
              value={`${overview?.docs_reviewed || 0}`}
              subtext={`of ${overview?.docs_total || 0} total`}
              icon={<CheckIcon />}
              color="blue"
            />
            <MetricCard
              label="Evaluated in Run"
              value={`${overview?.docs_total || 0}`}
              subtext="documents"
              icon={<DocsIcon />}
              color="gray"
            />
            <MetricCard
              label="Field Presence"
              value={`${overview?.required_field_presence_rate || 0}%`}
              subtext="required fields"
              icon={<FieldIcon />}
              color={getScoreColor(overview?.required_field_presence_rate || 0)}
            />
            <MetricCard
              label="Field Accuracy"
              value={`${overview?.required_field_accuracy || 0}%`}
              subtext="when present"
              icon={<AccuracyIcon />}
              color={getScoreColor(overview?.required_field_accuracy || 0)}
            />
            <MetricCard
              label="Evidence Rate"
              value={`${overview?.evidence_rate || 0}%`}
              subtext="with provenance"
              icon={<EvidenceIcon />}
              color={getScoreColor(overview?.evidence_rate || 0)}
            />
            <MetricCard
              label="Needs Vision"
              value={`${overview?.docs_needs_vision || 0}`}
              subtext="flagged docs"
              icon={<VisionIcon />}
              color="amber"
            />
          </div>

          {/* Secondary Row: Coverage Progress + Doc Type Scoreboard */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            {/* Coverage Progress */}
            <div className="bg-white rounded-lg border p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Coverage</h3>
              <div className="space-y-4">
                <ProgressBar
                  label="Label Coverage"
                  value={overview?.docs_reviewed || 0}
                  total={overview?.docs_total || 0}
                  percentage={labelCoverage}
                  color="green"
                />
                <ProgressBar
                  label="Run Coverage"
                  value={overview?.docs_with_extraction || 0}
                  total={overview?.docs_reviewed || 0}
                  percentage={overview?.run_coverage || 0}
                  color="blue"
                />
              </div>
              <div className="mt-4 pt-4 border-t space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Label Coverage</span>
                  <span className={cn(
                    "font-medium",
                    labelCoverage >= 80 ? "text-green-600" : labelCoverage >= 50 ? "text-amber-600" : "text-gray-600"
                  )}>
                    {labelCoverage}% ({overview?.docs_reviewed || 0} / {overview?.docs_total || 0})
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Run Coverage</span>
                  <span className={cn(
                    "font-medium",
                    (overview?.run_coverage || 0) >= 80 ? "text-blue-600" : (overview?.run_coverage || 0) >= 50 ? "text-amber-600" : "text-gray-600"
                  )}>
                    {overview?.run_coverage || 0}% ({overview?.docs_with_extraction || 0} / {overview?.docs_reviewed || 0})
                  </span>
                </div>
              </div>
            </div>

            {/* Mini Doc Type Scoreboard */}
            <div className="bg-white rounded-lg border p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Doc Type Scoreboard</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left py-2 font-medium text-gray-600">Type</th>
                      <th className="text-right py-2 font-medium text-gray-600">Reviewed</th>
                      <th className="text-right py-2 font-medium text-gray-600">Presence</th>
                      <th className="text-right py-2 font-medium text-gray-600">Accuracy</th>
                    </tr>
                  </thead>
                  <tbody>
                    {docTypes.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="py-4 text-center text-gray-400">
                          No doc types evaluated yet
                        </td>
                      </tr>
                    ) : (
                      docTypes.map((dt) => (
                        <tr key={dt.doc_type} className="border-b last:border-0">
                          <td className="py-2 text-gray-900">{getDocTypeName(dt.doc_type)}</td>
                          <td className="py-2 text-right text-gray-600">{dt.docs_reviewed}</td>
                          <td className="py-2 text-right">
                            <ScoreBadge value={dt.required_field_presence_pct} />
                          </td>
                          <td className="py-2 text-right">
                            <ScoreBadge value={dt.required_field_accuracy_pct} />
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Quality Summary */}
          <div className="bg-white rounded-lg border p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Quality Summary</h3>
            <div className="grid grid-cols-3 gap-6">
              <QualityStat
                label="Text Quality Good"
                value={overview?.docs_text_good || 0}
                total={overview?.docs_total || 0}
                color="green"
              />
              <QualityStat
                label="Text Quality Warn"
                value={overview?.docs_text_warn || 0}
                total={overview?.docs_total || 0}
                color="amber"
              />
              <QualityStat
                label="Text Quality Poor"
                value={overview?.docs_text_poor || 0}
                total={overview?.docs_total || 0}
                color="red"
              />
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// Helper functions
function getScoreColor(score: number): "green" | "amber" | "red" | "gray" {
  if (score >= 80) return "green";
  if (score >= 60) return "amber";
  if (score > 0) return "red";
  return "gray";
}

// Components
interface MetricCardProps {
  label: string;
  value: string;
  subtext: string;
  icon: React.ReactNode;
  color: "blue" | "green" | "amber" | "red" | "gray";
}

function MetricCard({ label, value, subtext, icon, color }: MetricCardProps) {
  const colorClasses = {
    blue: "bg-blue-50 text-blue-600",
    green: "bg-green-50 text-green-600",
    amber: "bg-amber-50 text-amber-600",
    red: "bg-red-50 text-red-600",
    gray: "bg-gray-50 text-gray-600",
  };

  return (
    <div className="bg-white rounded-lg border p-4">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs text-gray-500 mb-1">{label}</p>
          <p className="text-2xl font-semibold text-gray-900">{value}</p>
          <p className="text-xs text-gray-400 mt-0.5">{subtext}</p>
        </div>
        <div className={cn("w-10 h-10 rounded-lg flex items-center justify-center", colorClasses[color])}>
          {icon}
        </div>
      </div>
    </div>
  );
}

interface ProgressBarProps {
  label: string;
  value: number;
  total: number;
  percentage: number;
  color: "green" | "amber" | "red" | "blue";
  invert?: boolean;
}

function ProgressBar({ label, value, total, percentage, color, invert }: ProgressBarProps) {
  const colorClasses = {
    green: "bg-green-500",
    amber: "bg-amber-500",
    red: "bg-red-500",
    blue: "bg-blue-500",
  };

  // For inverted bars, higher is worse
  const displayPercentage = invert ? Math.min(percentage, 100) : percentage;
  const textColor = invert
    ? percentage > 10 ? "text-amber-600" : "text-green-600"
    : color === "blue"
    ? percentage >= 80 ? "text-blue-600" : percentage >= 50 ? "text-amber-600" : "text-gray-600"
    : percentage >= 80 ? "text-green-600" : percentage >= 50 ? "text-amber-600" : "text-gray-600";

  return (
    <div>
      <div className="flex justify-between text-sm mb-1.5">
        <span className="text-gray-700">{label}</span>
        <span className={cn("font-medium", textColor)}>
          {value} / {total}
        </span>
      </div>
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all", colorClasses[color])}
          style={{ width: `${displayPercentage}%` }}
        />
      </div>
    </div>
  );
}

function ScoreBadge({ value }: { value: number }) {
  const color = value >= 80 ? "text-green-600" : value >= 60 ? "text-amber-600" : "text-red-600";
  return <span className={cn("font-medium", color)}>{value}%</span>;
}

interface QualityStatProps {
  label: string;
  value: number;
  total: number;
  color: "green" | "amber" | "red";
}

function QualityStat({ label, value, total, color }: QualityStatProps) {
  const percentage = total > 0 ? Math.round((value / total) * 100) : 0;
  const colorClasses = {
    green: "text-green-600",
    amber: "text-amber-600",
    red: "text-red-600",
  };

  return (
    <div className="text-center">
      <div className={cn("text-3xl font-semibold", colorClasses[color])}>{value}</div>
      <div className="text-sm text-gray-500 mt-1">{label}</div>
      <div className="text-xs text-gray-400">{percentage}% of total</div>
    </div>
  );
}

// Icons
function CheckIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}

function DocsIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
    </svg>
  );
}

function FieldIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
    </svg>
  );
}

function AccuracyIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
    </svg>
  );
}

function EvidenceIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
    </svg>
  );
}

function VisionIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
    </svg>
  );
}
