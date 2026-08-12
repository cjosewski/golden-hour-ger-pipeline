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

Both levels distinguish a *content* problem (the row keeps breaking a rule) from
a *transport* problem (the role call never returned a usable reply). They are
different failures with different fixes, and reporting one as the other sends
whoever reads the escalation to the wrong place.
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
MAX_TRANSPORT_FAILURES = 2  # role calls that returned nothing usable, per item
TRIP_ON_NO_PROGRESS = True  # same violation-code set twice running
TRIP_ON_REGRESSION = True  # violation count grew vs the previous attempt
RUN_ABORT_ESCALATION_RATIO = 0.5

# Every transport trip reason starts with this, so a report writer can tell a
# transport escalation from a content escalation without parsing prose.
TRANSPORT_TRIP_PREFIX = "transport failure"


def is_transport_trip(reason: str) -> bool:
    """True when a trip reason describes a failed role call, not a bad row."""
    return reason.startswith(TRANSPORT_TRIP_PREFIX)


@dataclass
class ItemBreakerState:
    """Per-item refine history.

    ``history`` holds one frozenset of violation codes per *evaluated attempt*,
    oldest first — including the initial draft's evaluation. Sets rather than
    lists because two attempts raising the same rules in a different order have
    made no progress, and the breaker must see that as identical.

    ``transport_failures`` counts attempts where the role call itself failed —
    a rate limit, a dropped connection, a reply that was not JSON. Those are
    deliberately **not** in ``history``. The orchestrator turns them into a
    synthetic ``GEN_INVALID_JSON`` violation so the loop has something to
    record, and two of those in a row used to look identical to the no-progress
    rule, which would then report a network outage as "the refiner is returning
    an equivalent draft rather than reconciling the finding" — a confident
    diagnosis of a problem that does not exist, about a draft that was never
    produced. They are counted separately and tripped separately instead.
    """

    key: str
    attempts: int = 0
    history: list[frozenset[str]] = field(default_factory=list)
    transport_failures: int = 0


def should_trip(state: ItemBreakerState) -> tuple[bool, str]:
    """Return (trip, human-readable reason).

    The reason string is written to be read by a person in an escalation report,
    not parsed, so it explains the judgement rather than naming the constant.
    Checked in priority order: transport, then budget, then stagnation, then
    regression.
    """

    # 0. Transport. Checked first because when it fires, nothing below it has
    #    any evidence to reason about: no draft was produced, so no rule was
    #    evaluated. Failure stance, stated deliberately: **fail closed**. The
    #    item escalates to a human unchecked rather than being accepted
    #    unchecked, because a row nobody evaluated is exactly the row this
    #    pipeline exists to keep out of the DataTable. The wording says
    #    "transport", never "the refiner will not learn" — misdiagnosing an
    #    outage as a content problem sends a human to the wrong document.
    if state.transport_failures >= MAX_TRANSPORT_FAILURES:
        return (
            True,
            f"{TRANSPORT_TRIP_PREFIX}: {state.transport_failures} role call(s) "
            "for this item returned nothing usable (limit is "
            f"MAX_TRANSPORT_FAILURES = {MAX_TRANSPORT_FAILURES}). No draft was "
            "produced and no rule was evaluated, so this says nothing about the "
            "row — it is a transport or reply-format problem for a human to "
            "look at",
        )

    # 1. Attempt budget. First among the content rules because it is the
    #    unconditional ceiling — no amount of promising-looking movement buys a
    #    fourth attempt.
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
    model, the rule itself, or the transport underneath all three. Whichever it
    is, it is a problem for a human to look at and no additional retries will
    fix it. Continuing would just spend the rest of the budget confirming what
    the first few items already established.

    ``transport_escalated`` is tracked separately from ``escalated`` so the
    abort message can name which of those it is. That distinction is not
    cosmetic: content and transport failures are read by different people and
    fixed in different places.
    """

    completed: int = 0
    escalated: int = 0
    transport_escalated: int = 0

    def record(self, *, escalated: bool, trip_reason: str = "") -> None:
        """Record one finished item, accepted or escalated.

        ``trip_reason`` is the escalated item's trip reason, so this level can
        make the same content-versus-transport distinction the per-item level
        makes. Without it a rate-limit storm that escalates two items out of two
        aborted the run with "a prompt, model, or rule problem for a human to
        resolve" — the exact misdiagnosis `should_trip` was rewritten to
        prevent, sending whoever reads it to the GDD over a network outage.

        An escalation recorded with no reason counts as a content failure. That
        is the conservative default: it is what this class did before the
        distinction existed, and it points a reader at the rules rather than
        blaming an outage that may not have happened.
        """
        self.completed += 1
        if escalated:
            self.escalated += 1
            if is_transport_trip(trip_reason):
                self.transport_escalated += 1

    @property
    def content_escalated(self) -> int:
        """Escalations caused by a row breaking a rule, not by a failed call."""
        return self.escalated - self.transport_escalated

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

        The abort threshold is the same whatever caused the escalations — a run
        where most calls are failing should stop either way — but the *reason*
        is not, because the reason is the whole product of an abort. A run
        killed by an expired API key and a run killed by a broken rule need
        different people looking at different things.
        """
        if self.completed < 2:
            return (False, "")
        if self.escalation_ratio <= RUN_ABORT_ESCALATION_RATIO:
            return (False, "")

        headline = (
            f"run aborted: {self.escalated} of {self.completed} completed items "
            f"escalated ({self.escalation_ratio:.0%}), above the "
            f"{RUN_ABORT_ESCALATION_RATIO:.0%} tolerance. "
        )

        if self.transport_escalated == self.escalated:
            return (
                True,
                headline + "Every one of those escalations was a "
                f"{TRANSPORT_TRIP_PREFIX}: the role calls returned nothing "
                "usable, so no draft was evaluated and no rule was ever "
                "checked. This says nothing about the rows, the prompt or the "
                "rule — it is an API key, rate limit or network problem. Fix "
                "that and re-run; there is no design decision waiting here",
            )

        if self.transport_escalated:
            return (
                True,
                headline + f"{self.transport_escalated} of them were transport "
                "failures (role calls that returned nothing usable) and "
                f"{self.content_escalated} were content failures, so this run "
                "is failing for two unrelated reasons at once. Clear the "
                "transport problem and re-run before reading the content "
                "escalations as evidence about the prompt or the rule",
            )

        return (
            True,
            headline + "A majority of items failing is a prompt, model, or "
            "rule problem for a human to resolve — more retries will not fix "
            "it",
        )
