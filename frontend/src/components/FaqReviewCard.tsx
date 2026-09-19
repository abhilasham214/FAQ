"use client";

import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Cluster, Faq } from "@/lib/types";
import { StatusBadge } from "./ui";

interface Props {
  faq: Faq;
  onChange: (faq: Faq) => void;
  linkToCluster?: boolean;
  /** Shows a Regenerate button; receives the cluster with its new FAQ. */
  onRegenerated?: (cluster: Cluster) => void;
}

// Replacing one of these loses a reviewer's decision or edits, so ask first.
const CONFIRM_REGENERATE: Partial<Record<Faq["status"], string>> = {
  APPROVED: "This FAQ is approved.",
  REVIEW: "This FAQ has been edited.",
  REJECTED: "This FAQ was rejected.",
};

export function FaqReviewCard({ faq, onChange, linkToCluster, onRegenerated }: Props) {
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [confirmingRegenerate, setConfirmingRegenerate] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState({ question: "", answer: "", steps: "" });

  async function run(action: () => Promise<Faq>) {
    setBusy(true);
    setError(null);
    try {
      onChange(await action());
      setEditing(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Action failed");
    } finally {
      setBusy(false);
    }
  }

  // One Gemini call. On failure the backend keeps the current FAQ, so only the error is shown.
  async function regenerate() {
    if (!onRegenerated) return;
    setConfirmingRegenerate(false);
    setBusy(true);
    setRegenerating(true);
    setError(null);
    try {
      onRegenerated(await api.regenerateFaq(faq.cluster_id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Regeneration failed");
    } finally {
      setBusy(false);
      setRegenerating(false);
    }
  }

  function startEdit() {
    setDraft({ question: faq.question, answer: faq.answer, steps: faq.resolution_steps.join("\n") });
    setEditing(true);
  }

  function save() {
    const steps = draft.steps.split("\n").map((s) => s.trim()).filter(Boolean);
    run(() => api.editFaq(faq.id, { question: draft.question, answer: draft.answer, resolution_steps: steps }));
  }

  const btn = "rounded-md px-3 py-1.5 text-sm font-medium disabled:opacity-50";

  return (
    <article className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-400">{faq.theme}</p>
          {editing ? (
            <input
              aria-label="Question"
              className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1 text-lg font-semibold"
              value={draft.question}
              onChange={(e) => setDraft({ ...draft, question: e.target.value })}
            />
          ) : (
            <h3 className="mt-1 text-lg font-semibold">{faq.question}</h3>
          )}
        </div>
        <StatusBadge status={faq.status} />
      </div>

      {faq.insufficient_information && (
        <p className="mt-3 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
          The source tickets did not contain enough information for a reliable answer. Review carefully.
        </p>
      )}

      <div className="mt-4">
        <h4 className="text-sm font-medium text-slate-500">Answer</h4>
        {editing ? (
          <textarea
            aria-label="Answer"
            rows={4}
            className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1 text-sm"
            value={draft.answer}
            onChange={(e) => setDraft({ ...draft, answer: e.target.value })}
          />
        ) : (
          <p className="mt-1 text-sm leading-relaxed">{faq.answer}</p>
        )}
      </div>

      <div className="mt-4">
        <h4 className="text-sm font-medium text-slate-500">Resolution steps</h4>
        {editing ? (
          <textarea
            aria-label="Resolution steps (one per line)"
            rows={4}
            className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1 text-sm"
            value={draft.steps}
            onChange={(e) => setDraft({ ...draft, steps: e.target.value })}
          />
        ) : faq.resolution_steps.length ? (
          <ol className="mt-1 list-decimal space-y-1 pl-5 text-sm">
            {faq.resolution_steps.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ol>
        ) : (
          <p className="mt-1 text-sm text-slate-400">None listed.</p>
        )}
      </div>

      <div className="mt-4">
        <h4 className="text-sm font-medium text-slate-500">Source tickets</h4>
        <div className="mt-1 flex flex-wrap gap-1.5">
          {faq.source_ticket_ids.map((id) => (
            <span key={id} className="rounded bg-slate-100 px-2 py-0.5 font-mono text-xs">
              {id}
            </span>
          ))}
        </div>
      </div>

      {error && <p className="mt-3 text-sm text-rose-700">{error}</p>}

      {confirmingRegenerate && (
        <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          <p>
            {CONFIRM_REGENERATE[faq.status]} Regenerating replaces it with a new version from Gemini, which will need
            to be reviewed again.
          </p>
          <div className="mt-2 flex gap-2">
            <button className={`${btn} bg-indigo-600 text-white`} disabled={busy} onClick={regenerate}>
              Yes, regenerate
            </button>
            <button
              className={`${btn} border border-amber-300 bg-white`}
              disabled={busy}
              onClick={() => setConfirmingRegenerate(false)}
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      <div className="mt-5 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-4">
        {editing ? (
          <>
            <button className={`${btn} bg-indigo-600 text-white`} disabled={busy} onClick={save}>
              Save
            </button>
            <button className={`${btn} border border-slate-300`} disabled={busy} onClick={() => setEditing(false)}>
              Cancel
            </button>
          </>
        ) : (
          <>
            <button
              className={`${btn} bg-emerald-600 text-white`}
              disabled={busy || faq.status === "APPROVED"}
              onClick={() => run(() => api.approve(faq.id))}
            >
              Approve
            </button>
            <button
              className={`${btn} bg-rose-600 text-white`}
              disabled={busy || faq.status === "REJECTED"}
              onClick={() => run(() => api.reject(faq.id))}
            >
              Reject
            </button>
            <button className={`${btn} border border-slate-300`} disabled={busy} onClick={startEdit}>
              Edit
            </button>
            {onRegenerated && (
              <button
                className={`${btn} border border-indigo-300 text-indigo-700`}
                disabled={busy || confirmingRegenerate}
                onClick={() => (CONFIRM_REGENERATE[faq.status] ? setConfirmingRegenerate(true) : regenerate())}
              >
                {regenerating ? "Regenerating…" : "Regenerate"}
              </button>
            )}
          </>
        )}
        {linkToCluster && (
          <Link href={`/clusters/${faq.cluster_id}`} className="ml-auto text-sm text-indigo-600 hover:underline">
            View cluster →
          </Link>
        )}
      </div>
    </article>
  );
}
