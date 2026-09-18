"use client";

import Link from "next/link";
import { EmptyState, ErrorBanner, Loading, PageHeader, StatusBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { useLoad } from "@/lib/useLoad";

export default function ClustersPage() {
  const { data, error, loading } = useLoad(api.clusters);

  if (loading) return <Loading />;
  if (error) return <ErrorBanner message={error} />;
  if (!data || !data.run) {
    return (
      <>
        <PageHeader title="Clusters" />
        <EmptyState title="No clusters yet">
          <Link href="/upload" className="text-indigo-600 hover:underline">
            Upload tickets
          </Link>{" "}
          to generate them.
        </EmptyState>
      </>
    );
  }

  const { run, clusters } = data;
  return (
    <>
      <PageHeader
        title="Clusters"
        subtitle={`${clusters.length} clusters from ${run.total_tickets} tickets. K=${run.chosen_k} chosen by silhouette score (${run.silhouette.toFixed(3)}).`}
      />
      <div className="grid gap-4 md:grid-cols-2">
        {clusters.map((c) => (
          <Link
            key={c.id}
            href={`/clusters/${c.id}`}
            className="rounded-xl border border-slate-200 bg-white p-5 hover:border-indigo-300"
          >
            <div className="flex items-start justify-between gap-3">
              <h2 className="font-semibold">{c.name}</h2>
              {c.faq && <StatusBadge status={c.faq.status} />}
            </div>
            <p className="mt-1 line-clamp-2 text-sm text-slate-500">{c.description || "No description generated."}</p>
            {c.faq && <p className="mt-3 text-sm font-medium">{c.faq.question}</p>}
            {c.faq_error && <p className="mt-3 text-sm text-rose-700">FAQ generation failed: {c.faq_error}</p>}
            <p className="mt-3 text-xs text-slate-400">{c.ticket_count} tickets</p>
          </Link>
        ))}
      </div>
    </>
  );
}
