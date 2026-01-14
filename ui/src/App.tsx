import { useState, useEffect } from "react";
import { Routes, Route, Navigate, useNavigate, useLocation, useSearchParams } from "react-router-dom";
import { Sidebar } from "./components/Sidebar";
import { BatchWorkspace } from "./components/BatchWorkspace";
import { ClaimsTable } from "./components/ClaimsTable";
import { ClaimReview } from "./components/ClaimReview";
import { ClassificationReview } from "./components/ClassificationReview";
import { DocumentReview } from "./components/DocumentReview";
import { ExtractionPage } from "./components/ExtractionPage";
import { TemplatesPage } from "./components/TemplatesPage";
import { MetricsPage } from "./components/metrics";
import { EvaluationPage } from "./components/evaluation";
import { NewClaimPage } from "./components/NewClaimPage";
import { PipelineControlCenter } from "./components/PipelineControlCenter";
import { TruthPage } from "./components/TruthPage";
import LoginPage from "./components/LoginPage";
import ProtectedRoute from "./components/ProtectedRoute";
import { AdminPage } from "./components/AdminPage";
import { useAuth } from "./context/AuthContext";
import type { ClaimSummary, DocSummary } from "./types";
import {
  listClaims,
  listDocs,
  listClaimRuns,
  getRunOverview,
  getRunDocTypes,
  getDetailedRuns,
  type ClaimRunInfo,
  type InsightsOverview,
  type DocTypeMetrics,
  type DetailedRunInfo,
} from "./api/client";

