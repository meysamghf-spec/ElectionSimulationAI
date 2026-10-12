"use client";

import { useMemo, useState } from "react";
import { formatNumber, formatPercentagePoints, formatSeconds, formatShare } from "@/lib/format";
import type { ComparisonResult, ScenarioResult, SensitivityReport, SimulationOutput } from "@/lib/types";
import { BarPanel } from "./Charts";

export function ResultsView({
  output,
  simulationId,
  sensitivity,
  sensitivityLoading,
  onSensitivity,
  sensitivityError,
}: {
  output: SimulationOutput;
  simulationId: string;
  sensitivity: SensitivityReport | null;
  sensitivityLoading: boolean;
  onSensitivity: () => void;
  sensitivityError: unknown;
}) {
  const [scenarioId, setScenarioId] = useState(output.scenarios[0]?.scenario_id ?? "");
  const scenario = output.scenarios.find((item) => item.scenario_id === scenarioId) ?? output.scenarios[0];
  if (!scenario) return <p>This run did not return a scenario.</p>;

  return (
    <div className="stack">
      <nav className="section-nav" aria-label="Results sections">
        <a href="#overview">Overview</a>
        <a href="#candidates">Candidates</a>
        <a href="#geography">Geography</a>
        <a href="#statistics">Statistics</a>
        <a href="#comparison">Comparison</a>
        <a href="#details">Simulation details</a>
        <a href="#quality">Data quality</a>
      </nav>
      {output.scenarios.length > 1 ? (
        <label className="field">
          <span>Scenario shown in the sections below</span>
          <select value={scenario.scenario_id} onChange={(event) => setScenarioId(event.target.value)}>
            {output.scenarios.map((item) => (
              <option key={item.scenario_id} value={item.scenario_id}>
                {item.scenario_name}
              </option>
            ))}
          </select>
        </label>
      ) : null}
      <Overview scenario={scenario} />
      <Candidates scenario={scenario} />
      <Geography scenario={scenario} />
      <Statistics
        scenario={scenario}
        sensitivity={sensitivity}
        sensitivityLoading={sensitivityLoading}
        onSensitivity={onSensitivity}
        sensitivityError={sensitivityError}
      />
      <ComparisonBlock output={output} simulationId={simulationId} />
      <Details output={output} scenario={scenario} />
      <Quality output={output} scenario={scenario} />
    </div>
  );
}

