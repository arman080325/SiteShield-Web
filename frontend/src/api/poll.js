import { getScanStatus } from "./domains";

/**
 * Polls scan status until it finishes (done/failed) or times out.
 * Calls onUpdate with each interim status so the UI can show progress.
 * Returns the final { status, result } (or { status: "failed", error }).
 */
export async function pollScanStatus(taskId, onUpdate, { intervalMs = 2000, maxAttempts = 30 } = {}) {
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const data = await getScanStatus(taskId);

    if (onUpdate) onUpdate(data.status); // "pending" | "running" | ...

    if (data.status === "done") {
      return data; // { status: "done", result: {...} }
    }
    if (data.status === "failed") {
      return data; // { status: "failed", error: "..." }
    }

    // not finished yet — wait, then loop
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }

  // Safety net: stop polling after maxAttempts (60s by default)
  return { status: "failed", error: "Scan timed out. Please try again." };
}