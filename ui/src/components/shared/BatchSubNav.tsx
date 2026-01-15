import { NavLink, useParams } from "react-router-dom";
import { cn } from "../../lib/utils";

export type BatchTab = "overview" | "documents" | "classification" | "claims" | "metrics";

export interface BatchTabCounts {
  documents?: number;
  claims?: number;
}

interface BatchSubNavProps {
  className?: string;
  counts?: BatchTabCounts;
}

const tabs: { id: BatchTab; label: string; path: string; countKey?: keyof BatchTabCounts }[] = [
  { id: "overview", label: "Overview", path: "" },
  { id: "documents", label: "Documents", path: "/documents", countKey: "documents" },
  { id: "classification", label: "Classification", path: "/classification" },
  { id: "claims", label: "Claims", path: "/claims", countKey: "claims" },
  { id: "metrics", label: "Metrics", path: "/metrics" },
];

export function BatchSubNav({ className, counts }: BatchSubNavProps) {
  const { batchId } = useParams<{ batchId: string }>();
  const basePath = `/batches/${batchId}`;

  return (
    <div
      className={cn("bg-card border-b border-border px-6", className)}
      data-testid="batch-sub-nav"
    >
      <nav className="flex gap-1" aria-label="Batch views">
        {tabs.map((tab) => (
          <NavLink
            key={tab.id}
            to={`${basePath}${tab.path}`}
            end={tab.id === "overview"}
            data-testid={`batch-tab-${tab.id}`}
            className={({ isActive }) =>
              cn(
                "px-4 py-3 text-sm font-medium border-b-2 -mb-px transition-colors flex items-center gap-1.5",
                isActive
                  ? "border-primary text-primary"
                  : "border-transparent text-muted-foreground hover:text-foreground hover:border-muted"
              )
            }
          >
            {tab.label}
            {counts && tab.countKey && counts[tab.countKey] !== undefined && (
              <span className="px-1.5 py-0.5 text-xs bg-muted rounded-full">
                {counts[tab.countKey]}
              </span>
            )}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
