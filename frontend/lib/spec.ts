import type { ElectionSpecification, RegionSpec } from "./types";

export function slugify(name: string, used: string[]): string {
  let base = name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
  if (!/^[a-z]/.test(base)) base = `id_${base}`.replace(/_+$/g, "");
  base = (base || "id").slice(0, 60);
  let id = base;
  let suffix = 2;
  while (used.includes(id)) {
    id = `${base.slice(0, 56)}_${suffix}`;
    suffix += 1;
  }
  return id;
}

export function preferenceSum(preferences: Record<string, number>): number {
  return Object.values(preferences).reduce((total, value) => total + (Number.isFinite(value) ? value : 0), 0);
}

export function touchUser(spec: ElectionSpecification): ElectionSpecification {
  if (spec.assumptions.some((item) => item.field === "configuration" && item.source === "user")) {
    return spec;
  }
  return {
    ...spec,
    assumptions: [
      ...spec.assumptions,
      {
        field: "configuration",
        source: "user",
        note: "Edited in the structured configuration editor.",
      },
    ],
  };
}

export function placeholderSpec(): ElectionSpecification {
  return {
    title: "Untitled election",
    description: "",
    candidates: [
      { id: "candidate_a", name: "Candidate A" },
      { id: "candidate_b", name: "Candidate B" },
    ],
    regions: [
      {
        id: "region_1",
        name: "Region 1",
        eligible_voters: 0,
        turnout_probability: 0,
        preferences: { candidate_a: 0.5, candidate_b: 0.5 },
        blank_rate: 0,
        invalid_rate: 0,
      },
    ],
    voting_method: "plurality",
    seats: null,
    runoff_threshold: 0.5,
    runoff_transfers: null,
    iterations: 500,
    seed: 20241105,
    scenarios: [],
    assumptions: [
      {
        field: "eligible_voters",
        source: "inferred",
        note: "No population was supplied. Eligible voters are 0 until you enter a count. This is not an empirical observation.",
      },
      {
        field: "preferences",
        source: "inferred",
        note: "Placeholder preferences are equal. Replace them before interpreting the simulation.",
      },
      {
        field: "iterations",
        source: "default_policy",
        note: "Iteration count 500 is a placeholder default, not a value extracted from a prompt.",
      },
      {
        field: "seed",
        source: "default_policy",
        note: "Seed 20241105 is the application default when a prompt does not name one.",
      },
    ],
    empirical_data: false,
    turnout_shock_sd: 0,
    reporting: { include_regional: true, include_histograms: true, histogram_bins: 20 },
  };
}

export function withCandidatePreferences(region: RegionSpec, candidateIds: string[]): RegionSpec {
  const preferences: Record<string, number> = {};
  for (const id of candidateIds) {
    preferences[id] = region.preferences[id] ?? 0;
  }
  return { ...region, preferences };
}
