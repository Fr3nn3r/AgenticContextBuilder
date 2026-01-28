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
    bgColor: "bg-destructive/10",
    borderColor: "border-destructive/30",
    textColor: "text-destructive",
    badgeColor: "bg-destructive/10 text-destructive",
    description: "This assumption significantly affects the claim decision. Manual verification required.",
  },
  medium: {
    icon: AlertTriangle,
    label: "Medium Impact",
    bgColor: "bg-warning/10",
    borderColor: "border-warning/30",
    textColor: "text-warning",
    badgeColor: "bg-warning/10 text-warning",
    description: "This assumption may affect the claim outcome. Review if possible.",
  },
  low: {
    icon: Info,
    label: "Low Impact",
    bgColor: "bg-muted/50",
    borderColor: "border-border",
    textColor: "text-muted-foreground",
    badgeColor: "bg-muted text-muted-foreground",
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
            <p className="text-xs text-muted-foreground">
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
      <div className="bg-card rounded-lg p-3 mb-3 border border-border">
        <div className="flex items-center gap-2 mb-1">
          <HelpCircle className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="text-xs text-muted-foreground uppercase tracking-wider">
            Why was this assumed?
          </span>
        </div>
        <p className="text-sm text-foreground">
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
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          <p className="text-sm text-muted-foreground">Loading assumptions...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4">
        <div className="bg-card rounded-lg border border-destructive/30 p-6 text-center">
          <p className="text-sm text-destructive">{error}</p>
        </div>
      </div>
    );
  }

  if (assumptions.length === 0) {
    return (
      <div className="p-4">
        <div className="bg-card rounded-lg border border-border p-8 text-center">
          <div className="w-16 h-16 rounded-full bg-success/10 flex items-center justify-center mx-auto mb-4">
            <CheckCircle2 className="h-8 w-8 text-success" />
          </div>
          <h3 className="text-lg font-semibold text-foreground mb-2">
            No Assumptions Made
          </h3>
          <p className="text-sm text-muted-foreground max-w-md mx-auto">
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
            ? "bg-destructive/10 border-destructive/30"
            : counts.medium > 0
            ? "bg-warning/10 border-warning/30"
            : "bg-muted/50 border-border"
        )}
      >
        <div className="flex items-start gap-4">
          <div
            className={cn(
              "w-12 h-12 rounded-full flex items-center justify-center flex-shrink-0",
              counts.high > 0
                ? "bg-destructive/20"
                : counts.medium > 0
                ? "bg-warning/20"
                : "bg-muted"
            )}
          >
            <AlertTriangle
              className={cn(
                "h-6 w-6",
                counts.high > 0
                  ? "text-destructive"
                  : counts.medium > 0
                  ? "text-warning"
                  : "text-muted-foreground"
              )}
            />
          </div>
          <div className="flex-1">
            <h3 className="text-lg font-semibold text-foreground mb-1">
              {assumptions.length} Assumption{assumptions.length > 1 ? "s" : ""} Made
            </h3>
            <p className="text-sm text-muted-foreground mb-3">
              {counts.high > 0 ? (
                <>
                  <strong className="text-destructive">
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
                  <AlertOctagon className="h-4 w-4 text-destructive" />
                  <span className="text-sm font-medium text-destructive">
                    {counts.high} High
                  </span>
                </div>
              )}
              {counts.medium > 0 && (
                <div className="flex items-center gap-1.5">
                  <AlertTriangle className="h-4 w-4 text-warning" />
                  <span className="text-sm font-medium text-warning">
                    {counts.medium} Medium
                  </span>
                </div>
              )}
              {counts.low > 0 && (
                <div className="flex items-center gap-1.5">
                  <Info className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm font-medium text-muted-foreground">
                    {counts.low} Low
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* What are assumptions? */}
      <div className="bg-info/10 rounded-lg border border-info/30 p-4">
        <div className="flex items-start gap-3">
          <Info className="h-5 w-5 text-info flex-shrink-0 mt-0.5" />
          <div>
            <h4 className="font-medium text-info mb-1">
              What are assumptions?
            </h4>
            <p className="text-sm text-info/80">
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
        <div className="bg-card rounded-lg border border-border p-4">
          <h4 className="font-semibold text-foreground mb-3 flex items-center gap-2">
            <ChevronRight className="h-4 w-4" />
            Recommended Next Steps
          </h4>
          <ul className="space-y-2 text-sm text-muted-foreground">
            <li className="flex items-start gap-2">
              <span className="w-5 h-5 rounded-full bg-muted flex items-center justify-center flex-shrink-0 text-xs font-medium text-foreground">
                1
              </span>
              <span>
                Request missing documentation from the claimant to verify assumed values
              </span>
            </li>
            <li className="flex items-start gap-2">
              <span className="w-5 h-5 rounded-full bg-muted flex items-center justify-center flex-shrink-0 text-xs font-medium text-foreground">
                2
              </span>
              <span>
                Check if alternative data sources can provide the missing information
              </span>
            </li>
            <li className="flex items-start gap-2">
              <span className="w-5 h-5 rounded-full bg-muted flex items-center justify-center flex-shrink-0 text-xs font-medium text-foreground">
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
