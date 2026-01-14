import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { CHART_COLORS } from "../../lib/chartUtils";

interface TrendDataPoint {
  run_id: string;
  timestamp?: string | null;
  accuracy: number;
  presence: number;
  evidence: number;
}

interface TrendAreaChartProps {
  data: TrendDataPoint[];
  showLegend?: boolean;
}

/**
 * Area chart for accuracy/presence/evidence trends over runs
 */
export function TrendAreaChart({ data, showLegend = true }: TrendAreaChartProps) {
  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
        No trend data available
      </div>
    );
  }

  // Format run_id for display (show last 8 chars)
  const formattedData = data.map(d => ({
    ...d,
    displayId: d.run_id.slice(-8),
  }));

  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart
        data={formattedData}
        margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
      >
        <defs>
          <linearGradient id="colorAccuracy" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={CHART_COLORS.chart1} stopOpacity={0.3} />
            <stop offset="95%" stopColor={CHART_COLORS.chart1} stopOpacity={0} />
          </linearGradient>
          <linearGradient id="colorPresence" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={CHART_COLORS.chart2} stopOpacity={0.3} />
            <stop offset="95%" stopColor={CHART_COLORS.chart2} stopOpacity={0} />
          </linearGradient>
          <linearGradient id="colorEvidence" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={CHART_COLORS.chart3} stopOpacity={0.3} />
            <stop offset="95%" stopColor={CHART_COLORS.chart3} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.5} />
        <XAxis
          dataKey="displayId"
          tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
          tickLine={false}
          axisLine={{ stroke: "hsl(var(--border))" }}
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
          labelFormatter={(label) => `Run: ...${label}`}
        />
        {showLegend && (
          <Legend
            verticalAlign="top"
            height={36}
            formatter={(value) => (
              <span className="text-xs text-foreground capitalize">{value}</span>
            )}
          />
        )}
        <Area
          type="monotone"
          dataKey="accuracy"
          stroke={CHART_COLORS.chart1}
          fill="url(#colorAccuracy)"
          strokeWidth={2}
        />
        <Area
          type="monotone"
          dataKey="presence"
          stroke={CHART_COLORS.chart2}
          fill="url(#colorPresence)"
          strokeWidth={2}
        />
        <Area
          type="monotone"
          dataKey="evidence"
          stroke={CHART_COLORS.chart3}
          fill="url(#colorEvidence)"
          strokeWidth={2}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
