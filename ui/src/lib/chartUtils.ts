import type { InsightsOverview, DocTypeMetrics } from "../api/client";

export interface ChartDataPoint {
  name: string;
  value: number;
  fill?: string;
}

export interface BarChartDataPoint {
  name: string;
  accuracy: number;
  presence: number;
  evidence: number;
}

// Chart color palette - direct colors that work with recharts
// These are theme-aware colors that match the Northern Lights theme
export const CHART_COLORS = {
  success: "#22c55e",      // Green for correct/success
  error: "#ef4444",        // Red for errors/incorrect
  warning: "#f59e0b",      // Amber for warnings/missing
  info: "#3b82f6",         // Blue for info
  muted: "#9ca3af",        // Gray for muted
  chart1: "#14b8a6",       // Teal (primary - accuracy)
  chart2: "#8b5cf6",       // Purple (secondary - presence)
  chart3: "#06b6d4",       // Cyan (accent - evidence)
  chart4: "#6366f1",       // Indigo
  chart5: "#10b981",       // Emerald
};

/**
 * Transform overview data for outcome pie chart
 */
export function transformOutcomeData(overview: InsightsOverview | null): ChartDataPoint[] {
  if (!overview) return [];

  const correct = overview.correct_count || overview.match_count || 0;
  const incorrect = overview.incorrect_count || overview.mismatch_count || 0;
  const missing = overview.missing_count || overview.miss_count || 0;

  return [
    { name: "Correct", value: correct, fill: CHART_COLORS.success },
    { name: "Incorrect", value: incorrect, fill: CHART_COLORS.error },
    { name: "Missing", value: missing, fill: CHART_COLORS.warning },
  ].filter(d => d.value > 0);
}

/**
 * Transform doc type metrics for bar chart
 */
export function transformDocTypeData(docTypes: DocTypeMetrics[]): BarChartDataPoint[] {
  return docTypes.map(dt => ({
    name: formatDocTypeShort(dt.doc_type),
    accuracy: dt.required_field_accuracy_pct || 0,
    presence: dt.required_field_presence_pct || 0,
    evidence: dt.evidence_rate_pct || 0,
  }));
}

/**
 * Get gauge color based on value
 */
export function getGaugeColor(value: number): string {
  if (value >= 80) return CHART_COLORS.chart1;  // Teal for good scores
  if (value >= 60) return CHART_COLORS.warning; // Amber for medium
  if (value > 0) return CHART_COLORS.error;     // Red for poor
  return CHART_COLORS.muted;                    // Gray for zero
}

/**
 * Format doc type name for chart labels (shorter)
 */
function formatDocTypeShort(docType: string): string {
  return docType
    .replace(/_/g, " ")
    .replace(/\b\w/g, l => l.toUpperCase())
    .replace(/Form$/, "")
    .replace(/Document$/, "Doc")
    .replace(/Report$/, "Rpt")
    .trim();
}
