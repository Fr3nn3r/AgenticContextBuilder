import { useState } from "react";
import { Copy, Check } from "lucide-react";
import type { ClaimSummary, ClaimFacts, AggregatedFact } from "../../types";
import { StatusBadge } from "../shared/StatusBadge";
import { cn } from "../../lib/utils";

interface ClaimHeroHeaderProps {
  facts: ClaimFacts | null;
  claim: ClaimSummary;
}

function getFact(facts: AggregatedFact[], name: string): string | null {
  const fact = facts.find((f) => f.name === name);
  if (!fact) return null;
  if (Array.isArray(fact.value)) return fact.value.join(" ");
  return fact.value;
}

function formatCurrency(amount: number | null, currency: string): string {
  if (amount === null || amount === undefined) return "—";
  return new Intl.NumberFormat("de-CH", {
    style: "currency",
    currency: currency || "CHF",
    minimumFractionDigits: 2,
  }).format(amount);
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      onClick={handleCopy}
      className="ml-1.5 p-0.5 rounded hover:bg-muted/50 transition-colors"
      title="Copy to clipboard"
    >
      {copied ? (
        <Check className="h-3.5 w-3.5 text-success" />
      ) : (
        <Copy className="h-3.5 w-3.5 text-muted-foreground" />
      )}
    </button>
  );
}

export function ClaimHeroHeader({ facts, claim }: ClaimHeroHeaderProps) {
  const allFacts = facts?.facts || [];

  // Extract vehicle information
  const vehicleMake = getFact(allFacts, "vehicle_make");
  const vehicleModel = getFact(allFacts, "vehicle_model");
  const licensePlate = getFact(allFacts, "license_plate");
  const vin = getFact(allFacts, "vin");

  // Extract total amount from cost estimate
  const totalAmount = getFact(allFacts, "total_amount_incl_vat");
  const parsedAmount = totalAmount ? parseFloat(totalAmount.replace(/[^\d.-]/g, "")) : null;

  // Build display strings
  const hasVehicleInfo = vehicleMake || vehicleModel;
  const vehicleTitle = hasVehicleInfo
    ? [vehicleMake, vehicleModel].filter(Boolean).join(" ")
    : claim.claim_id;

  const identifiers = [licensePlate, vin].filter(Boolean);

  // Determine status badge
  const getStatusVariant = () => {
    if (claim.gate_fail_count > 0) return "error";
    if (claim.gate_warn_count > 0) return "warning";
    if (claim.gate_pass_count > 0) return "success";
    return "neutral";
  };

  const getStatusLabel = () => {
    if (claim.gate_fail_count > 0) return "Needs Review";
    if (claim.gate_warn_count > 0) return "Warnings";
    if (claim.gate_pass_count > 0) return "Valid";
    return "Pending";
  };

  return (
    <div className="bg-muted/30 border-b border-border px-6 py-4">
      <div className="flex items-start justify-between gap-4">
        {/* Left: Vehicle Identity */}
        <div className="min-w-0 flex-1">
          <h1 className="text-2xl font-bold text-foreground truncate">
            {vehicleTitle}
          </h1>
          {identifiers.length > 0 && (
            <div className="flex items-center gap-2 mt-1 text-sm text-muted-foreground">
              {licensePlate && (
                <span className="font-mono inline-flex items-center">
                  {licensePlate}
                  <CopyButton text={licensePlate} />
                </span>
              )}
              {licensePlate && vin && <span>·</span>}
              {vin && (
                <span className="font-mono inline-flex items-center">
                  {vin}
                  <CopyButton text={vin} />
                </span>
              )}
            </div>
          )}
          {hasVehicleInfo && (
            <p className="text-xs text-muted-foreground mt-1">
              {claim.claim_id}
              {(claim.lob || claim.loss_type) && (
                <span className="ml-2">
                  · {[claim.lob, claim.loss_type].filter(Boolean).join(" · ")}
                </span>
              )}
            </p>
          )}
          {!hasVehicleInfo && (claim.lob || claim.loss_type) && (
            <p className="text-sm text-muted-foreground mt-0.5">
              {[claim.lob, claim.loss_type].filter(Boolean).join(" · ")}
            </p>
          )}
        </div>

        {/* Right: KPIs */}
        <div className="flex items-center gap-4 flex-shrink-0">
          {/* Total Amount */}
          {(parsedAmount !== null || claim.amount !== null) && (
            <div className="text-right">
              <p className={cn(
                "text-2xl font-bold tabular-nums",
                parsedAmount && parsedAmount > 1000 ? "text-primary" : "text-foreground"
              )}>
                {formatCurrency(parsedAmount ?? claim.amount, claim.currency)}
              </p>
              <p className="text-xs text-muted-foreground">Total Estimate</p>
            </div>
          )}

          {/* Status Badge */}
          <StatusBadge variant={getStatusVariant()} size="md">
            {getStatusLabel()}
          </StatusBadge>
        </div>
      </div>
    </div>
  );
}
