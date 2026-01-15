import { createContext, useContext, useState, useCallback, ReactNode } from 'react';

// Filter state types
export interface FilterState {
  searchQuery: string;
  lobFilter: string;
  statusFilter: string;
  riskFilter: string;
}

interface FilterContextType {
  // State
  searchQuery: string;
  lobFilter: string;
  statusFilter: string;
  riskFilter: string;
  // Setters
  setSearchQuery: (query: string) => void;
  setLobFilter: (lob: string) => void;
  setStatusFilter: (status: string) => void;
  setRiskFilter: (risk: string) => void;
  // Convenience
  resetFilters: () => void;
  hasActiveFilters: boolean;
}

const FilterContext = createContext<FilterContextType | null>(null);

const DEFAULT_FILTERS: FilterState = {
  searchQuery: '',
  lobFilter: 'all',
  statusFilter: 'all',
  riskFilter: 'all',
};

interface FilterProviderProps {
  children: ReactNode;
}

export function FilterProvider({ children }: FilterProviderProps) {
  const [searchQuery, setSearchQuery] = useState(DEFAULT_FILTERS.searchQuery);
  const [lobFilter, setLobFilter] = useState(DEFAULT_FILTERS.lobFilter);
  const [statusFilter, setStatusFilter] = useState(DEFAULT_FILTERS.statusFilter);
  const [riskFilter, setRiskFilter] = useState(DEFAULT_FILTERS.riskFilter);

  const resetFilters = useCallback(() => {
    setSearchQuery(DEFAULT_FILTERS.searchQuery);
    setLobFilter(DEFAULT_FILTERS.lobFilter);
    setStatusFilter(DEFAULT_FILTERS.statusFilter);
    setRiskFilter(DEFAULT_FILTERS.riskFilter);
  }, []);

  const hasActiveFilters =
    searchQuery !== DEFAULT_FILTERS.searchQuery ||
    lobFilter !== DEFAULT_FILTERS.lobFilter ||
    statusFilter !== DEFAULT_FILTERS.statusFilter ||
    riskFilter !== DEFAULT_FILTERS.riskFilter;

  return (
    <FilterContext.Provider
      value={{
        searchQuery,
        lobFilter,
        statusFilter,
        riskFilter,
        setSearchQuery,
        setLobFilter,
        setStatusFilter,
        setRiskFilter,
        resetFilters,
        hasActiveFilters,
      }}
    >
      {children}
    </FilterContext.Provider>
  );
}

export function useFilters(): FilterContextType {
  const context = useContext(FilterContext);
  if (!context) {
    throw new Error('useFilters must be used within a FilterProvider');
  }
  return context;
}
