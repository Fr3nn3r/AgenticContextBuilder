import { cn } from "../../lib/utils";
import type { ConfidenceBand } from "../../types";

const BAND_STYLES: Record<ConfidenceBand, string> = {
  high: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300",
  moderate: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
  low: "bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300",
};

const SCORE_COLORS = {
  high: "text-foreground",
  moderate: "text-amber-600 dark:text-amber-400",
  low: "text-rose-600 dark:text-rose-400",
};

function bandFromScore(score: number): ConfidenceBand {
  if (score >= 0.80) return "high";
  if (score >= 0.65) return "moderate";
  return "low";
}

export function ConfidenceBadge({
  score,
  band,
}: {
  score: number | null;
  band?: ConfidenceBand | null;
}) {
  if (score == null) return null;

  const effectiveBand = band ?? bandFromScore(score);
  const display = score <= 1 ? Math.round(score * 100) : Math.round(score);

  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={cn("text-lg font-bold tabular-nums", SCORE_COLORS[effectiveBand])}>
        {display}%
      </span>
      <span
        className={cn(
          "text-[10px] px-1.5 py-0.5 rounded-full font-semibold uppercase tracking-wide",
          BAND_STYLES[effectiveBand]
        )}
      >
        {effectiveBand}
      </span>
    </span>
  );
}
