/**
 * Centralized route configuration.
 * Single source of truth for paths, labels, titles, and navigation metadata.
 *
 * To add a new route:
 * 1. Add entry to ROUTE_CONFIG
 * 2. If it needs sidebar nav, set showInNav: true
 * 3. Add icon to ICONS map in Sidebar.tsx
 */

export type ViewId =
  | "new-claim"
  | "batches"
  | "evaluation"
  | "all-claims"
  | "claims-explorer"
  | "documents"
  | "cost-estimates"
  | "decision-dossier"
  | "templates"
  | "pipeline"
  | "truth"
  | "costs"
  | "compliance"
  | "admin"
  | "assessment"
  | "triage"
  | "claim-intake";

export interface RouteConfig {
  /** Unique identifier for the route */
  id: ViewId;
  /** URL path (exact or prefix match) */
  path: string;
  /** Display label for navigation */
  label: string;
  /** Page title shown in header */
  title: string;
  /** If true, path is matched as prefix (e.g., /batches/*) */
  matchPrefix?: boolean;
  /** Show in sidebar navigation */
  showInNav?: boolean;
  /** Auth screen name for permission check (maps to Screen type in AuthContext) */
  authScreen?: string;
}

/**
 * All route configurations. Order matters for nav display.
 */
export const ROUTE_CONFIG: RouteConfig[] = [
  // Nav items (showInNav: true)
  { id: "new-claim", path: "/claims/new", label: "New Claim", title: "New Claim", showInNav: true, authScreen: "new-claim" },
  { id: "claim-intake", path: "/claim-intake", label: "Claim Intake", title: "Claim Intake", showInNav: true },
  { id: "batches", path: "/batches", label: "Batches", title: "Batches", matchPrefix: true, showInNav: true, authScreen: "batches" },
  { id: "evaluation", path: "/evaluation", label: "Evaluation", title: "Evaluation", showInNav: true, authScreen: "evaluation" },
  { id: "all-claims", path: "/claims/all", label: "Dashboard", title: "Claims Dashboard", showInNav: true, authScreen: "all-claims" },
  { id: "claims-explorer", path: "/claims/explorer", label: "Claim Explorer", title: "Claim Explorer", showInNav: true, authScreen: "claims-explorer" },
  { id: "documents", path: "/documents", label: "Documents", title: "Documents", showInNav: true, authScreen: "documents" },
  { id: "cost-estimates", path: "/cost-estimates", label: "Cost Estimates", title: "Cost Estimates Review", showInNav: true },
  { id: "decision-dossier", path: "/decision", label: "Workbench", title: "Claims Workbench", showInNav: true, authScreen: "decision-dossier" },
  { id: "truth", path: "/truth", label: "Ground Truth", title: "Ground Truth", showInNav: true, authScreen: "ground-truth" },
  { id: "templates", path: "/templates", label: "Templates", title: "Extraction Templates", showInNav: true, authScreen: "templates" },
  { id: "pipeline", path: "/pipeline", label: "Pipeline", title: "Pipeline Control Center", showInNav: true, authScreen: "pipeline" },
  { id: "costs", path: "/costs", label: "Token Costs", title: "Token Costs", showInNav: true, authScreen: "costs" },
  { id: "compliance", path: "/compliance", label: "Compliance", title: "Compliance", matchPrefix: true, showInNav: true, authScreen: "compliance" },
  { id: "admin", path: "/admin", label: "Admin", title: "Admin", showInNav: true, authScreen: "admin" },

  // Non-nav routes (for title/view lookups)
  { id: "assessment", path: "/assessment", label: "Assessment", title: "Assessment Console" },
  { id: "triage", path: "/triage", label: "Triage", title: "Triage Queue" },
];

/**
 * Get nav items for sidebar (filtered by showInNav).
 */
export function getNavItems(): RouteConfig[] {
  return ROUTE_CONFIG.filter((r) => r.showInNav);
}

/**
 * Get the view ID for a given path (for sidebar active state).
 */
export function getViewFromPath(path: string): ViewId {
  // Special case: claim review routes map to batches
  if (path.startsWith("/claims/") && path.endsWith("/review")) {
    return "batches";
  }

  // Check prefix matches first (more specific)
  for (const route of ROUTE_CONFIG) {
    if (route.matchPrefix && path.startsWith(route.path)) {
      return route.id;
    }
  }

  // Check exact matches
  for (const route of ROUTE_CONFIG) {
    if (!route.matchPrefix && path === route.path) {
      return route.id;
    }
  }

  // Default
  return "batches";
}

/**
 * Get the page title for a given path.
 */
export function getPageTitle(path: string): string {
  // Special case: claim review
  if (path.startsWith("/claims/") && path.endsWith("/review")) {
    return "Claim Review";
  }

  // Check prefix matches first
  for (const route of ROUTE_CONFIG) {
    if (route.matchPrefix && path.startsWith(route.path)) {
      return route.title;
    }
  }

  // Check exact matches
  for (const route of ROUTE_CONFIG) {
    if (!route.matchPrefix && path === route.path) {
      return route.title;
    }
  }

  return "True AIm";
}

/**
 * Get route config by ID.
 */
export function getRouteById(id: ViewId): RouteConfig | undefined {
  return ROUTE_CONFIG.find((r) => r.id === id);
}
