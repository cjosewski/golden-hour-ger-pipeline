"""Offline self-test. No API key, no network.

Twenty-four numbered sections covering the SALT derivation, the evaluator's
rule families, the circuit breaker at both levels, the knowledge-base loaders,
the prompt builders, the CSV contract, the run log's rendering, and the GER
loop's recovery from a failed role call. Run with:

    uv run python -m pipeline --selftest

Every case is deterministic and independent. Case 2 is the GDD's own worked
example and case 3 guards the question-(c) inversion — between them they are the
two assertions most likely to catch a future edit that quietly breaks the rule
this whole pipeline exists to enforce.

Section 12 exists because of a mutation battery run against `salt.py`. Two
single-character mutations — inverting the peripheral-pulse comparison, and
tightening the consciousness comparison off its boundary — both survived the
whole suite. Every derivation in the graded rule needs at least one case where
it is the *only* thing that can decide the answer; otherwise the suite is
testing the fixtures, not the rule.

Cases 22e and 22f are the guard on a count the notes file states in prose. It
shipped saying "Three things below are not columns of the 24-column CSV" while
`TriageIntent` had five — a falsifiable claim in a graded artifact, and the
second hand-typed count in this project to go stale. The number is now derived
from the model; those two cases check the artifact against the model rather than
against the sentence that wrote it.

Sections 17 to 23 come from a review that found the untested paths were the
load-bearing ones: what the run log actually renders (17), a transport failure
being reported as a content problem (18), the one breaker rule with no coverage
and the CLI budget override (19), the JSON extractor the live path depends on
(20), the CSV cell renderer (21), and the two end-to-end guarantees the whole
submission rests on — an escalated row never reaches the CSV (22), and the
run-level breaker actually stops a bad run (23).

Section 24 is the guard on this submission's central design claim — that the
generator is never shown the SALT rule. Until it was written, that claim rested
entirely on a comment in `prompts.py`: one added citation in the field-group
excerpt, or one helpful edit to a brief, would have turned the graded evidence
into an empty log with nothing failing to say so.
"""

from __future__ import annotations

import contextlib
import csv
import io
import re
import tempfile
from pathlib import Path

from . import breaker as breaker_policy
from .breaker import (
    MAX_REFINE_ATTEMPTS,
    MAX_TRANSPORT_FAILURES,
    RUN_ABORT_ESCALATION_RATIO,
    ItemBreakerState,
    RunBreaker,
    is_transport_trip,
    should_trip,
)
from .evaluator import _derived_sentence, evaluate, redact_derived_category
from .generator import (
    GenerationError,
    PLACEHOLDER_LABEL,
    exemplar_shaped_row,
    extract_json_object,
)
from .orchestrate import (
    AttemptRecord,
    ItemOutcome,
    RunResult,
    _csv_cell,
    _render_text_change,
    run_item,
    run_requests,
    write_escalation,
    write_ger_log,
)
from .prompts import (
    build_generator_prompt,
    build_refiner_prompt,
    load_exemplar_csv_text,
    load_exemplar_row_names,
    load_field_group_excerpt,
)
from .requests import REQUESTS, ArchetypeRequest
from .schema import (
    CSV_COLUMNS,
    ArchetypeRow,
    EvaluationResult,
    GeneratedArchetype,
    SaltCategory,
    TriageIntent,
    Violation,
)
from .salt import derive_salt_category

REPO_ROOT = Path(__file__).resolve().parent.parent
EXEMPLAR_CSV = REPO_ROOT / "knowledge_base/DT_CasualtyArchetypes.exemplar.csv"

# A fully-true SALT input set, used as the base for the truth-table cases so
# each one varies exactly the input it is testing.
ALL_TRUE = {
    "breathing": True,
    "obeys_commands_or_purposeful_movement": True,
    "peripheral_pulse_present": True,
    "respiratory_distress": False,
    "hemorrhage_controlled": True,
    "survivable_with_resources": True,
    "minor_injuries_only": True,
}

# One real trip reason of each kind, produced by `should_trip` rather than typed
# out as literals here. The run breaker classifies escalations by reading the
# item breaker's reason string, so feeding it a hand-written "transport failure:
# ..." would keep the run-level cases passing after someone renamed the prefix —
# which is exactly the coupling those cases exist to hold.
_TRANSPORT_TRIP = should_trip(
    ItemBreakerState(key="_reason_fixture", transport_failures=MAX_TRANSPORT_FAILURES)
)[1]
_CONTENT_TRIP = should_trip(
    ItemBreakerState(
        key="_reason_fixture",
        attempts=MAX_REFINE_ATTEMPTS,
        history=[frozenset({"R1_SALT_MISMATCH"})],
    )
)[1]


class _Results:
    """Collects case outcomes and prints a PASS/FAIL summary."""

    def __init__(self) -> None:
        self.passed = 0
        self.failed: list[str] = []

    def check(self, name: str, condition: bool, message: str) -> None:
        if condition:
            self.passed += 1
            print(f"  PASS  {name}")
        else:
            self.failed.append(f"{name}: {message}")
            print(f"  FAIL  {name}")
            print(f"        {message}")


def _intent(**overrides: object) -> TriageIntent:
    """A coherent triage intent with overrides applied."""
    values: dict[str, object] = {
        "DeclaredCategory": SaltCategory.RED,
        "InitialConsciousness01": 0.85,
        "bMinorInjuriesOnly": False,
        "bSurvivableWithResources": True,
        "AuthoringNote": f"Test fixture. Values are a {PLACEHOLDER_LABEL}.",
    }
    values.update(overrides)
    return TriageIntent(**values)  # type: ignore[arg-type]


def _raises_generation_error(call: object) -> bool:
    """True when calling ``call`` raises `GenerationError`.

    A malformed reply must become a retryable finding rather than a crash, so
    "it raised the right exception type" is the assertion, not "it raised".
    """
    try:
        call()  # type: ignore[operator]
    except GenerationError:
        return True
    except Exception:  # noqa: BLE001 — any other exception is the failure
        return False
    return False


def _fixture_request(key: str, category: SaltCategory) -> ArchetypeRequest:
    """A request that exists only to drive the loop; never sent to a model."""
    return ArchetypeRequest(
        key=key,
        intended_category=category,
        brief="Self-test fixture request; never sent to a model.",
    )


# Sections 22 and 23 drive the real `run_requests` with these. Kept out of the
# shipped `REQUESTS` tuple deliberately: the offline demo is evidence about the
# rules, and padding it with items designed to fail would make its counts mean
# something else.
_CLEAN_REQUEST = _fixture_request("selftest_clean", SaltCategory.RED)
_UNFIXABLE_REQUEST = _fixture_request("selftest_unfixable", SaltCategory.GRAY)
_ABORT_REQUESTS: tuple[ArchetypeRequest, ...] = tuple(
    _fixture_request(f"selftest_abort_{index}", SaltCategory.RED)
    for index in (1, 2, 3)
)


def _clean_item(name: str) -> GeneratedArchetype:
    """An exemplar-shaped row with a coherent Red declaration: passes cleanly."""
    return GeneratedArchetype(
        row=exemplar_shaped_row(Name=name),
        triage_intent=_intent(DeclaredCategory=SaltCategory.RED),
    )


class _ScriptedGenerator:
    """Deterministic generator for the two end-to-end sections."""

    def __init__(self) -> None:
        self.model = "selftest-fixture"
        self.calls = 0

    def generate(self, request: ArchetypeRequest) -> GeneratedArchetype:
        self.calls += 1
        if request.key == _CLEAN_REQUEST.key:
            return _clean_item("Casualty_Selftest_Clean")
        if request.key == _UNFIXABLE_REQUEST.key:
            # Declared Gray while authoring survivable = true, which derives
            # Red. Only the request brief could settle which is right, and the
            # refiner never receives it — the same construction as the shipped
            # escalation item.
            return GeneratedArchetype(
                row=exemplar_shaped_row(Name="Casualty_Selftest_Unfixable"),
                triage_intent=_intent(
                    DeclaredCategory=SaltCategory.GRAY,
                    bSurvivableWithResources=True,
                ),
            )
        # The abort set: one band violation each, nothing else.
        index = request.key.rsplit("_", 1)[-1]
        return GeneratedArchetype(
            row=exemplar_shaped_row(
                Name=f"Casualty_Selftest_Abort_{index}",
                TourniquetPassWindowSeconds=240.0,
            ),
            triage_intent=_intent(DeclaredCategory=SaltCategory.RED),
        )


class _EchoRefiner:
    """Returns the draft unchanged — the no-progress condition, exactly."""

    def __init__(self) -> None:
        self.model = "selftest-fixture"
        self.calls = 0

    def refine(
        self, item: GeneratedArchetype, violations: list[Violation]
    ) -> GeneratedArchetype:
        self.calls += 1
        return item


