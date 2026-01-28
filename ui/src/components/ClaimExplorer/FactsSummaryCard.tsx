import {
  Car,
  Calendar,
  Gauge,
  FileText,
  User,
  Shield,
  Hash,
} from "lucide-react";
import type { AggregatedFact } from "../../types";
import { cn } from "../../lib/utils";

interface FactsSummaryCardProps {
  facts: AggregatedFact[];
  onViewSource?: (
    docId: string,
    page: number | null,
    charStart: number | null,
    charEnd: number | null
  ) => void;
}

function getFact(facts: AggregatedFact[], name: string): AggregatedFact | null {
  return facts.find((f) => f.name === name) || null;
}

function getFactValue(facts: AggregatedFact[], name: string): string | null {
  const fact = getFact(facts, name);
  if (!fact) return null;
  if (Array.isArray(fact.value)) return fact.value.join(" ");
  return fact.value;
}

function formatMileage(value: string | null): string {
  if (!value) return "—";
  const num = parseInt(value.replace(/[^\d]/g, ""), 10);
  if (isNaN(num)) return value;
  return new Intl.NumberFormat("de-CH").format(num) + " km";
}

function formatDate(value: string | null): string {
  if (!value) return "—";
  // Try to parse and format
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
    // ignore parse errors
  }
  return value;
}

// Compact data field for the grid
function DataField({
  icon: Icon,
  label,
  value,
  mono = false,
  onClick,
}: {
  icon?: typeof Car;
  label: string;
  value: string | null;
  mono?: boolean;
  onClick?: () => void;
}) {
  if (!value) return null;

  return (
    <div
      className={cn(
        "flex items-start gap-2 py-2 px-3 rounded-lg transition-colors",
        "bg-muted/50",
        onClick && "cursor-pointer hover:bg-muted"
      )}
      onClick={onClick}
    >
      {Icon && <Icon className="h-4 w-4 text-muted-foreground flex-shrink-0 mt-0.5" />}
      <div className="min-w-0 flex-1">
        <span className="text-[10px] uppercase tracking-wider text-muted-foreground block">
          {label}
        </span>
        <span
          className={cn(
            "text-sm font-medium text-foreground block truncate",
            mono && "font-mono"
          )}
          title={value}
        >
          {value}
        </span>
      </div>
    </div>
  );
}

/**
 * Consolidated key-value facts grid showing vehicle, policy, and date information.
 * Used in the left column of the 60/40 layout.
 */
