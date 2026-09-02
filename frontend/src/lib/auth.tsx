'use client';

import { useRouter } from 'next/navigation';
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import { api, setAccessToken } from '@/lib/api';
import type { Role, User } from '@/types';

interface AuthState {
  user: User | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<User>;
  signOut: () => Promise<void>;
  refreshUser: () => Promise<void>;
  /** Server-side checks are authoritative; this only shapes the UI. */
  can: (permission: string) => boolean;
  hasRole: (...roles: Role[]) => boolean;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  // On mount, swap the httpOnly refresh cookie for a fresh access token.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await api.post<{ access: string; user: User }>(
          '/auth/refresh',
          undefined,
          { skipRetry: true },
        );
        if (!cancelled) {
          setAccessToken(data.access);
          setUser(data.user);
        }
      } catch {
        if (!cancelled) {
          setAccessToken(null);
          setUser(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const data = await api.post<{ access: string; user: User }>(
      '/auth/login',
      { email, password },
      { skipRetry: true },
    );
    setAccessToken(data.access);
    setUser(data.user);
    return data.user;
  }, []);

  const signOut = useCallback(async () => {
    try {
      await api.post('/auth/logout');
    } catch {
      /* signing out locally matters more than the server round-trip */
    }
    setAccessToken(null);
    setUser(null);
    router.push('/login');
  }, [router]);

  const refreshUser = useCallback(async () => {
    try {
      const data = await api.get<User>('/auth/me');
      setUser(data);
    } catch {
      /* leave the current user in place */
    }
  }, []);

  const can = useCallback(
    (permission: string) => Boolean(user?.permissions?.includes(permission)),
    [user],
  );

  const hasRole = useCallback(
    (...roles: Role[]) => Boolean(user && roles.includes(user.role)),
    [user],
  );

  const value = useMemo(
    () => ({ user, loading, signIn, signOut, refreshUser, can, hasRole }),
    [user, loading, signIn, signOut, refreshUser, can, hasRole],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside AuthProvider');
  return context;
}
