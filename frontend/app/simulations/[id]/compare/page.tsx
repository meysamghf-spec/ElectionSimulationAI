"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, downloadFile } from "@/lib/api";
import type { ComparisonResult, SimulationOutput } from "@/lib/types";
import { ComparisonTable } from "@/components/ResultsView";
import { ErrorText } from "@/components/ErrorText";
import { BarPanel } from "@/components/Charts";

export default function ComparePage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [output, setOutput] = useState<SimulationOutput | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [left, setLeft] = useState("");
  const [right, setRight] = useState("");
  const [comparison, setComparison] = useState<ComparisonResult | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<SimulationOutput>(`/simulations/${id}/results`)
      .then((payload) => {
        setOutput(payload);
        if (payload.scenarios.length >= 2) {
          setLeft(payload.scenarios[0].scenario_id);
          setRight(payload.scenarios[1].scenario_id);
        } else if (payload.scenarios.length === 1) {
          setLeft(payload.scenarios[0].scenario_id);
          setRight(payload.scenarios[0].scenario_id);
        }
      })
      .catch(setError);
  }, [id]);

  async function compare(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const payload = await api<ComparisonResult>(`/simulations/${id}/compare`, {
        method: "POST",
        body: JSON.stringify({ left_scenario_id: left, right_scenario_id: right }),
      });
      setComparison(payload);
    } catch (exc) {
      setError(exc);
    } finally {
      setBusy(false);
    }
  }

  const canCompare = Boolean(output && output.scenarios.length >= 2 && left && right && left !== right);

  return (
    <div className="stack">
      <header className="page-head">
        <h1>Scenario comparison</h1>
        <p>
          Percentage-point change is an absolute share difference. Relative change is the share difference divided by
          the left scenario&apos;s share.
        </p>
      </header>
      <ErrorText error={error} />
      {!output && !error ? <p>Loading scenarios…</p> : null}
      {output && output.scenarios.length < 2 ? (
        <p>This run has fewer than two scenarios. Comparison stays disabled until a run contains at least two.</p>
      ) : null}
      {output && output.scenarios.length >= 2 ? (
        <form className="card stack" onSubmit={(event) => void compare(event)}>
          <label className="field">
            <span>Left scenario</span>
            <select value={left} onChange={(event) => setLeft(event.target.value)}>
              {output.scenarios.map((scenario) => (
                <option key={scenario.scenario_id} value={scenario.scenario_id}>
                  {scenario.scenario_name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Right scenario</span>
            <select value={right} onChange={(event) => setRight(event.target.value)}>
              {output.scenarios.map((scenario) => (
                <option key={scenario.scenario_id} value={scenario.scenario_id}>
                  {scenario.scenario_name}
                </option>
              ))}
            </select>
          </label>
          <div className="button-row">
            <button type="submit" disabled={!canCompare || busy}>
              {busy ? "Comparing…" : "Compare"}
            </button>
            <button
              type="button"
              className="secondary"
              disabled={!canCompare}
              onClick={() =>
                void downloadFile(
                  `/simulations/${id}/compare.csv?left=${encodeURIComponent(left)}&right=${encodeURIComponent(right)}`,
                  "comparison.csv",
                ).catch(setError)
              }
            >
              Download comparison CSV
            </button>
          </div>
          {!canCompare ? <p className="hint">Choose two different scenarios.</p> : null}
        </form>
      ) : null}
      {comparison ? (
        <section className="card stack">
          <ComparisonTable comparison={comparison} />
          <BarPanel
            title="Vote difference (right minus left)"
            testId="comparison-chart"
            label="Vote difference"
            rows={comparison.candidates.map((candidate) => ({
              name: candidate.name,
              value: candidate.vote_difference,
            }))}
          />
        </section>
      ) : null}
      {output && output.reference_comparisons.length > 0 ? (
        <section className="stack">
          <h2>Comparisons stored with the run</h2>
          {output.reference_comparisons.map((item) => (
            <section className="card" key={`${item.left_scenario_id}-${item.right_scenario_id}`}>
              <ComparisonTable comparison={item} />
            </section>
          ))}
        </section>
      ) : null}
    </div>
  );
}
