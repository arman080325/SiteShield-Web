import { useState, useEffect } from "react";
import { useAuth } from "./context/AuthContext";

function App() {
  // Default to dark — your signature aesthetic. Read saved choice if present.
  const [dark, setDark] = useState(() => {
    const saved = localStorage.getItem("theme");
    return saved ? saved === "dark" : true;
  });

  // Apply the theme to the <html> element whenever it changes
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

  const { isAuthenticated, loading } = useAuth();
  console.log("auth state:", { isAuthenticated, loading });

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100 transition-colors">
      <header className="flex items-center justify-between px-6 py-4 border-b border-zinc-200 dark:border-zinc-800">
        <div className="flex items-center gap-2">
          <span className="text-xl">🛡️</span>
          <span className="font-semibold text-lg tracking-tight">
            SiteShield
          </span>
        </div>
        <button
          onClick={() => setDark((d) => !d)}
          className="px-3 py-1.5 rounded-md text-sm font-medium border border-zinc-300 dark:border-zinc-700 hover:bg-zinc-100 dark:hover:bg-zinc-900 transition-colors"
        >
          {dark ? "☀️ Light" : "🌙 Dark"}
        </button>
      </header>

      <main className="flex flex-col items-center justify-center px-6 py-24 text-center">
        <h1 className="text-4xl font-bold tracking-tight">SiteShield</h1>
        <p className="mt-3 max-w-md text-zinc-600 dark:text-zinc-400">
          Audit and monitor your website's security posture.
        </p>
        <p className="mt-8 text-sm text-zinc-500">
          Frontend scaffold is live. Toggle the theme top-right →
        </p>
      </main>
    </div>
  );
}

export default App;
