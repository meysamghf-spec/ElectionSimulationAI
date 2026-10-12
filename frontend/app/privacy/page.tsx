"use client";

import { useEffect, useState } from "react";
import { MarkdownView } from "@/components/MarkdownView";
import { ErrorText } from "@/components/ErrorText";
import { api } from "@/lib/api";

export default function PrivacyPage() {
  const [markdown, setMarkdown] = useState("");
  const [error, setError] = useState<unknown>(null);

  function load() {
    setError(null);
    api<{ markdown: string }>("/content/privacy")
      .then((payload) => setMarkdown(payload.markdown))
      .catch(setError);
  }

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const payload = await api<{ markdown: string }>("/content/privacy");
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
        <h1>Privacy and limitations</h1>
        <p>This tool does not build individual voter profiles or persuasion features.</p>
      </header>
      <ErrorText error={error} />
      {error ? (
        <button type="button" onClick={load}>
          Retry
        </button>
      ) : null}
      {markdown ? <MarkdownView markdown={markdown} /> : null}
      {!markdown && !error ? <p>Loading privacy notes…</p> : null}
    </div>
  );
}
