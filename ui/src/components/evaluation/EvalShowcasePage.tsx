import { useEffect, useState, useRef, useCallback } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import {
  Target,
  TrendingUp,
  Award,
  Star,
  Trophy,
  Loader2,
  AlertCircle,
} from "lucide-react";
import { RadialGauge } from "../charts/RadialGauge";
import { ChartCard } from "../charts/ChartCard";
import {
  getEvalShowcaseData,
  type EvalShowcaseRun,
  type EvalShowcaseData,
} from "../../api/client";
import "./eval-showcase.css";

// =============================================================================
// TYPES
// =============================================================================

interface FilteredRun {
  index: number;
  run: EvalShowcaseRun;
  accuracy: number;
  frr: number;
  far: number;
  totalProcessed: number;
}

// =============================================================================
// HELPER: AnimatedCounter
// =============================================================================

function AnimatedCounter({
  target,
  suffix = "",
  prefix = "",
  duration = 2000,
  decimals = 0,
}: {
  target: number;
  suffix?: string;
  prefix?: string;
  duration?: number;
  decimals?: number;
}) {
  const [value, setValue] = useState(0);
  const rafRef = useRef<number>(0);
  const startRef = useRef<number>(0);

  useEffect(() => {
    startRef.current = performance.now();
    const animate = (now: number) => {
      const elapsed = now - startRef.current;
      const progress = Math.min(elapsed / duration, 1);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(eased * target);
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(animate);
      }
    };
    rafRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(rafRef.current);
  }, [target, duration]);

  return (
    <span>
      {prefix}
      {value.toFixed(decimals)}
      {suffix}
    </span>
  );
}

// =============================================================================
// HELPER: GlassCard
// =============================================================================

function GlassCard({
  children,
  className = "",
  glow = false,
}: {
  children: React.ReactNode;
  className?: string;
  glow?: boolean;
}) {
  return (
    <div
      className={`glass-card p-6 ${glow ? "glow-border" : ""} ${className}`}
    >
      {children}
    </div>
  );
}

// =============================================================================
// HELPER: Sparkline
// =============================================================================

