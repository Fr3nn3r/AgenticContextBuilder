import { useState, useEffect } from "react";
import { cn } from "../lib/utils";
import { CHART_COLORS, type ChartDataPoint } from "../lib/chartUtils";
import {
  MetricCard,
  MetricCardRow,
  PageLoadingSkeleton,
  NoDataEmptyState,
} from "./shared";
import { ChartCard, DonutChart } from "./charts";
import {
  getCostOverview,
  getCostByOperation,
  getCostByRun,
  getCostByDay,
  getCostByModel,
  getCostByClaim,
} from "../api/client";
import type {
  CostOverview,
  CostByOperation,
  CostByRun,
  CostByDay,
  CostByModel,
  CostByClaim,
} from "../types";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  Cell,
} from "recharts";

/**
 * Token Cost Monitoring Dashboard
 *
 * Displays LLM token usage and costs across all pipeline operations
 * (classification, extraction, vision/OCR).
 */
export function TokenCostsPage() {
  // Data state
  const [overview, setOverview] = useState<CostOverview | null>(null);
  const [byOperation, setByOperation] = useState<CostByOperation[]>([]);
  const [byRun, setByRun] = useState<CostByRun[]>([]);
  const [dailyTrend, setDailyTrend] = useState<CostByDay[]>([]);
  const [byModel, setByModel] = useState<CostByModel[]>([]);

  // Drilldown state
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [claimsForRun, setClaimsForRun] = useState<CostByClaim[]>([]);

  // UI state
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load all data on mount
  useEffect(() => {
    loadAllData();
  }, []);

  async function loadAllData() {
    try {
      setLoading(true);
      setError(null);

      const [overviewData, operationData, runData, trendData, modelData] =
        await Promise.all([
          getCostOverview(),
          getCostByOperation(),
          getCostByRun(20),
          getCostByDay(30),
          getCostByModel(),
        ]);

      setOverview(overviewData);
      setByOperation(operationData);
      setByRun(runData);
      setDailyTrend(trendData);
      setByModel(modelData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load cost data");
    } finally {
      setLoading(false);
    }
  }

  // Load claims when run is selected
  async function handleRunClick(runId: string) {
    if (selectedRunId === runId) {
      setSelectedRunId(null);
      setClaimsForRun([]);
      return;
    }

    setSelectedRunId(runId);
    try {
      const claims = await getCostByClaim(runId);
      setClaimsForRun(claims);
    } catch {
      setClaimsForRun([]);
    }
  }

  if (loading) {
    return <PageLoadingSkeleton message="Loading token costs..." />;
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full">
        <p className="text-destructive mb-4">{error}</p>
        <button
          onClick={loadAllData}
          className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!overview || overview.total_calls === 0) {
    return (
      <div className="p-4">
        <NoDataEmptyState
          title="No LLM calls recorded"
          description="Token costs will appear here once you run the extraction pipeline."
        />
      </div>
    );
  }

  // Transform data for charts
  const operationChartData = transformOperationData(byOperation);
  const modelChartData = transformModelData(byModel);

  return (
    <div className="p-4 space-y-4">
      {/* KPI Row */}
      <MetricCardRow columns={5} testId="cost-kpi-row">
        <MetricCard
          testId="kpi-total-cost"
          label="Total Cost"
          value={formatCurrency(overview.total_cost_usd)}
          subtext={`${overview.total_calls.toLocaleString()} API calls`}
        />
        <MetricCard
          testId="kpi-total-tokens"
          label="Total Tokens"
          value={formatTokens(overview.total_tokens)}
          subtext={`${formatTokens(overview.total_prompt_tokens)} in / ${formatTokens(overview.total_completion_tokens)} out`}
        />
        <MetricCard
          testId="kpi-avg-cost-doc"
          label="Avg Cost/Doc"
          value={formatCurrency(overview.avg_cost_per_doc)}
          subtext={`${overview.docs_processed.toLocaleString()} docs processed`}
        />
        <MetricCard
          testId="kpi-calls-today"
          label="Calls Today"
          value={dailyTrend.length > 0 ? dailyTrend[dailyTrend.length - 1].call_count : 0}
          subtext={dailyTrend.length > 0 ? formatCurrency(dailyTrend[dailyTrend.length - 1].cost_usd) : "$0"}
        />
        <MetricCard
          testId="kpi-primary-model"
          label="Primary Model"
          value={formatModelName(overview.primary_model)}
          subtext="most used"
        />
      </MetricCardRow>

      {/* Charts Row 1: Operation & Model Breakdown */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <ChartCard title="Cost by Operation" height="h-[220px]">
          <DonutChart
            data={operationChartData}
            innerRadius={45}
            outerRadius={70}
            showLegend={true}
          />
        </ChartCard>
        <ChartCard title="Cost by Model" height="h-[220px]">
          <DonutChart
            data={modelChartData}
            innerRadius={45}
            outerRadius={70}
            showLegend={true}
          />
        </ChartCard>
      </div>

      {/* Chart Row 2: Daily Cost Trend */}
      <ChartCard title="Daily Cost Trend (Last 30 Days)" height="h-[250px]">
        <DailyCostChart data={dailyTrend} />
      </ChartCard>

      {/* Chart Row 3: Cost per Run */}
      <ChartCard title="Cost per Run" height="h-[300px]">
        <RunCostChart data={byRun} onRunClick={handleRunClick} selectedRunId={selectedRunId} />
      </ChartCard>

      {/* Drilldown Table: Runs with expandable claims */}
      <RunsTable
        runs={byRun}
        selectedRunId={selectedRunId}
        claimsForRun={claimsForRun}
        onRunClick={handleRunClick}
      />
    </div>
  );
}

// =============================================================================
// Helper Components
// =============================================================================

interface DailyCostChartProps {
  data: CostByDay[];
}

function DailyCostChart({ data }: DailyCostChartProps) {
  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
        No trend data available
      </div>
    );
  }

  // Format data for display
  const formattedData = data.map((d) => ({
    ...d,
    displayDate: d.date.slice(5), // MM-DD format
  }));

  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={formattedData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="colorCost" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={CHART_COLORS.chart1} stopOpacity={0.3} />
            <stop offset="95%" stopColor={CHART_COLORS.chart1} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.5} />
        <XAxis
          dataKey="displayDate"
          tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
          tickLine={false}
          axisLine={{ stroke: "hsl(var(--border))" }}
          interval="preserveStartEnd"
        />
        <YAxis
          tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
          tickLine={false}
          axisLine={{ stroke: "hsl(var(--border))" }}
          tickFormatter={(value) => `$${value}`}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "hsl(var(--card))",
            border: "1px solid hsl(var(--border))",
            borderRadius: "8px",
            fontSize: "12px",
          }}
          formatter={(value: number) => [`$${value.toFixed(2)}`, "Cost"]}
          labelFormatter={(label) => `Date: ${label}`}
        />
        <Legend
          verticalAlign="top"
          height={36}
          formatter={() => <span className="text-xs text-foreground">Daily Cost</span>}
        />
        <Area
          type="monotone"
          dataKey="cost_usd"
          stroke={CHART_COLORS.chart1}
          fill="url(#colorCost)"
          strokeWidth={2}
          name="cost"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

