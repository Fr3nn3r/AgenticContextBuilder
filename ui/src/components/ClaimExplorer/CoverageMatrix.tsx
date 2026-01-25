import { Check, X, Minus, AlertCircle } from "lucide-react";
import type { AggregatedFact } from "../../types";
import { cn } from "../../lib/utils";

interface CoverageMatrixProps {
  facts: AggregatedFact[];
  onViewSource?: (
    docId: string,
    page: number | null,
    charStart: number | null,
    charEnd: number | null
  ) => void;
}

// Coverage categories for the 2x2 grid
const COVERAGE_CATEGORIES: Record<string, { label: string; fields: string[] }> = {
  mechanical: {
    label: "Mechanical",
    fields: [
      "engine_covered", "turbo_covered", "transmission_covered",
      "drivetrain_covered", "4wd_covered", "suspension_covered",
      "steering_covered", "brakes_covered"
    ]
  },
  electrical: {
    label: "Electrical",
    fields: [
      "electrical_covered", "electronics_covered", "battery_covered",
      "starter_covered", "alternator_covered", "ac_covered",
      "heating_covered", "infotainment_covered"
    ]
  },
  limits: {
    label: "Coverage Limits",
    fields: [
      "max_coverage", "deductible", "labor_rate_limit",
      "max_repair_value", "coverage_percentage"
    ]
  },
  status: {
    label: "Policy Status",
    fields: [
      "warranty_valid", "warranty_active", "policy_active",
      "coverage_expired", "premium_paid", "claim_eligible"
    ]
  }
};

// Field display name mapping
const FIELD_LABELS: Record<string, string> = {
  engine_covered: "Engine",
  turbo_covered: "Turbo",
  transmission_covered: "Trans",
  drivetrain_covered: "Drive",
  "4wd_covered": "4WD",
  suspension_covered: "Susp",
  steering_covered: "Steer",
  brakes_covered: "Brakes",
  electrical_covered: "Elec",
  electronics_covered: "ECU",
  battery_covered: "Battery",
  starter_covered: "Starter",
  alternator_covered: "Alt",
  ac_covered: "A/C",
  heating_covered: "Heat",
  infotainment_covered: "Media",
  max_coverage: "Max",
  deductible: "Deduct",
  labor_rate_limit: "Labor",
  max_repair_value: "Repair",
  coverage_percentage: "Cover %",
  warranty_valid: "Valid",
  warranty_active: "Active",
  policy_active: "Policy",
  coverage_expired: "Expired",
  premium_paid: "Paid",
  claim_eligible: "Eligible"
};

function getBooleanValue(value: string | string[] | null): boolean | null {
  if (value === null || value === undefined) return null;
  const strValue = Array.isArray(value) ? value[0] : value;
  const lower = strValue.toLowerCase().trim();
  if (["true", "yes", "1", "ja", "oui", "covered", "active", "valid"].includes(lower)) return true;
  if (["false", "no", "0", "nein", "non", "not covered", "inactive", "invalid", "expired"].includes(lower)) return false;
  return null;
}

function formatValue(value: string | string[] | null): string {
  if (value === null || value === undefined) return "—";
  if (Array.isArray(value)) return value.join(", ");
  return value;
}

// Traffic light badge for boolean coverage
function CoverageBadge({
  name,
  value,
  onClick
}: {
  name: string;
  value: boolean | null;
  onClick?: () => void;
}) {
  const label = FIELD_LABELS[name] || name.replace(/_/g, " ").replace(/covered/gi, "").trim();

  return (
    <button
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium transition-all",
        "border hover:scale-105 active:scale-100",
        onClick && "cursor-pointer",
        !onClick && "cursor-default",
        value === true && "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/30",
        value === false && "bg-red-500/10 text-red-700 dark:text-red-400 border-red-500/30",
        value === null && "bg-slate-100 dark:bg-slate-800 text-slate-500 border-slate-200 dark:border-slate-700"
      )}
      title={`${label}: ${value === true ? "Covered" : value === false ? "Not Covered" : "N/A"}`}
    >
      {value === true && <Check className="h-3 w-3" />}
      {value === false && <X className="h-3 w-3" />}
      {value === null && <Minus className="h-3 w-3" />}
      <span className="uppercase tracking-wide">{label}</span>
    </button>
  );
}

// Value display for non-boolean fields
function ValueBadge({
  name,
  value,
  onClick
}: {
  name: string;
  value: string;
  onClick?: () => void;
}) {
  const label = FIELD_LABELS[name] || name.replace(/_/g, " ");

  return (
    <button
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-xs transition-all",
        "border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800",
        "hover:bg-slate-100 dark:hover:bg-slate-700",
        onClick && "cursor-pointer",
        !onClick && "cursor-default"
      )}
      title={`${label}: ${value}`}
    >
      <span className="text-slate-500 dark:text-slate-400 uppercase tracking-wide">{label}</span>
      <span className="font-mono font-semibold text-slate-700 dark:text-slate-200 tabular-nums">
        {value}
      </span>
    </button>
  );
}

