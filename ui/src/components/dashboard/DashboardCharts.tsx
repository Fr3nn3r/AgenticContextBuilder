import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { CHART_COLORS } from "../../lib/chartUtils";
import type { DashboardClaim } from "../../types";

interface DashboardChartsProps {
  claims: DashboardClaim[];
}

const TOOLTIP_STYLE = {
  backgroundColor: "hsl(var(--card))",
  border: "1px solid hsl(var(--border))",
  borderRadius: "8px",
  fontSize: "12px",
};

function extractMake(vehicle: string | null): string {
  if (!vehicle) return "Unknown";
  const words = vehicle.trim().split(/\s+/);
  if (words.length === 0) return "Unknown";
  const first = words[0].toLowerCase();
  // Multi-word makes
  if (first === "land" && words.length > 1 && words[1].toLowerCase() === "rover") return "Land Rover";
  if (first === "alfa" && words.length > 1 && words[1].toLowerCase() === "romeo") return "Alfa Romeo";
  // Keep short all-caps (BMW, VW, MG, etc.)
  if (words[0].length <= 3 && words[0] === words[0].toUpperCase()) return words[0];
  return words[0].charAt(0).toUpperCase() + words[0].slice(1).toLowerCase();
}

export function DashboardCharts({ claims }: DashboardChartsProps) {
  // Car manufacturer bar chart data
  const makeCounts: Record<string, number> = {};
  for (const c of claims) {
    const make = extractMake(c.gt_vehicle);
    makeCounts[make] = (makeCounts[make] || 0) + 1;
  }

  const makeData = Object.entries(makeCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
    .map(([name, value]) => ({ name, value }));

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
      {/* Car Manufacturer chart */}
      <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700 p-4">
        <h3 className="text-sm font-medium text-slate-700 dark:text-slate-200 mb-3">
          Vehicle Manufacturer
        </h3>
        <div className="h-64">
          {makeData.length === 0 ? (
            <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
              No vehicle data
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={makeData}
                layout="vertical"
                margin={{ top: 5, right: 30, left: 10, bottom: 5 }}
              >
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={100}
                  tick={{ fontSize: 11 }}
                />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Bar
                  dataKey="value"
                  fill={CHART_COLORS.chart1}
                  radius={[0, 4, 4, 0]}
                  name="Claims"
                />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Denial reason bar chart */}
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
