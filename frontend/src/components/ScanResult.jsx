import GradeBadge from "./GradeBadge";

export default function ScanResult({ result }) {
  if (!result) return null;

  // Backend returns { scan, final_url, status_code, checks, error }
  if (result.error) {
    return (
      <div className="mt-4 p-3 rounded-md bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300 text-sm">
        Scan failed: {result.error}
      </div>
    );
  }

  return (
    <div className="mt-4 border-t border-zinc-200 dark:border-zinc-800 pt-4">
      <div className="flex items-center gap-4 mb-4">
        <GradeBadge grade={result.scan.grade} score={result.scan.score} />
        <div className="text-sm text-zinc-500">
          <p>
            Scanned <span className="font-medium text-zinc-700 dark:text-zinc-300">{result.final_url}</span>
          </p>
          <p>HTTP status: {result.status_code}</p>
        </div>
      </div>

      <div className="space-y-2">
        {result.checks.map((check) => (
          <div
            key={check.header}
            className="flex items-start gap-3 text-sm p-2 rounded-md bg-zinc-50 dark:bg-zinc-800/50"
          >
            <span className={check.present ? "text-emerald-500" : "text-red-500"}>
              {check.present ? "✓" : "✗"}
            </span>
            <div className="min-w-0 flex-1">
              <p className="font-medium">{check.header}</p>
              {check.present ? (
                <p className="text-xs text-zinc-500 break-words mt-0.5">
                  {check.value}
                </p>
              ) : (
                <p className="text-xs text-amber-600 dark:text-amber-400 mt-0.5">
                  {check.advice}
                </p>
              )}
            </div>
            <span className="text-xs text-zinc-400 whitespace-nowrap">
              {check.weight} pts
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}