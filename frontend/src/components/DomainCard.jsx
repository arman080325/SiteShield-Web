import { useState } from "react";
import { startScan } from "../api/domains";
import { pollScanStatus } from "../api/poll";
import ScanResult from "./ScanResult";
import { Link } from "react-router-dom";
import { toggleMonitoring } from "../api/domains";

export default function DomainCard({ domain, onDelete }) {
  const [result, setResult] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [statusText, setStatusText] = useState(""); // "queued" | "running"
  const [error, setError] = useState(null);
  const [monitoring, setMonitoring] = useState(domain.monitoring_enabled || false);

  async function handleToggleMonitoring() {
    const next = !monitoring;
    setMonitoring(next); // optimistic update
    try {
      await toggleMonitoring(domain.id, next);
    } catch {
      setMonitoring(!next); // revert on failure
    }
  }

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
          <Link to={`/domains/${domain.id}`} className="min-w-0 block">
            <p className="font-medium truncate hover:text-emerald-600 transition">
              {domain.url}
            </p>
            <p className="text-xs text-zinc-500 mt-0.5">
              Added {new Date(domain.created_at + "Z").toLocaleDateString("en-GB")}
            </p>
          </Link>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={handleToggleMonitoring}
            title={monitoring ? "Monitoring on — auto-scans on schedule" : "Monitoring off"}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-sm font-medium border transition ${
              monitoring
                ? "border-emerald-500 text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/30"
                : "border-zinc-300 dark:border-zinc-700 text-zinc-500"
            }`}
          >
            <span className={`inline-block w-2 h-2 rounded-full ${monitoring ? "bg-emerald-500 animate-pulse" : "bg-zinc-400"}`} />
            {monitoring ? "Monitoring" : "Monitor"}
          </button>
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