class _ShufflingRefiner:
    """Trades one violation for a different one, forever.

    Neither the no-progress rule (identical code sets) nor the regression rule
    (more violations than before) can fire against this, so the only policy
    left to stop it is the attempt budget — which is what section 23 needs, so
    that the run-level abort it drives is provably caused by the budget
    override rather than by whichever rule happened to fire first.
    """

    def __init__(self) -> None:
        self.model = "selftest-fixture"
        self.calls = 0

    def refine(
        self, item: GeneratedArchetype, violations: list[Violation]
    ) -> GeneratedArchetype:
        self.calls += 1
        broke_the_band = any(
            v.code == "R2_TOURNIQUET_WINDOW_BAND" for v in violations
        )
        row: ArchetypeRow = item.row.model_copy(
            update={
                "TourniquetPassWindowSeconds": 120.0 if broke_the_band else 240.0,
                "RespirationRateDistressThresholdBpm": 40.0 if broke_the_band else 30.0,
            }
        )
        return GeneratedArchetype(row=row, triage_intent=item.triage_intent)


def run_selftest() -> int:
    """Run every case. Return 0 if all pass, 1 otherwise."""
    r = _Results()
    print("Golden Hour GER pipeline — self-test")
    print("=" * 72)
    print("")

    # ------------------------------------------------------------------
    print("[1] SALT truth table — all five categories reachable")
    # ------------------------------------------------------------------
    r.check(
        "1a not breathing -> Black",
        derive_salt_category(**{**ALL_TRUE, "breathing": False}) is SaltCategory.BLACK,
        "triage-system.md Core Rule 2.2: not breathing after airway "
        "repositioning means Dead (Black), full stop.",
    )
    r.check(
        "1b all four true + minor injuries -> Green",
        derive_salt_category(**ALL_TRUE) is SaltCategory.GREEN,
        "triage-system.md Core Rule 2.4: all four true and minor injuries only "
        "means Minimal (Green).",
    )
    r.check(
        "1c all four true + not minor -> Yellow",
        derive_salt_category(**{**ALL_TRUE, "minor_injuries_only": False})
        is SaltCategory.YELLOW,
        "triage-system.md Core Rule 2.4: all four true but injured and stable "
        "means Delayed (Yellow).",
    )
    r.check(
        "1d one question false + survivable -> Red",
        derive_salt_category(
            **{**ALL_TRUE, "peripheral_pulse_present": False, "minor_injuries_only": False}
        )
        is SaltCategory.RED,
        "triage-system.md Core Rule 2.5: any of the four false and survivable "
        "with available resources means Immediate (Red).",
    )
    r.check(
        "1e one question false + not survivable -> Gray",
        derive_salt_category(
            **{
                **ALL_TRUE,
                "peripheral_pulse_present": False,
                "survivable_with_resources": False,
                "minor_injuries_only": False,
            }
        )
        is SaltCategory.GRAY,
        "triage-system.md Core Rule 2.5: any of the four false and not "
        "survivable means Expectant (Gray).",
    )

    # ------------------------------------------------------------------
    print("")
    print("[2] The GDD's own worked example")
    # ------------------------------------------------------------------
    worked = derive_salt_category(
        breathing=True,
        obeys_commands_or_purposeful_movement=False,
        peripheral_pulse_present=True,
        respiratory_distress=False,
        hemorrhage_controlled=False,
        survivable_with_resources=True,
        minor_injuries_only=False,
    )
    r.check(
        "2 worked example derives Red",
        worked is SaltCategory.RED,
        "triage-system.md § Formulas, Worked example: 'A casualty is breathing, "
        "does not obey commands (unconscious), has a peripheral pulse, is not in "
        "respiratory distress, and has an uncontrolled hemorrhage. ... If "
        "survivable_with_resources = true ... category = Red.' "
        f"Derived {worked.value} instead.",
    )

    # ------------------------------------------------------------------
    print("")
    print("[3] The question-(c) inversion trap")
    # ------------------------------------------------------------------
    inverted = derive_salt_category(
        **{**ALL_TRUE, "respiratory_distress": True, "minor_injuries_only": False}
    )
    r.check(
        "3 respiratory distress alone derives Red, not Yellow",
        inverted is SaltCategory.RED,
        "triage-system.md § Formulas variable table: respiratory_distress is "
        "'SALT question (c) — inverted in the formula (question asks NOT in "
        "distress)'. A casualty in distress fails question (c), so with "
        "everything else true the category must be Red. "
        f"Derived {inverted.value} instead — the inversion has been dropped.",
    )

    # ------------------------------------------------------------------
    print("")
    print("[4] Evaluator catches the Pre-Build Declaration's failure")
    # ------------------------------------------------------------------
    declaration_case = GeneratedArchetype(
        row=exemplar_shaped_row(
            Name="Casualty_Declaration_Failure",
            InitialRespirationRateBpm=34.0,
            InitialSystolicBP=68.0,
            InitialDiastolicBP=44.0,
            HemorrhageInsultMagnitude01=0.45,
        ),
        triage_intent=_intent(
            DeclaredCategory=SaltCategory.YELLOW,
            InitialConsciousness01=0.15,
        ),
    )
    declaration_result = evaluate(declaration_case, seen_names=set())
    r.check(
        "4a R1_SALT_MISMATCH raised",
        "R1_SALT_MISMATCH" in declaration_result.codes,
        "RR 34, SBP 68, unresponsive and an uncontrolled bleed, declared Yellow: "
        "the exact row the Pre-Build Declaration names as the failure this "
        f"pipeline exists to catch. Codes raised: {sorted(declaration_result.codes)}",
    )
    r.check(
        "4b derived category is Red",
        declaration_result.derived_category is SaltCategory.RED,
        "All four SALT questions fail on these vitals and the casualty is "
        "survivable, so the ground truth is Red — the category the trainee "
        "correctly calls and would be marked down for. Derived "
        f"{declaration_result.derived_category}.",
    )
    # The refiner must never be handed the answer. The evaluator's own detail
    # names the derived category for the human reading the log; the refiner
    # prompt must have it stripped, or no item is ever genuinely unfixable and
    # the circuit breaker becomes unreachable.
    declaration_violations = declaration_result.violations
    disclosure = _derived_sentence(SaltCategory.RED)
    r.check(
        "4c the evaluator's own detail names the derived category (for humans)",
        any(disclosure in v.detail for v in declaration_violations),
        "ger_log.md and the escalation reports need both sides of the "
        "disagreement visible to a reviewer.",
    )
    refiner_prompt = build_refiner_prompt(declaration_case, declaration_violations)
    # Asserted against the redaction helper's contract — "none of the five
    # disclosure sentences survives" — rather than against the substring
    # "is Red". A substring check on a category name would false-fail the day a
    # fixture legitimately declares Red, which says nothing about redaction.
    leaked = [
        category.value
        for category in SaltCategory
        if _derived_sentence(category) in refiner_prompt
    ]
    r.check(
        "4d the refiner prompt does NOT disclose the derived category",
        not leaked,
        "prompts.py must strip the derived category before the refiner sees it, "
        "so the refiner reconciles the row itself instead of copying an answer. "
        f"Leaked disclosure sentence(s) for: {leaked}",
    )
    r.check(
        "4e redact_derived_category removes every category's disclosure",
        all(
            _derived_sentence(category)
            not in redact_derived_category(
                f"prefix {_derived_sentence(category)} suffix"
            )
            for category in SaltCategory
        ),
        "The helper owns both the sentence that goes in and the sentence that "
        "comes out, so it must handle all five categories, not just the ones a "
        "fixture happens to produce.",
    )

    # ------------------------------------------------------------------
    print("")
    print("[5] Evaluator passes a coherent row")
    # ------------------------------------------------------------------
    clean = GeneratedArchetype(
        row=exemplar_shaped_row(Name="Casualty_IED_LegHemorrhage_T1"),
        triage_intent=_intent(DeclaredCategory=SaltCategory.RED),
    )
    clean_result = evaluate(clean, seen_names=set())
    r.check(
        "5 exemplar row + coherent Red intent raises zero violations",
        clean_result.passed and not clean_result.violations,
        "The existing hand-authored row with a coherent Red declaration must "
        "pass cleanly, or the evaluator is producing false positives. Codes "
        f"raised: {sorted(clean_result.codes)}",
    )

    # ------------------------------------------------------------------
    print("")
    print("[6] R2 tuning-knob band")
    # ------------------------------------------------------------------
    band_case = GeneratedArchetype(
        row=exemplar_shaped_row(
            Name="Casualty_Band_Violation", TourniquetPassWindowSeconds=240.0
        ),
        triage_intent=_intent(DeclaredCategory=SaltCategory.RED),
    )
    band_result = evaluate(band_case, seen_names=set())
    r.check(
        "6a tourniquet window 240s raises R2_TOURNIQUET_WINDOW_BAND",
        "R2_TOURNIQUET_WINDOW_BAND" in band_result.codes,
        "treatment-interventions.md § Tuning Knobs gives the tourniquet pass "
        "window a safe range of 60-180s; 240s is outside it. Codes raised: "
        f"{sorted(band_result.codes)}",
    )

    # The blood-pressure ordering rule must not fire on a casualty in arrest,
    # who genuinely has no pulse pressure. Guarding both directions here because
    # an over-strict version of this rule pushes authors into inventing a blood
    # pressure for a dead casualty.
    arrest = GeneratedArchetype(
        row=exemplar_shaped_row(
            Name="Casualty_Arrest_ZeroBP",
            InitialHeartRateBpm=0.0,
            InitialRespirationRateBpm=0.0,
            InitialSpO2Percent=0.0,
            InitialSystolicBP=0.0,
            InitialDiastolicBP=0.0,
            HemorrhageInsultMagnitude01=0.0,
        ),
        triage_intent=_intent(
            DeclaredCategory=SaltCategory.BLACK,
            InitialConsciousness01=0.0,
            bSurvivableWithResources=False,
            bMinorInjuriesOnly=False,
        ),
    )
    arrest_result = evaluate(arrest, seen_names=set())
    r.check(
        "6b a 0/0 arrest row does not raise R2_BP_ORDER",
        "R2_BP_ORDER" not in arrest_result.codes,
        "A casualty in arrest has no pulse pressure, so 0/0 is the coherent "
        "authoring for the Black archetype in triage-system.md Core Rule 2.2. "
        f"Codes raised: {sorted(arrest_result.codes)}",
    )
    r.check(
        "6c a 0/0 arrest row passes cleanly overall",
        arrest_result.passed,
        "The apneic Black archetype must be authorable without tripping any "
        f"rule. Codes raised: {sorted(arrest_result.codes)}",
    )

    impossible_bp = GeneratedArchetype(
        row=exemplar_shaped_row(
            Name="Casualty_Impossible_BP",
            InitialSystolicBP=0.0,
            InitialDiastolicBP=40.0,
        ),
        triage_intent=_intent(DeclaredCategory=SaltCategory.RED),
    )
    r.check(
        "6d diastolic with zero systolic still raises R2_BP_ORDER",
        "R2_BP_ORDER" in evaluate(impossible_bp, seen_names=set()).codes,
        "A trough with no peak is impossible rather than merely absent, so the "
        "arrest carve-out must not swallow it.",
    )

    # A sign-flipped blood pressure used to pass clean. The ordering rule never
    # saw it: a non-positive systolic routes into the arrest carve-out, which
    # only objects to a *positive* diastolic, and -80 is not positive. Nothing
    # else reads these two fields, so SBP -120 / DBP -80 raised no violation
    # at all.
    negative_bp = GeneratedArchetype(
        row=exemplar_shaped_row(
            Name="Casualty_Negative_BP",
            InitialSystolicBP=-120.0,
            InitialDiastolicBP=-80.0,
        ),
        triage_intent=_intent(DeclaredCategory=SaltCategory.RED),
    )
    r.check(
        "6e negative blood pressure raises R2_NEGATIVE_BLOOD_PRESSURE",
        "R2_NEGATIVE_BLOOD_PRESSURE"
        in evaluate(negative_bp, seen_names=set()).codes,
        "R2 rejects a negative heart rate and a negative respiration rate; a "
        "negative blood pressure is the same class of impossible value and was "
        "passing cleanly.",
    )

    # ------------------------------------------------------------------
    print("")
    print("[7] R3 placeholder labelling")
    # ------------------------------------------------------------------
    unlabelled = GeneratedArchetype(
        row=exemplar_shaped_row(Name="Casualty_Unlabelled"),
        triage_intent=_intent(
            DeclaredCategory=SaltCategory.RED,
            AuthoringNote="Standard femoral bleed casualty, vitals per protocol.",
        ),
    )
    unlabelled_result = evaluate(unlabelled, seen_names=set())
    r.check(
        "7a unlabelled authoring note raises R3_MISSING_PLACEHOLDER_LABEL",
        "R3_MISSING_PLACEHOLDER_LABEL" in unlabelled_result.codes,
        "casualty-archetype-schema.md requires the 'clinically plausible "
        "placeholder - SME validation pending' label wherever an invented "
        f"clinical value is surfaced. Codes raised: {sorted(unlabelled_result.codes)}",
    )

    # Half a label is not a label. This rule used to match the bare word
    # "placeholder", which passed a note that used the word while never saying
    # review was pending — and "review is still pending" is the half that
    # carries the disclosure a reader acts on.
    half_labelled = GeneratedArchetype(
        row=exemplar_shaped_row(Name="Casualty_Half_Label"),
        triage_intent=_intent(
            DeclaredCategory=SaltCategory.RED,
            AuthoringNote="Femoral bleed casualty. Vitals are placeholder numbers.",
        ),
    )
    r.check(
        "7b a note saying 'placeholder' but not 'SME validation pending' still fails",
        "R3_MISSING_PLACEHOLDER_LABEL"
        in evaluate(half_labelled, seen_names=set()).codes,
        "The required label is 'clinically plausible placeholder — SME "
        "validation pending'. A note that calls the numbers placeholders "
        "without saying clinical review is outstanding does not disclose the "
        "thing the label exists to disclose.",
    )

    # ...and punctuation drift is not a labelling failure. The label contains an
    # em dash; an editor that normalises it, or a line break landing inside the
    # phrase, must not fail an honestly-labelled row.
    dash_variant = GeneratedArchetype(
        row=exemplar_shaped_row(Name="Casualty_Dash_Variant"),
        triage_intent=_intent(
            DeclaredCategory=SaltCategory.RED,
            AuthoringNote=(
                "Femoral bleed casualty. Vitals are a clinically plausible\n"
                "placeholder - SME  validation   pending."
            ),
        ),
    )
    r.check(
        "7c a hyphen, a line break and stray spaces do not fail an honest label",
        "R3_MISSING_PLACEHOLDER_LABEL"
        not in evaluate(dash_variant, seen_names=set()).codes,
        "R3 checks provenance, not typography. Matching the literal label "
        "string would fail a correctly-labelled row over an em dash an editor "
        "rewrote.",
    )

    # ------------------------------------------------------------------
    print("")
    print("[8] Circuit breaker — no progress")
    # ------------------------------------------------------------------
    stalled = ItemBreakerState(
        key="stalled",
        attempts=1,
        history=[frozenset({"R1_SALT_MISMATCH"}), frozenset({"R1_SALT_MISMATCH"})],
    )
    stalled_trip, stalled_reason = should_trip(stalled)
    r.check(
        "8 same violation set twice running trips the breaker",
        stalled_trip and "no progress" in stalled_reason,
        "TRIP_ON_NO_PROGRESS must fire when two consecutive attempts raise an "
        f"identical, non-empty violation set. Got trip={stalled_trip}, "
        f"reason={stalled_reason!r}",
    )

    # ------------------------------------------------------------------
    print("")
    print("[9] Circuit breaker — attempt budget")
    # ------------------------------------------------------------------
    exhausted = ItemBreakerState(
        key="exhausted",
        attempts=MAX_REFINE_ATTEMPTS,
        # Distinct sets each attempt, so only the budget rule can fire here.
        history=[
            frozenset({"R1_SALT_MISMATCH"}),
            frozenset({"R2_RR_THRESHOLD_BAND"}),
            frozenset({"R4_BAD_NAME"}),
        ],
    )
    exhausted_trip, exhausted_reason = should_trip(exhausted)
    r.check(
        "9 attempt budget exhausted trips the breaker",
        exhausted_trip and "attempt budget" in exhausted_reason,
        f"MAX_REFINE_ATTEMPTS is {MAX_REFINE_ATTEMPTS}; an item at that count "
        f"must trip. Got trip={exhausted_trip}, reason={exhausted_reason!r}",
    )

    # ------------------------------------------------------------------
    print("")
    print("[10] Run breaker aborts past the escalation ratio")
    # ------------------------------------------------------------------
    healthy = RunBreaker()
    healthy.record(escalated=True)
    early_abort, _ = healthy.should_abort_run()
    r.check(
        "10a one escalated item alone does not abort the run",
        not early_abort,
        "The run breaker requires at least 2 completed items before it can "
        "fire, so a single unlucky casualty cannot look like systemic failure.",
    )

    unhealthy = RunBreaker()
    unhealthy.record(escalated=True, trip_reason=_CONTENT_TRIP)
    unhealthy.record(escalated=True, trip_reason=_CONTENT_TRIP)
    unhealthy.record(escalated=False)
    abort, abort_reason = unhealthy.should_abort_run()
    r.check(
        "10b escalation ratio above tolerance aborts the run",
        abort and "run aborted" in abort_reason.lower(),
        f"2 of 3 escalated is {2 / 3:.0%}, above the "
        f"{RUN_ABORT_ESCALATION_RATIO:.0%} tolerance. Got abort={abort}, "
        f"reason={abort_reason!r}",
    )
    r.check(
        "10b-ii an all-content abort still blames the prompt, model or rule",
        "prompt, model, or rule" in abort_reason
        and "transport" not in abort_reason,
        "Nothing here is a transport failure, so the run-level diagnosis must "
        f"be the content one it always was. Reason: {abort_reason!r}",
    )

    # The run level used to count a transport escalation identically to a
    # content one, so a rate-limit storm that escalated 2 of 2 aborted with "a
    # prompt, model, or rule problem for a human to resolve" — sending a human
    # to the GDD over a dead network. That is the same misdiagnosis
    # `should_trip` was rewritten to prevent, one level up, and the live run is
    # exactly where it fires.
    storm = RunBreaker()
    storm.record(escalated=True, trip_reason=_TRANSPORT_TRIP)
    storm.record(escalated=True, trip_reason=_TRANSPORT_TRIP)
    storm_abort, storm_reason = storm.should_abort_run()
    r.check(
        "10c an all-transport abort is not reported as a content problem",
        storm_abort
        and storm.transport_escalated == 2
        and "transport failure" in storm_reason
        and "prompt, model, or rule problem" not in storm_reason,
        "Every escalation here was a failed role call: no draft was produced "
        "and no rule was ever checked, so the abort must say so and send the "
        f"reader at the API key or the network. Reason: {storm_reason!r}",
    )

    mixed = RunBreaker()
    mixed.record(escalated=True, trip_reason=_TRANSPORT_TRIP)
    mixed.record(escalated=True, trip_reason=_CONTENT_TRIP)
    mixed.record(escalated=False)
    mixed_abort, mixed_reason = mixed.should_abort_run()
    r.check(
        "10d a mixed abort names both causes instead of picking one",
        mixed_abort
        and mixed.transport_escalated == 1
        and mixed.content_escalated == 1
        and "transport failures" in mixed_reason
        and "content failures" in mixed_reason,
        "Reporting a mixed run as purely one or the other hides half of what "
        "went wrong, and the content escalation cannot be read as evidence "
        "about the prompt until the transport problem is cleared. Reason: "
        f"{mixed_reason!r}",
    )

    # ------------------------------------------------------------------
    print("")
    print("[11] R1 vitals-override gate")
    # ------------------------------------------------------------------
    # `casualty-archetype-schema.md` § Group 1 makes bApplyInitialVitalsOverride
    # the gate over the five Initial* fields, and defaults it to false. With the
    # gate off the row's vitals never reach the casualty, so deriving a SALT
    # category from them is deriving ground truth from numbers the row itself
    # declares inert — and a row that does exactly that used to pass every rule.
    gate_off = GeneratedArchetype(
        row=exemplar_shaped_row(
            Name="Casualty_Gate_Off",
            bApplyInitialVitalsOverride=False,
        ),
        triage_intent=_intent(DeclaredCategory=SaltCategory.RED),
    )
    gate_off_result = evaluate(gate_off, seen_names=set())
    r.check(
        "11a gate off raises R1_VITALS_GATE_OFF",
        "R1_VITALS_GATE_OFF" in gate_off_result.codes,
        "casualty-archetype-schema.md § Group 1: 'when false, the patient "
        "file's built-in baseline stands untouched.' The authored vitals are "
        "then not the spawn state and cannot ground a category. Codes raised: "
        f"{sorted(gate_off_result.codes)}",
    )
    r.check(
        "11b gate off suppresses the mismatch check rather than stacking on it",
        "R1_SALT_MISMATCH" not in gate_off_result.codes
        and gate_off_result.derived_category is None,
        "Once the gate is known to be off the derivation is not trustworthy, so "
        "reporting a mismatch derived from it would be noise on top of the real "
        f"finding. Codes raised: {sorted(gate_off_result.codes)}, derived "
        f"{gate_off_result.derived_category}.",
    )
    gate_on = GeneratedArchetype(
        row=exemplar_shaped_row(Name="Casualty_Gate_On"),
        triage_intent=_intent(DeclaredCategory=SaltCategory.RED),
    )
    gate_on_result = evaluate(gate_on, seen_names=set())
    r.check(
        "11c gate on with coherent vitals does NOT raise R1_VITALS_GATE_OFF",
        "R1_VITALS_GATE_OFF" not in gate_on_result.codes
        and gate_on_result.passed,
        "The gate rule must fire on the gate, not on every row. Codes raised: "
        f"{sorted(gate_on_result.codes)}",
    )
    # The Black sub-rule reads InitialRespirationRateBpm, so it is gated for the
    # same reason: with the gate off that number is not the spawn rate.
    gate_off_black = GeneratedArchetype(
        row=exemplar_shaped_row(
            Name="Casualty_Gate_Off_Black",
            bApplyInitialVitalsOverride=False,
            InitialRespirationRateBpm=11.0,
        ),
        triage_intent=_intent(
            DeclaredCategory=SaltCategory.BLACK,
            InitialConsciousness01=0.0,
            bSurvivableWithResources=False,
            bMinorInjuriesOnly=False,
        ),
    )
    r.check(
        "11d gate off also suppresses R1_BLACK_REQUIRES_APNEA",
        "R1_BLACK_REQUIRES_APNEA"
        not in evaluate(gate_off_black, seen_names=set()).codes,
        "'A breathing casualty cannot be Black' is an inference from "
        "InitialRespirationRateBpm, which the gate declares inert. Every rule "
        "that reads the five Initial* vitals is gated, not just the mismatch.",
    )

    # ------------------------------------------------------------------
    print("")
    print("[12] Mutation guards on the two unguarded derivations")
    # ------------------------------------------------------------------
    # 12a: peripheral pulse is the ONLY false question here. Everything else is
    # deliberately true — alert, breathing at 11, no bleed — so only the
    # `InitialSystolicBP >= PulseQualityAbsentThresholdSystolicBP` comparison
    # can decide the answer. Inverting that comparison makes this row derive
    # Yellow, match its declaration, and pass; before this case existed, that
    # inversion survived the entire suite.
    pulse_only = GeneratedArchetype(
        row=exemplar_shaped_row(
            Name="Casualty_PulseOnly_False",
            InitialRespirationRateBpm=11.0,
            InitialSystolicBP=60.0,  # below the row's own absent cut point (70)
            InitialDiastolicBP=38.0,
            HemorrhageInsultMagnitude01=0.0,
            HemorrhageInsultActionName="None",
        ),
        triage_intent=_intent(
            DeclaredCategory=SaltCategory.YELLOW,
            InitialConsciousness01=0.85,
            bSurvivableWithResources=True,
            bMinorInjuriesOnly=False,
        ),
    )
    pulse_only_result = evaluate(pulse_only, seen_names=set())
    r.check(
        "12a question (b) alone false: mismatch raised, derives Red",
        "R1_SALT_MISMATCH" in pulse_only_result.codes
        and pulse_only_result.derived_category is SaltCategory.RED,
        "SBP 60 is below this row's own PulseQualityAbsentThresholdSystolicBP "
        "of 70, so SALT question (b) is false while (a), (c) and (d) are true. "
        "Core Rule 2.5 then gives Red for a survivable casualty, against a "
        "declared Yellow. Codes raised: "
        f"{sorted(pulse_only_result.codes)}, derived "
        f"{pulse_only_result.derived_category}.",
    )

    # 12b: consciousness exactly AT the altered threshold. The derivation is
    # `InitialConsciousness01 >= ConsciousnessAlteredThreshold01`, and
    # casualty-archetype-schema.md § Group 6 places the Weak expression state
    # *below* the threshold — so a casualty sitting exactly on it still obeys
    # commands. Tightening `>=` to `>` flips this row to Red and used to be
    # invisible to the suite.
    at_threshold = GeneratedArchetype(
        row=exemplar_shaped_row(
            Name="Casualty_Consciousness_AtThreshold",
            InitialRespirationRateBpm=11.0,
            InitialSystolicBP=114.0,
            InitialDiastolicBP=73.0,
            HemorrhageInsultMagnitude01=0.0,
            HemorrhageInsultActionName="None",
            ConsciousnessAlteredThreshold01=0.5,
        ),
        triage_intent=_intent(
            DeclaredCategory=SaltCategory.YELLOW,
            InitialConsciousness01=0.5,  # exactly at the threshold
            bSurvivableWithResources=True,
            bMinorInjuriesOnly=False,
        ),
    )
    at_threshold_result = evaluate(at_threshold, seen_names=set())
    r.check(
        "12b consciousness exactly at the altered threshold still obeys",
        at_threshold_result.passed
        and at_threshold_result.derived_category is SaltCategory.YELLOW,
        "casualty-archetype-schema.md § Group 6 puts the 'Weak' expression "
        "state BELOW ConsciousnessAlteredThreshold01, so a casualty exactly at "
        "it is not yet altered and question (a) is true. All four true and not "
        "minor-injuries-only gives Yellow. Codes raised: "
        f"{sorted(at_threshold_result.codes)}, derived "
        f"{at_threshold_result.derived_category}.",
    )

    # ------------------------------------------------------------------
    print("")
    print("[13] R4 schema integrity against the live table")
    # ------------------------------------------------------------------
    exemplar_names = load_exemplar_row_names()
    collision = GeneratedArchetype(
        row=exemplar_shaped_row(Name="Casualty_IED_LegHemorrhage_T1"),
        triage_intent=_intent(DeclaredCategory=SaltCategory.RED),
    )
    r.check(
        "13a a row key already in the live table raises R4_DUPLICATE_NAME",
        "R4_DUPLICATE_NAME"
        in evaluate(collision, seen_names=set(exemplar_names)).codes,
        "run_pipeline seeds seen_names from the exemplar CSV. Unreal keys "
        "DataTable rows by Name, so a generated row reusing an existing key "
        "silently overwrites the hand-authored casualty on import — the one "
        f"collision that actually costs something. Exemplar keys: "
        f"{sorted(exemplar_names)}",
    )

    bad_path = GeneratedArchetype(
        row=exemplar_shaped_row(
            Name="Casualty_BadPath",
            CasualtyCharacterAssetPath=(
                "Content/GoldenHour/Characters/CasualtyT1/Casualty_01"
            ),
        ),
        triage_intent=_intent(DeclaredCategory=SaltCategory.RED),
    )
    r.check(
        "13b an on-disk content folder raises R4_BAD_ASSET_PATH",
        "R4_BAD_ASSET_PATH" in evaluate(bad_path, seen_names=set()).codes,
        "`Content/...` and `/Game/...` name the same file but only the second "
        "resolves at runtime, and per casualty-archetype-schema.md the failure "
        "surfaces only in a cooked build.",
    )

    unsafe_text = GeneratedArchetype(
        row=exemplar_shaped_row(
            Name="Casualty_UnsafeText",
            HemorrhageSiteTag="LeftThigh_Femoral, proximal",
        ),
        triage_intent=_intent(DeclaredCategory=SaltCategory.RED),
    )
    r.check(
        "13c a comma in a free-text column raises R4_UNSAFE_CSV_TEXT",
        "R4_UNSAFE_CSV_TEXT" in evaluate(unsafe_text, seen_names=set()).codes,
        "Unreal's DataTable importer reads the source line by line; a comma, "
        "quote or newline in a free-text cell changes the shape of the row.",
    )

    # ------------------------------------------------------------------
    print("")
    print("[14] Knowledge-base loaders used only by the live path")
    # ------------------------------------------------------------------
    # Neither loader is reachable from --selftest or --offline: both are called
    # only by LiveGenerator.generate. Their marker strings are matched against
    # the copied documents at read time, so a heading edit — or an editor
    # normalising the em dash in "### Group 1 —" to a hyphen — raises ValueError
    # on the first live call while both offline commands stay green. These two
    # cases are the only thing that fails fast instead.
    try:
        excerpt = load_field_group_excerpt()
    except ValueError as exc:
        excerpt = ""
        excerpt_error: str | None = str(exc)
    else:
        excerpt_error = None
    r.check(
        "14a load_field_group_excerpt returns the Group 1..7 specification",
        excerpt_error is None
        and "Group 1" in excerpt
        and "Group 7" in excerpt
        and "bApplyInitialVitalsOverride" in excerpt,
        "The live generator prompt is grounded in this slice of "
        "casualty-archetype-schema.md. If the headings it slices between have "
        f"moved, the live path raises on its first call. Error: {excerpt_error}; "
        f"length {len(excerpt)}.",
    )

    exemplar_text = load_exemplar_csv_text()
    r.check(
        "14b load_exemplar_csv_text returns the header and the live row",
        "Name,PulsePatientFileName" in exemplar_text
        and "Casualty_IED_LegHemorrhage_T1" in exemplar_text,
        "The live generator prompt shows the real table as it exists today so "
        f"the output shape is copied rather than described. Got {len(exemplar_text)} "
        "characters.",
    )

    # ------------------------------------------------------------------
    print("")
    print("[15] CSV columns match the real DataTable header")
    # ------------------------------------------------------------------
    with EXEMPLAR_CSV.open("r", encoding="utf-8", newline="") as handle:
        exemplar_header = tuple(next(csv.reader(handle)))
    r.check(
        "15a CSV_COLUMNS equals the exemplar CSV header exactly",
        CSV_COLUMNS == exemplar_header,
        "The generated CSV must carry the exact column names of the real "
        "DT_CasualtyArchetypes source, or Unreal's DataTable importer silently "
        "fails to map them (.claude/rules/data-files.md). "
        f"Model gives {len(CSV_COLUMNS)} columns, exemplar has "
        f"{len(exemplar_header)}. First difference: "
        f"{next((f'{a!r} != {b!r}' for a, b in zip(CSV_COLUMNS, exemplar_header) if a != b), 'none')}",
    )

    # The README claims its embedded diagram is identical to the standalone
    # `architecture.mmd`. Two copies of anything drift; this is the check that
    # keeps the claim true, rather than a promise to remember.
    diagram_source = (REPO_ROOT / "architecture.mmd").read_text(encoding="utf-8")
    readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    embedded = readme_text.split("```mermaid\n")
    embedded_diagram = (
        embedded[1].split("```")[0] if len(embedded) > 1 else "(no mermaid block)"
    )
    r.check(
        "15b the README's embedded diagram matches architecture.mmd exactly",
        embedded_diagram.strip() == diagram_source.strip(),
        "The README says the same diagram source is committed standalone. "
        "First differing line: "
        + str(
            next(
                (
                    f"{a!r} != {b!r}"
                    for a, b in zip(
                        embedded_diagram.strip().splitlines(),
                        diagram_source.strip().splitlines(),
                    )
                    if a != b
                ),
                "none (lengths may differ)",
            )
        ),
    )

    # ------------------------------------------------------------------
    print("")
    print("[16] GER loop recovery from a failed role call")
    # ------------------------------------------------------------------
    # The only rule-family code the offline run never produces is
    # GEN_INVALID_JSON, because a fixture cannot return malformed JSON. This
    # section drives that path with a generator that fails once, and pins the
    # two behaviours that were wrong: the refiner must be handed the last REAL
    # violations rather than the synthetic transport one, and the failed
    # attempt must record no draft rather than re-recording the previous one.
    class _FailOnceGenerator:
        """Raises on its first call, then returns a row breaking one R2 rule."""

        def __init__(self) -> None:
            self.model = "selftest-fixture"
            self.calls = 0

        def generate(self, request: ArchetypeRequest) -> GeneratedArchetype:
            self.calls += 1
            if self.calls == 1:
                raise GenerationError("simulated malformed reply")
            return GeneratedArchetype(
                row=exemplar_shaped_row(
                    Name="Casualty_Retry_Case", TourniquetPassWindowSeconds=240.0
                ),
                triage_intent=_intent(DeclaredCategory=SaltCategory.RED),
            )

    class _RecordingRefiner:
        """Repairs the band violation, and remembers what it was asked to fix."""

        def __init__(self) -> None:
            self.model = "selftest-fixture"
            self.calls = 0
            self.seen: list[frozenset[str]] = []

        def refine(
            self, item: GeneratedArchetype, violations: list[Violation]
        ) -> GeneratedArchetype:
            self.calls += 1
            self.seen.append(frozenset(v.code for v in violations))
            return GeneratedArchetype(
                row=item.row.model_copy(
                    update={"TourniquetPassWindowSeconds": 120.0}
                ),
                triage_intent=item.triage_intent,
            )

    retry_request = ArchetypeRequest(
        key="selftest_retry",
        intended_category=SaltCategory.RED,
        brief="Self-test fixture request; never sent to a model.",
    )
    retry_generator = _FailOnceGenerator()
    retry_refiner = _RecordingRefiner()
    retry_outcome = run_item(
        retry_request,
        generator=retry_generator,
        refiner=retry_refiner,
        seen_names=set(),
    )
    r.check(
        "16a a failed role call is recorded with no draft",
        retry_outcome.attempts[0].item is None
        and "GEN_INVALID_JSON" in retry_outcome.attempts[0].result.codes,
        "AttemptRecord.item is None when the role call itself failed — there "
        "was no draft to judge. Recording the previous draft there would show "
        "a revision the refiner never returned. Got "
        f"item={retry_outcome.attempts[0].item!r}, codes "
        f"{sorted(retry_outcome.attempts[0].result.codes)}.",
    )
    r.check(
        "16b the failed call is retried rather than refined",
        retry_generator.calls == 2,
        "A generator that returned garbage has produced no item to refine, so "
        f"the next pass must call the generator again. Generator calls: "
        f"{retry_generator.calls}.",
    )
    r.check(
        "16c the refiner is asked to fix the real violation, not the transport error",
        retry_refiner.seen == [frozenset({"R2_TOURNIQUET_WINDOW_BAND"})],
        "The synthetic GEN_INVALID_JSON verdict describes a malformed reply, "
        "not the rule the row breaks. Passing it to the refiner spends an "
        f"attempt fixing nothing. Refiner saw: {retry_refiner.seen}.",
    )
    r.check(
        "16d the item still completes and is accepted",
        retry_outcome.accepted and not retry_outcome.escalated,
        "One transport failure inside the attempt budget must not cost the "
        f"item. Accepted={retry_outcome.accepted}, "
        f"escalated={retry_outcome.escalated}.",
    )
    r.check(
        "16e the failed call is not counted as a refine attempt",
        retry_outcome.refine_attempts == 1,
        "Three attempts were recorded but the refiner ran once — the first "
        "attempt failed before producing a draft, and the loop answered that "
        "by calling the generator again. Counting drafts minus one reported "
        f"the refiner doing work it never did. Got "
        f"{retry_outcome.refine_attempts}.",
    )
    r.check(
        "16f the retried attempt is labelled a generator retry, not a revision",
        retry_outcome.attempt_label(retry_outcome.attempts[1])
        == "Attempt 2 — generator retry 1",
        "Attempt 2 here was the generator being called again, because attempt "
        "1 produced no draft. Labelling it 'refiner revision 1' in the run log "
        "credits the refiner with a draft it never returned. Got "
        f"{retry_outcome.attempt_label(retry_outcome.attempts[1])!r}.",
    )

    # ------------------------------------------------------------------
    print("")
    print("[17] The run log shows what each refine actually changed")
    # ------------------------------------------------------------------
    # The defect this guards: every draft was described by a hand-listed
    # summary line, so an item repaired in a column that line did not print
    # rendered two byte-identical drafts whose verdict flipped from violation
    # to clean. Read as evidence, that says the evaluator is
    # non-deterministic — an attack on the exact claim the log exists to prove.
    # The change line is computed by iterating the models, so a new field is
    # covered without anyone remembering to add it here.
    log_request = ArchetypeRequest(
        key="selftest_log_render",
        intended_category=SaltCategory.RED,
        brief="Self-test fixture request; never sent to a model.",
    )
    band_draft = GeneratedArchetype(
        row=exemplar_shaped_row(
            Name="Casualty_Log_Render", TourniquetPassWindowSeconds=240.0
        ),
        triage_intent=_intent(DeclaredCategory=SaltCategory.RED),
    )
    fixed_draft = GeneratedArchetype(
        row=band_draft.row.model_copy(
            update={"TourniquetPassWindowSeconds": 120.0}
        ),
        triage_intent=band_draft.triage_intent,
    )
    log_outcome = ItemOutcome(
        request=log_request,
        attempts=[
            AttemptRecord(
                index=0, item=band_draft, result=evaluate(band_draft, seen_names=set())
            ),
            AttemptRecord(
                index=1, item=fixed_draft, result=evaluate(fixed_draft, seen_names=set())
            ),
        ],
        accepted=True,
    )
    log_run = RunResult(
        outcomes=[log_outcome],
        mode="selftest",
        model="selftest-fixture",
        requested=1,
    )
    with tempfile.TemporaryDirectory() as tmp:
        log_path = Path(tmp) / "ger_log.md"
        write_ger_log(log_run, log_path)
        log_text = log_path.read_text(encoding="utf-8")

    attempt_blocks = log_text.split("### Attempt")
    # Everything the log says about the draft itself, before the verdict on it.
    draft_renders = [
        block.split("**Evaluator findings:**")[0] for block in attempt_blocks[1:3]
    ]
    r.check(
        "17a the two attempts do not render identically",
        len(draft_renders) == 2 and draft_renders[0] != draft_renders[1],
        "The only difference between these two drafts is "
        "TourniquetPassWindowSeconds, which is not a vital. If the log renders "
        "them identically, a reader sees an unchanged draft whose verdict "
        "flipped and concludes the evaluator is not deterministic.",
    )
    r.check(
        "17b the change line names the field and both values",
        "**Changed since attempt 1**: TourniquetPassWindowSeconds 240 → 120"
        in log_text,
        "The change line is the explicit answer to 'what did the refiner "
        "actually do'. Rendered log:\n"
        + "\n".join(line for line in log_text.splitlines() if "Changed" in line),
    )
    identical_run = RunResult(
        outcomes=[
            ItemOutcome(
                request=log_request,
                attempts=[
                    AttemptRecord(
                        index=index,
                        item=band_draft,
                        result=evaluate(band_draft, seen_names=set()),
                    )
                    for index in (0, 1)
                ],
                escalated=True,
                trip_reason=(
                    "no progress: the same rule broke on two consecutive attempts"
                ),
            )
        ],
        mode="selftest",
        model="selftest-fixture",
        requested=1,
    )
    with tempfile.TemporaryDirectory() as tmp:
        identical_path = Path(tmp) / "ger_log.md"
        write_ger_log(identical_run, identical_path)
        identical_text = identical_path.read_text(encoding="utf-8")
    r.check(
        "17c a draft that changed nothing says so, rather than saying nothing",
        "**Changed since attempt 1**: (no field changed)" in identical_text,
        "An identical re-submission is exactly the condition the breaker's "
        "no-progress rule exists to catch, so the log states it outright "
        "instead of leaving a reader to compare two blocks by eye. Change "
        "lines rendered: "
        + str([line for line in identical_text.splitlines() if "Changed" in line]),
    )

    # A refiner that re-wraps a long authoring note without changing a word is
    # the degenerate input to the eliding renderer: `_field_changes` sees the
    # raw values differ and reports a change, then both sides normalise to the
    # same string, the common prefix runs to full length, both middles come out
    # empty and the log prints `AuthoringNote gained ''`. A real difference
    # rendered as nothing is the precise failure this renderer was written to
    # remove, so it must be named rather than elided.
    rewrapped_before = (
        "Clinically plausible placeholder — SME validation pending. Vitals "
        "chosen to fit a femoral bleed in a warm zone with no intervention "
        "yet applied, and thresholds left at the archetype defaults."
    )
    rewrapped_after = rewrapped_before.replace(" ", "\n   ", 1) + "  "
    whitespace_render = _render_text_change(rewrapped_before, rewrapped_after)
    r.check(
        "17d a whitespace-only edit says so instead of rendering as nothing",
        whitespace_render == "whitespace only (no text changed)",
        "Re-wrapping a note changes the raw value, so a change line is emitted "
        "either way; if the renderer degenerates it emits `gained ''`, which "
        "reads as a difference the log could not describe. Rendered: "
        f"{whitespace_render!r}",
    )
    r.check(
        "17e a real edit to the same long note is still rendered as a diff",
        "gained" in _render_text_change(
            rewrapped_before, rewrapped_before + " Reviewed again."
        ),
        "17d must not be satisfiable by a renderer that has stopped "
        "distinguishing long strings at all.",
    )

    # ------------------------------------------------------------------
    print("")
    print("[18] A failed role call is not reported as a content problem")
    # ------------------------------------------------------------------
    transport_state = ItemBreakerState(
        key="transport", transport_failures=MAX_TRANSPORT_FAILURES
    )
    transport_trip, transport_reason = should_trip(transport_state)
    r.check(
        "18a repeated transport failures trip on their own dial",
        transport_trip and is_transport_trip(transport_reason),
        f"MAX_TRANSPORT_FAILURES is {MAX_TRANSPORT_FAILURES}; an item that has "
        "hit it must escalate. Got trip="
        f"{transport_trip}, reason={transport_reason!r}",
    )
    r.check(
        "18b the transport reason never diagnoses the refiner",
        "no progress" not in transport_reason
        and "equivalent draft" not in transport_reason,
        "Two rate limits used to enter the violation history as identical "
        "synthetic verdicts and trip the no-progress rule, which reports 'the "
        "refiner is returning an equivalent draft rather than reconciling the "
        "finding' — a confident diagnosis of a draft that was never produced. "
        f"Reason: {transport_reason!r}",
    )

    class _AlwaysFailsGenerator:
        """Every call fails, as a rate-limited or unreachable API would."""

        def __init__(self) -> None:
            self.model = "selftest-fixture"
            self.calls = 0

        def generate(self, request: ArchetypeRequest) -> GeneratedArchetype:
            self.calls += 1
            raise GenerationError("simulated rate limit (429)")

    class _UnusedRefiner:
        def __init__(self) -> None:
            self.model = "selftest-fixture"
            self.calls = 0

        def refine(
            self, item: GeneratedArchetype, violations: list[Violation]
        ) -> GeneratedArchetype:
            self.calls += 1
            return item

    transport_request = ArchetypeRequest(
        key="selftest_transport",
        intended_category=SaltCategory.RED,
        brief="Self-test fixture request; never sent to a model.",
    )
    transport_refiner = _UnusedRefiner()
    transport_outcome = run_item(
        transport_request,
        generator=_AlwaysFailsGenerator(),
        refiner=transport_refiner,
        seen_names=set(),
    )
    r.check(
        "18c an item whose role calls all fail escalates as a transport failure",
        transport_outcome.escalated
        and is_transport_trip(transport_outcome.trip_reason)
        and all(record.item is None for record in transport_outcome.attempts),
        "Fail-closed: a row nobody evaluated must not be accepted. Got "
        f"escalated={transport_outcome.escalated}, reason="
        f"{transport_outcome.trip_reason!r}",
    )
    r.check(
        "18d the refiner is never called when no draft exists",
        transport_refiner.calls == 0,
        "There is nothing to refine until a draft parses. Refiner calls: "
        f"{transport_refiner.calls}.",
    )
    with tempfile.TemporaryDirectory() as tmp:
        transport_report_path = Path(tmp) / "transport.md"
        write_escalation(transport_outcome, transport_report_path)
        transport_report = transport_report_path.read_text(encoding="utf-8")
    r.check(
        "18e the escalation report says plainly that the row was never judged",
        "This is not a finding about the row" in transport_report
        and "equivalent draft" not in transport_report,
        "The escalation report is what a human reads days later. Sending them "
        "to a GDD section over a network error wastes the one thing "
        "escalation buys.",
    )

    # ------------------------------------------------------------------
    print("")
    print("[19] Breaker regression rule and the --max-attempts override")
    # ------------------------------------------------------------------
    regressed = ItemBreakerState(
        key="regressed",
        attempts=1,
        history=[
            frozenset({"R1_SALT_MISMATCH"}),
            frozenset({"R1_SALT_MISMATCH", "R2_RR_THRESHOLD_BAND"}),
        ],
    )
    regression_trip, regression_reason = should_trip(regressed)
    r.check(
        "19a a correction that adds violations trips the regression rule",
        regression_trip and "regression" in regression_reason,
        "TRIP_ON_REGRESSION is the one breaker policy with no coverage "
        "anywhere else in this suite: a refine that broke more than it fixed "
        "must stop the loop rather than compound the damage. Got trip="
        f"{regression_trip}, reason={regression_reason!r}",
    )

    # The CLI budget override rebinds a module-level constant that `should_trip`
    # reads at call time. Restored in the `finally` so no later case inherits it.
    from .__main__ import apply_max_attempts_override, main as cli_main

    original_budget = breaker_policy.MAX_REFINE_ATTEMPTS
    try:
        apply_max_attempts_override(1)
        budget_state = ItemBreakerState(
            key="budget", attempts=1, history=[frozenset({"R1_SALT_MISMATCH"})]
        )
        budget_trip, budget_reason = should_trip(budget_state)
        r.check(
            "19b --max-attempts reaches the breaker, not just the parser",
            breaker_policy.MAX_REFINE_ATTEMPTS == 1
            and budget_trip
            and "attempt budget" in budget_reason,
            "An item at 1 refine attempt must trip once the budget is 1. If "
            "the override only changed a local variable, the breaker would "
            f"still be using {original_budget}. Got trip={budget_trip}, "
            f"reason={budget_reason!r}",
        )
    finally:
        apply_max_attempts_override(original_budget)
    # stderr is captured rather than let through: the CLI's refusal message is
    # correct behaviour here, and printing it unbuffered puts the word "Error"
    # at the top of an otherwise all-green self-test run.
    rejected_stderr = io.StringIO()
    with contextlib.redirect_stderr(rejected_stderr):
        rejected_exit = cli_main(["--max-attempts", "0"])
    r.check(
        "19c a budget of zero is rejected before anything runs",
        rejected_exit == 2 and "at least 1" in rejected_stderr.getvalue(),
        "A budget of 0 would escalate every item without attempting a single "
        "correction, so the CLI refuses it with an explanation rather than "
        f"producing a run whose escalations mean nothing. Exit {rejected_exit}, "
        f"stderr {rejected_stderr.getvalue()!r}",
    )

    # Found by deliberately breaking case 24a to check it failed loudly: it did
    # not. Its failure message contained an arrow, the console here is cp1252,
    # cp1252 has no U+2192, and printing the message raised UnicodeEncodeError —
    # so the run died with a codec error and never printed the finding or the
    # summary. Every rule name and GDD quotation in this project carries em
    # dashes, middots, ellipses or arrows, so this reaches far past one message.
    arrow_stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    try:
        arrow_stream.write("240 → 120")
        arrow_stream.flush()
        raised_before = False
    except UnicodeEncodeError:
        raised_before = True
    arrow_stream.reconfigure(errors="replace")
    try:
        arrow_stream.write("240 → 120")
        arrow_stream.flush()
        raised_after = False
    except UnicodeEncodeError:
        raised_after = True
    r.check(
        "19d an unencodable character degrades instead of killing the report",
        raised_before and not raised_after,
        "`_make_console_printable` sets errors='replace' on stdout and stderr "
        "before anything runs, so a check that fails still gets to say why on a "
        "console that cannot render the characters in its message. Losing one "
        "glyph is a cosmetic problem; losing the failure report is the whole "
        f"report. Raised before={raised_before}, after={raised_after}.",
    )

    # ------------------------------------------------------------------
    print("")
    print("[20] JSON extraction — the live path's first point of failure")
    # ------------------------------------------------------------------
    # Unreachable from --offline: a fixture returns objects, never text. Every
    # live reply goes through this function first, so a bug here fails the live
    # run on its very first call and nothing offline would have noticed.
    r.check(
        "20a a fenced code block yields the object",
        extract_json_object('```json\n{"a": 1}\n```') == {"a": 1},
        "Models routinely wrap JSON in a markdown fence despite being told not "
        "to.",
    )
    r.check(
        "20b prose before and after the object is ignored",
        extract_json_object('Here is the row:\n{"a": 1}\nHope that helps!')
        == {"a": 1},
        "A closing remark after valid JSON must not cost the run an attempt.",
    )
    r.check(
        "20c a brace inside a string does not end the scan early",
        extract_json_object('{"note": "a { brace", "b": 2}')
        == {"note": "a { brace", "b": 2},
        "AuthoringNote is free text a model can put anything in, including a "
        "brace.",
    )
    r.check(
        "20d an escaped quote inside a string is honoured",
        extract_json_object('{"note": "she said \\"ok\\"", "b": 2}')
        == {"note": 'she said "ok"', "b": 2},
        "Backslash escapes must not be mistaken for the end of the string.",
    )
    r.check(
        "20e nested objects return the outermost one",
        extract_json_object('{"row": {"Name": "Casualty_X"}}')
        == {"row": {"Name": "Casualty_X"}},
        "The item shape is two nested objects; stopping at the first closing "
        "brace would truncate it.",
    )
    r.check(
        "20f a reply with no JSON raises GenerationError",
        _raises_generation_error(lambda: extract_json_object("I cannot do that.")),
        "A refusal or a prose-only reply must become a retryable finding, not "
        "a crash.",
    )
    r.check(
        "20g a truncated object raises GenerationError",
        _raises_generation_error(
            lambda: extract_json_object('{"row": {"Name": "Casualty_X"')
        ),
        "Hitting the token limit mid-object is the most likely live failure of "
        "all, and it must be retryable rather than fatal.",
    )

    # ------------------------------------------------------------------
    print("")
    print("[21] CSV cell rendering")
    # ------------------------------------------------------------------
    # In Python a bool IS an int, so an ordering mistake in _csv_cell writes
    # `bApplyInitialVitalsOverride` as 1/0 instead of true/false. Unreal's
    # importer reads the column as a bool and the row's whole vitals gate turns
    # on it, which makes this a one-line change with a silent, large blast
    # radius.
    r.check(
        "21a booleans render as Unreal's lowercase true/false",
        _csv_cell(True) == "true" and _csv_cell(False) == "false",
        "The exemplar CSV writes `true`. Got "
        f"{_csv_cell(True)!r} / {_csv_cell(False)!r}.",
    )
    r.check(
        "21b the bool branch is checked before the numeric one",
        _csv_cell(False) != "0" and _csv_cell(True) != "1",
        "bool is a subclass of int in Python, so a float/int branch placed "
        "first swallows every boolean column silently.",
    )
    r.check(
        "21c whole floats lose the trailing .0 and decimals survive",
        _csv_cell(120.0) == "120" and _csv_cell(97.4) == "97.4",
        "Both parse identically as floats on import; what matters is that no "
        f"value renders in scientific notation. Got {_csv_cell(120.0)!r} / "
        f"{_csv_cell(97.4)!r}.",
    )
    r.check(
        "21d strings pass through untouched",
        _csv_cell("/Game/GoldenHour/Characters/CasualtyT1/Casualty_01")
        == "/Game/GoldenHour/Characters/CasualtyT1/Casualty_01",
        "Asset paths and site tags must reach the CSV exactly as authored.",
    )

    # ------------------------------------------------------------------
    print("")
    print("[22] End to end: an escalated row never reaches the CSV")
    # ------------------------------------------------------------------
    # The central safety claim of this submission, and it was resting on
    # inspection of one committed artifact. Driven here through the real
    # `run_requests`, into a temporary directory, with one item that passes and
    # one the refiner cannot fix.
    print("      (the progress lines below are a real run, into a temp directory)")
    with tempfile.TemporaryDirectory() as tmp:
        exclusion_dir = Path(tmp)
        exclusion_run = run_requests(
            (_CLEAN_REQUEST, _UNFIXABLE_REQUEST),
            generator=_ScriptedGenerator(),
            refiner=_EchoRefiner(),
            mode="selftest",
            model="selftest-fixture",
            output_dir=exclusion_dir,
        )
        csv_text = (
            exclusion_dir / "DT_CasualtyArchetypes.generated.csv"
        ).read_text(encoding="utf-8")
        notes_text = (
            exclusion_dir / "DT_CasualtyArchetypes.generated.notes.md"
        ).read_text(encoding="utf-8")
        escalation_exists = (
            exclusion_dir / "escalations" / f"{_UNFIXABLE_REQUEST.key}.md"
        ).is_file()

    r.check(
        "22a the accepted row is in the CSV",
        "Casualty_Selftest_Clean" in csv_text,
        f"A passing item must ship. CSV:\n{csv_text}",
    )
    r.check(
        "22b the escalated row is NOT in the CSV",
        "Casualty_Selftest_Unfixable" not in csv_text,
        "A row the pipeline knows is incoherent is worse than a missing row: "
        "it imports cleanly, looks plausible, and silently supplies the wrong "
        f"ground truth to scoring. CSV:\n{csv_text}",
    )
    r.check(
        "22c the escalation report was written instead",
        escalation_exists and exclusion_run.escalated,
        "Withholding the row is only half the job; the decision has to reach a "
        f"human. Escalated: {[o.request.key for o in exclusion_run.escalated]}",
    )
    r.check(
        "22d the sibling notes file carries the placeholder labelling",
        "Casualty_Selftest_Clean" in notes_text
        and "SME validation pending" in notes_text
        and "Casualty_Selftest_Unfixable" in notes_text
        and "refused to ship" in notes_text,
        "AuthoringNote is not one of the 24 CSV columns, so the label R3 "
        "enforces only survives into the artifact if the sibling notes file "
        "carries it — and the file must also name what was held back.",
    )

    # 22e/22f exist because the shipped notes file asserted "Three things below
    # are not columns of the 24-column CSV" while `TriageIntent` had five, two
    # of which the same block rendered on every row. The count is now derived,
    # so these two guard the derivation rather than the sentence: 22e catches a
    # number typed back in by hand, 22f catches a field added to the model with
    # no documented reason behind it. The real count is recomputed here from the
    # model rather than imported, so a bug in the derivation itself fails too.
    real_non_columns = tuple(
        name for name in TriageIntent.model_fields if name not in CSV_COLUMNS
    )
    # Transcribed independently of `orchestrate._COUNT_WORDS`: a test that reads
    # the number back through the same table it was written with proves nothing.
    word_to_int = {
        "zero": 0,
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
    }
    stated_match = re.search(
        r"\. ([A-Za-z]+) things below are \*\*not columns of the "
        r"(\d+)-column CSV\*\*",
        notes_text,
    )
    stated_count = (
        word_to_int.get(stated_match.group(1).casefold()) if stated_match else None
    )
    stated_columns = int(stated_match.group(2)) if stated_match else None
    matched_sentence = stated_match.group(0) if stated_match else "(no match)"
    r.check(
        "22e the notes file's stated non-column count matches the schema",
        stated_count == len(real_non_columns)
        and stated_columns == len(CSV_COLUMNS),
        "The sentence must be derived from `TriageIntent` minus `CSV_COLUMNS`, "
        f"not typed. Model says {len(real_non_columns)} "
        f"({', '.join(real_non_columns)}) across {len(CSV_COLUMNS)} columns; "
        f"the artifact says {stated_count} across {stated_columns} — "
        f"{matched_sentence!r}.",
    )

    listed_block = notes_text.partition("live here instead")[2].partition(
        "## Placeholder-labelling status"
    )[0]
    listed_items = re.findall(r"^(\d+)\. ", listed_block, flags=re.MULTILINE)
    r.check(
        "22f every non-column field is listed with a documented reason",
        len(listed_items) == len(real_non_columns)
        and listed_items == [str(n + 1) for n in range(len(real_non_columns))]
        and "**undocumented**" not in listed_block,
        "A field added to `TriageIntent` must arrive with the reason it is not "
        "a CSV column, or this file starts describing a shape it no longer "
        f"has. Model has {len(real_non_columns)} non-column field(s) "
        f"({', '.join(real_non_columns)}); the artifact lists "
        f"{len(listed_items)} item(s) {listed_items} and "
        f"{'contains' if '**undocumented**' in listed_block else 'contains no'}"
        " undocumented entry.",
    )

    # ------------------------------------------------------------------
    print("")
    print("[23] End to end: the run-level breaker stops a bad run")
    # ------------------------------------------------------------------
    # `RunBreaker` was unit-tested in isolation but unreachable in practice:
    # with the seven shipped fixtures the worst case is 1 escalation in 7, and
    # no CLI flag can move that. This drives three requests that all escalate,
    # with the item budget lowered through the same override the CLI uses, and
    # proves the run actually stops rather than grinding through the rest.
    print("      (the abort banner below is the expected result of this section)")
    run_budget = breaker_policy.MAX_REFINE_ATTEMPTS
    try:
        apply_max_attempts_override(1)
        with tempfile.TemporaryDirectory() as tmp:
            abort_dir = Path(tmp)
            abort_run = run_requests(
                _ABORT_REQUESTS,
                generator=_ScriptedGenerator(),
                refiner=_ShufflingRefiner(),
                mode="selftest",
                model="selftest-fixture",
                output_dir=abort_dir,
            )
            abort_csv = (
                abort_dir / "DT_CasualtyArchetypes.generated.csv"
            ).read_text(encoding="utf-8")
    finally:
        apply_max_attempts_override(run_budget)

    r.check(
        "23a the run aborts once a majority of completed items have escalated",
        abort_run.aborted and "run aborted" in abort_run.abort_reason.lower(),
        "A majority escalating is a prompt, model or rule problem — more "
        f"retries will not fix it. Aborted={abort_run.aborted}, reason="
        f"{abort_run.abort_reason!r}",
    )
    r.check(
        "23b it stops early instead of finishing the request list",
        len(abort_run.outcomes) == 2 and abort_run.requested == 3,
        "Stopping is the whole point; a breaker that lets the run finish is a "
        f"log message. Processed {len(abort_run.outcomes)} of "
        f"{abort_run.requested}.",
    )
    r.check(
        "23c every item tripped on the overridden attempt budget",
        all(
            "attempt budget" in outcome.trip_reason
            for outcome in abort_run.escalated
        ),
        "This also proves the --max-attempts override reaches the breaker in a "
        "real run, not just in a unit check. Reasons: "
        f"{[o.trip_reason for o in abort_run.escalated]}",
    )
    r.check(
        "23d an aborted run ships no rows at all",
        abort_csv.strip().splitlines() == [",".join(CSV_COLUMNS)],
        "Every item escalated, so the CSV must be a header and nothing else — "
        "the `finally` still writes it, and writing a header-only file is the "
        f"honest output. Got:\n{abort_csv}",
    )

    # ------------------------------------------------------------------
    print("")
    print("[24] The generator prompt does not contain the SALT rule")
    # ------------------------------------------------------------------
    # This submission's central design claim — README § "The one design choice
    # that makes this pipeline produce evidence" — had no guard at all: it was a
    # comment in prompts.py and the author's word. One added citation in the
    # field-group excerpt sliced out of the schema document, or one helpful edit
    # to a brief, silently turns the graded evidence into an empty log: the
    # exact Assignment #4 failure this pipeline was built to avoid, visible only
    # on the live path, and announcing itself as everything passing first time.
    #
    # All seven prompts are checked, not just the first. Six of the seven differ
    # only by their brief, and a brief is the likeliest place for the rule to
    # creep back in — someone "clarifying" what makes a casualty Red.
    gen_prompts = {
        request.key: build_generator_prompt(request).casefold()
        for request in REQUESTS
    }
    # Fingerprints of the decision tree, the derivation table and the R1 rule —
    # not of the vocabulary. Two of them are deliberately narrower than they
    # look, and must stay that way:
    #   * "ground-truth category derivation" is the full § Formulas heading,
    #     because a bare "ground-truth" appears legitimately in the excerpt's
    #     "Group 6 — Expression bands (ground-truth hard-override thresholds)".
    #   * "survivable_with_resources" is the snake_case SALT *input* name, not
    #     the PascalCase `bSurvivableWithResources` column the generator is
    #     required to author and which therefore must appear in the prompt.
    salt_fingerprints = (
        "derive_salt_category",
        "ground-truth category derivation",
        "core rule 2",
        "obeys commands or shows purposeful movement",
        "peripheral pulse present",
        "not in respiratory distress",
        "major hemorrhage controlled",
        "survivable_with_resources",
        "r1_salt_mismatch",
    )
    leaked_rule = sorted(
        f"{key}: {fingerprint!r}"
        for key, prompt in gen_prompts.items()
        for fingerprint in salt_fingerprints
        if fingerprint in prompt
    )
    r.check(
        "24a the generator prompt contains no SALT decision-tree fingerprint",
        not leaked_rule,
        "The generator must author from the clinical brief, not from the rule "
        "it is being graded against. If it sees the rule it self-censors, "
        "every item passes, and ger_log.md becomes the empty evidence file "
        f"Assignment #4 produced. Leaked: {leaked_rule}",
    )

    # 24a is satisfied by an empty string, so it is worth nothing on its own.
    briefs_missing = [
        request.key
        for request in REQUESTS
        if request.brief.casefold()[:60] not in gen_prompts[request.key]
    ]
    # Lower-cased because the prompts above are casefolded — the field name is
    # `bApplyInitialVitalsOverride` in the source document and would never match.
    schema_missing = [
        key
        for key, prompt in gen_prompts.items()
        if "bapplyinitialvitalsoverride" not in prompt
    ]
    r.check(
        "24b the generator prompt still carries the brief and the schema",
        not briefs_missing and not schema_missing,
        "24a must not be satisfiable by an empty prompt. Briefs missing from "
        f"their prompt: {briefs_missing}. Prompts missing the field spec: "
        f"{schema_missing}.",
    )

    # ------------------------------------------------------------------
    print("")
    print("=" * 72)
    total = r.passed + len(r.failed)
    if r.failed:
        print(f"SELF-TEST FAILED — {r.passed}/{total} cases passed")
        print("")
        for failure in r.failed:
            print(f"  - {failure}")
        return 1
    print(f"SELF-TEST PASSED — {r.passed}/{total} cases passed")
    return 0