function CategoryCard({
  category,
  label,
  facts,
  onViewSource
}: {
  category: string;
  label: string;
  facts: AggregatedFact[];
  onViewSource?: CoverageMatrixProps["onViewSource"];
}) {
  const categoryConfig = COVERAGE_CATEGORIES[category];
  if (!categoryConfig) return null;

  // Get facts that match this category
  const categoryFacts = facts.filter(f =>
    categoryConfig.fields.some(field =>
      f.name.toLowerCase().includes(field.replace(/_covered$/, "")) ||
      f.name.toLowerCase() === field
    )
  );

  if (categoryFacts.length === 0) return null;

  // Check for any exclusions (red flags)
  const hasExclusions = categoryFacts.some(f => {
    const boolVal = getBooleanValue(f.value);
    return boolVal === false;
  });

  const handleFactClick = (fact: AggregatedFact) => {
    if (onViewSource && fact.selected_from) {
      onViewSource(
        fact.selected_from.doc_id,
        fact.selected_from.page,
        fact.selected_from.char_start,
        fact.selected_from.char_end
      );
    }
  };

  return (
    <div className={cn(
      "rounded-lg border p-3 transition-all",
      "bg-white dark:bg-slate-900",
      hasExclusions
        ? "border-red-200 dark:border-red-900 ring-1 ring-red-100 dark:ring-red-900/50"
        : "border-slate-200 dark:border-slate-700"
    )}>
      {/* Category header */}
      <div className="flex items-center gap-2 mb-2">
        {hasExclusions && (
          <AlertCircle className="h-3.5 w-3.5 text-red-500" />
        )}
        <h4 className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
          {label}
        </h4>
      </div>

      {/* Badges grid */}
      <div className="flex flex-wrap gap-1.5">
        {categoryFacts.map((fact) => {
          const boolValue = getBooleanValue(fact.value);
          const isBooleanField = fact.name.includes("covered") ||
            fact.name.includes("valid") ||
            fact.name.includes("active") ||
            fact.name.includes("expired") ||
            fact.name.includes("eligible") ||
            fact.name.includes("paid");

          if (isBooleanField || boolValue !== null) {
            return (
              <CoverageBadge
                key={fact.name}
                name={fact.name}
                value={boolValue}
                onClick={onViewSource ? () => handleFactClick(fact) : undefined}
              />
            );
          }

          return (
            <ValueBadge
              key={fact.name}
              name={fact.name}
              value={formatValue(fact.value)}
              onClick={onViewSource ? () => handleFactClick(fact) : undefined}
            />
          );
        })}
      </div>
    </div>
  );
}

export function CoverageMatrix({ facts, onViewSource }: CoverageMatrixProps) {
  // Filter to warranty/coverage related facts
  const coverageFacts = facts.filter(f =>
    f.name.includes("covered") ||
    f.name.includes("warranty") ||
    f.name.includes("coverage") ||
    f.name.includes("deductible") ||
    f.name.includes("limit") ||
    f.name.includes("valid") ||
    f.name.includes("active") ||
    f.name.includes("eligible") ||
    f.name.includes("expired") ||
    f.name.includes("policy") ||
    f.name.includes("max_")
  );

  // Count exclusions for summary
  const exclusionCount = coverageFacts.filter(f => getBooleanValue(f.value) === false).length;
  const coveredCount = coverageFacts.filter(f => getBooleanValue(f.value) === true).length;

  if (coverageFacts.length === 0) {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700 p-4">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-2">
          Warranty & Coverage
        </h3>
        <p className="text-sm text-slate-500">No coverage data available</p>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
      {/* Header with summary */}
      <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
          Warranty & Coverage
        </h3>
        <div className="flex items-center gap-3">
          {coveredCount > 0 && (
            <div className="flex items-center gap-1 text-xs">
              <Check className="h-3 w-3 text-emerald-500" />
              <span className="font-medium text-emerald-600 dark:text-emerald-400">
                {coveredCount}
              </span>
            </div>
          )}
          {exclusionCount > 0 && (
            <div className="flex items-center gap-1 text-xs">
              <X className="h-3 w-3 text-red-500" />
              <span className="font-medium text-red-600 dark:text-red-400">
                {exclusionCount}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* 2x2 Grid */}
      <div className="p-3 grid grid-cols-1 sm:grid-cols-2 gap-3">
        {Object.entries(COVERAGE_CATEGORIES).map(([key, config]) => (
          <CategoryCard
            key={key}
            category={key}
            label={config.label}
            facts={coverageFacts}
            onViewSource={onViewSource}
          />
        ))}
      </div>
    </div>
  );
}
