import { useState, useCallback, useMemo } from "react";
import { cn } from "../lib/utils";

interface Provenance {
  page?: number;
  char_start?: number;
  char_end?: number;
  text_quote?: string;
}

interface JsonTreeViewerProps {
  data: unknown;
  /** Called when a field with provenance is clicked */
  onFieldClick?: (provenance: Provenance) => void;
  /** Maximum initial depth to expand (default: 2) */
  defaultExpandDepth?: number;
  /** CSS class for the container */
  className?: string;
}

interface TreeNodeProps {
  keyName?: string;
  value: unknown;
  depth: number;
  defaultExpandDepth: number;
  onFieldClick?: (provenance: Provenance) => void;
  selectedPath?: string;
  setSelectedPath?: (path: string) => void;
  path: string;
}

/**
 * Renders a collapsible JSON tree with syntax highlighting.
 * Clicking on extraction field values will trigger provenance highlighting.
 */
export function JsonTreeViewer({
  data,
  onFieldClick,
  defaultExpandDepth = 2,
  className,
}: JsonTreeViewerProps) {
  const [selectedPath, setSelectedPath] = useState<string>("");

  return (
    <div className={cn("font-mono text-sm p-3 overflow-auto", className)}>
      <TreeNode
        value={data}
        depth={0}
        defaultExpandDepth={defaultExpandDepth}
        onFieldClick={onFieldClick}
        selectedPath={selectedPath}
        setSelectedPath={setSelectedPath}
        path="$"
      />
    </div>
  );
}

function TreeNode({
  keyName,
  value,
  depth,
  defaultExpandDepth,
  onFieldClick,
  selectedPath,
  setSelectedPath,
  path,
}: TreeNodeProps) {
  const [isExpanded, setIsExpanded] = useState(depth < defaultExpandDepth);

  const isObject = value !== null && typeof value === "object";
  const isArray = Array.isArray(value);
  const isEmpty = isObject && Object.keys(value as object).length === 0;

  // Check if this node is an extraction field with provenance
  const provenance = useMemo(() => {
    if (!isObject || isArray) return null;
    const obj = value as Record<string, unknown>;
    // Look for provenance fields
    if (
      obj.page !== undefined ||
      obj.char_start !== undefined ||
      obj.char_end !== undefined ||
      obj.text_quote !== undefined
    ) {
      return {
        page: typeof obj.page === "number" ? obj.page : undefined,
        char_start: typeof obj.char_start === "number" ? obj.char_start : undefined,
        char_end: typeof obj.char_end === "number" ? obj.char_end : undefined,
        text_quote: typeof obj.text_quote === "string" ? obj.text_quote : undefined,
      };
    }
    return null;
  }, [value, isObject, isArray]);

  // Check if this is a field with a "value" key (extraction field pattern)
  const isExtractionField = useMemo(() => {
    if (!isObject || isArray) return false;
    const obj = value as Record<string, unknown>;
    return "value" in obj || "name" in obj;
  }, [value, isObject, isArray]);

  const handleClick = useCallback(() => {
    if (provenance && onFieldClick) {
      setSelectedPath?.(path);
      onFieldClick(provenance);
    }
  }, [provenance, onFieldClick, path, setSelectedPath]);

  const handleToggle = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    setIsExpanded((prev) => !prev);
  }, []);

  const isSelected = selectedPath === path;
  const indent = depth * 16;

  // Render primitive values
  if (!isObject) {
    return (
      <span
        className={cn(
          "inline",
          provenance && onFieldClick && "cursor-pointer hover:bg-accent/50 rounded px-0.5",
          isSelected && "bg-accent"
        )}
        onClick={provenance ? handleClick : undefined}
      >
        {keyName !== undefined && (
          <>
            <span className="text-purple-600 dark:text-purple-400">"{keyName}"</span>
            <span className="text-foreground">: </span>
          </>
        )}
        {renderValue(value)}
      </span>
    );
  }

  // Empty object/array
  if (isEmpty) {
    return (
      <span>
        {keyName !== undefined && (
          <>
            <span className="text-purple-600 dark:text-purple-400">"{keyName}"</span>
            <span className="text-foreground">: </span>
          </>
        )}
        <span className="text-muted-foreground">{isArray ? "[]" : "{}"}</span>
      </span>
    );
  }

  const entries = isArray
    ? (value as unknown[]).map((v, i) => [i, v] as const)
    : Object.entries(value as object);

  const bracket = isArray ? ["[", "]"] : ["{", "}"];
  const previewCount = 3;
  const preview = entries.slice(0, previewCount);

  return (
    <div
      className={cn(
        "relative",
        isExtractionField && provenance && onFieldClick && "cursor-pointer",
        isSelected && "bg-accent/30 rounded"
      )}
      onClick={isExtractionField && provenance ? handleClick : undefined}
    >
      <div className="flex items-start">
        {/* Toggle button */}
        <button
          onClick={handleToggle}
          className="w-4 h-4 flex items-center justify-center text-muted-foreground hover:text-foreground flex-shrink-0 mr-1"
        >
          <svg
            className={cn("w-3 h-3 transition-transform", isExpanded && "rotate-90")}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>

        {/* Key and bracket */}
        <span>
          {keyName !== undefined && (
            <>
              <span className="text-purple-600 dark:text-purple-400">"{keyName}"</span>
              <span className="text-foreground">: </span>
            </>
          )}
          <span className="text-foreground">{bracket[0]}</span>

          {/* Collapsed preview */}
          {!isExpanded && (
            <span className="text-muted-foreground">
              {preview.map(([key, val], i) => (
                <span key={String(key)}>
                  {!isArray && (
                    <>
                      <span className="text-purple-600/70 dark:text-purple-400/70">"{key}"</span>
                      <span>: </span>
                    </>
                  )}
                  {renderValuePreview(val)}
                  {i < preview.length - 1 && ", "}
                </span>
              ))}
              {entries.length > previewCount && `, ... (${entries.length - previewCount} more)`}
              <span className="text-foreground">{bracket[1]}</span>
            </span>
          )}
        </span>
      </div>

      {/* Expanded children */}
      {isExpanded && (
        <div style={{ marginLeft: indent + 20 }}>
          {entries.map(([key, val], i) => (
            <div key={String(key)} className="leading-relaxed">
              <TreeNode
                keyName={isArray ? undefined : String(key)}
                value={val}
                depth={depth + 1}
                defaultExpandDepth={defaultExpandDepth}
                onFieldClick={onFieldClick}
                selectedPath={selectedPath}
                setSelectedPath={setSelectedPath}
                path={`${path}.${key}`}
              />
              {i < entries.length - 1 && <span className="text-foreground">,</span>}
            </div>
          ))}
          <div className="text-foreground">{bracket[1]}</div>
        </div>
      )}
    </div>
  );
}

