import { useState, useEffect } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { cn } from "../lib/utils";
import { useAuth, Screen } from "../context/AuthContext";
import { getAppVersion } from "../api/client";
import { getNavItems, ViewId } from "../routes";

interface SidebarProps {
  currentView: ViewId;
}

function ChevronLeftIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
    </svg>
  );
}

// Icon components keyed by route ID
const ICONS: Record<ViewId, React.ComponentType<{ className?: string }>> = {
  "new-claim": PlusIcon,
  "claim-intake": ClaimIntakeIcon,
  "batches": BatchesIcon,
  "evaluation": EvaluationIcon,
  "all-claims": ClaimsIcon,
  "claims-explorer": ExplorerIcon,
  "documents": DocumentsIcon,
  "cost-estimates": ReceiptIcon,
  "decision-dossier": ScaleIcon,
  "truth": TruthIcon,
  "templates": TemplatesIcon,
  "pipeline": PipelineIcon,
  "costs": CostsIcon,
  "compliance": ComplianceIcon,
  "admin": AdminIcon,
  "assessment": EvaluationIcon, // Reuse evaluation icon
  "triage": ClaimsIcon, // Reuse claims icon
};

// Get nav items from centralized config
const navItems = getNavItems();

export function Sidebar({ currentView }: SidebarProps) {
  const location = useLocation();
  const { user, canAccess } = useAuth();
  const [versionDisplay, setVersionDisplay] = useState("True AIm");
  const [collapsed, setCollapsed] = useState(() => {
    return localStorage.getItem("sidebar-collapsed") === "true";
  });

  // Persist collapsed state
  useEffect(() => {
    localStorage.setItem("sidebar-collapsed", String(collapsed));
  }, [collapsed]);

  // Fetch version on mount
  useEffect(() => {
    getAppVersion()
      .then((info) => setVersionDisplay(`True AIm ${info.display}`))
      .catch(() => setVersionDisplay("True AIm"));
  }, []);

  // Check if current path is under /batches (for active highlighting)
  const isBatchRoute = location.pathname.startsWith("/batches");

  // Filter nav items based on user role using permission matrix
  const visibleNavItems = navItems.filter((item) => {
    // If route has authScreen, check permission matrix
    if (item.authScreen) {
      return canAccess(item.authScreen as Screen);
    }
    // Routes without authScreen are accessible to all authenticated users
    return true;
  });

  return (
    <div
      className={cn(
        "bg-sidebar text-sidebar-foreground flex flex-col transition-all duration-200",
        collapsed ? "w-16" : "w-56"
      )}
      data-testid="sidebar"
    >
      {/* Logo */}
      <div className={cn("p-4 flex items-center", collapsed ? "justify-center" : "gap-2")}>
        <img
          src="/trueaim-logo.png"
          alt="True AIm Logo"
          className="w-8 h-8 object-contain dark:brightness-0 dark:invert flex-shrink-0"
        />
        {!collapsed && <span className="font-semibold text-lg">True AIm</span>}
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-2 py-4 space-y-1">
        {visibleNavItems.map((item) => {
          const Icon = ICONS[item.id];
          // For batches, check if any batch route is active
          const isActive =
            item.id === "batches"
              ? isBatchRoute
              : currentView === item.id;

          return (
            <NavLink
              key={item.id}
              to={item.path}
              title={collapsed ? item.label : undefined}
              data-testid={`nav-${item.id}`}
              className={cn(
                "w-full flex items-center rounded-lg text-sm transition-colors",
                collapsed ? "justify-center px-2 py-2" : "gap-3 px-3 py-2",
                isActive
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-muted-foreground hover:text-sidebar-foreground hover:bg-sidebar-accent/50"
              )}
            >
              <Icon className="w-5 h-5 flex-shrink-0" />
              {!collapsed && item.label}
            </NavLink>
          );
        })}
      </nav>

      {/* Footer - Toggle + Version */}
      <div className="border-t border-sidebar-border mt-auto">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="w-full flex items-center gap-2 px-4 py-3 text-muted-foreground hover:text-sidebar-foreground transition-colors"
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          <ChevronLeftIcon
            className={cn(
              "w-4 h-4 transition-transform duration-200 flex-shrink-0",
              collapsed && "rotate-180"
            )}
          />
          {!collapsed && <span className="text-xs">Collapse</span>}
        </button>
        {!collapsed && (
          <div className="px-4 pb-3 text-xs text-muted-foreground">
            {versionDisplay}
          </div>
        )}
      </div>
    </div>
  );
}

// Icon components
function BatchesIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
      />
    </svg>
  );
}

function ClaimsIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
    </svg>
  );
}

function TemplatesIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z" />
    </svg>
  );
}

function PlusIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
    </svg>
  );
}

function PipelineIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h10M4 18h16" />
    </svg>
  );
}

function TruthIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M9 12l2 2 4-4m5 2a9 9 0 11-18 0 9 9 0 0118 0z"
      />
    </svg>
  );
}

function AdminIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"
      />
    </svg>
  );
}

function ComplianceIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
      />
    </svg>
  );
}

function EvaluationIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
      />
    </svg>
  );
}

function DocumentsIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M5 19a2 2 0 01-2-2V7a2 2 0 012-2h4l2 2h4a2 2 0 012 2v1M5 19h14a2 2 0 002-2v-5a2 2 0 00-2-2H9a2 2 0 00-2 2v5a2 2 0 01-2 2z"
      />
    </svg>
  );
}

function ExplorerIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7"
      />
    </svg>
  );
}

function CostsIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
      />
    </svg>
  );
}

function ReceiptIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M9 14l6-6m-5.5.5h.01m4.99 5h.01M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16l3.5-2 3.5 2 3.5-2 3.5 2zM10 8.5a.5.5 0 11-1 0 .5.5 0 011 0zm5 5a.5.5 0 11-1 0 .5.5 0 011 0z"
      />
    </svg>
  );
}

function ClaimIntakeIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"
      />
    </svg>
  );
}

function ScaleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3"
      />
    </svg>
  );
}
