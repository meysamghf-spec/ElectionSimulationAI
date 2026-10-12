"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { SpecEditor } from "@/components/SpecEditor";
import { useDraft } from "@/components/useDraft";
import { placeholderSpec } from "@/lib/spec";

export function ConfigureEditor() {
  const params = useSearchParams();
  const simulationId = params.get("id");
  const { spec, update } = useDraft();

  if (!spec) {
    return (
      <div className="stack">
        <header className="page-head">
          <h1>Configuration editor</h1>
          <p>There is no draft yet. Start from a prompt, import a file, or open a labeled placeholder.</p>
        </header>
        <div className="button-row">
          <Link className="button" href="/prompt">
            Write a prompt
          </Link>
          <Link className="button secondary" href="/import">
            Import data
          </Link>
          <button
            type="button"
            onClick={() => update(placeholderSpec())}
          >
            Open a placeholder specification
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="stack">
      <header className="page-head">
        <h1>Configuration editor</h1>
        <p>
          Changes stay in this browser until you save. Invalid probabilities are left as entered so the server can
          reject them instead of silently repairing them.
        </p>
        {simulationId ? <p>Updating saved simulation {simulationId}.</p> : null}
      </header>
      <SpecEditor spec={spec} onChange={update} simulationId={simulationId} />
    </div>
  );
}
