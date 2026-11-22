import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { api, setToken, token } from "./api";

export type User = {
  id: string;
  username: string;
  display_name: string;
  role: string;
  faculty?: string | null;
  scope_building_id?: string | null;
};

type AuthCtx = {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  can: (roles: string[]) => boolean;
};

const Ctx = createContext<AuthCtx>(null as any);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token()) {
      setLoading(false);
      return;
    }
    api.get<User>("/auth/me")
      .then(setUser)
      .catch(() => setToken(null))
      .finally(() => setLoading(false));
  }, []);

  const login = async (username: string, password: string) => {
    const res = await api.post<{ access_token: string; user: User }>("/auth/login", { username, password });
    setToken(res.access_token);
    setUser(res.user);
  };

  const logout = () => {
    setToken(null);
    setUser(null);
  };

  const can = (roles: string[]) => !!user && roles.includes(user.role);

  return <Ctx.Provider value={{ user, loading, login, logout, can }}>{children}</Ctx.Provider>;
}

export const useAuth = () => useContext(Ctx);
