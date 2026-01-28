import { Car, Calendar, Gauge, Palette } from "lucide-react";
import type { AggregatedFact } from "../../types";
import { cn } from "../../lib/utils";

interface VehicleCardProps {
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

// Compact key-value display
function DataField({
  icon: Icon,
  label,
  value,
  mono = false,
  onClick
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
        "flex items-center gap-2 py-1.5 px-2 rounded transition-colors",
        onClick && "cursor-pointer hover:bg-muted"
      )}
      onClick={onClick}
    >
      {Icon && <Icon className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />}
      <div className="min-w-0 flex-1">
        <span className="text-[10px] uppercase tracking-wider text-muted-foreground block">
          {label}
        </span>
        <span className={cn(
          "text-sm font-medium text-foreground block truncate",
          mono && "font-mono"
        )} title={value}>
          {value}
        </span>
      </div>
    </div>
  );
}

export function VehicleCard({ facts, onViewSource }: VehicleCardProps) {
  // Extract vehicle facts
  const make = getFactValue(facts, "vehicle_make");
  const model = getFactValue(facts, "vehicle_model");
  const year = getFactValue(facts, "first_registration_date") || getFactValue(facts, "registration_year");
  const mileage = getFactValue(facts, "mileage") || getFactValue(facts, "current_mileage");
  const color = getFactValue(facts, "vehicle_color") || getFactValue(facts, "color");
  const engineType = getFactValue(facts, "engine_type") || getFactValue(facts, "fuel_type");
  const transmission = getFactValue(facts, "transmission");
  const ownerName = getFactValue(facts, "owner_name") || getFactValue(facts, "registered_owner");

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

  // Check if we have any vehicle data
  const hasData = make || model || year || mileage || color;

  if (!hasData) {
    return (
      <div className="bg-card rounded-lg border border-border p-4">
        <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-2">
          Vehicle Information
        </h3>
        <p className="text-sm text-muted-foreground">No vehicle data available</p>
      </div>
    );
  }

  return (
    <div className="bg-card rounded-lg border border-border overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border flex items-center gap-2">
        <Car className="h-4 w-4 text-muted-foreground" />
        <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
          Vehicle
        </h3>
      </div>

      {/* Content grid */}
      <div className="p-2 grid grid-cols-2 gap-x-2">
        <DataField
          label="Make"
          value={make}
          onClick={onViewSource ? () => handleClick("vehicle_make") : undefined}
        />
        <DataField
          label="Model"
          value={model}
          onClick={onViewSource ? () => handleClick("vehicle_model") : undefined}
        />
        <DataField
          icon={Calendar}
          label="Year"
          value={year}
          mono
          onClick={onViewSource ? () => handleClick("first_registration_date") : undefined}
        />
        <DataField
          icon={Gauge}
          label="Mileage"
          value={formatMileage(mileage)}
          mono
          onClick={onViewSource ? () => handleClick("mileage") : undefined}
        />
        <DataField
          icon={Palette}
          label="Color"
          value={color}
          onClick={onViewSource ? () => handleClick("vehicle_color") : undefined}
        />
        <DataField
          label="Engine"
          value={engineType}
          onClick={onViewSource ? () => handleClick("engine_type") : undefined}
        />
        {transmission && (
          <DataField
            label="Trans"
            value={transmission}
            onClick={onViewSource ? () => handleClick("transmission") : undefined}
          />
        )}
        {ownerName && (
          <DataField
            label="Owner"
            value={ownerName}
            onClick={onViewSource ? () => handleClick("owner_name") : undefined}
          />
        )}
      </div>
    </div>
  );
}
