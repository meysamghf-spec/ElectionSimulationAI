"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import type { SimulationDetail } from "@/lib/types";
import { AssumptionTable } from "@/components/PromptWorkbench";
import { ErrorText } from "@/components/ErrorText";

export default function RunPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [detail, setDetail] = useState<SimulationDetail | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [message, setMessage] = useState("");
  const [polling, setPolling] = useState(false);
  const [watch, setWatch] = useState(0);

  useEffect(() => {
    let timer: number | undefined;
    let cancelled = false;
    async function tick() {
      try {
        const next = await api<SimulationDetail>(`/simulations/${id}`);
        if (cancelled) return;
        setDetail(next);
        if (next.status === "queued" || next.status === "running") {
          setPolling(true);
          timer = window.setTimeout(() => void tick(), 1000);
        } else {
          setPolling(false);
        }
      } catch (exc) {
        if (!cancelled) setError(exc);
      }
    }
    void tick();
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [id, watch]);

  async function start() {
    setError(null);
    setMessage("");
    try {
      await api(`/simulations/${id}/execute`, { method: "POST", body: JSON.stringify({ wait: false }) });
      setMessage("The run was queued. Status updates as the worker progresses.");
      setWatch((value) => value + 1);
    } catch (exc) {
      setError(exc);
    }
  }

  async function cancel() {
    setError(null);
    try {
      const payload = await api<{ message: string }>(`/simulations/${id}/cancel`, { method: "POST" });
      setMessage(payload.message);
      setWatch((value) => value + 1);
    } catch (exc) {
      setError(exc);
    }
  }

  const status = detail?.status;
  const running = status === "queued" || status === "running";

  return (
    <div className="stack">
      <header className="page-head">
        <h1>Simulation execution</h1>
        <p>Nothing runs until you choose Start. Closing this page does not cancel a queued or running job.</p>
      </header>
      <ErrorText error={error} />
      {!detail ? <p>Loading execution status…</p> : null}
      {detail ? (
        <section className="card stack">
          <h2>{detail.title}</h2>
          <p aria-live="polite">
            Status: <strong>{detail.status}</strong>
            {polling ? " (checking)" : ""}
          </p>
          <progress value={Math.min(1, Math.max(0, detail.progress))} max={1} />
          <p>{Math.round(detail.progress * 100)}% reported by the worker.</p>
          {detail.error_message ? <p className="field-error">{detail.error_message}</p> : null}
          {message ? <p>{message}</p> : null}
          <p>
            {detail.iterations.toLocaleString("en-US")} iterations, seed {detail.seed}, method {detail.voting_method}.
          </p>
          <AssumptionTable assumptions={detail.specification.assumptions} />
          <div className="button-row">
            <button type="button" onClick={() => void start()} disabled={running}>
              {running ? "Running" : status === "failed" || status === "cancelled" ? "Retry run" : "Start simulation"}
            </button>
            <button type="button" className="secondary" onClick={() => void cancel()} disabled={!running}>
              Cancel
            </button>
            {!running ? (
              <span className="hint">Cancel is available after the run is queued or running.</span>
            ) : null}
          </div>
          {status === "completed" ? (
            <a className="button" href={`/simulations/${id}`}>
              Open results
            </a>
          ) : null}
          {status === "completed" ? null : (
            <p className="hint">Results stay unavailable until status is completed.</p>
          )}
          <a href={`/simulations/${id}/details`}>Saved simulation details</a>
        </section>
      ) : null}
    </div>
  );
}
