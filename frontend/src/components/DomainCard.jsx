export default function DomainCard({ domain, onDelete }) {
  return (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4 flex items-center justify-between">
      <div className="min-w-0">
        <p className="font-medium truncate">{domain.url}</p>
        <p className="text-xs text-zinc-500 mt-0.5">
          Added {new Date(domain.created_at).toLocaleDateString()}
        </p>
      </div>
      <button
        onClick={() => onDelete(domain.id)}
        className="text-sm text-zinc-500 hover:text-red-600 dark:hover:text-red-400 transition px-2 py-1"
      >
        Delete
      </button>
    </div>
  );
}