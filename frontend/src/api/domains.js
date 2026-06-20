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

export function runScan(id) {
  return api.post(`/domains/${id}/scan`);
}

export function listScans(id) {
  return api.get(`/domains/${id}/scans`);
}