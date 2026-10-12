export type AssumptionSource = "extracted" | "inferred" | "user" | "default_policy" | "model_proposed";
export type VotingMethod = "plurality" | "two_round" | "ranked_choice" | "dhondt";
export type InterpreterMode = "deterministic" | "deterministic_fallback" | "llm" | "json";
export type SimulationStatus = "draft" | "queued" | "running" | "completed" | "failed" | "cancelled";

export interface Assumption {
  field: string;
  source: AssumptionSource;
  note: string;
}

export interface CandidateSpec {
  id: string;
  name: string;
}

export interface RankingBloc {
  ranking: string[];
  weight: number;
}

export interface SegmentSpec {
  id: string;
  name: string;
  share: number;
  turnout_probability: number;
  preferences: Record<string, number>;
  blank_rate: number;
  invalid_rate: number;
  ranking_blocs?: RankingBloc[] | null;
}

export interface RegionSpec {
  id: string;
  name: string;
  eligible_voters: number;
  turnout_probability: number;
  preferences: Record<string, number>;
  blank_rate: number;
  invalid_rate: number;
  ranking_blocs?: RankingBloc[] | null;
  segments?: SegmentSpec[] | null;
}

export interface ScenarioSpec {
  id: string;
  name: string;
  description: string;
  turnout_multiplier?: number | null;
  turnout_by_region?: Record<string, number> | null;
  preference_overrides?: Record<string, Record<string, number>> | null;
  invalid_rate_override?: number | null;
  blank_rate_override?: number | null;
  voting_method_override?: VotingMethod | null;
  seats_override?: number | null;
  runoff_threshold_override?: number | null;
  turnout_shock_sd_override?: number | null;
}

export interface ReportingOptions {
  include_regional: boolean;
  include_histograms: boolean;
  histogram_bins: number;
}

export interface ElectionSpecification {
  title: string;
  description: string;
  candidates: CandidateSpec[];
  regions: RegionSpec[];
  voting_method: VotingMethod;
  seats?: number | null;
  runoff_threshold: number;
  runoff_transfers?: Record<string, Record<string, number>> | null;
  iterations: number;
  seed: number;
  scenarios: ScenarioSpec[];
  assumptions: Assumption[];
  empirical_data: boolean;
  turnout_shock_sd: number;
  reporting: ReportingOptions;
}

export interface ValidationIssue {
  field: string;
  message: string;
  severity: "error" | "warning";
}

export interface ValidationReport {
  valid: boolean;
  errors: ValidationIssue[];
  warnings: ValidationIssue[];
}

export interface InterpretationResult {
  specification: ElectionSpecification;
  interpreter_mode: InterpreterMode;
  llm_configured: boolean;
  notices: string[];
}

export interface ExamplePrompt {
  id: string;
  title: string;
  description: string;
  prompt: string;
}

export interface SimulationSummary {
  id: string;
  project_id: string | null;
  title: string;
  status: SimulationStatus;
  seed: number;
  iterations: number;
  algorithm_version: string;
  voting_method: string;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  finished_at: string | null;
  progress: number;
  error_message: string | null;
  hypothetical: true;
}

export interface AuditEvent {
  id: string;
  action: string;
  detail: string;
  created_at: string;
}

export interface SimulationDetail extends SimulationSummary {
  description: string;
  specification: ElectionSpecification;
  validation: ValidationReport | null;
  results: SimulationOutput | null;
  audit_events: AuditEvent[];
}

export interface IntervalEstimate {
  low: number;
  high: number;
  level: number;
  method: string;
  meaning: string;
}

export interface CandidateSummary {
  id: string;
  name: string;
  mean_votes: number;
  median_votes: number;
  std_votes: number;
  vote_quantiles: Record<string, number>;
  vote_mean_interval: IntervalEstimate;
  mean_share: number | null;
  median_share: number | null;
  std_share: number | null;
  share_quantiles: Record<string, number> | null;
  sole_win_frequency: number;
  tie_frequency: number;
  sole_win_frequency_se: number;
  sole_win_frequency_interval: IntervalEstimate;
  mean_seats?: number | null;
  seat_frequencies?: Record<string, number> | null;
}

export interface RegionalSummary {
  id: string;
  name: string;
  eligible_voters: number;
  expected_ballots: number | null;
  expected_ballots_label: string;
  analytical_turnout_variance: number | null;
  mean_ballots: number;
  std_ballots: number;
  mean_turnout_rate: number | null;
  mean_valid: number;
  mean_blank: number;
  mean_invalid: number;
  mean_votes: Record<string, number>;
  std_votes: Record<string, number>;
  mean_shares: Record<string, number | null>;
}

