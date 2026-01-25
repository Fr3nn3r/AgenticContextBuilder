import { useState, useMemo } from "react";
import { Check, Minus, RotateCcw, DollarSign } from "lucide-react";
import type { AggregatedFact } from "../../types";
import { cn } from "../../lib/utils";

interface CostLedgerProps {
  facts: AggregatedFact[];
  onViewSource?: (
    docId: string,
    page: number | null,
    charStart: number | null,
    charEnd: number | null
  ) => void;
  onApprovedAmountChange?: (amount: number) => void;
}

interface LineItem {
  id: string;
  description: string;
  partNumber?: string;
  quantity: number;
  unitPrice: number;
  total: number;
  factName: string;
  isApproved: boolean;
}

// Parse currency amount from various formats
function parseAmount(value: string | string[] | null): number | null {
  if (value === null || value === undefined) return null;
  const strValue = Array.isArray(value) ? value[0] : value;
  const normalized = strValue
    .replace(/[CHF€$£\s]/gi, "")
    .replace(/'/g, "")
    .replace(/,(?=\d{3})/g, "")
    .replace(/,/g, ".");
  const num = parseFloat(normalized);
  return isNaN(num) ? null : num;
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("de-CH", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

// Map fact names to display config
const COST_ITEMS: Record<string, { label: string; order: number; isLineItem: boolean }> = {
  // Line items
  parts_cost: { label: "Parts & Components", order: 1, isLineItem: true },
  parts_amount: { label: "Parts & Components", order: 1, isLineItem: true },
  labor_cost: { label: "Labor", order: 2, isLineItem: true },
  labor_amount: { label: "Labor", order: 2, isLineItem: true },
  materials_cost: { label: "Materials", order: 3, isLineItem: true },
  other_cost: { label: "Other Charges", order: 4, isLineItem: true },
  diagnostic_fee: { label: "Diagnostic Fee", order: 5, isLineItem: true },
  // Adjustments
  discount: { label: "Discount", order: 10, isLineItem: true },
  adjustment: { label: "Adjustment", order: 11, isLineItem: true },
  // Tax
  vat_amount: { label: "VAT (7.7%)", order: 20, isLineItem: false },
  tax_amount: { label: "Tax", order: 20, isLineItem: false },
  mwst: { label: "MwSt. (7.7%)", order: 20, isLineItem: false },
  // Subtotals (not line items)
  total_amount_excl_vat: { label: "Subtotal", order: 25, isLineItem: false },
  net_total: { label: "Net Total", order: 25, isLineItem: false },
  // Grand total
  total_amount_incl_vat: { label: "GRAND TOTAL", order: 30, isLineItem: false },
  total_amount: { label: "GRAND TOTAL", order: 30, isLineItem: false },
  gross_total: { label: "GRAND TOTAL", order: 30, isLineItem: false },
  invoice_total: { label: "GRAND TOTAL", order: 30, isLineItem: false },
};

// Toggle switch component
function ApprovalToggle({
  isApproved,
  onToggle,
  disabled
}: {
  isApproved: boolean;
  onToggle: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      onClick={(e) => {
        e.stopPropagation();
        onToggle();
      }}
      disabled={disabled}
      className={cn(
        "w-7 h-4 rounded-full transition-all relative flex-shrink-0",
        "focus:outline-none focus:ring-2 focus:ring-offset-1",
        isApproved
          ? "bg-emerald-500 focus:ring-emerald-400"
          : "bg-slate-300 dark:bg-slate-600 focus:ring-slate-400",
        disabled && "opacity-50 cursor-not-allowed"
      )}
    >
      <span
        className={cn(
          "absolute top-0.5 w-3 h-3 rounded-full bg-white shadow-sm transition-transform",
          isApproved ? "translate-x-3.5" : "translate-x-0.5"
        )}
      />
    </button>
  );
}

// Line item row
function LedgerRow({
  item,
  onToggle,
  onClick,
  showToggle = true
}: {
  item: LineItem;
  onToggle: () => void;
  onClick?: () => void;
  showToggle?: boolean;
}) {
  const isDiscount = item.description.toLowerCase().includes("discount");

  return (
    <div
      className={cn(
        "grid grid-cols-[1fr,auto,auto] gap-3 items-center px-3 py-2 border-b border-slate-100 dark:border-slate-800 transition-all",
        "hover:bg-slate-50 dark:hover:bg-slate-800/50",
        !item.isApproved && "opacity-50 bg-slate-50 dark:bg-slate-900/50",
        onClick && "cursor-pointer"
      )}
      onClick={onClick}
    >
      {/* Description */}
      <div className="min-w-0">
        <span className={cn(
          "text-sm truncate block",
          item.isApproved
            ? "text-slate-700 dark:text-slate-200"
            : "text-slate-500 dark:text-slate-500 line-through"
        )}>
          {item.description}
        </span>
        {item.partNumber && (
          <span className="text-xs text-slate-400 font-mono">
            #{item.partNumber}
          </span>
        )}
      </div>

      {/* Amount */}
      <div className={cn(
        "text-right font-mono tabular-nums text-sm font-medium",
        isDiscount
          ? "text-red-600 dark:text-red-400"
          : item.isApproved
            ? "text-slate-700 dark:text-slate-200"
            : "text-slate-400 line-through"
      )}>
        {isDiscount && "-"}{formatCurrency(Math.abs(item.total))}
      </div>

      {/* Toggle */}
      {showToggle && (
        <ApprovalToggle isApproved={item.isApproved} onToggle={onToggle} />
      )}
    </div>
  );
}

export function CostLedger({ facts, onViewSource, onApprovedAmountChange }: CostLedgerProps) {
  // Build line items from facts
  const initialItems = useMemo(() => {
    const items: LineItem[] = [];

    for (const fact of facts) {
      const config = COST_ITEMS[fact.name];
      if (!config || !config.isLineItem) continue;

      const amount = parseAmount(fact.value);
      if (amount === null) continue;

      items.push({
        id: fact.name,
        description: config.label,
        quantity: 1,
        unitPrice: amount,
        total: amount,
        factName: fact.name,
        isApproved: true
      });
    }

    // Sort by order
    items.sort((a, b) => {
      const orderA = COST_ITEMS[a.factName]?.order ?? 99;
      const orderB = COST_ITEMS[b.factName]?.order ?? 99;
      return orderA - orderB;
    });

    return items;
  }, [facts]);

  const [lineItems, setLineItems] = useState<LineItem[]>(initialItems);

  // Get tax and totals
  const taxFact = facts.find(f => ["vat_amount", "tax_amount", "mwst"].includes(f.name));
  const subtotalFact = facts.find(f => ["total_amount_excl_vat", "net_total"].includes(f.name));
  const grandTotalFact = facts.find(f =>
    ["total_amount_incl_vat", "total_amount", "gross_total", "invoice_total"].includes(f.name)
  );

  const taxAmount = parseAmount(taxFact?.value ?? null) ?? 0;
  const originalTotal = parseAmount(grandTotalFact?.value ?? null) ?? 0;

  // Calculate approved total
  const approvedSubtotal = lineItems
    .filter(item => item.isApproved)
    .reduce((sum, item) => {
      const isDiscount = item.description.toLowerCase().includes("discount");
      return sum + (isDiscount ? -Math.abs(item.total) : item.total);
    }, 0);

  // Recalculate tax proportionally
  const originalSubtotal = parseAmount(subtotalFact?.value ?? null) ?? (originalTotal - taxAmount);
  const taxRate = originalSubtotal > 0 ? taxAmount / originalSubtotal : 0.077;
  const approvedTax = approvedSubtotal * taxRate;
  const approvedTotal = approvedSubtotal + approvedTax;

  const allApproved = lineItems.every(item => item.isApproved);
  const noneApproved = lineItems.every(item => !item.isApproved);

  // Toggle item approval
  const toggleItem = (id: string) => {
    setLineItems(prev => {
      const updated = prev.map(item =>
        item.id === id ? { ...item, isApproved: !item.isApproved } : item
      );
      const newTotal = updated
        .filter(item => item.isApproved)
        .reduce((sum, item) => {
          const isDiscount = item.description.toLowerCase().includes("discount");
          return sum + (isDiscount ? -Math.abs(item.total) : item.total);
        }, 0);
      const newTax = newTotal * taxRate;
      onApprovedAmountChange?.(newTotal + newTax);
      return updated;
    });
  };

  // Reset all to approved
  const resetAll = () => {
    setLineItems(prev => prev.map(item => ({ ...item, isApproved: true })));
    onApprovedAmountChange?.(originalTotal);
  };

  // Handle source click
  const handleFactClick = (factName: string) => {
    if (!onViewSource) return;
    const fact = facts.find(f => f.name === factName);
    if (fact?.selected_from) {
      onViewSource(
        fact.selected_from.doc_id,
        fact.selected_from.page,
        fact.selected_from.char_start,
        fact.selected_from.char_end
      );
    }
  };

  if (lineItems.length === 0 && !grandTotalFact) {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700 p-4">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-2">
          Cost Estimate
        </h3>
        <p className="text-sm text-slate-500">No cost data available</p>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-slate-900 rounded-lg border-2 border-slate-200 dark:border-slate-700 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <DollarSign className="h-4 w-4 text-slate-500" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
            Cost Ledger
          </h3>
        </div>

        {!allApproved && (
          <button
            onClick={resetAll}
            className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 transition-colors"
          >
            <RotateCcw className="h-3 w-3" />
            Reset
          </button>
        )}
      </div>

      {/* Line items */}
      <div className="divide-y divide-slate-100 dark:divide-slate-800">
        {/* Column headers */}
        <div className="grid grid-cols-[1fr,auto,auto] gap-3 px-3 py-1.5 bg-slate-50 dark:bg-slate-800/30 text-[10px] uppercase tracking-wider text-slate-500">
          <span>Description</span>
          <span className="text-right">Amount</span>
          <span className="w-7 text-center">OK</span>
        </div>

        {lineItems.map(item => (
          <LedgerRow
            key={item.id}
            item={item}
            onToggle={() => toggleItem(item.id)}
            onClick={onViewSource ? () => handleFactClick(item.factName) : undefined}
          />
        ))}

        {/* Tax row */}
        {taxAmount > 0 && (
          <div className="grid grid-cols-[1fr,auto,auto] gap-3 items-center px-3 py-2 bg-slate-50/50 dark:bg-slate-800/30">
            <span className="text-sm text-slate-500 dark:text-slate-400">
              VAT ({(taxRate * 100).toFixed(1)}%)
            </span>
            <span className="text-right font-mono tabular-nums text-sm text-slate-500 dark:text-slate-400">
              {formatCurrency(approvedTax)}
            </span>
            <div className="w-7" />
          </div>
        )}
      </div>

      {/* Total */}
      <div className={cn(
        "px-4 py-3 flex items-center justify-between",
        "bg-gradient-to-r from-slate-100 to-slate-50 dark:from-slate-800 dark:to-slate-800/50",
        "border-t-2 border-slate-200 dark:border-slate-700"
      )}>
        <div className="flex items-center gap-2">
          {allApproved ? (
            <Check className="h-4 w-4 text-emerald-500" />
          ) : noneApproved ? (
            <Minus className="h-4 w-4 text-slate-400" />
          ) : (
            <div className="w-4 h-4 rounded-full border-2 border-amber-400 bg-amber-100" />
          )}
          <span className="text-sm font-bold uppercase tracking-wide text-slate-700 dark:text-slate-200">
            {allApproved ? "Approved Total" : "Adjusted Total"}
          </span>
        </div>

        <div className="text-right">
          <div className="flex items-baseline gap-2">
            <span className="text-xs text-slate-500 dark:text-slate-400">CHF</span>
            <span className={cn(
              "text-xl font-bold font-mono tabular-nums",
              allApproved
                ? "text-slate-800 dark:text-slate-100"
                : "text-amber-600 dark:text-amber-400"
            )}>
              {formatCurrency(approvedTotal)}
            </span>
          </div>

          {!allApproved && (
            <div className="flex items-center justify-end gap-1 text-xs text-slate-500">
              <span className="line-through">{formatCurrency(originalTotal)}</span>
              <span className="text-red-500">
                (-{formatCurrency(originalTotal - approvedTotal)})
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
