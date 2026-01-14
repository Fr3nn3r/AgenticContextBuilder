import { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth, Screen } from '../context/AuthContext';

interface ProtectedRouteProps {
  children: ReactNode;
  screen?: Screen;
}

export default function ProtectedRoute({ children, screen }: ProtectedRouteProps) {
  const { user, isLoading, canAccess } = useAuth();
  const location = useLocation();

  // Show loading spinner while checking auth
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--color-bg-primary)]">
        <div className="flex flex-col items-center gap-4">
          <div className="w-8 h-8 border-2 border-[var(--color-accent-primary)] border-t-transparent rounded-full animate-spin" />
          <p className="text-[var(--color-text-secondary)]">Loading...</p>
        </div>
      </div>
    );
  }

  // Redirect to login if not authenticated
  if (!user) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }

  // Check screen-level permission
  if (screen && !canAccess(screen)) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--color-bg-primary)]">
        <div className="max-w-md p-8 text-center bg-[var(--color-bg-secondary)] rounded-lg border border-[var(--color-border)]">
          <div className="w-12 h-12 mx-auto mb-4 rounded-full bg-red-500/10 flex items-center justify-center">
            <svg
              className="w-6 h-6 text-red-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-2">
            Access Denied
          </h2>
          <p className="text-[var(--color-text-secondary)] mb-4">
            You don't have permission to access this page.
          </p>
          <p className="text-sm text-[var(--color-text-tertiary)]">
            Your role: <span className="font-medium">{user.role}</span>
          </p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
