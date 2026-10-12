# Simulation methodology

ElectionSimulationAI evaluates a user-supplied probabilistic model. It does not retrieve official returns, poll averages, or forecasts. Every result page is labeled as a hypothetical simulation.

## Population and turnout

Eligible voters and ballots cast are different quantities.

For a population unit with `N` eligible voters and turnout probability `t`:

- Expected ballots: `E[V] = N × t`. This expected value may be fractional and is never labeled as an observed integer count.
- Simulated ballots: `V ~ Binomial(N, t)`.

A region without segments is one unit. A region with demographic segments is split once, before the first iteration, by the largest-remainder (Hamilton) method so the integer segment sizes sum to the region's eligible voters. Each segment then has its own turnout, ballot-validity rates, and preferences. Segment sizes are fixed, not redrawn.

When `turnout_shock_sd` is 0, regional binomial draws are independent. When it is positive, one shared `Normal(0, sd)` shock is added to every unit's turnout probability in that iteration and the result is clipped to `[0, 1]`. Clipping means the expected turnout need not equal the configured probability, so closed-form expectations are withheld.

## Ballot validity

Blank and invalid rates are conditional on a ballot being cast. They are not shares of the eligible population.

Given `V` ballots:

`(valid, blank, invalid) ~ Multinomial(V, [1 - b - i, b, i])`

with `b + i ≤ 1`. Valid, blank, and invalid counts sum to ballots cast. Candidate votes are allocated only from valid ballots and sum to the valid count. The same ballot is not counted twice.

## Candidate preferences

For plurality, two-round, and D'Hondt elections, valid ballots in a unit are

`votes ~ Multinomial(valid, preferences)`.

Preferences must be nonnegative and sum to 1. The server rejects other totals instead of renormalizing them. A residual within `1e-6` of 1 may be divided by the sum so the multinomial generator receives a vector that sums to 1. That adjustment is floating-point hygiene after validation, not a repair of an invalid distribution.

Ranked-choice elections draw ranking blocs with a multinomial when blocs are configured. Otherwise each ballot is a singleton ranking of its first preference and is exhausted when that candidate is eliminated. The result records that limitation.

Voters inside a unit are exchangeable conditional on that unit's parameters. Segments and regions are how the model represents people who do not share those parameters.

## Election methods

### Plurality

The candidate with the most valid votes wins. A tie is reported. No tie is broken. This implementation does not allocate multiple seats.

### Two-round

A first-round win requires a unique leader whose valid-vote share is strictly greater than `runoff_threshold` (default 0.5). Otherwise the top two candidates advance. Ties for advancement break toward the lexicographically smaller candidate id.

If `runoff_transfers` is omitted, finalists keep their first-round votes and every other ballot abstains. That retention-abstention rule does not invent second preferences. If transfers are present, each first-choice group is reallocated with a multinomial over the finalists; probability mass not assigned to a finalist abstains.

### Ranked choice

Instant-runoff:

1. Count the highest-ranked candidate who has not been eliminated.
2. A winner needs a strict majority of continuing ballots, checked with integer arithmetic (`votes × 2 > continuing`).
3. Otherwise eliminate the candidate with the fewest continuing votes. Elimination ties remove the lexicographically greatest id.
4. If every remaining candidate has the same total, report a tie.
5. Ballots with no continuing preference are exhausted and leave the denominator.

### D'Hondt

Seats are required. For the next seat, candidate A beats B when `votes[A] × (seats[B] + 1) > votes[B] × (seats[A] + 1)`. Equal quotients go to the lexicographically smaller id. The comparison is exact integer arithmetic. If every candidate has zero votes, every seat stays unallocated and the result says why. Plurality, two-round, and ranked-choice requests that set `seats` above 1 are rejected rather than approximated.

## Monte Carlo

Each scenario starts a PCG64 generator at the specification seed. The draw order is fixed: optional shared shock, then regions and segments in specification order (binomial, then ballot types, then preferences or blocs), then two-round transfers in candidate order when a runoff uses a transfer matrix. Counts of zero do not consume a multinomial draw.

The same specification, algorithm version, and seed reproduce the same numerical summaries. Runtime is not part of the numerical result.

Reported for each scenario:

- vote totals, shares, ranks, turnout, and valid, blank, and invalid ballots
- mean, median, sample standard deviation, and empirical quantiles
- sole-win frequency and its Monte Carlo standard error
- a 95% Wilson interval for that frequency
- a normal approximation interval for the mean vote count when at least two iterations exist
- histograms and the distribution of the first-to-second margin

These intervals estimate Monte Carlo error under the model. They are not confidence intervals for a real election. A small iteration count makes the normal approximation rough; the median and quantiles remain empirical summaries of the draws.

## Scenario comparison and sensitivity

Scenario comparison subtracts stored Monte Carlo means. Percentage-point difference is `(right share - left share) × 100`. Relative share change is `(right - left) / left` when the left share is not zero. The comparison does not re-draw the election.

Sensitivity runs a separate, smaller Monte Carlo (capped by `SENSITIVITY_ITERATION_CAP`) for a turnout grid, invalid-rate replacements, and a preference shift from the first candidate to the second. Unlisted parameters stay at the baseline. The largest effect is the largest absolute share change inside that sweep, not a real-world causal effect. Turnout and invalid-rate changes often move ballot counts without moving conditional vote shares.

## What this is not

A correct implementation of these rules is not a prediction. Wrong preferences, populations, turnout, or an independence assumption that reality does not satisfy will produce confident-looking and still misleading numbers. Inferred values are placeholders. User-supplied files are inputs to the model, not official results.
