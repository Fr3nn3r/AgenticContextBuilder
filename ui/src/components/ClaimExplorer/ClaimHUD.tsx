import { useState } from "react";
import { Copy, Check, AlertTriangle, CheckCircle2, Clock, Search } from "lucide-react";
import type { ClaimSummary, ClaimFacts, AggregatedFact } from "../../types";
import { cn } from "../../lib/utils";

interface ClaimHUDProps {
  facts: ClaimFacts | null;
  claim: ClaimSummary;
  maxCoverage?: number;
  onVinSearch?: (vin: string) => void;
}

function getFact(facts: AggregatedFact[], name: string): string | null {
  const fact = facts.find((f) => f.name === name);
  if (!fact) return null;
  if (Array.isArray(fact.value)) return fact.value.join(" ");
  return fact.value;
}

function parseAmount(value: string | null): number | null {
  if (!value) return null;
  const normalized = value
    .replace(/[CHF€$£\s]/gi, "")
    .replace(/'/g, "")
    .replace(/,(?=\d{3})/g, "")
    .replace(/,/g, ".");
  const num = parseFloat(normalized);
  return isNaN(num) ? null : num;
}

function CopyableField({
  label,
  value,
  mono = true,
  onSearch
}: {
  label: string;
  value: string;
  mono?: boolean;
  onSearch?: () => void;
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    await navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="flex items-center gap-1.5 group">
      <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      <span className={cn(
        "text-sm font-semibold text-foreground",
        mono && "font-mono tracking-tight"
      )}>
        {value}
      </span>
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
      {onSearch && (
        <button
          onClick={onSearch}
          className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-muted transition-all"
          title="Search history"
        >
          <Search className="h-3 w-3 text-muted-foreground" />
        </button>
      )}
    </div>
  );
}

// Claim lifecycle stages
const CLAIM_STAGES = ["New", "Triage", "Review", "Decision", "Closed"] as const;

function ClaimThermometer({ currentStage }: { currentStage: string }) {
  const stageIndex = CLAIM_STAGES.findIndex(
    s => s.toLowerCase() === currentStage.toLowerCase()
  );
  const activeIndex = stageIndex >= 0 ? stageIndex : 1; // Default to Triage

  return (
    <div className="flex items-center gap-0.5">
      {CLAIM_STAGES.map((stage, idx) => {
        const isActive = idx <= activeIndex;
        const isCurrent = idx === activeIndex;

        return (
          <div key={stage} className="flex items-center">
            <div
              className={cn(
                "h-1.5 w-8 rounded-full transition-colors",
                isActive
                  ? isCurrent
                    ? "bg-warning"
                    : "bg-success"
                  : "bg-muted"
              )}
              title={stage}
            />
            {idx < CLAIM_STAGES.length - 1 && (
              <div className="w-0.5" />
            )}
          </div>
        );
      })}
      <span className="ml-2 text-[10px] uppercase tracking-wider text-muted-foreground">
        {CLAIM_STAGES[activeIndex]}
      </span>
    </div>
  );
}

function CostIndicator({
  amount,
  maxCoverage,
  currency = "CHF"
}: {
  amount: number;
  maxCoverage?: number;
  currency?: string;
}) {
  const isOverLimit = maxCoverage ? amount > maxCoverage : false;
  const percentage = maxCoverage ? Math.min((amount / maxCoverage) * 100, 100) : null;

  const formattedAmount = new Intl.NumberFormat("de-CH", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);

  return (
    <div className="flex flex-col items-end">
      <div className="flex items-baseline gap-1.5">
        <span className="text-xs text-muted-foreground font-medium">
          {currency}
        </span>
        <span className={cn(
          "text-2xl font-bold tabular-nums tracking-tight font-mono",
          isOverLimit
            ? "text-destructive"
            : "text-foreground"
        )}>
          {formattedAmount}
        </span>
      </div>

      {maxCoverage && (
        <div className="flex items-center gap-2 mt-1">
          <div className="w-20 h-1 bg-muted rounded-full overflow-hidden">
            <div
              className={cn(
                "h-full rounded-full transition-all",
                isOverLimit
                  ? "bg-destructive"
                  : percentage && percentage > 80
                    ? "bg-warning"
                    : "bg-success"
              )}
              style={{ width: `${percentage}%` }}
            />
          </div>
          <span className={cn(
            "text-[10px] uppercase tracking-wider",
            isOverLimit
              ? "text-destructive font-semibold"
              : "text-muted-foreground"
          )}>
            {isOverLimit ? "Over Limit" : "Within Limits"}
          </span>
        </div>
      )}
    </div>
  );
}

export function ClaimHUD({ facts, claim, maxCoverage = 5000, onVinSearch }: ClaimHUDProps) {
  const allFacts = facts?.facts || [];

  // Extract key identifiers
  const vehicleMake = getFact(allFacts, "vehicle_make");
  const vehicleModel = getFact(allFacts, "vehicle_model");
  const licensePlate = getFact(allFacts, "license_plate");
  const vin = getFact(allFacts, "vin");
  const totalAmount = getFact(allFacts, "total_amount_incl_vat");
  const parsedAmount = parseAmount(totalAmount) ?? claim.amount ?? 0;

  // Vehicle display
  const vehicleTitle = [vehicleMake, vehicleModel].filter(Boolean).join(" ") || "Unknown Vehicle";

  // Status determination
  const hasErrors = claim.gate_fail_count > 0;
  const hasWarnings = claim.gate_warn_count > 0;

  return (
    <div className={cn(
      "relative border-b-2 px-5 py-3",
      "bg-gradient-to-r from-muted/50 via-muted/50 to-muted",
      hasErrors
        ? "border-b-destructive"
        : hasWarnings
          ? "border-b-warning"
          : "border-b-success"
    )}>
      {/* Status indicator strip */}
      <div className={cn(
        "absolute left-0 top-0 bottom-0 w-1",
        hasErrors
          ? "bg-destructive"
          : hasWarnings
            ? "bg-warning"
            : "bg-success"
      )} />

      <div className="flex items-start justify-between gap-6">
        {/* Left: Vehicle Identity Block */}
        <div className="flex-1 min-w-0">
          {/* Vehicle name with status icon */}
          <div className="flex items-center gap-2 mb-1">
            {hasErrors ? (
              <AlertTriangle className="h-4 w-4 text-destructive flex-shrink-0" />
            ) : hasWarnings ? (
              <Clock className="h-4 w-4 text-warning flex-shrink-0" />
            ) : (
              <CheckCircle2 className="h-4 w-4 text-success flex-shrink-0" />
            )}
            <h1 className="text-lg font-bold text-foreground truncate">
              {vehicleTitle}
            </h1>
          </div>

          {/* Identifiers row */}
          <div className="flex items-center gap-4 flex-wrap">
            {licensePlate && (
              <CopyableField label="Plate" value={licensePlate} />
            )}
            {vin && (
              <CopyableField
                label="VIN"
                value={vin}
                onSearch={onVinSearch ? () => onVinSearch(vin) : undefined}
              />
            )}
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
                Claim
              </span>
              <span className="text-sm font-mono font-medium text-foreground">
                {claim.claim_id}
              </span>
            </div>
          </div>
        </div>

        {/* Center: Claim Thermometer */}
        <div className="hidden md:flex flex-col items-center justify-center px-4">
          <ClaimThermometer currentStage={claim.status || "Review"} />
        </div>

        {/* Right: Cost Indicator */}
        <div className="flex-shrink-0">
          <CostIndicator
            amount={parsedAmount}
            maxCoverage={maxCoverage}
            currency={claim.currency || "CHF"}
          />
        </div>
      </div>
    </div>
  );
}