function renderValue(value: unknown): React.ReactNode {
  if (value === null) {
    return <span className="text-orange-600 dark:text-orange-400">null</span>;
  }
  if (typeof value === "boolean") {
    return <span className="text-blue-600 dark:text-blue-400">{String(value)}</span>;
  }
  if (typeof value === "number") {
    return <span className="text-emerald-600 dark:text-emerald-400">{value}</span>;
  }
  if (typeof value === "string") {
    // Truncate long strings
    const display = value.length > 100 ? value.slice(0, 100) + "..." : value;
    return <span className="text-amber-600 dark:text-amber-400">"{display}"</span>;
  }
  return <span className="text-muted-foreground">{String(value)}</span>;
}

function renderValuePreview(value: unknown): React.ReactNode {
  if (value === null) {
    return <span className="text-orange-600/70 dark:text-orange-400/70">null</span>;
  }
  if (typeof value === "boolean") {
    return <span className="text-blue-600/70 dark:text-blue-400/70">{String(value)}</span>;
  }
  if (typeof value === "number") {
    return <span className="text-emerald-600/70 dark:text-emerald-400/70">{value}</span>;
  }
  if (typeof value === "string") {
    const display = value.length > 20 ? value.slice(0, 20) + "..." : value;
    return <span className="text-amber-600/70 dark:text-amber-400/70">"{display}"</span>;
  }
  if (Array.isArray(value)) {
    return <span className="text-muted-foreground">[...]</span>;
  }
  if (typeof value === "object") {
    return <span className="text-muted-foreground">{"{...}"}</span>;
  }
  return <span className="text-muted-foreground">{String(value)}</span>;
}
