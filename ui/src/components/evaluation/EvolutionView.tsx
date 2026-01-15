import { useState, useEffect, useMemo } from "react";
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { cn } from "../../lib/utils";
import { formatDocType } from "../../lib/formatters";
import { getEvolutionTimeline } from "../../api/client";
import type {
  EvolutionSummary,
  EvolutionDataPoint,
  DocTypeEvolution,
} from "../../types";
import { PageLoadingSkeleton } from "../shared";

// =============================================================================
// INDUSTRIAL COLOR PALETTE - Data Visualization Theme
// =============================================================================

const EVOLUTION_COLORS = {
  scope: "#06b6d4",      // Cyan for scope/fields
  accuracy: "#22c55e",   // Green for accuracy
  docTypes: "#8b5cf6",   // Purple for doc types
  grid: "rgba(148, 163, 184, 0.15)",
  gridStrong: "rgba(148, 163, 184, 0.3)",
  text: {
    primary: "hsl(var(--foreground))",
    muted: "hsl(var(--muted-foreground))",
  },
};

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export function EvolutionView() {
  const [data, setData] = useState<EvolutionSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedVersion, setSelectedVersion] = useState<string | null>(null);

  useEffect(() => {
    loadEvolutionData();
  }, []);

  async function loadEvolutionData() {
    try {
      setLoading(true);
      const result = await getEvolutionTimeline();
      setData(result);
      // Select latest version by default
      if (result.timeline.length > 0) {
        setSelectedVersion(result.timeline[result.timeline.length - 1].spec_hash);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load evolution data");
    } finally {
      setLoading(false);
    }
  }

  const selectedPoint = useMemo(() => {
    if (!data || !selectedVersion) return null;
    return data.timeline.find((p) => p.spec_hash === selectedVersion) || null;
  }, [data, selectedVersion]);

  if (loading) {
    return <PageLoadingSkeleton message="Loading pipeline evolution..." />;
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64 text-destructive">
        {error}
      </div>
    );
  }

  if (!data || data.timeline.length === 0) {
    return <EmptyEvolution />;
  }

  return (
    <div className="space-y-6">
      {/* Summary Header */}
      <SummaryHeader data={data} />

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ScopeChart
          timeline={data.timeline}
          selectedVersion={selectedVersion}
          onSelectVersion={setSelectedVersion}
        />
        <AccuracyChart
          timeline={data.timeline}
          selectedVersion={selectedVersion}
          onSelectVersion={setSelectedVersion}
        />
      </div>

      {/* Version Timeline */}
      <VersionTimeline
        timeline={data.timeline}
        selectedVersion={selectedVersion}
        onSelectVersion={setSelectedVersion}
      />

      {/* Version Details + Matrix */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {selectedPoint && <VersionDetails point={selectedPoint} />}
        <div className={selectedPoint ? "xl:col-span-2" : "xl:col-span-3"}>
          <DocTypeMatrix
            matrix={data.doc_type_matrix}
            specVersions={data.spec_versions}
            selectedVersion={selectedVersion}
          />
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// SUMMARY HEADER
// =============================================================================

function SummaryHeader({ data }: { data: EvolutionSummary }) {
  const { scope_growth, accuracy_trend, timeline } = data;
  const versions = timeline.length;

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {/* Versions */}
      <SummaryCard
        label="SPEC VERSIONS"
        value={versions}
        icon={<VersionIcon />}
      />

      {/* Doc Types Growth */}
      <SummaryCard
        label="DOC TYPES"
        value={scope_growth.end_doc_types}
        delta={scope_growth.end_doc_types - scope_growth.start_doc_types}
        deltaLabel="from start"
        color="purple"
        icon={<DocTypeIcon />}
      />

      {/* Fields Growth */}
      <SummaryCard
        label="TOTAL FIELDS"
        value={scope_growth.end_fields}
        delta={scope_growth.fields_delta}
        deltaLabel="fields added"
        color="cyan"
        icon={<FieldIcon />}
      />

      {/* Accuracy Trend */}
      <SummaryCard
        label="ACCURACY"
        value={accuracy_trend.end_accuracy !== null ? `${accuracy_trend.end_accuracy}%` : "—"}
        delta={accuracy_trend.delta}
        deltaLabel="change"
        color={accuracy_trend.trend === "improving" ? "green" : accuracy_trend.trend === "regressing" ? "red" : "neutral"}
        icon={<AccuracyIcon />}
        isPercent
      />
    </div>
  );
}

interface SummaryCardProps {
  label: string;
  value: string | number;
  delta?: number | null;
  deltaLabel?: string;
  color?: "cyan" | "purple" | "green" | "red" | "neutral";
  icon?: React.ReactNode;
  isPercent?: boolean;
}

function SummaryCard({
  label,
  value,
  delta,
  deltaLabel,
  color = "neutral",
  icon,
  isPercent,
}: SummaryCardProps) {
  const colorClasses = {
    cyan: "border-cyan-500/30 bg-cyan-500/5",
    purple: "border-purple-500/30 bg-purple-500/5",
    green: "border-green-500/30 bg-green-500/5",
    red: "border-red-500/30 bg-red-500/5",
    neutral: "border-border bg-card",
  };

  const iconColors = {
    cyan: "text-cyan-500",
    purple: "text-purple-500",
    green: "text-green-500",
    red: "text-red-500",
    neutral: "text-muted-foreground",
  };

  return (
    <div
      className={cn(
        "rounded-lg border p-4 transition-all",
        colorClasses[color]
      )}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[10px] font-medium tracking-widest text-muted-foreground uppercase">
            {label}
          </p>
          <p className="text-2xl font-bold mt-1 font-mono tracking-tight">
            {value}
          </p>
          {delta !== null && delta !== undefined && (
            <p className="text-xs text-muted-foreground mt-1">
              <span
                className={cn(
                  "font-medium",
                  delta > 0 ? "text-green-500" : delta < 0 ? "text-red-500" : ""
                )}
              >
                {delta > 0 ? "+" : ""}
                {delta}
                {isPercent ? "%" : ""}
              </span>
              {deltaLabel && <span className="ml-1 opacity-70">{deltaLabel}</span>}
            </p>
          )}
        </div>
        {icon && <div className={cn("opacity-60", iconColors[color])}>{icon}</div>}
      </div>
    </div>
  );
}

// =============================================================================
// SCOPE CHART
// =============================================================================

interface ChartProps {
  timeline: EvolutionDataPoint[];
  selectedVersion: string | null;
  onSelectVersion: (version: string) => void;
}

function ScopeChart({ timeline, selectedVersion, onSelectVersion }: ChartProps) {
  const chartData = timeline.map((point, idx) => ({
    idx,
    version: point.spec_hash,
    fields: point.total_fields,
    docTypes: point.doc_types_count,
  }));

  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold">Pipeline Scope</h3>
          <p className="text-xs text-muted-foreground">Fields & doc types over versions</p>
        </div>
        <div className="flex items-center gap-4 text-xs">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-cyan-500" />
            Fields
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-purple-500" />
            Doc Types
          </span>
        </div>
      </div>
      <div className="h-[200px]">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={chartData}
            margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
            onClick={(e: any) => {
              if (e?.activePayload?.[0]?.payload?.version) {
                onSelectVersion(e.activePayload[0].payload.version);
              }
            }}
          >
            <defs>
              <linearGradient id="scopeFieldsGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={EVOLUTION_COLORS.scope} stopOpacity={0.3} />
                <stop offset="95%" stopColor={EVOLUTION_COLORS.scope} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke={EVOLUTION_COLORS.grid}
              vertical={false}
            />
            <XAxis
              dataKey="version"
              tick={{ fontSize: 9, fill: EVOLUTION_COLORS.text.muted }}
              tickLine={false}
              axisLine={{ stroke: EVOLUTION_COLORS.gridStrong }}
              interval="preserveStartEnd"
            />
            <YAxis
              tick={{ fontSize: 9, fill: EVOLUTION_COLORS.text.muted }}
              tickLine={false}
              axisLine={false}
              width={35}
            />
            <Tooltip content={<ScopeTooltip />} />
            {selectedVersion && (
              <ReferenceLine
                x={selectedVersion}
                stroke="hsl(var(--foreground))"
                strokeDasharray="3 3"
                strokeOpacity={0.5}
              />
            )}
            <Area
              type="stepAfter"
              dataKey="fields"
              stroke={EVOLUTION_COLORS.scope}
              fill="url(#scopeFieldsGrad)"
              strokeWidth={2}
            />
            <Line
              type="stepAfter"
              dataKey="docTypes"
              stroke={EVOLUTION_COLORS.docTypes}
              strokeWidth={2}
              dot={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function ScopeTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const data = payload[0].payload;
  return (
    <div className="bg-popover border rounded-lg p-3 shadow-lg text-xs">
      <p className="font-mono text-muted-foreground mb-2">v...{data.version}</p>
      <div className="space-y-1">
        <p className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-cyan-500" />
          <span className="font-medium">{data.fields}</span> fields
        </p>
        <p className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-purple-500" />
          <span className="font-medium">{data.docTypes}</span> doc types
        </p>
      </div>
    </div>
  );
}

// =============================================================================
// ACCURACY CHART
// =============================================================================

function AccuracyChart({ timeline, selectedVersion, onSelectVersion }: ChartProps) {
  const chartData = timeline.map((point, idx) => ({
    idx,
    version: point.spec_hash,
    accuracy: point.accuracy_rate,
    docs: point.docs_evaluated,
  }));

  const hasAccuracyData = chartData.some((d) => d.accuracy !== null);

  if (!hasAccuracyData) {
    return (
      <div className="rounded-lg border bg-card p-4">
        <div className="mb-4">
          <h3 className="text-sm font-semibold">Accuracy Trend</h3>
          <p className="text-xs text-muted-foreground">Performance against ground truth</p>
        </div>
        <div className="h-[200px] flex items-center justify-center text-muted-foreground text-sm">
          No accuracy data available yet
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold">Accuracy Trend</h3>
          <p className="text-xs text-muted-foreground">Performance against ground truth</p>
        </div>
        <div className="flex items-center gap-1.5 text-xs">
          <span className="w-2 h-2 rounded-full bg-green-500" />
          Accuracy %
        </div>
      </div>
      <div className="h-[200px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={chartData}
            margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
            onClick={(e: any) => {
              if (e?.activePayload?.[0]?.payload?.version) {
                onSelectVersion(e.activePayload[0].payload.version);
              }
            }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke={EVOLUTION_COLORS.grid}
              vertical={false}
            />
            <XAxis
              dataKey="version"
              tick={{ fontSize: 9, fill: EVOLUTION_COLORS.text.muted }}
              tickLine={false}
              axisLine={{ stroke: EVOLUTION_COLORS.gridStrong }}
              interval="preserveStartEnd"
            />
            <YAxis
              tick={{ fontSize: 9, fill: EVOLUTION_COLORS.text.muted }}
              tickLine={false}
              axisLine={false}
              domain={[0, 100]}
              width={35}
              tickFormatter={(v) => `${v}%`}
            />
            <Tooltip content={<AccuracyTooltip />} />
            {/* Target line at 80% */}
            <ReferenceLine
              y={80}
              stroke={EVOLUTION_COLORS.accuracy}
              strokeDasharray="6 3"
              strokeOpacity={0.3}
              label={{
                value: "Target",
                position: "right",
                fontSize: 9,
                fill: EVOLUTION_COLORS.text.muted,
              }}
            />
            {selectedVersion && (
              <ReferenceLine
                x={selectedVersion}
                stroke="hsl(var(--foreground))"
                strokeDasharray="3 3"
                strokeOpacity={0.5}
              />
            )}
            <Line
              type="monotone"
              dataKey="accuracy"
              stroke={EVOLUTION_COLORS.accuracy}
              strokeWidth={2}
              dot={{ fill: EVOLUTION_COLORS.accuracy, r: 3 }}
              activeDot={{ r: 5, strokeWidth: 2 }}
              connectNulls
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function AccuracyTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const data = payload[0].payload;
  return (
    <div className="bg-popover border rounded-lg p-3 shadow-lg text-xs">
      <p className="font-mono text-muted-foreground mb-2">v...{data.version}</p>
      <div className="space-y-1">
        {data.accuracy !== null ? (
          <>
            <p className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-green-500" />
              <span className="font-medium">{data.accuracy}%</span> accuracy
            </p>
            <p className="text-muted-foreground">
              {data.docs} docs evaluated
            </p>
          </>
        ) : (
          <p className="text-muted-foreground">No accuracy data</p>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// VERSION TIMELINE
// =============================================================================

interface VersionTimelineProps {
  timeline: EvolutionDataPoint[];
  selectedVersion: string | null;
  onSelectVersion: (version: string) => void;
}

function VersionTimeline({
  timeline,
  selectedVersion,
  onSelectVersion,
}: VersionTimelineProps) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <h3 className="text-sm font-semibold mb-4">Version Timeline</h3>
      <div className="relative">
        {/* Timeline track */}
        <div className="absolute top-1/2 left-0 right-0 h-px bg-border -translate-y-1/2" />

        {/* Version markers */}
        <div className="relative flex justify-between items-center px-2">
          {timeline.map((point, idx) => {
            const isSelected = point.spec_hash === selectedVersion;
            const isFirst = idx === 0;
            const isLast = idx === timeline.length - 1;

            return (
              <button
                key={point.spec_hash}
                onClick={() => onSelectVersion(point.spec_hash)}
                className={cn(
                  "relative flex flex-col items-center transition-all group",
                  isSelected ? "z-10" : "z-0"
                )}
              >
                {/* Marker */}
                <div
                  className={cn(
                    "w-3 h-3 rounded-full border-2 transition-all",
                    isSelected
                      ? "bg-foreground border-foreground scale-125"
                      : "bg-background border-muted-foreground/50 group-hover:border-foreground group-hover:scale-110"
                  )}
                />

                {/* Label */}
                <div
                  className={cn(
                    "mt-2 text-[10px] font-mono transition-all",
                    isSelected ? "text-foreground font-medium" : "text-muted-foreground"
                  )}
                >
                  {isFirst ? "v1" : isLast ? `v${timeline.length}` : ""}
                </div>

                {/* Tooltip on hover */}
                <div
                  className={cn(
                    "absolute -top-12 left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none",
                    isSelected && "opacity-100"
                  )}
                >
                  <div className="bg-popover border rounded px-2 py-1 text-[10px] whitespace-nowrap shadow-lg">
                    <span className="font-mono">{point.spec_hash}</span>
                    <span className="text-muted-foreground ml-2">
                      {point.total_fields} fields
                    </span>
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// VERSION DETAILS
// =============================================================================

function VersionDetails({ point }: { point: EvolutionDataPoint }) {
  const formatDate = (iso: string) => {
    return new Date(iso).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  };

  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-2 h-2 rounded-full bg-foreground" />
        <h3 className="text-sm font-semibold font-mono">{point.spec_hash}</h3>
      </div>

      <div className="space-y-4">
        {/* Scope */}
        <div>
          <p className="text-[10px] font-medium tracking-widest text-muted-foreground uppercase mb-2">
            SCOPE
          </p>
          <div className="grid grid-cols-2 gap-2">
            <div className="rounded bg-muted/50 p-2">
              <p className="text-lg font-bold font-mono">{point.doc_types_count}</p>
              <p className="text-[10px] text-muted-foreground">Doc Types</p>
            </div>
            <div className="rounded bg-muted/50 p-2">
              <p className="text-lg font-bold font-mono">{point.total_fields}</p>
              <p className="text-[10px] text-muted-foreground">Total Fields</p>
            </div>
          </div>
        </div>

        {/* Accuracy */}
        <div>
          <p className="text-[10px] font-medium tracking-widest text-muted-foreground uppercase mb-2">
            ACCURACY
          </p>
          <div className="rounded bg-muted/50 p-2">
            {point.accuracy_rate !== null ? (
              <>
                <p className="text-lg font-bold font-mono">
                  {point.accuracy_rate}%
                </p>
                <p className="text-[10px] text-muted-foreground">
                  {point.correct_count} correct / {point.correct_count + point.incorrect_count + point.missing_count} total
                </p>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">No eval data</p>
            )}
          </div>
        </div>

        {/* Metadata */}
        <div>
          <p className="text-[10px] font-medium tracking-widest text-muted-foreground uppercase mb-2">
            METADATA
          </p>
          <div className="space-y-1 text-xs">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Model</span>
              <span className="font-mono">{point.model_name}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Version</span>
              <span className="font-mono">{point.contextbuilder_version}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">First seen</span>
              <span>{formatDate(point.first_seen)}</span>
            </div>
            {point.git_commit && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Commit</span>
                <span className="font-mono">{point.git_commit}</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// DOC TYPE MATRIX
// =============================================================================

interface DocTypeMatrixProps {
  matrix: DocTypeEvolution[];
  specVersions: string[];
  selectedVersion: string | null;
}

function DocTypeMatrix({ matrix, specVersions, selectedVersion }: DocTypeMatrixProps) {
  if (matrix.length === 0) {
    return (
      <div className="rounded-lg border bg-card p-4">
        <h3 className="text-sm font-semibold mb-4">Doc Type Matrix</h3>
        <p className="text-sm text-muted-foreground text-center py-8">
          No doc type evolution data
        </p>
      </div>
    );
  }

  // Build lookup for quick access
  const matrixLookup = new Map<string, Map<string, { field_count: number; accuracy_rate: number | null }>>();
  for (const dt of matrix) {
    const versionMap = new Map<string, { field_count: number; accuracy_rate: number | null }>();
    for (const app of dt.appearances) {
      versionMap.set(app.spec_hash, { field_count: app.field_count, accuracy_rate: app.accuracy_rate });
    }
    matrixLookup.set(dt.doc_type, versionMap);
  }

  return (
    <div className="rounded-lg border bg-card p-4">
      <h3 className="text-sm font-semibold mb-4">Doc Type Evolution Matrix</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b">
              <th className="text-left p-2 font-medium text-muted-foreground">Doc Type</th>
              {specVersions.map((v, idx) => (
                <th
                  key={v}
                  className={cn(
                    "text-center p-2 font-mono font-normal",
                    v === selectedVersion ? "bg-foreground/5" : ""
                  )}
                >
                  v{idx + 1}
                </th>
              ))}
              <th className="text-center p-2 font-medium text-muted-foreground">Current</th>
            </tr>
          </thead>
          <tbody>
            {matrix.map((dt) => (
              <tr key={dt.doc_type} className="border-b border-border/50">
                <td className="p-2 font-medium">{formatDocType(dt.doc_type)}</td>
                {specVersions.map((v) => {
                  const entry = matrixLookup.get(dt.doc_type)?.get(v);
                  const isSelected = v === selectedVersion;
                  return (
                    <td
                      key={v}
                      className={cn(
                        "text-center p-2",
                        isSelected ? "bg-foreground/5" : ""
                      )}
                    >
                      {entry ? (
                        <div className="flex flex-col items-center gap-0.5">
                          <span className="font-mono">{entry.field_count}</span>
                          {entry.accuracy_rate !== null && (
                            <span
                              className={cn(
                                "text-[9px] px-1 rounded",
                                entry.accuracy_rate >= 80
                                  ? "bg-green-500/20 text-green-600"
                                  : entry.accuracy_rate >= 60
                                  ? "bg-amber-500/20 text-amber-600"
                                  : "bg-red-500/20 text-red-600"
                              )}
                            >
                              {entry.accuracy_rate}%
                            </span>
                          )}
                        </div>
                      ) : (
                        <span className="text-muted-foreground/40">—</span>
                      )}
                    </td>
                  );
                })}
                <td className="text-center p-2 font-mono font-medium">
                  {dt.current_fields}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 mt-4 text-[10px] text-muted-foreground">
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded bg-green-500/20" /> 80%+
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded bg-amber-500/20" /> 60-79%
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded bg-red-500/20" /> &lt;60%
        </span>
        <span>— Not supported</span>
      </div>
    </div>
  );
}

// =============================================================================
// EMPTY STATE
// =============================================================================

function EmptyEvolution() {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="w-16 h-16 rounded-full bg-muted/50 flex items-center justify-center mb-4">
        <svg
          className="w-8 h-8 text-muted-foreground"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
          />
        </svg>
      </div>
      <h3 className="text-lg font-semibold mb-2">No Evolution Data Yet</h3>
      <p className="text-sm text-muted-foreground max-w-md">
        Run the extraction pipeline to start tracking how your pipeline scope and accuracy evolve over time.
      </p>
    </div>
  );
}

// =============================================================================
// ICONS
// =============================================================================

function VersionIcon() {
  return (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}

function DocTypeIcon() {
  return (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
    </svg>
  );
}

function FieldIcon() {
  return (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
    </svg>
  );
}

function AccuracyIcon() {
  return (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}
