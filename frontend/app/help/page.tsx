"use client";

import { useEffect, useState } from "react";
import { MarkdownView } from "@/components/MarkdownView";
import { ErrorText } from "@/components/ErrorText";
import { api } from "@/lib/api";

export default function HelpPage() {
  const [markdown, setMarkdown] = useState("");
  const [error, setError] = useState<unknown>(null);

  function load() {
    setError(null);
    api<{ markdown: string }>("/content/methodology")
      .then((payload) => setMarkdown(payload.markdown))
      .catch(setError);
  }

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const payload = await api<{ markdown: string }>("/content/methodology");
        if (!cancelled) setMarkdown(payload.markdown);
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
        <h1>Help and methodology</h1>
        <p>The text below is the methodology document served by the API.</p>
      </header>
      <p>
        <a href="/privacy">Privacy and limitations</a>
      </p>
      <ErrorText error={error} />
      {error ? (
        <button type="button" onClick={load}>
          Retry
        </button>
      ) : null}
      {markdown ? <MarkdownView markdown={markdown} /> : null}
      {!markdown && !error ? <p>Loading methodology…</p> : null}
    </div>
  );
}
