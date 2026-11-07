import { api, getToken, BASE_URL } from "./client";

export function listDomains() {
  return api.get("/domains");
}

export function addDomain(url) {
  return api.post("/domains", { url });
}

export function deleteDomain(id) {
  return api.delete(`/domains/${id}`);
}

export function startScan(id) {
  // Enqueues the job, returns { task_id, status } instantly
  return api.post(`/domains/${id}/scan`);
}

export function getScanStatus(taskId) {
  // Polls the worker: pending / running / done / failed
  return api.get(`/domains/scan-status/${taskId}`);
}

export function listScans(id) {
  return api.get(`/domains/${id}/scans`);
}

export function getDomain(id) {
  return api.get(`/domains/${id}`);
}

export function toggleMonitoring(id, enabled) {
  return api.patch(`/domains/${id}/monitoring`, { enabled });
}

export async function downloadReport(id, domainUrl) {
  const res = await fetch(`${BASE_URL}/domains/${id}/report`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  if (!res.ok) {
    throw new Error("Could not generate report");
  }
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  const safeName = domainUrl.replace(/^https?:\/\//, "").replace(/\//g, "_");
  a.download = `siteshield_${safeName}.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}
