import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import { Sidebar } from "./components/Sidebar";
import LoginPage from "./components/LoginPage";
import { useAuth } from "./context/AuthContext";
import { useClaims } from "./context/ClaimsContext";
import { AppRoutes } from "./AppRoutes";

function App() {
  const location = useLocation();
  const { user, isLoading: authLoading } = useAuth();
  const { loading, error, refreshClaims } = useClaims();

  // Get current view for sidebar active state
  function getCurrentView(): "new-claim" | "batches" | "evaluation" | "all-claims" | "templates" | "pipeline" | "truth" | "compliance" | "admin" {
    const path = location.pathname;
    if (path.startsWith("/batches")) return "batches";
    if (path === "/evaluation") return "evaluation";
    if (path === "/claims/new") return "new-claim";
    if (path === "/claims/all") return "all-claims";
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
