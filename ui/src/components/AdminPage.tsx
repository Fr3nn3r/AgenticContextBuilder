import React, { useState, useEffect } from 'react';
import { listUsers, createUser, updateUser, deleteUser, type UserResponse } from '../api/client';
import { useAuth } from '../context/AuthContext';

const ROLES = ['admin', 'reviewer', 'operator', 'auditor'] as const;

interface UserFormData {
  username: string;
  password: string;
  role: string;
}

export function AdminPage() {
  const { user: currentUser, switchUser } = useAuth();
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
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex flex-col items-center gap-4">
          <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          <p className="text-muted-foreground">Loading users...</p>
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
    <div className="p-6 max-w-4xl mx-auto">
      {/* Profile Switcher */}
      <div className="mb-6 p-3 bg-secondary rounded-lg border border-border flex items-center gap-3">
        <span className="text-sm font-medium text-muted-foreground">Switch Profile:</span>
        <select
          value={currentUser?.username || ''}
          onChange={(e) => handleProfileSwitch(e.target.value)}
          className="px-3 py-1.5 bg-input border border-border rounded-md text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        >
          {users.map((user) => (
            <option key={user.username} value={user.username}>
              {user.username} ({user.role})
            </option>
          ))}
        </select>
        <span className="text-xs text-muted-foreground ml-auto">
          Current: <span className="font-medium text-foreground">{currentUser?.username}</span> ({currentUser?.role})
        </span>
      </div>

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-foreground">User Management</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Manage users and their roles
          </p>
        </div>
        {!showCreateForm && !editingUser && (
          <button
            onClick={() => {
              setShowCreateForm(true);
              setFormData({ username: '', password: '', role: 'reviewer' });
            }}
            className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity"
          >
            Add User
          </button>
        )}
      </div>

      {error && (
        <div className="mb-4 p-3 rounded-md bg-destructive/10 border border-destructive/30">
          <p className="text-sm text-destructive">{error}</p>
        </div>
      )}

      {/* Create/Edit Form */}
      {(showCreateForm || editingUser) && (
        <div className="mb-6 p-4 bg-card rounded-lg border border-border">
          <h2 className="text-lg font-semibold text-foreground mb-4">
            {editingUser ? `Edit User: ${editingUser}` : 'Create New User'}
          </h2>
          <form onSubmit={editingUser ? handleUpdateUser : handleCreateUser} className="space-y-4">
            {formError && (
              <div className="p-3 rounded-md bg-destructive/10 border border-destructive/30">
                <p className="text-sm text-destructive">{formError}</p>
              </div>
            )}

            {!editingUser && (
              <div>
                <label className="block text-sm font-medium text-muted-foreground mb-1">
                  Username
                </label>
                <input
                  type="text"
                  value={formData.username}
                  onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                  className="w-full px-3 py-2 bg-input border border-border rounded-md text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                  placeholder="Enter username"
                  required
                />
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-muted-foreground mb-1">
                Password {editingUser && '(leave blank to keep current)'}
              </label>
              <input
                type="password"
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                className="w-full px-3 py-2 bg-input border border-border rounded-md text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                placeholder={editingUser ? 'Enter new password' : 'Enter password'}
                required={!editingUser}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-muted-foreground mb-1">
                Role
              </label>
              <select
                value={formData.role}
                onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                disabled={editingUser === currentUser?.username}
                className="w-full px-3 py-2 bg-input border border-border rounded-md text-foreground focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
              >
                {ROLES.map((role) => (
                  <option key={role} value={role}>
                    {role.charAt(0).toUpperCase() + role.slice(1)}
                  </option>
                ))}
              </select>
              {editingUser === currentUser?.username && (
                <p className="text-xs text-muted-foreground mt-1">
                  You cannot change your own role
                </p>
              )}
            </div>

            <div className="flex gap-2">
              <button
                type="submit"
                disabled={formLoading}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {formLoading ? 'Saving...' : editingUser ? 'Update User' : 'Create User'}
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

      {/* Users Table */}
      <div className="bg-card rounded-lg border border-border overflow-hidden">
        <table className="w-full">
          <thead className="bg-muted">
            <tr>
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                Username
              </th>
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                Role
              </th>
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                Created
              </th>
              <th className="px-4 py-3 text-right text-sm font-medium text-muted-foreground">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {users.map((user) => (
              <tr key={user.username} className="hover:bg-muted/50">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-primary/20 rounded-full flex items-center justify-center text-sm font-medium text-primary">
                      {user.username.charAt(0).toUpperCase()}
                    </div>
                    <span className="text-foreground font-medium">
                      {user.username}
                    </span>
                    {user.username === currentUser?.username && (
                      <span className="text-xs px-2 py-0.5 bg-primary/20 text-primary rounded-full">
                        You
                      </span>
                    )}
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span className="capitalize text-muted-foreground">
                    {user.role}
                  </span>
                </td>
                <td className="px-4 py-3 text-muted-foreground text-sm">
                  {formatDate(user.created_at)}
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="flex items-center justify-end gap-2">
                    <button
                      onClick={() => startEdit(user)}
                      className="px-3 py-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
                    >
                      Edit
                    </button>
                    {user.username !== currentUser?.username && (
                      <>
                        {deletingUser === user.username ? (
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => handleDeleteUser(user.username)}
                              className="px-3 py-1 text-sm text-destructive hover:opacity-80 transition-colors"
                            >
                              Confirm
                            </button>
                            <button
                              onClick={() => setDeletingUser(null)}
                              className="px-3 py-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
                            >
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <button
                            onClick={() => setDeletingUser(user.username)}
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

        {users.length === 0 && (
          <div className="p-8 text-center text-muted-foreground">
            No users found
          </div>
        )}
      </div>
    </div>
  );
}
