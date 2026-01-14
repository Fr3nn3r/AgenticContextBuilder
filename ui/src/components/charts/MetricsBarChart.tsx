import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import type { BarChartDataPoint } from "../../lib/chartUtils";
import { CHART_COLORS } from "../../lib/chartUtils";

interface MetricsBarChartProps {
  data: BarChartDataPoint[];
  showLegend?: boolean;
}

/**
 * Grouped bar chart for doc type accuracy/presence/evidence comparison
 */
export function MetricsBarChart({ data, showLegend = true }: MetricsBarChartProps) {
  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
        No data available
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart
        data={data}
        margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
      >
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
        {showLegend && (
          <Legend
            verticalAlign="top"
            height={36}
            formatter={(value) => (
              <span className="text-xs text-foreground capitalize">{value}</span>
            )}
          />
        )}
        <Bar
          dataKey="accuracy"
          fill={CHART_COLORS.chart1}
          radius={[2, 2, 0, 0]}
          maxBarSize={40}
        />
        <Bar
          dataKey="presence"
          fill={CHART_COLORS.chart2}
          radius={[2, 2, 0, 0]}
          maxBarSize={40}
        />
        <Bar
          dataKey="evidence"
          fill={CHART_COLORS.chart3}
          radius={[2, 2, 0, 0]}
          maxBarSize={40}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}
