import { api } from "./client";

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