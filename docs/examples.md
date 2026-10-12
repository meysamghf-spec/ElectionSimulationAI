# Examples

Load these from the prompt page. The API also returns them at `GET /api/v1/examples`.

## Four candidates and three turnout scenarios

Simulate an election with four candidates, 2 million eligible voters, five regions, regional turnout differences, candidate preferences, 2% invalid ballots, and 10,000 Monte Carlo iterations. Compare three turnout scenarios.

The deterministic parser records which values were extracted and which were inferred, including equal preferences and an illustrative turnout gradient when the prompt does not give per-region rates.

## Harbor City two-round election

Run a two-round election titled "Harbor City Council". Candidates Alice, Bob, and Carol. 10000 eligible voters. One region. Turnout of 60%. Alice 45%, Bob 35%, Carol 20%. 1% blank ballots and 1% invalid ballots. 500 iterations. Seed 7.

## Ranked-choice blocs

Ranked-choice election. Candidates Alice, Bob, and Carol. 1000 eligible voters. Turnout of 100%. 0% invalid ballots. Rankings: 40% Alice > Bob > Carol; 35% Bob > Carol > Alice; 25% Carol > Alice > Bob. 200 iterations. Seed 1.

## D'Hondt

D'Hondt allocation with 5 seats. Candidates Red, Blue, and Green. 100000 eligible voters. Turnout of 50%. Red 50%, Blue 30%, Green 20%. 100 iterations.

## Small plurality check

Plurality election titled "Hand check". Candidates Alpha and Beta. 100 eligible voters. One region. Turnout of 100%. Alpha 100%, Beta 0%. 0% invalid ballots. 20 iterations. Seed 1.

## Regional CSV

Download `GET /api/v1/examples/datasets/regions.csv`.

Required columns: `region_id`, `name`, `eligible_voters`, `turnout_probability`, `blank_rate`, `invalid_rate`, plus one `pref_<candidate_id>` column per candidate. Preference probabilities on a row must sum to 1. Unknown columns are rejected. The importer does not evaluate spreadsheet formulas.

A full specification can be pasted as JSON on the import page or posted to `POST /api/v1/imports/json`.