interface RunCostChartProps {
  data: CostByRun[];
  onRunClick: (runId: string) => void;
  selectedRunId: string | null;
}

function RunCostChart({ data, onRunClick, selectedRunId }: RunCostChartProps) {
  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
        No run data available
      </div>
    );
  }

  // Show last 10 runs, reversed for chronological order (oldest to newest)
  const chartData = data
    .slice(0, 10)
    .reverse()
    .map((r) => ({
      ...r,
      displayId: r.run_id.slice(-12),
      fill: r.run_id === selectedRunId ? CHART_COLORS.chart2 : CHART_COLORS.chart1,
    }));

  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart
        data={chartData}
        layout="vertical"
        margin={{ top: 10, right: 30, left: 80, bottom: 0 }}
        onClick={(e) => {
          if (e && e.activePayload && e.activePayload[0]) {
            onRunClick(e.activePayload[0].payload.run_id);
          }
        }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.5} />
        <XAxis
          type="number"
          tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
          tickLine={false}
          axisLine={{ stroke: "hsl(var(--border))" }}
          tickFormatter={(value) => `$${value}`}
        />
        <YAxis
          type="category"
          dataKey="displayId"
          tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
          tickLine={false}
          axisLine={{ stroke: "hsl(var(--border))" }}
          width={75}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "hsl(var(--card))",
            border: "1px solid hsl(var(--border))",
            borderRadius: "8px",
            fontSize: "12px",
          }}
          formatter={(value: number) => [`$${value.toFixed(2)}`, "Cost"]}
          labelFormatter={(label) => `Run: ...${label}`}
        />
        <Bar dataKey="cost_usd" radius={[0, 4, 4, 0]} cursor="pointer">
          {chartData.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={entry.fill} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

interface RunsTableProps {
  runs: CostByRun[];
  selectedRunId: string | null;
  claimsForRun: CostByClaim[];
  onRunClick: (runId: string) => void;
}

function RunsTable({ runs, selectedRunId, claimsForRun, onRunClick }: RunsTableProps) {
  return (
    <div className="bg-card rounded-lg border shadow-sm overflow-hidden">
      <div className="border-b bg-muted/50 px-4 py-2">
        <h3 className="text-sm font-semibold">Run Details</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b bg-muted/30">
              <th className="text-left p-2 font-medium">Run ID</th>
              <th className="text-left p-2 font-medium">Timestamp</th>
              <th className="text-left p-2 font-medium">Model</th>
              <th className="text-right p-2 font-medium">Claims</th>
              <th className="text-right p-2 font-medium">Docs</th>
              <th className="text-right p-2 font-medium">Tokens</th>
              <th className="text-right p-2 font-medium">Cost</th>
              <th className="text-right p-2 font-medium">Avg/Doc</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <>
                <tr
                  key={run.run_id}
                  onClick={() => onRunClick(run.run_id)}
                  className={cn(
                    "border-b cursor-pointer hover:bg-muted/50 transition-colors",
                    selectedRunId === run.run_id && "bg-accent/10"
                  )}
                >
                  <td className="p-2 font-mono text-[10px]">{run.run_id.slice(-16)}</td>
                  <td className="p-2 text-muted-foreground">
                    {run.timestamp ? formatTimestamp(run.timestamp) : "—"}
                  </td>
                  <td className="p-2">{formatModelName(run.model || "unknown")}</td>
                  <td className="p-2 text-right">{run.claims_count}</td>
                  <td className="p-2 text-right">{run.docs_count}</td>
                  <td className="p-2 text-right font-mono">{formatTokens(run.tokens)}</td>
                  <td className="p-2 text-right font-semibold text-accent">
                    {formatCurrency(run.cost_usd)}
                  </td>
                  <td className="p-2 text-right text-muted-foreground">
                    {formatCurrency(run.avg_cost_per_doc)}
                  </td>
                </tr>
                {/* Expanded claims row */}
                {selectedRunId === run.run_id && claimsForRun.length > 0 && (
                  <tr key={`${run.run_id}-claims`}>
                    <td colSpan={8} className="p-0 bg-muted/30">
                      <div className="px-4 py-2">
                        <div className="text-[10px] text-muted-foreground mb-1 uppercase tracking-wide">
                          Claims in this run
                        </div>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                          {claimsForRun.slice(0, 8).map((claim) => (
                            <div
                              key={claim.claim_id}
                              className="bg-card rounded border px-2 py-1 text-[10px]"
                            >
                              <span className="font-mono">{claim.claim_id}</span>
                              <span className="text-muted-foreground ml-2">
                                {claim.docs_count} docs · {formatCurrency(claim.cost_usd)}
                              </span>
                            </div>
                          ))}
                          {claimsForRun.length > 8 && (
                            <div className="text-[10px] text-muted-foreground flex items-center">
                              +{claimsForRun.length - 8} more
                            </div>
                          )}
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
            {runs.length === 0 && (
              <tr>
                <td colSpan={8} className="p-4 text-center text-muted-foreground">
                  No runs recorded
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// =============================================================================
// Data Transformation Functions
// =============================================================================

function transformOperationData(data: CostByOperation[]): ChartDataPoint[] {
  const colors = [CHART_COLORS.chart1, CHART_COLORS.chart2, CHART_COLORS.chart3, CHART_COLORS.chart4];
  return data.map((item, idx) => ({
    name: formatOperationName(item.operation),
    value: item.cost_usd,
    fill: colors[idx % colors.length],
  }));
}

function transformModelData(data: CostByModel[]): ChartDataPoint[] {
  const colors = [CHART_COLORS.chart1, CHART_COLORS.chart3, CHART_COLORS.chart2, CHART_COLORS.chart5];
  return data.map((item, idx) => ({
    name: formatModelName(item.model),
    value: item.cost_usd,
    fill: colors[idx % colors.length],
  }));
}

// =============================================================================
// Formatting Utilities
// =============================================================================

function formatCurrency(amount: number): string {
  if (amount >= 100) {
    return `$${amount.toFixed(0)}`;
  } else if (amount >= 1) {
    return `$${amount.toFixed(2)}`;
  } else if (amount >= 0.01) {
    return `$${amount.toFixed(3)}`;
  } else {
    return `$${amount.toFixed(4)}`;
  }
}

function formatTokens(tokens: number): string {
  if (tokens >= 1_000_000) {
    return `${(tokens / 1_000_000).toFixed(1)}M`;
  } else if (tokens >= 1_000) {
    return `${(tokens / 1_000).toFixed(1)}K`;
  } else {
    return tokens.toString();
  }
}

function formatModelName(model: string): string {
  // Shorten common model names
  return model
    .replace("gpt-4o-mini", "GPT-4o Mini")
    .replace("gpt-4o", "GPT-4o")
    .replace("gpt-4-turbo", "GPT-4 Turbo")
    .replace("gpt-4", "GPT-4")
    .replace("gpt-3.5-turbo", "GPT-3.5")
    .replace("claude-3-5-sonnet", "Claude 3.5 Sonnet")
    .replace("claude-3-opus", "Claude 3 Opus")
    .replace("claude-3-haiku", "Claude 3 Haiku");
}

function formatOperationName(operation: string): string {
  const names: Record<string, string> = {
    classification: "Classification",
    extraction: "Extraction",
    vision_ocr: "Vision/OCR",
    vision: "Vision/OCR",
    ocr: "Vision/OCR",
  };
  return names[operation] || operation.charAt(0).toUpperCase() + operation.slice(1);
}

function formatTimestamp(ts: string): string {
  try {
    const date = new Date(ts);
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return ts;
  }
}
