import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Format a field name for display, handling namespaced fields.
 *
 * Namespaced fields (doc_type.field_name) are formatted as:
 * "field name (doc type)"
 *
 * Regular fields are formatted by replacing underscores with spaces.
 *
 * Examples:
 * - "service_history.document_date" → "document date (service history)"
 * - "cost_estimate.document_date" → "document date (cost estimate)"
 * - "vehicle_vin" → "vehicle vin"
 */
export function formatFieldName(name: string): string {
  // Check if this is a namespaced field (contains a dot)
  const dotIndex = name.indexOf(".");
  if (dotIndex > 0) {
    const docType = name.slice(0, dotIndex).replace(/_/g, " ");
    const fieldName = name.slice(dotIndex + 1).replace(/_/g, " ");
    return `${fieldName} (${docType})`;
  }
  // Regular field - just replace underscores with spaces
  return name.replace(/_/g, " ");
}
