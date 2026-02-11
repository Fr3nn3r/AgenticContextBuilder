import { useState, useEffect, useCallback } from "react";
import { getClaimNotes, saveClaimNotes } from "../../api/client";
import type { ClaimNotes } from "../../types";

export function NotesTab({ claimId }: { claimId: string }) {
  const [notes, setNotes] = useState<ClaimNotes | null>(null);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const loadNotes = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getClaimNotes(claimId);
      setNotes(data);
      setDraft(data.content);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load notes");
    } finally {
      setLoading(false);
    }
  }, [claimId]);

  useEffect(() => {
    loadNotes();
  }, [loadNotes]);

  const handleSave = async () => {
    try {
      setSaving(true);
      setError(null);
      const data = await saveClaimNotes(claimId, draft);
      setNotes(data);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save notes");
    } finally {
      setSaving(false);
    }
  };

  const isDirty = notes !== null && draft !== notes.content;

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
        Loading notes...
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <textarea
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        placeholder="Add notes about this claim..."
        className="w-full min-h-[160px] p-3 text-sm border border-border rounded-lg bg-background text-foreground resize-y focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
      />

      <div className="flex items-center justify-between">
        <div className="text-xs text-muted-foreground">
          {notes?.updated_at && (
            <span>
              Last saved {new Date(notes.updated_at).toLocaleString()}
              {notes.updated_by && <> by {notes.updated_by}</>}
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          {saved && (
            <span className="text-xs text-success font-medium">Saved</span>
          )}
          {error && (
            <span className="text-xs text-destructive">{error}</span>
          )}
          <button
            onClick={handleSave}
            disabled={!isDirty || saving}
            className="px-4 py-1.5 text-sm font-medium rounded-md transition-colors bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? "Saving..." : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
