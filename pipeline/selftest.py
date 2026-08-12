"""Offline self-test. No API key, no network.

Sixteen numbered sections covering the SALT derivation, the evaluator's rule
families, the circuit breaker, the knowledge-base loaders, the CSV contract and
the GER loop's recovery from a failed role call. Run with:

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
"""

from __future__ import annotations

import csv
from pathlib import Path

from .breaker import (
    MAX_REFINE_ATTEMPTS,
    RUN_ABORT_ESCALATION_RATIO,
    ItemBreakerState,
    RunBreaker,
    should_trip,
)
from .evaluator import _derived_sentence, evaluate, redact_derived_category
from .generator import GenerationError, PLACEHOLDER_LABEL, exemplar_shaped_row
from .orchestrate import run_item
from .prompts import (
    build_refiner_prompt,
    load_exemplar_csv_text,
    load_exemplar_row_names,
    load_field_group_excerpt,
)
from .requests import ArchetypeRequest
from .schema import (
    CSV_COLUMNS,
    GeneratedArchetype,
    SaltCategory,
    TriageIntent,
    Violation,
)
from .salt import derive_salt_category

EXEMPLAR_CSV = Path(__file__).resolve().parent.parent / (
    "knowledge_base/DT_CasualtyArchetypes.exemplar.csv"
)

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
        "7 unlabelled authoring note raises R3_MISSING_PLACEHOLDER_LABEL",
        "R3_MISSING_PLACEHOLDER_LABEL" in unlabelled_result.codes,
        "casualty-archetype-schema.md requires the 'clinically plausible "
        "placeholder - SME validation pending' label wherever an invented "
        f"clinical value is surfaced. Codes raised: {sorted(unlabelled_result.codes)}",
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
    unhealthy.record(escalated=True)
    unhealthy.record(escalated=True)
    unhealthy.record(escalated=False)
    abort, abort_reason = unhealthy.should_abort_run()
    r.check(
        "10b escalation ratio above tolerance aborts the run",
        abort and "run aborted" in abort_reason.lower(),
        f"2 of 3 escalated is {2 / 3:.0%}, above the "
        f"{RUN_ABORT_ESCALATION_RATIO:.0%} tolerance. Got abort={abort}, "
        f"reason={abort_reason!r}",
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
        "15 CSV_COLUMNS equals the exemplar CSV header exactly",
        CSV_COLUMNS == exemplar_header,
        "The generated CSV must carry the exact column names of the real "
        "DT_CasualtyArchetypes source, or Unreal's DataTable importer silently "
        "fails to map them (.claude/rules/data-files.md). "
        f"Model gives {len(CSV_COLUMNS)} columns, exemplar has "
        f"{len(exemplar_header)}. First difference: "
        f"{next((f'{a!r} != {b!r}' for a, b in zip(CSV_COLUMNS, exemplar_header) if a != b), 'none')}",
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
