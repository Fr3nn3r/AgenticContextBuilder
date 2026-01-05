import type { ExtractedField, FieldLabel } from "../types";
import { cn } from "../lib/utils";

interface FieldsTableProps {
  fields: ExtractedField[];
  labels: FieldLabel[];
  onLabelChange: (fieldName: string, judgement: "correct" | "incorrect" | "unknown") => void;
  onQuoteClick: (quote: string, page: number) => void;
}

export function FieldsTable({
  fields,
  labels,
  onLabelChange,
  onQuoteClick,
}: FieldsTableProps) {
  function getLabel(fieldName: string): FieldLabel | undefined {
    return labels.find((l) => l.field_name === fieldName);
  }

  return (
    <div className="divide-y">
      {fields.map((field) => {
        const label = getLabel(field.name);
        const provenance = field.provenance[0];

        return (
          <div key={field.name} className="p-3">
            {/* Field header */}
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="font-medium">{field.name}</span>
                <StatusBadge status={field.status} />
                {field.value_is_placeholder && (
                  <span className="text-xs px-1.5 py-0.5 bg-purple-100 text-purple-700 rounded">
                    Placeholder
                  </span>
                )}
              </div>
              <div className="text-sm text-muted-foreground">
                {(field.confidence * 100).toFixed(0)}%
              </div>
            </div>

            {/* Value */}
            <div className="mb-2">
              {field.value ? (
                <div className="font-mono text-sm bg-secondary/50 px-2 py-1 rounded">
                  {field.normalized_value || field.value}
                  {field.normalized_value &&
                    field.normalized_value !== field.value && (
                      <span className="text-muted-foreground ml-2">
                        (raw: {field.value})
                      </span>
                    )}
                </div>
              ) : (
                <span className="text-muted-foreground italic text-sm">
                  Not found
                </span>
              )}
            </div>

            {/* Evidence quote */}
            {provenance && (
              <button
                onClick={() => onQuoteClick(provenance.text_quote, provenance.page)}
                className="text-left w-full mb-2"
              >
                <div className="text-xs text-muted-foreground mb-1">
                  Evidence (Page {provenance.page}):
                </div>
                <div className="text-sm bg-yellow-50 border-l-2 border-yellow-400 px-2 py-1 hover:bg-yellow-100 transition-colors">
                  "{provenance.text_quote}"
                </div>
              </button>
            )}

            {/* Label buttons */}
            <div className="flex gap-2">
              <LabelButton
                label="correct"
                selected={label?.judgement === "correct"}
                onClick={() => onLabelChange(field.name, "correct")}
                color="green"
              />
              <LabelButton
                label="incorrect"
                selected={label?.judgement === "incorrect"}
                onClick={() => onLabelChange(field.name, "incorrect")}
                color="red"
              />
              <LabelButton
                label="unknown"
                selected={label?.judgement === "unknown"}
                onClick={() => onLabelChange(field.name, "unknown")}
                color="gray"
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function StatusBadge({ status }: { status: "present" | "missing" | "uncertain" }) {
  const styles: Record<string, string> = {
    present: "bg-green-100 text-green-700",
    missing: "bg-red-100 text-red-700",
    uncertain: "bg-yellow-100 text-yellow-700",
  };

  return (
    <span className={cn("text-xs px-1.5 py-0.5 rounded", styles[status])}>
      {status}
    </span>
  );
}

interface LabelButtonProps {
  label: string;
  selected: boolean;
  onClick: () => void;
  color: "green" | "red" | "gray";
}

function LabelButton({ label, selected, onClick, color }: LabelButtonProps) {
  const colors = {
    green: selected
      ? "bg-green-500 text-white"
      : "bg-green-100 text-green-700 hover:bg-green-200",
    red: selected
      ? "bg-red-500 text-white"
      : "bg-red-100 text-red-700 hover:bg-red-200",
    gray: selected
      ? "bg-gray-500 text-white"
      : "bg-gray-100 text-gray-700 hover:bg-gray-200",
  };

  const icons = {
    correct: "✓",
    incorrect: "✗",
    unknown: "?",
  };

  return (
    <button
      onClick={onClick}
      className={cn(
        "px-3 py-1 rounded text-sm font-medium transition-colors",
        colors[color]
      )}
    >
      {icons[label as keyof typeof icons]} {label}
    </button>
  );
}
