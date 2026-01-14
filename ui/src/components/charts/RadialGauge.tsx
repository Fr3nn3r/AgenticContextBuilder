import { RadialBarChart, RadialBar, ResponsiveContainer, PolarAngleAxis } from "recharts";
import { getGaugeColor } from "../../lib/chartUtils";

interface RadialGaugeProps {
  value: number;
  label: string;
  max?: number;
  size?: "sm" | "md" | "lg";
}

/**
 * Radial gauge chart for KPI percentages
 */
export function RadialGauge({ value, label, max = 100, size = "md" }: RadialGaugeProps) {
  const percentage = Math.min((value / max) * 100, 100);
  const color = getGaugeColor(percentage);

  const data = [{ name: label, value: percentage, fill: color }];

  const sizeConfig = {
    sm: { inner: 40, outer: 55, font: "text-lg" },
    md: { inner: 50, outer: 70, font: "text-2xl" },
    lg: { inner: 60, outer: 85, font: "text-3xl" },
  };

  const config = sizeConfig[size];

  return (
    <div className="relative w-full h-full">
      <ResponsiveContainer width="100%" height="100%">
        <RadialBarChart
          cx="50%"
          cy="50%"
          innerRadius={config.inner}
          outerRadius={config.outer}
          barSize={10}
          data={data}
          startAngle={180}
          endAngle={0}
        >
          <PolarAngleAxis
            type="number"
            domain={[0, 100]}
            angleAxisId={0}
            tick={false}
          />
          <RadialBar
            background={{ fill: "hsl(var(--muted))" }}
            dataKey="value"
            cornerRadius={5}
          />
        </RadialBarChart>
      </ResponsiveContainer>
      {/* Center text */}
      <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
        <span className={`${config.font} font-bold text-foreground`}>
          {Math.round(value)}%
        </span>
        <span className="text-xs text-muted-foreground">{label}</span>
      </div>
    </div>
  );
}
