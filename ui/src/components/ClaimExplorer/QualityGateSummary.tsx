import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ShieldCheck,
} from "lucide-react";
import { cn } from "../../lib/utils";
import type { ClaimSummary, ClaimFacts } from "../../types";

interface QualityGateSummaryProps {
  claim: ClaimSummary;
  facts: ClaimFacts | null;
  className?: string;
}

// Gate result entry
interface GateResult {
  field: string;
  status: "pass" | "warn" | "fail";
  message?: string;
}

// Determine overall gate status
function getOverallStatus(passCount: number, warnCount: number, failCount: number): "pass" | "warn" | "fail" {
  if (failCount > 0) return "fail";
  if (warnCount > 0) return "warn";
  return "pass";
}

// Status icon component
function StatusIcon({
  status,
  size = "sm",
}: {
  status: "pass" | "warn" | "fail";
  size?: "sm" | "md";
}) {
  const sizeClass = size === "sm" ? "h-4 w-4" : "h-5 w-5";

  switch (status) {
    case "pass":
      return <CheckCircle2 className={cn(sizeClass, "text-green-600 dark:text-green-400")} />;
    case "warn":
      return <AlertTriangle className={cn(sizeClass, "text-amber-500")} />;
    case "fail":
      return <XCircle className={cn(sizeClass, "text-red-600 dark:text-red-400")} />;
  }
}

// Counter badge
function CounterBadge({
  count,
  status,
}: {
  count: number;
  status: "pass" | "warn" | "fail";
}) {
  const colors = {
    pass: "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400",
    warn: "bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400",
    fail: "bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400",
  };

  return (
    <span className={cn(
      "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold",
      colors[status]
    )}>
      <StatusIcon status={status} size="sm" />
      {count}
    </span>
  );
}

// Gate entry row
function GateRow({ gate }: { gate: GateResult }) {
  return (
    <div className={cn(
      "flex items-center gap-2 py-1.5 px-2 rounded text-sm",
      gate.status === "fail" && "bg-red-50 dark:bg-red-900/10",
      gate.status === "warn" && "bg-amber-50 dark:bg-amber-900/10"
    )}>
      <StatusIcon status={gate.status} />
      <span className={cn(
        "flex-1 truncate",
        gate.status === "pass" && "text-slate-600 dark:text-slate-400",
        gate.status === "warn" && "text-amber-700 dark:text-amber-300",
        gate.status === "fail" && "text-red-700 dark:text-red-300"
      )}>
        {gate.field}
      </span>
      {gate.message && (
        <span className="text-xs text-slate-400 truncate max-w-[120px]" title={gate.message}>
          {gate.message}
        </span>
      )}
    </div>
  );
}

/**
 * Quality gate summary showing pass/warn/fail counts and missing fields.
 * Used in the right column of the 60/40 layout.
 */
export function QualityGateSummary({ claim, facts, className }: QualityGateSummaryProps) {
  const passCount = claim.gate_pass_count || 0;
  const warnCount = claim.gate_warn_count || 0;
  const failCount = claim.gate_fail_count || 0;
  const totalCount = passCount + warnCount + failCount;

  const overallStatus = getOverallStatus(passCount, warnCount, failCount);

  // Mock gate results - in production, this would come from the API
  // For now we'll show a summary based on available data
  const gateResults: GateResult[] = [];

  // Check for missing critical fields from facts
  if (facts?.facts) {
    const factNames = facts.facts.map((f) => f.name);

    // Critical fields check
    const criticalFields = [
      { name: "vin", label: "VIN" },
      { name: "license_plate", label: "License Plate" },
      { name: "policy_number", label: "Policy Number" },
      { name: "incident_date", label: "Incident Date" },
    ];

    criticalFields.forEach(({ name, label }) => {
      const hasFact = factNames.includes(name);
      if (!hasFact) {
        gateResults.push({ field: label, status: "fail", message: "Missing" });
      }
    });

    // Warning fields
    const warningFields = [
      { name: "mileage", label: "Mileage" },
      { name: "owner_name", label: "Owner Name" },
    ];

    warningFields.forEach(({ name, label }) => {
      const hasFact = factNames.includes(name);
      if (!hasFact) {
        gateResults.push({ field: label, status: "warn", message: "Not found" });
      }
    });
  }

  // If we have failures/warnings from claim but no specific gates, show generic entries
  if (gateResults.length === 0) {
    if (failCount > 0) {
      for (let i = 0; i < failCount; i++) {
        gateResults.push({ field: `Quality check ${i + 1}`, status: "fail" });
      }
    }
    if (warnCount > 0) {
      for (let i = 0; i < warnCount; i++) {
        gateResults.push({ field: `Warning ${i + 1}`, status: "warn" });
      }
    }
  }

  // Sort by status: fail first, then warn, then pass
  gateResults.sort((a, b) => {
    const order = { fail: 0, warn: 1, pass: 2 };
    return order[a.status] - order[b.status];
  });

  return (
    <div className={cn(
      "bg-white dark:bg-slate-900 rounded-lg border overflow-hidden",
      overallStatus === "fail" && "border-red-200 dark:border-red-900",
      overallStatus === "warn" && "border-amber-200 dark:border-amber-900",
      overallStatus === "pass" && "border-slate-200 dark:border-slate-700",
      className
    )}>
      {/* Header */}
      <div className={cn(
        "px-4 py-3 border-b flex items-center justify-between",
        overallStatus === "fail" && "bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-900",
        overallStatus === "warn" && "bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-900",
        overallStatus === "pass" && "bg-slate-50 dark:bg-slate-800/50 border-slate-200 dark:border-slate-700"
      )}>
        <div className="flex items-center gap-2">
          <ShieldCheck className={cn(
            "h-4 w-4",
            overallStatus === "pass" && "text-green-600 dark:text-green-400",
            overallStatus === "warn" && "text-amber-500",
            overallStatus === "fail" && "text-red-600 dark:text-red-400"
          )} />
          <span className="text-sm font-semibold text-slate-700 dark:text-slate-200">
            Quality Gate
          </span>
        </div>

        {/* Status counts */}
        <div className="flex items-center gap-2">
          {passCount > 0 && <CounterBadge count={passCount} status="pass" />}
          {warnCount > 0 && <CounterBadge count={warnCount} status="warn" />}
          {failCount > 0 && <CounterBadge count={failCount} status="fail" />}
        </div>
      </div>

      {/* Content */}
      <div className="p-3">
        {totalCount === 0 ? (
          <div className="text-center py-4">
            <CheckCircle2 className="h-8 w-8 text-green-500 mx-auto mb-2" />
            <p className="text-sm text-slate-600 dark:text-slate-400">
              All quality checks passed
            </p>
          </div>
        ) : gateResults.length > 0 ? (
          <div className="space-y-1 max-h-[200px] overflow-y-auto">
            {gateResults.map((gate, idx) => (
              <GateRow key={idx} gate={gate} />
            ))}
          </div>
        ) : (
          <div className="text-center py-4 text-sm text-slate-500">
            No gate details available
          </div>
        )}
      </div>
    </div>
  );
}
