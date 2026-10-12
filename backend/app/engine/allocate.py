"""Election methods with explicit, testable counting rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from app.engine.population import as_simplex
from app.errors import InvariantError


@dataclass
class MethodResult:
    winner_ids: list[str]
    ranking: list[str]
    seats: dict[str, int] | None
    unallocated_seats: int
    seat_explanation: str
    rounds: list[dict[str, Any]]
    exhausted: int
    notes: list[str] = field(default_factory=list)


def plurality(votes: dict[str, int]) -> MethodResult:
    """Single-winner plurality. Ties are reported, not broken."""

    ranking = sorted(votes, key=lambda candidate: (-votes[candidate], candidate))
    total = sum(votes.values())
    rounds = [
        {
            "round_number": 1,
            "votes": dict(votes),
            "continuing_ballots": total,
            "exhausted_ballots": 0,
            "eliminated": [],
            "note": "Plurality count of valid ballots.",
        }
    ]
    if total == 0:
        return MethodResult(
            winner_ids=[],
            ranking=ranking,
            seats=None,
            unallocated_seats=0,
            seat_explanation="Plurality does not allocate seats. There are no valid ballots.",
            rounds=rounds,
            exhausted=0,
            notes=["No valid ballots, so there is no plurality winner."],
        )
    top = votes[ranking[0]]
    leaders = [candidate for candidate in ranking if votes[candidate] == top]
    note = (
        "Sole plurality winner."
        if len(leaders) == 1
        else "Two or more candidates tied for the most valid votes. The tie is reported."
    )
    return MethodResult(
        winner_ids=leaders,
        ranking=ranking,
        seats=None,
        unallocated_seats=0,
        seat_explanation="Plurality is implemented as a single-winner method and does not allocate seats.",
        rounds=rounds,
        exhausted=0,
        notes=[note],
    )


def _transfer_row(
    votes_for_candidate: int,
    destination: dict[str, float],
    finalists: list[str],
    rng: np.random.Generator,
) -> tuple[dict[str, int], int]:
    probabilities = [destination.get(finalist, 0.0) for finalist in finalists]
    assigned = math_sum(probabilities)
    if assigned > 1.0 + 1e-6:
        raise InvariantError("A runoff transfer row sums to more than 1.")
    abstain = 1.0 - assigned
    weights = as_simplex(probabilities + [abstain])
    drawn = rng.multinomial(votes_for_candidate, weights)
    allocated = {
        finalist: int(count) for finalist, count in zip(finalists, drawn[:-1], strict=True)
    }
    return allocated, int(drawn[-1])


def math_sum(values: list[float]) -> float:
    total = 0.0
    for value in values:
        total += value
    return total


def two_round(
    votes: dict[str, int],
    transfers: dict[str, dict[str, float]] | None,
    threshold: float,
    rng: np.random.Generator,
    candidate_order: list[str],
) -> MethodResult:
    """Two-round runoff.

    A first-round win requires a valid-vote share strictly greater than
    ``threshold`` and a unique leader. Otherwise the top two candidates by
    votes, with lexicographic id as the tie break, advance.

    When ``transfers`` is omitted, finalists keep their first-round votes and
    every other ballot abstains. This retention-abstention rule is exact; it
    does not invent second preferences.
    """

    ranking = sorted(votes, key=lambda candidate: (-votes[candidate], candidate))
    total = sum(votes.values())
    first_round = {
        "round_number": 1,
        "votes": dict(votes),
        "continuing_ballots": total,
        "exhausted_ballots": 0,
        "eliminated": [],
        "note": "First-round plurality count.",
    }
    if total == 0:
        return MethodResult(
            winner_ids=[],
            ranking=ranking,
            seats=None,
            unallocated_seats=0,
            seat_explanation="Two-round plurality does not allocate seats.",
            rounds=[first_round],
            exhausted=0,
            notes=["No valid ballots, so there is no winner."],
        )
    top = votes[ranking[0]]
    leaders = [candidate for candidate in ranking if votes[candidate] == top]
    if (top / total) > threshold and len(leaders) == 1:
        return MethodResult(
            winner_ids=leaders,
            ranking=ranking,
            seats=None,
            unallocated_seats=0,
            seat_explanation="Two-round plurality does not allocate seats.",
            rounds=[first_round],
            exhausted=0,
            notes=["First-round share strictly exceeded the configured threshold."],
        )
    if len(ranking) < 2:
        return MethodResult(
            winner_ids=[],
            ranking=ranking,
            seats=None,
            unallocated_seats=0,
            seat_explanation="Two-round plurality does not allocate seats.",
            rounds=[first_round],
            exhausted=0,
            notes=[
                "The leading share did not strictly exceed the threshold, and a runoff "
                "cannot be formed with fewer than two candidates."
            ],
        )
    finalists = ranking[:2]
    eliminated = [candidate for candidate in candidate_order if candidate not in finalists]
    second_votes = {finalist: 0 for finalist in finalists}
    abstain = 0
    notes = [
        "No candidate had a unique first-round share strictly above the threshold.",
        f"Finalists: {', '.join(finalists)}. Advancement ties break toward the smaller candidate id.",
    ]
    if transfers is None:
        notes.append(
            "Retention-abstention rule: finalists keep first-round votes; other ballots abstain. "
            "No second-preference distribution was configured."
        )
        for candidate, count in votes.items():
            if candidate in second_votes:
                second_votes[candidate] += count
            else:
                abstain += count
    else:
        notes.append("Second-round choices were drawn from the configured transfer distributions.")
        for candidate in candidate_order:
            count = votes.get(candidate, 0)
            if count == 0:
                continue
            row = transfers[candidate]
            moved, abstained = _transfer_row(count, row, finalists, rng)
            for finalist, moved_count in moved.items():
                second_votes[finalist] += moved_count
            abstain += abstained
    second_total = sum(second_votes.values())
    second_round = {
        "round_number": 2,
        "votes": dict(second_votes),
        "continuing_ballots": second_total,
        "exhausted_ballots": abstain,
        "eliminated": eliminated,
        "note": "Runoff among the two finalists. Abstained ballots are exhausted.",
    }
    if second_total == 0:
        return MethodResult(
            winner_ids=[],
            ranking=sorted(second_votes, key=lambda candidate: (-second_votes[candidate], candidate)),
            seats=None,
            unallocated_seats=0,
            seat_explanation="Two-round plurality does not allocate seats.",
            rounds=[first_round, second_round],
            exhausted=abstain,
            notes=notes + ["Every runoff ballot abstained, so there is no second-round winner."],
        )
    second_ranking = sorted(second_votes, key=lambda candidate: (-second_votes[candidate], candidate))
    second_top = second_votes[second_ranking[0]]
    second_leaders = [
        candidate for candidate in second_ranking if second_votes[candidate] == second_top
    ]
    if len(second_leaders) == 1:
        notes.append("Unique second-round plurality winner.")
    else:
        notes.append("Second-round tie. Both finalists are reported; the tie is not broken.")
    full_ranking = second_ranking + [candidate for candidate in ranking if candidate not in second_ranking]
    return MethodResult(
        winner_ids=second_leaders,
        ranking=full_ranking,
        seats=None,
        unallocated_seats=0,
        seat_explanation="Two-round plurality does not allocate seats.",
        rounds=[first_round, second_round],
        exhausted=abstain,
        notes=notes,
    )


def _full_ranking(order: list[str], eliminated_in_order: list[str]) -> list[str]:
    seen = set(order)
    return order + [candidate for candidate in reversed(eliminated_in_order) if candidate not in seen]


def instant_runoff(bloc_counts: dict[tuple[str, ...], int], candidate_ids: list[str]) -> MethodResult:
    """Instant-runoff / ranked-choice elimination.

    A majority is a continuing-ballot total strictly greater than half, checked
    with integer arithmetic. The candidate with the fewest continuing votes is
    eliminated. Elimination ties remove the lexicographically greatest id.
    If every remaining candidate has the same continuing total, the result is a tie.
    Ballots move to the next continuing preference. Ballots with none remaining
    are exhausted and leave the majority denominator.
    """

    active = set(candidate_ids)
    eliminated_in_order: list[str] = []
    total = sum(bloc_counts.values())
    rounds: list[dict[str, Any]] = []
    seat_note = "Ranked-choice voting is implemented as a single-winner method."
    if total == 0 or not candidate_ids:
        return MethodResult(
            winner_ids=[],
            ranking=list(candidate_ids),
            seats=None,
            unallocated_seats=0,
            seat_explanation=seat_note,
            rounds=rounds,
            exhausted=total,
            notes=["No continuing ballots, so there is no ranked-choice winner."],
        )
    for _ in range(len(candidate_ids) + 1):
        first = {candidate: 0 for candidate in candidate_ids if candidate in active}
        continuing = 0
        for ballot_order, count in bloc_counts.items():
            if count <= 0:
                continue
            choice = next((candidate for candidate in ballot_order if candidate in active), None)
            if choice is not None:
                first[choice] += count
                continuing += count
        exhausted = total - continuing
        order = sorted(first, key=lambda candidate: (-first[candidate], candidate))
        ranking = _full_ranking(order, eliminated_in_order)
        if continuing == 0:
            rounds.append(
                {
                    "round_number": len(rounds) + 1,
                    "votes": first,
                    "continuing_ballots": 0,
                    "exhausted_ballots": exhausted,
                    "eliminated": [],
                    "note": "No continuing preferences remain.",
                }
            )
            return MethodResult(
                winner_ids=[],
                ranking=ranking,
                seats=None,
                unallocated_seats=0,
                seat_explanation=seat_note,
                rounds=rounds,
                exhausted=exhausted,
                notes=["All ballots were exhausted before a winner emerged."],
            )
        top = first[order[0]]
        leaders = [candidate for candidate in order if first[candidate] == top]
        has_majority = top * 2 > continuing and len(leaders) == 1
        if has_majority or len(active) == 1:
            rounds.append(
                {
                    "round_number": len(rounds) + 1,
                    "votes": first,
                    "continuing_ballots": continuing,
                    "exhausted_ballots": exhausted,
                    "eliminated": [],
                    "note": (
                        "A candidate has a strict majority of continuing ballots."
                        if has_majority
                        else "Only one candidate remains."
                    ),
                }
            )
            return MethodResult(
                winner_ids=[order[0]],
                ranking=ranking,
                seats=None,
                unallocated_seats=0,
                seat_explanation=seat_note,
                rounds=rounds,
                exhausted=exhausted,
                notes=["Ranked-choice winner on continuing ballots."],
            )
        if len(leaders) == len(active):
            rounds.append(
                {
                    "round_number": len(rounds) + 1,
                    "votes": first,
                    "continuing_ballots": continuing,
                    "exhausted_ballots": exhausted,
                    "eliminated": [],
                    "note": "Every remaining candidate has the same continuing total.",
                }
            )
            return MethodResult(
                winner_ids=leaders,
                ranking=ranking,
                seats=None,
                unallocated_seats=0,
                seat_explanation=seat_note,
                rounds=rounds,
                exhausted=exhausted,
                notes=["The remaining candidates are tied. The tie is reported."],
            )
        lowest = min(first.values())
        tied_low = [candidate for candidate, count in first.items() if count == lowest]
        eliminate = max(tied_low)
        rounds.append(
            {
                "round_number": len(rounds) + 1,
                "votes": first,
                "continuing_ballots": continuing,
                "exhausted_ballots": exhausted,
                "eliminated": [eliminate],
                "note": (
                    "Eliminated the lowest continuing candidate. "
                    "Ties remove the lexicographically greatest id."
                ),
            }
        )
        active.remove(eliminate)
        eliminated_in_order.append(eliminate)
    raise InvariantError("Ranked-choice counting did not terminate.")


def dhondt(votes: dict[str, int], seats: int) -> MethodResult:
    """D'Hondt seat allocation using exact integer quotient comparisons.

    Candidate A beats B for the next seat when
    votes[A] * (seats[B] + 1) > votes[B] * (seats[A] + 1).
    Equal quotients go to the lexicographically smaller candidate id.
    If every candidate has zero votes, seats stay unallocated and the reason
    is returned with the result.
    """

    ranking = sorted(votes, key=lambda candidate: (-votes[candidate], candidate))
    allocation = {candidate: 0 for candidate in ranking}
    if seats == 0:
        return MethodResult(
            winner_ids=[],
            ranking=ranking,
            seats=allocation,
            unallocated_seats=0,
            seat_explanation="Zero seats were requested, so the allocation is empty.",
            rounds=[],
            exhausted=0,
            notes=["D'Hondt was asked to allocate zero seats."],
        )
    if all(count == 0 for count in votes.values()):
        return MethodResult(
            winner_ids=[],
            ranking=ranking,
            seats=allocation,
            unallocated_seats=seats,
            seat_explanation=(
                "No valid votes. Every D'Hondt quotient is zero, so seats remain unallocated "
                "rather than being assigned arbitrarily."
            ),
            rounds=[],
            exhausted=0,
            notes=["Seats were left unallocated because there were no valid votes."],
        )
    for _ in range(seats):
        winner = ranking[0]
        for candidate in ranking[1:]:
            left = votes[candidate] * (allocation[winner] + 1)
            right = votes[winner] * (allocation[candidate] + 1)
            if left > right or (left == right and candidate < winner):
                winner = candidate
        allocation[winner] += 1
    ordered = sorted(
        allocation,
        key=lambda candidate: (-allocation[candidate], -votes[candidate], candidate),
    )
    top_seats = allocation[ordered[0]]
    leaders = [
        candidate
        for candidate in ordered
        if allocation[candidate] == top_seats and allocation[candidate] > 0
    ]
    return MethodResult(
        winner_ids=leaders,
        ranking=ordered,
        seats=allocation,
        unallocated_seats=0,
        seat_explanation="All requested seats were allocated by the D'Hondt rule.",
        rounds=[
            {
                "round_number": 1,
                "votes": dict(votes),
                "continuing_ballots": sum(votes.values()),
                "exhausted_ballots": 0,
                "eliminated": [],
                "note": "D'Hondt uses valid-vote totals. Seat ties in the winner list share the top seat count.",
            }
        ],
        exhausted=0,
        notes=["D'Hondt allocation completed."],
    )
