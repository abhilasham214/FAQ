"use client";

import Link from "next/link";
import { useState } from "react";
import { FaqReviewCard } from "@/components/FaqReviewCard";
import { EmptyState, ErrorBanner, Loading, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import type { FaqStatus } from "@/lib/types";
import { useLoad } from "@/lib/useLoad";

const FILTERS: ("ALL" | FaqStatus)[] = ["ALL", "GENERATED", "REVIEW", "APPROVED", "REJECTED"];

export default function FaqReviewPage() {
  const { data, error, loading, setData } = useLoad(api.clusters);
  const [filter, setFilter] = useState<"ALL" | FaqStatus>("ALL");

  if (loading) return <Loading />;
  if (error) return <ErrorBanner message={error} />;

  const faqs = (data?.clusters ?? []).flatMap((c) => (c.faq ? [c.faq] : []));
  const visible = faqs.filter((f) => filter === "ALL" || f.status === filter);

  return (
    <>
      <PageHeader title="FAQ review" subtitle="Generated FAQs are drafts until approved." />
      {faqs.length === 0 ? (
        <EmptyState title="No FAQs yet">
          <Link href="/upload" className="text-indigo-600 hover:underline">
            Upload tickets
          </Link>{" "}
          to generate them.
        </EmptyState>
      ) : (
        <>
          <div className="mb-4 flex flex-wrap gap-2" role="group" aria-label="Filter by status">
            {FILTERS.map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                aria-pressed={filter === f}
                className={`rounded-full px-3 py-1 text-sm ${
                  filter === f ? "bg-indigo-600 text-white" : "bg-white text-slate-600 ring-1 ring-slate-200"
                }`}
              >
                {f === "ALL" ? "All" : f}
              </button>
            ))}
          </div>
          <div className="space-y-4">
            {visible.map((faq) => (
              <FaqReviewCard
                key={faq.id}
                faq={faq}
                linkToCluster
                onChange={(updated) =>
                  data &&
                  setData({
                    ...data,
                    clusters: data.clusters.map((c) => (c.faq?.id === updated.id ? { ...c, faq: updated } : c)),
                  })
                }
                onRegenerated={(cluster) =>
                  data &&
                  setData({ ...data, clusters: data.clusters.map((c) => (c.id === cluster.id ? cluster : c)) })
                }
              />
            ))}
            {visible.length === 0 && <p className="text-sm text-slate-500">No FAQs with this status.</p>}
          </div>
        </>
      )}
    </>
  );
}
