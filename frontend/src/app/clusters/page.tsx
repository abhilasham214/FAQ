"use client";

import Link from "next/link";
import { useState } from "react";
import { EmptyState, ErrorBanner, Loading, PageHeader, StatusBadge } from "@/components/ui";
import { api } from "@/lib/api";
import type { Cluster } from "@/lib/types";
import { useLoad } from "@/lib/useLoad";

export default function ClustersPage() {
  const { data, error, loading, setData } = useLoad(api.clusters);
  const [generatingId, setGeneratingId] = useState<number | null>(null);
  const [generateErrors, setGenerateErrors] = useState<Record<number, string>>({});

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

  // One Gemini call for this cluster only; the other clusters are untouched.
  async function generateFaq(cluster: Cluster) {
    setGeneratingId(cluster.id);
    setGenerateErrors((prev) => {
      const next = { ...prev };
      delete next[cluster.id];
      return next;
    });
    try {
      const updated = await api.generateFaq(cluster.id);
      setData((prev) =>
        prev ? { ...prev, clusters: prev.clusters.map((c) => (c.id === updated.id ? updated : c)) } : prev
      );
    } catch (e) {
      const message = e instanceof Error ? e.message : "FAQ generation failed";
      setGenerateErrors((prev) => ({ ...prev, [cluster.id]: message }));
    } finally {
      setGeneratingId(null);
    }
  }

  return (
    <>
      <PageHeader
        title="Clusters"
        subtitle={`${clusters.length} clusters from ${run.total_tickets} tickets. K=${run.chosen_k} chosen by silhouette score (${run.silhouette.toFixed(3)}). Generate an FAQ for a cluster with its own button.`}
      />
      <div className="grid gap-4 md:grid-cols-2">
        {clusters.map((c) => (
          <div key={c.id} className="flex flex-col rounded-xl border border-slate-200 bg-white p-5 hover:border-indigo-300">
            <Link href={`/clusters/${c.id}`} className="block flex-1">
              <div className="flex items-start justify-between gap-3">
                <h2 className="font-semibold">{c.name}</h2>
                {c.faq_status && <StatusBadge status={c.faq_status} />}
              </div>
              <p className="mt-1 line-clamp-2 text-sm text-slate-500">{c.description || "No description generated."}</p>
              {c.faq && <p className="mt-3 text-sm font-medium">{c.faq.question}</p>}
              {c.faq_error && <p className="mt-3 text-sm text-rose-700">{c.faq_error}</p>}
              <p className="mt-3 text-xs text-slate-400">{c.ticket_count} tickets</p>
            </Link>
            {!c.faq && (
              <div className="mt-4 flex flex-wrap items-center gap-3">
                <button
                  onClick={() => generateFaq(c)}
                  disabled={generatingId !== null}
                  className="rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
                >
                  {generatingId === c.id ? "Generating…" : c.faq_error ? "Retry FAQ generation" : "Generate FAQ"}
                </button>
                {generateErrors[c.id] && (
                  <span role="alert" className="text-sm text-rose-700">
                    {generateErrors[c.id]}
                  </span>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </>
  );
}
