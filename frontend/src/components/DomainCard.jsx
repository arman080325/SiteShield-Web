import { useState } from "react";
import { startScan } from "../api/domains";
import { pollScanStatus } from "../api/poll";
import ScanResult from "./ScanResult";

export default function DomainCard({ domain, onDelete }) {
  const [result, setResult] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [statusText, setStatusText] = useState(""); // "queued" | "running"
  const [error, setError] = useState(null);

  async function handleScan() {
    setError(null);
    setResult(null);
    setScanning(true);
    setStatusText("queued");

    try {
      // 1. Enqueue — returns instantly with a task_id
      const { task_id } = await startScan(domain.id);

      // 2. Poll until done, updating the status line as we go
      const final = await pollScanStatus(task_id, (status) => {
        setStatusText(status);
      });

      // 3. Handle the outcome
      if (final.status === "done") {
        setResult(final.result);
      } else {
        setError(final.error || "Scan failed.");
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setScanning(false);
      setStatusText("");
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
            disabled={scanning}
            className="text-sm text-zinc-500 hover:text-red-600 dark:hover:text-red-400 disabled:opacity-40 transition px-2 py-1"
          >
            Delete
          </button>
        </div>
      </div>

      {/* Live status line — shows the real backend state while polling */}
      {scanning && statusText && (
        <div className="mt-3 flex items-center gap-2 text-sm text-zinc-500">
          <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="capitalize">{statusText}…</span>
        </div>
      )}

      {error && (
        <p className="mt-3 text-sm text-red-600 dark:text-red-400">{error}</p>
      )}

      <ScanResult result={result} />
    </div>
  );
}