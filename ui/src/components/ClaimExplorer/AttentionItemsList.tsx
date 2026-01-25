import {
  AlertTriangle,
  XCircle,
  Info,
  ChevronRight,
  ExternalLink,
  Eye,
} from "lucide-react";
import { cn } from "../../lib/utils";

export interface AttentionItem {
  id: string;
  type: "error" | "warning" | "info";
  title: string;
  description: string;
  action: string;
  docId?: string;
  checkNumber?: number;
}

interface AttentionItemsListProps {
  items: AttentionItem[];
  onDocumentClick?: (docId: string) => void;
  maxItems?: number;
}

const TYPE_CONFIG: Record<
  AttentionItem["type"],
  { icon: typeof AlertTriangle; bgColor: string; borderColor: string; iconColor: string; textColor: string }
> = {
  error: {
    icon: XCircle,
    bgColor: "bg-red-50 dark:bg-red-900/20",
    borderColor: "border-red-200 dark:border-red-800",
    iconColor: "text-red-500",
    textColor: "text-red-700 dark:text-red-300",
  },
  warning: {
    icon: AlertTriangle,
    bgColor: "bg-amber-50 dark:bg-amber-900/20",
    borderColor: "border-amber-200 dark:border-amber-800",
    iconColor: "text-amber-500",
    textColor: "text-amber-700 dark:text-amber-300",
  },
  info: {
    icon: Info,
    bgColor: "bg-blue-50 dark:bg-blue-900/20",
    borderColor: "border-blue-200 dark:border-blue-800",
    iconColor: "text-blue-500",
    textColor: "text-blue-700 dark:text-blue-300",
  },
};

/**
 * Shows prioritized list of items needing human attention.
 * Items are derived from real backend data (failed checks, assumptions, quality gates).
 */
export function AttentionItemsList({
  items,
  onDocumentClick,
  maxItems = 8,
}: AttentionItemsListProps) {
  const displayItems = items.slice(0, maxItems);
  const hasMore = items.length > maxItems;

  // Count by type
  const errorCount = items.filter((i) => i.type === "error").length;
  const warningCount = items.filter((i) => i.type === "warning").length;
  const infoCount = items.filter((i) => i.type === "info").length;

  if (items.length === 0) {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50">
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
            Attention Items
          </h3>
        </div>
        <div className="p-6 text-center">
          <div className="w-12 h-12 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center mx-auto mb-3">
            <svg
              className="h-6 w-6 text-green-500"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5 13l4 4L19 7"
              />
            </svg>
          </div>
          <p className="text-sm font-medium text-slate-700 dark:text-slate-200">
            No items need attention
          </p>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            All checks passed with no critical issues
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
      {/* Header with counts */}
      <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
          Attention Items
        </h3>
        <div className="flex items-center gap-2">
          {errorCount > 0 && (
            <span className="px-2 py-0.5 text-[10px] font-medium rounded-full bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400">
              {errorCount} error{errorCount > 1 ? "s" : ""}
            </span>
          )}
          {warningCount > 0 && (
            <span className="px-2 py-0.5 text-[10px] font-medium rounded-full bg-amber-100 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400">
              {warningCount} warning{warningCount > 1 ? "s" : ""}
            </span>
          )}
          {infoCount > 0 && (
            <span className="px-2 py-0.5 text-[10px] font-medium rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400">
              {infoCount} info
            </span>
          )}
        </div>
      </div>

      {/* Items List */}
      <div className="divide-y divide-slate-100 dark:divide-slate-800">
        {displayItems.map((item) => {
          const config = TYPE_CONFIG[item.type];
          const Icon = config.icon;

          return (
            <div
              key={item.id}
              className={cn(
                "px-4 py-3 flex items-start gap-3 transition-colors",
                item.docId && onDocumentClick
                  ? "hover:bg-slate-50 dark:hover:bg-slate-800/50 cursor-pointer"
                  : ""
              )}
              onClick={() => {
                if (item.docId && onDocumentClick) {
                  onDocumentClick(item.docId);
                }
              }}
            >
              {/* Icon */}
              <div
                className={cn(
                  "w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0",
                  config.bgColor
                )}
              >
                <Icon className={cn("h-4 w-4", config.iconColor)} />
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-2">
                  <h4 className={cn("text-sm font-medium", config.textColor)}>
                    {item.title}
                  </h4>
                  {item.checkNumber !== undefined && (
                    <span className="text-[10px] text-slate-400 dark:text-slate-500 font-mono flex-shrink-0">
                      Check #{item.checkNumber}
                    </span>
                  )}
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 line-clamp-2">
                  {item.description}
                </p>
                <div className="flex items-center gap-2 mt-1.5">
                  <span className="text-[10px] text-slate-400 dark:text-slate-500 uppercase tracking-wider">
                    {item.action}
                  </span>
                  {item.docId && onDocumentClick && (
                    <span className="flex items-center gap-0.5 text-[10px] text-blue-500 dark:text-blue-400">
                      <Eye className="h-3 w-3" />
                      View document
                    </span>
                  )}
                </div>
              </div>

              {/* Arrow */}
              <ChevronRight className="h-4 w-4 text-slate-300 dark:text-slate-600 flex-shrink-0 mt-2" />
            </div>
          );
        })}
      </div>

      {/* Show more */}
      {hasMore && (
        <div className="px-4 py-2 border-t border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/30">
          <button className="text-xs text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1">
            View all {items.length} items
            <ExternalLink className="h-3 w-3" />
          </button>
        </div>
      )}
    </div>
  );
}
