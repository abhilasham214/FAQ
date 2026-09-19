/**
 * TypeScript mirror of the backend's response models (backend/app/schemas/api.py).
 * Keep the two in sync by hand: a renamed backend field shows up here as `undefined`, not as an error.
 */

export type FaqStatus =
  | "GENERATED"
  | "REVIEW"
  | "APPROVED"
  | "REJECTED"
  | "GENERATION_FAILED"
  | "QUOTA_EXHAUSTED";

export interface Ticket {
  ticket_id: string;
  title: string;
  description: string;
  resolution: string;
  status: string;
}

export interface Faq {
  id: number;
  cluster_id: number;
  theme: string;
  description: string;
  question: string;
  answer: string;
  resolution_steps: string[];
  source_ticket_ids: string[];
  insufficient_information: boolean;
  status: FaqStatus;
  updated_at: string | null;
}

export interface KResult {
  k: number;
  silhouette: number;
}

export interface Run {
  id: number;
  chosen_k: number;
  silhouette: number;
  k_results: KResult[];
  total_tickets: number;
  created_at: string | null;
}

export interface Cluster {
  id: number;
  cluster_index: number;
  name: string;
  description: string;
  ticket_count: number;
  representative_tickets: Ticket[];
  faq: Faq | null;
  faq_error: string | null;
  faq_status: FaqStatus | null;
}

export interface FaqBatchResult {
  attempted: number;
  faqs_generated: number;
  faqs_failed: number;
  quota_exhausted: boolean;
  clusters: Cluster[];
}

export interface ClusterList {
  run: Run | null;
  clusters: Cluster[];
}

export interface ClusterDetail extends Cluster {
  run: Run;
}

export interface Stats {
  total_tickets: number;
  resolved_tickets: number;
  clusters: number;
  faqs: number;
  faqs_by_status: Partial<Record<FaqStatus, number>>;
  cluster_distribution: { cluster_id: number; name: string; ticket_count: number }[];
}

export interface UploadResult {
  tickets_added: number;
  tickets_skipped_existing: number;
  rejected_rows: { row: number; message: string }[];
}

export interface Step {
  name: string;
  status: "done" | "failed";
  detail: string | null;
}

/** Clustering only: FAQ generation is a separate, explicit step. */
export interface GenerateResult {
  run: Run;
  clusters: number;
  steps: Step[];
}

export interface FaqUpdate {
  theme?: string;
  description?: string;
  question?: string;
  answer?: string;
  resolution_steps?: string[];
}
