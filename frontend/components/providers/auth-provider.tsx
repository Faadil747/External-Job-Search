"use client";

import * as React from "react";

import { authApi, ApiError } from "@/lib/api";
import { useAuthStore } from "@/lib/auth-store";

/**
 * Hydrates auth state from localStorage on mount and fetches the current
 * user (`GET /auth/me`) when a token is present, so pages can trust
 * `useAuthStore` without every page re-implementing this dance.
 */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const hydrate = useAuthStore((s) => s.hydrate);
  const hydrated = useAuthStore((s) => s.hydrated);
  const accessToken = useAuthStore((s) => s.accessToken);
  const setUser = useAuthStore((s) => s.setUser);
  const logout = useAuthStore((s) => s.logout);

  React.useEffect(() => {
    hydrate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  React.useEffect(() => {
    if (!hydrated) return;
    if (!accessToken) return;

    let cancelled = false;
    authApi
      .me()
      .then((user) => {
        if (!cancelled) setUser(user);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          logout();
        }
      });
    return () => {
      cancelled = true;
    };
  }, [hydrated, accessToken, setUser, logout]);

  return <>{children}</>;
}
