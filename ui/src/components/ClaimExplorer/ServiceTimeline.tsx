import { useMemo } from "react";
import { AlertTriangle, Wrench, Calendar, ExternalLink } from "lucide-react";
import type { AggregatedFact, ServiceEntry, ServiceEntryProvenance } from "../../types";
import { cn } from "../../lib/utils";

interface ServiceTimelineProps {
  facts: AggregatedFact[];
  onViewSource?: (
    docId: string,
    page: number | null,
    charStart: number | null,
    charEnd: number | null
  ) => void;
}

interface TimelineEntry extends ServiceEntry {
  parsedDate: Date | null;
  parsedMileage: number | null;
  gapWarning?: "time" | "mileage" | "both" | null;
}

// Parse date from various formats
function parseServiceDate(dateStr: string | null | undefined): Date | null {
  if (!dateStr) return null;

  // Try various formats
  const formats = [
    /(\d{1,2})\.(\d{1,2})\.(\d{4})/, // DD.MM.YYYY
    /(\d{4})-(\d{2})-(\d{2})/,       // YYYY-MM-DD
    /(\d{1,2})\/(\d{1,2})\/(\d{4})/, // DD/MM/YYYY or MM/DD/YYYY
  ];

  for (const format of formats) {
    const match = dateStr.match(format);
    if (match) {
      // Handle DD.MM.YYYY format
      if (format === formats[0]) {
        return new Date(parseInt(match[3]), parseInt(match[2]) - 1, parseInt(match[1]));
      }
      // Handle YYYY-MM-DD
      if (format === formats[1]) {
        return new Date(parseInt(match[1]), parseInt(match[2]) - 1, parseInt(match[3]));
      }
    }
  }

  // Fallback to Date.parse
  const parsed = Date.parse(dateStr);
  return isNaN(parsed) ? null : new Date(parsed);
}

function parseMileage(mileage: string | number | null | undefined): number | null {
  if (mileage === null || mileage === undefined) return null;
  if (typeof mileage === "number") return mileage;

  const normalized = mileage.replace(/[^\d]/g, "");
  const num = parseInt(normalized, 10);
  return isNaN(num) ? null : num;
}

function formatDate(date: Date): string {
  return date.toLocaleDateString("de-CH", {
    day: "2-digit",
    month: "short",
    year: "numeric"
  });
}

function formatMileage(km: number): string {
  return new Intl.NumberFormat("de-CH").format(km) + " km";
}

// Calculate days between two dates
function daysBetween(d1: Date, d2: Date): number {
  const diffTime = Math.abs(d2.getTime() - d1.getTime());
  return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
}

