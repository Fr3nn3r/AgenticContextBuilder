import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { ServiceEntry } from "../../types";
import { cn } from "../../lib/utils";

interface ServiceEntriesTableProps {
  entries: ServiceEntry[];
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  if (typeof value === "number") return String(value);
  return JSON.stringify(value);
}

function ServiceEntryRow({
  entry,
  index,
}: {
  entry: ServiceEntry;
  index: number;
}) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Extract known fields for display
  const date = formatValue(entry.date);
  const mileage = formatValue(entry.mileage);
  const serviceType = formatValue(entry.service_type);
  const provider = formatValue(entry.provider);
  const workPerformed = formatValue(entry.work_performed);

  // Get additional fields not in the standard set
  const knownFields = [
    "date",
    "mileage",
    "service_type",
    "provider",
    "work_performed",
    "cost",
  ];
  const additionalFields = Object.entries(entry).filter(
    ([key]) => !knownFields.includes(key)
  );

  return (
    <div className="border-b border-border last:border-b-0">
      <div
        className={cn(
          "flex items-center gap-2 px-3 py-2 cursor-pointer hover:bg-muted/50 transition-colors",
          isExpanded && "bg-muted/30"
        )}
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <button className="p-0.5">
          {isExpanded ? (
            <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
          )}
        </button>
        <span className="text-xs text-muted-foreground w-6">#{index + 1}</span>
        <span className="text-sm font-medium flex-1 truncate">{date}</span>
        {mileage !== "—" && (
          <span className="text-xs text-muted-foreground">{mileage} km</span>
        )}
      </div>

      {isExpanded && (
        <div className="px-3 pb-3 pl-10 space-y-1.5 bg-muted/20">
          {serviceType !== "—" && (
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Service Type</span>
              <span className="text-foreground font-medium">{serviceType}</span>
            </div>
          )}
          {provider !== "—" && (
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Provider</span>
              <span className="text-foreground">{provider}</span>
            </div>
          )}
          {workPerformed !== "—" && (
            <div className="text-sm">
              <span className="text-muted-foreground block mb-0.5">
                Work Performed
              </span>
              <span className="text-foreground text-xs">{workPerformed}</span>
            </div>
          )}
          {additionalFields.map(([key, value]) => (
            <div key={key} className="flex justify-between text-sm">
              <span className="text-muted-foreground capitalize">
                {key.replace(/_/g, " ")}
              </span>
              <span className="text-foreground">{formatValue(value)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function ServiceEntriesTable({ entries }: ServiceEntriesTableProps) {
  if (!entries || entries.length === 0) {
    return (
      <div className="text-sm text-muted-foreground italic">
        No service entries
      </div>
    );
  }

  return (
    <div className="border border-border rounded-md overflow-hidden">
      <div className="px-3 py-2 bg-muted/50 border-b border-border">
        <span className="text-xs font-medium text-muted-foreground">
          {entries.length} Service {entries.length === 1 ? "Entry" : "Entries"}
        </span>
      </div>
      <div className="max-h-64 overflow-y-auto">
        {entries.map((entry, index) => (
          <ServiceEntryRow key={index} entry={entry} index={index} />
        ))}
      </div>
    </div>
  );
}