export function FactsSummaryCard({ facts, onViewSource }: FactsSummaryCardProps) {
  // Extract facts
  const make = getFactValue(facts, "vehicle_make");
  const model = getFactValue(facts, "vehicle_model");
  const vin = getFactValue(facts, "vin") || getFactValue(facts, "chassis_number");
  const licensePlate = getFactValue(facts, "license_plate");
  const year = getFactValue(facts, "first_registration_date") || getFactValue(facts, "registration_year");
  const mileage = getFactValue(facts, "mileage") || getFactValue(facts, "current_mileage");

  // Policy facts
  const policyNumber = getFactValue(facts, "policy_number") || getFactValue(facts, "contract_number");
  const policyHolder = getFactValue(facts, "policy_holder") || getFactValue(facts, "owner_name") || getFactValue(facts, "registered_owner");
  const coverageStart = getFactValue(facts, "coverage_start_date") || getFactValue(facts, "policy_start_date");
  const coverageEnd = getFactValue(facts, "coverage_end_date") || getFactValue(facts, "policy_end_date");

  // Incident facts
  const incidentDate = getFactValue(facts, "incident_date") || getFactValue(facts, "loss_date");
  const reportDate = getFactValue(facts, "report_date") || getFactValue(facts, "notification_date");

  // Handler for clicking on a field
  const handleClick = (factName: string) => {
    if (!onViewSource) return;
    const fact = getFact(facts, factName);
    if (fact?.selected_from) {
      onViewSource(
        fact.selected_from.doc_id,
        fact.selected_from.page,
        fact.selected_from.char_start,
        fact.selected_from.char_end
      );
    }
  };

  // Check if we have any data
  const hasVehicleData = make || model || vin || licensePlate || year || mileage;
  const hasPolicyData = policyNumber || policyHolder || coverageStart || coverageEnd;
  const hasIncidentData = incidentDate || reportDate;

  if (!hasVehicleData && !hasPolicyData && !hasIncidentData) {
    return (
      <div className="bg-card rounded-lg border border-border p-4">
        <h3 className="text-sm font-semibold text-foreground mb-2">
          Claim Facts
        </h3>
        <p className="text-sm text-muted-foreground">No facts extracted</p>
      </div>
    );
  }

  return (
    <div className="bg-card rounded-lg border border-border overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border bg-muted/50">
        <h3 className="text-sm font-semibold text-foreground">
          Key Facts
        </h3>
      </div>

      <div className="p-4 space-y-4">
        {/* Vehicle section */}
        {hasVehicleData && (
          <div className="space-y-2">
            <h4 className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold flex items-center gap-1.5">
              <Car className="h-3 w-3" />
              Vehicle
            </h4>
            <div className="grid grid-cols-2 gap-2">
              {(make || model) && (
                <DataField
                  label="Vehicle"
                  value={[make, model].filter(Boolean).join(" ")}
                  onClick={onViewSource ? () => handleClick("vehicle_make") : undefined}
                />
              )}
              {licensePlate && (
                <DataField
                  label="License Plate"
                  value={licensePlate}
                  mono
                  onClick={onViewSource ? () => handleClick("license_plate") : undefined}
                />
              )}
              {vin && (
                <DataField
                  icon={Hash}
                  label="VIN"
                  value={vin}
                  mono
                  onClick={onViewSource ? () => handleClick("vin") : undefined}
                />
              )}
              {year && (
                <DataField
                  icon={Calendar}
                  label="First Reg."
                  value={formatDate(year)}
                  mono
                  onClick={onViewSource ? () => handleClick("first_registration_date") : undefined}
                />
              )}
              {mileage && (
                <DataField
                  icon={Gauge}
                  label="Mileage"
                  value={formatMileage(mileage)}
                  mono
                  onClick={onViewSource ? () => handleClick("mileage") : undefined}
                />
              )}
            </div>
          </div>
        )}

        {/* Policy section */}
        {hasPolicyData && (
          <div className="space-y-2">
            <h4 className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold flex items-center gap-1.5">
              <Shield className="h-3 w-3" />
              Policy
            </h4>
            <div className="grid grid-cols-2 gap-2">
              {policyNumber && (
                <DataField
                  icon={FileText}
                  label="Policy No."
                  value={policyNumber}
                  mono
                  onClick={onViewSource ? () => handleClick("policy_number") : undefined}
                />
              )}
              {policyHolder && (
                <DataField
                  icon={User}
                  label="Holder"
                  value={policyHolder}
                  onClick={onViewSource ? () => handleClick("policy_holder") : undefined}
                />
              )}
              {coverageStart && (
                <DataField
                  icon={Calendar}
                  label="Coverage Start"
                  value={formatDate(coverageStart)}
                  mono
                  onClick={onViewSource ? () => handleClick("coverage_start_date") : undefined}
                />
              )}
              {coverageEnd && (
                <DataField
                  icon={Calendar}
                  label="Coverage End"
                  value={formatDate(coverageEnd)}
                  mono
                  onClick={onViewSource ? () => handleClick("coverage_end_date") : undefined}
                />
              )}
            </div>
          </div>
        )}

        {/* Incident section */}
        {hasIncidentData && (
          <div className="space-y-2">
            <h4 className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold flex items-center gap-1.5">
              <Calendar className="h-3 w-3" />
              Incident
            </h4>
            <div className="grid grid-cols-2 gap-2">
              {incidentDate && (
                <DataField
                  icon={Calendar}
                  label="Loss Date"
                  value={formatDate(incidentDate)}
                  mono
                  onClick={onViewSource ? () => handleClick("incident_date") : undefined}
                />
              )}
              {reportDate && (
                <DataField
                  icon={Calendar}
                  label="Reported"
                  value={formatDate(reportDate)}
                  mono
                  onClick={onViewSource ? () => handleClick("report_date") : undefined}
                />
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
