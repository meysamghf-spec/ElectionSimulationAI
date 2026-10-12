"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { SimulationSummary } from "@/lib/types";
import { ErrorText } from "@/components/ErrorText";

export default function HistoryPage() {
  const [items, setItems] = useState<SimulationSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const limit = 20;

  useEffect(() => {
    let cancelled = false;
    api<{ items: SimulationSummary[]; total: number }>(`/simulations?limit=${limit}&offset=${offset}`)
      .then((payload) => {
        if (!cancelled) {
          setItems(payload.items);
          setTotal(payload.total);
          setError(null);
        }
      })
      .catch((exc) => {
        if (!cancelled) setError(exc);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [offset]);

  return (
    <div className="stack">
      <header className="page-head">
        <h1>Simulation history</h1>
        <p>Saved configurations and runs stored by the API. A server restart keeps them when the database file or PostgreSQL volume is intact.</p>
      </header>
      <ErrorText error={error} />
      {loading ? <p>Loading saved simulations…</p> : null}
      {!loading && items.length === 0 ? (
        <div className="card stack">
          <p>No saved simulations yet.</p>
          <a className="button" href="/new">
            Create one
          </a>
        </div>
      ) : null}
      <ul className="history-list">
        {items.map((item) => (
          <li key={item.id} className="card">
            <h2>{item.title}</h2>
            <p>
              Status: {item.status}. Method: {item.voting_method}. Iterations: {item.iterations.toLocaleString("en-US")}.
            </p>
            <p>Updated {item.updated_at}</p>
            <div className="button-row">
              <a className="button secondary" href={`/simulations/${item.id}/details`}>
                Details
              </a>
              {item.status === "completed" ? (
                <a className="button" href={`/simulations/${item.id}`}>
                  Results
                </a>
              ) : (
                <a className="button" href={`/simulations/${item.id}/run`}>
                  Execution
                </a>
              )}
            </div>
          </li>
        ))}
      </ul>
      <div className="button-row">
        <button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}>
          Previous page
        </button>
        <button type="button" disabled={offset + limit >= total} onClick={() => setOffset(offset + limit)}>
          Next page
        </button>
        <span>
          {total === 0 ? "0 saved" : `${offset + 1}–${Math.min(offset + limit, total)} of ${total}`}
        </span>
      </div>
    </div>
  );
}
