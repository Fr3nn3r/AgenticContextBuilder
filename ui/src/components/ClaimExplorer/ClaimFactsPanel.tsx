import { useState } from "react";
import { ExternalLink, ChevronDown, ChevronRight } from "lucide-react";
import type { ClaimFacts, AggregatedFact, ServiceEntry } from "../../types";
import { cn } from "../../lib/utils";
import { ServiceEntriesTable } from "./ServiceEntriesTable";

interface ClaimFactsPanelProps {
  facts: ClaimFacts;
  onViewSource?: (docId: string, page: number | null, charStart: number | null, charEnd: number | null) => void;
}

// Map doc_type to human-readable category names
const DOC_TYPE_LABELS: Record<string, string> = {
  vehicle_registration: "Vehicle Information",
  service_history: "Service History",
  nsa_guarantee: "Policy Details",
  cost_estimate: "Cost Estimate",
  fnol_form: "First Notice of Loss",
  police_report: "Police Report",
  damage_assessment: "Damage Assessment",
  invoice: "Invoice",
  unknown: "Other",
};

function getDocTypeLabel(docType: string): string {
  return DOC_TYPE_LABELS[docType] || formatFieldName(docType);
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


// Compact inline fact display
function CompactFactRow({
  fact,
  onViewSource,
}: {
  fact: AggregatedFact;
  onViewSource?: (docId: string, page: number | null, charStart: number | null, charEnd: number | null) => void;
}) {
  const hasStructuredValue =
    fact.structured_value !== undefined && fact.structured_value !== null;
  const isServiceEntries =
    fact.name === "service_entries" && Array.isArray(fact.structured_value);

  const handleViewSource = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (fact.selected_from && onViewSource) {
      onViewSource(
        fact.selected_from.doc_id,
        fact.selected_from.page,
        fact.selected_from.char_start,
        fact.selected_from.char_end
      );
    }
  };

  // For service entries, show expandable section
  if (isServiceEntries) {
    return (
      <div className="py-2">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs font-medium text-foreground">
            {formatFieldName(fact.name)}
          </span>
          {fact.selected_from && onViewSource && (
            <button onClick={handleViewSource} className="ml-auto text-muted-foreground hover:text-foreground transition-colors">
              <ExternalLink className="h-3 w-3" />
            </button>
          )}
        </div>
        <ServiceEntriesTable entries={fact.structured_value as ServiceEntry[]} />
      </div>
    );
  }

  // For other structured values, show as collapsible JSON
  if (hasStructuredValue) {
    return (
      <div className="py-2">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-medium text-foreground">
            {formatFieldName(fact.name)}
          </span>
          {fact.selected_from && onViewSource && (
            <button onClick={handleViewSource} className="ml-auto text-muted-foreground hover:text-foreground transition-colors">
              <ExternalLink className="h-3 w-3" />
            </button>
          )}
        </div>
        <div className="text-[10px] text-muted-foreground bg-muted/30 p-2 rounded overflow-x-auto ml-3">
          <pre className="whitespace-pre-wrap">{JSON.stringify(fact.structured_value, null, 2)}</pre>
        </div>
      </div>
    );
  }

  // Standard inline fact
  return (
    <div className="flex items-center gap-2 py-1.5 group">
      <span className="text-xs text-muted-foreground min-w-[100px] flex-shrink-0">
        {formatFieldName(fact.name)}
      </span>
      <span className="text-xs font-medium text-foreground flex-1 truncate">
        {formatValue(fact.value)}
      </span>
      {fact.selected_from && onViewSource && (
        <button
          onClick={handleViewSource}
          className="opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-foreground flex-shrink-0"
          title="View source"
        >
          <ExternalLink className="h-3 w-3" />
        </button>
      )}
    </div>
  );
}

function FactsGroup({
  docType,
  facts,
  onViewSource,
  defaultExpanded = true,
}: {
  docType: string;
  facts: AggregatedFact[];
  onViewSource?: (docId: string, page: number | null, charStart: number | null, charEnd: number | null) => void;
  defaultExpanded?: boolean;
}) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  return (
    <div className="mb-3 last:mb-0">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center gap-2 w-full text-left py-1.5 hover:bg-muted/30 rounded -mx-1 px-1 transition-colors"
      >
        {isExpanded ? (
          <ChevronDown className="h-3 w-3 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-3 w-3 text-muted-foreground" />
        )}
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
          {getDocTypeLabel(docType)}
        </span>
        <span className="text-[10px] text-muted-foreground/70">
          ({facts.length})
        </span>
      </button>

      {isExpanded && (
        <div className="ml-5 mt-1 border-l-2 border-border/50 pl-3">
          {facts.map((fact) => (
            <CompactFactRow key={fact.name} fact={fact} onViewSource={onViewSource} />
          ))}
        </div>
      )}
    </div>
  );
}

export function ClaimFactsPanel({ facts, onViewSource }: ClaimFactsPanelProps) {
  // Group facts by their source doc_type
  const groupedFacts = facts.facts.reduce<Record<string, AggregatedFact[]>>(
    (acc, fact) => {
      const docType = fact.selected_from?.doc_type || "unknown";
      if (!acc[docType]) {
        acc[docType] = [];
      }
      acc[docType].push(fact);
      return acc;
    },
    {}
  );

  // Order groups by a sensible priority
  const docTypePriority = [
    "vehicle_registration",
    "nsa_guarantee",
    "service_history",
    "cost_estimate",
    "fnol_form",
    "police_report",
    "damage_assessment",
    "invoice",
  ];

  const sortedDocTypes = Object.keys(groupedFacts).sort((a, b) => {
    const aIndex = docTypePriority.indexOf(a);
    const bIndex = docTypePriority.indexOf(b);
    if (aIndex === -1 && bIndex === -1) return a.localeCompare(b);
    if (aIndex === -1) return 1;
    if (bIndex === -1) return -1;
    return aIndex - bIndex;
  });

  if (facts.facts.length === 0) {
    return (
      <div className="text-sm text-muted-foreground text-center py-4">
        No facts aggregated for this claim
      </div>
    );
  }

  return (
    <div>
      {sortedDocTypes.map((docType, idx) => (
        <FactsGroup
          key={docType}
          docType={docType}
          facts={groupedFacts[docType]}
          onViewSource={onViewSource}
          defaultExpanded={idx < 3} // First 3 groups expanded by default
        />
      ))}
      <div className="text-[10px] text-muted-foreground mt-4 pt-3 border-t border-border">
        Generated {new Date(facts.generated_at).toLocaleString()} from {facts.sources.length} source{facts.sources.length !== 1 ? "s" : ""}
      </div>
    </div>
  );
}
