import { useState } from "react";
import { runScan } from "../api/domains";
import ScanResult from "./ScanResult";


export default function DomainCard({ domain, onDelete }) {
  const [result, setResult] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState(null);

  async function handleScan() {
    setError(null);
    setScanning(true);
    try {
      const data = await runScan(domain.id);
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setScanning(false);
    }
  }

  return (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4">
      <div className="flex items-center justify-between">
        <div className="min-w-0">
          <p className="font-medium truncate">{domain.url}</p>
          <p className="text-xs text-zinc-500 mt-0.5">
            Added {new Date(domain.created_at + "Z").toLocaleDateString("en-GB")}
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={handleScan}
            disabled={scanning}
            className="px-3 py-1.5 rounded-md text-sm font-medium bg-emerald-600 hover:bg-emerald-500 disabled:opacity-60 text-white transition"
          >
            {scanning ? "Scanning…" : "Scan now"}
          </button>
          <button
            onClick={() => onDelete(domain.id)}
            className="text-sm text-zinc-500 hover:text-red-600 dark:hover:text-red-400 transition px-2 py-1"
          >
            Delete
          </button>
        </div>
      </div>

      {error && (
        <p className="mt-3 text-sm text-red-600 dark:text-red-400">{error}</p>
      )}

      <ScanResult result={result} />
    </div>
  );
}