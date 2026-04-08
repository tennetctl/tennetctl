"use client";

import * as React from "react";
import { login, logout, getMe, tokenStore } from "@/lib/api";
import type { MeData } from "@/types/api";

type AuthState =
  | { status: "loading" }
  | { status: "unauthenticated" }
  | { status: "authenticated"; me: MeData; accessToken: string; sessionId: string };

type AuthContextValue = AuthState & {
  signIn: (username: string, password: string) => Promise<{ ok: true } | { ok: false; message: string }>;
  signOut: () => Promise<void>;
};

const AuthContext = React.createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = React.useState<AuthState>({ status: "loading" });

  // Rehydrate from localStorage on mount
  React.useEffect(() => {
    const { access, sessionId } = tokenStore.get();
    if (!access || !sessionId) {
      setState({ status: "unauthenticated" });
      return;
    }
    getMe(access)
      .then((res) => {
        if (res.ok) {
          setState({ status: "authenticated", me: res.data, accessToken: access, sessionId });
        } else {
          tokenStore.clear();
          setState({ status: "unauthenticated" });
        }
      })
      .catch(() => {
        // Backend unreachable — keep stored token, show as unauthenticated
        tokenStore.clear();
        setState({ status: "unauthenticated" });
      });
  }, []);

  const signIn: AuthContextValue["signIn"] = React.useCallback(async (username, password) => {
    const res = await login(username, password);
    if (!res.ok) return { ok: false, message: res.error.message };
    tokenStore.set(res.data);
    const meRes = await getMe(res.data.access_token);
    if (!meRes.ok) return { ok: false, message: "Signed in but could not fetch profile." };
    setState({
      status: "authenticated",
      me: meRes.data,
      accessToken: res.data.access_token,
      sessionId: res.data.session_id,
    });
    return { ok: true };
  }, []);

  const signOut: AuthContextValue["signOut"] = React.useCallback(async () => {
    if (state.status === "authenticated") {
      try {
        await logout(state.sessionId, state.accessToken);
      } catch {
        // best-effort
      }
    }
    tokenStore.clear();
    setState({ status: "unauthenticated" });
  }, [state]);

  return (
    <AuthContext.Provider value={{ ...state, signIn, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = React.useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