function App() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const { user, isLoading: authLoading } = useAuth();

  const [claims, setClaims] = useState<ClaimSummary[]>([]);
  const [filteredClaims, setFilteredClaims] = useState<ClaimSummary[]>([]);
  const [selectedClaim, setSelectedClaim] = useState<ClaimSummary | null>(null);
  const [docs, setDocs] = useState<DocSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Run state
  const [runs, setRuns] = useState<ClaimRunInfo[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  // Extraction page state (detailed runs with phase metrics)
  const [detailedRuns, setDetailedRuns] = useState<DetailedRunInfo[]>([]);
  const [selectedDetailedRun, setSelectedDetailedRun] = useState<DetailedRunInfo | null>(null);

  // Dashboard insights state
  const [dashboardOverview, setDashboardOverview] = useState<InsightsOverview | null>(null);
  const [dashboardDocTypes, setDashboardDocTypes] = useState<DocTypeMetrics[]>([]);
  const [dashboardLoading, setDashboardLoading] = useState(false);

  // Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [lobFilter, setLobFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [riskFilter, setRiskFilter] = useState("all");

  // Load runs on mount
  useEffect(() => {
    loadRuns();
  }, []);

  // Handle run_id from URL query params (e.g., from NewClaimPage navigation)
  useEffect(() => {
    const urlRunId = searchParams.get('run_id');
    if (urlRunId && urlRunId !== selectedRunId) {
      // Set the run_id from URL and refresh runs list to include it
      setSelectedRunId(urlRunId);
      loadRuns(); // Refresh to include the new run in the dropdown
    }
  }, [searchParams, selectedRunId]);

  // Load claims and dashboard data when run selection changes
  useEffect(() => {
    loadClaims(selectedRunId || undefined);
    if (selectedRunId) {
      loadDashboardData(selectedRunId);
      // Update selected detailed run
      const detailed = detailedRuns.find((r) => r.run_id === selectedRunId);
      setSelectedDetailedRun(detailed || null);
    }
  }, [selectedRunId, detailedRuns]);

  // Apply filters whenever claims or filters change
  useEffect(() => {
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
  }, [claims, searchQuery, lobFilter, statusFilter, riskFilter, selectedRunId]);

  async function loadRuns() {
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
      console.error("Failed to load runs:", err);
    }
  }

  async function loadClaims(runId?: string) {
    try {
      setLoading(true);
      setError(null);
      const data = await listClaims(runId);
      setClaims(data);
      setFilteredClaims(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load claims");
    } finally {
      setLoading(false);
    }
  }

  async function loadDashboardData(runId: string) {
    try {
      setDashboardLoading(true);
      const [overviewData, docTypesData] = await Promise.all([
        getRunOverview(runId),
        getRunDocTypes(runId),
      ]);
      setDashboardOverview(overviewData.overview);
      setDashboardDocTypes(docTypesData);
    } catch (err) {
      console.error("Failed to load dashboard data:", err);
      setDashboardOverview(null);
      setDashboardDocTypes([]);
    } finally {
      setDashboardLoading(false);
    }
  }

  async function handleSelectClaim(claim: ClaimSummary) {
    try {
      setSelectedClaim(claim);
      const data = await listDocs(claim.folder_name, selectedRunId || undefined);
      setDocs(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load docs");
    }
  }

  function handleSelectDoc(docId: string, claimId: string) {
    navigate(`/claims/${claimId}/review?doc=${docId}`);
  }

  function handleNavigateToReview(claimId: string) {
    navigate(`/claims/${claimId}/review`);
  }

  // Get current page title based on route (for non-batch routes)
  function getPageTitle(): string {
    const path = location.pathname;
    if (path === "/claims/new") return "New Claim";
    if (path === "/claims/all") return "All Claims";
    if (path.startsWith("/claims/") && path.endsWith("/review")) return "Claim Review";
    if (path === "/templates") return "Extraction Templates";
    if (path === "/pipeline") return "Pipeline Control Center";
    if (path === "/truth") return "Ground Truth";
    return "ContextBuilder";
  }

  // Get current view for sidebar active state
  function getCurrentView(): "new-claim" | "batches" | "evaluation" | "all-claims" | "templates" | "pipeline" | "truth" | "admin" {
    const path = location.pathname;
    if (path.startsWith("/batches")) return "batches";
    if (path === "/evaluation") return "evaluation";
    if (path === "/claims/new") return "new-claim";
    if (path === "/claims/all") return "all-claims";
    if (path === "/templates") return "templates";
    if (path === "/pipeline") return "pipeline";
    if (path === "/truth") return "truth";
    if (path === "/admin") return "admin";
    // Default to batches for claim review (accessed from batch context)
    if (path.startsWith("/claims/") && path.endsWith("/review")) return "batches";
    return "batches";
  }

  // Check if current route is a batch workspace route (no header needed)
  const isBatchRoute = location.pathname.startsWith("/batches");

  // Check if on login page (don't show sidebar/header)
  const isLoginRoute = location.pathname === "/login";

  // Show loading while checking auth
  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--color-bg-primary)]">
        <div className="flex flex-col items-center gap-4">
          <div className="w-8 h-8 border-2 border-[var(--color-accent-primary)] border-t-transparent rounded-full animate-spin" />
          <p className="text-[var(--color-text-secondary)]">Loading...</p>
        </div>
      </div>
    );
  }

  // Login page (no sidebar/header)
  if (isLoginRoute) {
    return (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
      </Routes>
    );
  }

  // Protected app (requires auth)
  if (!user) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }

  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      <Sidebar currentView={getCurrentView()} />

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header - only show for non-batch routes */}
        {!isBatchRoute && (
          <header className="bg-card border-b border-border px-6 py-4 flex items-center justify-between">
            <h1 className="text-xl font-semibold text-foreground">
              {getPageTitle()}
            </h1>
            <div className="flex items-center gap-4">
              <button className="p-2 text-muted-foreground hover:text-foreground">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
                </svg>
              </button>
              <button className="p-2 text-muted-foreground hover:text-foreground relative">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                </svg>
                <span className="absolute top-1 right-1 w-2 h-2 bg-destructive rounded-full"></span>
              </button>
              <div className="w-8 h-8 bg-muted rounded-full flex items-center justify-center text-sm font-medium text-muted-foreground">
                CB
              </div>
            </div>
          </header>
        )}

        {/* Content */}
        <main className={isBatchRoute ? "flex-1 overflow-hidden" : "flex-1 overflow-auto"}>
          {loading && !isBatchRoute ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-muted-foreground">Loading...</div>
            </div>
          ) : error && !isBatchRoute ? (
            <div className="flex flex-col items-center justify-center h-full">
              <p className="text-destructive mb-4">{error}</p>
              <button
                onClick={() => loadClaims(selectedRunId || undefined)}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
              >
                Retry
              </button>
            </div>
          ) : (
            <Routes>
              {/* Batch workspace routes */}
              <Route
                path="/batches"
                element={
                  <BatchWorkspace
                    batches={detailedRuns}
                    selectedBatchId={selectedRunId}
                    onBatchChange={setSelectedRunId}
                    selectedBatch={selectedDetailedRun}
                  />
                }
              >
                <Route
                  index
                  element={
                    selectedRunId ? (
                      <Navigate to={selectedRunId} replace />
                    ) : (
                      <div className="flex items-center justify-center h-full text-muted-foreground">
                        Loading batches...
                      </div>
                    )
                  }
                />
                <Route
                  path=":batchId"
                  element={
                    <ExtractionPage
                      batches={detailedRuns}
                      selectedBatchId={selectedRunId}
                      onBatchChange={setSelectedRunId}
                      selectedBatch={selectedDetailedRun}
                      overview={dashboardOverview}
                      docTypes={dashboardDocTypes}
                      loading={dashboardLoading}
                    />
                  }
                />
                <Route
                  path=":batchId/documents"
                  element={
                    <DocumentReview
                      batches={runs}
                      selectedBatchId={selectedRunId}
                      onBatchChange={setSelectedRunId}
                    />
                  }
                />
                <Route
                  path=":batchId/classification"
                  element={
                    <ClassificationReview
                      batches={runs}
                      selectedBatchId={selectedRunId}
                      onBatchChange={setSelectedRunId}
                    />
                  }
                />
                <Route
                  path=":batchId/claims"
                  element={
                    <ClaimsTable
                      claims={filteredClaims}
                      totalCount={claims.length}
                      selectedClaim={selectedClaim}
                      docs={docs}
                      searchQuery={searchQuery}
                      lobFilter={lobFilter}
                      statusFilter={statusFilter}
                      riskFilter={riskFilter}
                      runs={runs}
                      selectedRunId={selectedRunId}
                      onRunChange={setSelectedRunId}
                      onSearchChange={setSearchQuery}
                      onLobFilterChange={setLobFilter}
                      onStatusFilterChange={setStatusFilter}
                      onRiskFilterChange={setRiskFilter}
                      onSelectClaim={handleSelectClaim}
                      onSelectDoc={handleSelectDoc}
                      onNavigateToReview={handleNavigateToReview}
                    />
                  }
                />
                <Route
                  path=":batchId/metrics"
                  element={
                    <MetricsPage
                      selectedBatchId={selectedRunId}
                      onBatchChange={setSelectedRunId}
                    />
                  }
                />
                {/* Redirect old benchmark URL to new metrics */}
                <Route
                  path=":batchId/benchmark"
                  element={<Navigate to="../metrics" replace />}
                />
              </Route>

              {/* Batch-independent routes */}
              <Route
                path="/claims/new"
                element={
                  <ProtectedRoute screen="new-claim">
                    <NewClaimPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/claims/all"
                element={
                  <ClaimsTable
                    claims={claims}
                    totalCount={claims.length}
                    selectedClaim={selectedClaim}
                    docs={docs}
                    searchQuery={searchQuery}
                    lobFilter={lobFilter}
                    statusFilter={statusFilter}
                    riskFilter={riskFilter}
                    runs={runs}
                    selectedRunId={selectedRunId}
                    onRunChange={setSelectedRunId}
                    onSearchChange={setSearchQuery}
                    onLobFilterChange={setLobFilter}
                    onStatusFilterChange={setStatusFilter}
                    onRiskFilterChange={setRiskFilter}
                    onSelectClaim={handleSelectClaim}
                    onSelectDoc={handleSelectDoc}
                    onNavigateToReview={handleNavigateToReview}
                  />
                }
              />
              <Route
                path="/claims/:claimId/review"
                element={<ClaimReview onSaved={() => loadClaims(selectedRunId || undefined)} selectedRunId={selectedRunId} />}
              />
              <Route
                path="/templates"
                element={
                  <ProtectedRoute screen="templates">
                    <TemplatesPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/pipeline"
                element={
                  <ProtectedRoute screen="pipeline">
                    <PipelineControlCenter />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/truth"
                element={
                  <ProtectedRoute screen="ground-truth">
                    <TruthPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin"
                element={
                  <ProtectedRoute screen="admin">
                    <AdminPage />
                  </ProtectedRoute>
                }
              />
              <Route path="/evaluation" element={<EvaluationPage />} />

              {/* Redirects for backwards compatibility */}
              <Route path="/" element={<Navigate to="/batches" replace />} />
              <Route path="/dashboard" element={<Navigate to="/batches" replace />} />
              <Route
                path="/documents"
                element={
                  selectedRunId ? (
                    <Navigate to={`/batches/${selectedRunId}/documents`} replace />
                  ) : (
                    <Navigate to="/batches" replace />
                  )
                }
              />
              <Route
                path="/classification"
                element={
                  selectedRunId ? (
                    <Navigate to={`/batches/${selectedRunId}/classification`} replace />
                  ) : (
                    <Navigate to="/batches" replace />
                  )
                }
              />
              <Route
                path="/claims"
                element={
                  selectedRunId ? (
                    <Navigate to={`/batches/${selectedRunId}/claims`} replace />
                  ) : (
                    <Navigate to="/batches" replace />
                  )
                }
              />
              <Route
                path="/insights"
                element={<Navigate to="/evaluation" replace />}
              />
            </Routes>
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
