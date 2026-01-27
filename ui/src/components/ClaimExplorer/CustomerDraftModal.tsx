import { useState, useEffect } from "react";
import { X, Loader2, Copy, Check, Mail } from "lucide-react";
import { cn } from "../../lib/utils";
import { generateCustomerDraft, type CustomerDraftResponse } from "../../api/client";

interface CustomerDraftModalProps {
  isOpen: boolean;
  onClose: () => void;
  claimId: string;
}

type Language = "en" | "de";

/**
 * Modal for viewing customer communication draft emails.
 * Supports English and German with language tabs.
 */
export function CustomerDraftModal({
  isOpen,
  onClose,
  claimId,
}: CustomerDraftModalProps) {
  const [language, setLanguage] = useState<Language>("en");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<Language, CustomerDraftResponse | null>>({
    en: null,
    de: null,
  });
  const [copied, setCopied] = useState(false);

  // Load draft when modal opens or language changes
  useEffect(() => {
    if (!isOpen) return;

    // Check if we already have this language's draft
    if (drafts[language]) return;

    const loadDraft = async () => {
      setLoading(true);
      setError(null);
      try {
        const result = await generateCustomerDraft(claimId, language);
        setDrafts((prev) => ({ ...prev, [language]: result }));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to generate draft");
      } finally {
        setLoading(false);
      }
    };

    loadDraft();
  }, [isOpen, language, claimId, drafts]);

  // Reset state when modal closes
  useEffect(() => {
    if (!isOpen) {
      // Keep drafts cached for re-opening, but reset other state
      setCopied(false);
      setError(null);
    }
  }, [isOpen]);

  const handleCopy = async () => {
    const draft = drafts[language];
    if (!draft) return;

    const textToCopy = `Subject: ${draft.subject}\n\n${draft.body}`;
    try {
      await navigator.clipboard.writeText(textToCopy);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for older browsers
      const textarea = document.createElement("textarea");
      textarea.value = textToCopy;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (!isOpen) return null;

  const currentDraft = drafts[language];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-background/80 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-card rounded-xl border border-border shadow-2xl w-full max-w-2xl mx-4 max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-blue-500/10 flex items-center justify-center">
              <Mail className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-foreground">
                Customer Communication Draft
              </h2>
              <p className="text-sm text-muted-foreground">
                Claim: {claimId}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Language Tabs */}
        <div className="px-6 pt-4">
          <div className="flex gap-1 p-1 bg-muted rounded-lg w-fit">
            <button
              onClick={() => setLanguage("en")}
              className={cn(
                "px-4 py-2 text-sm font-medium rounded-md transition-colors",
                language === "en"
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              English
            </button>
            <button
              onClick={() => setLanguage("de")}
              className={cn(
                "px-4 py-2 text-sm font-medium rounded-md transition-colors",
                language === "de"
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              German
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
              <p className="mt-3 text-sm text-muted-foreground">
                Generating {language === "en" ? "English" : "German"} draft...
              </p>
            </div>
          ) : error ? (
            <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-4">
              <p className="text-sm text-destructive">{error}</p>
            </div>
          ) : currentDraft ? (
            <div className="space-y-4">
              {/* Subject */}
              <div>
                <label className="block text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">
                  Subject
                </label>
                <div className="bg-muted/50 rounded-lg px-4 py-3 text-sm font-medium text-foreground">
                  {currentDraft.subject}
                </div>
              </div>

              {/* Body */}
              <div>
                <label className="block text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">
                  Email Body
                </label>
                <div className="bg-muted/50 rounded-lg px-4 py-4 text-sm text-foreground whitespace-pre-wrap leading-relaxed">
                  {currentDraft.body}
                </div>
              </div>

              {/* Tokens used */}
              {currentDraft.tokens_used > 0 && (
                <p className="text-xs text-muted-foreground">
                  Tokens used: {currentDraft.tokens_used}
                </p>
              )}
            </div>
          ) : null}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-border">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg transition-colors"
          >
            Close
          </button>
          <button
            onClick={handleCopy}
            disabled={!currentDraft || loading}
            className={cn(
              "inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors",
              "bg-primary text-primary-foreground hover:opacity-90",
              "disabled:opacity-50 disabled:cursor-not-allowed"
            )}
          >
            {copied ? (
              <>
                <Check className="w-4 h-4" />
                Copied!
              </>
            ) : (
              <>
                <Copy className="w-4 h-4" />
                Copy to Clipboard
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
