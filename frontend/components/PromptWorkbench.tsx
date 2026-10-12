"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { saveDraft } from "@/lib/draft";
import type { ExamplePrompt, InterpretationResult } from "@/lib/types";
import { ErrorText } from "./ErrorText";

export function PromptWorkbench({
  heading,
  intro,
}: {
  heading: string;
  intro: string;
}) {
  const [prompt, setPrompt] = useState("");
  const [examples, setExamples] = useState<ExamplePrompt[]>([]);
  const [examplesError, setExamplesError] = useState<unknown>(null);
  const [result, setResult] = useState<InterpretationResult | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function loadExamples() {
    setExamplesError(null);
    try {
      const payload = await api<{ prompts: ExamplePrompt[] }>("/examples");
      setExamples(payload.prompts);
    } catch (exc) {
      setExamplesError(exc);
    }
  }

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const payload = await api<{ prompts: ExamplePrompt[] }>("/examples");
        if (!cancelled) setExamples(payload.prompts);
      } catch (exc) {
        if (!cancelled) setExamplesError(exc);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function interpret(text: string) {
    const trimmed = text.trim();
    if (!trimmed) {
      setError(new Error("Enter a prompt before interpreting it."));
      setResult(null);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const interpreted = await api<InterpretationResult>("/interpret", {
        method: "POST",
        body: JSON.stringify({ prompt: trimmed }),
      });
      saveDraft(interpreted.specification);
      setResult(interpreted);
    } catch (exc) {
      setResult(null);
      setError(exc);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="stack">
      <header className="page-head">
        <h1>{heading}</h1>
        <p>{intro}</p>
      </header>
      <form
        className="card stack"
        onSubmit={(event) => {
          event.preventDefault();
          void interpret(prompt);
        }}
      >
        <label className="field">
          <span>Election prompt</span>
          <textarea
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            rows={8}
            placeholder="Describe the electorate, candidates, turnout, ballots, method, and iterations."
          />
        </label>
        <div className="button-row">
          <button type="submit" disabled={busy}>
            {busy ? "Interpreting…" : "Interpret prompt"}
          </button>
          <a className="button secondary" href="/configure">
            Open configuration editor
          </a>
        </div>
        <ErrorText error={error} />
      </form>

      <section className="card stack">
        <h2>Example prompts</h2>
        <p>One click loads the example and interprets it. Review the assumptions before running.</p>
        {examplesError ? (
          <div>
            <ErrorText error={examplesError} />
            <button type="button" onClick={() => void loadExamples()}>
              Retry examples
            </button>
          </div>
        ) : null}
        {examples.length === 0 && !examplesError ? <p>Loading examples…</p> : null}
        <ul className="example-list">
          {examples.map((example) => (
            <li key={example.id}>
              <h3>{example.title}</h3>
              <p>{example.description}</p>
              <button
                type="button"
                onClick={() => {
                  setPrompt(example.prompt);
                  void interpret(example.prompt);
                }}
                disabled={busy}
              >
                Load and interpret
              </button>
            </li>
          ))}
        </ul>
      </section>

      {result ? (
        <section className="card stack">
          <h2>Interpreted specification</h2>
          <p>
            Interpreter mode: <strong>{result.interpreter_mode}</strong>. Language model configured:{" "}
            <strong>{result.llm_configured ? "yes" : "no"}</strong>.
          </p>
          {result.notices.map((notice) => (
            <p key={notice} className="notice">
              {notice}
            </p>
          ))}
          <dl className="meta-list">
            <div>
              <dt>Title</dt>
              <dd>{result.specification.title}</dd>
            </div>
            <div>
              <dt>Method</dt>
              <dd>{result.specification.voting_method}</dd>
            </div>
            <div>
              <dt>Eligible voters</dt>
              <dd>
                {result.specification.regions.reduce((sum, region) => sum + region.eligible_voters, 0).toLocaleString("en-US")}
              </dd>
            </div>
            <div>
              <dt>Iterations</dt>
              <dd>{result.specification.iterations.toLocaleString("en-US")}</dd>
            </div>
            <div>
              <dt>Seed</dt>
              <dd>{result.specification.seed}</dd>
            </div>
          </dl>
          <h3>Assumptions</h3>
          <AssumptionTable assumptions={result.specification.assumptions} />
          <a className="button" href="/configure">
            Review and edit configuration
          </a>
        </section>
      ) : null}
    </section>
  );
}

export function AssumptionTable({
  assumptions,
}: {
  assumptions: { field: string; source: string; note: string }[];
}) {
  if (assumptions.length === 0) return <p>No assumption notes were recorded.</p>;
  return (
    <div className="table-wrap">
      <table>
        <caption>Extracted facts and inferred assumptions</caption>
        <thead>
          <tr>
            <th scope="col">Field</th>
            <th scope="col">Source</th>
            <th scope="col">Note</th>
          </tr>
        </thead>
        <tbody>
          {assumptions.map((item, index) => (
            <tr key={`${item.field}-${index}`}>
              <td>{item.field}</td>
              <td>
                <span className={`source source-${item.source}`}>{item.source}</span>
              </td>
              <td>{item.note}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
