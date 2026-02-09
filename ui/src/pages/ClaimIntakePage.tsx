import { useState, useEffect, useCallback, useRef } from "react";
import { cn } from "../lib/utils";

// =============================================================================
// TYPES
// =============================================================================

type StepStatus = "idle" | "uploading" | "processing" | "complete";

interface LineItem {
  id: number;
  description: string;
  partNo: string;
  hours: number;
  labor: number;
  parts: number;
  total: number;
  covered: boolean;
  reason?: string;
}

// =============================================================================
// MOCK DATA
// =============================================================================

const VEHICLE = {
  brand: "BMW",
  model: "X3 xDrive20d",
  vin: "WBA8E1105J7890123",
  plate: "ZH 456 789",
  firstRegistration: "15.03.2021",
  mileage: 45230,
};

const OWNER = {
  name: "Hans Müller",
  street: "Bahnhofstrasse 42",
  zip: "8001",
  city: "Zürich",
  phone: "+41 79 123 45 67",
};

const POLICY = {
  number: "NSA-2024-78543",
  type: "Premium Plus",
  validFrom: "01.04.2024",
  validTo: "31.03.2027",
  maxAmount: 15000,
  deductible: 200,
  mileageLimit: 150000,
};

const COVERED_COMPONENTS = [
  "Engine",
  "Turbocharger",
  "Transmission",
  "Differential",
  "Steering",
  "Electrical",
  "A/C",
  "Fuel system",
  "Cooling",
];

const NOT_COVERED_COMPONENTS = ["Brakes", "Wear parts", "Body/Paint"];

const GARAGE = {
  name: "AutoCenter Zürich AG",
  contact: "Marco Bernasconi",
  phone: "+41 44 987 65 43",
};

const LINE_ITEMS: LineItem[] = [
  { id: 1, description: "Turbocharger replacement", partNo: "11657849650", hours: 4.5, labor: 675, parts: 1850, total: 2525, covered: true },
  { id: 2, description: "Turbo oil feed line", partNo: "11657848070", hours: 1.0, labor: 150, parts: 85, total: 235, covered: true },
  { id: 3, description: "Gasket set turbo", partNo: "18307812281", hours: 0.5, labor: 75, parts: 45, total: 120, covered: true },
  { id: 4, description: "Brake disc front (pair)", partNo: "34116860912", hours: 1.5, labor: 225, parts: 380, total: 605, covered: false, reason: "Wear part" },
  { id: 5, description: "Brake pads front", partNo: "34116888457", hours: 0.5, labor: 75, parts: 120, total: 195, covered: false, reason: "Wear part" },
  { id: 6, description: "Diagnostic & test drive", partNo: "\u2014", hours: 1.0, labor: 150, parts: 0, total: 150, covered: true },
];

const SUMMARY = {
  total: 3830,
  covered: 3030,
  notCovered: 800,
  deductible: 200,
  netPayout: 2830,
};

const STEP1_MESSAGES = [
  "Reading document...",
  "Detecting document type...",
  "Extracting vehicle data...",
  "Extracting owner information...",
  "Validating VIN checksum...",
  "Complete",
];

const STEP2_MESSAGES = [
  "Looking up VIN in policy database...",
  "Matching active policies...",
  "Loading coverage details...",
  "Complete",
];

const STEP3_MESSAGES = [
  "Parsing cost estimate...",
  "Identifying garage information...",
  "Extracting line items...",
  "Matching parts to coverage...",
  "Calculating payout...",
  "Complete",
];

// =============================================================================
// HELPERS
// =============================================================================

