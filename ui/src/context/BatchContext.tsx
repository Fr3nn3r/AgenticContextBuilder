import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useRef,
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
  isRefreshing: boolean;
  // Polling control
  pollingEnabled: boolean;
  setPollingEnabled: (enabled: boolean) => void;
}

const BatchContext = createContext<BatchContextType | null>(null);

interface BatchProviderProps {
  children: ReactNode;
}

// Polling interval in milliseconds (30 seconds)
const POLLING_INTERVAL = 30000;

export function BatchProvider({ children }: BatchProviderProps) {
  const [searchParams] = useSearchParams();

  // Run state
  const [runs, setRuns] = useState<ClaimRunInfo[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Detailed runs (with phase metrics for ExtractionPage)
  const [detailedRuns, setDetailedRuns] = useState<DetailedRunInfo[]>([]);
  const [selectedDetailedRun, setSelectedDetailedRun] = useState<DetailedRunInfo | null>(null);

  // Polling state (disabled by default to avoid UI flickering)
  const [pollingEnabled, setPollingEnabled] = useState(false);

  // Dashboard insights state
  const [dashboardOverview, setDashboardOverview] = useState<InsightsOverview | null>(null);
  const [dashboardDocTypes, setDashboardDocTypes] = useState<DocTypeMetrics[]>([]);
  const [dashboardLoading, setDashboardLoading] = useState(false);

  // Load runs from API
  const loadRuns = useCallback(async (isManualRefresh = false) => {
    try {
      if (isManualRefresh) {
        setIsRefreshing(true);
      }
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
    } finally {
      if (isManualRefresh) {
        setIsRefreshing(false);
      }
    }
  }, [selectedRunId]);

  // Manual refresh handler (with loading indicator)
  const refreshRuns = useCallback(async () => {
    await loadRuns(true);
  }, [loadRuns]);

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

  // Polling for new runs (background refresh without loading indicator)
  const pollingEnabledRef = useRef(pollingEnabled);
  pollingEnabledRef.current = pollingEnabled;

  useEffect(() => {
    if (!pollingEnabled) return;

    const intervalId = setInterval(() => {
      if (pollingEnabledRef.current) {
        loadRuns(false); // Silent refresh (no loading indicator)
      }
    }, POLLING_INTERVAL);

    return () => clearInterval(intervalId);
  }, [pollingEnabled, loadRuns]);

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
        refreshRuns,
        isRefreshing,
        pollingEnabled,
        setPollingEnabled,
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