function Overview({ scenario }: { scenario: ScenarioResult }) {
  return (
    <section id="overview" className="card stack">
      <h2>Overview</h2>
      <p className="notice">Hypothetical simulation. {scenario.expectation_note}</p>
      <dl className="stat-grid">
        <Stat label="Scenario" value={scenario.scenario_name} />
        <Stat label="Method" value={scenario.voting_method} />
        <Stat label="Eligible voters" value={formatNumber(scenario.eligible_voters)} />
        <Stat label="Mean ballots cast" value={formatNumber(scenario.mean_ballots, 1)} />
        <Stat label="Mean turnout" value={formatShare(scenario.mean_turnout_rate)} />
        <Stat label="Mean valid ballots" value={formatNumber(scenario.mean_valid, 1)} />
        <Stat label="Mean blank ballots" value={formatNumber(scenario.mean_blank, 1)} />
        <Stat label="Mean invalid ballots" value={formatNumber(scenario.mean_invalid, 1)} />
        <Stat
          label="Analytical expected ballots"
          value={scenario.expected_ballots == null ? "Withheld" : formatNumber(scenario.expected_ballots, 2)}
        />
      </dl>
      {scenario.parameter_notes.length > 0 ? (
        <ul>
          {scenario.parameter_notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function Candidates({ scenario }: { scenario: ScenarioResult }) {
  const rows = scenario.candidates.map((candidate) => ({ name: candidate.name, value: candidate.mean_votes }));
  const shareRows = scenario.candidates.map((candidate) => ({
    name: candidate.name,
    value: candidate.mean_share == null ? 0 : Number((candidate.mean_share * 100).toFixed(2)),
  }));
  return (
    <section id="candidates" className="card stack">
      <h2>Candidate results</h2>
      <p>Means are averages across Monte Carlo iterations. Shares are conditional on valid ballots when a share exists.</p>
      <div className="table-wrap">
        <table>
          <caption>Candidate summaries</caption>
          <thead>
            <tr>
              <th scope="col">Candidate</th>
              <th scope="col">Mean votes</th>
              <th scope="col">Median votes</th>
              <th scope="col">SD</th>
              <th scope="col">Mean share</th>
              <th scope="col">Sole win frequency</th>
              <th scope="col">Mean seats</th>
            </tr>
          </thead>
          <tbody>
            {scenario.candidates.map((candidate) => (
              <tr key={candidate.id}>
                <th scope="row">{candidate.name}</th>
                <td>{formatNumber(candidate.mean_votes, 2)}</td>
                <td>{formatNumber(candidate.median_votes, 2)}</td>
                <td>{formatNumber(candidate.std_votes, 2)}</td>
                <td>{formatShare(candidate.mean_share)}</td>
                <td>{formatShare(candidate.sole_win_frequency)}</td>
                <td>{candidate.mean_seats == null ? "—" : formatNumber(candidate.mean_seats, 2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <h3>Ranking by mean votes</h3>
      <ol>
        {scenario.ranking_by_mean_votes.map((id) => (
          <li key={id}>{scenario.candidates.find((candidate) => candidate.id === id)?.name || id}</li>
        ))}
      </ol>
      <Margins scenario={scenario} />
      <BarPanel title="Mean votes" rows={rows} label="Mean votes" testId="mean-votes-chart" />
      <BarPanel title="Mean vote share (percent)" rows={shareRows} label="Mean share %" testId="mean-share-chart" />
      {scenario.mean_second_round_votes ? (
        <div>
          <h3>Mean second-round votes</h3>
          <p>Runoff iterations: {scenario.runoff_iterations.toLocaleString("en-US")}</p>
          <ul>
            {Object.entries(scenario.mean_second_round_votes).map(([id, votes]) => (
              <li key={id}>
                {nameOf(scenario, id)}: {formatNumber(votes, 2)}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

function Margins({ scenario }: { scenario: ScenarioResult }) {
  const ranked = [...scenario.candidates].sort((left, right) => right.mean_votes - left.mean_votes);
  if (ranked.length < 2) return <p>One candidate is configured, so there is no margin between candidates.</p>;
  const margin = ranked[0].mean_votes - ranked[1].mean_votes;
  return (
    <p>
      Mean-vote margin between {ranked[0].name} and {ranked[1].name}: {formatNumber(margin, 2)} votes. A tie frequency
      above zero means some iterations did not have a unique leader.
    </p>
  );
}

function Geography({ scenario }: { scenario: ScenarioResult }) {
  if (scenario.regional.length === 0) {
    return (
      <section id="geography" className="card stack">
        <h2>Geographic analysis</h2>
        <p>Regional summaries were not included in this run. {scenario.regional_note}</p>
      </section>
    );
  }
  return (
    <section id="geography" className="card stack">
      <h2>Geographic analysis</h2>
      <p>{scenario.regional_note}</p>
      <div className="table-wrap">
        <table>
          <caption>Regional means</caption>
          <thead>
            <tr>
              <th scope="col">Region</th>
              <th scope="col">Eligible</th>
              <th scope="col">Mean ballots</th>
              <th scope="col">Mean turnout</th>
              <th scope="col">Mean valid</th>
              <th scope="col">Mean blank</th>
              <th scope="col">Mean invalid</th>
              {scenario.candidates.map((candidate) => (
                <th scope="col" key={candidate.id}>
                  {candidate.name} mean votes
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {scenario.regional.map((region) => (
              <tr key={region.id}>
                <th scope="row">{region.name}</th>
                <td>{formatNumber(region.eligible_voters)}</td>
                <td>{formatNumber(region.mean_ballots, 1)}</td>
                <td>{formatShare(region.mean_turnout_rate)}</td>
                <td>{formatNumber(region.mean_valid, 1)}</td>
                <td>{formatNumber(region.mean_blank, 1)}</td>
                <td>{formatNumber(region.mean_invalid, 1)}</td>
                {scenario.candidates.map((candidate) => (
                  <td key={candidate.id}>{formatNumber(region.mean_votes[candidate.id] ?? 0, 1)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Statistics({
  scenario,
  sensitivity,
  sensitivityLoading,
  onSensitivity,
  sensitivityError,
}: {
  scenario: ScenarioResult;
  sensitivity: SensitivityReport | null;
  sensitivityLoading: boolean;
  onSensitivity: () => void;
  sensitivityError: unknown;
}) {
  const histogram = scenario.candidates[0] ? scenario.vote_histograms[scenario.candidates[0].id] : undefined;
  const histogramRows = useMemo(() => histogramBins(histogram), [histogram]);
  return (
    <section id="statistics" className="card stack">
      <h2>Statistical analysis</h2>
      <p>
        Intervals below describe Monte Carlo uncertainty for this model. They are not confidence intervals for an
        unobserved real electorate.
      </p>
      <div className="table-wrap">
        <table>
          <caption>Vote quantiles and simulation intervals</caption>
          <thead>
            <tr>
              <th scope="col">Candidate</th>
              <th scope="col">p05</th>
              <th scope="col">p50</th>
              <th scope="col">p95</th>
              <th scope="col">Mean-vote interval</th>
              <th scope="col">Sole-win frequency interval</th>
            </tr>
          </thead>
          <tbody>
            {scenario.candidates.map((candidate) => (
              <tr key={candidate.id}>
                <th scope="row">{candidate.name}</th>
                <td>{formatNumber(candidate.vote_quantiles.p05, 1)}</td>
                <td>{formatNumber(candidate.vote_quantiles.p50, 1)}</td>
                <td>{formatNumber(candidate.vote_quantiles.p95, 1)}</td>
                <td>
                  {formatNumber(candidate.vote_mean_interval.low, 1)} – {formatNumber(candidate.vote_mean_interval.high, 1)}
                  <span className="hint"> {candidate.vote_mean_interval.method}</span>
                </td>
                <td>
                  {formatShare(candidate.sole_win_frequency_interval.low)} –{" "}
                  {formatShare(candidate.sole_win_frequency_interval.high)}
                  <span className="hint"> {candidate.sole_win_frequency_interval.meaning}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {histogramRows.length > 0 ? (
        <BarPanel
          title={`${scenario.candidates[0].name} vote histogram`}
          rows={histogramRows}
          label="Iterations"
          testId="histogram-chart"
        />
      ) : (
        <p>Histograms were not stored for this run.</p>
      )}
      <h3>Sensitivity</h3>
      <p>
        A sensitivity sweep reruns a smaller simulation. It does not change the saved Monte Carlo results above.
      </p>
      <button type="button" onClick={onSensitivity} disabled={sensitivityLoading}>
        {sensitivityLoading ? "Running sensitivity…" : "Run sensitivity sweep"}
      </button>
      {sensitivityError instanceof Error ? <p className="field-error">{sensitivityError.message}</p> : null}
      {sensitivity ? <SensitivityTable report={sensitivity} /> : null}
    </section>
  );
}

function SensitivityTable({ report }: { report: SensitivityReport }) {
  const rows = report.variations
    .filter((item) => item.applied && item.max_absolute_share_percentage_points != null)
    .map((item) => ({
      name: `${item.parameter}: ${item.change}`,
      value: item.max_absolute_share_percentage_points ?? 0,
    }));
  return (
    <div className="stack">
      <p>{report.design}</p>
      <p>
        Varied: {report.varied_parameters.join(", ") || "none"}. Held constant: {report.held_constant.join(", ")}.
      </p>
      <p>
        Largest effect: {report.largest_effect_parameter ?? "none"} {report.largest_effect_change ?? ""} (
        {report.largest_effect_percentage_points == null
          ? "—"
          : formatPercentagePoints(report.largest_effect_percentage_points)}
        ).
      </p>
      <p>{report.note}</p>
      {rows.length > 0 ? (
        <BarPanel title="Maximum absolute share change" rows={rows} label="Percentage points" testId="sensitivity-chart" />
      ) : (
        <p>No applied variation produced a share change to chart.</p>
      )}
      <div className="table-wrap">
        <table>
          <caption>Sensitivity variations</caption>
          <thead>
            <tr>
              <th scope="col">Parameter</th>
              <th scope="col">Change</th>
              <th scope="col">Applied</th>
              <th scope="col">Max absolute share change</th>
              <th scope="col">Reason</th>
            </tr>
          </thead>
          <tbody>
            {report.variations.map((item) => (
              <tr key={`${item.parameter}-${item.change}`}>
                <td>{item.parameter}</td>
                <td>{item.change}</td>
                <td>{item.applied ? "yes" : "no"}</td>
                <td>{formatPercentagePoints(item.max_absolute_share_percentage_points)}</td>
                <td>{item.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ComparisonBlock({ output, simulationId }: { output: SimulationOutput; simulationId: string }) {
  return (
    <section id="comparison" className="card stack">
      <h2>Scenario comparison</h2>
      {output.reference_comparisons.length === 0 ? (
        <p>This run has no stored pairwise comparison. Open the comparison page after a multi-scenario run.</p>
      ) : (
        output.reference_comparisons.map((comparison) => (
          <ComparisonTable key={`${comparison.left_scenario_id}-${comparison.right_scenario_id}`} comparison={comparison} />
        ))
      )}
      {simulationId ? (
        <a className="button secondary" href={`/simulations/${simulationId}/compare`}>
          Open comparison tools
        </a>
      ) : (
        <p>Comparison tools are available from a saved simulation.</p>
      )}
    </section>
  );
}

export function ComparisonTable({ comparison }: { comparison: ComparisonResult }) {
  return (
    <div className="stack">
      <h3>
        {comparison.left_scenario_name} compared with {comparison.right_scenario_name}
      </h3>
      <p>{comparison.explanation}</p>
      <dl className="stat-grid">
        <Stat label="Ballot difference (right − left)" value={formatNumber(comparison.mean_ballots_difference, 2)} />
        <Stat
          label="Turnout difference"
          value={
            comparison.turnout_percentage_point_difference == null
              ? "—"
              : formatPercentagePoints(comparison.turnout_percentage_point_difference)
          }
        />
        <Stat label="Valid ballot difference" value={formatNumber(comparison.mean_valid_difference, 2)} />
      </dl>
      <div className="table-wrap">
        <table>
          <caption>Candidate differences</caption>
          <thead>
            <tr>
              <th scope="col">Candidate</th>
              <th scope="col">Vote difference</th>
              <th scope="col">Percentage-point share change</th>
              <th scope="col">Relative share change</th>
              <th scope="col">Seat difference</th>
            </tr>
          </thead>
          <tbody>
            {comparison.candidates.map((candidate) => (
              <tr key={candidate.id}>
                <th scope="row">{candidate.name}</th>
                <td>{formatNumber(candidate.vote_difference, 2)}</td>
                <td>{formatPercentagePoints(candidate.percentage_point_difference)}</td>
                <td>{formatRelative(candidate.relative_share_change)}</td>
                <td>
                  {candidate.left_mean_seats == null || candidate.right_mean_seats == null
                    ? "—"
                    : formatNumber(candidate.right_mean_seats - candidate.left_mean_seats, 2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function formatRelative(value: number | null): string {
  if (value == null || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(2)}% relative`;
}

function Details({ output, scenario }: { output: SimulationOutput; scenario: ScenarioResult }) {
  return (
    <section id="details" className="card stack">
      <h2>Simulation details</h2>
      <dl className="meta-list">
        <div>
          <dt>Algorithm version</dt>
          <dd>{output.algorithm_version}</dd>
        </div>
        <div>
          <dt>Seed</dt>
          <dd>{output.seed}</dd>
        </div>
        <div>
          <dt>Iterations requested</dt>
          <dd>{output.iterations.toLocaleString("en-US")}</dd>
        </div>
        <div>
          <dt>Iterations completed in this scenario</dt>
          <dd>{scenario.iterations_completed.toLocaleString("en-US")}</dd>
        </div>
        <div>
          <dt>Scenario runtime</dt>
          <dd>{formatSeconds(scenario.runtime_seconds)}</dd>
        </div>
        <div>
          <dt>Specification hash</dt>
          <dd className="mono">{output.spec_hash}</dd>
        </div>
      </dl>
      <h3>Validation checks</h3>
      <CheckList checks={scenario.validation_checks} />
      {scenario.single_iteration_rounds ? (
        <div>
          <h3>Single-iteration round trace</h3>
          <ul>
            {scenario.single_iteration_rounds.map((round) => (
              <li key={round.round_number}>
                Round {round.round_number}: continuing {round.continuing_ballots}, exhausted {round.exhausted_ballots}.{" "}
                {round.note}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

function Quality({ output, scenario }: { output: SimulationOutput; scenario: ScenarioResult }) {
  const failed = [...output.validation_checks, ...scenario.validation_checks].filter((check) => !check.passed);
  return (
    <section id="quality" className="card stack">
      <h2>Data quality</h2>
      {failed.length === 0 ? <p>Recorded validation checks passed.</p> : <CheckList checks={failed} />}
      <h3>Model limitations</h3>
      <ul>
        {output.limitations.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
      <p>{output.disclaimer}</p>
    </section>
  );
}

function CheckList({ checks }: { checks: { name: string; passed: boolean; detail: string }[] }) {
  if (checks.length === 0) return <p>No checks were recorded.</p>;
  return (
    <ul className="check-list">
      {checks.map((check) => (
        <li key={`${check.name}-${check.detail}`}>
          <strong>{check.passed ? "Passed" : "Failed"}:</strong> {check.name}. {check.detail}
        </li>
      ))}
    </ul>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function nameOf(scenario: ScenarioResult, id: string): string {
  return scenario.candidates.find((candidate) => candidate.id === id)?.name || id;
}

function histogramBins(histogram: ScenarioResult["vote_histograms"][string] | undefined): { name: string; value: number }[] {
  if (!histogram) return [];
  return histogram.counts.map((count, index) => {
    const low = histogram.edges[index];
    const high = histogram.edges[index + 1];
    const name = high == null ? String(low) : `${Math.round(low)}–${Math.round(high)}`;
    return { name, value: count };
  });
}
