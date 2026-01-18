import * as Tooltip from "@radix-ui/react-tooltip";
import { terminology, type TermKey } from "../../lib/terminology";
import { cn } from "../../lib/utils";

interface HelpTermProps {
  /** The terminology key to look up */
  term: TermKey;
  /** Custom content to display (defaults to the term's display name) */
  children?: React.ReactNode;
  /** Additional classes for the trigger element */
  className?: string;
  /** Whether to show the dotted underline (default: true) */
  showUnderline?: boolean;
  /** Tooltip placement */
  side?: "top" | "right" | "bottom" | "left";
  /** Tooltip alignment */
  align?: "start" | "center" | "end";
}

/**
 * Contextual help component that displays terminology definitions on hover.
 * Wraps text with a subtle dotted underline and shows a tooltip with the definition.
 *
 * @example
 * <HelpTerm term="qualityGate">Quality Gate</HelpTerm>
 * <HelpTerm term="confidence" /> // Uses term's display name
 */
export function HelpTerm({
  term,
  children,
  className,
  showUnderline = true,
  side = "top",
  align = "center",
}: HelpTermProps) {
  const definition = terminology[term];

  if (!definition) {
    console.warn(`HelpTerm: Unknown term "${term}"`);
    return <span className={className}>{children}</span>;
  }

  return (
    <Tooltip.Root delayDuration={300}>
      <Tooltip.Trigger asChild>
        <span
          className={cn(
            "cursor-help transition-colors",
            showUnderline && [
              "border-b border-dotted border-muted-foreground/40",
              "hover:border-primary hover:text-primary",
            ],
            className
          )}
        >
          {children ?? definition.term}
        </span>
      </Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content
          side={side}
          align={align}
          sideOffset={6}
          className={cn(
            // Base styles
            "z-50 max-w-[280px] select-none",
            // Card-like appearance matching existing design system
            "rounded-lg border border-border bg-popover px-3.5 py-3 shadow-lg",
            // Accent border on left
            "border-l-2 border-l-primary",
            // Animation
            "animate-in fade-in-0 zoom-in-95",
            "data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95",
            "data-[side=bottom]:slide-in-from-top-2",
            "data-[side=left]:slide-in-from-right-2",
            "data-[side=right]:slide-in-from-left-2",
            "data-[side=top]:slide-in-from-bottom-2"
          )}
        >
          {/* Term title */}
          <div className="font-semibold text-[13px] text-foreground mb-1">
            {definition.term}
          </div>
          {/* Definition body */}
          <div className="text-[12px] leading-relaxed text-muted-foreground">
            {definition.definition}
          </div>
          {/* Arrow */}
          <Tooltip.Arrow className="fill-popover" />
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
}

/**
 * Standalone help icon that shows a tooltip on hover.
 * Use when you want an info icon next to text rather than wrapping the text itself.
 *
 * @example
 * <span>Evidence Rate <HelpIcon term="evidenceRate" /></span>
 */
export function HelpIcon({
  term,
  className,
  side = "top",
  align = "center",
}: Omit<HelpTermProps, "children" | "showUnderline">) {
  const definition = terminology[term];

  if (!definition) {
    console.warn(`HelpIcon: Unknown term "${term}"`);
    return null;
  }

  return (
    <Tooltip.Root delayDuration={300}>
      <Tooltip.Trigger asChild>
        <span
          className={cn(
            "inline-flex items-center justify-center",
            "w-3.5 h-3.5 ml-1 rounded-full",
            "text-[9px] font-medium",
            "bg-muted text-muted-foreground",
            "cursor-help transition-colors",
            "hover:bg-primary/20 hover:text-primary",
            className
          )}
        >
          ?
        </span>
      </Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content
          side={side}
          align={align}
          sideOffset={6}
          className={cn(
            "z-50 max-w-[280px] select-none",
            "rounded-lg border border-border bg-popover px-3.5 py-3 shadow-lg",
            "border-l-2 border-l-primary",
            "animate-in fade-in-0 zoom-in-95",
            "data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95",
            "data-[side=bottom]:slide-in-from-top-2",
            "data-[side=left]:slide-in-from-right-2",
            "data-[side=right]:slide-in-from-left-2",
            "data-[side=top]:slide-in-from-bottom-2"
          )}
        >
          <div className="font-semibold text-[13px] text-foreground mb-1">
            {definition.term}
          </div>
          <div className="text-[12px] leading-relaxed text-muted-foreground">
            {definition.definition}
          </div>
          <Tooltip.Arrow className="fill-popover" />
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
}

/**
 * Provider component that wraps the app to enable shared tooltip settings.
 * Add this once at the app root level.
 */
export function HelpTooltipProvider({ children }: { children: React.ReactNode }) {
  return (
    <Tooltip.Provider delayDuration={300} skipDelayDuration={100}>
      {children}
    </Tooltip.Provider>
  );
}
