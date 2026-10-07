"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { ApiError, get, getToken, post, setToken, setUnauthorizedHandler } from "./api";
import type { Me } from "./types";

type Status = "loading" | "authenticated" | "anonymous";

interface AuthContextValue {
  status: Status;
  user: Me | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  setSession: (token: string, user: Me) => void;
  setUser: (user: Me) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

interface LoginResponse {
  access_token: string;
  user: Me;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>("loading");
  const [user, setUserState] = useState<Me | null>(null);
  const queryClient = useQueryClient();
  const router = useRouter();

  const logout = useCallback(() => {
    setToken(null);
    setUserState(null);
    setStatus("anonymous");
    queryClient.clear();
    router.replace("/login");
  }, [queryClient, router]);

  useEffect(() => {
    setUnauthorizedHandler(logout);
    return () => setUnauthorizedHandler(null);
  }, [logout]);

  useEffect(() => {
    if (!getToken()) {
      setStatus("anonymous");
      return;
    }
    get<Me>("/api/me")
      .then((me) => {
        setUserState(me);
        setStatus("authenticated");
      })
      .catch((err) => {
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) setToken(null);
        setStatus("anonymous");
      });
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const res = await post<LoginResponse>("/api/auth/login", { username, password });
    setToken(res.access_token);
    setUserState(res.user);
    setStatus("authenticated");
  }, []);

  const setSession = useCallback((token: string, me: Me) => {
    setToken(token);
    setUserState(me);
    setStatus("authenticated");
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ status, user, login, logout, setSession, setUser: setUserState }),
    [status, user, login, logout, setSession],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth outside AuthProvider");
  return ctx;
}

export function useMe(): Me {
  const { user } = useAuth();
  if (!user) throw new Error("not authenticated");
  return user;
}
