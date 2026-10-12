"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { saveDraft } from "@/lib/draft";
import type { SimulationDetail } from "@/lib/types";
import { AssumptionTable } from "@/components/PromptWorkbench";
import { ErrorText } from "@/components/ErrorText";

export default function DetailsPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [detail, setDetail] = useState<SimulationDetail | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const router = useRouter();

  useEffect(() => {
    api<SimulationDetail>(`/simulations/${id}`)
      .then(setDetail)
      .catch(setError);
  }, [id]);

  async function duplicate() {
    setBusy(true);
    setError(null);
    try {
      const copy = await api<SimulationDetail>(`/simulations/${id}/duplicate`, { method: "POST" });
      router.push(`/simulations/${copy.id}/details`);
    } catch (exc) {
      setError(exc);
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    setError(null);
    try {
      await api<void>(`/simulations/${id}`, { method: "DELETE" });
      router.push("/history");
    } catch (exc) {
      setError(exc);
      setBusy(false);
    }
  }

  return (
    <div className="stack">
      <header className="page-head">
        <h1>Saved simulation</h1>
        <p>Configuration, validation, and audit events for this saved run.</p>
      </header>
      <ErrorText error={error} />
      {!detail && !error ? <p>Loading…</p> : null}
      {detail ? (
        <>
          <section className="card stack">
            <h2>{detail.title}</h2>
            <p>{detail.description || "No description."}</p>
            <p>
              Status {detail.status}. Created {detail.created_at}. Hypothetical: yes.
            </p>
            <div className="button-row">
              <a className="button" href={`/simulations/${id}/run`}>
                Execution
              </a>
              {detail.status === "completed" ? (
                <a className="button secondary" href={`/simulations/${id}`}>
                  Results
                </a>
              ) : null}
              <button
                type="button"
                className="secondary"
                onClick={() => {
                  saveDraft(detail.specification);
                  router.push(`/configure?id=${id}`);
                }}
              >
                Edit configuration
              </button>
              <button type="button" className="secondary" disabled={busy} onClick={() => void duplicate()}>
                Duplicate
              </button>
              <button type="button" className="danger" onClick={() => setConfirming(true)}>
                Delete
              </button>
            </div>
            {confirming ? (
              <div role="alertdialog" aria-label="Confirm deletion">
                <p>Delete this saved simulation? This cannot be undone.</p>
                <div className="button-row">
                  <button type="button" className="danger" disabled={busy} onClick={() => void remove()}>
                    Delete permanently
                  </button>
                  <button type="button" className="secondary" onClick={() => setConfirming(false)}>
                    Keep
                  </button>
                </div>
              </div>
            ) : null}
          </section>
          <section className="card stack">
            <h2>Assumptions</h2>
            <AssumptionTable assumptions={detail.specification.assumptions} />
          </section>
          <section className="card stack">
            <h2>Validation</h2>
            {detail.validation ? (
              <p>{detail.validation.valid ? "Valid when last saved." : "Invalid when last saved."}</p>
            ) : (
              <p>No validation report was stored.</p>
            )}
            {detail.validation?.warnings.map((issue) => (
              <p key={issue.message}>
                Warning — {issue.field}: {issue.message}
              </p>
            ))}
          </section>
          <section className="card stack">
            <h2>Audit</h2>
            {detail.audit_events.length === 0 ? <p>No audit events.</p> : null}
            <ul>
              {detail.audit_events.map((event) => (
                <li key={event.id}>
                  {event.created_at}: {event.action}. {event.detail}
                </li>
              ))}
            </ul>
          </section>
          <section className="card stack">
            <h2>Specification</h2>
            <pre className="code-block">{JSON.stringify(detail.specification, null, 2)}</pre>
          </section>
        </>
      ) : null}
    </div>
  );
}
