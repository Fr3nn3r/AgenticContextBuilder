import {
  Loader2,
  AlertTriangle,
  AlertOctagon,
  Info,
  CheckCircle2,
  HelpCircle,
  ChevronRight,
  Lightbulb,
} from "lucide-react";
import { cn } from "../../lib/utils";
import type { AssessmentAssumption, AssessmentCheck, AssumptionImpact } from "../../types";

interface ClaimAssumptionsTabProps {
  assumptions: AssessmentAssumption[];
  checks?: AssessmentCheck[];
  loading: boolean;
  error: string | null;
}

/** Format field name from snake_case to Title Case */
function formatFieldName(name: string): string {
  return name
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

const IMPACT_CONFIG: Record<
  AssumptionImpact,
  {
    icon: typeof AlertTriangle;
    label: string;
    bgColor: string;
    borderColor: string;
    textColor: string;
    badgeColor: string;
    description: string;
  }
> = {
  high: {
    icon: AlertOctagon,
    label: "High Impact",
    bgColor: "bg-red-50 dark:bg-red-900/20",
    borderColor: "border-red-200 dark:border-red-800",
    textColor: "text-red-700 dark:text-red-300",
    badgeColor: "bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300",
    description: "This assumption significantly affects the claim decision. Manual verification required.",
  },
  medium: {
    icon: AlertTriangle,
    label: "Medium Impact",
    bgColor: "bg-amber-50 dark:bg-amber-900/20",
    borderColor: "border-amber-200 dark:border-amber-800",
    textColor: "text-amber-700 dark:text-amber-300",
    badgeColor: "bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300",
    description: "This assumption may affect the claim outcome. Review if possible.",
  },
  low: {
    icon: Info,
    label: "Low Impact",
    bgColor: "bg-slate-50 dark:bg-slate-800/50",
    borderColor: "border-slate-200 dark:border-slate-700",
    textColor: "text-slate-600 dark:text-slate-400",
    badgeColor: "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400",
    description: "This assumption has minimal impact on the decision.",
  },
};

interface AssumptionCardProps {
  assumption: AssessmentAssumption;
  checks?: AssessmentCheck[];
  index: number;
}

/** Get display title for an assumption, using check name as fallback */
function getAssumptionTitle(assumption: AssessmentAssumption, checks?: AssessmentCheck[]): string {
  // If field is provided, use it
  if (assumption.field && assumption.field.trim()) {
    return formatFieldName(assumption.field);
  }

  // Try to find the check by check_number
  if (checks) {
    const check = checks.find((c) => c.check_number === assumption.check_number);
    if (check) {
      return formatFieldName(check.check_name);
    }
  }

  // Fallback based on assumed value
  if (assumption.assumed_value === "compliant") {
    return "Service Compliance";
  }

  return `Assumption #${assumption.check_number}`;
}

/** Get display reason, with fallback explanations */
function getAssumptionReason(assumption: AssessmentAssumption, checks?: AssessmentCheck[]): string {
  // If reason is provided, use it
  if (assumption.reason && assumption.reason.trim()) {
    return assumption.reason;
  }

  // Generate explanation based on context
  const check = checks?.find((c) => c.check_number === assumption.check_number);

  if (assumption.assumed_value === "compliant") {
    if (check?.check_name === "service_compliance") {
      return "The repair shop compliance could not be verified from documents. Assumed compliant based on context.";
    }
    return "Compliance status could not be extracted from documents. Assumed compliant based on available evidence.";
  }

  if (check) {
    return `Value for "${formatFieldName(check.check_name)}" was not found in documents. System made a reasonable assumption.`;
  }

  return "This value was not found in the submitted documents. The system made a reasonable assumption based on available context.";
}

function AssumptionCard({ assumption, checks, index }: AssumptionCardProps) {
  const config = IMPACT_CONFIG[assumption.impact];
  const Icon = config.icon;

  const title = getAssumptionTitle(assumption, checks);
  const reason = getAssumptionReason(assumption, checks);

  return (
    <div
      className={cn(
        "rounded-lg border p-4 transition-all",
        config.bgColor,
        config.borderColor
      )}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-3">
          <div
            className={cn(
              "w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0",
              config.badgeColor
            )}
          >
            <Icon className="h-4 w-4" />
          </div>
          <div>
            <h4 className={cn("font-semibold", config.textColor)}>
              {title}
            </h4>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Assumed "{assumption.assumed_value || "unknown"}"
            </p>
          </div>
        </div>
        <span
          className={cn(
            "px-2 py-1 rounded-full text-xs font-medium flex-shrink-0",
            config.badgeColor
          )}
        >
          {config.label}
        </span>
      </div>

      {/* Reason / Explanation */}
      <div className="bg-white dark:bg-slate-900/50 rounded-lg p-3 mb-3 border border-slate-200 dark:border-slate-700">
        <div className="flex items-center gap-2 mb-1">
          <HelpCircle className="h-3.5 w-3.5 text-slate-400" />
          <span className="text-xs text-slate-500 dark:text-slate-400 uppercase tracking-wider">
            Why was this assumed?
          </span>
        </div>
        <p className="text-sm text-slate-600 dark:text-slate-300">
          {reason}
        </p>
      </div>

      {/* Business Impact */}
      <div className={cn("p-2 rounded-md text-xs", config.badgeColor)}>
        <strong>Business Impact:</strong> {config.description}
      </div>
    </div>
  );
}

/**
 * Assumptions tab showing all assumptions made during claim assessment.
 * Business-friendly layout with clear impact indicators.
 */
export function ClaimAssumptionsTab({
  assumptions,
  checks,
  loading,
  error,
}: ClaimAssumptionsTabProps) {
  // Sort assumptions by impact (high first)
  const sortedAssumptions = [...assumptions].sort((a, b) => {
    const order: Record<AssumptionImpact, number> = { high: 0, medium: 1, low: 2 };
    return order[a.impact] - order[b.impact];
  });

  // Count by impact
  const counts = {
    high: assumptions.filter((a) => a.impact === "high").length,
    medium: assumptions.filter((a) => a.impact === "medium").length,
    low: assumptions.filter((a) => a.impact === "low").length,
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
          <p className="text-sm text-slate-500">Loading assumptions...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4">
        <div className="bg-white dark:bg-slate-900 rounded-lg border border-red-200 dark:border-red-900 p-6 text-center">
          <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
        </div>
      </div>
    );
  }

  if (assumptions.length === 0) {
    return (
      <div className="p-4">
        <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700 p-8 text-center">
          <div className="w-16 h-16 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center mx-auto mb-4">
            <CheckCircle2 className="h-8 w-8 text-green-500" />
          </div>
          <h3 className="text-lg font-semibold text-slate-700 dark:text-slate-200 mb-2">
            No Assumptions Made
          </h3>
          <p className="text-sm text-slate-500 dark:text-slate-400 max-w-md mx-auto">
            All required data was extracted from the documents.
            No values needed to be assumed during the assessment.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 space-y-4">
      {/* Summary Banner */}
      <div
        className={cn(
          "rounded-lg border p-4",
          counts.high > 0
            ? "bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800"
            : counts.medium > 0
            ? "bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800"
            : "bg-slate-50 dark:bg-slate-800/50 border-slate-200 dark:border-slate-700"
        )}
      >
        <div className="flex items-start gap-4">
          <div
            className={cn(
              "w-12 h-12 rounded-full flex items-center justify-center flex-shrink-0",
              counts.high > 0
                ? "bg-red-100 dark:bg-red-900/40"
                : counts.medium > 0
                ? "bg-amber-100 dark:bg-amber-900/40"
                : "bg-slate-100 dark:bg-slate-800"
            )}
          >
            <AlertTriangle
              className={cn(
                "h-6 w-6",
                counts.high > 0
                  ? "text-red-500"
                  : counts.medium > 0
                  ? "text-amber-500"
                  : "text-slate-400"
              )}
            />
          </div>
          <div className="flex-1">
            <h3 className="text-lg font-semibold text-slate-700 dark:text-slate-200 mb-1">
              {assumptions.length} Assumption{assumptions.length > 1 ? "s" : ""} Made
            </h3>
            <p className="text-sm text-slate-600 dark:text-slate-400 mb-3">
              {counts.high > 0 ? (
                <>
                  <strong className="text-red-600 dark:text-red-400">
                    {counts.high} high-impact
                  </strong>{" "}
                  assumption{counts.high > 1 ? "s" : ""} require manual verification
                  before this claim can be auto-approved.
                </>
              ) : counts.medium > 0 ? (
                <>
                  Some assumptions were made during assessment. Review recommended
                  before finalizing the decision.
                </>
              ) : (
                <>
                  Minor assumptions were made. These have minimal impact on the
                  claim decision.
                </>
              )}
            </p>

            {/* Impact counts */}
            <div className="flex items-center gap-4">
              {counts.high > 0 && (
                <div className="flex items-center gap-1.5">
                  <AlertOctagon className="h-4 w-4 text-red-500" />
                  <span className="text-sm font-medium text-red-600 dark:text-red-400">
                    {counts.high} High
                  </span>
                </div>
              )}
              {counts.medium > 0 && (
                <div className="flex items-center gap-1.5">
                  <AlertTriangle className="h-4 w-4 text-amber-500" />
                  <span className="text-sm font-medium text-amber-600 dark:text-amber-400">
                    {counts.medium} Medium
                  </span>
                </div>
              )}
              {counts.low > 0 && (
                <div className="flex items-center gap-1.5">
                  <Info className="h-4 w-4 text-slate-400" />
                  <span className="text-sm font-medium text-slate-600 dark:text-slate-400">
                    {counts.low} Low
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* What are assumptions? */}
      <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800 p-4">
        <div className="flex items-start gap-3">
          <Info className="h-5 w-5 text-blue-500 flex-shrink-0 mt-0.5" />
          <div>
            <h4 className="font-medium text-blue-700 dark:text-blue-300 mb-1">
              What are assumptions?
            </h4>
            <p className="text-sm text-blue-600 dark:text-blue-400">
              When critical data is missing from documents, the system makes reasonable
              assumptions based on available context. High-impact assumptions prevent
              auto-approval and require human review. You can verify or override these
              values by providing additional documentation.
            </p>
          </div>
        </div>
      </div>

      {/* Assumptions List */}
      <div className="space-y-3">
        {sortedAssumptions.map((assumption, idx) => (
          <AssumptionCard
            key={`${assumption.check_number}-${assumption.field}-${idx}`}
            assumption={assumption}
            checks={checks}
            index={idx}
          />
        ))}
      </div>

      {/* Next Steps */}
      {counts.high > 0 && (
        <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700 p-4">
          <h4 className="font-semibold text-slate-700 dark:text-slate-200 mb-3 flex items-center gap-2">
            <ChevronRight className="h-4 w-4" />
            Recommended Next Steps
          </h4>
          <ul className="space-y-2 text-sm text-slate-600 dark:text-slate-400">
            <li className="flex items-start gap-2">
              <span className="w-5 h-5 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center flex-shrink-0 text-xs font-medium">
                1
              </span>
              <span>
                Request missing documentation from the claimant to verify assumed values
              </span>
            </li>
            <li className="flex items-start gap-2">
              <span className="w-5 h-5 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center flex-shrink-0 text-xs font-medium">
                2
              </span>
              <span>
                Check if alternative data sources can provide the missing information
              </span>
            </li>
            <li className="flex items-start gap-2">
              <span className="w-5 h-5 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center flex-shrink-0 text-xs font-medium">
                3
              </span>
              <span>
                If verified manually, document the verification and refer to human reviewer
              </span>
            </li>
          </ul>
        </div>
      )}
    </div>
  );
}
