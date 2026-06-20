import { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import Dashboard from "./pages/Dashboard";

function Header({ dark, setDark }) {
  const { isAuthenticated, logout, user } = useAuth();
  return (
    <header className="flex items-center justify-between px-6 py-4 border-b border-zinc-200 dark:border-zinc-800">
      <Link to="/" className="flex items-center gap-2">
        <span className="text-xl">🛡️</span>
        <span className="font-semibold text-lg tracking-tight">SiteShield</span>
      </Link>
      <div className="flex items-center gap-3">
        {isAuthenticated && (
          <>
            <span className="text-sm text-zinc-500 hidden sm:inline">{user?.email}</span>
            <button
              onClick={logout}
              className="px-3 py-1.5 rounded-md text-sm font-medium border border-zinc-300 dark:border-zinc-700 hover:bg-zinc-100 dark:hover:bg-zinc-900 transition-colors"
            >
              Log out
            </button>
          </>
        )}
        <button
          onClick={() => setDark((d) => !d)}
          className="px-3 py-1.5 rounded-md text-sm font-medium border border-zinc-300 dark:border-zinc-700 hover:bg-zinc-100 dark:hover:bg-zinc-900 transition-colors"
        >
          {dark ? "☀️ Light" : "🌙 Dark"}
        </button>
      </div>
    </header>
  );
}

function App() {
  const [dark, setDark] = useState(() => {
    const saved = localStorage.getItem("theme");
    return saved ? saved === "dark" : true;
  });

  useEffect(() => {
    const root = document.documentElement;
    if (dark) {
      root.classList.add("dark");
      localStorage.setItem("theme", "dark");
    } else {
      root.classList.remove("dark");
      localStorage.setItem("theme", "light");
    }
  }, [dark]);

  return (
    <BrowserRouter>
      <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100 transition-colors">
        <Header dark={dark} setDark={setDark} />
        <main className="max-w-3xl mx-auto px-6 py-16">
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/signup" element={<Signup />} />
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <Dashboard />
                </ProtectedRoute>
              }
            />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;