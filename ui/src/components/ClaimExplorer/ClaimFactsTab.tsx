import { useState, useCallback } from "react";
import {
  Loader2,
  Car,
  FileText,
  Calendar,
  DollarSign,
  Shield,
  Wrench,
  ExternalLink,
  MapPin,
  User,
  Hash,
  Gauge,
  Clock,
  Copy,
  Check,
  Database,
  CreditCard,
  Fuel,
  Tag,
  Building2,
  Search,
  Wallet,
  Package,
  HardHat,
  Minus,
} from "lucide-react";
import type { ClaimSummary, DocSummary, ClaimFacts, AggregatedFact } from "../../types";
import { cn } from "../../lib/utils";
import { DocumentsPanel } from "./DocumentsPanel";
import { WorkflowActionsPanel } from "./WorkflowActionsPanel";

interface ClaimWithDocs extends ClaimSummary {
  documents?: DocSummary[];
}

interface ClaimFactsTabProps {
  claim: ClaimWithDocs;
  facts: ClaimFacts | null;
  loading: boolean;
  error: string | null;
  onDocumentClick?: (docId: string) => void;
  onViewSource?: (
    docId: string,
    page: number | null,
    charStart: number | null,
    charEnd: number | null,
    highlightText?: string,
    highlightValue?: string
  ) => void;
}

/** Get a fact value by trying multiple possible field names */
function getFactValue(
  facts: AggregatedFact[],
  ...names: string[]
): { value: string | null; fact: AggregatedFact | null } {
  for (const name of names) {
    const fact = facts.find(
      (f) => f.name.toLowerCase() === name.toLowerCase()
    );
    if (fact && fact.value !== null && fact.value !== "") {
      const value = Array.isArray(fact.value)
        ? fact.value.join(" ")
        : String(fact.value);
      return { value, fact };
    }
  }
  // Try partial match
  for (const name of names) {
    const fact = facts.find((f) =>
      f.name.toLowerCase().includes(name.toLowerCase().replace("_", ""))
    );
    if (fact && fact.value !== null && fact.value !== "") {
      const value = Array.isArray(fact.value)
        ? fact.value.join(" ")
        : String(fact.value);
      return { value, fact };
    }
  }
  return { value: null, fact: null };
}

/** Format date for display */
function formatDate(value: string | null): string {
  if (!value) return "";
  try {
    const date = new Date(value);
    if (!isNaN(date.getTime())) {
      return new Intl.DateTimeFormat("de-CH", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      }).format(date);
    }
  } catch {
    // ignore
  }
  return value;
}

