import { useState, useEffect, useMemo, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { getDashboardClaims } from "../../api/client";
import type { DashboardClaim } from "../../types";
import { DashboardFilters, type DashboardFilterValues } from "./DashboardFilters";
import { DashboardCharts } from "./DashboardCharts";
import { DashboardTable } from "./DashboardTable";

export function ClaimsDashboardPage() {
  const [claims, setClaims] = useState<DashboardClaim[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();

  const filters: DashboardFilterValues = useMemo(
    () => ({
      search: searchParams.get("search") || "",
      decision: searchParams.get("decision") || "",
      gtDecision: searchParams.get("gtDecision") || "",
      resultCode: searchParams.get("resultCode") || "",
      dataset: searchParams.get("dataset") || "",
    }),
    [searchParams]
  );

  const setFilters = useCallback(
    (f: DashboardFilterValues) => {
      const params = new URLSearchParams();
      for (const [key, val] of Object.entries(f)) {
        if (val) params.set(key, val);
      }
      setSearchParams(params, { replace: true });
    },
    [setSearchParams]
  );

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getDashboardClaims();
      setClaims(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load claims");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const filteredClaims = useMemo(() => {
    return claims.filter((c) => {
      if (filters.search && !c.claim_id.includes(filters.search)) return false;

      if (filters.decision) {
        const d = c.decision?.toUpperCase();
        if (filters.decision === "APPROVE" && d !== "APPROVE" && d !== "APPROVED")
          return false;
        if (filters.decision === "REJECT" && d !== "REJECT" && d !== "DENIED")
          return false;
        if (filters.decision === "REFER_TO_HUMAN" && d !== "REFER_TO_HUMAN")
          return false;
      }

      if (filters.gtDecision) {
        if (c.gt_decision?.toUpperCase() !== filters.gtDecision.toUpperCase())
          return false;
      }

      if (filters.resultCode && c.result_code !== filters.resultCode) return false;

      if (filters.dataset && c.dataset_id !== filters.dataset) return false;

      return true;
    });
  }, [claims, filters]);

  const stats = useMemo(() => {
    const total = filteredClaims.length;
    const withAssessment = filteredClaims.filter((c) => c.decision).length;
    const matches = filteredClaims.filter((c) => c.decision_match === true).length;
    const mismatches = filteredClaims.filter((c) => c.decision_match === false).length;
    return { total, withAssessment, matches, mismatches };
  }, [filteredClaims]);

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">
            Claims Dashboard
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            {stats.total} claims
            {stats.withAssessment > 0 && (
              <>
                {" \u00B7 "}
                {stats.matches} match, {stats.mismatches} mismatch
              </>
            )}
          </p>
        </div>
        <button
          onClick={loadData}
          disabled={loading}
          className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors disabled:opacity-50"
        >
          <svg
            className={`w-4 h-4 ${loading ? "animate-spin" : ""}`}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path d="M21 12a9 9 0 1 1-6.22-8.56" />
          </svg>
          Refresh
        </button>
      </div>

      {/* Filters */}
      <DashboardFilters filters={filters} onChange={setFilters} claims={claims} />

      {/* Loading / Error */}
      {loading && claims.length === 0 && (
        <div className="flex items-center justify-center py-20">
          <div className="text-sm text-slate-500 dark:text-slate-400">
            Loading claims...
          </div>
        </div>
      )}

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-sm text-red-700 dark:text-red-300">
          {error}
          <button
            onClick={loadData}
            className="ml-3 text-red-600 dark:text-red-400 underline hover:no-underline"
          >
            Retry
          </button>
        </div>
      )}

      {/* Charts + Table */}
      {!loading || claims.length > 0 ? (
        <>
          <DashboardCharts claims={filteredClaims} />
          <DashboardTable claims={filteredClaims} />
        </>
      ) : null}
    </div>
  );
}