function Sparkline({
  data,
  color = "#22c55e",
  height = 40,
}: {
  data: number[];
  color?: string;
  height?: number;
}) {
  const chartData = data.map((v, i) => ({ i, v }));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={chartData} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
        <defs>
          <linearGradient id={`spark-${color.replace("#", "")}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.3} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <Area
          type="monotone"
          dataKey="v"
          stroke={color}
          strokeWidth={1.5}
          fill={`url(#spark-${color.replace("#", "")})`}
          dot={false}
          isAnimationActive={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

// =============================================================================
// HELPER: MilestoneTimeline
// =============================================================================

const MILESTONE_CONFIG = [
  { threshold: 50, icon: Target, label: "50% — First signal", color: "#f59e0b" },
  { threshold: 80, icon: TrendingUp, label: "80% — Production-viable", color: "#3b82f6" },
  { threshold: 90, icon: Award, label: "90% — High accuracy", color: "#8b5cf6" },
  { threshold: 95, icon: Star, label: "95% — Near-perfect", color: "#14b8a6" },
  { threshold: 100, icon: Trophy, label: "100% — Perfect score", color: "#22c55e" },
] as const;

function MilestoneTimeline({ runs }: { runs: FilteredRun[] }) {
  const milestones = MILESTONE_CONFIG.map((m) => {
    const firstRun = runs.find((r) => r.accuracy >= m.threshold);
    return {
      ...m,
      reached: !!firstRun,
      runIndex: firstRun?.index,
      date: firstRun
        ? new Date(firstRun.run.timestamp).toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
          })
        : null,
    };
  });

  return (
    <div className="relative pl-8">
      {/* Vertical line */}
      <div className="timeline-line absolute left-[15px] top-2 bottom-2 w-[3px] rounded-full" />

      <div className="space-y-6">
        {milestones.map((m) => {
          const Icon = m.icon;
          return (
            <div key={m.threshold} className="relative flex items-center gap-4">
              {/* Dot on line */}
              <div
                className="absolute -left-8 flex h-8 w-8 items-center justify-center rounded-full border-2"
                style={{
                  borderColor: m.reached ? m.color : "hsl(var(--muted))",
                  backgroundColor: m.reached
                    ? `${m.color}20`
                    : "hsl(var(--muted) / 0.3)",
                }}
              >
                <Icon
                  size={16}
                  style={{ color: m.reached ? m.color : "hsl(var(--muted-foreground))" }}
                />
              </div>
              <div className="flex-1">
                <div
                  className="text-sm font-semibold"
                  style={{ color: m.reached ? m.color : "hsl(var(--muted-foreground))" }}
                >
                  {m.label}
                </div>
                {m.reached && m.date && (
                  <div className="text-xs text-muted-foreground">
                    Reached on {m.date} (eval #{m.runIndex! + 1})
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// =============================================================================
// HELPER: ConfusionHeatmap
// =============================================================================

function ConfusionHeatmap({ run }: { run: EvalShowcaseRun }) {
  const m = run.metrics;
  const cells = [
    {
      label: "Approve → Approve",
      value: m.approved_correct,
      total: m.approved_total,
      correct: true,
    },
    {
      label: "Approve → Deny",
      value: m.approved_total - m.approved_correct,
      total: m.approved_total,
      correct: false,
    },
    {
      label: "Deny → Approve",
      value: m.denied_total - m.denied_correct,
      total: m.denied_total,
      correct: false,
    },
    {
      label: "Deny → Deny",
      value: m.denied_correct,
      total: m.denied_total,
      correct: true,
    },
  ];

  return (
    <div>
      <div className="mb-3 grid grid-cols-3 gap-1 text-xs text-muted-foreground">
        <div />
        <div className="text-center font-medium">Pred: Approve</div>
        <div className="text-center font-medium">Pred: Deny</div>
      </div>
      <div className="grid grid-cols-3 gap-2">
        <div className="flex items-center text-xs font-medium text-muted-foreground">
          Actual: Approve
        </div>
        {cells.slice(0, 2).map((c, i) => (
          <div
            key={i}
            className={`flex flex-col items-center justify-center rounded-lg p-4 ${
              c.correct ? "matrix-cell-correct" : "matrix-cell-error"
            }`}
            style={{
              backgroundColor: c.correct
                ? `oklch(0.65 0.15 145 / ${0.1 + (c.value / Math.max(c.total, 1)) * 0.3})`
                : c.value > 0
                  ? `oklch(0.6 0.2 25 / ${0.05 + (c.value / Math.max(c.total, 1)) * 0.2})`
                  : "hsl(var(--muted) / 0.2)",
            }}
          >
            <span className="text-2xl font-bold text-foreground">{c.value}</span>
            <span className="text-xs text-muted-foreground mt-1">
              /{c.total}
            </span>
          </div>
        ))}

        <div className="flex items-center text-xs font-medium text-muted-foreground">
          Actual: Deny
        </div>
        {cells.slice(2, 4).map((c, i) => (
          <div
            key={i + 2}
            className={`flex flex-col items-center justify-center rounded-lg p-4 ${
              c.correct ? "matrix-cell-correct" : "matrix-cell-error"
            }`}
            style={{
              backgroundColor: c.correct
                ? `oklch(0.65 0.15 145 / ${0.1 + (c.value / Math.max(c.total, 1)) * 0.3})`
                : c.value > 0
                  ? `oklch(0.6 0.2 25 / ${0.05 + (c.value / Math.max(c.total, 1)) * 0.2})`
                  : "hsl(var(--muted) / 0.2)",
            }}
          >
            <span className="text-2xl font-bold text-foreground">{c.value}</span>
            <span className="text-xs text-muted-foreground mt-1">
              /{c.total}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// =============================================================================
// DATA PROCESSING
// =============================================================================

/** Filter out partial runs (< 10 claims processed) */
function filterRuns(data: EvalShowcaseData): FilteredRun[] {
  let idx = 0;
  return data.runs
    .map((run) => {
      const totalProcessed =
        run.metrics.decision_correct + run.metrics.decision_wrong;
      return { run, totalProcessed };
    })
    .filter((r) => r.totalProcessed >= 10)
    .map((r) => ({
      index: idx++,
      run: r.run,
      accuracy: r.run.metrics.decision_accuracy * 100,
      frr: r.run.metrics.false_reject_rate * 100,
      far: r.run.metrics.false_approve_rate * 100,
      totalProcessed: r.totalProcessed,
    }));
}

/** Consolidate rare error categories into "Other" */
function getErrorStreamData(runs: FilteredRun[]) {
  // Collect all categories and their total counts
  const categoryCounts = new Map<string, number>();
  for (const r of runs) {
    for (const e of r.run.top_errors) {
      categoryCounts.set(
        e.category,
        (categoryCounts.get(e.category) || 0) + e.count
      );
    }
  }

  // Determine which categories to keep (total >= 5)
  const keepCategories = new Set<string>();
  for (const [cat, count] of categoryCounts) {
    if (count >= 5) keepCategories.add(cat);
  }

  // Build data points
  return runs.map((r) => {
    const point: Record<string, number | string> = {
      label: `#${r.index + 1}`,
    };
    let otherCount = 0;
    for (const e of r.run.top_errors) {
      if (keepCategories.has(e.category)) {
        point[e.category] = e.count;
      } else {
        otherCount += e.count;
      }
    }
    if (otherCount > 0) point["other"] = otherCount;
    return point;
  });
}

/** Human-friendly error category labels */
function formatCategory(cat: string): string {
  return cat
    .replace(/_/g, " ")
    .replace(/:/g, " — ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

const ERROR_COLORS = [
  "#ef4444", // red
  "#f59e0b", // amber
  "#8b5cf6", // purple
  "#3b82f6", // blue
  "#06b6d4", // cyan
  "#10b981", // emerald
  "#ec4899", // pink
  "#6366f1", // indigo
  "#9ca3af", // gray (for "other")
];

/** Compute first and last timestamps for "X days" stat */
function getDaySpan(runs: FilteredRun[]): number {
  if (runs.length < 2) return 0;
  const first = new Date(runs[0].run.timestamp).getTime();
  const last = new Date(runs[runs.length - 1].run.timestamp).getTime();
  return Math.ceil((last - first) / (1000 * 60 * 60 * 24));
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export function EvalShowcaseView() {
  const [data, setData] = useState<EvalShowcaseData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getEvalShowcaseData()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-24 text-muted-foreground">
        <AlertCircle className="h-8 w-8" />
        <p>{error || "No data available"}</p>
      </div>
    );
  }

  const runs = filterRuns(data);
  if (runs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-24 text-muted-foreground">
        <AlertCircle className="h-8 w-8" />
        <p>No valid eval runs found (need at least 10 claims processed per run)</p>
      </div>
    );
  }

  const latest = runs[runs.length - 1];
  const first = runs[0];

  return (
    <div className="pb-16 -mx-6 -mt-6">
      {/* 1. Hero Banner */}
      <HeroBanner runs={runs} latest={latest} first={first} totalClaims={data.ground_truth_claims} />

      <div className="mx-auto max-w-7xl space-y-8 px-6 mt-8">
        {/* 2. Radial Gauge Trio */}
        <GaugeSection latest={latest} first={first} />

        {/* 3. Accuracy Journey */}
        <AccuracyJourney runs={runs} />

        {/* 4. Error Stream */}
        <ErrorStream runs={runs} />

        <div className="grid gap-8 lg:grid-cols-2">
          {/* 5. Confusion Matrix */}
          <GlassCard>
            <h3 className="text-lg font-semibold text-foreground mb-4">
              Confusion Matrix (Latest Run)
            </h3>
            <ConfusionHeatmap run={latest.run} />
          </GlassCard>

          {/* 6. Milestone Timeline */}
          <GlassCard>
            <h3 className="text-lg font-semibold text-foreground mb-4">
              Accuracy Milestones
            </h3>
            <MilestoneTimeline runs={runs} />
          </GlassCard>
        </div>

        {/* 7. Stats Ribbon */}
        <StatsRibbon runs={runs} totalClaims={data.ground_truth_claims} />
      </div>
    </div>
  );
}

// =============================================================================
// SECTION: Hero Banner
// =============================================================================

function HeroBanner({
  runs,
  latest,
  first,
  totalClaims,
}: {
  runs: FilteredRun[];
  latest: FilteredRun;
  first: FilteredRun;
  totalClaims: number;
}) {
  const daySpan = getDaySpan(runs);

  return (
    <section className="hero-gradient-bg py-16 px-6">
      <div className="mx-auto max-w-7xl text-center">
        {/* Giant accuracy number */}
        <div className="mb-2">
          <span className="hero-number text-8xl font-black tracking-tight text-foreground md:text-9xl">
            <AnimatedCounter target={latest.accuracy} decimals={0} suffix="%" duration={2500} />
          </span>
        </div>
        <p className="text-lg text-muted-foreground mb-8">
          Decision Accuracy — up from {Math.round(first.accuracy)}%
        </p>

        {/* Stat counters row */}
        <div className="stagger-children mx-auto flex max-w-2xl flex-wrap items-center justify-center gap-8">
          <StatCounter value={runs.length} label="Eval Runs" />
          <StatCounter value={totalClaims} label="Claims Tested" />
          <StatCounter value={daySpan} label="Days" />
          <StatCounter
            value={latest.run.metrics.decision_wrong}
            label="Errors (Latest)"
          />
        </div>
      </div>
    </section>
  );
}

function StatCounter({ value, label }: { value: number; label: string }) {
  return (
    <div className="text-center">
      <div className="text-3xl font-bold text-foreground">
        <AnimatedCounter target={value} duration={1800} />
      </div>
      <div className="text-xs text-muted-foreground uppercase tracking-wider mt-1">
        {label}
      </div>
    </div>
  );
}

// =============================================================================
// SECTION: Radial Gauge Trio
// =============================================================================

function GaugeSection({
  latest,
  first,
}: {
  latest: FilteredRun;
  first: FilteredRun;
}) {
  const gauges = [
    {
      label: "Accuracy",
      value: latest.accuracy,
      delta: latest.accuracy - first.accuracy,
      startLabel: `was ${Math.round(first.accuracy)}%`,
    },
    {
      label: "FRR",
      value: 100 - latest.frr, // Invert: 0% FRR = 100% gauge
      delta: first.frr - latest.frr, // Positive delta means improvement
      startLabel: `was ${Math.round(first.frr)}%`,
      displayValue: `${latest.frr.toFixed(1)}%`,
    },
    {
      label: "FAR",
      value: 100 - latest.far, // Invert: 0% FAR = 100% gauge
      delta: first.far - latest.far,
      startLabel: `was ${Math.round(first.far)}%`,
      displayValue: `${latest.far.toFixed(1)}%`,
    },
  ];

  return (
    <div className="stagger-children grid gap-6 md:grid-cols-3">
      {gauges.map((g) => (
        <GlassCard key={g.label} glow className="flex flex-col items-center">
          <div className="h-[160px] w-full">
            <RadialGauge value={g.value} label={g.label} size="lg" />
          </div>
          {g.displayValue !== undefined ? (
            <p className="text-2xl font-bold text-foreground -mt-2">
              {g.displayValue}
            </p>
          ) : null}
          <p className="text-xs text-muted-foreground mt-1">
            {g.startLabel}{" "}
            <span
              className={
                g.delta >= 0 ? "text-green-500" : "text-red-500"
              }
            >
              ({g.delta >= 0 ? "+" : ""}
              {Math.round(g.delta)}pp)
            </span>
          </p>
        </GlassCard>
      ))}
    </div>
  );
}

// =============================================================================
// SECTION: Accuracy Journey Chart
// =============================================================================

const ACCURACY_MILESTONES = [50, 80, 90, 95, 100];

function AccuracyJourney({ runs }: { runs: FilteredRun[] }) {
  const chartData = runs.map((r) => ({
    label: `#${r.index + 1}`,
    accuracy: r.accuracy,
    timestamp: new Date(r.run.timestamp).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }),
  }));

  // Find which runs first hit milestones
  const milestonePoints = useCallback(() => {
    const reached = new Set<number>();
    const points: Array<{ index: number; threshold: number }> = [];
    for (const r of runs) {
      for (const t of ACCURACY_MILESTONES) {
        if (!reached.has(t) && r.accuracy >= t) {
          reached.add(t);
          points.push({ index: r.index, threshold: t });
        }
      }
    }
    return points;
  }, [runs])();

  return (
    <ChartCard title="Accuracy Journey" height="h-[350px]">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="accuracyGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#22c55e" stopOpacity={0.3} />
              <stop offset="50%" stopColor="#22c55e" stopOpacity={0.1} />
              <stop offset="100%" stopColor="#22c55e" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
          />
          <YAxis
            domain={[0, 105]}
            tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
            tickFormatter={(v: number) => `${v}%`}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: "8px",
              fontSize: "12px",
            }}
            formatter={(value: number) => [`${value.toFixed(1)}%`, "Accuracy"]}
            labelFormatter={(_label: string, payload: Array<{ payload?: { timestamp?: string } }>) => {
              const ts = payload?.[0]?.payload?.timestamp;
              return ts || _label;
            }}
          />
          <ReferenceLine
            y={80}
            stroke="#3b82f6"
            strokeDasharray="4 4"
            strokeOpacity={0.5}
            label={{ value: "80%", position: "right", fontSize: 10, fill: "#3b82f6" }}
          />
          <ReferenceLine
            y={95}
            stroke="#14b8a6"
            strokeDasharray="4 4"
            strokeOpacity={0.5}
            label={{ value: "95%", position: "right", fontSize: 10, fill: "#14b8a6" }}
          />
          <Area
            type="monotone"
            dataKey="accuracy"
            stroke="#22c55e"
            strokeWidth={2.5}
            fill="url(#accuracyGrad)"
            dot={(props: { cx: number; cy: number; index: number }) => {
              const isMilestone = milestonePoints.some(
                (m) => m.index === props.index
              );
              if (!isMilestone) return <circle key={props.index} cx={0} cy={0} r={0} />;
              return (
                <circle
                  key={props.index}
                  cx={props.cx}
                  cy={props.cy}
                  r={5}
                  fill="#22c55e"
                  stroke="#fff"
                  strokeWidth={2}
                />
              );
            }}
            activeDot={{ r: 6, fill: "#22c55e", stroke: "#fff", strokeWidth: 2 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

// =============================================================================
// SECTION: Error Stream (Stacked Area)
// =============================================================================

function ErrorStream({ runs }: { runs: FilteredRun[] }) {
  const streamData = getErrorStreamData(runs);

  // Collect all category keys (excluding "label")
  const allKeys = new Set<string>();
  for (const d of streamData) {
    for (const k of Object.keys(d)) {
      if (k !== "label") allKeys.add(k);
    }
  }
  const categories = Array.from(allKeys);

  // Sort so "other" is last
  categories.sort((a, b) => {
    if (a === "other") return 1;
    if (b === "other") return -1;
    return a.localeCompare(b);
  });

  return (
    <ChartCard title="Error Categories Over Time" height="h-[300px]">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={streamData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
          />
          <YAxis
            tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: "8px",
              fontSize: "12px",
            }}
            formatter={(value: number, name: string) => [
              value,
              formatCategory(name),
            ]}
          />
          {categories.map((cat, i) => (
            <Area
              key={cat}
              type="monotone"
              dataKey={cat}
              stackId="errors"
              stroke={ERROR_COLORS[i % ERROR_COLORS.length]}
              fill={ERROR_COLORS[i % ERROR_COLORS.length]}
              fillOpacity={0.6}
              name={cat}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

// =============================================================================
// SECTION: Stats Ribbon
// =============================================================================

function StatsRibbon({
  runs,
  totalClaims,
}: {
  runs: FilteredRun[];
  totalClaims: number;
}) {
  const latest = runs[runs.length - 1];
  const accuracyValues = runs.map((r) => r.accuracy);
  const frrValues = runs.map((r) => r.frr);
  const farValues = runs.map((r) => r.far);
  const correctValues = runs.map((r) => r.run.metrics.decision_correct);
  const wrongValues = runs.map((r) => r.run.metrics.decision_wrong);
  const approvedValues = runs.map((r) => r.run.metrics.approved_correct);

  const stats = [
    {
      label: "Decision Accuracy",
      value: `${latest.accuracy.toFixed(1)}%`,
      sparkData: accuracyValues,
      color: "#22c55e",
    },
    {
      label: "False Reject Rate",
      value: `${latest.frr.toFixed(1)}%`,
      sparkData: frrValues,
      color: "#ef4444",
    },
    {
      label: "False Approve Rate",
      value: `${latest.far.toFixed(1)}%`,
      sparkData: farValues,
      color: "#f59e0b",
    },
    {
      label: "Correct Decisions",
      value: `${latest.run.metrics.decision_correct}/${totalClaims}`,
      sparkData: correctValues,
      color: "#14b8a6",
    },
    {
      label: "Wrong Decisions",
      value: String(latest.run.metrics.decision_wrong),
      sparkData: wrongValues,
      color: "#8b5cf6",
    },
    {
      label: "Approved Correct",
      value: `${latest.run.metrics.approved_correct}/${latest.run.metrics.approved_total}`,
      sparkData: approvedValues,
      color: "#3b82f6",
    },
  ];

  return (
    <div className="stagger-children grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
      {stats.map((s) => (
        <GlassCard key={s.label} className="!p-4">
          <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">
            {s.label}
          </div>
          <div className="text-xl font-bold text-foreground mb-2">
            {s.value}
          </div>
          <Sparkline data={s.sparkData} color={s.color} height={32} />
        </GlassCard>
      ))}
    </div>
  );
}
