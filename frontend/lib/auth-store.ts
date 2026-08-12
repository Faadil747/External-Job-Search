"use client";

import { create } from "zustand";
import type { UserPublic } from "./types";

// ---------------------------------------------------------------------------
// Auth state.
//
// Phase-1 tradeoff: tokens are kept in localStorage and attached manually as
// `Authorization: Bearer <token>` on every request. This is simple and works
// well for a client-rendered SPA-ish app, but it is XSS-exposed — a
// production hardening pass should move to httpOnly, SameSite=strict cookies
// issued by the backend and drop client-side token storage entirely.
// ---------------------------------------------------------------------------

const ACCESS_TOKEN_KEY = "jobmatch_access_token";
const REFRESH_TOKEN_KEY = "jobmatch_refresh_token";

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: UserPublic | null;
  hydrated: boolean;
  setTokens: (accessToken: string, refreshToken: string) => void;
  setUser: (user: UserPublic | null) => void;
  logout: () => void;
  hydrate: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  refreshToken: null,
  user: null,
  hydrated: false,

  setTokens: (accessToken, refreshToken) => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
      window.localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
    }
    set({ accessToken, refreshToken });
  },

  setUser: (user) => set({ user }),

  logout: () => {
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(ACCESS_TOKEN_KEY);
      window.localStorage.removeItem(REFRESH_TOKEN_KEY);
    }
    set({ accessToken: null, refreshToken: null, user: null });
  },

  hydrate: () => {
    if (typeof window === "undefined") return;
    const accessToken = window.localStorage.getItem(ACCESS_TOKEN_KEY);
    const refreshToken = window.localStorage.getItem(REFRESH_TOKEN_KEY);
    set({ accessToken, refreshToken, hydrated: true });
  },
}));

/** Read the current access token synchronously (for the API client). */
export function getStoredAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getStoredRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function storeTokens(accessToken: string, refreshToken: string) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  window.localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
}

export function clearStoredTokens() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
  window.localStorage.removeItem(REFRESH_TOKEN_KEY);
}
