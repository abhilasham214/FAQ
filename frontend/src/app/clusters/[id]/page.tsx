"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { DistributionChart } from "@/components/DistributionChart";
import { FaqReviewCard } from "@/components/FaqReviewCard";
import { ErrorBanner, Loading, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import type { Ticket } from "@/lib/types";
import { useLoad } from "@/lib/useLoad";

export default function ClusterDetailPage() {
  const id = Number(useParams<{ id: string }>().id);
  const { data: cluster, error, loading, setData } = useLoad(() => api.cluster(id));
  const [tickets, setTickets] = useState<Ticket[] | null>(null);
  const [ticketError, setTicketError] = useState<string | null>(null);

  async function showAllTickets() {
    try {
      setTickets(await api.clusterTickets(id));
    } catch (e) {
      setTicketError(e instanceof Error ? e.message : "Could not load tickets");
    }
  }

  if (loading) return <Loading />;
  if (error) return <ErrorBanner message={error} />;
  if (!cluster) return null;

  return (
    <>
      <Link href="/clusters" className="text-sm text-indigo-600 hover:underline">
        ← All clusters
      </Link>
      <div className="mt-3">
        <PageHeader title={cluster.name} subtitle={cluster.description} />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          {cluster.faq ? (
            <FaqReviewCard faq={cluster.faq} onChange={(faq) => setData({ ...cluster, faq })} />
          ) : (
            <ErrorBanner message={`No FAQ available: ${cluster.faq_error ?? "not generated"}`} />
          )}

          <section className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="mb-3 font-semibold">Representative tickets</h2>
            <TicketList tickets={cluster.representative_tickets} />
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-5">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold">All {cluster.ticket_count} tickets</h2>
              {!tickets && (
                <button onClick={showAllTickets} className="text-sm text-indigo-600 hover:underline">
                  Load tickets
                </button>
              )}
            </div>
            {ticketError && <p className="mt-2 text-sm text-rose-700">{ticketError}</p>}
            {tickets && (
              <div className="mt-3">
                <TicketList tickets={tickets} />
              </div>
            )}
          </section>
        </div>

        <aside className="space-y-6">
          <section className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="mb-3 font-semibold">Clustering information</h2>
            <dl className="space-y-2 text-sm">
              <Row label="Tickets in cluster" value={cluster.ticket_count} />
              <Row label="Total tickets" value={cluster.run.total_tickets} />
              <Row label="Chosen K" value={cluster.run.chosen_k} />
              <Row label="Silhouette (chosen)" value={cluster.run.silhouette.toFixed(3)} />
            </dl>
            <h3 className="mb-1 mt-5 text-sm font-medium text-slate-500">Silhouette by K</h3>
            <DistributionChart
              label="Silhouette score by K"
              height={140}
              data={cluster.run.k_results.map((r) => ({ name: `K=${r.k}`, value: r.silhouette }))}
            />
          </section>
        </aside>
      </div>
    </>
  );
}

function Row({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex justify-between">
      <dt className="text-slate-500">{label}</dt>
      <dd className="font-medium tabular-nums">{value}</dd>
    </div>
  );
}

function TicketList({ tickets }: { tickets: Ticket[] }) {
  return (
    <ul className="divide-y divide-slate-100">
      {tickets.map((t) => (
        <li key={t.ticket_id} className="py-3 text-sm">
          <p>
            <span className="mr-2 rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs">{t.ticket_id}</span>
            <span className="font-medium">{t.title}</span>
          </p>
          <p className="mt-1 text-slate-500">{t.description}</p>
          <p className="mt-1 text-slate-700">
            <span className="text-slate-400">Resolution: </span>
            {t.resolution}
          </p>
        </li>
      ))}
    </ul>
  );
}
