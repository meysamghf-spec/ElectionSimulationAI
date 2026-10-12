import Link from "next/link";

export default function HomePage() {
  return (
    <div className="stack">
      <header className="page-head">
        <p className="eyebrow">Simulation and statistical analysis</p>
        <h1>Describe an election. Inspect the assumptions. Run the math.</h1>
        <p>
          ElectionSimulationAI turns a written description into a validated specification, then runs a reproducible
          Monte Carlo model. The numbers come from the simulation engine, not from a language model.
        </p>
      </header>
      <ol className="steps">
        <li>Write a prompt or start from an example.</li>
        <li>Review extracted facts and inferred assumptions.</li>
        <li>Edit the structured configuration.</li>
        <li>Run the simulation and read the dashboard.</li>
        <li>Compare scenarios and export the computed results.</li>
      </ol>
      <div className="button-row">
        <Link className="button" href="/new">
          Start a simulation
        </Link>
        <Link className="button secondary" href="/help">
          Read the methodology
        </Link>
      </div>
      <section className="card stack">
        <h2>What this platform does</h2>
        <ul>
          <li>Plurality, two-round, ranked-choice, and D&apos;Hondt seat allocation.</li>
          <li>Regional turnout, preferences, blank ballots, and invalid ballots.</li>
          <li>Monte Carlo distributions, scenario differences, and sensitivity sweeps.</li>
          <li>CSV and JSON import, plus CSV, JSON, and PDF export of computed runs.</li>
        </ul>
        <p>
          It does not retrieve official returns or polls. A saved result stays labeled hypothetical even when you
          imported your own aggregate inputs.
        </p>
      </section>
    </div>
  );
}
