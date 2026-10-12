"""Hand-checkable election rules."""

from __future__ import annotations

import numpy as np
from app.engine.allocate import dhondt, instant_runoff, plurality, two_round
from app.engine.population import largest_remainder


def test_plurality_tie_is_reported() -> None:
    result = plurality({"a": 5, "b": 5, "c": 1})
    assert result.winner_ids == ["a", "b"]
    assert result.ranking == ["a", "b", "c"]


def test_plurality_zero_ballots_has_no_winner() -> None:
    result = plurality({"a": 0, "b": 0})
    assert result.winner_ids == []


def test_dhondt_classic_allocation() -> None:
    result = dhondt({"a": 100, "b": 80, "c": 30}, 5)
    assert result.seats == {"a": 3, "b": 2, "c": 0}
    assert result.unallocated_seats == 0


def test_dhondt_tie_uses_smaller_id() -> None:
    result = dhondt({"b": 10, "a": 10}, 1)
    assert result.seats == {"a": 1, "b": 0}


def test_dhondt_zero_votes_leaves_seats_unallocated() -> None:
    result = dhondt({"a": 0, "b": 0}, 3)
    assert result.seats == {"a": 0, "b": 0}
    assert result.unallocated_seats == 3
    assert result.seat_explanation


def test_instant_runoff_transfer() -> None:
    blocs = {("a", "b", "c"): 4, ("b", "c", "a"): 3, ("c", "b", "a"): 3}
    result = instant_runoff(blocs, ["a", "b", "c"])
    assert result.winner_ids == ["b"]
    assert result.rounds[0]["eliminated"] == ["c"]
    assert result.rounds[1]["votes"]["b"] == 6


def test_instant_runoff_exact_tie() -> None:
    result = instant_runoff({("a", "b"): 5, ("b", "a"): 5}, ["a", "b"])
    assert result.winner_ids == ["a", "b"]


def test_two_round_majority_ends_early() -> None:
    rng = np.random.default_rng(1)
    result = two_round({"a": 51, "b": 49}, None, 0.5, rng, ["a", "b"])
    assert result.winner_ids == ["a"]
    assert len(result.rounds) == 1


def test_two_round_retention_abstention() -> None:
    rng = np.random.default_rng(1)
    result = two_round({"a": 40, "b": 35, "c": 25}, None, 0.5, rng, ["a", "b", "c"])
    assert result.winner_ids == ["a"]
    assert result.rounds[1]["votes"] == {"a": 40, "b": 35}
    assert result.exhausted == 25


def test_two_round_configured_transfer() -> None:
    rng = np.random.default_rng(1)
    transfers = {"a": {"a": 1.0}, "b": {"b": 1.0}, "c": {"a": 1.0}}
    result = two_round({"a": 40, "b": 35, "c": 25}, transfers, 0.5, rng, ["a", "b", "c"])
    assert result.rounds[1]["votes"]["a"] == 65
    assert result.winner_ids == ["a"]


def test_largest_remainder_splits_ties_toward_earlier_index() -> None:
    assert largest_remainder(10, [1 / 3, 1 / 3, 1 / 3]) == [4, 3, 3]
    assert largest_remainder(10, [0.6, 0.4]) == [6, 4]
