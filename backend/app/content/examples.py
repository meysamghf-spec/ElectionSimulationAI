"""Example prompts and the documented region CSV."""

from __future__ import annotations

EXAMPLE_PROMPTS: list[dict[str, str]] = [
    {
        "id": "four-candidate-regional",
        "title": "Four candidates and three turnout scenarios",
        "description": "The canonical workflow: population, regions, invalid ballots, and a turnout comparison.",
        "prompt": (
            "Simulate an election with four candidates, 2 million eligible voters, five regions, "
            "regional turnout differences, candidate preferences, 2% invalid ballots, and 10,000 "
            "Monte Carlo iterations. Compare three turnout scenarios."
        ),
    },
    {
        "id": "harbor-runoff",
        "title": "Two-round city election",
        "description": "Named candidates, an explicit turnout rate, and blank and invalid ballots.",
        "prompt": (
            "Run a two-round election titled \"Harbor City Council\". Candidates Alice, Bob, and Carol. "
            "10000 eligible voters. One region. Turnout of 60%. Alice 45%, Bob 35%, Carol 20%. "
            "1% blank ballots and 1% invalid ballots. 500 iterations. Seed 7."
        ),
    },
    {
        "id": "ranked-choice-blocs",
        "title": "Ranked-choice blocs",
        "description": "Full rankings with weights that sum to 100%.",
        "prompt": (
            "Ranked-choice election. Candidates Alice, Bob, and Carol. 1000 eligible voters. "
            "Turnout of 100%. 0% invalid ballots. Rankings: 40% Alice > Bob > Carol; "
            "35% Bob > Carol > Alice; 25% Carol > Alice > Bob. 200 iterations. Seed 1."
        ),
    },
    {
        "id": "dhondt-seats",
        "title": "D'Hondt seat allocation",
        "description": "Proportional allocation with an explicit seat total.",
        "prompt": (
            "D'Hondt allocation with 5 seats. Candidates Red, Blue, and Green. "
            "100000 eligible voters. Turnout of 50%. Red 50%, Blue 30%, Green 20%. 100 iterations."
        ),
    },
    {
        "id": "small-hand-check",
        "title": "Small deterministic plurality",
        "description": "One candidate receives every valid ballot, which makes the result easy to check.",
        "prompt": (
            "Plurality election titled \"Hand check\". Candidates Alpha and Beta. "
            "100 eligible voters. One region. Turnout of 100%. Alpha 100%, Beta 0%. "
            "0% invalid ballots. 20 iterations. Seed 1."
        ),
    },
]

REGION_CSV = (
    "region_id,name,eligible_voters,turnout_probability,blank_rate,invalid_rate,"
    "pref_alice,pref_bob,pref_carol\n"
    "north,North,10000,0.62,0.01,0.02,0.45,0.35,0.20\n"
    "south,South,15000,0.58,0.01,0.02,0.30,0.40,0.30\n"
    "central,Central,12000,0.66,0.01,0.02,0.34,0.33,0.33\n"
)

IMPORT_SCHEMAS = {
    "regions_csv": {
        "description": (
            "Aggregate regional inputs. One row is a region, not a voter. "
            "Preference columns are probabilities conditional on a valid ballot and must sum to 1."
        ),
        "required_columns": [
            "region_id",
            "name",
            "eligible_voters",
            "turnout_probability",
            "blank_rate",
            "invalid_rate",
        ],
        "preference_columns": "pref_<candidate_id>",
        "candidate_id_pattern": "lowercase letter followed by lowercase letters, digits, underscores, or hyphens",
        "limits": {"max_rows": 5000, "max_bytes": 2000000},
        "example": "GET /api/v1/examples/datasets/regions.csv",
    },
    "specification_json": {
        "description": "A full ElectionSpecification JSON object. Extra fields are rejected.",
        "content_type": "application/json",
    },
}
