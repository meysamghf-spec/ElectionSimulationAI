"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { SimulationSummary } from "@/lib/types";
import { ErrorText } from "@/components/ErrorText";
import { useI18n } from "@/lib/i18n";

export default function HistoryPage() {
  const { t, numberLocale } = useI18n();
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
        <h1>{t("history.title")}</h1>
        <p>{t("history.lead")}</p>
      </header>
      <ErrorText error={error} />
      {loading ? <p>{t("history.loading")}</p> : null}
      {!loading && items.length === 0 ? (
        <div className="card stack">
          <p>{t("history.empty")}</p>
          <a className="button" href="/new">
            {t("history.create")}
          </a>
        </div>
      ) : null}
      <ul className="history-list">
        {items.map((item) => (
          <li key={item.id} className="card">
            <h2>{item.title}</h2>
            <p>
              {t("history.status")}: {item.status}. {t("history.method")}: {item.voting_method}. {t("history.iterations")}:{" "}
              {item.iterations.toLocaleString(numberLocale)}.
            </p>
            <p>
              {t("history.updated")}: <bdi>{item.updated_at}</bdi>
            </p>
            <div className="button-row">
              <a className="button secondary" href={`/simulations/${item.id}/details`}>
                {t("history.details")}
              </a>
              {item.status === "completed" ? (
                <a className="button" href={`/simulations/${item.id}`}>
                  {t("history.results")}
                </a>
              ) : (
                <a className="button" href={`/simulations/${item.id}/run`}>
                  {t("history.execution")}
                </a>
              )}
            </div>
          </li>
        ))}
      </ul>
      <div className="button-row">
        <button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}>
          {t("history.prev")}
        </button>
        <button type="button" disabled={offset + limit >= total} onClick={() => setOffset(offset + limit)}>
          {t("history.next")}
        </button>
        <span>
          {total === 0
            ? t("history.none")
            : `${offset + 1}–${Math.min(offset + limit, total)} ${t("history.of")} ${total}`}
        </span>
      </div>
    </div>
  );
}
