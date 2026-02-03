import { useMemo } from "react";
import type { DashboardClaim } from "../../types";

export interface DashboardFilterValues {
  search: string;
  decision: string;
  gtDecision: string;
  resultCode: string;
  dataset: string;
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

  const datasetOptions = useMemo(() => {
    const map = new Map<string, string>();
    for (const c of claims) {
      if (c.dataset_id && c.dataset_label) {
        map.set(c.dataset_id, c.dataset_label);
      }
    }
    return Array.from(map.entries()).sort((a, b) => a[1].localeCompare(b[1]));
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
        type="text"
        value={filters.search}
        onChange={(e) => update("search", e.target.value)}
        placeholder="Search claim ID..."
        className={`${inputClass} w-44`}
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
      {datasetOptions.length > 0 && (
        <select
          value={filters.dataset}
          onChange={(e) => update("dataset", e.target.value)}
          className={selectClass}
        >
          <option value="">All Datasets</option>
          {datasetOptions.map(([id, label]) => (
            <option key={id} value={id}>
              {label}
            </option>
          ))}
        </select>
      )}
      {Object.values(filters).some((v) => v !== "") && (
        <button
          onClick={() =>
            onChange({
              search: "",
              decision: "",
              gtDecision: "",
              resultCode: "",
              dataset: "",
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
