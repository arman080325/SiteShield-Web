import { getScanJob } from "./domains";

/**
 * Polls scan job status until it finishes (succeeded/failed) or times out.
 * Calls onUpdate with each interim status so the UI can show progress.
 * Returns the final { status, result } (or { status: "failed", error }).
 */
export async function pollScanStatus(jobId, onUpdate, { intervalMs = 2000, maxAttempts = 30 } = {}) {
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const data = await getScanJob(jobId);

    if (onUpdate) onUpdate(data.status); // "queued" | "running" | ...

    if (data.status === "succeeded" || data.status === "done") {
      return { status: "done", result: data };
    }
    if (data.status === "failed") {
      return { status: "failed", error: data.error || "Scan failed" };
    }

    // not finished yet — wait, then loop
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }

  // Safety net: stop polling after maxAttempts (60s by default)
  return { status: "failed", error: "Scan timed out. Please try again." };
}
