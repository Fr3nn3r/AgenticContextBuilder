import { useState } from "react";
import {
  Copy,
  Check,
  CheckCircle2,
  XCircle,
  ArrowRightCircle,
  Download,
} from "lucide-react";
import { cn } from "../../lib/utils";
import type { ClaimSummary, ClaimFacts, ClaimAssessment, AssessmentDecision } from "../../types";

interface ClaimContextBarProps {
  claim: ClaimSummary;
  facts: ClaimFacts | null;
  assessment: ClaimAssessment | null;
  onExport?: () => void;
  className?: string;
}

// Decision badge configuration
const DECISION_CONFIG: Record<AssessmentDecision, {
  icon: typeof CheckCircle2;
  label: string;
  bg: string;
  text: string;
}> = {
  APPROVE: {
    icon: CheckCircle2,
    label: "Approved",
    bg: "bg-success/10",
    text: "text-success",
  },
  REJECT: {
    icon: XCircle,
    label: "Rejected",
    bg: "bg-destructive/10",
    text: "text-destructive",
  },
  REFER_TO_HUMAN: {
    icon: ArrowRightCircle,
    label: "Referred",
    bg: "bg-warning/10",
    text: "text-warning",
  },
};

function getFact(facts: ClaimFacts | null, name: string): string | null {
  if (!facts?.facts) return null;
  const fact = facts.facts.find((f) => f.name === name);
  if (!fact) return null;
  if (Array.isArray(fact.value)) return fact.value.join(" ");
  return fact.value;
}

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    await navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <button
      onClick={handleCopy}
      className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-muted transition-all"
      title="Copy"
    >
      {copied ? (
        <Check className="h-3 w-3 text-success" />
      ) : (
        <Copy className="h-3 w-3 text-muted-foreground" />
      )}
    </button>
  );
}

function DecisionBadge({ decision }: { decision: AssessmentDecision }) {
  const config = DECISION_CONFIG[decision];
  const Icon = config.icon;

  return (
    <span className={cn(
      "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold",
      config.bg,
      config.text
    )}>
      <Icon className="h-3.5 w-3.5" />
      {config.label}
    </span>
  );
}

function ActionButton({
  onClick,
  variant,
  icon: Icon,
  children,
  disabled,
}: {
  onClick?: () => void;
  variant: "approve" | "reject" | "refer" | "neutral";
  icon: typeof CheckCircle2;
  children: React.ReactNode;
  disabled?: boolean;
}) {
  const variantStyles = {
    approve: "bg-success hover:bg-success/90 text-success-foreground",
    reject: "bg-destructive hover:bg-destructive/90 text-destructive-foreground",
    refer: "bg-warning hover:bg-warning/90 text-warning-foreground",
    neutral: "bg-muted hover:bg-muted/80 text-foreground",
  };

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors",
        variantStyles[variant],
        disabled && "opacity-50 cursor-not-allowed"
      )}
    >
      <Icon className="h-3.5 w-3.5" />
      {children}
    </button>
  );
}

function formatCurrency(amount: number, currency = "CHF"): string {
  const formatted = new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
  return `${currency} ${formatted}`;
}

/**
 * Sticky top bar for claim context with identity, status, actions, and user controls.
 * Follows the BatchContextBar pattern.
 */
export function ClaimContextBar({
  claim,
  facts,
  assessment,
  onExport,
  className,
}: ClaimContextBarProps) {
  // Extract key identifiers from facts
  const vehicleMake = getFact(facts, "vehicle_make");
  const vehicleModel = getFact(facts, "vehicle_model");
  const licensePlate = getFact(facts, "license_plate");

  const vehicleTitle = [vehicleMake, vehicleModel].filter(Boolean).join(" ") || "Unknown Vehicle";

  // Status determination
  const hasErrors = claim.gate_fail_count > 0;
  const hasWarnings = claim.gate_warn_count > 0;

  // Payout amount and currency (prefer assessment's currency if available)
  const payoutAmount = assessment?.payout ?? claim.amount ?? 0;
  const payoutCurrency = (assessment as { currency?: string | null })?.currency || claim.currency || "CHF";

  return (
    <div
      className={cn(
        "sticky top-0 z-10 bg-card border-b px-5 py-3",
        hasErrors
          ? "border-b-destructive"
          : hasWarnings
            ? "border-b-warning"
            : "border-b-success",
        className
      )}
      data-testid="claim-context-bar"
    >
      <div className="flex items-center justify-between gap-4">
        {/* Left: Claim identity */}
        <div className="flex items-center gap-4 min-w-0 flex-1">
          {/* Decision badge */}
          <div className="flex items-center gap-3">
            {assessment && (
              <DecisionBadge decision={assessment.decision} />
            )}
          </div>

          {/* Claim ID + Vehicle */}
          <div className="min-w-0 border-l border-border pl-4">
            <div className="flex items-center gap-2 group">
              <span className="text-sm font-mono font-semibold text-foreground truncate">
                {claim.claim_id}
              </span>
              <CopyButton value={claim.claim_id} />
            </div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span className="truncate">{vehicleTitle}</span>
              {licensePlate && (
                <>
                  <span className="text-border">|</span>
                  <span className="font-mono">{licensePlate}</span>
                </>
              )}
            </div>
          </div>

          {/* Payout total */}
          <div className="hidden md:block border-l border-border pl-4">
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground block">
              Total
            </span>
            <span className={cn(
              "text-lg font-bold tabular-nums font-mono",
              payoutAmount > 5000
                ? "text-destructive"
                : "text-foreground"
            )}>
              {formatCurrency(payoutAmount, payoutCurrency)}
            </span>
          </div>
        </div>

        {/* Right: Actions */}
        <div className="flex items-center gap-3 flex-shrink-0">
          <ActionButton
            variant="neutral"
            icon={Download}
            onClick={onExport}
            disabled={!onExport}
          >
            Export
          </ActionButton>
        </div>
      </div>
    </div>
  );
}
