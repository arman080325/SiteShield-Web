import { useState, useEffect, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import { getDomain, listScans, startScan } from "../api/domains";
import { pollScanStatus } from "../api/poll";
import ScanResult from "../components/ScanResult";
import GradeBadge from "../components/GradeBadge";
import ScoreTrendChart from "../components/ScoreTrendChart";

export default function DomainDetail() {
  const { id } = useParams();
  const [domain, setDomain] = useState(null);
  const [scans, setScans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [statusText, setStatusText] = useState("");
  const [selectedScan, setSelectedScan] = useState(null);

  const loadData = useCallback(async () => {
    setError(null);
    try {
      const [domainData, scansData] = await Promise.all([
        getDomain(id),
        listScans(id),
      ]);
      setDomain(domainData);
      setScans(scansData);
      setSelectedScan(scansData[0] || null); // default to most recent
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  async function handleScan() {
    setScanning(true);
    setStatusText("queued");
    try {
      const { task_id } = await startScan(id);
      const final = await pollScanStatus(task_id, (s) => setStatusText(s));
      if (final.status === "done") {
        await loadData(); // refresh history with the new scan
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setScanning(false);
      setStatusText("");
    }
  }

  if (loading) {
    return <p className="text-zinc-500">Loading…</p>;
  }

  if (error) {
    return <p className="text-red-600 dark:text-red-400">{error}</p>;
  }

  return (
    <div>
      <Link to="/" className="text-sm text-emerald-600 hover:underline">
        ← Back to domains
      </Link>

      <div className="flex items-center justify-between mt-3 mb-6">
        <h1 className="text-2xl font-bold truncate">{domain?.url}</h1>
        <button
          onClick={handleScan}
          disabled={scanning}
          className="px-4 py-2 rounded-md bg-emerald-600 hover:bg-emerald-500 disabled:opacity-60 text-white font-medium transition whitespace-nowrap"
        >
          {scanning ? `${statusText}…` : "Scan now"}
        </button>
      </div>

    {scans.length > 1 && (
        <div className="mb-8 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4">
          <h2 className="text-sm font-semibold mb-4 text-zinc-500 uppercase tracking-wide">
            Score Trend
          </h2>
          <ScoreTrendChart scans={scans} />
        </div>
      )}

      {scans.length === 0 ? (
        <div className="text-center py-16 text-zinc-500">
          <p>No scans yet.</p>
          <p className="text-sm mt-1">Run your first scan above.</p>
        </div>
      ) : (
        <div className="grid md:grid-cols-3 gap-6">
          {/* History list — left column */}
          <div className="md:col-span-1">
            <h2 className="text-sm font-semibold mb-3 text-zinc-500 uppercase tracking-wide">
              Scan History
            </h2>
            <div className="space-y-2">
              {scans.map((scan) => (
                <button
                  key={scan.id}
                  onClick={() => setSelectedScan(scan)}
                  className={`w-full flex items-center gap-3 p-3 rounded-lg border text-left transition ${
                    selectedScan?.id === scan.id
                      ? "border-emerald-500 bg-emerald-50 dark:bg-emerald-950/30"
                      : "border-zinc-200 dark:border-zinc-800 hover:bg-zinc-50 dark:hover:bg-zinc-900"
                  }`}
                >
                  <GradeBadge grade={scan.grade} score={scan.score} />
                  <div className="text-sm">
                    <p className="font-medium">{scan.grade} · {scan.score}/100</p>
                    <p className="text-xs text-zinc-500">
                      {new Date(scan.created_at + "Z").toLocaleString("en-GB")}
                    </p>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Selected scan detail — right column */}
          <div className="md:col-span-2">
            <h2 className="text-sm font-semibold mb-3 text-zinc-500 uppercase tracking-wide">
              Scan Details
            </h2>
            {selectedScan && (
              <ScanResult
                result={{
                  grade: selectedScan.grade,
                  score: selectedScan.score,
                  final_url: domain?.url,
                  categories: selectedScan.categories,
                }}
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
}