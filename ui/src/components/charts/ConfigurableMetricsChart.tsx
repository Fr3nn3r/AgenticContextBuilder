import { useState, useMemo } from "react";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { cn } from "../../lib/utils";
import type { BarChartDataPoint } from "../../lib/chartUtils";
import { CHART_COLORS } from "../../lib/chartUtils";

type ChartType = "bar" | "line" | "area";
type SortBy = "name" | "accuracy" | "presence" | "evidence";
type SortOrder = "asc" | "desc";

interface MetricConfig {
  key: "accuracy" | "presence" | "evidence";
  label: string;
  color: string;
  enabled: boolean;
}

interface ConfigurableMetricsChartProps {
  data: BarChartDataPoint[];
  title?: string;
}

const DEFAULT_METRICS: MetricConfig[] = [
  { key: "accuracy", label: "Accuracy", color: CHART_COLORS.chart1, enabled: true },
  { key: "presence", label: "Presence", color: CHART_COLORS.chart2, enabled: true },
  { key: "evidence", label: "Evidence", color: CHART_COLORS.chart3, enabled: true },
];

/**
 * Configurable chart for doc type metrics with user controls
 */
export function ConfigurableMetricsChart({ data, title = "Doc Type Performance" }: ConfigurableMetricsChartProps) {
  const [chartType, setChartType] = useState<ChartType>("bar");
  const [sortBy, setSortBy] = useState<SortBy>("name");
  const [sortOrder, setSortOrder] = useState<SortOrder>("asc");
  const [metrics, setMetrics] = useState<MetricConfig[]>(DEFAULT_METRICS);
  const [showConfig, setShowConfig] = useState(false);

  // Process and sort data
  const processedData = useMemo(() => {
    const sorted = [...data].sort((a, b) => {
      let aVal: string | number;
      let bVal: string | number;

      if (sortBy === "name") {
        aVal = a.name;
        bVal = b.name;
      } else {
        aVal = a[sortBy];
        bVal = b[sortBy];
      }

      if (typeof aVal === "string" && typeof bVal === "string") {
        return sortOrder === "asc"
          ? aVal.localeCompare(bVal)
          : bVal.localeCompare(aVal);
      }

      return sortOrder === "asc"
        ? (aVal as number) - (bVal as number)
        : (bVal as number) - (aVal as number);
    });

    return sorted;
  }, [data, sortBy, sortOrder]);

  const toggleMetric = (key: "accuracy" | "presence" | "evidence") => {
    setMetrics(prev =>
      prev.map(m => m.key === key ? { ...m, enabled: !m.enabled } : m)
    );
  };

  const enabledMetrics = metrics.filter(m => m.enabled);

  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
        No data available
      </div>
    );
  }

  const chartContent = (
    <ResponsiveContainer width="100%" height="100%">
      {chartType === "bar" ? (
        <BarChart data={processedData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.5} />
          <XAxis
            dataKey="name"
            tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
            tickLine={false}
            axisLine={{ stroke: "hsl(var(--border))" }}
            interval={0}
            angle={-45}
            textAnchor="end"
            height={60}
          />
          <YAxis
            tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
            tickLine={false}
            axisLine={{ stroke: "hsl(var(--border))" }}
            domain={[0, 100]}
            tickFormatter={(value) => `${value}%`}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: "8px",
              fontSize: "12px",
            }}
            formatter={(value) => [`${value}%`]}
          />
          <Legend verticalAlign="top" height={36} />
          {enabledMetrics.map(metric => (
            <Bar
              key={metric.key}
              dataKey={metric.key}
              name={metric.label}
              fill={metric.color}
              radius={[2, 2, 0, 0]}
              maxBarSize={40}
            />
          ))}
        </BarChart>
      ) : chartType === "line" ? (
        <LineChart data={processedData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.5} />
          <XAxis
            dataKey="name"
            tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
            tickLine={false}
            axisLine={{ stroke: "hsl(var(--border))" }}
            interval={0}
            angle={-45}
            textAnchor="end"
            height={60}
          />
          <YAxis
            tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
            tickLine={false}
            axisLine={{ stroke: "hsl(var(--border))" }}
            domain={[0, 100]}
            tickFormatter={(value) => `${value}%`}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: "8px",
              fontSize: "12px",
            }}
            formatter={(value) => [`${value}%`]}
          />
          <Legend verticalAlign="top" height={36} />
          {enabledMetrics.map(metric => (
            <Line
              key={metric.key}
              type="monotone"
              dataKey={metric.key}
              name={metric.label}
              stroke={metric.color}
              strokeWidth={2}
              dot={{ fill: metric.color, strokeWidth: 0 }}
            />
          ))}
        </LineChart>
      ) : (
        <AreaChart data={processedData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
          <defs>
            {enabledMetrics.map(metric => (
              <linearGradient key={`gradient-${metric.key}`} id={`gradient-${metric.key}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={metric.color} stopOpacity={0.3} />
                <stop offset="95%" stopColor={metric.color} stopOpacity={0} />
              </linearGradient>
            ))}
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.5} />
          <XAxis
            dataKey="name"
            tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
            tickLine={false}
            axisLine={{ stroke: "hsl(var(--border))" }}
            interval={0}
            angle={-45}
            textAnchor="end"
            height={60}
          />
          <YAxis
            tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
            tickLine={false}
            axisLine={{ stroke: "hsl(var(--border))" }}
            domain={[0, 100]}
            tickFormatter={(value) => `${value}%`}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: "8px",
              fontSize: "12px",
            }}
            formatter={(value) => [`${value}%`]}
          />
          <Legend verticalAlign="top" height={36} />
          {enabledMetrics.map(metric => (
            <Area
              key={metric.key}
              type="monotone"
              dataKey={metric.key}
              name={metric.label}
              stroke={metric.color}
              fill={`url(#gradient-${metric.key})`}
              strokeWidth={2}
            />
          ))}
        </AreaChart>
      )}
    </ResponsiveContainer>
  );

  return (
    <div className="bg-card rounded-lg border shadow-sm">
      {/* Header with title and config toggle */}
      <div className="flex items-center justify-between p-4 border-b">
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
        <button
          onClick={() => setShowConfig(!showConfig)}
          className={cn(
            "p-1.5 rounded transition-colors",
            showConfig
              ? "bg-accent text-accent-foreground"
              : "text-muted-foreground hover:text-foreground hover:bg-muted"
          )}
          title="Configure chart"
        >
          <SettingsIcon className="w-4 h-4" />
        </button>
      </div>

      {/* Config Panel */}
      {showConfig && (
        <div className="p-4 border-b bg-muted/30 space-y-4">
          <div className="grid grid-cols-3 gap-4">
            {/* Chart Type */}
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-2 block">Chart Type</label>
              <div className="flex gap-1">
                {([
                  { type: "bar" as ChartType, icon: <BarChartIcon className="w-4 h-4" /> },
                  { type: "line" as ChartType, icon: <LineChartIcon className="w-4 h-4" /> },
                  { type: "area" as ChartType, icon: <AreaChartIcon className="w-4 h-4" /> },
                ]).map(({ type, icon }) => (
                  <button
                    key={type}
                    onClick={() => setChartType(type)}
                    className={cn(
                      "p-2 rounded border transition-colors",
                      chartType === type
                        ? "bg-accent text-accent-foreground border-accent"
                        : "bg-background text-muted-foreground border-border hover:border-accent/50"
                    )}
                    title={`${type.charAt(0).toUpperCase() + type.slice(1)} chart`}
                  >
                    {icon}
                  </button>
                ))}
              </div>
            </div>

            {/* Sort By */}
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-2 block">Sort By</label>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as SortBy)}
                className="w-full px-2 py-1.5 text-sm border rounded bg-background"
              >
                <option value="name">Name</option>
                <option value="accuracy">Accuracy</option>
                <option value="presence">Presence</option>
                <option value="evidence">Evidence</option>
              </select>
            </div>

            {/* Sort Order */}
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-2 block">Order</label>
              <div className="flex gap-1">
                <button
                  onClick={() => setSortOrder("asc")}
                  className={cn(
                    "flex-1 px-3 py-1.5 text-xs rounded border transition-colors",
                    sortOrder === "asc"
                      ? "bg-accent text-accent-foreground border-accent"
                      : "bg-background text-muted-foreground border-border hover:border-accent/50"
                  )}
                >
                  Asc ↑
                </button>
                <button
                  onClick={() => setSortOrder("desc")}
                  className={cn(
                    "flex-1 px-3 py-1.5 text-xs rounded border transition-colors",
                    sortOrder === "desc"
                      ? "bg-accent text-accent-foreground border-accent"
                      : "bg-background text-muted-foreground border-border hover:border-accent/50"
                  )}
                >
                  Desc ↓
                </button>
              </div>
            </div>
          </div>

          {/* Metric Toggles */}
          <div>
            <label className="text-xs font-medium text-muted-foreground mb-2 block">Metrics</label>
            <div className="flex gap-2">
              {metrics.map(metric => (
                <button
                  key={metric.key}
                  onClick={() => toggleMetric(metric.key)}
                  className={cn(
                    "flex items-center gap-2 px-3 py-1.5 text-xs rounded border transition-colors",
                    metric.enabled
                      ? "bg-accent/10 border-accent text-foreground"
                      : "bg-background border-border text-muted-foreground hover:border-accent/50"
                  )}
                >
                  <span
                    className="w-3 h-3 rounded-sm"
                    style={{ backgroundColor: metric.enabled ? metric.color : "hsl(var(--muted))" }}
                  />
                  {metric.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Chart */}
      <div className="p-4 h-[280px]">
        {enabledMetrics.length === 0 ? (
          <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
            Select at least one metric to display
          </div>
        ) : (
          chartContent
        )}
      </div>
    </div>
  );
}

// Icons
function SettingsIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  );
}

function BarChartIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
    </svg>
  );
}

function LineChartIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4v16" />
    </svg>
  );
}

function AreaChartIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 3v18h18M7 16l4-4 4 4 5-6" />
    </svg>
  );
}