export interface Histogram {
  edges: number[];
  counts: number[];
  note: string;
}

export interface RoundTrace {
  round_number: number;
  votes: Record<string, number>;
  continuing_ballots: number;
  exhausted_ballots: number;
  eliminated: string[];
  note: string;
}

export interface CheckResult {
  name: string;
  passed: boolean;
  detail: string;
}

export interface ScenarioResult {
  scenario_id: string;
  scenario_name: string;
  parameter_notes: string[];
  voting_method: string;
  seats_requested: number | null;
  iterations_completed: number;
  runtime_seconds: number;
  eligible_voters: number;
  expected_ballots: number | null;
  expected_valid: number | null;
  expected_votes: Record<string, number> | null;
  expectation_note: string;
  mean_ballots: number;
  median_ballots: number;
  std_ballots: number;
  mean_turnout_rate: number | null;
  mean_valid: number;
  mean_blank: number;
  mean_invalid: number;
  candidates: CandidateSummary[];
  ranking_by_mean_votes: string[];
  regional: RegionalSummary[];
  regional_note: string;
  vote_histograms: Record<string, Histogram>;
  margin_histogram: Histogram | null;
  mean_exhausted_ballots: number;
  runoff_iterations: number;
  mean_second_round_votes: Record<string, number> | null;
  single_iteration_rounds: RoundTrace[] | null;
  validation_checks: CheckResult[];
  hypothetical: true;
}

export interface CandidateDelta {
  id: string;
  name: string;
  left_mean_votes: number;
  right_mean_votes: number;
  vote_difference: number;
  left_mean_share: number | null;
  right_mean_share: number | null;
  percentage_point_difference: number | null;
  relative_share_change: number | null;
  left_sole_win_frequency: number;
  right_sole_win_frequency: number;
  sole_win_frequency_difference: number;
  left_mean_seats: number | null;
  right_mean_seats: number | null;
}

export interface ComparisonResult {
  left_scenario_id: string;
  left_scenario_name: string;
  right_scenario_id: string;
  right_scenario_name: string;
  explanation: string;
  eligible_voters_left: number;
  eligible_voters_right: number;
  mean_ballots_difference: number;
  turnout_percentage_point_difference: number | null;
  mean_valid_difference: number;
  mean_blank_difference: number;
  mean_invalid_difference: number;
  candidates: CandidateDelta[];
}

export interface SimulationOutput {
  algorithm_version: string;
  hypothetical: true;
  disclaimer: string;
  spec_hash: string;
  seed: number;
  iterations: number;
  scenarios: ScenarioResult[];
  reference_comparisons: ComparisonResult[];
  limitations: string[];
  validation_checks: CheckResult[];
}

export interface SensitivityVariation {
  parameter: string;
  change: string;
  applied: boolean;
  reason: string;
  held_constant: string[];
  max_absolute_share_percentage_points: number | null;
  leading_candidate_id: string | null;
  leading_share_percentage_point_change: number | null;
  mean_ballots: number | null;
  mean_ballots_difference: number | null;
  candidate_share_percentage_points: Record<string, number | null>;
}

export interface SensitivityReport {
  hypothetical: true;
  disclaimer: string;
  iteration_cap: number;
  seed: number;
  design: string;
  varied_parameters: string[];
  held_constant: string[];
  variations: SensitivityVariation[];
  largest_effect_parameter: string | null;
  largest_effect_change: string | null;
  largest_effect_percentage_points: number | null;
  note: string;
}

export interface ExpectationPreview {
  ballots: number | null;
  valid: number | null;
  votes: Record<string, number> | null;
  note: string;
}

export interface PreviewResponse {
  hypothetical: true;
  disclaimer: string;
  validation: ValidationReport;
  spec_hash: string;
  expectations: ExpectationPreview | null;
  note: string;
}

export interface MetaResponse {
  algorithm_version: string;
  environment: string;
  persistence: string;
  llm_configured: boolean;
  interpreter_default: string;
  api_token_required: boolean;
  max_iterations: number;
  max_candidates: number;
  max_regions: number;
  max_upload_bytes: number;
  sensitivity_iteration_cap: number;
  authentication: string;
  disclaimer: string;
  worker: string;
}

export interface ApiErrorBody {
  code: string;
  message: string;
  details: { field: string; message: string }[];
}
