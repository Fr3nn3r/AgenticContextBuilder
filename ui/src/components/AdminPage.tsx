import React, { useState, useEffect, useRef } from 'react';
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

const roleConfig: Record<string, { label: string; color: string; description: string }> = {
  admin: {
    label: 'Admin',
    color: 'bg-violet-500/15 text-violet-700 dark:text-violet-300 border-violet-500/30',
    description: 'Full system access'
  },
  reviewer: {
    label: 'Reviewer',
    color: 'bg-sky-500/15 text-sky-700 dark:text-sky-300 border-sky-500/30',
    description: 'Review and approve'
  },
  operator: {
    label: 'Operator',
    color: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/30',
    description: 'Process claims'
  },
  auditor: {
    label: 'Auditor',
    color: 'bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/30',
    description: 'Read-only audit access'
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

  // Action menu
  const [openMenuUser, setOpenMenuUser] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadUsers();
  }, []);

  // Close menu on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setOpenMenuUser(null);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
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
    setOpenMenuUser(null);
  }

  function formatDate(dateStr: string) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  }

  function formatTime(dateStr: string) {
    const date = new Date(dateStr);
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full min-h-[400px]">
        <div className="flex flex-col items-center gap-6">
          <div className="relative">
            <div className="w-12 h-12 border-2 border-primary/30 rounded-full" />
            <div className="absolute inset-0 w-12 h-12 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          </div>
          <p className="text-muted-foreground text-sm tracking-wide">Loading users...</p>
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

  const usersByRole = ROLES.map(role => ({
    role,
    users: users.filter(u => u.role === role),
  })).filter(group => group.users.length > 0);

  return (
    <div className="min-h-full">
      {/* Header Section */}
      <div className="border-b border-border bg-card/50">
        <div className="px-8 py-6">
          {/* Profile Switcher - Compact */}
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-3 px-4 py-2 bg-background rounded-lg border border-border">
                <div className="w-8 h-8 bg-primary/20 rounded-full flex items-center justify-center">
                  <span className="text-sm font-semibold text-primary">
                    {currentUser?.username.charAt(0).toUpperCase()}
                  </span>
                </div>
                <div className="flex flex-col">
                  <span className="text-sm font-medium text-foreground">{currentUser?.username}</span>
                  <span className="text-xs text-muted-foreground capitalize">{currentUser?.role}</span>
                </div>
              </div>
              <select
                value={currentUser?.username || ''}
                onChange={(e) => handleProfileSwitch(e.target.value)}
                className="px-3 py-2 bg-background border border-border rounded-lg text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring cursor-pointer hover:border-primary/50 transition-colors"
              >
                {users.map((user) => (
                  <option key={user.username} value={user.username}>
                    Switch to {user.username}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Tab Navigation */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setActiveTab('users')}
              className={`px-5 py-2.5 text-sm font-medium rounded-lg transition-all duration-200 ${
                activeTab === 'users'
                  ? 'bg-primary text-primary-foreground shadow-md'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted'
              }`}
            >
              <span className="flex items-center gap-2">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
                User Management
              </span>
            </button>
            <button
              onClick={() => setActiveTab('workspaces')}
              className={`px-5 py-2.5 text-sm font-medium rounded-lg transition-all duration-200 ${
                activeTab === 'workspaces'
                  ? 'bg-primary text-primary-foreground shadow-md'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted'
              }`}
            >
              <span className="flex items-center gap-2">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                </svg>
                Workspaces
              </span>
            </button>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="px-8 py-8">
        {activeTab === 'workspaces' ? (
          <WorkspaceManager />
        ) : (
          <div className="space-y-8">
            {/* Page Header */}
            <div className="flex items-start justify-between">
              <div>
                <h1 className="text-2xl font-semibold text-foreground tracking-tight">Users</h1>
                <p className="mt-1 text-muted-foreground">
                  {users.length} user{users.length !== 1 ? 's' : ''} across {usersByRole.length} role{usersByRole.length !== 1 ? 's' : ''}
                </p>
              </div>
              {!showCreateForm && !editingUser && (
                <button
                  onClick={() => {
                    setShowCreateForm(true);
                    setFormData({ username: '', password: '', role: 'reviewer' });
                  }}
                  className="inline-flex items-center gap-2 px-5 py-2.5 bg-primary text-primary-foreground rounded-lg font-medium text-sm hover:opacity-90 transition-all duration-200 shadow-md hover:shadow-lg"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                  Add User
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

            {/* Create/Edit Form */}
            {(showCreateForm || editingUser) && (
              <div className="bg-card rounded-xl border border-border shadow-lg overflow-hidden">
                <div className="px-6 py-4 border-b border-border bg-muted/30">
                  <h2 className="text-lg font-semibold text-foreground">
                    {editingUser ? `Edit User` : 'Create New User'}
                  </h2>
                  {editingUser && (
                    <p className="text-sm text-muted-foreground mt-0.5">Editing {editingUser}</p>
                  )}
                </div>
                <form onSubmit={editingUser ? handleUpdateUser : handleCreateUser} className="p-6">
                  {formError && (
                    <div className="mb-6 flex items-center gap-3 p-4 rounded-lg bg-destructive/10 border border-destructive/30">
                      <svg className="w-5 h-5 text-destructive flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      <p className="text-sm text-destructive">{formError}</p>
                    </div>
                  )}

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    {!editingUser && (
                      <div className="space-y-2">
                        <label className="block text-sm font-medium text-foreground">
                          Username
                        </label>
                        <input
                          type="text"
                          value={formData.username}
                          onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                          className="w-full px-4 py-2.5 bg-background border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all"
                          placeholder="Enter username"
                          required
                        />
                      </div>
                    )}

                    <div className="space-y-2">
                      <label className="block text-sm font-medium text-foreground">
                        Password
                      </label>
                      <input
                        type="password"
                        value={formData.password}
                        onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                        className="w-full px-4 py-2.5 bg-background border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all"
                        placeholder={editingUser ? 'Leave blank to keep' : 'Enter password'}
                        required={!editingUser}
                      />
                      {editingUser && (
                        <p className="text-xs text-muted-foreground">Leave blank to keep current password</p>
                      )}
                    </div>

                    <div className="space-y-2">
                      <label className="block text-sm font-medium text-foreground">
                        Role
                      </label>
                      <select
                        value={formData.role}
                        onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                        disabled={editingUser === currentUser?.username}
                        className="w-full px-4 py-2.5 bg-background border border-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {ROLES.map((role) => (
                          <option key={role} value={role}>
                            {roleConfig[role].label} - {roleConfig[role].description}
                          </option>
                        ))}
                      </select>
                      {editingUser === currentUser?.username && (
                        <p className="text-xs text-amber-600">You cannot change your own role</p>
                      )}
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
                          Saving...
                        </>
                      ) : (
                        <>
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                          </svg>
                          {editingUser ? 'Update User' : 'Create User'}
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

            {/* Delete Confirmation Modal */}
            {deletingUser && (
              <div className="fixed inset-0 z-50 flex items-center justify-center">
                <div className="absolute inset-0 bg-background/80 backdrop-blur-sm" onClick={() => setDeletingUser(null)} />
                <div className="relative bg-card rounded-xl border border-border shadow-2xl p-6 max-w-md w-full mx-4">
                  <div className="flex items-start gap-4">
                    <div className="w-12 h-12 rounded-full bg-destructive/10 flex items-center justify-center flex-shrink-0">
                      <svg className="w-6 h-6 text-destructive" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </div>
                    <div className="flex-1">
                      <h3 className="text-lg font-semibold text-foreground">Delete User</h3>
                      <p className="mt-2 text-sm text-muted-foreground">
                        Are you sure you want to delete <span className="font-medium text-foreground">{deletingUser}</span>? This action cannot be undone.
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center justify-end gap-3 mt-6 pt-4 border-t border-border">
                    <button
                      onClick={() => setDeletingUser(null)}
                      className="px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg transition-all"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={() => handleDeleteUser(deletingUser)}
                      className="px-4 py-2 text-sm font-medium bg-destructive text-destructive-foreground rounded-lg hover:opacity-90 transition-all"
                    >
                      Delete User
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Users Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
              {users.map((user) => (
                <div
                  key={user.username}
                  className={`group relative bg-card rounded-xl border border-border p-5 transition-all duration-200 hover:shadow-lg hover:border-primary/30 ${
                    user.username === currentUser?.username ? 'ring-2 ring-primary/20' : ''
                  }`}
                >
                  {/* Current User Indicator */}
                  {user.username === currentUser?.username && (
                    <div className="absolute -top-px -right-px">
                      <div className="px-2.5 py-1 bg-primary text-primary-foreground text-xs font-medium rounded-bl-lg rounded-tr-xl">
                        You
                      </div>
                    </div>
                  )}

                  {/* User Info */}
                  <div className="flex items-start gap-4">
                    <div className={`w-12 h-12 rounded-xl flex items-center justify-center text-lg font-semibold ${
                      user.username === currentUser?.username
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-muted text-muted-foreground'
                    }`}>
                      {user.username.charAt(0).toUpperCase()}
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="text-base font-semibold text-foreground truncate">
                        {user.username}
                      </h3>
                      <div className={`inline-flex items-center gap-1.5 mt-1.5 px-2.5 py-1 text-xs font-medium rounded-md border ${roleConfig[user.role]?.color || 'bg-muted text-muted-foreground'}`}>
                        {roleConfig[user.role]?.label || user.role}
                      </div>
                    </div>

                    {/* Actions Menu */}
                    <div className="relative" ref={openMenuUser === user.username ? menuRef : null}>
                      <button
                        onClick={() => setOpenMenuUser(openMenuUser === user.username ? null : user.username)}
                        className="p-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-all opacity-0 group-hover:opacity-100 focus:opacity-100"
                      >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z" />
                        </svg>
                      </button>
                      {openMenuUser === user.username && (
                        <div className="absolute right-0 top-full mt-1 w-40 bg-popover border border-border rounded-lg shadow-xl z-10 py-1 overflow-hidden">
                          <button
                            onClick={() => startEdit(user)}
                            className="w-full px-4 py-2 text-left text-sm text-foreground hover:bg-muted transition-colors flex items-center gap-2"
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                            </svg>
                            Edit
                          </button>
                          {user.username !== currentUser?.username && (
                            <button
                              onClick={() => {
                                setDeletingUser(user.username);
                                setOpenMenuUser(null);
                              }}
                              className="w-full px-4 py-2 text-left text-sm text-destructive hover:bg-destructive/10 transition-colors flex items-center gap-2"
                            >
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                              </svg>
                              Delete
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Metadata */}
                  <div className="mt-4 pt-4 border-t border-border/50">
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                      <span>Created {formatDate(user.created_at)}</span>
                      <span className="text-border">·</span>
                      <span>{formatTime(user.created_at)}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Empty State */}
            {users.length === 0 && (
              <div className="text-center py-16">
                <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-muted flex items-center justify-center">
                  <svg className="w-8 h-8 text-muted-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                </div>
                <h3 className="text-lg font-medium text-foreground">No users found</h3>
                <p className="mt-1 text-sm text-muted-foreground">Get started by creating your first user.</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
