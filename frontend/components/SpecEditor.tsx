"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { saveDraft } from "@/lib/draft";
import { preferenceSum, slugify, touchUser, withCandidatePreferences } from "@/lib/spec";
import type {
  ElectionSpecification,
  PreviewResponse,
  ScenarioSpec,
  ValidationReport,
  VotingMethod,
} from "@/lib/types";
import { AssumptionTable } from "./PromptWorkbench";
import { ErrorText } from "./ErrorText";
import { NumberField, TextField } from "./Fields";

const METHODS: VotingMethod[] = ["plurality", "two_round", "ranked_choice", "dhondt"];

export function SpecEditor({
  spec,
  onChange,
  simulationId,
}: {
  spec: ElectionSpecification;
  onChange: (spec: ElectionSpecification) => void;
  simulationId?: string | null;
}) {
  const [report, setReport] = useState<ValidationReport | null>(null);
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [advanced, setAdvanced] = useState(JSON.stringify(spec, null, 2));
  const [advancedError, setAdvancedError] = useState<string | null>(null);
  const [projectName, setProjectName] = useState("");
  const router = useRouter();

  function commit(next: ElectionSpecification) {
    const touched = touchUser(next);
    onChange(touched);
    saveDraft(touched);
    setAdvanced(JSON.stringify(touched, null, 2));
    setPreview(null);
  }

  async function validate() {
    setBusy("validate");
    setError(null);
    try {
      const next = await api<ValidationReport>("/simulations/validate", {
        method: "POST",
        body: JSON.stringify({ specification: spec, project_name: projectName || null }),
      });
      setReport(next);
    } catch (exc) {
      setError(exc);
    } finally {
      setBusy(null);
    }
  }

  async function runPreview() {
    setBusy("preview");
    setError(null);
    try {
      const next = await api<PreviewResponse>("/simulations/preview", {
        method: "POST",
        body: JSON.stringify({ specification: spec }),
      });
      setPreview(next);
      setReport(next.validation);
    } catch (exc) {
      setError(exc);
    } finally {
      setBusy(null);
    }
  }

  async function saveSimulation() {
    setBusy("save");
    setError(null);
    try {
      const path = simulationId ? `/simulations/${simulationId}` : "/simulations";
      const method = simulationId ? "PATCH" : "POST";
      const saved = await api<{ id: string }>(path, {
        method,
        body: JSON.stringify({ specification: spec, project_name: projectName || null }),
      });
      router.push(`/simulations/${saved.id}/run`);
    } catch (exc) {
      setError(exc);
      setBusy(null);
    }
  }

  function applyAdvanced() {
    try {
      const parsed = JSON.parse(advanced) as ElectionSpecification;
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        setAdvancedError("The JSON must be an object. It was not applied.");
        return;
      }
      setAdvancedError(null);
      commit(parsed);
    } catch {
      setAdvancedError("The JSON could not be parsed. The configuration was not changed.");
    }
  }

  const candidateIds = spec.candidates.map((candidate) => candidate.id);

  return (
    <div className="stack">
      <section className="card stack">
        <h2>Election</h2>
        <TextField label="Title" value={spec.title} onValue={(title) => commit({ ...spec, title })} />
        <label className="field">
          <span>Description</span>
          <textarea
            rows={3}
            value={spec.description}
            onChange={(event) => commit({ ...spec, description: event.target.value })}
          />
        </label>
        <label className="field">
          <span>Voting method</span>
          <select
            value={spec.voting_method}
            onChange={(event) => commit({ ...spec, voting_method: event.target.value as VotingMethod })}
          >
            {METHODS.map((method) => (
              <option key={method} value={method}>
                {method}
              </option>
            ))}
          </select>
        </label>
        <div className="grid-2">
          <NumberField
            label="Iterations"
            integer
            value={spec.iterations}
            onValue={(iterations) => commit({ ...spec, iterations })}
          />
          <NumberField label="Random seed" integer value={spec.seed} onValue={(seed) => commit({ ...spec, seed })} />
          <NumberField
            label="Runoff threshold"
            value={spec.runoff_threshold}
            hint="Used by two-round elections. A unique leader must exceed this share to win in round one."
            onValue={(runoff_threshold) => commit({ ...spec, runoff_threshold })}
          />
          <NumberField
            label="Seats"
            integer
            value={spec.seats ?? 0}
            hint="Required for D'Hondt. Leave 0 only when the method does not allocate seats; plurality rejects a seat total above 1."
            onValue={(seats) => commit({ ...spec, seats: spec.voting_method === "dhondt" ? seats : seats === 0 ? null : seats })}
          />
          <NumberField
            label="Shared turnout shock SD"
            value={spec.turnout_shock_sd}
            hint="0 keeps independent binomial turnout. A positive value adds one shared normal shock and withholds closed-form expectations."
            onValue={(turnout_shock_sd) => commit({ ...spec, turnout_shock_sd })}
          />
        </div>
        <label className="check">
          <input
            type="checkbox"
            checked={spec.empirical_data}
            onChange={(event) => commit({ ...spec, empirical_data: event.target.checked })}
          />
          <span>These inputs were supplied as user data. The outputs remain hypothetical simulations.</span>
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={spec.reporting.include_regional}
            onChange={(event) =>
              commit({ ...spec, reporting: { ...spec.reporting, include_regional: event.target.checked } })
            }
          />
          <span>Include regional summaries</span>
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={spec.reporting.include_histograms}
            onChange={(event) =>
              commit({ ...spec, reporting: { ...spec.reporting, include_histograms: event.target.checked } })
            }
          />
          <span>Include vote histograms</span>
        </label>
      </section>

      <section className="card stack">
        <h2>Candidates</h2>
        {spec.candidates.map((candidate, index) => (
          <div className="split" key={candidate.id}>
            <TextField
              label={`Name for ${candidate.id}`}
              value={candidate.name}
              onValue={(name) => {
                const candidates = spec.candidates.map((item, itemIndex) =>
                  itemIndex === index ? { ...item, name } : item,
                );
                commit({ ...spec, candidates });
              }}
            />
            <button
              type="button"
              className="secondary"
              onClick={() => {
                const removed = candidate.id;
                const candidates = spec.candidates.filter((item) => item.id !== removed);
                const regions = spec.regions.map((region) => {
                  const preferences = { ...region.preferences };
                  delete preferences[removed];
                  return { ...region, preferences };
                });
                commit({ ...spec, candidates, regions });
              }}
              disabled={spec.candidates.length <= 1}
            >
              Remove {candidate.name}
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={() => {
            const id = slugify("candidate", candidateIds);
            const candidates = [...spec.candidates, { id, name: "New candidate" }];
            const regions = spec.regions.map((region) => ({
              ...region,
              preferences: { ...region.preferences, [id]: 0 },
            }));
            commit({
              ...spec,
              candidates,
              regions,
              assumptions: [
                ...spec.assumptions,
                {
                  field: `preferences.${id}`,
                  source: "user",
                  note: "A new candidate was added with preference 0 in every region so the other probabilities were not renormalized. Set the distribution yourself.",
                },
              ],
            });
          }}
        >
          Add candidate
        </button>
        <p className="hint">Removing a candidate does not rescale the remaining probabilities. Validate before saving.</p>
      </section>

      <section className="card stack">
        <h2>Regions</h2>
        {spec.regions.map((region, index) => {
          const sum = preferenceSum(region.preferences);
          return (
            <details key={region.id} open={spec.regions.length < 4}>
              <summary>
                {region.name} · {region.eligible_voters.toLocaleString("en-US")} eligible · preference sum {sum.toFixed(4)}
              </summary>
              <div className="stack inner">
                <TextField
                  label="Region name"
                  value={region.name}
                  onValue={(name) => updateRegion(index, { name })}
                />
                <div className="grid-2">
                  <NumberField
                    label="Eligible voters"
                    integer
                    value={region.eligible_voters}
                    onValue={(eligible_voters) => updateRegion(index, { eligible_voters })}
                  />
                  <NumberField
                    label="Turnout probability"
                    value={region.turnout_probability}
                    onValue={(turnout_probability) => updateRegion(index, { turnout_probability })}
                  />
                  <NumberField
                    label="Blank rate, given a ballot is cast"
                    value={region.blank_rate}
                    onValue={(blank_rate) => updateRegion(index, { blank_rate })}
                  />
                  <NumberField
                    label="Invalid rate, given a ballot is cast"
                    value={region.invalid_rate}
                    onValue={(invalid_rate) => updateRegion(index, { invalid_rate })}
                  />
                </div>
                <h3>Preferences on valid ballots</h3>
                {candidateIds.map((id) => (
                  <NumberField
                    key={id}
                    label={spec.candidates.find((candidate) => candidate.id === id)?.name || id}
                    value={region.preferences[id] ?? 0}
                    onValue={(value) =>
                      updateRegion(index, { preferences: { ...region.preferences, [id]: value } })
                    }
                  />
                ))}
                {Math.abs(sum - 1) > 1e-6 ? (
                  <p className="field-error">
                    Preferences sum to {sum.toFixed(6)}. The server will reject this region until they sum to 1. They
                    are not rescaled automatically.
                  </p>
                ) : (
                  <p className="hint">Preferences sum to 1.</p>
                )}
                {region.segments?.length ? (
                  <p className="notice">
                    This region has {region.segments.length} demographic segment(s). Segment rates are used instead of
                    the region rates above. Edit segments in Advanced JSON so they are not dropped.
                  </p>
                ) : null}
                {region.ranking_blocs?.length ? (
                  <p className="notice">
                    This region has ranking blocs. Edit them in Advanced JSON. The form keeps them when you change
                    other region fields.
                  </p>
                ) : null}
                <button
                  type="button"
                  className="secondary"
                  disabled={spec.regions.length <= 1}
                  onClick={() => commit({ ...spec, regions: spec.regions.filter((_, itemIndex) => itemIndex !== index) })}
                >
                  Remove region
                </button>
              </div>
            </details>
          );
        })}
        <button
          type="button"
          onClick={() => {
            const id = slugify("region", spec.regions.map((region) => region.id));
            const equal = 1 / candidateIds.length;
            const preferences: Record<string, number> = {};
            candidateIds.forEach((candidateId, candidateIndex) => {
              preferences[candidateId] =
                candidateIndex === candidateIds.length - 1
                  ? 1 - equal * (candidateIds.length - 1)
                  : equal;
            });
            const region = {
              id,
              name: "New region",
              eligible_voters: 0,
              turnout_probability: 0,
              preferences,
              blank_rate: 0,
              invalid_rate: 0,
            };
            commit({
              ...spec,
              regions: [...spec.regions, region],
              assumptions: [
                ...spec.assumptions,
                {
                  field: id,
                  source: "inferred",
                  note: "New region starts at 0 eligible voters and equal placeholder preferences. Enter the population and preferences. This is not empirical data.",
                },
              ],
            });
          }}
        >
          Add region
        </button>
      </section>

      <section className="card stack">
        <h2>Scenarios</h2>
        {spec.scenarios.length === 0 ? (
          <p>No named scenarios. A run uses one implicit baseline.</p>
        ) : null}
        {spec.scenarios.map((scenario, index) => (
          <fieldset key={scenario.id} className="stack">
            <legend>{scenario.name}</legend>
            <TextField label="Scenario name" value={scenario.name} onValue={(name) => updateScenario(index, { name })} />
            <TextField
              label="Description"
              value={scenario.description}
              onValue={(description) => updateScenario(index, { description })}
            />
            <NumberField
              label="Turnout multiplier"
              value={scenario.turnout_multiplier ?? 1}
              hint="1 leaves turnout unchanged. The multiplier is clipped to a probability after it is applied."
              onValue={(turnout_multiplier) => updateScenario(index, { turnout_multiplier })}
            />
            <label className="field">
              <span>Voting method override</span>
              <select
                value={scenario.voting_method_override ?? ""}
                onChange={(event) =>
                  updateScenario(index, {
                    voting_method_override: event.target.value
                      ? (event.target.value as VotingMethod)
                      : null,
                  })
                }
              >
                <option value="">No override</option>
                {METHODS.map((method) => (
                  <option key={method} value={method}>
                    {method}
                  </option>
                ))}
              </select>
            </label>
            <button type="button" className="secondary" onClick={() => removeScenario(index)}>
              Remove scenario
            </button>
          </fieldset>
        ))}
        <button
          type="button"
          onClick={() => {
            const id = slugify("scenario", spec.scenarios.map((scenario) => scenario.id));
            const scenario: ScenarioSpec = {
              id,
              name: "New scenario",
              description: "",
              turnout_multiplier: 1,
            };
            commit({ ...spec, scenarios: [...spec.scenarios, scenario] });
          }}
        >
          Add scenario
        </button>
      </section>

      <section className="card stack">
        <h2>Assumptions</h2>
        <AssumptionTable assumptions={spec.assumptions} />
        {spec.assumptions.map((assumption, index) => (
          <label className="field" key={`${assumption.field}-${index}`}>
            <span>
              Note for {assumption.field} ({assumption.source})
            </span>
            <textarea
              rows={2}
              value={assumption.note}
              onChange={(event) => {
                const assumptions = spec.assumptions.map((item, itemIndex) =>
                  itemIndex === index ? { ...item, note: event.target.value } : item,
                );
                commit({ ...spec, assumptions });
              }}
            />
          </label>
        ))}
      </section>

      <section className="card stack">
        <h2>Advanced JSON</h2>
        <p>
          Use this for segments, ranking blocs, runoff transfers, and preference overrides. Applying invalid JSON does
          not change the configuration. The server still validates every field.
        </p>
        <textarea rows={14} value={advanced} onChange={(event) => setAdvanced(event.target.value)} spellCheck={false} />
        {advancedError ? <p className="field-error">{advancedError}</p> : null}
        <button type="button" onClick={applyAdvanced}>
          Apply JSON
        </button>
      </section>

      <section className="card stack">
        <h2>Check and save</h2>
        <TextField
          label="Project name (optional)"
          value={projectName}
          onValue={setProjectName}
          hint="Simulations with the same project name are grouped. Leave blank to use the election title."
        />
        <div className="button-row">
          <button type="button" onClick={() => void validate()} disabled={busy !== null}>
            {busy === "validate" ? "Validating…" : "Validate"}
          </button>
          <button type="button" className="secondary" onClick={() => void runPreview()} disabled={busy !== null}>
            {busy === "preview" ? "Calculating…" : "Preview expectations"}
          </button>
          <button type="button" onClick={() => void saveSimulation()} disabled={busy !== null}>
            {busy === "save" ? "Saving…" : simulationId ? "Update saved simulation" : "Save and continue to run"}
          </button>
        </div>
        <ErrorText error={error} />
        {report ? (
          <div>
            <p>{report.valid ? "The specification passed validation." : "Validation failed. Nothing was rewritten."}</p>
            {report.errors.length > 0 ? (
              <ul>
                {report.errors.map((issue) => (
                  <li key={`${issue.field}-${issue.message}`}>
                    {issue.field}: {issue.message}
                  </li>
                ))}
              </ul>
            ) : null}
            {report.warnings.length > 0 ? (
              <ul>
                {report.warnings.map((issue) => (
                  <li key={`${issue.field}-${issue.message}`}>
                    Warning — {issue.field}: {issue.message}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}
        {preview ? (
          <div>
            <p>{preview.note}</p>
            <p>{preview.expectations?.note}</p>
            {preview.expectations?.ballots != null ? (
              <p>
                Analytical expected ballots: {preview.expectations.ballots.toLocaleString("en-US")}. This can be
                fractional and is not an observed count.
              </p>
            ) : (
              <p>No closed-form ballot expectation is available for this specification.</p>
            )}
          </div>
        ) : null}
      </section>
    </div>
  );

  function updateRegion(index: number, patch: Partial<ElectionSpecification["regions"][number]>) {
    const regions = spec.regions.map((region, regionIndex) =>
      regionIndex === index ? withCandidatePreferences({ ...region, ...patch }, candidateIds) : region,
    );
    commit({ ...spec, regions });
  }

  function updateScenario(index: number, patch: Partial<ScenarioSpec>) {
    const scenarios = spec.scenarios.map((scenario, scenarioIndex) =>
      scenarioIndex === index ? { ...scenario, ...patch } : scenario,
    );
    commit({ ...spec, scenarios });
  }

  function removeScenario(index: number) {
    commit({ ...spec, scenarios: spec.scenarios.filter((_, scenarioIndex) => scenarioIndex !== index) });
  }
}
