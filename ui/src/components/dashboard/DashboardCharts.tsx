import {
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { CHART_COLORS } from "../../lib/chartUtils";
import type { DashboardClaim } from "../../types";

interface DashboardChartsProps {
  claims: DashboardClaim[];
}

interface ChartPoint {
  name: string;
  value: number;
  fill: string;
}

const TOOLTIP_STYLE = {
  backgroundColor: "hsl(var(--card))",
  border: "1px solid hsl(var(--border))",
  borderRadius: "8px",
  fontSize: "12px",
};

export function DashboardCharts({ claims }: DashboardChartsProps) {
  // Decision donut data
  const decisionCounts = { approve: 0, reject: 0, refer: 0 };
  for (const c of claims) {
    const d = c.decision?.toUpperCase();
    if (d === "APPROVE" || d === "APPROVED") decisionCounts.approve++;
    else if (d === "REJECT" || d === "DENIED") decisionCounts.reject++;
    else if (d === "REFER_TO_HUMAN") decisionCounts.refer++;
  }

  const donutData: ChartPoint[] = [
    { name: "Approved", value: decisionCounts.approve, fill: CHART_COLORS.success },
    { name: "Rejected", value: decisionCounts.reject, fill: CHART_COLORS.error },
    { name: "Refer", value: decisionCounts.refer, fill: CHART_COLORS.warning },
  ].filter((d) => d.value > 0);

  const donutTotal = donutData.reduce((s, d) => s + d.value, 0);

  // Denial reason bar chart data
  const reasonCounts: Record<string, number> = {};
  for (const c of claims) {
    const d = c.decision?.toUpperCase();
    if (d === "REJECT" || d === "DENIED") {
      const code = c.result_code || "Unknown";
      reasonCounts[code] = (reasonCounts[code] || 0) + 1;
    }
  }

  const barData = Object.entries(reasonCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([name, value]) => ({ name, value }));

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {/* Donut chart */}
      <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700 p-4">
        <h3 className="text-sm font-medium text-slate-700 dark:text-slate-200 mb-3">
          Decision Distribution
        </h3>
        <div className="h-64">
          {donutData.length === 0 ? (
            <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
              No assessment data
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={donutData}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={80}
                  paddingAngle={2}
                  dataKey="value"
                  label={({ name, percent }) =>
                    `${name} ${((percent ?? 0) * 100).toFixed(0)}%`
                  }
                  labelLine={false}
                >
                  {donutData.map((entry, i) => (
                    <Cell key={i} fill={entry.fill} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={TOOLTIP_STYLE}
                  formatter={(value, name) => [
                    `${value} (${((Number(value) / donutTotal) * 100).toFixed(1)}%)`,
                    name,
                  ]}
                />
                <Legend
                  verticalAlign="bottom"
                  height={36}
                  formatter={(value) => (
                    <span className="text-xs text-foreground">{value}</span>
                  )}
                />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Horizontal bar chart */}
      <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700 p-4">
        <h3 className="text-sm font-medium text-slate-700 dark:text-slate-200 mb-3">
          Denial Reasons
        </h3>
        <div className="h-64">
          {barData.length === 0 ? (
            <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
              No denials
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={barData}
                layout="vertical"
                margin={{ top: 5, right: 30, left: 10, bottom: 5 }}
              >
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={130}
                  tick={{ fontSize: 11 }}
                />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Bar
                  dataKey="value"
                  fill={CHART_COLORS.error}
                  radius={[0, 4, 4, 0]}
                  name="Claims"
                />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </div>
  );
}
