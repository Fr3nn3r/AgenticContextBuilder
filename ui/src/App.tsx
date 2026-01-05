import { useState, useEffect } from "react";
import { Sidebar } from "./components/Sidebar";
import { ClaimsTable } from "./components/ClaimsTable";
import { DocReview } from "./components/DocReview";
import { Dashboard } from "./components/Dashboard";
import type { ClaimSummary, DocSummary } from "./types";
import { listClaims, listDocs } from "./api/client";

type View = "dashboard" | "claims" | "review" | "qa-insights" | "reports" | "settings";

function App() {
  const [view, setView] = useState<View>("claims");
  const [claims, setClaims] = useState<ClaimSummary[]>([]);
  const [filteredClaims, setFilteredClaims] = useState<ClaimSummary[]>([]);
  const [selectedClaim, setSelectedClaim] = useState<ClaimSummary | null>(null);
  const [docs, setDocs] = useState<DocSummary[]>([]);
  const [selectedDoc, setSelectedDoc] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [lobFilter, setLobFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [riskFilter, setRiskFilter] = useState("all");

  // Load claims on mount
  useEffect(() => {
    loadClaims();
  }, []);

  // Apply filters whenever claims or filters change
  useEffect(() => {
    let result = [...claims];

    // Search filter
    if (searchQuery) {
      result = result.filter((c) =>
        c.claim_id.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }

    // LOB filter
    if (lobFilter !== "all") {
      result = result.filter((c) => c.lob === lobFilter);
    }

    // Status filter
    if (statusFilter !== "all") {
      result = result.filter((c) => c.status === statusFilter);
    }

    // Risk filter
    if (riskFilter !== "all") {
      if (riskFilter === "high") {
        result = result.filter((c) => c.risk_score >= 50);
      } else if (riskFilter === "medium") {
        result = result.filter((c) => c.risk_score >= 25 && c.risk_score < 50);
      } else if (riskFilter === "low") {
        result = result.filter((c) => c.risk_score < 25);
      }
    }

    setFilteredClaims(result);
  }, [claims, searchQuery, lobFilter, statusFilter, riskFilter]);

  async function loadClaims() {
    try {
      setLoading(true);
      setError(null);
      const data = await listClaims();
      setClaims(data);
      setFilteredClaims(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load claims");
    } finally {
      setLoading(false);
    }
  }

  async function handleSelectClaim(claim: ClaimSummary) {
    try {
      setSelectedClaim(claim);
      const data = await listDocs(claim.folder_name);
      setDocs(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load docs");
    }
  }

  function handleSelectDoc(docId: string) {
    setSelectedDoc(docId);
    setView("review");
  }

  function handleBackToClaims() {
    setView("claims");
    setSelectedDoc(null);
  }

  function handleNavigation(newView: View) {
    setView(newView);
    if (newView !== "review") {
      setSelectedDoc(null);
    }
  }

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <Sidebar
        currentView={view}
        onNavigate={handleNavigation}
      />

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="bg-white border-b px-6 py-4 flex items-center justify-between">
          <h1 className="text-xl font-semibold text-gray-900">
            {view === "dashboard" && "Dashboard"}
            {view === "claims" && "Claims Review"}
            {view === "review" && "Document Review"}
            {view === "qa-insights" && "QA Insights"}
            {view === "reports" && "Reports"}
            {view === "settings" && "Settings"}
          </h1>
          <div className="flex items-center gap-4">
            <button className="p-2 text-gray-500 hover:text-gray-700">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
              </svg>
            </button>
            <button className="p-2 text-gray-500 hover:text-gray-700 relative">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
              </svg>
              <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full"></span>
            </button>
            <div className="w-8 h-8 bg-gray-300 rounded-full flex items-center justify-center text-sm font-medium text-gray-700">
              QA
            </div>
          </div>
        </header>

        {/* Content */}
        <main className="flex-1 overflow-auto">
          {loading ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-gray-500">Loading...</div>
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center h-full">
              <p className="text-red-600 mb-4">{error}</p>
              <button
                onClick={loadClaims}
                className="px-4 py-2 bg-gray-900 text-white rounded-md hover:bg-gray-800"
              >
                Retry
              </button>
            </div>
          ) : view === "dashboard" ? (
            <Dashboard claims={claims} />
          ) : view === "claims" ? (
            <ClaimsTable
              claims={filteredClaims}
              totalCount={claims.length}
              selectedClaim={selectedClaim}
              docs={docs}
              searchQuery={searchQuery}
              lobFilter={lobFilter}
              statusFilter={statusFilter}
              riskFilter={riskFilter}
              onSearchChange={setSearchQuery}
              onLobFilterChange={setLobFilter}
              onStatusFilterChange={setStatusFilter}
              onRiskFilterChange={setRiskFilter}
              onSelectClaim={handleSelectClaim}
              onSelectDoc={handleSelectDoc}
            />
          ) : view === "review" && selectedDoc ? (
            <DocReview
              docId={selectedDoc}
              onBack={handleBackToClaims}
              onSaved={loadClaims}
            />
          ) : (
            <div className="flex items-center justify-center h-full text-gray-500">
              Coming soon...
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
