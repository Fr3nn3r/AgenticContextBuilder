import type { AggregatedFact } from "../../types";
import { cn } from "../../lib/utils";

interface CostEstimateCardProps {
  facts: AggregatedFact[];
  onViewSource?: (
    docId: string,
    page: number | null,
    charStart: number | null,
    charEnd: number | null
  ) => void;
}

interface CostLineItem {
  label: string;
  amount: number;
  isTotal: boolean;
  factName: string;
}

// Map fact names to display labels and determine if they're totals
const COST_FIELD_CONFIG: Record<string, { label: string; isTotal: boolean; order: number }> = {
  // Line items
  parts_cost: { label: "Parts", isTotal: false, order: 1 },
  labor_cost: { label: "Labor", isTotal: false, order: 2 },
  parts_amount: { label: "Parts", isTotal: false, order: 1 },
  labor_amount: { label: "Labor", isTotal: false, order: 2 },
  materials_cost: { label: "Materials", isTotal: false, order: 3 },
  other_cost: { label: "Other", isTotal: false, order: 4 },
  discount: { label: "Discount", isTotal: false, order: 5 },
  // Tax
  vat_amount: { label: "VAT", isTotal: false, order: 10 },
  tax_amount: { label: "Tax", isTotal: false, order: 10 },
  mwst: { label: "MwSt.", isTotal: false, order: 10 },
  // Subtotals
  total_amount_excl_vat: { label: "Subtotal", isTotal: false, order: 15 },
  net_total: { label: "Subtotal", isTotal: false, order: 15 },
  // Totals
  total_amount_incl_vat: { label: "Total", isTotal: true, order: 20 },
  total_amount: { label: "Total", isTotal: true, order: 20 },
  gross_total: { label: "Total", isTotal: true, order: 20 },
  invoice_total: { label: "Total", isTotal: true, order: 20 },
};

function parseAmount(value: string | string[] | null): number | null {
  if (value === null || value === undefined) return null;
  const strValue = Array.isArray(value) ? value[0] : value;
  // Remove currency symbols, spaces, and handle European number formats
  const normalized = strValue
    .replace(/[CHF€$£\s]/gi, "")
    .replace(/'/g, "") // Swiss thousand separator
    .replace(/,(?=\d{3})/g, "") // Remove thousand separators
    .replace(/,/g, "."); // Convert decimal comma to point
  const num = parseFloat(normalized);
  return isNaN(num) ? null : num;
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("de-CH", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

export function CostEstimateCard({ facts, onViewSource }: CostEstimateCardProps) {
  // Parse cost facts into line items
  const lineItems: CostLineItem[] = [];

  for (const fact of facts) {
    const config = COST_FIELD_CONFIG[fact.name];
    if (!config) continue;

    const amount = parseAmount(fact.value);
    if (amount === null) continue;

    lineItems.push({
      label: config.label,
      amount,
      isTotal: config.isTotal,
      factName: fact.name,
    });
  }

  // Sort by order
  lineItems.sort((a, b) => {
    const orderA = COST_FIELD_CONFIG[a.factName]?.order ?? 99;
    const orderB = COST_FIELD_CONFIG[b.factName]?.order ?? 99;
    return orderA - orderB;
  });

  // Separate totals from line items
  const regularItems = lineItems.filter((item) => !item.isTotal);
  const totalItems = lineItems.filter((item) => item.isTotal);
  const grandTotal = totalItems[0]; // Use first total found

  // Handle click on a fact
  const handleClick = (factName: string) => {
    if (!onViewSource) return;
    const fact = facts.find((f) => f.name === factName);
    if (fact?.selected_from) {
      onViewSource(
        fact.selected_from.doc_id,
        fact.selected_from.page,
        fact.selected_from.char_start,
        fact.selected_from.char_end
      );
    }
  };

  if (lineItems.length === 0) {
    return null;
  }

  return (
    <div className="bg-card rounded-lg border border-border border-l-4 border-l-primary shadow-sm hover:shadow-md transition-shadow">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border">
        <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
          Cost Estimate
        </h3>
      </div>

      {/* Content */}
      <div className="p-4">
        {/* Line items */}
        <div className="space-y-2">
          {regularItems.map((item) => (
            <div
              key={item.factName}
              className={cn(
                "flex justify-between items-center text-sm",
                onViewSource && "cursor-pointer hover:bg-muted/30 -mx-2 px-2 py-1 rounded transition-colors"
              )}
              onClick={() => handleClick(item.factName)}
            >
              <span className="text-muted-foreground">{item.label}</span>
              <span className="font-medium tabular-nums text-right">
                {formatCurrency(item.amount)}
              </span>
            </div>
          ))}
        </div>

        {/* Total row */}
        {grandTotal && (
          <>
            <div className="border-t border-border my-3" />
            <div
              className={cn(
                "flex justify-between items-center bg-muted/50 -mx-4 px-4 py-3 rounded-b-lg",
                onViewSource && "cursor-pointer hover:bg-muted/70 transition-colors"
              )}
              onClick={() => handleClick(grandTotal.factName)}
            >
              <span className="text-sm font-semibold text-foreground">TOTAL</span>
              <div className="text-right">
                <span className="text-xs text-muted-foreground mr-2">CHF</span>
                <span className="text-lg font-bold tabular-nums text-foreground">
                  {formatCurrency(grandTotal.amount)}
                </span>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
