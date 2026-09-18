import type {
  ClusterDetail,
  ClusterList,
  Faq,
  FaqUpdate,
  GenerateResult,
  Stats,
  Ticket,
  UploadResult,
} from "./types";

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
  approve: (id: number) => request<Faq>(`/api/faqs/${id}/approve`, { method: "POST" }),
  reject: (id: number) => request<Faq>(`/api/faqs/${id}/reject`, { method: "POST" }),
  editFaq: (id: number, update: FaqUpdate) =>
    request<Faq>(`/api/faqs/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(update),
    }),
};
