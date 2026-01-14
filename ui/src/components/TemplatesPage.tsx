import { useState, useEffect } from "react";
import { getTemplates } from "../api/client";
import type { TemplateSpec } from "../types";
import { cn } from "../lib/utils";

export function TemplatesPage() {
  const [templates, setTemplates] = useState<TemplateSpec[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<TemplateSpec | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadTemplates();
  }, []);

  async function loadTemplates() {
    try {
      setLoading(true);
      setError(null);
      const data = await getTemplates();
      setTemplates(data);
      if (data.length > 0) {
        setSelectedTemplate(data[0]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load templates");
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-muted-foreground">Loading templates...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full">
        <p className="text-destructive mb-4">{error}</p>
        <button
          onClick={loadTemplates}
          className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="p-6">
      {/* Template cards */}
      <div className="flex gap-3 mb-6 overflow-x-auto pb-2">
        {templates.map((template) => (
          <button
            key={`${template.doc_type}_${template.version}`}
            onClick={() => setSelectedTemplate(template)}
            className={cn(
              "px-4 py-3 rounded-lg border text-left whitespace-nowrap transition-colors",
              selectedTemplate?.doc_type === template.doc_type
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border bg-card hover:border-muted-foreground"
            )}
          >
            <div className="font-medium">{formatDocType(template.doc_type)}</div>
            <div className={cn(
              "text-xs",
              selectedTemplate?.doc_type === template.doc_type ? "text-primary-foreground/70" : "text-muted-foreground"
            )}>
              {template.version}
            </div>
          </button>
        ))}
      </div>

      {/* Selected template details */}
      {selectedTemplate && (
        <div className="bg-card rounded-lg border border-border">
          {/* Template header */}
          <div className="p-4 border-b border-border">
            <h3 className="text-lg font-semibold text-foreground">
              {formatDocType(selectedTemplate.doc_type)}
            </h3>
            <p className="text-sm text-muted-foreground">
              Version: {selectedTemplate.version}
            </p>
          </div>

          {/* Fields section */}
          <div className="p-4 border-b border-border">
            <h4 className="text-sm font-semibold text-foreground mb-3">Fields</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Required fields */}
              <div>
                <h5 className="text-xs font-medium text-muted-foreground uppercase mb-2">Required</h5>
                <div className="space-y-2">
                  {selectedTemplate.required_fields.map((field) => (
                    <FieldCard
                      key={field}
                      name={field}
                      rule={selectedTemplate.field_rules[field]}
                      required
                    />
                  ))}
                </div>
              </div>

              {/* Optional fields */}
              <div>
                <h5 className="text-xs font-medium text-muted-foreground uppercase mb-2">Optional</h5>
                <div className="space-y-2">
                  {selectedTemplate.optional_fields.map((field) => (
                    <FieldCard
                      key={field}
                      name={field}
                      rule={selectedTemplate.field_rules[field]}
                    />
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Quality gate section */}
          <div className="p-4">
            <h4 className="text-sm font-semibold text-foreground mb-3">Quality Gate Rules</h4>
            <div className="space-y-2 text-sm">
              {selectedTemplate.quality_gate.pass_if && (
                <div className="flex items-start gap-2">
                  <span className="w-16 text-green-600 dark:text-green-400 font-medium">PASS if:</span>
                  <code className="text-foreground bg-muted px-2 py-0.5 rounded">
                    {selectedTemplate.quality_gate.pass_if.join(" AND ")}
                  </code>
                </div>
              )}
              {selectedTemplate.quality_gate.warn_if && (
                <div className="flex items-start gap-2">
                  <span className="w-16 text-yellow-600 dark:text-yellow-400 font-medium">WARN if:</span>
                  <code className="text-foreground bg-muted px-2 py-0.5 rounded">
                    {selectedTemplate.quality_gate.warn_if.join(" OR ")}
                  </code>
                </div>
              )}
              {selectedTemplate.quality_gate.fail_if && (
                <div className="flex items-start gap-2">
                  <span className="w-16 text-red-600 dark:text-red-400 font-medium">FAIL if:</span>
                  <code className="text-foreground bg-muted px-2 py-0.5 rounded">
                    {selectedTemplate.quality_gate.fail_if.join(" OR ")}
                  </code>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {templates.length === 0 && (
        <div className="text-center py-12 text-muted-foreground">
          No extraction templates available.
        </div>
      )}
    </div>
  );
}

interface FieldRule {
  normalize?: string;
  validate?: string;
  hints?: string[];
}

function FieldCard({ name, rule, required }: { name: string; rule?: FieldRule; required?: boolean }) {
  return (
    <div className="p-3 bg-muted rounded-lg border border-border">
      <div className="flex items-center gap-2 mb-1">
        <span className="font-medium text-foreground">{formatFieldName(name)}</span>
        {required && (
          <span className="text-xs px-1.5 py-0.5 bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 rounded">Required</span>
        )}
      </div>
      <code className="text-xs text-muted-foreground">{name}</code>
      {rule && (
        <div className="mt-2 text-xs text-muted-foreground space-y-1">
          {rule.normalize && (
            <div>
              <span className="text-muted-foreground/70">Normalize:</span> {rule.normalize}
            </div>
          )}
          {rule.validate && (
            <div>
              <span className="text-muted-foreground/70">Validate:</span> {rule.validate}
            </div>
          )}
          {rule.hints && rule.hints.length > 0 && (
            <div>
              <span className="text-muted-foreground/70">Hints:</span>{" "}
              <span className="text-muted-foreground">{rule.hints.slice(0, 5).join(", ")}</span>
              {rule.hints.length > 5 && <span className="text-muted-foreground/70"> +{rule.hints.length - 5} more</span>}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function formatDocType(docType: string): string {
  return docType
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatFieldName(fieldName: string): string {
  return fieldName
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