// Timeline node component
function TimelineNode({
  entry,
  isFirst,
  isLast,
  prevEntry,
  onViewSource
}: {
  entry: TimelineEntry;
  isFirst: boolean;
  isLast: boolean;
  prevEntry?: TimelineEntry;
  onViewSource?: (
    docId: string,
    page: number | null,
    charStart: number | null,
    charEnd: number | null
  ) => void;
}) {
  // Calculate gap from previous entry
  let gapDays = 0;
  let gapKm = 0;

  if (prevEntry && entry.parsedDate && prevEntry.parsedDate) {
    gapDays = daysBetween(entry.parsedDate, prevEntry.parsedDate);
  }
  if (prevEntry && entry.parsedMileage && prevEntry.parsedMileage) {
    gapKm = Math.abs(entry.parsedMileage - prevEntry.parsedMileage);
  }

  // Determine if there's a warning gap (>365 days or >30,000 km)
  const hasTimeGap = gapDays > 365;
  const hasMileageGap = gapKm > 30000;
  const hasGap = hasTimeGap || hasMileageGap;

  // P0.1: Handle per-row click for viewing source
  const hasRowProvenance = entry.provenance && entry.provenance.doc_id;
  const handleEntryClick = (e: React.MouseEvent) => {
    if (!onViewSource || !entry.provenance) return;
    e.stopPropagation(); // Prevent bubbling to parent container

    onViewSource(
      entry.provenance.doc_id,
      entry.provenance.page ?? null,
      entry.provenance.char_start ?? null,
      entry.provenance.char_end ?? null
    );
  };

  return (
    <div className="relative flex items-start gap-3">
      {/* Timeline line */}
      <div className="flex flex-col items-center">
        {/* Top connector */}
        {!isFirst && (
          <div className={cn(
            "w-0.5 h-4 -mt-1",
            hasGap
              ? "bg-gradient-to-b from-slate-300 via-amber-400 to-amber-400 dark:from-slate-600 dark:via-amber-500 dark:to-amber-500"
              : "bg-slate-300 dark:bg-slate-600"
          )} />
        )}

        {/* Node dot */}
        <div className={cn(
          "relative z-10 w-3 h-3 rounded-full border-2 flex-shrink-0",
          hasGap
            ? "bg-amber-100 border-amber-400 dark:bg-amber-900 dark:border-amber-500"
            : "bg-white border-slate-400 dark:bg-slate-800 dark:border-slate-500"
        )}>
          {hasGap && (
            <div className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-amber-500 rounded-full animate-pulse" />
          )}
        </div>

        {/* Bottom connector */}
        {!isLast && (
          <div className="w-0.5 flex-1 min-h-[24px] bg-slate-300 dark:bg-slate-600" />
        )}
      </div>

      {/* Content */}
      <div className={cn(
        "flex-1 pb-4 min-w-0",
        isLast && "pb-0"
      )}>
        {/* Gap warning banner */}
        {hasGap && !isFirst && (
          <div className="flex items-center gap-1.5 mb-1.5 text-xs text-amber-600 dark:text-amber-400">
            <AlertTriangle className="h-3 w-3" />
            <span className="font-medium">
              Service Gap:
              {hasTimeGap && ` ${Math.floor(gapDays / 30)} months`}
              {hasTimeGap && hasMileageGap && ","}
              {hasMileageGap && ` ${formatMileage(gapKm)}`}
            </span>
          </div>
        )}

        {/* Service entry card - P0.1: clickable for per-row navigation */}
        <div
          className={cn(
            "rounded-lg border p-2.5 transition-all",
            hasGap
              ? "border-amber-200 dark:border-amber-800 bg-amber-50/50 dark:bg-amber-950/30"
              : "border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50",
            hasRowProvenance && onViewSource
              ? "cursor-pointer hover:shadow-md hover:border-primary/50"
              : "hover:shadow-sm"
          )}
          onClick={hasRowProvenance ? handleEntryClick : undefined}
          title={hasRowProvenance ? "Click to view source" : undefined}
        >
          {/* Header: Date and Type */}
          <div className="flex items-center justify-between gap-2 mb-1">
            <div className="flex items-center gap-2">
              {entry.parsedDate && (
                <span className="text-xs font-mono font-semibold text-slate-700 dark:text-slate-200">
                  {formatDate(entry.parsedDate)}
                </span>
              )}
              {!entry.parsedDate && entry.date && (
                <span className="text-xs font-mono text-slate-500">
                  {entry.date}
                </span>
              )}
            </div>

            <div className="flex items-center gap-2">
              {entry.parsedMileage && (
                <span className="text-xs font-mono text-slate-500 dark:text-slate-400 tabular-nums">
                  {formatMileage(entry.parsedMileage)}
                </span>
              )}
              {/* P0.1: Show indicator when row has provenance */}
              {hasRowProvenance && onViewSource && (
                <ExternalLink className="h-3 w-3 text-slate-400" />
              )}
            </div>
          </div>

          {/* Service details */}
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            {entry.service_type && (
              <div className="flex items-center gap-1 text-sm text-slate-600 dark:text-slate-300">
                <Wrench className="h-3 w-3 text-slate-400" />
                <span className="truncate max-w-[150px]" title={entry.service_type}>
                  {entry.service_type}
                </span>
              </div>
            )}
            {entry.provider && (
              <span className="text-xs text-slate-500 dark:text-slate-400 truncate max-w-[120px]" title={entry.provider}>
                @ {entry.provider}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export function ServiceTimeline({ facts, onViewSource }: ServiceTimelineProps) {
  // Extract service entries from facts
  const serviceEntriesFact = facts.find(
    f => f.name === "service_entries" && Array.isArray(f.structured_value)
  );

  const serviceEntries = useMemo(() => {
    if (!serviceEntriesFact?.structured_value) return [];

    const entries = serviceEntriesFact.structured_value as ServiceEntry[];

    // Parse and sort entries
    const parsed: TimelineEntry[] = entries.map(entry => ({
      ...entry,
      parsedDate: parseServiceDate(entry.date),
      parsedMileage: parseMileage(entry.mileage)
    }));

    // Sort by date descending (most recent first)
    parsed.sort((a, b) => {
      if (a.parsedDate && b.parsedDate) {
        return b.parsedDate.getTime() - a.parsedDate.getTime();
      }
      if (a.parsedMileage && b.parsedMileage) {
        return b.parsedMileage - a.parsedMileage;
      }
      return 0;
    });

    return parsed;
  }, [serviceEntriesFact]);

  // Count service gaps
  const gapCount = useMemo(() => {
    let count = 0;
    for (let i = 1; i < serviceEntries.length; i++) {
      const curr = serviceEntries[i];
      const prev = serviceEntries[i - 1];

      if (curr.parsedDate && prev.parsedDate) {
        const days = daysBetween(curr.parsedDate, prev.parsedDate);
        if (days > 365) count++;
      }
      if (curr.parsedMileage && prev.parsedMileage) {
        const km = Math.abs(curr.parsedMileage - prev.parsedMileage);
        if (km > 30000) count++;
      }
    }
    return count;
  }, [serviceEntries]);

  if (serviceEntries.length === 0) {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700 p-4">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-2">
          Service History
        </h3>
        <p className="text-sm text-slate-500">No service records available</p>
      </div>
    );
  }

  const handleViewSource = () => {
    if (onViewSource && serviceEntriesFact?.selected_from) {
      onViewSource(
        serviceEntriesFact.selected_from.doc_id,
        serviceEntriesFact.selected_from.page,
        serviceEntriesFact.selected_from.char_start,
        serviceEntriesFact.selected_from.char_end
      );
    }
  };

  return (
    <div
      className={cn(
        "bg-white dark:bg-slate-900 rounded-lg border overflow-hidden transition-all",
        gapCount > 0
          ? "border-amber-200 dark:border-amber-800"
          : "border-slate-200 dark:border-slate-700",
        onViewSource && "cursor-pointer hover:shadow-md"
      )}
      onClick={handleViewSource}
    >
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Calendar className="h-4 w-4 text-slate-400" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
            Service History
          </h3>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-500 dark:text-slate-400">
            {serviceEntries.length} records
          </span>
          {gapCount > 0 && (
            <div className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-100 dark:bg-amber-900/50">
              <AlertTriangle className="h-3 w-3 text-amber-500" />
              <span className="text-xs font-medium text-amber-700 dark:text-amber-400">
                {gapCount} gap{gapCount > 1 ? "s" : ""}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Timeline */}
      <div className="p-4 max-h-[300px] overflow-y-auto">
        {serviceEntries.map((entry, idx) => (
          <TimelineNode
            key={idx}
            entry={entry}
            isFirst={idx === 0}
            isLast={idx === serviceEntries.length - 1}
            prevEntry={idx > 0 ? serviceEntries[idx - 1] : undefined}
            onViewSource={onViewSource}
          />
        ))}
      </div>
    </div>
  );
}
