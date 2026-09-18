"use client";

import Link from "next/link";
import { useState } from "react";
import { ErrorBanner, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import type { GenerateResult, UploadResult } from "@/lib/types";

type Phase = "idle" | "uploading" | "generating" | "done";

const PIPELINE = ["Loaded tickets", "Generated embeddings", "Identified clusters", "Generated themes", "Generated FAQs"];

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<string | null>(null);
  const [upload, setUpload] = useState<UploadResult | null>(null);
  const [result, setResult] = useState<GenerateResult | null>(null);

  async function start() {
    if (!file) return;
    setError(null);
    setResult(null);
    setUpload(null);
    try {
      setPhase("uploading");
      setUpload(await api.upload(file));
      setPhase("generating");
      setResult(await api.generate());
      setPhase("done");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Processing failed");
      setPhase("idle");
    }
  }

  // Backend runs the pipeline in one request, so steps are shown as pending while it runs
  // and resolved from the response's step list when it finishes.
  function stepState(name: string): "done" | "failed" | "pending" | "waiting" {
    const step = result?.steps.find((s) => s.name === name);
    if (step) return step.status;
    return phase === "generating" ? "pending" : "waiting";
  }

  const busy = phase === "uploading" || phase === "generating";

  return (
    <>
      <PageHeader
        title="Upload tickets"
        subtitle="CSV with columns: ticket_id, title, description, resolution, status"
      />

      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <input
          type="file"
          accept=".csv,text/csv"
          aria-label="Ticket CSV file"
          disabled={busy}
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="block w-full text-sm file:mr-4 file:rounded-md file:border-0 file:bg-indigo-50 file:px-4 file:py-2 file:text-sm file:font-medium file:text-indigo-700"
        />
        <button
          onClick={start}
          disabled={!file || busy}
          className="mt-4 rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {phase === "uploading" ? "Uploading…" : phase === "generating" ? "Processing…" : "Upload & generate"}
        </button>
      </div>

      {error && (
        <div className="mt-4">
          <ErrorBanner message={error} />
        </div>
      )}

      {upload && (
        <div className="mt-4 rounded-xl border border-slate-200 bg-white p-5 text-sm">
          <p>
            <span className="font-semibold">{upload.tickets_added}</span> tickets added
            {upload.tickets_skipped_existing > 0 && `, ${upload.tickets_skipped_existing} skipped (already stored)`}
            {upload.rejected_rows.length > 0 && `, ${upload.rejected_rows.length} rows rejected`}.
          </p>
          {upload.rejected_rows.length > 0 && (
            <ul className="mt-2 list-disc pl-5 text-slate-600">
              {upload.rejected_rows.slice(0, 5).map((r) => (
                <li key={r.row}>
                  Row {r.row}: {r.message}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {(phase === "generating" || phase === "done") && (
        <div className="mt-4 rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="mb-3 font-semibold">Processing</h2>
          <ul className="space-y-2 text-sm">
            {PIPELINE.map((name) => {
              const state = stepState(name);
              const detail = result?.steps.find((s) => s.name === name)?.detail;
              return (
                <li key={name} className="flex items-center gap-2">
                  <span
                    aria-hidden
                    className={
                      state === "done"
                        ? "text-emerald-600"
                        : state === "failed"
                        ? "text-rose-600"
                        : "animate-pulse text-slate-400"
                    }
                  >
                    {state === "done" ? "✓" : state === "failed" ? "✗" : "…"}
                  </span>
                  <span className={state === "pending" ? "text-slate-500" : ""}>{name}</span>
                  {detail && <span className="text-slate-400">({detail})</span>}
                </li>
              );
            })}
          </ul>
          {result && (
            <div className="mt-4 border-t border-slate-100 pt-4 text-sm">
              <p>
                {result.clusters} clusters (K={result.run.chosen_k}, silhouette {result.run.silhouette.toFixed(3)}),{" "}
                {result.faqs_generated} FAQs generated
                {result.faqs_failed > 0 && `, ${result.faqs_failed} failed`}.
              </p>
              <Link href="/clusters" className="mt-2 inline-block text-indigo-600 hover:underline">
                View clusters →
              </Link>
            </div>
          )}
        </div>
      )}
    </>
  );
}
