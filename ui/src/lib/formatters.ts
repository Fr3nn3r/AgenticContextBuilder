/**
 * Shared formatting utilities for consistent display across the UI.
 */

// ============================================================================
// Document Type Formatting
// ============================================================================

/**
 * Canonical display names for document types.
 * Uses Title Case consistently.
 */
const DOC_TYPE_DISPLAY_NAMES: Record<string, string> = {
  fnol_form: "FNOL Form",
  loss_notice: "Loss Notice",
  police_report: "Police Report",
  insurance_policy: "Insurance Policy",
  id_document: "ID Document",
  vehicle_registration: "Vehicle Registration",
  certificate: "Certificate",
  medical_report: "Medical Report",
  travel_itinerary: "Travel Itinerary",
  customer_comm: "Customer Communication",
  supporting_document: "Supporting Document",
  invoice: "Invoice",
};

/**
 * Formats a document type for display.
 * Converts snake_case to Title Case and applies canonical names.
 *
 * @example
 * formatDocType("fnol_form") // "FNOL Form"
 * formatDocType("police_report") // "Police Report"
 * formatDocType("unknown_type") // "Unknown Type"
 */
export function formatDocType(docType: string | null | undefined): string {
  if (!docType) return "Unknown";

  // Check for canonical name first
  const canonical = DOC_TYPE_DISPLAY_NAMES[docType.toLowerCase()];
  if (canonical) return canonical;

  // Fall back to Title Case conversion
  return docType
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

// ============================================================================
// Field Name Formatting
// ============================================================================

/**
 * Canonical display names for common field names.
 */
const FIELD_DISPLAY_NAMES: Record<string, string> = {
  incident_date: "Incident Date",
  event_date: "Event Date",
  incident_location: "Incident Location",
  event_location: "Event Location",
  policy_number: "Policy Number",
  claim_number: "Claim Number",
  claimant_name: "Claimant Name",
  claimant_email: "Claimant Email",
  claimant_phone: "Claimant Phone",
  vehicle_plate: "Vehicle Plate",
  vehicle_make: "Vehicle Make",
  vehicle_model: "Vehicle Model",
  vehicle_year: "Vehicle Year",
  loss_description: "Loss Description",
  loss_type: "Loss Type",
  reported_date: "Report Date",
  report_date: "Report Date",
  report_number: "Report Number",
  officer_name: "Officer Name",
  badge_number: "Badge Number",
  location: "Location",
  coverage_start: "Coverage Start",
  coverage_end: "Coverage End",
  total_amount_claimed: "Total Amount Claimed",
  trip_start_date: "Trip Start Date",
  trip_end_date: "Trip End Date",
  destination: "Destination",
  expense_items: "Expense Items",
};

/**
 * Formats a field name for display.
 * Converts snake_case to Title Case and applies canonical names.
 *
 * @example
 * formatFieldName("policy_number") // "Policy Number"
 * formatFieldName("claim_number") // "Claim Number"
 */
export function formatFieldName(fieldName: string | null | undefined): string {
  if (!fieldName) return "Unknown";

  // Check for canonical name first
  const canonical = FIELD_DISPLAY_NAMES[fieldName.toLowerCase()];
  if (canonical) return canonical;

  // Fall back to Title Case conversion
  return fieldName
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

// ============================================================================
// Timestamp Formatting
// ============================================================================

/**
 * Formats a timestamp for display.
 *
 * @example
 * formatTimestamp("2025-01-08T19:31:31Z") // "1/8/2025, 7:31:31 PM"
 */
export function formatTimestamp(ts: string | null | undefined): string {
  if (!ts) return "Unknown";
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

/**
 * Formats a timestamp as date only.
 *
 * @example
 * formatDate("2025-01-08T19:31:31Z") // "1/8/2025"
 */
export function formatDate(ts: string | null | undefined): string {
  if (!ts) return "Unknown";
  try {
    return new Date(ts).toLocaleDateString();
  } catch {
    return ts;
  }
}

/**
 * Formats a timestamp as time only.
 *
 * @example
 * formatTime("2025-01-08T19:31:31Z") // "7:31:31 PM"
 */
export function formatTime(ts: string | null | undefined): string {
  if (!ts) return "";
  try {
    return new Date(ts).toLocaleTimeString();
  } catch {
    return ts;
  }
}

/**
 * Formats a timestamp as relative time (e.g., "2 hours ago").
 */
export function formatRelativeTime(ts: string | null | undefined): string {
  if (!ts) return "Unknown";
  try {
    const date = new Date(ts);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / (1000 * 60));
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays === 1) return "Yesterday";
    if (diffDays < 7) return `${diffDays}d ago`;
    return formatDate(ts);
  } catch {
    return ts;
  }
}

// ============================================================================
// Number Formatting
// ============================================================================

/**
 * Formats a percentage value.
 *
 * @example
 * formatPercent(0.95) // "95%"
 * formatPercent(95) // "95%"
 */
export function formatPercent(value: number, decimals = 0): string {
  // Handle values that are already percentages (0-100) vs decimals (0-1)
  const pct = value > 1 ? value : value * 100;
  return `${pct.toFixed(decimals)}%`;
}

/**
 * Formats a number with thousand separators.
 *
 * @example
 * formatNumber(1234567) // "1,234,567"
 */
export function formatNumber(value: number): string {
  return value.toLocaleString();
}

/**
 * Formats a duration in seconds to human readable format.
 *
 * @example
 * formatDuration(125) // "2m 5s"
 * formatDuration(13.4) // "13.4s"
 */
export function formatDuration(seconds: number): string {
  if (seconds < 60) {
    return `${seconds.toFixed(1)}s`;
  }
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
}

// ============================================================================
// Run ID Formatting
// ============================================================================

/**
 * Truncates a run ID for display while keeping it recognizable.
 *
 * @example
 * truncateRunId("run_20260108_173118_5e32c71") // "20260108_173118..."
 */
export function truncateRunId(runId: string, maxLength = 18): string {
  // Remove "run_" prefix if present
  const cleanId = runId.startsWith("run_") ? runId.slice(4) : runId;

  if (cleanId.length <= maxLength) return cleanId;
  return cleanId.slice(0, maxLength) + "...";
}

/**
 * Formats a run ID with optional metadata for display in selectors.
 *
 * @example
 * formatRunOption("run_20260108_173118_5e32c71", true, 3) // "20260108_173118... (Latest, 3 docs)"
 */
export function formatRunOption(
  runId: string,
  isLatest = false,
  docsCount?: number,
  claimsCount?: number
): string {
  const truncated = truncateRunId(runId);
  const parts: string[] = [];

  if (isLatest) parts.push("Latest");
  if (docsCount !== undefined) parts.push(`${docsCount} docs`);
  if (claimsCount !== undefined) parts.push(`${claimsCount} claims`);

  if (parts.length === 0) return truncated;
  return `${truncated} (${parts.join(", ")})`;
}
