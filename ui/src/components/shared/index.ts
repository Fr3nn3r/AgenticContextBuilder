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

// Run selector
export { RunSelector, formatRunLabel } from "./RunSelector";
