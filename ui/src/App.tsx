import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import { Sidebar } from "./components/Sidebar";
import LoginPage from "./components/LoginPage";
import { useAuth } from "./context/AuthContext";
import { AppRoutes } from "./AppRoutes";
import { ThemePopover, HeaderUserMenu } from "./components/shared";
import { getViewFromPath, getPageTitle } from "./routes";

function App() {
  const location = useLocation();
  const { user, isLoading: authLoading } = useAuth();

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
      <Sidebar currentView={getViewFromPath(location.pathname)} />

      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header - only show for non-batch routes (excluding claims explorer which has its own header) */}
        {!isBatchRoute && !isClaimsExplorerRoute && (
          <header className="bg-card border-b border-border px-6 py-3 flex items-center justify-between">
            <h1 className="text-xl font-semibold text-foreground">
              {getPageTitle(location.pathname)}
            </h1>
            <div className="flex items-center gap-2">
              <ThemePopover />
              <HeaderUserMenu />
            </div>
          </header>
        )}

        {/* Content */}
        <main className={(isBatchRoute || isClaimsExplorerRoute) ? "flex-1 overflow-hidden" : "flex-1 overflow-auto"}>
          <AppRoutes />
        </main>
      </div>
    </div>
  );
}

export default App;
