import {
  Car,
  FileText,
  Calendar,
  DollarSign,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  ExternalLink,
} from "lucide-react";
import { cn } from "../../lib/utils";
import type { AggregatedFact } from "../../types";

interface QuickFactsSummaryProps {
  facts: AggregatedFact[];
  onViewSource?: (
    docId: string,
    page: number | null,
    charStart: number | null,
    charEnd: number | null
  ) => void;
}

/** Status of a fact value */
type FactStatus = "present" | "assumed" | "missing";

interface QuickFactItem {
  label: string;
  value: string | null;
  status: FactStatus;
  factName: string;
  docId?: string;
  page?: number | null;
  charStart?: number | null;
  charEnd?: number | null;
}

/**
 * Get fact value from the facts array, handling various naming conventions.
 */
function getFact(facts: AggregatedFact[], ...names: string[]): AggregatedFact | null {
  for (const name of names) {
    const fact = facts.find(
      (f) => f.name.toLowerCase() === name.toLowerCase()
    );
    if (fact) return fact;
  }
  // Try partial match
  for (const name of names) {
    const fact = facts.find((f) =>
      f.name.toLowerCase().includes(name.toLowerCase().replace("_", ""))
    );
    if (fact) return fact;
  }
  return null;
}

/**
 * Build quick fact item from fact data.
 */
function buildFactItem(
  facts: AggregatedFact[],
  label: string,
  ...names: string[]
): QuickFactItem {
  const fact = getFact(facts, ...names);

  if (!fact) {
    return {
      label,
      value: null,
      status: "missing",
      factName: names[0],
    };
  }

  // Determine value
  let value: string | null = null;
  if (Array.isArray(fact.value)) {
    value = fact.value.join(" ");
  } else if (fact.value !== null && fact.value !== undefined) {
    value = String(fact.value);
  }

  // Determine status based on confidence and provenance
  let status: FactStatus = "present";
  if (!value || value === "") {
    status = "missing";
  } else if (fact.confidence < 0.7 || !fact.selected_from?.doc_id) {
    status = "assumed";
  }

  return {
    label,
    value,
    status,
    factName: fact.name,
    docId: fact.selected_from?.doc_id,
    page: fact.selected_from?.page,
    charStart: fact.selected_from?.char_start,
    charEnd: fact.selected_from?.char_end,
  };
}

/**
 * Format date value for display.
 */
