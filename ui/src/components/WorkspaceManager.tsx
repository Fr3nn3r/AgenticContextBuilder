import React, { useState, useEffect } from 'react';
import {
  listWorkspaces,
  createWorkspace,
  activateWorkspace,
  deleteWorkspace,
  rebuildIndex,
  type WorkspaceResponse,
  type CreateWorkspaceRequest,
  type RebuildIndexResponse,
} from '../api/client';

interface CreateFormData {
  name: string;
  description: string;
}

export function WorkspaceManager() {
  const [workspaces, setWorkspaces] = useState<WorkspaceResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [formData, setFormData] = useState<CreateFormData>({
    name: '',
    description: '',
  });
  const [formError, setFormError] = useState<string | null>(null);
  const [formLoading, setFormLoading] = useState(false);

  // Activation confirmation
  const [activatingId, setActivatingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // Index rebuild state
  const [rebuildingIndex, setRebuildingIndex] = useState(false);
  const [rebuildResult, setRebuildResult] = useState<RebuildIndexResponse | null>(null);

  useEffect(() => {
    loadWorkspaces();
  }, []);

  async function loadWorkspaces() {
    try {
      setLoading(true);
      setError(null);
      const data = await listWorkspaces();
      setWorkspaces(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load workspaces');
    } finally {
      setLoading(false);
    }
  }

  function resetForm() {
    setFormData({ name: '', description: '' });
    setFormError(null);
    setShowCreateForm(false);
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!formData.name) {
      setFormError('Name is required');
      return;
    }

    try {
      setFormLoading(true);
      setFormError(null);
      const request: CreateWorkspaceRequest = {
        name: formData.name,
        description: formData.description || undefined,
      };
      await createWorkspace(request);
      await loadWorkspaces();
      resetForm();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Failed to create workspace');
    } finally {
      setFormLoading(false);
    }
  }

  async function handleActivate(workspaceId: string) {
    try {
      const result = await activateWorkspace(workspaceId);
      // Redirect to login since all sessions are cleared
      alert(
        `Workspace "${workspaceId}" activated.\n\n` +
        `${result.sessions_cleared} session(s) cleared.\n\n` +
        `You will be logged out and redirected to the login page.`
      );
      // Clear local auth state
      localStorage.removeItem('auth_token');
      localStorage.removeItem('auth_user');
      window.location.href = '/login';
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to activate workspace');
      setActivatingId(null);
    }
  }

  async function handleDelete(workspaceId: string) {
    try {
      await deleteWorkspace(workspaceId);
      setDeletingId(null);
      await loadWorkspaces();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete workspace');
      setDeletingId(null);
    }
  }

  async function handleRebuildIndex() {
    try {
      setRebuildingIndex(true);
      setRebuildResult(null);
      setError(null);
      const result = await rebuildIndex();
      setRebuildResult(result);
      // Clear success message after 5 seconds
      setTimeout(() => setRebuildResult(null), 5000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to rebuild index');
    } finally {
      setRebuildingIndex(false);
    }
  }

  function formatDate(dateStr: string | null) {
    if (!dateStr) return 'Never';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  const [copiedPath, setCopiedPath] = useState<string | null>(null);

  async function copyToClipboard(path: string) {
    try {
      await navigator.clipboard.writeText(path);
      setCopiedPath(path);
      setTimeout(() => setCopiedPath(null), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="flex flex-col items-center gap-4">
          <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          <p className="text-muted-foreground">Loading workspaces...</p>
        </div>
      </div>
    );
  }

  const activeWorkspace = workspaces.find(ws => ws.is_active);

  return (
    <div>
      {/* Active Workspace Banner */}
      {activeWorkspace && (
        <div className="mb-6 p-4 bg-green-500/10 rounded-lg border border-green-500/30">
          <div className="flex items-center gap-3">
            <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse" />
            <span className="font-semibold text-foreground">{activeWorkspace.name}</span>
            <div className="flex items-center gap-2 ml-auto">
              <span className="text-xs text-muted-foreground font-mono truncate max-w-md" title={activeWorkspace.path}>
                {activeWorkspace.path}
              </span>
              <button
                onClick={() => copyToClipboard(activeWorkspace.path)}
                className="p-1 text-muted-foreground hover:text-foreground transition-colors"
                title="Copy path"
              >
                {copiedPath === activeWorkspace.path ? (
                  <svg className="w-4 h-4 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                )}
              </button>
              <button
                onClick={handleRebuildIndex}
                disabled={rebuildingIndex}
                className="px-3 py-1 text-xs bg-primary/20 text-primary rounded-md hover:bg-primary/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                title="Rebuild document, label, and run indexes"
              >
                {rebuildingIndex ? 'Rebuilding...' : 'Rebuild Index'}
              </button>
            </div>
          </div>
          {rebuildResult && (
            <div className="mt-3 pt-3 border-t border-green-500/20 text-xs text-green-600">
              Index rebuilt: {rebuildResult.stats.doc_count} docs, {rebuildResult.stats.claim_count} claims, {rebuildResult.stats.run_count} runs
            </div>
          )}
        </div>
      )}

      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-foreground">Workspaces</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Manage storage locations for isolated environments
          </p>
        </div>
        {!showCreateForm && (
          <button
            onClick={() => setShowCreateForm(true)}
            className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity"
          >
            Create Workspace
          </button>
        )}
      </div>

      {error && (
        <div className="mb-4 p-3 rounded-md bg-destructive/10 border border-destructive/30">
          <p className="text-sm text-destructive">{error}</p>
          <button
            onClick={() => setError(null)}
            className="text-xs text-destructive/70 hover:text-destructive mt-1"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Create Form */}
      {showCreateForm && (
        <div className="mb-6 p-4 bg-card rounded-lg border border-border">
          <h3 className="text-lg font-semibold text-foreground mb-4">Create New Workspace</h3>
          <form onSubmit={handleCreate} className="space-y-4">
            {formError && (
              <div className="p-3 rounded-md bg-destructive/10 border border-destructive/30">
                <p className="text-sm text-destructive">{formError}</p>
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-foreground mb-1">
                Name
              </label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full px-3 py-2 bg-background border border-border rounded-md text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                placeholder="e.g., Integration Tests"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-1">
                Description (optional)
              </label>
              <input
                type="text"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                className="w-full px-3 py-2 bg-background border border-border rounded-md text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                placeholder="e.g., For automated integration testing"
              />
            </div>

            <div className="flex gap-2">
              <button
                type="submit"
                disabled={formLoading}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {formLoading ? 'Creating...' : 'Create Workspace'}
              </button>
              <button
                type="button"
                onClick={resetForm}
                className="px-4 py-2 bg-muted text-foreground rounded-md hover:bg-accent transition-colors"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Workspaces Table */}
      <div className="bg-card rounded-lg border border-border overflow-hidden">
        <table className="w-full">
          <thead className="bg-muted">
            <tr>
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                Workspace
              </th>
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                Path
              </th>
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                Last Accessed
              </th>
              <th className="px-4 py-3 text-right text-sm font-medium text-muted-foreground">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {workspaces.map((workspace) => (
              <tr
                key={workspace.workspace_id}
                className={`hover:bg-muted/50 ${workspace.is_active ? 'bg-primary/5' : ''}`}
              >
                <td className="px-4 py-3">
                  <div className="flex items-center gap-3">
                    <div
                      className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                        workspace.is_active
                          ? 'bg-green-500/20 text-green-600'
                          : 'bg-muted text-muted-foreground'
                      }`}
                    >
                      {workspace.name.charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <span className="text-foreground font-medium">
                        {workspace.name}
                      </span>
                      {workspace.is_active && (
                        <span className="ml-2 text-xs px-2 py-0.5 bg-green-500/20 text-green-600 rounded-full">
                          Active
                        </span>
                      )}
                      {workspace.description && (
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {workspace.description}
                        </p>
                      )}
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground font-mono truncate max-w-xs" title={workspace.path}>
                      {workspace.path}
                    </span>
                    <button
                      onClick={() => copyToClipboard(workspace.path)}
                      className="p-1 text-muted-foreground hover:text-foreground transition-colors flex-shrink-0"
                      title="Copy path"
                    >
                      {copiedPath === workspace.path ? (
                        <svg className="w-3.5 h-3.5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                      ) : (
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                        </svg>
                      )}
                    </button>
                  </div>
                </td>
                <td className="px-4 py-3 text-muted-foreground text-sm">
                  {formatDate(workspace.last_accessed_at)}
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="flex items-center justify-end gap-2">
                    {!workspace.is_active && (
                      <>
                        {activatingId === workspace.workspace_id ? (
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-amber-600">
                              This will log out all users!
                            </span>
                            <button
                              onClick={() => handleActivate(workspace.workspace_id)}
                              className="px-3 py-1 text-sm text-amber-600 font-medium hover:opacity-80 transition-colors"
                            >
                              Confirm
                            </button>
                            <button
                              onClick={() => setActivatingId(null)}
                              className="px-3 py-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
                            >
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <button
                            onClick={() => setActivatingId(workspace.workspace_id)}
                            className="px-3 py-1 text-sm text-primary hover:opacity-80 transition-colors"
                          >
                            Activate
                          </button>
                        )}
                      </>
                    )}
                    {!workspace.is_active && (
                      <>
                        {deletingId === workspace.workspace_id ? (
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-destructive">
                              Delete "{workspace.name}"?
                            </span>
                            <button
                              onClick={() => handleDelete(workspace.workspace_id)}
                              className="px-3 py-1 text-sm text-destructive font-medium hover:opacity-80 transition-colors"
                            >
                              Confirm
                            </button>
                            <button
                              onClick={() => setDeletingId(null)}
                              className="px-3 py-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
                            >
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <button
                            onClick={() => setDeletingId(workspace.workspace_id)}
                            className="px-3 py-1 text-sm text-destructive hover:opacity-80 transition-colors"
                          >
                            Delete
                          </button>
                        )}
                      </>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {workspaces.length === 0 && (
          <div className="p-8 text-center text-muted-foreground">
            No workspaces found. Create one to get started.
          </div>
        )}
      </div>

      {/* Help text */}
      <div className="mt-6 p-4 bg-muted/50 rounded-lg border border-border">
        <h4 className="text-sm font-medium text-foreground mb-2">About Workspaces</h4>
        <ul className="text-xs text-muted-foreground space-y-1">
          <li>
            Workspaces allow you to switch between different storage locations at runtime.
          </li>
          <li>
            Workspace paths are auto-generated under the <code className="font-mono">workspaces/</code> directory.
          </li>
          <li>
            Activating a workspace will clear all sessions and log out all users.
          </li>
          <li>
            Deleting a workspace only removes it from the registry; files on disk are preserved.
          </li>
          <li>
            Each workspace has its own claims, runs, logs, and configuration.
          </li>
        </ul>
      </div>
    </div>
  );
}
