import { useState, useEffect, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import { getDomain, listScans, startScan, downloadReport } from "../api/domains";
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
  const [downloading, setDownloading] = useState(false);

  async function handleDownload() {
    setDownloading(true);
    const start = Date.now();
    try {
      await downloadReport(id, domain.url);
    } catch (err) {
      setError(err.message);
    } finally {
      // Ensure the spinner shows for at least 600ms so the feedback registers
      const elapsed = Date.now() - start;
      const minVisible = 600;
      if (elapsed < minVisible) {
        await new Promise((r) => setTimeout(r, minVisible - elapsed));
      }
      setDownloading(false);
    }
  }

  const loadData = useCallback(async () => {
    try {
      const [domainData, scansData] = await Promise.all([
        getDomain(id),
        listScans(id),
      ]);
      setError(null);
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
    let ignore = false;
    async function fetchData() {
      try {
        const [domainData, scansData] = await Promise.all([
          getDomain(id),
          listScans(id),
        ]);
        if (!ignore) {
          setError(null);
          setDomain(domainData);
          setScans(scansData);
          setSelectedScan(scansData[0] || null);
        }
      } catch (err) {
        if (!ignore) {
          setError(err.message);
        }
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    }
    fetchData();
    return () => {
      ignore = true;
    };
  }, [id]);

  async function handleScan() {
    setScanning(true);
    setStatusText("queued");
    try {
      const res = await startScan(id);
      const jobId = res.job_id || res.task_id;
      if (res.cached || res.status === "succeeded") {
        await loadData();
        return;
      }
      const final = await pollScanStatus(jobId, (s) => setStatusText(s));
      if (final.status === "done") {
        await loadData(); // refresh history with the new scan
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
        <div className="flex items-center gap-2">
          <button
            onClick={handleDownload}
            disabled={downloading || scans.length === 0}
            className="flex items-center gap-2 px-4 py-2 rounded-md border border-zinc-300 dark:border-zinc-700 hover:bg-zinc-100 dark:hover:bg-zinc-900 disabled:opacity-50 font-medium transition whitespace-nowrap"
          >
            {downloading ? (
              <>
                <span className="inline-block w-4 h-4 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
                Generating…
              </>
            ) : (
              "↓ Report"
            )}
          </button>
          <button
            onClick={handleScan}
            disabled={scanning}
            className="px-4 py-2 rounded-md bg-emerald-600 hover:bg-emerald-500 disabled:opacity-60 text-white font-medium transition whitespace-nowrap"
          >
            {scanning ? `${statusText}…` : "Scan now"}
          </button>
        </div>
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
              {scans.map((s) => {
                const isSelected = selectedScan?.id === s.id;
                return (
                  <button
                    key={s.id}
                    onClick={() => setSelectedScan(s)}
                    className={`w-full text-left p-3 rounded-lg border transition flex items-center justify-between ${
                      isSelected
                        ? "border-emerald-500 bg-emerald-50/50 dark:bg-emerald-950/20"
                        : "border-zinc-200 dark:border-zinc-800 hover:border-zinc-300 dark:hover:border-zinc-700 bg-white dark:bg-zinc-900"
                    }`}
                  >
                    <div>
                      <p className="text-sm font-medium">
                        {new Date(s.created_at).toLocaleString()}
                      </p>
                      <p className="text-xs text-zinc-500 mt-0.5">
                        Score: {s.score}/100
                      </p>
                    </div>
                    <GradeBadge grade={s.grade} score={s.score} size="sm" />
                  </button>
                );
              })}
            </div>
          </div>

          {/* Scan detail — right 2 columns */}
          <div className="md:col-span-2">
            <h2 className="text-sm font-semibold mb-3 text-zinc-500 uppercase tracking-wide">
              Selected Scan Details
            </h2>
            <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-6">
              <ScanResult result={selectedScan} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
