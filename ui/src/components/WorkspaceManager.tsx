import React, { useState, useEffect, useRef } from 'react';
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

  // Confirmation states
  const [activatingId, setActivatingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // Action menu
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  // Index rebuild state
  const [rebuildingIndex, setRebuildingIndex] = useState(false);
  const [rebuildResult, setRebuildResult] = useState<RebuildIndexResponse | null>(null);

  // Clipboard state
  const [copiedPath, setCopiedPath] = useState<string | null>(null);

  useEffect(() => {
    loadWorkspaces();
  }, []);

  // Close menu on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setOpenMenuId(null);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
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
      alert(
        `Workspace "${workspaceId}" activated.\n\n` +
        `${result.sessions_cleared} session(s) cleared.\n\n` +
        `You will be logged out and redirected to the login page.`
      );
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
    });
  }

  function formatTime(dateStr: string | null) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
    });
  }

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
      <div className="flex items-center justify-center py-16">
        <div className="flex flex-col items-center gap-6">
          <div className="relative">
            <div className="w-12 h-12 border-2 border-primary/30 rounded-full" />
            <div className="absolute inset-0 w-12 h-12 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          </div>
          <p className="text-muted-foreground text-sm tracking-wide">Loading workspaces...</p>
        </div>
      </div>
    );
  }

  const activeWorkspace = workspaces.find(ws => ws.is_active);
  const inactiveWorkspaces = workspaces.filter(ws => !ws.is_active);

  return (
    <div className="space-y-8">
      {/* Active Workspace Card */}
      {activeWorkspace && (
        <div className="bg-gradient-to-br from-emerald-500/10 via-emerald-500/5 to-transparent rounded-xl border border-emerald-500/30 overflow-hidden">
          <div className="p-6">
            <div className="flex items-start justify-between">
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-xl bg-emerald-500/20 flex items-center justify-center">
                  <div className="w-3 h-3 bg-emerald-500 rounded-full animate-pulse" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-lg font-semibold text-foreground">{activeWorkspace.name}</h3>
                    <span className="px-2 py-0.5 text-xs font-medium bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 rounded-full border border-emerald-500/30">
                      Active
                    </span>
                  </div>
                  {activeWorkspace.description && (
                    <p className="text-sm text-muted-foreground mt-1">{activeWorkspace.description}</p>
                  )}
                </div>
              </div>
              <button
                onClick={handleRebuildIndex}
                disabled={rebuildingIndex}
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 rounded-lg hover:bg-emerald-500/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {rebuildingIndex ? (
                  <>
                    <div className="w-4 h-4 border-2 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin" />
                    Rebuilding...
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    Rebuild Index
                  </>
                )}
              </button>
            </div>

            {/* Path Display */}
            <div className="mt-4 p-3 bg-background/50 rounded-lg border border-border">
              <div className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-2 min-w-0 flex-1">
                  <svg className="w-4 h-4 text-muted-foreground flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                  </svg>
                  <code className="text-sm text-muted-foreground font-mono truncate" title={activeWorkspace.path}>
                    {activeWorkspace.path}
                  </code>
                </div>
                <button
                  onClick={() => copyToClipboard(activeWorkspace.path)}
                  className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors flex-shrink-0"
                  title="Copy path"
                >
                  {copiedPath === activeWorkspace.path ? (
                    <svg className="w-4 h-4 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  ) : (
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                  )}
                </button>
              </div>
            </div>

            {/* Rebuild Result */}
            {rebuildResult && (
              <div className="mt-4 flex items-center gap-2 text-sm text-emerald-700 dark:text-emerald-300">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                Index rebuilt: {rebuildResult.stats.doc_count} docs, {rebuildResult.stats.claim_count} claims, {rebuildResult.stats.run_count} runs
              </div>
            )}
          </div>
        </div>
      )}

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground tracking-tight">Workspaces</h1>
          <p className="mt-1 text-muted-foreground">
            {workspaces.length} workspace{workspaces.length !== 1 ? 's' : ''} configured
          </p>
        </div>
        {!showCreateForm && (
          <button
            onClick={() => setShowCreateForm(true)}
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-primary text-primary-foreground rounded-lg font-medium text-sm hover:opacity-90 transition-all duration-200 shadow-md hover:shadow-lg"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Create Workspace
          </button>
        )}
      </div>

      {/* Error Banner */}
      {error && (
        <div className="flex items-center gap-3 p-4 rounded-lg bg-destructive/10 border border-destructive/30">
          <svg className="w-5 h-5 text-destructive flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-sm text-destructive flex-1">{error}</p>
          <button
            onClick={() => setError(null)}
            className="text-destructive/70 hover:text-destructive transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      )}

      {/* Create Form */}
      {showCreateForm && (
        <div className="bg-card rounded-xl border border-border shadow-lg overflow-hidden">
          <div className="px-6 py-4 border-b border-border bg-muted/30">
            <h2 className="text-lg font-semibold text-foreground">Create New Workspace</h2>
            <p className="text-sm text-muted-foreground mt-0.5">Set up an isolated environment for your data</p>
          </div>
          <form onSubmit={handleCreate} className="p-6">
            {formError && (
              <div className="mb-6 flex items-center gap-3 p-4 rounded-lg bg-destructive/10 border border-destructive/30">
                <svg className="w-5 h-5 text-destructive flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <p className="text-sm text-destructive">{formError}</p>
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="block text-sm font-medium text-foreground">
                  Name
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-4 py-2.5 bg-background border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all"
                  placeholder="e.g., Production, Staging, Test"
                  required
                />
              </div>

              <div className="space-y-2">
                <label className="block text-sm font-medium text-foreground">
                  Description <span className="text-muted-foreground font-normal">(optional)</span>
                </label>
                <input
                  type="text"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  className="w-full px-4 py-2.5 bg-background border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all"
                  placeholder="e.g., For integration testing"
                />
              </div>
            </div>

            <div className="flex items-center gap-3 mt-8 pt-6 border-t border-border">
              <button
                type="submit"
                disabled={formLoading}
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-primary text-primary-foreground rounded-lg font-medium text-sm hover:opacity-90 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {formLoading ? (
                  <>
                    <div className="w-4 h-4 border-2 border-primary-foreground/30 border-t-primary-foreground rounded-full animate-spin" />
                    Creating...
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    Create Workspace
                  </>
                )}
              </button>
              <button
                type="button"
                onClick={resetForm}
                className="px-5 py-2.5 text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg transition-all"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Activation Confirmation Modal */}
      {activatingId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-background/80 backdrop-blur-sm" onClick={() => setActivatingId(null)} />
          <div className="relative bg-card rounded-xl border border-border shadow-2xl p-6 max-w-md w-full mx-4">
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 rounded-full bg-amber-500/10 flex items-center justify-center flex-shrink-0">
                <svg className="w-6 h-6 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-foreground">Activate Workspace</h3>
                <p className="mt-2 text-sm text-muted-foreground">
                  Activating <span className="font-medium text-foreground">{workspaces.find(w => w.workspace_id === activatingId)?.name}</span> will log out all users and clear all sessions.
                </p>
              </div>
            </div>
            <div className="flex items-center justify-end gap-3 mt-6 pt-4 border-t border-border">
              <button
                onClick={() => setActivatingId(null)}
                className="px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg transition-all"
              >
                Cancel
              </button>
              <button
                onClick={() => handleActivate(activatingId)}
                className="px-4 py-2 text-sm font-medium bg-amber-600 text-white rounded-lg hover:opacity-90 transition-all"
              >
                Activate Workspace
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deletingId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-background/80 backdrop-blur-sm" onClick={() => setDeletingId(null)} />
          <div className="relative bg-card rounded-xl border border-border shadow-2xl p-6 max-w-md w-full mx-4">
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 rounded-full bg-destructive/10 flex items-center justify-center flex-shrink-0">
                <svg className="w-6 h-6 text-destructive" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-foreground">Delete Workspace</h3>
                <p className="mt-2 text-sm text-muted-foreground">
                  Remove <span className="font-medium text-foreground">{workspaces.find(w => w.workspace_id === deletingId)?.name}</span> from the registry? Files on disk will be preserved.
                </p>
              </div>
            </div>
            <div className="flex items-center justify-end gap-3 mt-6 pt-4 border-t border-border">
              <button
                onClick={() => setDeletingId(null)}
                className="px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg transition-all"
              >
                Cancel
              </button>
              <button
                onClick={() => handleDelete(deletingId)}
                className="px-4 py-2 text-sm font-medium bg-destructive text-destructive-foreground rounded-lg hover:opacity-90 transition-all"
              >
                Delete Workspace
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Workspaces Grid */}
      {inactiveWorkspaces.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {inactiveWorkspaces.map((workspace) => (
            <div
              key={workspace.workspace_id}
              className="group relative bg-card rounded-xl border border-border p-5 transition-all duration-200 hover:shadow-lg hover:border-primary/30"
            >
              {/* Workspace Info */}
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-xl bg-muted flex items-center justify-center text-lg font-semibold text-muted-foreground">
                  {workspace.name.charAt(0).toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="text-base font-semibold text-foreground truncate">
                    {workspace.name}
                  </h3>
                  {workspace.description && (
                    <p className="text-sm text-muted-foreground mt-0.5 truncate">{workspace.description}</p>
                  )}
                </div>

                {/* Actions Menu */}
                <div className="relative" ref={openMenuId === workspace.workspace_id ? menuRef : null}>
                  <button
                    onClick={() => setOpenMenuId(openMenuId === workspace.workspace_id ? null : workspace.workspace_id)}
                    className="p-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-all opacity-0 group-hover:opacity-100 focus:opacity-100"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z" />
                    </svg>
                  </button>
                  {openMenuId === workspace.workspace_id && (
                    <div className="absolute right-0 top-full mt-1 w-44 bg-popover border border-border rounded-lg shadow-xl z-10 py-1 overflow-hidden">
                      <button
                        onClick={() => {
                          setActivatingId(workspace.workspace_id);
                          setOpenMenuId(null);
                        }}
                        className="w-full px-4 py-2 text-left text-sm text-foreground hover:bg-muted transition-colors flex items-center gap-2"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                        </svg>
                        Activate
                      </button>
                      <button
                        onClick={() => {
                          setDeletingId(workspace.workspace_id);
                          setOpenMenuId(null);
                        }}
                        className="w-full px-4 py-2 text-left text-sm text-destructive hover:bg-destructive/10 transition-colors flex items-center gap-2"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                        Delete
                      </button>
                    </div>
                  )}
                </div>
              </div>

              {/* Path Display */}
              <div className="mt-4 p-3 bg-muted/50 rounded-lg">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2 min-w-0 flex-1">
                    <svg className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                    </svg>
                    <code className="text-xs text-muted-foreground font-mono truncate" title={workspace.path}>
                      {workspace.path}
                    </code>
                  </div>
                  <button
                    onClick={() => copyToClipboard(workspace.path)}
                    className="p-1 rounded text-muted-foreground hover:text-foreground transition-colors flex-shrink-0"
                    title="Copy path"
                  >
                    {copiedPath === workspace.path ? (
                      <svg className="w-3.5 h-3.5 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                    ) : (
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                      </svg>
                    )}
                  </button>
                </div>
              </div>

              {/* Metadata */}
              <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>Last accessed {formatDate(workspace.last_accessed_at)}</span>
                {workspace.last_accessed_at && (
                  <>
                    <span className="text-border">·</span>
                    <span>{formatTime(workspace.last_accessed_at)}</span>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Empty State */}
      {workspaces.length === 0 && (
        <div className="text-center py-16">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-muted flex items-center justify-center">
            <svg className="w-8 h-8 text-muted-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
          </div>
          <h3 className="text-lg font-medium text-foreground">No workspaces configured</h3>
          <p className="mt-1 text-sm text-muted-foreground">Create your first workspace to get started.</p>
        </div>
      )}

      {/* Help Section */}
      <div className="bg-muted/30 rounded-xl border border-border p-6">
        <h4 className="text-sm font-semibold text-foreground flex items-center gap-2">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          About Workspaces
        </h4>
        <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
          <li className="flex items-start gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground mt-1.5 flex-shrink-0" />
            Workspaces allow you to switch between different storage locations at runtime.
          </li>
          <li className="flex items-start gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground mt-1.5 flex-shrink-0" />
            Paths are auto-generated under the <code className="px-1 py-0.5 bg-muted rounded text-xs font-mono">workspaces/</code> directory.
          </li>
          <li className="flex items-start gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground mt-1.5 flex-shrink-0" />
            Activating a workspace will clear all sessions and log out all users.
          </li>
          <li className="flex items-start gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground mt-1.5 flex-shrink-0" />
            Deleting a workspace only removes it from the registry; files on disk are preserved.
          </li>
        </ul>
      </div>
    </div>
  );
}
