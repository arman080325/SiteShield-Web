import { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import { listDomains, addDomain, deleteDomain } from "../api/domains";
import AddDomainForm from "../components/AddDomainForm";
import DomainCard from "../components/DomainCard";

export default function Dashboard() {
  const { user } = useAuth();
  const [domains, setDomains] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Load the user's domains on mount
  useEffect(() => {
    listDomains()
      .then((data) => setDomains(data))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  async function handleAdd(url) {
    const newDomain = await addDomain(url);
    // Prepend so newest shows first (matches backend ordering)
    setDomains((prev) => [newDomain, ...prev]);
  }

  async function handleDelete(id) {
    await deleteDomain(id);
    setDomains((prev) => prev.filter((d) => d.id !== id));
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Your domains</h1>
        <p className="text-sm text-zinc-500 mt-1">
          Signed in as {user?.email}
        </p>
      </div>

      <AddDomainForm onAdd={handleAdd} />

      {loading && <p className="text-zinc-500">Loading domains…</p>}
      {error && <p className="text-red-600 dark:text-red-400">{error}</p>}

      {!loading && !error && domains.length === 0 && (
        <div className="text-center py-16 text-zinc-500">
          <p>No domains yet.</p>
          <p className="text-sm mt-1">Add one above to run your first scan.</p>
        </div>
      )}

      <div className="space-y-3">
        {domains.map((domain) => (
          <DomainCard key={domain.id} domain={domain} onDelete={handleDelete} />
        ))}
      </div>
    </div>
  );
}