"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { saveDraft } from "@/lib/draft";
import type { ElectionSpecification, ValidationReport } from "@/lib/types";
import { ErrorText } from "@/components/ErrorText";

interface ImportResult {
  dataset_id: string;
  warnings: string[];
  validation: ValidationReport;
  specification: ElectionSpecification;
  hypothetical: true;
}

export default function ImportPage() {
  const [schemas, setSchemas] = useState<string>("");
  const [schemaError, setSchemaError] = useState<unknown>(null);
  const [title, setTitle] = useState("");
  const [method, setMethod] = useState("plurality");
  const [iterations, setIterations] = useState("500");
  const [seed, setSeed] = useState("20241105");
  const [seats, setSeats] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [jsonText, setJsonText] = useState("");
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<Record<string, unknown>>("/imports/schemas")
      .then((payload) => setSchemas(JSON.stringify(payload, null, 2)))
      .catch((exc) => setSchemaError(exc));
  }, []);

  async function submitCsv(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setResult(null);
    if (!file) {
      setError(new Error("Choose a CSV file first."));
      return;
    }
    if (!title.trim()) {
      setError(new Error("Enter a title. The file was not uploaded."));
      return;
    }
    const iterationCount = Number(iterations);
    const seedNumber = Number(seed);
    if (!Number.isInteger(iterationCount) || !Number.isInteger(seedNumber)) {
      setError(new Error("Iterations and seed must be whole numbers. The file was not uploaded."));
      return;
    }
    const body = new FormData();
    body.set("file", file);
    body.set("title", title.trim());
    body.set("voting_method", method);
    body.set("iterations", String(iterationCount));
    body.set("seed", String(seedNumber));
    body.set("description", "Imported from a regional CSV.");
    if (seats.trim()) body.set("seats", seats.trim());
    setBusy(true);
    try {
      const imported = await api<ImportResult>("/imports/csv", { method: "POST", body });
      saveDraft(imported.specification);
      setResult(imported);
    } catch (exc) {
      setError(exc);
    } finally {
      setBusy(false);
    }
  }

  async function submitJson(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setResult(null);
    let specification: ElectionSpecification;
    try {
      const parsed = JSON.parse(jsonText) as { specification?: ElectionSpecification } | ElectionSpecification;
      specification = "specification" in parsed && parsed.specification ? parsed.specification : (parsed as ElectionSpecification);
    } catch {
      setError(new Error("The JSON could not be parsed. Nothing was imported."));
      return;
    }
    setBusy(true);
    try {
      const imported = await api<ImportResult>("/imports/json", {
        method: "POST",
        body: JSON.stringify({ specification, filename: "specification.json" }),
      });
      saveDraft(imported.specification);
      setResult(imported);
    } catch (exc) {
      setError(exc);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="stack">
      <header className="page-head">
        <h1>Data import</h1>
        <p>
          Import aggregate regional rows or a full specification. Files are validated and are not executed. Voter-level
          files are not a supported schema.
        </p>
      </header>
      <p>
        <a href="/api/v1/examples/datasets/regions.csv">Download the example regions CSV</a>
      </p>
      <ErrorText error={schemaError} />
      {schemas ? (
        <section className="card stack">
          <h2>Supported schemas</h2>
          <pre className="code-block">{schemas}</pre>
        </section>
      ) : null}
      <form className="card stack" onSubmit={(event) => void submitCsv(event)}>
        <h2>CSV regions</h2>
        <label className="field">
          <span>Title</span>
          <input value={title} onChange={(event) => setTitle(event.target.value)} />
        </label>
        <label className="field">
          <span>Voting method</span>
          <select value={method} onChange={(event) => setMethod(event.target.value)}>
            <option value="plurality">plurality</option>
            <option value="two_round">two_round</option>
            <option value="ranked_choice">ranked_choice</option>
            <option value="dhondt">dhondt</option>
          </select>
        </label>
        <label className="field">
          <span>Iterations</span>
          <input value={iterations} onChange={(event) => setIterations(event.target.value)} />
        </label>
        <label className="field">
          <span>Seed</span>
          <input value={seed} onChange={(event) => setSeed(event.target.value)} />
        </label>
        <label className="field">
          <span>Seats, required for D&apos;Hondt</span>
          <input value={seats} onChange={(event) => setSeats(event.target.value)} />
        </label>
        <label className="field">
          <span>CSV file</span>
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
        </label>
        <button type="submit" disabled={busy}>
          {busy ? "Importing…" : "Import CSV"}
        </button>
      </form>
      <form className="card stack" onSubmit={(event) => void submitJson(event)}>
        <h2>JSON specification</h2>
        <label className="field">
          <span>Specification JSON</span>
          <textarea rows={10} value={jsonText} onChange={(event) => setJsonText(event.target.value)} />
        </label>
        <button type="submit" disabled={busy}>
          Import JSON
        </button>
      </form>
      <ErrorText error={error} />
      {result ? (
        <section className="card stack">
          <h2>Import accepted</h2>
          <p>Dataset {result.dataset_id}. The draft configuration was saved in this browser.</p>
          {result.warnings.map((warning) => (
            <p key={warning}>{warning}</p>
          ))}
          <a className="button" href="/configure">
            Review configuration
          </a>
        </section>
      ) : null}
    </div>
  );
}
