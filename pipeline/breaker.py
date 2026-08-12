"""The Circuit Breaker: when to stop refining and hand the problem to a human.

A refine loop with no breaker has two failure modes, and both are worse than
stopping. It can spin forever on an item the model cannot fix, burning tokens on
identical retries; or it can quietly accept a draft that stopped improving three
attempts ago. The breaker converts both into an explicit escalation with a
readable reason.

There are two levels:

* **Per item** (`ItemBreakerState` + `should_trip`) — this item is not
  converging.
* **Per run** (`RunBreaker`) — the run itself is unhealthy and should stop.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# =========================================================================
# POLICY DIAL — the project owner's tuning knobs for this pipeline.
# These are the values a human changes to make the pipeline more or less
# patient. They are constants rather than buried literals precisely so that
# "how many retries is too many" stays a visible, arguable decision.
# =========================================================================

MAX_REFINE_ATTEMPTS = 3
TRIP_ON_NO_PROGRESS = True  # same violation-code set twice running
TRIP_ON_REGRESSION = True  # violation count grew vs the previous attempt
RUN_ABORT_ESCALATION_RATIO = 0.5


@dataclass
class ItemBreakerState:
    """Per-item refine history.

    ``history`` holds one frozenset of violation codes per *evaluated attempt*,
    oldest first — including the initial draft's evaluation. Sets rather than
    lists because two attempts raising the same rules in a different order have
    made no progress, and the breaker must see that as identical.
    """

    key: str
    attempts: int = 0
    history: list[frozenset[str]] = field(default_factory=list)


def should_trip(state: ItemBreakerState) -> tuple[bool, str]:
    """Return (trip, human-readable reason).

    The reason string is written to be read by a person in an escalation report,
    not parsed, so it explains the judgement rather than naming the constant.
    Checked in priority order: budget first, then stagnation, then regression.
    """

    # 1. Attempt budget. Checked first because it is the unconditional ceiling —
    #    no amount of promising-looking movement buys a fourth attempt.
    if state.attempts >= MAX_REFINE_ATTEMPTS:
        return (
            True,
            f"attempt budget exhausted: {state.attempts} refine attempt(s) were "
            f"made and the item still fails (limit is MAX_REFINE_ATTEMPTS = "
            f"{MAX_REFINE_ATTEMPTS})",
        )

    # 2. No progress. Identical, non-empty violation sets on two consecutive
    #    attempts means the refiner is re-emitting a semantically equivalent
    #    draft. A third identical attempt is not going to be different.
    if TRIP_ON_NO_PROGRESS and len(state.history) >= 2:
        last, previous = state.history[-1], state.history[-2]
        if last and last == previous:
            return (
                True,
                "no progress: the same rule broke on two consecutive attempts "
                f"({', '.join(sorted(last))}). The refiner is returning an "
                "equivalent draft rather than reconciling the finding",
            )

    # 3. Regression. If a correction broke more than it fixed, continuing tends
    #    to compound the damage rather than recover from it.
    if TRIP_ON_REGRESSION and len(state.history) >= 2:
        if len(state.history[-1]) > len(state.history[-2]):
            return (
                True,
                "regression: the correction introduced more violations than it "
                f"fixed ({len(state.history[-2])} → {len(state.history[-1])} "
                "violations)",
            )

    return (False, "")


@dataclass
class RunBreaker:
    """Run-level health check.

    Rationale for existing at all: a per-item breaker catches a bad *item*. It
    cannot see that the whole run is failing. If a majority of items are
    escalating, the problem is not any one casualty — it is the prompt, the
    model, or the rule itself. That is a design problem for a human to look at,
    and no additional retries will fix it. Continuing would just spend the rest
    of the budget confirming what the first few items already established.
    """

    completed: int = 0
    escalated: int = 0

    def record(self, *, escalated: bool) -> None:
        """Record one finished item, accepted or escalated."""
        self.completed += 1
        if escalated:
            self.escalated += 1

    @property
    def escalation_ratio(self) -> float:
        """Escalated share of finished items; 0.0 before anything finishes."""
        if self.completed == 0:
            return 0.0
        return self.escalated / self.completed

    def should_abort_run(self) -> tuple[bool, str]:
        """Return (abort, human-readable reason).

        Requires at least 2 completed items before it can fire: aborting a run
        because its single first item escalated would make one unlucky casualty
        look like a systemic failure.
        """
        if self.completed < 2:
            return (False, "")
        if self.escalation_ratio > RUN_ABORT_ESCALATION_RATIO:
            return (
                True,
                f"run aborted: {self.escalated} of {self.completed} completed "
                f"items escalated ({self.escalation_ratio:.0%}), above the "
                f"{RUN_ABORT_ESCALATION_RATIO:.0%} tolerance. A majority of items "
                "failing is a prompt, model, or rule problem for a human to "
                "resolve — more retries will not fix it",
            )
        return (False, "")
