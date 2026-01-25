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
      <span className="text-[10px] uppercase tracking-wider text-slate-500 dark:text-slate-400">
        {label}
      </span>
      <span className={cn(
        "text-sm font-semibold text-slate-800 dark:text-slate-100",
        mono && "font-mono tracking-tight"
      )}>
        {value}
      </span>
      <button
        onClick={handleCopy}
        className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-slate-200 dark:hover:bg-slate-700 transition-all"
        title="Copy"
      >
        {copied ? (
          <Check className="h-3 w-3 text-emerald-500" />
        ) : (
          <Copy className="h-3 w-3 text-slate-400" />
        )}
      </button>
      {onSearch && (
        <button
          onClick={onSearch}
          className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-slate-200 dark:hover:bg-slate-700 transition-all"
          title="Search history"
        >
          <Search className="h-3 w-3 text-slate-400" />
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
                    ? "bg-amber-400 dark:bg-amber-500"
                    : "bg-emerald-400 dark:bg-emerald-500"
                  : "bg-slate-200 dark:bg-slate-700"
              )}
              title={stage}
            />
            {idx < CLAIM_STAGES.length - 1 && (
              <div className="w-0.5" />
            )}
          </div>
        );
      })}
      <span className="ml-2 text-[10px] uppercase tracking-wider text-slate-500 dark:text-slate-400">
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
        <span className="text-xs text-slate-500 dark:text-slate-400 font-medium">
          {currency}
        </span>
        <span className={cn(
          "text-2xl font-bold tabular-nums tracking-tight font-mono",
          isOverLimit
            ? "text-red-600 dark:text-red-400"
            : "text-slate-800 dark:text-slate-100"
        )}>
          {formattedAmount}
        </span>
      </div>

      {maxCoverage && (
        <div className="flex items-center gap-2 mt-1">
          <div className="w-20 h-1 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
            <div
              className={cn(
                "h-full rounded-full transition-all",
                isOverLimit
                  ? "bg-red-500"
                  : percentage && percentage > 80
                    ? "bg-amber-500"
                    : "bg-emerald-500"
              )}
              style={{ width: `${percentage}%` }}
            />
          </div>
          <span className={cn(
            "text-[10px] uppercase tracking-wider",
            isOverLimit
              ? "text-red-600 dark:text-red-400 font-semibold"
              : "text-slate-500 dark:text-slate-400"
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
      "bg-gradient-to-r from-slate-50 via-slate-50 to-slate-100",
      "dark:from-slate-900 dark:via-slate-900 dark:to-slate-800",
      hasErrors
        ? "border-b-red-500"
        : hasWarnings
          ? "border-b-amber-500"
          : "border-b-emerald-500"
    )}>
      {/* Status indicator strip */}
      <div className={cn(
        "absolute left-0 top-0 bottom-0 w-1",
        hasErrors
          ? "bg-red-500"
          : hasWarnings
            ? "bg-amber-500"
            : "bg-emerald-500"
      )} />

      <div className="flex items-start justify-between gap-6">
        {/* Left: Vehicle Identity Block */}
        <div className="flex-1 min-w-0">
          {/* Vehicle name with status icon */}
          <div className="flex items-center gap-2 mb-1">
            {hasErrors ? (
              <AlertTriangle className="h-4 w-4 text-red-500 flex-shrink-0" />
            ) : hasWarnings ? (
              <Clock className="h-4 w-4 text-amber-500 flex-shrink-0" />
            ) : (
              <CheckCircle2 className="h-4 w-4 text-emerald-500 flex-shrink-0" />
            )}
            <h1 className="text-lg font-bold text-slate-800 dark:text-slate-100 truncate">
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
              <span className="text-[10px] uppercase tracking-wider text-slate-500 dark:text-slate-400">
                Claim
              </span>
              <span className="text-sm font-mono font-medium text-slate-600 dark:text-slate-300">
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
