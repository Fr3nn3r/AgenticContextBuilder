import type { AggregatedFact, ServiceEntry } from "../../types";
import { StatusBadge } from "../shared/StatusBadge";
import { cn } from "../../lib/utils";

interface FactCardProps {
  title: string;
  facts: AggregatedFact[];
  onViewSource?: (
    docId: string,
    page: number | null,
    charStart: number | null,
    charEnd: number | null
  ) => void;
}

function formatFieldName(name: string): string {
  return name
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function formatValue(value: string | string[] | null): string {
  if (value === null || value === undefined) return "—";
  if (Array.isArray(value)) return value.join(", ");
  return value;
}

function isBooleanField(name: string): boolean {
  return (
    name.includes("covered") ||
    name.includes("valid") ||
    name.includes("active") ||
    name.includes("expired") ||
    name.endsWith("_flag")
  );
}

function getBooleanValue(value: string | string[] | null): boolean | null {
  if (value === null || value === undefined) return null;
  const strValue = Array.isArray(value) ? value[0] : value;
  const lower = strValue.toLowerCase();
  if (["true", "yes", "1", "ja", "oui"].includes(lower)) return true;
  if (["false", "no", "0", "nein", "non"].includes(lower)) return false;
  return null;
}

function FactRow({
  fact,
  onViewSource,
}: {
  fact: AggregatedFact;
  onViewSource?: (
    docId: string,
    page: number | null,
    charStart: number | null,
    charEnd: number | null
  ) => void;
}) {
  const handleClick = () => {
    if (fact.selected_from && onViewSource) {
      onViewSource(
        fact.selected_from.doc_id,
        fact.selected_from.page,
        fact.selected_from.char_start,
        fact.selected_from.char_end
      );
    }
  };

  const isBoolean = isBooleanField(fact.name);
  const boolValue = isBoolean ? getBooleanValue(fact.value) : null;

  return (
    <div
      className={cn(
        "py-2 first:pt-0 last:pb-0",
        onViewSource &&
          fact.selected_from &&
          "cursor-pointer hover:bg-muted/30 -mx-4 px-4 transition-colors rounded"
      )}
      onClick={onViewSource && fact.selected_from ? handleClick : undefined}
    >
      <p className="text-xs text-muted-foreground mb-0.5">
        {formatFieldName(fact.name)}
      </p>
      {isBoolean && boolValue !== null ? (
        <StatusBadge
          variant={boolValue ? "success" : "neutral"}
          size="sm"
        >
          {boolValue ? "Yes" : "No"}
        </StatusBadge>
      ) : (
        <p className="text-sm font-medium text-foreground">
          {formatValue(fact.value)}
        </p>
      )}
    </div>
  );
}

function ServiceEntryRow({ entry, index }: { entry: ServiceEntry; index: number }) {
  return (
    <div className="bg-muted/30 rounded px-3 py-2 text-sm">
      <div className="flex justify-between items-center mb-1">
        <span className="text-xs text-muted-foreground">Service #{index + 1}</span>
        {entry.date && (
          <span className="text-xs font-medium">{entry.date}</span>
        )}
      </div>
      {entry.mileage && (
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">Mileage</span>
          <span>{entry.mileage}</span>
        </div>
      )}
      {entry.service_type && (
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">Type</span>
          <span>{entry.service_type}</span>
        </div>
      )}
      {entry.provider && (
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">Provider</span>
          <span>{entry.provider}</span>
        </div>
      )}
    </div>
  );
}

export function FactCard({ title, facts, onViewSource }: FactCardProps) {
  // Separate service entries from regular facts
  const serviceEntriesFact = facts.find(
    (f) => f.name === "service_entries" && Array.isArray(f.structured_value)
  );
  const regularFacts = facts.filter(
    (f) => f.name !== "service_entries" && !f.structured_value
  );

  const serviceEntries = serviceEntriesFact?.structured_value as ServiceEntry[] | undefined;

  if (regularFacts.length === 0 && !serviceEntries?.length) {
    return null;
  }

  return (
    <div className="bg-card rounded-lg border border-border shadow-sm hover:shadow-md transition-shadow">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border">
        <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
          {title}
        </h3>
      </div>

      {/* Content */}
      <div className="p-4 space-y-3">
        {/* Regular facts */}
        {regularFacts.map((fact) => (
          <FactRow key={fact.name} fact={fact} onViewSource={onViewSource} />
        ))}

        {/* Service entries */}
        {serviceEntries && serviceEntries.length > 0 && (
          <div className="space-y-2 pt-2">
            <p className="text-xs text-muted-foreground">
              Service History ({serviceEntries.length} entries)
            </p>
            {serviceEntries.map((entry, idx) => (
              <ServiceEntryRow key={idx} entry={entry} index={idx} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
