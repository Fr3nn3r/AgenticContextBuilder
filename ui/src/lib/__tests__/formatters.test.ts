import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  formatDocType,
  formatFieldName,
  formatTimestamp,
  formatDate,
  formatTime,
  formatRelativeTime,
  formatPercent,
  formatNumber,
  formatDuration,
  truncateBatchId,
  formatBatchOption,
} from "../formatters";

// ============================================================================
// formatDocType
// ============================================================================

describe("formatDocType", () => {
  it("returns canonical name for known doc types", () => {
    expect(formatDocType("fnol_form")).toBe("FNOL Form");
    expect(formatDocType("police_report")).toBe("Police Report");
    expect(formatDocType("insurance_policy")).toBe("Insurance Policy");
    expect(formatDocType("id_document")).toBe("ID Document");
    expect(formatDocType("vehicle_registration")).toBe("Vehicle Registration");
    expect(formatDocType("medical_report")).toBe("Medical Report");
    expect(formatDocType("invoice")).toBe("Invoice");
  });

  it("converts snake_case to Title Case for unknown types", () => {
    expect(formatDocType("custom_document_type")).toBe("Custom Document Type");
    expect(formatDocType("some_other_type")).toBe("Some Other Type");
  });

  it('returns "Unknown" for null or undefined', () => {
    expect(formatDocType(null)).toBe("Unknown");
    expect(formatDocType(undefined)).toBe("Unknown");
    expect(formatDocType("")).toBe("Unknown");
  });

  it("handles case-insensitive lookup", () => {
    expect(formatDocType("FNOL_FORM")).toBe("FNOL Form");
    expect(formatDocType("Police_Report")).toBe("Police Report");
    expect(formatDocType("INSURANCE_POLICY")).toBe("Insurance Policy");
  });
});

// ============================================================================
// formatFieldName
// ============================================================================

describe("formatFieldName", () => {
  it("returns canonical name for known fields", () => {
    expect(formatFieldName("policy_number")).toBe("Policy Number");
    expect(formatFieldName("claim_number")).toBe("Claim Number");
    expect(formatFieldName("claimant_name")).toBe("Claimant Name");
    expect(formatFieldName("incident_date")).toBe("Incident Date");
    expect(formatFieldName("vehicle_plate")).toBe("Vehicle Plate");
    expect(formatFieldName("loss_description")).toBe("Loss Description");
  });

  it("converts snake_case to Title Case for unknown fields", () => {
    expect(formatFieldName("custom_field_name")).toBe("Custom Field Name");
    expect(formatFieldName("some_value")).toBe("Some Value");
  });

  it('returns "Unknown" for null or undefined', () => {
    expect(formatFieldName(null)).toBe("Unknown");
    expect(formatFieldName(undefined)).toBe("Unknown");
    expect(formatFieldName("")).toBe("Unknown");
  });

  it("handles case-insensitive lookup", () => {
    expect(formatFieldName("POLICY_NUMBER")).toBe("Policy Number");
    expect(formatFieldName("Claim_Number")).toBe("Claim Number");
    expect(formatFieldName("INCIDENT_DATE")).toBe("Incident Date");
  });
});

// ============================================================================
// formatTimestamp
// ============================================================================

describe("formatTimestamp", () => {
  it("formats valid ISO timestamp to locale string", () => {
    const result = formatTimestamp("2025-01-08T19:31:31Z");
    // Result is locale-dependent, so just verify it's not the fallback
    expect(result).not.toBe("Unknown");
    expect(result).toContain("2025");
  });

  it('returns "Unknown" for null or undefined', () => {
    expect(formatTimestamp(null)).toBe("Unknown");
    expect(formatTimestamp(undefined)).toBe("Unknown");
  });

  it("returns original string for invalid date", () => {
    expect(formatTimestamp("not-a-date")).toBe("Invalid Date");
  });
});

// ============================================================================
// formatDate
// ============================================================================

describe("formatDate", () => {
  it("formats valid timestamp to date only", () => {
    const result = formatDate("2025-01-08T19:31:31Z");
    expect(result).not.toBe("Unknown");
    // Should contain year but not time components like "PM"
    expect(result).toContain("2025");
  });

  it('returns "Unknown" for null or undefined', () => {
    expect(formatDate(null)).toBe("Unknown");
    expect(formatDate(undefined)).toBe("Unknown");
  });
});

// ============================================================================
// formatTime
// ============================================================================

describe("formatTime", () => {
  it("formats valid timestamp to time only", () => {
    const result = formatTime("2025-01-08T19:31:31Z");
    expect(result).not.toBe("");
    // Should be a time string (locale-dependent)
    expect(result.length).toBeGreaterThan(0);
  });

  it("returns empty string for null or undefined", () => {
    expect(formatTime(null)).toBe("");
    expect(formatTime(undefined)).toBe("");
  });
});

// ============================================================================
// formatRelativeTime
// ============================================================================