/** Format currency for display */
function formatCurrency(value: string | null): string {
  if (!value) return "";
  const num = parseFloat(value.replace(/[^\d.-]/g, ""));
  if (isNaN(num)) return value;
  return new Intl.NumberFormat("de-CH", {
    style: "currency",
    currency: "CHF",
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(num);
}

/** Format mileage for display */
function formatMileage(value: string | null): string {
  if (!value) return "";
  const num = parseInt(value.replace(/[^\d]/g, ""), 10);
  if (isNaN(num)) return value;
  return new Intl.NumberFormat("de-CH").format(num) + " km";
}

interface FactItemProps {
  icon?: typeof Car;
  label: string;
  value: string | null;
  fact: AggregatedFact | null;
  mono?: boolean;
  onViewSource?: ClaimFactsTabProps["onViewSource"];
}

function FactItem({ icon: Icon, label, value, fact, mono, onViewSource }: FactItemProps) {
  if (!value) return null;

  const hasSource = fact?.selected_from?.doc_id;

  const handleClick = () => {
    if (onViewSource && fact?.selected_from) {
      onViewSource(
        fact.selected_from.doc_id,
        fact.selected_from.page,
        fact.selected_from.char_start,
        fact.selected_from.char_end,
        fact.selected_from.text_quote ?? undefined,
        value ?? undefined
      );
    }
  };

  return (
    <div
      className={cn(
        "flex items-center gap-2 py-1.5 px-2 rounded-md transition-colors",
        hasSource && onViewSource
          ? "hover:bg-muted/50 cursor-pointer"
          : ""
      )}
      onClick={hasSource ? handleClick : undefined}
    >
      {Icon && <Icon className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />}
      <span className="text-xs text-muted-foreground flex-shrink-0 min-w-[80px]">
        {label}
      </span>
      <span
        className={cn(
          "text-sm font-medium text-foreground truncate",
          mono && "font-mono text-xs"
        )}
        title={value}
      >
        {value}
      </span>
      {hasSource && onViewSource && (
        <ExternalLink className="h-3 w-3 text-border flex-shrink-0 ml-auto" />
      )}
    </div>
  );
}

interface FactCardProps {
  icon: typeof Car;
  title: string;
  children: React.ReactNode;
  badge?: React.ReactNode;
}

function FactCard({ icon: Icon, title, children, badge }: FactCardProps) {
  return (
    <div className="bg-card rounded-lg border border-border overflow-hidden">
      <div className="px-3 py-2 border-b border-border bg-muted/50 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Icon className="h-4 w-4 text-muted-foreground" />
          <h4 className="text-xs font-semibold text-foreground uppercase tracking-wider">
            {title}
          </h4>
        </div>
        {badge}
      </div>
      <div className="p-2">{children}</div>
    </div>
  );
}

interface ClaimRunBadgeProps {
  claimRunId?: string;
  generatedAt?: string;
  extractionRuns?: string[];
}

/** Shows the current claim run ID with copy functionality */
function ClaimRunBadge({ claimRunId, generatedAt, extractionRuns }: ClaimRunBadgeProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    if (!claimRunId) return;
    try {
      await navigator.clipboard.writeText(claimRunId);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  }, [claimRunId]);

  if (!claimRunId && !generatedAt) return null;

  // Format timestamp for display
  const formattedDate = generatedAt
    ? new Intl.DateTimeFormat("en-GB", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      }).format(new Date(generatedAt))
    : null;

  // Shorten claim run ID for display (keep prefix + last 6 chars)
  const shortId = claimRunId
    ? claimRunId.length > 20
      ? `${claimRunId.slice(0, 4)}...${claimRunId.slice(-6)}`
      : claimRunId
    : null;

  return (
    <div className="mb-3 flex items-center gap-2 text-xs text-muted-foreground">
      <Database className="h-3.5 w-3.5" />
      <span>Claim Run:</span>
      {shortId && (
        <button
          onClick={handleCopy}
          className={cn(
            "inline-flex items-center gap-1 px-2 py-0.5 rounded font-mono text-xs",
            "bg-muted hover:bg-muted/80",
            "transition-colors cursor-pointer"
          )}
          title={`Click to copy: ${claimRunId}`}
        >
          {claimRunId}
          {copied ? (
            <Check className="h-3 w-3 text-success" />
          ) : (
            <Copy className="h-3 w-3 text-muted-foreground" />
          )}
        </button>
      )}
      {formattedDate && (
        <>
          <span className="text-border">|</span>
          <span>{formattedDate}</span>
        </>
      )}
      {extractionRuns && extractionRuns.length > 0 && (
        <>
          <span className="text-border">|</span>
          <span title={extractionRuns.join(", ")}>
            {extractionRuns.length} extraction run{extractionRuns.length !== 1 ? "s" : ""}
          </span>
        </>
      )}
    </div>
  );
}

/**
 * Facts tab showing extracted claim data in a clean, compact layout.
 * Only displays facts that actually exist - no empty sections.
 */
