import React, { useState, useEffect } from 'react';
import { listUsers, createUser, updateUser, deleteUser, type UserResponse } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { WorkspaceManager } from './WorkspaceManager';

const ROLES = ['admin', 'reviewer', 'operator', 'auditor'] as const;
type AdminTab = 'users' | 'workspaces';

interface UserFormData {
  username: string;
  password: string;
  role: string;
}

const roleConfig: Record<string, { label: string; color: string }> = {
  admin: {
    label: 'Admin',
    color: 'bg-violet-100 text-violet-700 dark:bg-violet-500/20 dark:text-violet-300',
  },
  reviewer: {
    label: 'Reviewer',
    color: 'bg-sky-100 text-sky-700 dark:bg-sky-500/20 dark:text-sky-300',
  },
  operator: {
    label: 'Operator',
    color: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300',
  },
  auditor: {
    label: 'Auditor',
    color: 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300',
  },
};

export function AdminPage() {
  const { user: currentUser, switchUser } = useAuth();
  const [activeTab, setActiveTab] = useState<AdminTab>('users');
  const [users, setUsers] = useState<UserResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editingUser, setEditingUser] = useState<string | null>(null);
  const [formData, setFormData] = useState<UserFormData>({
    username: '',
    password: '',
    role: 'reviewer',
  });
  const [formError, setFormError] = useState<string | null>(null);
  const [formLoading, setFormLoading] = useState(false);

  // Delete confirmation
  const [deletingUser, setDeletingUser] = useState<string | null>(null);

  useEffect(() => {
    loadUsers();
  }, []);

  async function loadUsers() {
    try {
      setLoading(true);
      setError(null);
      const data = await listUsers();
      setUsers(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load users');
    } finally {
      setLoading(false);
    }
  }

  function resetForm() {
    setFormData({ username: '', password: '', role: 'reviewer' });
    setFormError(null);
    setShowCreateForm(false);
    setEditingUser(null);
  }

  async function handleCreateUser(e: React.FormEvent) {
    e.preventDefault();
    if (!formData.username || !formData.password) {
      setFormError('Username and password are required');
      return;
    }

    try {
      setFormLoading(true);
      setFormError(null);
      await createUser(formData.username, formData.password, formData.role);
      await loadUsers();
      resetForm();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Failed to create user');
    } finally {
      setFormLoading(false);
    }
  }

  async function handleUpdateUser(e: React.FormEvent) {
    e.preventDefault();
    if (!editingUser) return;

    const updateData: { password?: string; role?: string } = {};
    if (formData.password) updateData.password = formData.password;
    if (formData.role) updateData.role = formData.role;

    try {
      setFormLoading(true);
      setFormError(null);
      await updateUser(editingUser, updateData);
      await loadUsers();
      resetForm();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Failed to update user');
    } finally {
      setFormLoading(false);
    }
  }

  async function handleDeleteUser(username: string) {
    try {
      await deleteUser(username);
      setDeletingUser(null);
      await loadUsers();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete user');
    }
  }

  function startEdit(user: UserResponse) {
    setEditingUser(user.username);
    setFormData({
      username: user.username,
      password: '',
      role: user.role,
    });
    setShowCreateForm(false);
    setFormError(null);
  }

  function formatDate(dateStr: string) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full min-h-[400px]">
        <div className="flex flex-col items-center gap-4">
          <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          <p className="text-muted-foreground text-sm">Loading...</p>
        </div>
      </div>
    );
  }

  function handleProfileSwitch(username: string) {
    const targetUser = users.find(u => u.username === username);
    if (targetUser) {
      switchUser({ username: targetUser.username, role: targetUser.role as 'admin' | 'reviewer' | 'operator' | 'auditor' });
    }
  }

  return (
    <div className="min-h-full bg-background">
      {/* Tab Navigation */}
      <div className="border-b border-border">
        <div className="px-6 lg:px-8">
          <nav className="flex gap-6" aria-label="Tabs">
            <button
              onClick={() => setActiveTab('users')}
              className={`relative py-4 text-sm font-medium transition-colors ${
                activeTab === 'users'
                  ? 'text-foreground'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              Users
              {activeTab === 'users' && (
                <span className="absolute inset-x-0 bottom-0 h-0.5 bg-primary" />
              )}
            </button>
            <button
              onClick={() => setActiveTab('workspaces')}
              className={`relative py-4 text-sm font-medium transition-colors ${
                activeTab === 'workspaces'
                  ? 'text-foreground'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              Workspaces
              {activeTab === 'workspaces' && (
                <span className="absolute inset-x-0 bottom-0 h-0.5 bg-primary" />
              )}
            </button>
          </nav>
        </div>
      </div>

      {/* Main Content */}
      <div className="px-6 lg:px-8 py-6">
        {activeTab === 'workspaces' ? (
          <WorkspaceManager />
        ) : (
          <div className="space-y-6">
            {/* Header with Actions */}
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-lg font-semibold text-foreground">User Management</h1>
                <p className="text-sm text-muted-foreground">{users.length} users</p>
              </div>
              <div className="flex items-center gap-3">
                {/* Profile Switcher */}
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-muted-foreground">Acting as:</span>
                  <select
                    value={currentUser?.username || ''}
                    onChange={(e) => handleProfileSwitch(e.target.value)}
                    className="px-2 py-1 bg-muted border-0 rounded text-sm font-medium text-foreground focus:outline-none focus:ring-2 focus:ring-ring cursor-pointer"
                  >
                    {users.map((user) => (
                      <option key={user.username} value={user.username}>
                        {user.username} ({user.role})
                      </option>
                    ))}
                  </select>
                </div>
                <div className="w-px h-6 bg-border" />
                {!showCreateForm && !editingUser && (
                  <button
                    onClick={() => {
                      setShowCreateForm(true);
                      setFormData({ username: '', password: '', role: 'reviewer' });
                    }}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:opacity-90 transition-opacity"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                    Add User
                  </button>
                )}
              </div>
            </div>

            {/* Error Banner */}
            {error && (
              <div className="flex items-center justify-between gap-3 px-4 py-3 rounded-lg bg-destructive/10 border border-destructive/20">
                <p className="text-sm text-destructive">{error}</p>
                <button onClick={() => setError(null)} className="text-destructive/60 hover:text-destructive">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            )}

            {/* Create/Edit Form */}
            {(showCreateForm || editingUser) && (
              <div className="p-4 bg-muted/50 rounded-lg border border-border">
                <h2 className="text-sm font-medium text-foreground mb-4">
                  {editingUser ? `Edit "${editingUser}"` : 'New User'}
                </h2>
                <form onSubmit={editingUser ? handleUpdateUser : handleCreateUser}>
                  {formError && (
                    <div className="mb-4 px-3 py-2 rounded bg-destructive/10 border border-destructive/20">
                      <p className="text-sm text-destructive">{formError}</p>
                    </div>
                  )}

                  <div className="flex flex-wrap items-end gap-4">
                    {!editingUser && (
                      <div className="flex-1 min-w-[200px]">
                        <label className="block text-xs font-medium text-muted-foreground mb-1.5">
                          Username
                        </label>
                        <input
                          type="text"
                          value={formData.username}
                          onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                          className="w-full px-3 py-2 bg-background border border-border rounded-md text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                          placeholder="username"
                          required
                        />
                      </div>
                    )}

                    <div className="flex-1 min-w-[200px]">
                      <label className="block text-xs font-medium text-muted-foreground mb-1.5">
                        Password {editingUser && <span className="font-normal">(leave blank to keep)</span>}
                      </label>
                      <input
                        type="password"
                        value={formData.password}
                        onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                        className="w-full px-3 py-2 bg-background border border-border rounded-md text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                        placeholder={editingUser ? '••••••••' : 'password'}
                        required={!editingUser}
                      />
                    </div>

                    <div className="w-[160px]">
                      <label className="block text-xs font-medium text-muted-foreground mb-1.5">
                        Role
                      </label>
                      <select
                        value={formData.role}
                        onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                        disabled={editingUser === currentUser?.username}
                        className="w-full px-3 py-2 bg-background border border-border rounded-md text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
                      >
                        {ROLES.map((role) => (
                          <option key={role} value={role}>
                            {roleConfig[role].label}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        type="submit"
                        disabled={formLoading}
                        className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
                      >
                        {formLoading ? 'Saving...' : editingUser ? 'Update' : 'Create'}
                      </button>
                      <button
                        type="button"
                        onClick={resetForm}
                        className="px-4 py-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                </form>
              </div>
            )}

            {/* Delete Confirmation Modal */}
            {deletingUser && (
              <div className="fixed inset-0 z-50 flex items-center justify-center">
                <div className="absolute inset-0 bg-background/80 backdrop-blur-sm" onClick={() => setDeletingUser(null)} />
                <div className="relative bg-card rounded-lg border border-border shadow-lg p-5 max-w-sm w-full mx-4">
                  <h3 className="text-base font-semibold text-foreground">Delete User</h3>
                  <p className="mt-2 text-sm text-muted-foreground">
                    Are you sure you want to delete <span className="font-medium text-foreground">{deletingUser}</span>?
                  </p>
                  <div className="flex items-center justify-end gap-2 mt-5">
                    <button
                      onClick={() => setDeletingUser(null)}
                      className="px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={() => handleDeleteUser(deletingUser)}
                      className="px-3 py-1.5 text-sm font-medium bg-destructive text-destructive-foreground rounded-md hover:opacity-90 transition-opacity"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Users Table */}
            <div className="bg-card rounded-lg border border-border overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border bg-muted/50">
                    <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                      User
                    </th>
                    <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                      Role
                    </th>
                    <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                      Created
                    </th>
                    <th className="text-right text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {users.map((user) => (
                    <tr
                      key={user.username}
                      className={`hover:bg-muted/30 transition-colors ${
                        user.username === currentUser?.username ? 'bg-primary/5' : ''
                      }`}
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                            user.username === currentUser?.username
                              ? 'bg-primary text-primary-foreground'
                              : 'bg-muted text-muted-foreground'
                          }`}>
                            {user.username.charAt(0).toUpperCase()}
                          </div>
                          <div>
                            <span className="text-sm font-medium text-foreground">{user.username}</span>
                            {user.username === currentUser?.username && (
                              <span className="ml-2 text-xs text-primary">(you)</span>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex px-2 py-0.5 text-xs font-medium rounded ${roleConfig[user.role]?.color || 'bg-muted text-muted-foreground'}`}>
                          {roleConfig[user.role]?.label || user.role}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm text-muted-foreground">
                        {formatDate(user.created_at)}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            onClick={() => startEdit(user)}
                            className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted rounded transition-colors"
                            title="Edit user"
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                            </svg>
                          </button>
                          {user.username !== currentUser?.username && (
                            <button
                              onClick={() => setDeletingUser(user.username)}
                              className="p-1.5 text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded transition-colors"
                              title="Delete user"
                            >
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                              </svg>
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {users.length === 0 && (
                <div className="px-4 py-12 text-center">
                  <p className="text-sm text-muted-foreground">No users found</p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
