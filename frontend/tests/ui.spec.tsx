import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { SpecEditor } from "@/components/SpecEditor";
import { Shell } from "@/components/Shell";
import { ResultsView } from "@/components/ResultsView";
import { ApiError } from "@/lib/api";
import { ErrorText } from "@/components/ErrorText";
import type { ElectionSpecification, SimulationOutput } from "@/lib/types";
import { placeholderSpec } from "@/lib/spec";

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({ push: () => undefined }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children?: ReactNode }) => children ?? null,
  BarChart: ({ children }: { children?: ReactNode }) => children ?? null,
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  CartesianGrid: () => null,
}));

const spec: ElectionSpecification = {
  ...placeholderSpec(),
  title: "Editable title",
  regions: [
    {
      ...placeholderSpec().regions[0],
      eligible_voters: 100,
      turnout_probability: 1,
      preferences: { candidate_a: 1, candidate_b: 0 },
    },
  ],
};

describe("configuration editor", () => {
  it("records a title edit without calling the network", () => {
    const onChange = vi.fn();
    render(<SpecEditor spec={spec} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "City vote" } });
    const last = onChange.mock.calls.at(-1)?.[0] as ElectionSpecification;
    expect(last.title).toBe("City vote");
    expect(last.assumptions.some((item) => item.source === "user")).toBe(true);
  });

  it("shows an API validation message", () => {
    render(
      <ErrorText
        error={new ApiError(400, { code: "validation_error", message: "Rejected.", details: [{ field: "regions", message: "sum is 1.2" }] }, "no")}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("sum is 1.2");
  });
});

describe("navigation", () => {
  it("exposes the primary workflow links", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            authenticated: false,
            email: null,
            auth_mode: "development",
            registration_open: false,
            csrf_token: null,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    render(<Shell><p>Home</p></Shell>);
    expect(screen.getByRole("link", { name: "New simulation" })).toHaveAttribute("href", "/new");
    expect(screen.getByRole("link", { name: "History" })).toHaveAttribute("href", "/history");
    expect(screen.getByRole("note")).toHaveTextContent("hypothetical");
  });
});

describe("results", () => {
  it("renders the vote totals it was given", () => {
    render(
      <ResultsView
        output={output()}
        simulationId="sim-1"
        sensitivity={null}
        sensitivityLoading={false}
        onSensitivity={() => undefined}
        sensitivityError={null}
      />,
    );
    expect(screen.getByTestId("mean-votes-chart")).toHaveAttribute("data-values", "12345,10");
    expect(screen.getAllByText("Alpha").length).toBeGreaterThan(0);
    expect(screen.getByText(/Monte Carlo uncertainty/)).toBeInTheDocument();
  });
});

function output(): SimulationOutput {
  return {
    algorithm_version: "1.0.0",
    hypothetical: true,
    disclaimer: "Hypothetical.",
    spec_hash: "abc",
    seed: 1,
    iterations: 4,
    reference_comparisons: [],
    limitations: ["Independent draws are a model choice."],
    validation_checks: [{ name: "counts", passed: true, detail: "ok" }],
    scenarios: [
      {
        scenario_id: "baseline",
        scenario_name: "Baseline",
        parameter_notes: [],
        voting_method: "plurality",
        seats_requested: null,
        iterations_completed: 4,
        runtime_seconds: 0.01,
        eligible_voters: 100,
        expected_ballots: 100,
        expected_valid: 100,
        expected_votes: { a: 100, b: 0 },
        expectation_note: "Expected ballots are analytical.",
        mean_ballots: 100,
        median_ballots: 100,
        std_ballots: 0,
        mean_turnout_rate: 1,
        mean_valid: 100,
        mean_blank: 0,
        mean_invalid: 0,
        ranking_by_mean_votes: ["a", "b"],
        regional: [],
        regional_note: "Regional detail omitted.",
        vote_histograms: {},
        margin_histogram: null,
        mean_exhausted_ballots: 0,
        runoff_iterations: 0,
        mean_second_round_votes: null,
        single_iteration_rounds: null,
        validation_checks: [{ name: "counts", passed: true, detail: "ok" }],
        hypothetical: true,
        candidates: [
          candidate("a", "Alpha", 12345),
          candidate("b", "Beta", 10),
        ],
      },
    ],
  };
}

function candidate(id: string, name: string, votes: number) {
  return {
    id,
    name,
    mean_votes: votes,
    median_votes: votes,
    std_votes: 0,
    vote_quantiles: { p05: votes, p25: votes, p50: votes, p75: votes, p95: votes },
    vote_mean_interval: { low: votes, high: votes, level: 0.95, method: "normal", meaning: "Monte Carlo mean interval" },
    mean_share: id === "a" ? 0.99 : 0.01,
    median_share: id === "a" ? 0.99 : 0.01,
    std_share: 0,
    share_quantiles: { p50: 0.5 },
    sole_win_frequency: id === "a" ? 1 : 0,
    tie_frequency: 0,
    sole_win_frequency_se: 0,
    sole_win_frequency_interval: { low: 0, high: 1, level: 0.95, method: "wilson", meaning: "simulation frequency interval" },
    mean_seats: null,
    seat_frequencies: null,
  };
}
