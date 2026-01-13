import { cn } from "../../lib/utils";

interface EmptyStateProps {
  /** Main message */
  title: string;
  /** Optional description with more context */
  description?: string;
  /** Icon to display (optional) */
  icon?: "search" | "document" | "chart" | "folder" | "error" | "info";
  /** Optional action button */
  action?: {
    label: string;
    onClick: () => void;
  };
  /** Size variant */
  size?: "sm" | "md" | "lg";
  className?: string;
}

const iconComponents: Record<string, React.FC<{ className?: string }>> = {
  search: SearchIcon,
  document: DocumentIcon,
  chart: ChartIcon,
  folder: FolderIcon,
  error: ErrorIcon,
  info: InfoIcon,
};

const sizeStyles = {
  sm: {
    container: "py-6",
    icon: "w-8 h-8",
    title: "text-sm",
    description: "text-xs",
  },
  md: {
    container: "py-8",
    icon: "w-12 h-12",
    title: "text-base",
    description: "text-sm",
  },
  lg: {
    container: "py-12",
    icon: "w-16 h-16",
    title: "text-lg",
    description: "text-base",
  },
};

/**
 * Consistent empty state component used when there's no data to display.
 */
export function EmptyState({
  title,
  description,
  icon = "info",
  action,
  size = "md",
  className,
}: EmptyStateProps) {
  const styles = sizeStyles[size];
  const IconComponent = iconComponents[icon];

  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center text-center",
        styles.container,
        className
      )}
    >
      <IconComponent className={cn("text-muted-foreground/50 mb-3", styles.icon)} />
      <p className={cn("font-medium text-muted-foreground mb-1", styles.title)}>
        {title}
      </p>
      {description && (
        <p className={cn("text-muted-foreground/70 max-w-sm", styles.description)}>
          {description}
        </p>
      )}
      {action && (
        <button
          onClick={action.onClick}
          className="mt-4 px-4 py-2 text-sm font-medium text-primary bg-primary/10 rounded-md hover:bg-primary/20 transition-colors"
        >
          {action.label}
        </button>
      )}
    </div>
  );
}

// Icon components

function SearchIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.5}
        d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
      />
    </svg>
  );
}

function DocumentIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.5}
        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
      />
    </svg>
  );
}

function ChartIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.5}
        d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
      />
    </svg>
  );
}

function FolderIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.5}
        d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"
      />
    </svg>
  );
}

function ErrorIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.5}
        d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
      />
    </svg>
  );
}

function InfoIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.5}
        d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
      />
    </svg>
  );
}

// Pre-configured empty states for common scenarios

export function NoDataEmptyState() {
  return (
    <EmptyState
      icon="chart"
      title="No data available"
      description="There is no data to display for the current selection."
    />
  );
}

export function NoSearchResultsEmptyState({ query }: { query?: string }) {
  return (
    <EmptyState
      icon="search"
      title="No results found"
      description={query ? `No matches for "${query}"` : "Try adjusting your search or filters."}
    />
  );
}

export function NoDocumentsEmptyState() {
  return (
    <EmptyState
      icon="document"
      title="No documents"
      description="No documents have been processed yet."
    />
  );
}

export function SelectToViewEmptyState({ itemType = "item" }: { itemType?: string }) {
  return (
    <EmptyState
      icon="info"
      title={`Select a ${itemType} to view`}
      description={`Choose a ${itemType} from the list to see details.`}
      size="sm"
    />
  );
}

export function ErrorEmptyState({
  message,
  onRetry,
}: {
  message?: string;
  onRetry?: () => void;
}) {
  return (
    <EmptyState
      icon="error"
      title="Something went wrong"
      description={message || "An error occurred while loading data."}
      action={onRetry ? { label: "Try again", onClick: onRetry } : undefined}
    />
  );
}

export function NoLabelsEmptyState() {
  return (
    <EmptyState
      icon="chart"
      title="No labels yet"
      description="Add truth labels to see insights and accuracy metrics."
    />
  );
}
