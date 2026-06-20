import { createContext, useContext, useState, useEffect } from "react";
import { getToken, setToken, clearToken } from "../api/client";
import { login as apiLogin, signup as apiSignup, getMe } from "../api/auth";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // On app load: if a token exists, verify it by fetching the current user
// On app load: if a token exists, verify it by fetching the current user
  useEffect(() => {
    async function restoreSession() {
      const token = getToken();
      if (!token) {
        setLoading(false);
        return;
      }
      try {
        const u = await getMe();
        setUser(u);
      } catch {
        clearToken(); // token invalid/expired — drop it
      } finally {
        setLoading(false);
      }
    }
    restoreSession();
  }, []);

  async function login(email, password) {
    const { access_token } = await apiLogin(email, password);
    setToken(access_token);
    const u = await getMe();
    setUser(u);
  }

  async function signup(email, password) {
    await apiSignup(email, password);
    // Auto-login right after signup for a smooth flow
    await login(email, password);
  }

  function logout() {
    clearToken();
    setUser(null);
  }

  const value = {
    user,
    loading,
    isAuthenticated: !!user,
    login,
    signup,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// Convenience hook so components just call useAuth()
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}