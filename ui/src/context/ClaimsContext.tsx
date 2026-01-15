import {
  createContext,
  useContext,
  useState,
  useEffect,
  useMemo,
  useCallback,
  ReactNode,
} from 'react';
import { listClaims, listDocs } from '../api/client';
import { useBatch } from './BatchContext';
import { useFilters } from './FilterContext';
import type { ClaimSummary, DocSummary } from '../types';

interface ClaimsContextType {
  // Claims list
  claims: ClaimSummary[];
  filteredClaims: ClaimSummary[];
  // Selected claim and its docs
  selectedClaim: ClaimSummary | null;
  docs: DocSummary[];
  // Loading state
  loading: boolean;
  error: string | null;
  // Actions
  selectClaim: (claim: ClaimSummary) => Promise<void>;
  refreshClaims: () => Promise<void>;
}

const ClaimsContext = createContext<ClaimsContextType | null>(null);

interface ClaimsProviderProps {
  children: ReactNode;
}

export function ClaimsProvider({ children }: ClaimsProviderProps) {
  const { selectedRunId } = useBatch();
  const { searchQuery, lobFilter, statusFilter, riskFilter } = useFilters();

  // Claims state
  const [claims, setClaims] = useState<ClaimSummary[]>([]);
  const [selectedClaim, setSelectedClaim] = useState<ClaimSummary | null>(null);
  const [docs, setDocs] = useState<DocSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load claims from API
  const loadClaims = useCallback(async (runId?: string) => {
    try {
      setLoading(true);
      setError(null);
      const data = await listClaims(runId);
      setClaims(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load claims');
    } finally {
      setLoading(false);
    }
  }, []);

  // Select a claim and load its documents
  const selectClaim = useCallback(async (claim: ClaimSummary) => {
    try {
      setSelectedClaim(claim);
      const data = await listDocs(claim.folder_name, selectedRunId || undefined);
      setDocs(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load docs');
    }
  }, [selectedRunId]);

  // Load claims when run selection changes
  useEffect(() => {
    loadClaims(selectedRunId || undefined);
  }, [selectedRunId, loadClaims]);

  // Filter claims - useMemo ensures synchronous filtering (no race condition)
  const filteredClaims = useMemo(() => {
    let result = [...claims];

    // Filter by run - only show claims that are in the selected run
    if (selectedRunId) {
      result = result.filter((c) => c.in_run);
    }

    // Search filter
    if (searchQuery) {
      result = result.filter((c) =>
        c.claim_id.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }

    // LOB filter
    if (lobFilter !== 'all') {
      result = result.filter((c) => c.lob === lobFilter);
    }

    // Status filter
    if (statusFilter !== 'all') {
      result = result.filter((c) => c.status === statusFilter);
    }

    // Risk filter
    if (riskFilter !== 'all') {
      if (riskFilter === 'high') {
        result = result.filter((c) => c.risk_score >= 50);
      } else if (riskFilter === 'medium') {
        result = result.filter((c) => c.risk_score >= 25 && c.risk_score < 50);
      } else if (riskFilter === 'low') {
        result = result.filter((c) => c.risk_score < 25);
      }
    }

    return result;
  }, [claims, searchQuery, lobFilter, statusFilter, riskFilter, selectedRunId]);

  // Refresh function for external use
  const refreshClaims = useCallback(async () => {
    await loadClaims(selectedRunId || undefined);
  }, [selectedRunId, loadClaims]);

  return (
    <ClaimsContext.Provider
      value={{
        claims,
        filteredClaims,
        selectedClaim,
        docs,
        loading,
        error,
        selectClaim,
        refreshClaims,
      }}
    >
      {children}
    </ClaimsContext.Provider>
  );
}

export function useClaims(): ClaimsContextType {
  const context = useContext(ClaimsContext);
  if (!context) {
    throw new Error('useClaims must be used within a ClaimsProvider');
  }
  return context;
}
