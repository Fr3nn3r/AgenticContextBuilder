import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import { Sidebar } from "./components/Sidebar";
import LoginPage from "./components/LoginPage";
import { useAuth } from "./context/AuthContext";
import { useClaims } from "./context/ClaimsContext";
import { AppRoutes } from "./AppRoutes";
import { ThemePopover, HeaderUserMenu } from "./components/shared";

function App() {
  const location = useLocation();
  const { user, isLoading: authLoading } = useAuth();
  const { loading, error, refreshClaims } = useClaims();

  // Get current view for sidebar active state
  function getCurrentView(): "new-claim" | "batches" | "evaluation" | "all-claims" | "claims-explorer" | "templates" | "pipeline" | "truth" | "compliance" | "admin" {
    const path = location.pathname;
    if (path.startsWith("/batches")) return "batches";
    if (path === "/evaluation") return "evaluation";
    if (path === "/claims/new") return "new-claim";
    if (path === "/claims/all") return "all-claims";
    if (path === "/claims/explorer") return "claims-explorer";
    if (path === "/templates") return "templates";
    if (path === "/pipeline") return "pipeline";
    if (path === "/truth") return "truth";
    if (path.startsWith("/compliance")) return "compliance";
    if (path === "/admin") return "admin";
    if (path.startsWith("/claims/") && path.endsWith("/review")) return "batches";
    return "batches";
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
    if (path.startsWith("/compliance")) return "Compliance";
    return "ContextBuilder";
  }

  const isBatchRoute = location.pathname.startsWith("/batches");
  const isClaimsExplorerRoute = location.pathname === "/claims/explorer";
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
      <Sidebar currentView={getCurrentView()} />

      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header - only show for non-batch routes (excluding claims explorer which has its own header) */}
        {!isBatchRoute && !isClaimsExplorerRoute && (
          <header className="bg-card border-b border-border px-6 py-3 flex items-center justify-between">
            <h1 className="text-xl font-semibold text-foreground">
              {getPageTitle()}
            </h1>
            <div className="flex items-center gap-2">
              <ThemePopover />
              <HeaderUserMenu />
            </div>
          </header>
        )}

        {/* Content */}
        <main className={(isBatchRoute || isClaimsExplorerRoute) ? "flex-1 overflow-hidden" : "flex-1 overflow-auto"}>
          {loading && !isBatchRoute ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-muted-foreground">Loading...</div>
            </div>
          ) : error && !isBatchRoute ? (
            <div className="flex flex-col items-center justify-center h-full">
              <p className="text-destructive mb-4">{error}</p>
              <button
                onClick={refreshClaims}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
              >
                Retry
              </button>
            </div>
          ) : (
            <AppRoutes />
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
