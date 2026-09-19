/**
 * Typed client for the FastAPI backend. Every request goes through `request` below.
 *
 * Debugging "Cannot reach the backend. Is it running?": fetch itself failed. Usual causes are
 * - the backend is down or asleep (Render free plan: the first request after idle takes ~1 min);
 * - NEXT_PUBLIC_API_URL is wrong. It is baked in at BUILD time, so redeploy after changing it;
 * - CORS: the backend's CORS_ORIGINS does not list this site's exact URL (browser console shows it).
 * Any other message is the backend's own `detail` text, so search the backend for it.
 */

import type {
  Cluster,
  ClusterDetail,
  ClusterList,
  Faq,
  FaqUpdate,
  FaqBatchResult,
  GenerateResult,
  Stats,
  Ticket,
  UploadResult,
} from "./types";

// A deployed site calling localhost:8000 (see the browser's Network tab) means the variable
// was missing when the site was built.
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, { cache: "no-store", ...init });
  } catch {
    throw new Error("Cannot reach the backend. Is it running?");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail = typeof body?.detail === "string" ? body.detail : `Request failed (${res.status})`;
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  stats: () => request<Stats>("/api/stats"),
  clusters: () => request<ClusterList>("/api/clusters"),
  cluster: (id: number) => request<ClusterDetail>(`/api/clusters/${id}`),
  clusterTickets: (id: number) => request<Ticket[]>(`/api/clusters/${id}/tickets`),
  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<UploadResult>("/api/tickets/upload", { method: "POST", body: form });
  },
  generate: () => request<GenerateResult>("/api/clusters/generate", { method: "POST" }),
  generateFaq: (clusterId: number) =>
    request<Cluster>(`/api/clusters/${clusterId}/faq/generate`, { method: "POST" }),
  regenerateFaq: (clusterId: number) =>
    request<Cluster>(`/api/clusters/${clusterId}/faq/regenerate`, { method: "POST" }),
  generateFaqs: () => request<FaqBatchResult>("/api/clusters/faqs/generate", { method: "POST" }),
  retryFailedFaqs: () => request<FaqBatchResult>("/api/clusters/faqs/retry-failed", { method: "POST" }),
  approve: (id: number) => request<Faq>(`/api/faqs/${id}/approve`, { method: "POST" }),
  reject: (id: number) => request<Faq>(`/api/faqs/${id}/reject`, { method: "POST" }),
  editFaq: (id: number, update: FaqUpdate) =>
    request<Faq>(`/api/faqs/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(update),
    }),
};
