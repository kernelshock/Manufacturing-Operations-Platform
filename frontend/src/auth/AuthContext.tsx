import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode
} from "react";

import { ApiError, api } from "../api/client";
import type { CurrentUser, LoginPayload } from "../api/types";

type AuthState =
  | { status: "loading"; user: null; error: null }
  | { status: "anonymous"; user: null; error: null }
  | { status: "authenticated"; user: CurrentUser; error: null }
  | { status: "error"; user: null; error: string };

type AuthContextValue = {
  state: AuthState;
  login: (payload: LoginPayload) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    status: "loading",
    user: null,
    error: null
  });

  const refresh = useCallback(async () => {
    try {
      const user = await api.me();
      setState({ status: "authenticated", user, error: null });
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setState({ status: "anonymous", user: null, error: null });
        return;
      }
      setState({
        status: "error",
        user: null,
        error:
          error instanceof Error
            ? error.message
            : "No fue posible consultar la sesión."
      });
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const login = useCallback(
    async (payload: LoginPayload) => {
      await api.login(payload);
      await refresh();
    },
    [refresh]
  );

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      setState({ status: "anonymous", user: null, error: null });
    }
  }, []);

  const value = useMemo(
    () => ({ state, login, logout, refresh }),
    [state, login, logout, refresh]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return context;
}
