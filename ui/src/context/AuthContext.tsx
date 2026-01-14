import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';

// Types
export type Role = 'admin' | 'reviewer' | 'operator' | 'auditor';

export type Screen =
  | 'batch-workspace'
  | 'document-review'
  | 'classification-review'
  | 'claims-table'
  | 'claim-review'
  | 'pipeline'
  | 'ground-truth'
  | 'templates'
  | 'new-claim'
  | 'compliance'
  | 'admin';

export interface User {
  username: string;
  role: Role;
}

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  switchUser: (user: User) => void;
  canEdit: (screen: Screen) => boolean;
  canAccess: (screen: Screen) => boolean;
}

const AuthContext = createContext<AuthContextType | null>(null);

// Permission matrix
const SCREEN_ACCESS: Record<Screen, Role[]> = {
  'batch-workspace': ['admin', 'reviewer', 'operator', 'auditor'],
  'document-review': ['admin', 'reviewer', 'operator', 'auditor'],
  'classification-review': ['admin', 'reviewer', 'operator', 'auditor'],
  'claims-table': ['admin', 'reviewer', 'operator', 'auditor'],
  'claim-review': ['admin', 'reviewer', 'operator', 'auditor'],
  'pipeline': ['admin', 'operator', 'auditor'],
  'ground-truth': ['admin', 'reviewer', 'operator', 'auditor'],
  'templates': ['admin', 'reviewer', 'auditor'],
  'new-claim': ['admin', 'reviewer', 'operator'],
  'compliance': ['admin', 'auditor'],
  'admin': ['admin'],
};

const SCREEN_EDIT: Record<Screen, Role[]> = {
  'batch-workspace': ['admin', 'reviewer', 'operator'],
  'document-review': ['admin', 'reviewer'],
  'classification-review': ['admin', 'reviewer'],
  'claims-table': ['admin', 'reviewer', 'operator'],
  'claim-review': ['admin', 'reviewer'],
  'pipeline': ['admin', 'operator'],
  'ground-truth': ['admin', 'reviewer'],
  'templates': ['admin'],
  'new-claim': ['admin', 'reviewer', 'operator'],
  'compliance': ['admin'],
  'admin': ['admin'],
};

const TOKEN_KEY = 'auth_token';
const USER_KEY = 'auth_user';

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Restore session from localStorage on mount
  useEffect(() => {
    const restoreSession = async () => {
      const token = localStorage.getItem(TOKEN_KEY);
      const savedUser = localStorage.getItem(USER_KEY);

      if (token && savedUser) {
        try {
          // Validate token with server
          const response = await fetch('/api/auth/me', {
            headers: {
              'Authorization': `Bearer ${token}`,
            },
          });

          if (response.ok) {
            const userData = await response.json();
            setUser(userData);
          } else {
            // Token invalid, clear storage
            localStorage.removeItem(TOKEN_KEY);
            localStorage.removeItem(USER_KEY);
          }
        } catch (error) {
          console.error('Failed to restore session:', error);
          localStorage.removeItem(TOKEN_KEY);
          localStorage.removeItem(USER_KEY);
        }
      }

      setIsLoading(false);
    };

    restoreSession();
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ username, password }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Login failed');
    }

    const data = await response.json();
    localStorage.setItem(TOKEN_KEY, data.token);
    localStorage.setItem(USER_KEY, JSON.stringify(data.user));
    setUser(data.user);
  }, []);

  const logout = useCallback(async () => {
    const token = localStorage.getItem(TOKEN_KEY);

    if (token) {
      try {
        await fetch('/api/auth/logout', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        });
      } catch (error) {
        console.error('Logout request failed:', error);
      }
    }

    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setUser(null);
  }, []);

  // Admin-only: switch to a different user profile (for testing)
  const switchUser = useCallback((newUser: User) => {
    localStorage.setItem(USER_KEY, JSON.stringify(newUser));
    setUser(newUser);
  }, []);

  const canAccess = useCallback((screen: Screen): boolean => {
    if (!user) return false;
    const allowedRoles = SCREEN_ACCESS[screen];
    return allowedRoles.includes(user.role);
  }, [user]);

  const canEdit = useCallback((screen: Screen): boolean => {
    if (!user) return false;
    const allowedRoles = SCREEN_EDIT[screen];
    return allowedRoles.includes(user.role);
  }, [user]);

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        login,
        logout,
        switchUser,
        canEdit,
        canAccess,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

// Helper to get auth token for API requests
export function getAuthToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
