// Shared UI components for consistent design across all screens

// Status badges
export {
  StatusBadge,
  LatestBadge,
  BaselineBadge,
  CompleteBadge,
  PartialBadge,
  PassBadge,
  WarnBadge,
  FailBadge,
  LabeledBadge,
  UnlabeledBadge,
  PendingBadge,
  ConfirmedBadge,
  NotInRunBadge,
  RequiredBadge,
  CorrectBadge,
  IncorrectBadge,
  MissingBadge,
  UnverifiableBadge,
  ScoreBadge,
  GateStatusBadge,
  OutcomeBadge,
  type BadgeVariant,
} from "./StatusBadge";

// Metric cards
export {
  MetricCard,
  DeltaMetricCard,
  MetricCardRow,
  getScoreVariant,
} from "./MetricCard";

// Loading skeletons
export {
  Skeleton,
  TextSkeleton,
  MetricCardSkeleton,
  TableRowSkeleton,
  RunListSkeleton,
  PageLoadingSkeleton,
  Spinner,
  DocumentViewerSkeleton,
  FieldListSkeleton,
} from "./LoadingSkeleton";

// Empty states
export {
  EmptyState,
  NoDataEmptyState,
  NoSearchResultsEmptyState,
  NoDocumentsEmptyState,
  SelectToViewEmptyState,
  ErrorEmptyState,
  NoLabelsEmptyState,
} from "./EmptyState";

// Batch selector
export { BatchSelector } from "./BatchSelector";

// Batch workspace components
export { BatchContextBar } from "./BatchContextBar";
export { BatchSubNav, type BatchTab } from "./BatchSubNav";

// Header components
export { ThemePopover } from "./ThemePopover";
export { HeaderUserMenu } from "./HeaderUserMenu";

// Help tooltips
export { HelpTerm, HelpIcon, HelpTooltipProvider } from "./HelpTerm";

// Extractor badge
export { ExtractorBadge } from "./ExtractorBadge";