const chf = new Intl.NumberFormat("de-CH", {
  style: "currency",
  currency: "CHF",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function formatCHF(value: number): string {
  return chf.format(value);
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat("de-CH").format(value);
}

// =============================================================================
// HOOKS
// =============================================================================

function useSimulatedProgress(
  active: boolean,
  durationMs: number,
  messages: string[],
  onComplete: () => void
) {
  const [progress, setProgress] = useState(0);
  const [messageIndex, setMessageIndex] = useState(0);
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  useEffect(() => {
    if (!active) {
      setProgress(0);
      setMessageIndex(0);
      return;
    }

    const tickInterval = 50;
    const totalTicks = durationMs / tickInterval;
    const messageInterval = durationMs / messages.length;
    let tick = 0;

    const timer = setInterval(() => {
      tick++;
      const pct = Math.min((tick / totalTicks) * 100, 99);
      setProgress(pct);
      const mIdx = Math.min(
        Math.floor((tick * tickInterval) / messageInterval),
        messages.length - 1
      );
      setMessageIndex(mIdx);

      if (tick >= totalTicks) {
        clearInterval(timer);
        setProgress(100);
        setMessageIndex(messages.length - 1);
        setTimeout(() => onCompleteRef.current(), 300);
      }
    }, tickInterval);

    return () => clearInterval(timer);
  }, [active, durationMs, messages.length]);

  return { progress, message: messages[messageIndex] ?? "" };
}

// =============================================================================
// SUB-COMPONENTS
// =============================================================================

function StepIndicator({
  steps,
  statuses,
}: {
  steps: string[];
  statuses: StepStatus[];
}) {
  return (
    <div className="flex items-center justify-center gap-0 w-full max-w-2xl mx-auto py-2">
      {steps.map((label, i) => {
        const status = statuses[i];
        const isComplete = status === "complete";
        const isActive = status === "uploading" || status === "processing";
        const isIdle = status === "idle";

        return (
          <div key={i} className="flex items-center flex-1 last:flex-none">
            {/* Step circle + label */}
            <div className="flex flex-col items-center gap-1.5">
              <div
                className={cn(
                  "w-10 h-10 rounded-full flex items-center justify-center text-sm font-semibold transition-all duration-500 border-2",
                  isComplete &&
                    "bg-success text-success-foreground border-success",
                  isActive &&
                    "bg-primary text-primary-foreground border-primary animate-pulse",
                  isIdle &&
                    "bg-muted text-muted-foreground border-border"
                )}
              >
                {isComplete ? (
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  i + 1
                )}
              </div>
              <span
                className={cn(
                  "text-xs font-medium whitespace-nowrap transition-colors duration-300",
                  isComplete && "text-success",
                  isActive && "text-primary",
                  isIdle && "text-muted-foreground"
                )}
              >
                {label}
              </span>
            </div>

            {/* Connecting line */}
            {i < steps.length - 1 && (
              <div className="flex-1 mx-3 mt-[-1.25rem]">
                <div className="h-0.5 w-full bg-border rounded-full overflow-hidden">
                  <div
                    className={cn(
                      "h-full transition-all duration-700 rounded-full",
                      isComplete ? "w-full bg-success" : "w-0 bg-primary"
                    )}
                  />
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function DemoDropZone({
  label,
  sublabel,
  disabled,
  onDrop,
}: {
  label: string;
  sublabel: string;
  disabled?: boolean;
  onDrop: () => void;
}) {
  const [dragging, setDragging] = useState(false);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    if (!disabled) setDragging(true);
  }, [disabled]);

  const handleDragLeave = useCallback(() => setDragging(false), []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      if (!disabled) onDrop();
    },
    [disabled, onDrop]
  );

  const handleClick = useCallback(() => {
    if (!disabled) onDrop();
  }, [disabled, onDrop]);

  return (
    <button
      type="button"
      onClick={handleClick}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      disabled={disabled}
      className={cn(
        "w-full rounded-lg border-2 border-dashed p-8 transition-all duration-300 text-center cursor-pointer group",
        dragging
          ? "border-primary bg-primary/5 scale-[1.01]"
          : "border-border hover:border-primary/50 hover:bg-muted/50",
        disabled && "opacity-40 cursor-not-allowed hover:border-border hover:bg-transparent"
      )}
    >
      {/* Upload icon */}
      <div className="flex flex-col items-center gap-3">
        <div
          className={cn(
            "w-14 h-14 rounded-xl flex items-center justify-center transition-all duration-300",
            dragging
              ? "bg-primary/10 text-primary"
              : "bg-muted text-muted-foreground group-hover:bg-primary/10 group-hover:text-primary"
          )}
        >
          <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
            />
          </svg>
        </div>
        <div>
          <p className="text-sm font-semibold text-foreground">{label}</p>
          <p className="text-xs text-muted-foreground mt-0.5">{sublabel}</p>
        </div>
      </div>
    </button>
  );
}

function ProcessingOverlay({
  progress,
  message,
}: {
  progress: number;
  message: string;
}) {
  return (
    <div className="bg-card border rounded-lg p-6 space-y-4">
      <div className="flex items-center gap-3">
        <div className="relative w-5 h-5 flex-shrink-0">
          <svg className="w-5 h-5 animate-spin text-primary" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        </div>
        <span className="text-sm font-medium text-foreground">{message}</span>
      </div>
      <div className="w-full h-2 bg-muted rounded-full overflow-hidden">
        <div
          className="h-full bg-primary rounded-full transition-all duration-100 ease-linear"
          style={{ width: `${progress}%` }}
        />
      </div>
      <p className="text-xs text-muted-foreground text-right tabular-nums">
        {Math.round(progress)}%
      </p>
    </div>
  );
}

function VehicleDataCard() {
  return (
    <div className="bg-card text-card-foreground border rounded-lg shadow-sm overflow-hidden">
      <div className="px-5 py-3 border-b bg-muted/30">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17a2 2 0 11-4 0 2 2 0 014 0zM19 17a2 2 0 11-4 0 2 2 0 014 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16V6a1 1 0 00-1-1H4a1 1 0 00-1 1v10a1 1 0 001 1h1m8-1a1 1 0 01-1 1H9m4-1V8a1 1 0 011-1h2.586a1 1 0 01.707.293l3.414 3.414a1 1 0 01.293.707V16a1 1 0 01-1 1h-1m-6-1a1 1 0 001 1h1M5 17a2 2 0 104 0m-4 0a2 2 0 114 0m6 0a2 2 0 104 0m-4 0a2 2 0 114 0" />
          </svg>
          <h3 className="text-sm font-semibold">Vehicle Registration Data</h3>
        </div>
      </div>
      <div className="grid md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-border">
        {/* Vehicle */}
        <div className="p-5 space-y-3">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Vehicle
          </h4>
          <dl className="space-y-2">
            <DataRow label="Brand / Model" value={`${VEHICLE.brand} ${VEHICLE.model}`} />
            <DataRow label="VIN" value={VEHICLE.vin} mono />
            <DataRow label="License Plate" value={VEHICLE.plate} />
            <DataRow label="First Registration" value={VEHICLE.firstRegistration} />
            <DataRow label="Mileage" value={`${formatNumber(VEHICLE.mileage)} km`} />
          </dl>
        </div>
        {/* Owner */}
        <div className="p-5 space-y-3">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Owner
          </h4>
          <dl className="space-y-2">
            <DataRow label="Name" value={OWNER.name} />
            <DataRow label="Address" value={OWNER.street} />
            <DataRow label="City" value={`${OWNER.zip} ${OWNER.city}`} />
            <DataRow label="Phone" value={OWNER.phone} />
          </dl>
        </div>
      </div>
    </div>
  );
}

function DataRow({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex justify-between items-baseline gap-4">
      <dt className="text-xs text-muted-foreground whitespace-nowrap">{label}</dt>
      <dd
        className={cn(
          "text-sm font-medium text-right",
          mono && "font-mono text-xs"
        )}
      >
        {value}
      </dd>
    </div>
  );
}

function PolicyCard() {
  return (
    <div className="bg-card text-card-foreground border rounded-lg shadow-sm overflow-hidden">
      <div className="px-5 py-3 border-b bg-muted/30">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
          </svg>
          <h3 className="text-sm font-semibold">Policy Found</h3>
          <span className="ml-auto inline-flex items-center gap-1 text-xs font-medium text-success bg-success/10 px-2 py-0.5 rounded-full">
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
            </svg>
            Active
          </span>
        </div>
      </div>
      <div className="p-5 space-y-5">
        {/* Policy details grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <PolicyDetail label="Policy Number" value={POLICY.number} />
          <PolicyDetail label="Type" value={POLICY.type} />
          <PolicyDetail label="Valid" value={`${POLICY.validFrom} \u2013 ${POLICY.validTo}`} />
          <PolicyDetail label="Max Coverage" value={formatCHF(POLICY.maxAmount)} />
          <PolicyDetail label="Deductible" value={formatCHF(POLICY.deductible)} />
          <PolicyDetail label="Mileage Limit" value={`${formatNumber(POLICY.mileageLimit)} km`} />
        </div>

        {/* Covered components */}
        <div className="space-y-2.5">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Coverage
          </h4>
          <div className="flex flex-wrap gap-2">
            {COVERED_COMPONENTS.map((c) => (
              <CoverageTag key={c} label={c} covered />
            ))}
            {NOT_COVERED_COMPONENTS.map((c) => (
              <CoverageTag key={c} label={c} covered={false} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function PolicyDetail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-sm font-medium mt-0.5">{value}</p>
    </div>
  );
}

function CoverageTag({
  label,
  covered,
  reason,
}: {
  label: string;
  covered: boolean;
  reason?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium transition-colors",
        covered
          ? "bg-success/10 text-success"
          : "bg-destructive/10 text-destructive"
      )}
    >
      {covered ? (
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
        </svg>
      ) : (
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
        </svg>
      )}
      {label}
      {reason && <span className="opacity-70">({reason})</span>}
    </span>
  );
}

function CostEstimateResults() {
  return (
    <div className="space-y-4">
      {/* Garage info */}
      <div className="bg-card text-card-foreground border rounded-lg shadow-sm overflow-hidden">
        <div className="px-5 py-3 border-b bg-muted/30">
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
            </svg>
            <h3 className="text-sm font-semibold">Garage Information</h3>
          </div>
        </div>
        <div className="p-5">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <PolicyDetail label="Garage" value={GARAGE.name} />
            <PolicyDetail label="Contact" value={GARAGE.contact} />
            <PolicyDetail label="Phone" value={GARAGE.phone} />
          </div>
        </div>
      </div>

      {/* Line items table */}
      <div className="bg-card text-card-foreground border rounded-lg shadow-sm overflow-hidden">
        <div className="px-5 py-3 border-b bg-muted/30">
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 14l6-6m-5.5.5h.01m4.99 5h.01M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16l3.5-2 3.5 2 3.5-2 3.5 2zM10 8.5a.5.5 0 11-1 0 .5.5 0 011 0zm5 5a.5.5 0 11-1 0 .5.5 0 011 0z" />
            </svg>
            <h3 className="text-sm font-semibold">Cost Estimate Line Items</h3>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/20">
                <th className="text-left px-4 py-2.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider">#</th>
                <th className="text-left px-4 py-2.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Description</th>
                <th className="text-left px-4 py-2.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider hidden sm:table-cell">Part No.</th>
                <th className="text-right px-4 py-2.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider hidden md:table-cell">Hrs</th>
                <th className="text-right px-4 py-2.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider hidden md:table-cell">Labor</th>
                <th className="text-right px-4 py-2.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider hidden md:table-cell">Parts</th>
                <th className="text-right px-4 py-2.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Total</th>
                <th className="text-left px-4 py-2.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Verdict</th>
              </tr>
            </thead>
            <tbody>
              {LINE_ITEMS.map((item) => (
                <tr
                  key={item.id}
                  className={cn(
                    "border-b last:border-b-0 transition-colors",
                    !item.covered && "bg-destructive/[0.03]"
                  )}
                >
                  <td className="px-4 py-2.5 text-muted-foreground tabular-nums">{item.id}</td>
                  <td className="px-4 py-2.5 font-medium">{item.description}</td>
                  <td className="px-4 py-2.5 font-mono text-xs text-muted-foreground hidden sm:table-cell">{item.partNo}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums hidden md:table-cell">{item.hours.toFixed(1)}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums hidden md:table-cell">{formatCHF(item.labor)}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums hidden md:table-cell">{formatCHF(item.parts)}</td>
                  <td className="px-4 py-2.5 text-right font-medium tabular-nums">{formatCHF(item.total)}</td>
                  <td className="px-4 py-2.5">
                    <CoverageTag
                      label={item.covered ? "Covered" : "Not covered"}
                      covered={item.covered}
                      reason={item.reason}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Payout summary */}
      <div className="bg-card text-card-foreground border rounded-lg shadow-sm overflow-hidden">
        <div className="px-5 py-3 border-b bg-muted/30">
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <h3 className="text-sm font-semibold">Payout Summary</h3>
          </div>
        </div>
        <div className="p-5">
          <div className="max-w-sm ml-auto space-y-2">
            <SummaryRow label="Total claimed" value={formatCHF(SUMMARY.total)} />
            <SummaryRow label="Covered amount" value={formatCHF(SUMMARY.covered)} positive />
            <SummaryRow label="Not covered" value={`\u2212 ${formatCHF(SUMMARY.notCovered)}`} negative />
            <SummaryRow label="Deductible" value={`\u2212 ${formatCHF(SUMMARY.deductible)}`} negative />
            <div className="border-t pt-2 mt-2">
              <SummaryRow label="Net payout" value={formatCHF(SUMMARY.netPayout)} bold />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function SummaryRow({
  label,
  value,
  bold,
  positive,
  negative,
}: {
  label: string;
  value: string;
  bold?: boolean;
  positive?: boolean;
  negative?: boolean;
}) {
  return (
    <div className="flex justify-between items-baseline">
      <span
        className={cn(
          "text-sm",
          bold ? "font-semibold text-foreground" : "text-muted-foreground"
        )}
      >
        {label}
      </span>
      <span
        className={cn(
          "tabular-nums",
          bold ? "text-lg font-bold text-primary" : "text-sm font-medium",
          positive && "text-success",
          negative && "text-destructive"
        )}
      >
        {value}
      </span>
    </div>
  );
}

// =============================================================================
// SECTION WRAPPER (fade+slide animation)
// =============================================================================

function AnimatedSection({
  visible,
  children,
  className,
}: {
  visible: boolean;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "transition-all duration-500 ease-out",
        visible
          ? "opacity-100 translate-y-0"
          : "opacity-0 translate-y-4 pointer-events-none h-0 overflow-hidden",
        className
      )}
    >
      {children}
    </div>
  );
}

// =============================================================================
// MAIN PAGE
// =============================================================================

export function ClaimIntakePage() {
  const [step1Status, setStep1Status] = useState<StepStatus>("idle");
  const [step2Status, setStep2Status] = useState<StepStatus>("idle");
  const [step3Status, setStep3Status] = useState<StepStatus>("idle");

  // Step 1 processing
  const step1Progress = useSimulatedProgress(
    step1Status === "processing",
    3000,
    STEP1_MESSAGES,
    () => {
      setStep1Status("complete");
      // Auto-trigger step 2
      setTimeout(() => setStep2Status("processing"), 400);
    }
  );

  // Step 2 processing
  const step2Progress = useSimulatedProgress(
    step2Status === "processing",
    2000,
    STEP2_MESSAGES,
    () => setStep2Status("complete")
  );

  // Step 3 processing
  const step3Progress = useSimulatedProgress(
    step3Status === "processing",
    3000,
    STEP3_MESSAGES,
    () => setStep3Status("complete")
  );

  const handleStep1Drop = useCallback(() => {
    if (step1Status !== "idle") return;
    setStep1Status("uploading");
    // Brief "uploading" state then switch to processing
    setTimeout(() => setStep1Status("processing"), 500);
  }, [step1Status]);

  const handleStep3Drop = useCallback(() => {
    if (step3Status !== "idle") return;
    setStep3Status("uploading");
    setTimeout(() => setStep3Status("processing"), 500);
  }, [step3Status]);

  const handleReset = useCallback(() => {
    setStep1Status("idle");
    setStep2Status("idle");
    setStep3Status("idle");
  }, []);

  const allComplete =
    step1Status === "complete" &&
    step2Status === "complete" &&
    step3Status === "complete";

  return (
    <div className="p-6 space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="space-y-1">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Claim Intake</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Digital claim submission \u2014 upload documents, verify coverage, get instant payout calculation
            </p>
          </div>
          {(step1Status !== "idle" || step2Status !== "idle" || step3Status !== "idle") && (
            <button
              onClick={handleReset}
              className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors px-3 py-1.5 rounded-md border hover:bg-muted/50"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Reset Demo
            </button>
          )}
        </div>
      </div>

      {/* Demo banner */}
      <div className="bg-info/10 border border-info/20 rounded-lg px-4 py-3 flex items-start gap-3">
        <svg className="w-4 h-4 text-info mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <p className="text-xs text-info">
          <span className="font-semibold">Demo mode</span> \u2014 Drop any file (or click) to simulate the intake flow. All data is mocked.
        </p>
      </div>

      {/* Step indicator */}
      <StepIndicator
        steps={["Vehicle Registration", "Policy Lookup", "Cost Estimate"]}
        statuses={[step1Status, step2Status, step3Status]}
      />

      {/* Step 1: Upload vehicle registration */}
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-primary/10 text-primary text-xs font-bold">1</span>
          <h2 className="text-base font-semibold">Upload Vehicle Registration</h2>
        </div>

        {step1Status === "idle" && (
          <DemoDropZone
            label="Drop vehicle registration document"
            sublabel="Fahrzeugausweis / Vehicle Registration Certificate"
            onDrop={handleStep1Drop}
          />
        )}

        <AnimatedSection visible={step1Status === "uploading" || step1Status === "processing"}>
          <ProcessingOverlay
            progress={step1Progress.progress}
            message={step1Status === "uploading" ? "Uploading document..." : step1Progress.message}
          />
        </AnimatedSection>

        <AnimatedSection visible={step1Status === "complete"}>
          <VehicleDataCard />
        </AnimatedSection>
      </div>

      {/* Step 2: Policy lookup */}
      <AnimatedSection visible={step2Status !== "idle"}>
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-primary/10 text-primary text-xs font-bold">2</span>
            <h2 className="text-base font-semibold">Policy Lookup</h2>
            <span className="text-xs text-muted-foreground ml-1">(automatic by VIN)</span>
          </div>

          <AnimatedSection visible={step2Status === "processing"}>
            <ProcessingOverlay
              progress={step2Progress.progress}
              message={step2Progress.message}
            />
          </AnimatedSection>

          <AnimatedSection visible={step2Status === "complete"}>
            <PolicyCard />
          </AnimatedSection>
        </div>
      </AnimatedSection>

      {/* Step 3: Upload cost estimate */}
      <AnimatedSection visible={step2Status === "complete"}>
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-primary/10 text-primary text-xs font-bold">3</span>
            <h2 className="text-base font-semibold">Upload Cost Estimate</h2>
          </div>

          {step3Status === "idle" && (
            <DemoDropZone
              label="Drop cost estimate document"
              sublabel="Kostenvoranschlag / Repair Cost Estimate"
              onDrop={handleStep3Drop}
            />
          )}

          <AnimatedSection visible={step3Status === "uploading" || step3Status === "processing"}>
            <ProcessingOverlay
              progress={step3Progress.progress}
              message={step3Status === "uploading" ? "Uploading document..." : step3Progress.message}
            />
          </AnimatedSection>

          <AnimatedSection visible={step3Status === "complete"}>
            <CostEstimateResults />
          </AnimatedSection>
        </div>
      </AnimatedSection>

      {/* Completion banner */}
      <AnimatedSection visible={allComplete}>
        <div className="bg-success/10 border border-success/20 rounded-lg px-5 py-4 flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-success/20 flex items-center justify-center flex-shrink-0">
            <svg className="w-5 h-5 text-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <div>
            <p className="text-sm font-semibold text-success">Claim Ready for Submission</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              All documents processed. Estimated net payout: <span className="font-semibold text-foreground">{formatCHF(SUMMARY.netPayout)}</span>
            </p>
          </div>
        </div>
      </AnimatedSection>
    </div>
  );
}
