"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { MetaResponse } from "@/lib/types";
import { ErrorText } from "@/components/ErrorText";

export default function SettingsPage() {
  const [meta, setMeta] = useState<MetaResponse | null>(null);
  const [error, setError] = useState<unknown>(null);

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
        <p>The browser does not store API tokens. Access depends on the server auth mode.</p>
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
              <dt>Auth mode</dt>
              <dd>{meta.auth_mode}</dd>
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
              <dt>Registration</dt>
              <dd>{meta.registration_open ? "open" : "closed"}</dd>
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
              PostgreSQL URL for a shared deployment.
            </p>
          ) : null}
          {meta.auth_mode === "development" ? (
            <p className="notice">
              Development mode keeps one shared local workspace so the app can be used without an account. Production
              startup refuses this mode.
            </p>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
