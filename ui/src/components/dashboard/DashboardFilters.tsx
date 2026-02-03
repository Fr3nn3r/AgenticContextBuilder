import { useMemo } from "react";
import type { DashboardClaim } from "../../types";

export interface DashboardFilterValues {
  search: string;
  decision: string;
  gtDecision: string;
  matchStatus: string;
  resultCode: string;
  dateFrom: string;
  dateTo: string;
}

interface DashboardFiltersProps {
  filters: DashboardFilterValues;
  onChange: (filters: DashboardFilterValues) => void;
  claims: DashboardClaim[];
}

export function DashboardFilters({ filters, onChange, claims }: DashboardFiltersProps) {
  const resultCodes = useMemo(() => {
    const codes = new Set<string>();
    for (const c of claims) {
      if (c.result_code) codes.add(c.result_code);
    }
    return Array.from(codes).sort();
  }, [claims]);

  const update = (key: keyof DashboardFilterValues, value: string) => {
    onChange({ ...filters, [key]: value });
  };

  const selectClass =
    "h-9 rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 text-sm text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-primary/40";
  const inputClass =
    "h-9 rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 text-sm text-slate-700 dark:text-slate-200 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-primary/40";

  return (
    <div className="flex flex-wrap items-center gap-3">
      <input
        type="date"
        value={filters.dateFrom}
        onChange={(e) => update("dateFrom", e.target.value)}
        className={inputClass}
        title="Date from"
      />
      <input
        type="date"
        value={filters.dateTo}
        onChange={(e) => update("dateTo", e.target.value)}
        className={inputClass}
        title="Date to"
      />
      <select
        value={filters.decision}
        onChange={(e) => update("decision", e.target.value)}
        className={selectClass}
      >
        <option value="">All Decisions</option>
        <option value="APPROVE">Approve</option>
        <option value="REJECT">Reject</option>
        <option value="REFER_TO_HUMAN">Refer</option>
      </select>
      <select
        value={filters.gtDecision}
        onChange={(e) => update("gtDecision", e.target.value)}
        className={selectClass}
      >
        <option value="">All GT Decisions</option>
        <option value="APPROVED">Approved</option>
        <option value="DENIED">Denied</option>
      </select>
      <select
        value={filters.matchStatus}
        onChange={(e) => update("matchStatus", e.target.value)}
        className={selectClass}
      >
        <option value="">All Match Status</option>
        <option value="match">Match</option>
        <option value="mismatch">Mismatch</option>
      </select>
      <select
        value={filters.resultCode}
        onChange={(e) => update("resultCode", e.target.value)}
        className={selectClass}
      >
        <option value="">All Result Codes</option>
        {resultCodes.map((code) => (
          <option key={code} value={code}>
            {code}
          </option>
        ))}
      </select>
      <input
        type="text"
        value={filters.search}
        onChange={(e) => update("search", e.target.value)}
        placeholder="Search claim ID..."
        className={`${inputClass} w-44`}
      />
      {Object.values(filters).some((v) => v !== "") && (
        <button
          onClick={() =>
            onChange({
              search: "",
              decision: "",
              gtDecision: "",
              matchStatus: "",
              resultCode: "",
              dateFrom: "",
              dateTo: "",
            })
          }
          className="h-9 px-3 text-sm text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
        >
          Clear
        </button>
      )}
    </div>
  );
}
