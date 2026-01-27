import { CheckCircle2, XCircle, HelpCircle, ClipboardCheck } from "lucide-react";
import * as Tooltip from "@radix-ui/react-tooltip";
import { cn } from "../../lib/utils";
import type { AssessmentCheck, CheckResult } from "../../types";

interface ChecksSummaryPanelProps {
  checks: AssessmentCheck[];
  onCheckClick?: (checkNumber: number) => void;
  className?: string;
}

const RESULT_CONFIG: Record<CheckResult, {
  icon: typeof CheckCircle2;
  dot: string;
  text: string;
  bg: string;
}> = {
  PASS: {
    icon: CheckCircle2,
    dot: "bg-success",
    text: "text-success",
    bg: "bg-success/10",
  },
  FAIL: {
    icon: XCircle,
    dot: "bg-destructive",
    text: "text-destructive",
    bg: "bg-destructive/10",
  },
  INCONCLUSIVE: {
    icon: HelpCircle,
    dot: "bg-warning",
    text: "text-warning",
    bg: "bg-warning/10",
  },
};

/**
 * Compact assessment checks panel for the Overview tab.
 * Traffic light visual indicators for instant status scanning.
 */
export function ChecksSummaryPanel({ checks, onCheckClick, className }: ChecksSummaryPanelProps) {
  // Count by result type
  const counts: Record<CheckResult, number> = {
    PASS: checks.filter((c) => c.result === "PASS").length,
    FAIL: checks.filter((c) => c.result === "FAIL").length,
    INCONCLUSIVE: checks.filter((c) => c.result === "INCONCLUSIVE").length,
  };

  const total = checks.length;
  const passRate = total > 0 ? Math.round((counts.PASS / total) * 100) : 0;

  if (checks.length === 0) {
    return (
      <div className={cn("bg-card rounded-lg border border-border", className)}>
        <div className="px-4 py-3 border-b border-border bg-muted/50">
          <div className="flex items-center gap-2">
            <ClipboardCheck className="h-4 w-4 text-muted-foreground" />
            <h3 className="text-sm font-semibold text-foreground">
              Assessment Checks
            </h3>
          </div>
        </div>
        <div className="p-4 text-center">
          <p className="text-sm text-muted-foreground">No checks performed</p>
        </div>
      </div>
    );
  }

  return (
    <Tooltip.Provider delayDuration={300}>
    <div className={cn("bg-card rounded-lg border border-border overflow-hidden", className)}>
      {/* Header with visual summary */}
      <div className="px-4 py-3 border-b border-border bg-muted/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ClipboardCheck className="h-4 w-4 text-muted-foreground" />
            <h3 className="text-sm font-semibold text-foreground">
              Assessment Checks
            </h3>
          </div>
          {/* Traffic light summary */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-success" />
              <span className="text-xs font-medium text-foreground">{counts.PASS}</span>
            </div>
            {counts.FAIL > 0 && (
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-destructive" />
                <span className="text-xs font-medium text-foreground">{counts.FAIL}</span>
              </div>
            )}
            {counts.INCONCLUSIVE > 0 && (
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-warning" />
                <span className="text-xs font-medium text-foreground">{counts.INCONCLUSIVE}</span>
              </div>
            )}
          </div>
        </div>

        {/* Progress bar */}
        <div className="mt-2 h-1.5 bg-muted rounded-full overflow-hidden flex">
          {counts.PASS > 0 && (
            <div
              className="h-full bg-success transition-all"
              style={{ width: `${(counts.PASS / total) * 100}%` }}
            />
          )}
          {counts.FAIL > 0 && (
            <div
              className="h-full bg-destructive transition-all"
              style={{ width: `${(counts.FAIL / total) * 100}%` }}
            />
          )}
          {counts.INCONCLUSIVE > 0 && (
            <div
              className="h-full bg-warning transition-all"
              style={{ width: `${(counts.INCONCLUSIVE / total) * 100}%` }}
            />
          )}
        </div>
      </div>

      {/* Compact check list */}
      <div className="divide-y divide-border">
        {checks.map((check) => {
          const config = RESULT_CONFIG[check.result];
          const Icon = config.icon;

          return (
            <button
              key={check.check_number}
              onClick={() => onCheckClick?.(check.check_number)}
              className={cn(
                "w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors",
                "hover:bg-muted/50",
                check.result === "FAIL" && "bg-destructive/5"
              )}
            >
              {/* Status dot */}
              <span className={cn("w-2 h-2 rounded-full flex-shrink-0", config.dot)} />

              {/* Check info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-muted-foreground font-mono">#{check.check_number}</span>
                  <Tooltip.Root>
                    <Tooltip.Trigger asChild>
                      <span className={cn(
                        "text-sm truncate cursor-help",
                        check.result === "PASS"
                          ? "text-foreground"
                          : config.text
                      )}>
                        {check.check_name}
                      </span>
                    </Tooltip.Trigger>
                    <Tooltip.Portal>
                      <Tooltip.Content
                        side="top"
                        align="start"
                        sideOffset={5}
                        className={cn(
                          "z-50 max-w-[320px] select-none",
                          "rounded-lg border border-border",
                          "bg-popover px-3 py-2 shadow-lg",
                          "text-sm text-popover-foreground",
                          "animate-in fade-in-0 zoom-in-95"
                        )}
                      >
                        {check.details}
                        <Tooltip.Arrow className="fill-popover" />
                      </Tooltip.Content>
                    </Tooltip.Portal>
                  </Tooltip.Root>
                </div>
              </div>

              {/* Result icon */}
              <Icon className={cn("h-4 w-4 flex-shrink-0", config.text)} />
            </button>
          );
        })}
      </div>

      {/* Footer with pass rate */}
      <div className="px-4 py-2 border-t border-border bg-muted/30">
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted-foreground">
            {counts.PASS} of {total} checks passed
          </span>
          <span className={cn(
            "text-xs font-semibold",
            passRate >= 80 ? "text-success" :
            passRate >= 50 ? "text-warning" :
            "text-destructive"
          )}>
            {passRate}%
          </span>
        </div>
      </div>
    </div>
    </Tooltip.Provider>
  );
}
