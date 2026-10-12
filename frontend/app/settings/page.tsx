"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { loadToken, saveToken } from "@/lib/draft";
import type { MetaResponse } from "@/lib/types";
import { ErrorText } from "@/components/ErrorText";

const SettingsPage = dynamic(() => Promise.resolve(SettingsForm), {
  ssr: false,
  loading: () => <p>Loading settings…</p>,
});

export default SettingsPage;

function SettingsForm() {
  const [meta, setMeta] = useState<MetaResponse | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [token, setToken] = useState(() => loadToken());
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const payload = await api<MetaResponse>("/meta");
        if (!cancelled) setMeta(payload);
      } catch (exc) {
        if (!cancelled) setError(exc);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="stack">
      <header className="page-head">
        <h1>Settings</h1>
        <p>There are no user accounts. An optional bearer token, when the API is configured with one, is stored only in this browser.</p>
      </header>
      <ErrorText error={error} />
      {meta ? (
        <section className="card stack">
          <h2>Server</h2>
          <dl className="meta-list">
            <div>
              <dt>Persistence</dt>
              <dd>{meta.persistence}</dd>
            </div>
            <div>
              <dt>Environment</dt>
              <dd>{meta.environment}</dd>
            </div>
            <div>
              <dt>Algorithm</dt>
              <dd>{meta.algorithm_version}</dd>
            </div>
            <div>
              <dt>Language model</dt>
              <dd>{meta.llm_configured ? "configured" : "not configured; deterministic parser is used"}</dd>
            </div>
            <div>
              <dt>API token required</dt>
              <dd>{meta.api_token_required ? "yes" : "no"}</dd>
            </div>
            <div>
              <dt>Worker</dt>
              <dd>{meta.worker}</dd>
            </div>
            <div>
              <dt>Max iterations</dt>
              <dd>{meta.max_iterations.toLocaleString("en-US")}</dd>
            </div>
            <div>
              <dt>Max upload</dt>
              <dd>{meta.max_upload_bytes.toLocaleString("en-US")} bytes</dd>
            </div>
          </dl>
          <p>{meta.authentication}</p>
          <p>{meta.disclaimer}</p>
          {meta.persistence === "sqlite" ? (
            <p className="notice">
              This API is using SQLite. That is a durable local database, not PostgreSQL. Set DATABASE_URL to a
              PostgreSQL URL for the production path.
            </p>
          ) : null}
        </section>
      ) : null}
      <form
        className="card stack"
        onSubmit={(event) => {
          event.preventDefault();
          saveToken(token);
          setSaved(true);
        }}
      >
        <h2>API token</h2>
        <label className="field">
          <span>Bearer token</span>
          <input
            type="password"
            autoComplete="off"
            value={token}
            onChange={(event) => {
              setToken(event.target.value);
              setSaved(false);
            }}
          />
        </label>
        <div className="button-row">
          <button type="submit">Save token in this browser</button>
          <button
            type="button"
            className="secondary"
            onClick={() => {
              setToken("");
              saveToken("");
              setSaved(true);
            }}
          >
            Clear token
          </button>
        </div>
        {saved ? <p>Saved locally. The token is not written into the repository.</p> : null}
      </form>
    </div>
  );
}