describe("formatRelativeTime", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-01-13T12:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('returns "Just now" for timestamps < 1 minute ago', () => {
    expect(formatRelativeTime("2026-01-13T11:59:30Z")).toBe("Just now");
    expect(formatRelativeTime("2026-01-13T11:59:59Z")).toBe("Just now");
  });

  it('returns "Xm ago" for timestamps < 1 hour ago', () => {
    expect(formatRelativeTime("2026-01-13T11:55:00Z")).toBe("5m ago");
    expect(formatRelativeTime("2026-01-13T11:30:00Z")).toBe("30m ago");
    expect(formatRelativeTime("2026-01-13T11:01:00Z")).toBe("59m ago");
  });

  it('returns "Xh ago" for timestamps < 24 hours ago', () => {
    expect(formatRelativeTime("2026-01-13T10:00:00Z")).toBe("2h ago");
    expect(formatRelativeTime("2026-01-13T00:00:00Z")).toBe("12h ago");
    expect(formatRelativeTime("2026-01-12T13:00:00Z")).toBe("23h ago");
  });

  it('returns "Yesterday" for timestamps 1 day ago', () => {
    expect(formatRelativeTime("2026-01-12T12:00:00Z")).toBe("Yesterday");
  });

  it('returns "Xd ago" for timestamps < 7 days ago', () => {
    expect(formatRelativeTime("2026-01-11T12:00:00Z")).toBe("2d ago");
    expect(formatRelativeTime("2026-01-08T12:00:00Z")).toBe("5d ago");
    expect(formatRelativeTime("2026-01-07T12:00:00Z")).toBe("6d ago");
  });

  it("returns formatted date for timestamps >= 7 days ago", () => {
    const result = formatRelativeTime("2026-01-01T12:00:00Z");
    // Should fall back to formatDate, containing the year
    expect(result).toContain("2026");
  });

  it('returns "Unknown" for null or undefined', () => {
    expect(formatRelativeTime(null)).toBe("Unknown");
    expect(formatRelativeTime(undefined)).toBe("Unknown");
  });
});

// ============================================================================
// formatPercent
// ============================================================================

describe("formatPercent", () => {
  it("formats decimal value (0-1) as percentage", () => {
    expect(formatPercent(0.95)).toBe("95%");
    expect(formatPercent(0.5)).toBe("50%");
    expect(formatPercent(0.0)).toBe("0%");
    expect(formatPercent(1.0)).toBe("100%");
  });

  it("formats whole number (>1) as percentage", () => {
    expect(formatPercent(95)).toBe("95%");
    expect(formatPercent(50)).toBe("50%");
    expect(formatPercent(100)).toBe("100%");
  });

  it("respects decimals parameter", () => {
    expect(formatPercent(0.956, 1)).toBe("95.6%");
    expect(formatPercent(0.9567, 2)).toBe("95.67%");
    expect(formatPercent(95.67, 1)).toBe("95.7%");
  });
});

// ============================================================================
// formatNumber
// ============================================================================

describe("formatNumber", () => {
  it("formats number with locale separators", () => {
    // Results are locale-dependent, but should format large numbers
    const result = formatNumber(1234567);
    expect(result).not.toBe("1234567"); // Should have separators
    expect(result).toContain("1");
    expect(result).toContain("234");
  });

  it("handles small numbers without separators", () => {
    expect(formatNumber(123)).toBe("123");
  });
});

// ============================================================================
// formatDuration
// ============================================================================

describe("formatDuration", () => {
  it("formats seconds < 60 with decimal", () => {
    expect(formatDuration(13.4)).toBe("13.4s");
    expect(formatDuration(0.5)).toBe("0.5s");
    expect(formatDuration(59.9)).toBe("59.9s");
  });

  it("formats >= 60 seconds as minutes and seconds", () => {
    expect(formatDuration(125)).toBe("2m 5s");
    expect(formatDuration(90)).toBe("1m 30s");
    expect(formatDuration(61)).toBe("1m 1s");
  });

  it("omits seconds when zero remainder", () => {
    expect(formatDuration(120)).toBe("2m");
    expect(formatDuration(60)).toBe("1m");
    expect(formatDuration(180)).toBe("3m");
  });
});

// ============================================================================
// truncateBatchId
// ============================================================================

describe("truncateBatchId", () => {
  it('removes "batch_" prefix', () => {
    // "20260108_173118_5e32c71" is 23 chars, maxLength defaults to 18
    expect(truncateBatchId("batch_20260108_173118_5e32c71")).toBe(
      "20260108_173118_5e..."
    );
  });

  it('removes "run_" prefix', () => {
    // "20260108_173118_5e32c71" is 23 chars, maxLength defaults to 18
    expect(truncateBatchId("run_20260108_173118_5e32c71")).toBe(
      "20260108_173118_5e..."
    );
  });

  it("truncates to maxLength and adds ellipsis", () => {
    expect(truncateBatchId("very_long_batch_id_that_exceeds_limit")).toBe(
      "very_long_batch_id..."
    );
    expect(truncateBatchId("short_id_here", 10)).toBe("short_id_h...");
  });

  it("returns unchanged if under maxLength", () => {
    expect(truncateBatchId("short")).toBe("short");
    expect(truncateBatchId("batch_short")).toBe("short");
  });
});

// ============================================================================
// formatBatchOption
// ============================================================================

describe("formatBatchOption", () => {
  it("formats with docs count only", () => {
    expect(formatBatchOption("batch_20260108_173118", 3)).toBe(
      "20260108_173118 (3 docs)"
    );
  });

  it("formats with both docs and claims counts", () => {
    expect(formatBatchOption("batch_20260108_173118", 5, 2)).toBe(
      "20260108_173118 (5 docs, 2 claims)"
    );
  });

  it("returns just truncated ID when no counts provided", () => {
    expect(formatBatchOption("batch_20260108_173118")).toBe("20260108_173118");
  });

  it("formats with claims count only", () => {
    expect(formatBatchOption("batch_20260108_173118", undefined, 2)).toBe(
      "20260108_173118 (2 claims)"
    );
  });
});