export function ClaimFactsTab({
  claim,
  facts,
  loading,
  error,
  onDocumentClick,
  onViewSource,
}: ClaimFactsTabProps) {
  const allFacts = facts?.facts || [];

  // Extract facts by category
  const vehicle = {
    make: getFactValue(allFacts, "vehicle_make", "make", "vehicle_brand"),
    model: getFactValue(allFacts, "vehicle_model", "model"),
    vin: getFactValue(allFacts, "vin", "vehicle_vin", "chassis_number"),
    plate: getFactValue(allFacts, "license_plate", "plate_number", "registration_number"),
    year: getFactValue(allFacts, "vehicle_first_registration", "first_registration_date", "registration_date", "registration_year"),
    mileage: getFactValue(allFacts, "mileage", "odometer_km", "vehicle_current_km", "current_mileage"),
    color: getFactValue(allFacts, "color", "vehicle_color"),
    engine: getFactValue(allFacts, "engine_type", "vehicle_fuel_type", "vehicle_type"),
    owner: getFactValue(allFacts, "owner_name", "registered_owner", "vehicle_owner", "keeper"),
  };

  const policy = {
    number: getFactValue(allFacts, "policy_number", "document_number", "contract_number", "guarantee_number"),
    holder: getFactValue(allFacts, "policyholder_name", "policy_holder", "customer_name"),
    start: getFactValue(allFacts, "start_date", "coverage_start_date", "policy_start_date", "delivery_date"),
    end: getFactValue(allFacts, "end_date", "expiry_date", "coverage_end_date", "policy_end_date"),
    type: getFactValue(allFacts, "guarantee_type", "policy_type", "coverage_type", "warranty_type"),
    dealer: getFactValue(allFacts, "garage_name", "dealer_name", "seller"),
  };

  const dates = {
    incident: getFactValue(allFacts, "incident_date", "loss_date", "damage_date", "document_date", "claim_date"),
    repair: getFactValue(allFacts, "repair_date", "service_date"),
    diagnostic: getFactValue(allFacts, "diagnostic_date", "inspection_date"),
  };

  const amounts = {
    claimed: getFactValue(allFacts, "total_amount_incl_vat", "total_amount", "claimed_amount", "subtotal_before_vat"),
    parts: getFactValue(allFacts, "parts_total", "parts_cost", "spare_parts"),
    labor: getFactValue(allFacts, "labor_total", "labor_cost", "workmanship"),
    maxCoverage: getFactValue(allFacts, "max_coverage", "max_coverage_engine", "coverage_limit"),
    deductible: getFactValue(allFacts, "excess_minimum", "excess_percent", "deductible", "franchise"),
  };

  const service = {
    provider: getFactValue(allFacts, "service_provider", "workshop", "garage_name", "repairer"),
    address: getFactValue(allFacts, "service_address", "workshop_address", "garage_address"),
    phone: getFactValue(allFacts, "service_phone", "workshop_phone", "contact"),
    workDone: getFactValue(allFacts, "work_performed", "repair_description", "service_description"),
    diagnosis: getFactValue(allFacts, "diagnosis", "fault_description", "problem_description"),
  };

  // Check which sections have data
  const hasVehicle = Object.values(vehicle).some((v) => v.value);
  const hasPolicy = Object.values(policy).some((v) => v.value);
  const hasDates = Object.values(dates).some((v) => v.value);
  const hasAmounts = Object.values(amounts).some((v) => v.value);
  const hasService = Object.values(service).some((v) => v.value);

  // Coverage facts (for warranty/coverage section)
  const coverageFacts = allFacts.filter(
    (f) =>
      f.name.includes("covered") ||
      f.name.includes("warranty") ||
      (f.name.includes("coverage") && !f.name.includes("date"))
  );
  const hasCoverage = coverageFacts.length > 0;

  const hasAnyFacts =
    hasVehicle || hasPolicy || hasDates || hasAmounts || hasService || hasCoverage;

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          <p className="text-sm text-muted-foreground">Loading facts...</p>
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

  if (!hasAnyFacts) {
    return (
      <div className="p-4">
        {/* Show claim run info even when no facts */}
        <ClaimRunBadge
          claimRunId={facts?.claim_run_id}
          generatedAt={facts?.generated_at}
          extractionRuns={facts?.extraction_runs_used}
        />

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          <div className="lg:col-span-3">
            <div className="bg-card rounded-lg border border-border p-8 text-center">
              <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center mx-auto mb-4">
                <FileText className="h-6 w-6 text-muted-foreground" />
              </div>
              <h3 className="text-sm font-medium text-foreground mb-1">
                No Facts Extracted
              </h3>
              <p className="text-xs text-muted-foreground">
                Run the extraction pipeline to generate claim facts.
              </p>
            </div>
          </div>
          <div className="lg:col-span-2">
            <DocumentsPanel
              documents={claim.documents || []}
              onDocumentClick={onDocumentClick}
            />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4">
      {/* Claim Run Badge */}
      <ClaimRunBadge
        claimRunId={facts?.claim_run_id}
        generatedAt={facts?.generated_at}
        extractionRuns={facts?.extraction_runs_used}
      />

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        {/* LEFT COLUMN - Facts Cards */}
        <div className="lg:col-span-3 space-y-3">
          {/* Vehicle */}
          {hasVehicle && (
            <FactCard icon={Car} title="Vehicle">
              <div className="grid grid-cols-2 gap-x-2">
                {(vehicle.make.value || vehicle.model.value) && (
                  <FactItem
                    icon={Car}
                    label="Vehicle"
                    value={[vehicle.make.value, vehicle.model.value]
                      .filter(Boolean)
                      .join(" ")}
                    fact={vehicle.make.fact || vehicle.model.fact}
                    onViewSource={onViewSource}
                  />
                )}
                <FactItem
                  icon={User}
                  label="Owner"
                  value={vehicle.owner.value}
                  fact={vehicle.owner.fact}
                  onViewSource={onViewSource}
                />
                <FactItem
                  icon={Hash}
                  label="VIN"
                  value={vehicle.vin.value}
                  fact={vehicle.vin.fact}
                  mono
                  onViewSource={onViewSource}
                />
                <FactItem
                  icon={CreditCard}
                  label="Plate"
                  value={vehicle.plate.value}
                  fact={vehicle.plate.fact}
                  mono
                  onViewSource={onViewSource}
                />
                <FactItem
                  icon={Calendar}
                  label="First Reg."
                  value={formatDate(vehicle.year.value)}
                  fact={vehicle.year.fact}
                  onViewSource={onViewSource}
                />
                <FactItem
                  icon={Gauge}
                  label="Mileage"
                  value={formatMileage(vehicle.mileage.value)}
                  fact={vehicle.mileage.fact}
                  onViewSource={onViewSource}
                />
                <FactItem
                  icon={Fuel}
                  label="Engine"
                  value={vehicle.engine.value}
                  fact={vehicle.engine.fact}
                  onViewSource={onViewSource}
                />
              </div>
            </FactCard>
          )}

          {/* Policy */}
          {hasPolicy && (
            <FactCard icon={Shield} title="Policy & Coverage">
              <div className="grid grid-cols-2 gap-x-2">
                <FactItem
                  icon={FileText}
                  label="Policy #"
                  value={policy.number.value}
                  fact={policy.number.fact}
                  mono
                  onViewSource={onViewSource}
                />
                <FactItem
                  icon={User}
                  label="Holder"
                  value={policy.holder.value}
                  fact={policy.holder.fact}
                  onViewSource={onViewSource}
                />
                <FactItem
                  icon={Calendar}
                  label="Start"
                  value={formatDate(policy.start.value)}
                  fact={policy.start.fact}
                  onViewSource={onViewSource}
                />
                <FactItem
                  icon={Calendar}
                  label="End"
                  value={formatDate(policy.end.value)}
                  fact={policy.end.fact}
                  onViewSource={onViewSource}
                />
                <FactItem
                  icon={Tag}
                  label="Type"
                  value={policy.type.value}
                  fact={policy.type.fact}
                  onViewSource={onViewSource}
                />
                <FactItem
                  icon={Building2}
                  label="Dealer"
                  value={policy.dealer.value}
                  fact={policy.dealer.fact}
                  onViewSource={onViewSource}
                />
              </div>
            </FactCard>
          )}

          {/* Dates */}
          {hasDates && (
            <FactCard icon={Calendar} title="Timeline">
              <div className="grid grid-cols-2 gap-x-2">
                <FactItem
                  icon={Clock}
                  label="Incident"
                  value={formatDate(dates.incident.value)}
                  fact={dates.incident.fact}
                  onViewSource={onViewSource}
                />
                <FactItem
                  icon={Wrench}
                  label="Repair"
                  value={formatDate(dates.repair.value)}
                  fact={dates.repair.fact}
                  onViewSource={onViewSource}
                />
                <FactItem
                  icon={Search}
                  label="Diagnostic"
                  value={formatDate(dates.diagnostic.value)}
                  fact={dates.diagnostic.fact}
                  onViewSource={onViewSource}
                />
              </div>
            </FactCard>
          )}

          {/* Amounts */}
          {hasAmounts && (
            <FactCard icon={DollarSign} title="Amounts">
              <div className="grid grid-cols-2 gap-x-2">
                <FactItem
                  icon={DollarSign}
                  label="Claimed"
                  value={formatCurrency(amounts.claimed.value)}
                  fact={amounts.claimed.fact}
                  onViewSource={onViewSource}
                />
                <FactItem
                  icon={Wallet}
                  label="Max Cover"
                  value={formatCurrency(amounts.maxCoverage.value)}
                  fact={amounts.maxCoverage.fact}
                  onViewSource={onViewSource}
                />
                <FactItem
                  icon={Package}
                  label="Parts"
                  value={formatCurrency(amounts.parts.value)}
                  fact={amounts.parts.fact}
                  onViewSource={onViewSource}
                />
                <FactItem
                  icon={HardHat}
                  label="Labor"
                  value={formatCurrency(amounts.labor.value)}
                  fact={amounts.labor.fact}
                  onViewSource={onViewSource}
                />
                <FactItem
                  icon={Minus}
                  label="Deductible"
                  value={formatCurrency(amounts.deductible.value)}
                  fact={amounts.deductible.fact}
                  onViewSource={onViewSource}
                />
              </div>
            </FactCard>
          )}

          {/* Service / Repair */}
          {hasService && (
            <FactCard icon={Wrench} title="Service & Repair">
              <div className="space-y-1">
                <FactItem
                  icon={Wrench}
                  label="Provider"
                  value={service.provider.value}
                  fact={service.provider.fact}
                  onViewSource={onViewSource}
                />
                <FactItem
                  icon={MapPin}
                  label="Address"
                  value={service.address.value}
                  fact={service.address.fact}
                  onViewSource={onViewSource}
                />
                {service.diagnosis.value && (
                  <div className="pt-2 border-t border-border mt-2">
                    <p className="text-xs text-muted-foreground mb-1">
                      Diagnosis
                    </p>
                    <p className="text-sm text-foreground">
                      {service.diagnosis.value}
                    </p>
                  </div>
                )}
                {service.workDone.value && (
                  <div className="pt-2 border-t border-border mt-2">
                    <p className="text-xs text-muted-foreground mb-1">
                      Work Performed
                    </p>
                    <p className="text-sm text-foreground">
                      {service.workDone.value}
                    </p>
                  </div>
                )}
              </div>
            </FactCard>
          )}

          {/* Coverage Matrix - compact version */}
          {hasCoverage && (
            <FactCard
              icon={Shield}
              title="Coverage Details"
              badge={
                <span className="text-xs text-muted-foreground">
                  {coverageFacts.length} items
                </span>
              }
            >
              <div className="flex flex-wrap gap-1.5">
                {coverageFacts.map((fact) => {
                  const strValue = Array.isArray(fact.value)
                    ? fact.value[0]
                    : String(fact.value || "");
                  const isTrue = ["true", "yes", "1", "ja", "covered"].includes(
                    strValue.toLowerCase()
                  );
                  const isFalse = ["false", "no", "0", "nein", "not covered"].includes(
                    strValue.toLowerCase()
                  );

                  return (
                    <button
                      key={fact.name}
                      onClick={() => {
                        if (onViewSource && fact.selected_from) {
                          onViewSource(
                            fact.selected_from.doc_id,
                            fact.selected_from.page,
                            fact.selected_from.char_start,
                            fact.selected_from.char_end,
                            fact.selected_from.text_quote ?? undefined,
                            strValue ?? undefined
                          );
                        }
                      }}
                      className={cn(
                        "px-2 py-1 rounded text-xs font-medium transition-colors",
                        isTrue && "bg-success/10 text-success",
                        isFalse && "bg-destructive/10 text-destructive",
                        !isTrue && !isFalse && "bg-muted text-foreground"
                      )}
                    >
                      {fact.name
                        .replace(/_covered$/, "")
                        .replace(/_/g, " ")
                        .replace(/\b\w/g, (c) => c.toUpperCase())}
                      {!isTrue && !isFalse && `: ${strValue}`}
                    </button>
                  );
                })}
              </div>
            </FactCard>
          )}
        </div>

        {/* RIGHT COLUMN - Documents & Feedback */}
        <div className="lg:col-span-2 space-y-4">
          <DocumentsPanel
            documents={claim.documents || []}
            onDocumentClick={onDocumentClick}
          />
          <WorkflowActionsPanel
            readiness={{ readinessPct: 0, blockingIssues: [], criticalAssumptions: 0, canAutoApprove: false, canAutoReject: false }}
            currentDecision={null}
          />
        </div>
      </div>
    </div>
  );
}
