import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  ReactNode,
} from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  listClaimRuns,
  getRunOverview,
  getRunDocTypes,
  getDetailedRuns,
  type ClaimRunInfo,
  type InsightsOverview,
  type DocTypeMetrics,
  type DetailedRunInfo,
} from '../api/client';

interface BatchContextType {
  // Run list (for dropdowns)
  runs: ClaimRunInfo[];
  // Selected run
  selectedRunId: string | null;
  setSelectedRunId: (runId: string | null) => void;
  // Detailed runs (with phase metrics)
  detailedRuns: DetailedRunInfo[];
  selectedDetailedRun: DetailedRunInfo | null;
  // Dashboard data (scoped to selected run)
  dashboardOverview: InsightsOverview | null;
  dashboardDocTypes: DocTypeMetrics[];
  dashboardLoading: boolean;
  // Actions
  refreshRuns: () => Promise<void>;
}

const BatchContext = createContext<BatchContextType | null>(null);

interface BatchProviderProps {
  children: ReactNode;
}

export function BatchProvider({ children }: BatchProviderProps) {
  const [searchParams] = useSearchParams();

  // Run state
  const [runs, setRuns] = useState<ClaimRunInfo[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  // Detailed runs (with phase metrics for ExtractionPage)
  const [detailedRuns, setDetailedRuns] = useState<DetailedRunInfo[]>([]);
  const [selectedDetailedRun, setSelectedDetailedRun] = useState<DetailedRunInfo | null>(null);

  // Dashboard insights state
  const [dashboardOverview, setDashboardOverview] = useState<InsightsOverview | null>(null);
  const [dashboardDocTypes, setDashboardDocTypes] = useState<DocTypeMetrics[]>([]);
  const [dashboardLoading, setDashboardLoading] = useState(false);

  // Load runs from API
  const loadRuns = useCallback(async () => {
    try {
      const [claimRuns, detailed] = await Promise.all([
        listClaimRuns(),
        getDetailedRuns(),
      ]);
      setRuns(claimRuns);
      setDetailedRuns(detailed);
      // Auto-select latest run if none selected
      if (detailed.length > 0 && !selectedRunId) {
        setSelectedRunId(detailed[0].run_id);
        setSelectedDetailedRun(detailed[0]);
      }
    } catch (err) {
      console.error('Failed to load runs:', err);
    }
  }, [selectedRunId]);

  // Load dashboard data for a specific run
  const loadDashboardData = useCallback(async (runId: string) => {
    try {
      setDashboardLoading(true);
      const [overviewData, docTypesData] = await Promise.all([
        getRunOverview(runId),
        getRunDocTypes(runId),
      ]);
      setDashboardOverview(overviewData.overview);
      setDashboardDocTypes(docTypesData);
    } catch (err) {
      console.error('Failed to load dashboard data:', err);
      setDashboardOverview(null);
      setDashboardDocTypes([]);
    } finally {
      setDashboardLoading(false);
    }
  }, []);

  // Load runs on mount
  useEffect(() => {
    loadRuns();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Handle run_id from URL query params (e.g., from NewClaimPage navigation)
  useEffect(() => {
    const urlRunId = searchParams.get('run_id');
    if (urlRunId && urlRunId !== selectedRunId) {
      // Set the run_id from URL and refresh runs list to include it
      setSelectedRunId(urlRunId);
      loadRuns(); // Refresh to include the new run in the dropdown
    }
  }, [searchParams, selectedRunId, loadRuns]);

  // Load dashboard data when run selection changes
  useEffect(() => {
    if (selectedRunId) {
      loadDashboardData(selectedRunId);
      // Update selected detailed run
      const detailed = detailedRuns.find((r) => r.run_id === selectedRunId);
      setSelectedDetailedRun(detailed || null);
    }
  }, [selectedRunId, detailedRuns, loadDashboardData]);

  return (
    <BatchContext.Provider
      value={{
        runs,
        selectedRunId,
        setSelectedRunId,
        detailedRuns,
        selectedDetailedRun,
        dashboardOverview,
        dashboardDocTypes,
        dashboardLoading,
        refreshRuns: loadRuns,
      }}
    >
      {children}
    </BatchContext.Provider>
  );
}

export function useBatch(): BatchContextType {
  const context = useContext(BatchContext);
  if (!context) {
    throw new Error('useBatch must be used within a BatchProvider');
  }
  return context;
}