function formatDate(value: string | null): string {
  if (!value) return "—";
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

/**
 * Format currency value for display.
 */
function formatCurrency(value: string | null): string {
  if (!value) return "—";
  const num = parseFloat(value.replace(/[^\d.-]/g, ""));
  if (isNaN(num)) return value;
  return new Intl.NumberFormat("de-CH", {
    style: "currency",
    currency: "CHF",
  }).format(num);
}

const STATUS_CONFIG: Record<
  FactStatus,
  { icon: typeof CheckCircle2; color: string; bg: string; label: string }
> = {
  present: {
    icon: CheckCircle2,
    color: "text-green-500",
    bg: "bg-green-100 dark:bg-green-900/30",
    label: "Sourced",
  },
  assumed: {
    icon: AlertTriangle,
    color: "text-amber-500",
    bg: "bg-amber-100 dark:bg-amber-900/30",
    label: "Assumed",
  },
  missing: {
    icon: XCircle,
    color: "text-red-400",
    bg: "bg-red-100 dark:bg-red-900/30",
    label: "Missing",
  },
};

/**
 * Compact facts summary for the Overview tab.
 * Shows key identifying facts with provenance indicators.
 */
export function QuickFactsSummary({ facts, onViewSource }: QuickFactsSummaryProps) {
  // Build quick facts from real data - use actual field names from backend
  const vehicleMake = buildFactItem(facts, "Make", "vehicle_make", "make", "vehicle_brand");
  const vehicleModel = buildFactItem(facts, "Model", "vehicle_model", "model");
  const vin = buildFactItem(facts, "VIN", "vin", "vehicle_vin", "chassis_number");
  const licensePlate = buildFactItem(facts, "Plate", "license_plate", "plate_number", "registration_number");

  const policyNumber = buildFactItem(facts, "Policy #", "policy_number", "document_number", "guarantee_number");
  const policyHolder = buildFactItem(
    facts,
    "Holder",
    "policyholder_name",
    "policy_holder",
    "owner_name"
  );

  const incidentDate = buildFactItem(facts, "Incident", "incident_date", "loss_date", "damage_date", "document_date", "claim_date");
  const coverageStart = buildFactItem(
    facts,
    "Coverage Start",
    "start_date",
    "coverage_start_date",
    "delivery_date"
  );
  const coverageEnd = buildFactItem(facts, "Coverage End", "end_date", "expiry_date", "coverage_end_date");

  const claimedAmount = buildFactItem(
    facts,
    "Claimed",
    "total_amount_incl_vat",
    "total_amount",
    "claimed_amount"
  );
  const coverageLimit = buildFactItem(
    facts,
    "Limit",
    "max_coverage",
    "max_coverage_engine",
    "coverage_limit"
  );

  // Combine vehicle make/model
  const vehicleValue =
    vehicleMake.value || vehicleModel.value
      ? [vehicleMake.value, vehicleModel.value].filter(Boolean).join(" ")
      : null;
  const vehicleStatus =
    vehicleMake.status === "missing" && vehicleModel.status === "missing"
      ? "missing"
      : vehicleMake.status === "assumed" || vehicleModel.status === "assumed"
      ? "assumed"
      : "present";

  const handleClick = (item: QuickFactItem) => {
    if (onViewSource && item.docId) {
      onViewSource(item.docId, item.page ?? null, item.charStart ?? null, item.charEnd ?? null);
    }
  };

  return (
    <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
          Key Facts
        </h3>
        <div className="flex items-center gap-2 text-[10px]">
          <span className="flex items-center gap-1 text-green-600 dark:text-green-400">
            <CheckCircle2 className="h-3 w-3" /> Sourced
          </span>
          <span className="flex items-center gap-1 text-amber-600 dark:text-amber-400">
            <AlertTriangle className="h-3 w-3" /> Low conf.
          </span>
          <span className="flex items-center gap-1 text-red-400">
            <XCircle className="h-3 w-3" /> Missing
          </span>
        </div>
      </div>

      <div className="p-4 grid grid-cols-2 gap-3">
        {/* Vehicle */}
        <FactGroup
          icon={Car}
          title="Vehicle"
          items={[
            {
              label: "Vehicle",
              value: vehicleValue,
              status: vehicleStatus,
              factName: "vehicle",
              docId: vehicleMake.docId || vehicleModel.docId,
            },
            vin,
            licensePlate,
          ]}
          onItemClick={handleClick}
        />

        {/* Policy */}
        <FactGroup
          icon={FileText}
          title="Policy"
          items={[policyNumber, policyHolder]}
          onItemClick={handleClick}
        />

        {/* Dates */}
        <FactGroup
          icon={Calendar}
          title="Dates"
          items={[
            { ...incidentDate, value: formatDate(incidentDate.value) },
            { ...coverageStart, value: formatDate(coverageStart.value) },
            { ...coverageEnd, value: formatDate(coverageEnd.value) },
          ]}
          onItemClick={handleClick}
        />

        {/* Amounts */}
        <FactGroup
          icon={DollarSign}
          title="Amounts"
          items={[
            { ...claimedAmount, value: formatCurrency(claimedAmount.value) },
            { ...coverageLimit, value: formatCurrency(coverageLimit.value) },
          ]}
          onItemClick={handleClick}
        />
      </div>
    </div>
  );
}

interface FactGroupProps {
  icon: typeof Car;
  title: string;
  items: QuickFactItem[];
  onItemClick?: (item: QuickFactItem) => void;
}

function FactGroup({ icon: Icon, title, items, onItemClick }: FactGroupProps) {
  return (
    <div className="space-y-1.5">
      <h4 className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold flex items-center gap-1">
        <Icon className="h-3 w-3" />
        {title}
      </h4>
      {items.map((item, idx) => {
        const statusConfig = STATUS_CONFIG[item.status];
        const StatusIcon = statusConfig.icon;
        const hasSource = item.docId;

        return (
          <div
            key={idx}
            className={cn(
              "flex items-center justify-between py-1 px-2 rounded transition-colors",
              hasSource && onItemClick
                ? "hover:bg-slate-50 dark:hover:bg-slate-800/50 cursor-pointer"
                : ""
            )}
            onClick={() => hasSource && onItemClick?.(item)}
          >
            <div className="flex items-center gap-2 min-w-0 flex-1">
              <StatusIcon className={cn("h-3 w-3 flex-shrink-0", statusConfig.color)} />
              <span className="text-xs text-slate-500 dark:text-slate-400 flex-shrink-0">
                {item.label}:
              </span>
              <span
                className={cn(
                  "text-xs font-medium truncate",
                  item.status === "missing"
                    ? "text-slate-400 dark:text-slate-500 italic"
                    : "text-slate-700 dark:text-slate-200"
                )}
                title={item.value || undefined}
              >
                {item.value || "Not found"}
              </span>
            </div>
            {hasSource && onItemClick && (
              <ExternalLink className="h-3 w-3 text-slate-300 dark:text-slate-600 flex-shrink-0 ml-1" />
            )}
          </div>
        );
      })}
    </div>
  );
}
