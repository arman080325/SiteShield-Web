import GradeBadge from "./GradeBadge";

function CheckRow({ label, passed, detail, weight, advice }) {
  return (
    <div className="flex items-start gap-3 text-sm p-2 rounded-md bg-zinc-50 dark:bg-zinc-800/50">
      <span className={passed ? "text-emerald-500" : "text-red-500"}>
        {passed ? "✓" : "✗"}
      </span>
      <div className="min-w-0 flex-1">
        <p className="font-medium">{label}</p>
        <p className="text-xs text-zinc-500 break-words mt-0.5">{detail}</p>
        {!passed && advice && (
          <p className="text-xs text-amber-600 dark:text-amber-400 mt-0.5">
            {advice}
          </p>
        )}
      </div>
      <span className="text-xs text-zinc-400 whitespace-nowrap">
        {weight} pts
      </span>
    </div>
  );
}

function CategorySection({ title, icon, score, unreachable, children }) {
  return (
    <div className="mt-4">
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-sm font-semibold flex items-center gap-2">
          <span>{icon}</span> {title}
        </h4>
        {unreachable ? (
          <span className="text-xs px-2 py-0.5 rounded-full bg-zinc-200 dark:bg-zinc-700 text-zinc-600 dark:text-zinc-300">
            Unreachable · not scored
          </span>
        ) : (
          <span className="text-xs text-zinc-500">{score}/100</span>
        )}
      </div>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

export default function ScanResult({ result }) {
  if (!result) return null;

  if (result.error && !result.categories) {
    return (
      <div className="mt-4 p-3 rounded-md bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300 text-sm">
        Scan failed: {result.error}
      </div>
    );
  }

  const headers = result.categories?.headers;
  const tls = result.categories?.tls;

  return (
    <div className="mt-4 border-t border-zinc-200 dark:border-zinc-800 pt-4">
      <div className="flex items-center gap-4 mb-2">
        <GradeBadge grade={result.grade} score={result.score} />
        <div className="text-sm text-zinc-500">
          <p>
            Scanned{" "}
            <span className="font-medium text-zinc-700 dark:text-zinc-300">
              {result.final_url}
            </span>
          </p>
          {tls?.protocol && <p>TLS: {tls.protocol}</p>}
        </div>
      </div>

      {/* HTTP Headers category */}
      {headers && (
        <CategorySection
          title="HTTP Security Headers"
          icon="🛡️"
          score={headers.score}
          unreachable={headers.unreachable}
        >
          {headers.unreachable ? (
            <p className="text-sm text-zinc-500">
              Could not reach the site to check headers — excluded from the
              grade.
            </p>
          ) : (
            headers.checks.map((c) => (
              <CheckRow
                key={c.header}
                label={c.header}
                passed={c.present}
                detail={c.present ? c.value : "Missing"}
                weight={c.weight}
                advice={c.advice}
              />
            ))
          )}
        </CategorySection>
      )}

{/* TLS/SSL category */}
      {tls && (
        <CategorySection
          title="TLS / SSL"
          icon="🔐"
          score={tls.score}
          unreachable={tls.unreachable}
        >
          {tls.unreachable ? (
            <p className="text-sm text-zinc-500">
              Could not establish a TLS connection — excluded from the grade.
            </p>
          ) : tls.error ? (
            <p className="text-sm text-red-600 dark:text-red-400">
              {tls.error}
            </p>
          ) : (
            tls.checks.map((c) => (
              <CheckRow
                key={c.name}
                label={c.name}
                passed={c.passed}
                detail={c.detail}
                weight={c.weight}
                advice={c.advice}
              />
            ))
          )}
        </CategorySection>
      )}
{/* DNS hygiene category */}
      {result.categories?.dns && (
        <CategorySection
          title="DNS / Email Security"
          icon="🌐"
          score={result.categories.dns.score}
          unreachable={result.categories.dns.unreachable}
        >
          {result.categories.dns.unreachable ? (
            <p className="text-sm text-zinc-500">
              Could not resolve the domain — excluded from the grade.
            </p>
          ) : result.categories.dns.error ? (
            <p className="text-sm text-red-600 dark:text-red-400">
              {result.categories.dns.error}
            </p>
          ) : (
            result.categories.dns.checks.map((c) => (
              <CheckRow
                key={c.name}
                label={c.name}
                passed={c.passed}
                detail={c.detail}
                weight={c.weight}
                advice={c.advice}
              />
            ))
          )}
        </CategorySection>
      )}
    </div>
  );
}
