"use client";

import Link from "next/link";
import { DistributionChart } from "@/components/DistributionChart";
import { EmptyState, ErrorBanner, Loading, PageHeader, StatCard } from "@/components/ui";
import { api } from "@/lib/api";
import { useLoad } from "@/lib/useLoad";

export default function DashboardPage() {
  const { data: stats, error, loading } = useLoad(api.stats);

  if (loading) return <Loading />;
  if (error) return <ErrorBanner message={error} />;
  if (!stats) return null;

  const approved = stats.faqs_by_status.APPROVED ?? 0;

  return (
    <>
      <PageHeader title="Dashboard" subtitle="Overview of the generated knowledge base" />
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard label="Total tickets" value={stats.total_tickets} />
        <StatCard label="Resolved tickets" value={stats.resolved_tickets} />
        <StatCard label="Clusters" value={stats.clusters} />
        <StatCard label="Generated FAQs" value={stats.faqs} hint={`${approved} approved`} />
      </div>

      <section className="mt-8 rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="mb-4 font-semibold">Cluster distribution</h2>
        {stats.cluster_distribution.length === 0 ? (
          <EmptyState title="No clusters yet">
            <Link href="/upload" className="text-indigo-600 hover:underline">
              Upload tickets
            </Link>{" "}
            and generate the knowledge base to see results.
          </EmptyState>
        ) : (
          <DistributionChart
            label="Tickets per cluster"
            data={stats.cluster_distribution.map((c) => ({ name: c.name, value: c.ticket_count }))}
          />
        )}
      </section>

      {stats.faqs > 0 && (
        <section className="mt-8 rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="mb-3 font-semibold">Review status</h2>
          <ul className="flex flex-wrap gap-6 text-sm">
            {(["GENERATED", "REVIEW", "APPROVED", "REJECTED"] as const).map((s) => (
              <li key={s}>
                <span className="text-slate-500">{s}</span>{" "}
                <span className="font-semibold tabular-nums">{stats.faqs_by_status[s] ?? 0}</span>
              </li>
            ))}
          </ul>
          <Link href="/faqs" className="mt-4 inline-block text-sm text-indigo-600 hover:underline">
            Review FAQs →
          </Link>
        </section>
      )}
    </>
  );
}
