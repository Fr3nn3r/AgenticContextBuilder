import { NavLink, useLocation } from "react-router-dom";
import { useSpacemanTheme } from "@space-man/react-theme-animation";
import { cn } from "../lib/utils";

type View = "new-claim" | "batches" | "all-claims" | "templates" | "pipeline" | "truth";

interface SidebarProps {
  currentView: View;
}

const navItems = [
  { id: "new-claim" as View, label: "New Claim", path: "/claims/new", icon: PlusIcon },
  { id: "batches" as View, label: "Batches", path: "/batches", icon: BatchesIcon },
  { id: "all-claims" as View, label: "All Claims", path: "/claims/all", icon: ClaimsIcon },
  { id: "truth" as View, label: "Ground Truth", path: "/truth", icon: TruthIcon },
  { id: "templates" as View, label: "Templates", path: "/templates", icon: TemplatesIcon },
  { id: "pipeline" as View, label: "Pipeline", path: "/pipeline", icon: PipelineIcon },
];

const COLOR_THEMES = [
  { id: 'northern-lights', name: 'Northern Lights' },
  { id: 'default', name: 'Default' },
  { id: 'pink', name: 'Pink' },
] as const;

export function Sidebar({ currentView }: SidebarProps) {
  const location = useLocation();
  const { theme: darkMode, switchThemeFromElement, setColorTheme, colorTheme } = useSpacemanTheme();

  // Use colorTheme from hook, fallback to northern-lights
  const currentColorTheme = colorTheme || 'northern-lights';

  // Check if current path is under /batches (for active highlighting)
  const isBatchRoute = location.pathname.startsWith("/batches");

  return (
    <div className="w-56 bg-sidebar text-sidebar-foreground flex flex-col" data-testid="sidebar">
      {/* Logo */}
      <div className="p-4 flex items-center gap-2">
        <div className="w-8 h-8 bg-sidebar-primary rounded flex items-center justify-center text-sidebar-primary-foreground font-bold text-sm">
          CB
        </div>
        <span className="font-semibold text-lg">ContextBuilder</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-2 py-4 space-y-1">
        {navItems.map((item) => {
          const Icon = item.icon;
          // For batches, check if any batch route is active
          const isActive =
            item.id === "batches"
              ? isBatchRoute
              : currentView === item.id;

          return (
            <NavLink
              key={item.id}
              to={item.path}
              data-testid={`nav-${item.id}`}
              className={cn(
                "w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
                isActive
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-muted-foreground hover:text-sidebar-foreground hover:bg-sidebar-accent/50"
              )}
            >
              <Icon className="w-5 h-5" />
              {item.label}
            </NavLink>
          );
        })}
      </nav>

      {/* Footer - Theme Controls */}
      <div className="p-4 border-t border-sidebar-border space-y-3">
        {/* Color Theme Selector */}
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted-foreground">Theme</span>
          <select
            value={currentColorTheme}
            onChange={(e) => setColorTheme(e.target.value)}
            className="text-xs bg-sidebar-accent text-sidebar-accent-foreground rounded px-2 py-1 border-0 cursor-pointer"
          >
            {COLOR_THEMES.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        </div>

        {/* Dark Mode Toggle */}
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted-foreground">Mode</span>
          <div className="flex items-center gap-1">
            <button
              onClick={(e) => switchThemeFromElement("light", e.currentTarget)}
              className={cn(
                "p-1.5 rounded text-xs transition-colors",
                darkMode === "light"
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-muted-foreground hover:text-sidebar-foreground"
              )}
              title="Light mode"
            >
              <SunIcon className="w-4 h-4" />
            </button>
            <button
              onClick={(e) => switchThemeFromElement("dark", e.currentTarget)}
              className={cn(
                "p-1.5 rounded text-xs transition-colors",
                darkMode === "dark"
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-muted-foreground hover:text-sidebar-foreground"
              )}
              title="Dark mode"
            >
              <MoonIcon className="w-4 h-4" />
            </button>
            <button
              onClick={(e) => switchThemeFromElement("system", e.currentTarget)}
              className={cn(
                "p-1.5 rounded text-xs transition-colors",
                darkMode === "system"
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-muted-foreground hover:text-sidebar-foreground"
              )}
              title="System preference"
            >
              <SystemIcon className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="text-xs text-muted-foreground pt-1">
          ContextBuilder v1.0
        </div>
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

function SunIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"
      />
    </svg>
  );
}

function MoonIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"
      />
    </svg>
  );
}

function SystemIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
      />
    </svg>
  );
}
