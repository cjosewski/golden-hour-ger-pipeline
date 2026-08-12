"""The Evaluator role: rules R1..R4, pure Python, ZERO LLM.

The evaluator is deliberately not a model call. The rule it enforces is a
decision tree written down in a GDD — it is decidable, so asking a language
model to judge it would trade a guaranteed answer for a probabilistic one and
lose the ability to cite a line number. Everything here is deterministic and
every violation names the `knowledge_base/` section that authorizes it.

Rule families
-------------
R1  SALT coherence   — the graded rule. A row's declared category must equal
                       the category its own vitals derive.
R2  Tuning-knob bands — authored numbers must sit inside the safe ranges the
                       GDDs publish, and internally-consistent cut points must
                       stay ordered.
R3  Placeholder label — invented clinical values must be labelled as such.
R4  Schema integrity  — names, uniqueness, asset paths, required tags.

A note on ``gdd_source`` honesty
-------------------------------
Most rules here transcribe something a `knowledge_base/` document actually
publishes, and cite the file and section that publishes it. A few do not: the
blood-pressure ordering, the non-negativity checks and the SpO2 range are
physiological invariants that no GDD in this project states, and the row-name
shape and uniqueness come from the exemplar CSV plus Unreal's own DataTable
keying rather than from a design document. Those cite themselves as invariants
instead of borrowing authority from a section that never mentions them — a
citation that implies authority it does not have is worse than no citation.
"""

from __future__ import annotations

import re

from .salt import derive_inputs_from_row, derive_salt_category, failing_salt_questions
from .schema import EvaluationResult, GeneratedArchetype, SaltCategory, Violation

# `triage-system.md` § Tuning Knobs, "Respiratory rate 'Red' threshold (RR)":
# current value 30 breaths/min, safe range 25–35.
RR_DISTRESS_THRESHOLD_BAND = (25.0, 35.0)

# `treatment-interventions.md` § Tuning Knobs, "Tourniquet application pass
# window": current value <=120s, safe range 60–180s. `triage-system.md` § Tuning
# Knobs carries the same knob and the same range.
TOURNIQUET_WINDOW_BAND = (60.0, 180.0)

# `casualty-archetype-schema.md` § Type-restriction notes — every asset
# reference on this row is "typed as a plain `string` holding the asset's
# content path (e.g. `/Game/GoldenHour/Data/Trajectories/...`)". `/Game/` is
# Unreal's content root, so a path that does not start with it is not a content
# path at all.
UNREAL_CONTENT_ROOT = "/Game/"

# Row keys in `DT_CasualtyArchetypes` follow the exemplar's
# `Casualty_IED_LegHemorrhage_T1` shape.
NAME_PATTERN = re.compile(r"^Casualty_[A-Za-z0-9_]+$")

# Characters that cannot appear in a DataTable source cell without forcing the
# writer to quote it. Unreal's CSV importer is tolerant of quoted commas but not
# of embedded newlines, and a quoted multi-line cell is the shape that breaks it.
CSV_UNSAFE_CHARS: tuple[str, ...] = ("\r", "\n", ",", '"')

# The row columns a model writes free text into. `Name` is excluded because
# `R4_BAD_NAME`'s pattern already rejects every character in CSV_UNSAFE_CHARS.
FREE_TEXT_COLUMNS: tuple[str, ...] = (
    "PulsePatientFileName",
    "HemorrhageInsultActionName",
    "HemorrhageSiteTag",
    "HemorrhageCessationActionName",
    "CasualtyCharacterAssetPath",
)

# `casualty-archetype-schema.md` § "Placeholder-labeled clinical values and
# their sources": every value listed there "must carry the 'clinically plausible
# placeholder — SME validation pending' label wherever surfaced". Matching on
# the word "placeholder" alone keeps the check robust to wording drift while
# still failing a note that never mentions provenance at all.
PLACEHOLDER_TOKEN = "placeholder"

# Used as `gdd_source` by the handful of R2 rules that no `knowledge_base/`
# document publishes. `casualty-archetype-schema.md` § Group 1 defines the five
# `Initial*` fields and gives each a default, but states no range, no ordering
# and no sign constraint for them. Rather than cite Group 1 and imply it says
# something it does not, these rules say plainly what they are: invariants of
# the quantity itself, which hold whether or not a GDD ever writes them down.
PHYSIOLOGICAL_INVARIANT = (
    "Physiological invariant — not published by any knowledge_base/ document; "
    "the fields are defined in casualty-archetype-schema.md § Group 1 — "
    "Pulse-reference, which states no range, ordering or sign constraint"
)

# Used as `gdd_source` by the two row-key rules. `casualty-archetype-schema.md`
# § Ruling makes `F_CasualtyArchetypeRow` the DataTable's row type but says
# nothing about row keys: it names no `Casualty_` convention and no uniqueness
# requirement. The real authorities are the one row that already exists and the
# engine's own keying behaviour.
ROW_KEY_AUTHORITY = (
    "DT_CasualtyArchetypes.exemplar.csv — the existing row key "
    "Casualty_IED_LegHemorrhage_T1, plus Unreal's DataTable row keying "
    "(engine behaviour, not a GDD rule)"
)


def _derived_sentence(category: SaltCategory) -> str:
    """The one sentence in an R1 detail that discloses the derived category.

    Isolated as a single, exactly-known sentence so that
    `redact_derived_category` can remove it reliably, instead of trying to
    pattern-match arbitrary prose.
    """
    return (
        f"The category derived from this row's own vitals is {category.value}, "
        "which disagrees with the declaration."
    )


_REDACTED_SENTENCE = (
    "The category derived from this row's own vitals disagrees with the "
    "declaration."
)


def redact_derived_category(detail: str) -> str:
    """Strip the derived-category disclosure out of a violation detail.

    Two audiences read the same violation and must be told different amounts.
    A human reviewing `ger_log.md` or an escalation report needs to see both
    the declared and the derived category to judge the disagreement. The
    Refiner must not: if it is handed the answer, the loop proves only that the
    pipeline can copy a string from the evaluator into the output, and no item
    is ever genuinely unfixable, which makes the circuit breaker unreachable.

    Exact-match replacement over the five possible sentences, because this
    module owns both the sentence that goes in and the sentence that comes out.
    """
    for category in SaltCategory:
        detail = detail.replace(_derived_sentence(category), _REDACTED_SENTENCE)
    return detail


def redact_violations(violations: list[Violation]) -> list[Violation]:
    """Refiner-safe copies of a violation list."""
    return [
        v.model_copy(update={"detail": redact_derived_category(v.detail)})
        for v in violations
    ]


def _band(
    violations: list[Violation],
    *,
    code: str,
    value: float,
    low: float,
    high: float,
    field: str,
    rule: str,
    gdd_source: str,
) -> None:
    """Append a violation if ``value`` falls outside the inclusive band."""
    if not (low <= value <= high):
        violations.append(
            Violation(
                code=code,
                rule=rule,
                gdd_source=gdd_source,
                detail=(
                    f"{field} is {value:g}, outside the documented safe range "
                    f"{low:g}–{high:g}."
                ),
            )
        )


def evaluate(item: GeneratedArchetype, *, seen_names: set[str]) -> EvaluationResult:
    """Check one generated archetype against every rule. Deterministic.

    ``seen_names`` holds the row names already accepted in this run, so
    duplicate keys are caught across items rather than only within one.
    """
    row = item.row
    intent = item.triage_intent
    violations: list[Violation] = []

    # ------------------------------------------------------------------
    # R1 — SALT coherence. The graded rule.
    # ------------------------------------------------------------------
    # The gate comes first. `casualty-archetype-schema.md` § Group 1 defines
    # `bApplyInitialVitalsOverride` as the switch over the five `Initial*`
    # fields: "when true, the five `Initial*` fields below are applied over the
    # patient file's own baseline at spawn; when false, the patient file's
    # built-in baseline stands untouched." Its documented default is `false`.
    #
    # So with the gate off, the authored vitals are not the casualty's spawn
    # state, and deriving a SALT category from them would be deriving ground
    # truth from numbers the row itself says are never applied. Everything that
    # reads those five values is skipped in that case and this rule is raised
    # instead. (The 2026-07-29 addendum to the same document narrows the gate's
    # live semantics further still — with the gate ON, `BP_Casualty` only
    # warn-logs divergence rather than applying the values — which makes the
    # five fields "the authored expectation record". With the gate OFF they are
    # not even that.)
    #
    # R2 still checks these numbers for shape (non-negative, in range, ordered):
    # a malformed value is malformed whether or not it is applied. Only the
    # clinical inference is gated.
    derived: SaltCategory | None = None
    inputs = derive_inputs_from_row(row, intent)

    if not row.bApplyInitialVitalsOverride:
        violations.append(
            Violation(
                code="R1_VITALS_GATE_OFF",
                rule=(
                    "A row's declared SALT category can only be checked against "
                    "its own authored vitals when the row applies those vitals "
                    "at spawn. With the override gate off, the patient file's "
                    "baseline stands and the authored values are inert."
                ),
                gdd_source="casualty-archetype-schema.md § Group 1 — Pulse-reference",
                detail=(
                    "bApplyInitialVitalsOverride is false, which declares this "
                    "row's own five Initial* vitals inert — the Pulse patient "
                    f"file {row.PulsePatientFileName!r} supplies the spawn state "
                    "instead, so the authored HR "
                    f"{row.InitialHeartRateBpm:g}, RR "
                    f"{row.InitialRespirationRateBpm:g}, SpO2 "
                    f"{row.InitialSpO2Percent:g}, BP {row.InitialSystolicBP:g}/"
                    f"{row.InitialDiastolicBP:g} describe no casualty that will "
                    "ever spawn and the declared category "
                    f"{intent.DeclaredCategory.value} rests on nothing. The SALT "
                    "derivation was not run against them."
                ),
            )
        )

    if row.bApplyInitialVitalsOverride:
        derived = derive_salt_category(
            breathing=inputs.breathing,
            obeys_commands_or_purposeful_movement=inputs.obeys_commands_or_purposeful_movement,
            peripheral_pulse_present=inputs.peripheral_pulse_present,
            respiratory_distress=inputs.respiratory_distress,
            hemorrhage_controlled=inputs.hemorrhage_controlled,
            survivable_with_resources=inputs.survivable_with_resources,
            minor_injuries_only=inputs.minor_injuries_only,
        )

    if derived is not None and derived != intent.DeclaredCategory:
        if not inputs.breathing:
            # A non-breathing casualty never reaches the four questions at all
            # (Core Rule 2.2 says "Stop."), so naming failed questions would be
            # misleading. Report the breathing check instead.
            which = (
                "the breathing check resolved false "
                f"(InitialRespirationRateBpm = {row.InitialRespirationRateBpm:g})"
            )
        else:
            failed = failing_salt_questions(inputs)
            if failed:
                which = "these SALT questions resolved false: " + "; ".join(failed)
            else:
                # All four questions true — the split that decided the category
                # was the minor-injuries / survivability authored flag instead.
                which = (
                    "all four SALT questions resolved true, so the category was "
                    "decided by the minor-injuries-only split "
                    f"(bMinorInjuriesOnly = {intent.bMinorInjuriesOnly})"
                )

        violations.append(
            Violation(
                code="R1_SALT_MISMATCH",
                rule=(
                    "A row's declared SALT category must equal the category "
                    "derived from that row's own authored vitals. The "
                    "ground-truth category is derived live from physiology, "
                    "never author-placed."
                ),
                gdd_source=(
                    "triage-system.md § Formulas — Ground-Truth Category Derivation"
                ),
                # States the disagreement and the evidence, but never the fix.
                # The derived category IS named here, because this detail is
                # what a human reads in ger_log.md and in an escalation report,
                # and a reviewer needs to see both sides of the disagreement.
                # It is stripped again by `redact_derived_category` on the way
                # into the refiner prompt — see that function and prompts.py.
                detail=(
                    f"DeclaredCategory is {intent.DeclaredCategory.value}. "
                    f"{_derived_sentence(derived)} Evidence: {which}. "
                    f"Vitals as authored: RR {row.InitialRespirationRateBpm:g} vs "
                    f"distress threshold {row.RespirationRateDistressThresholdBpm:g}; "
                    f"SBP {row.InitialSystolicBP:g} vs pulse-absent threshold "
                    f"{row.PulseQualityAbsentThresholdSystolicBP:g}; consciousness "
                    f"{intent.InitialConsciousness01:g} vs altered threshold "
                    f"{row.ConsciousnessAlteredThreshold01:g}; hemorrhage insult "
                    f"magnitude {row.HemorrhageInsultMagnitude01:g}; "
                    f"bSurvivableWithResources = {intent.bSurvivableWithResources}; "
                    f"bMinorInjuriesOnly = {intent.bMinorInjuriesOnly}."
                ),
            )
        )

    # R1 sub-rule — Black is defined by apnea and nothing else. Gated on the
    # same override switch for the same reason: with the gate off,
    # InitialRespirationRateBpm is not the rate this casualty spawns with, so
    # "a breathing casualty cannot be Black" would be an inference about a
    # number the row declares inert.
    if (
        row.bApplyInitialVitalsOverride
        and intent.DeclaredCategory is SaltCategory.BLACK
        and row.InitialRespirationRateBpm > 0.0
    ):
        violations.append(
            Violation(
                code="R1_BLACK_REQUIRES_APNEA",
                rule=(
                    "Category Black is reached only by the breathing check "
                    "failing after one airway-reposition attempt."
                ),
                gdd_source="triage-system.md § Detailed Design — Core Rules, rule 2.2",
                detail=(
                    f"DeclaredCategory is Black but InitialRespirationRateBpm is "
                    f"{row.InitialRespirationRateBpm:g}; a breathing casualty cannot "
                    "be Black."
                ),
            )
        )

    # R1 sub-rule — a dead casualty declared survivable is incoherent.
    if intent.DeclaredCategory is SaltCategory.BLACK and (
        intent.bSurvivableWithResources or intent.bMinorInjuriesOnly
    ):
        violations.append(
            Violation(
                code="R1_BLACK_CONTRADICTION",
                rule=(
                    "The survivability and minor-injuries flags only decide "
                    "splits reached by a breathing casualty; neither can be true "
                    "for a casualty declared Dead (Black)."
                ),
                gdd_source="triage-system.md § Detailed Design — Core Rules, rule 2",
                detail=(
                    "DeclaredCategory is Black but "
                    f"bSurvivableWithResources = {intent.bSurvivableWithResources} and "
                    f"bMinorInjuriesOnly = {intent.bMinorInjuriesOnly}. The Black "
                    "branch stops before either flag is consulted, so a true value "
                    "here contradicts the declaration."
                ),
            )
        )

    # ------------------------------------------------------------------
    # R2 — tuning-knob band conformance.
    # ------------------------------------------------------------------
    _band(
        violations,
        code="R2_TOURNIQUET_WINDOW_BAND",
        value=row.TourniquetPassWindowSeconds,
        low=TOURNIQUET_WINDOW_BAND[0],
        high=TOURNIQUET_WINDOW_BAND[1],
        field="TourniquetPassWindowSeconds",
        rule="Tourniquet application pass window must stay inside its safe range.",
        gdd_source="treatment-interventions.md § Tuning Knobs",
    )
    _band(
        violations,
        code="R2_RR_THRESHOLD_BAND",
        value=row.RespirationRateDistressThresholdBpm,
        low=RR_DISTRESS_THRESHOLD_BAND[0],
        high=RR_DISTRESS_THRESHOLD_BAND[1],
        field="RespirationRateDistressThresholdBpm",
        rule="Respiratory-rate distress threshold must stay inside its safe range.",
        gdd_source="triage-system.md § Tuning Knobs",
    )

    if row.PulseQualityAbsentThresholdSystolicBP >= row.PulseQualityWeakThresholdSystolicBP:
        violations.append(
            Violation(
                code="R2_PULSE_BAND_ORDER",
                rule=(
                    "The pulse-absent systolic cut point must be strictly below "
                    "the pulse-weak cut point."
                ),
                gdd_source="casualty-archetype-schema.md § Group 5 — Assessment-verb bands",
                detail=(
                    "PulseQualityAbsentThresholdSystolicBP is "
                    f"{row.PulseQualityAbsentThresholdSystolicBP:g} and "
                    "PulseQualityWeakThresholdSystolicBP is "
                    f"{row.PulseQualityWeakThresholdSystolicBP:g}. Quality degrades "
                    "normal → weak → absent as pressure falls, so absent must be the "
                    "lower cut point."
                ),
            )
        )

    if row.ConsciousnessUnconsciousThreshold01 >= row.ConsciousnessAlteredThreshold01:
        violations.append(
            Violation(
                code="R2_CONSCIOUSNESS_BAND_ORDER",
                rule=(
                    "The unconscious consciousness cut point must be strictly "
                    "below the altered cut point."
                ),
                gdd_source="casualty-archetype-schema.md § Group 6 — Expression bands",
                detail=(
                    "ConsciousnessUnconsciousThreshold01 is "
                    f"{row.ConsciousnessUnconsciousThreshold01:g} and "
                    "ConsciousnessAlteredThreshold01 is "
                    f"{row.ConsciousnessAlteredThreshold01:g}. Group 6 defines Altered "
                    "as the band above Unconscious, so Unconscious must be lower."
                ),
            )
        )

    # `casualty-archetype-schema.md` § Group 1 defines InitialSpO2Percent and
    # gives it a default, but publishes no range for it — so this cites the
    # invariant rather than borrowing authority from a section that is silent.
    _band(
        violations,
        code="R2_SPO2_RANGE",
        value=row.InitialSpO2Percent,
        low=0.0,
        high=100.0,
        field="InitialSpO2Percent",
        rule="SpO2 is a percentage and must lie in 0..100.",
        gdd_source=PHYSIOLOGICAL_INVARIANT,
    )

    # Diastolic must sit strictly below systolic — but only where a pulse
    # pressure exists at all. A casualty in arrest has no waveform, and 0/0 is
    # the coherent authoring for the Black archetype `triage-system.md` Core
    # Rule 2.2 describes; flagging it would be a false positive that pushed
    # authors toward inventing a blood pressure for a casualty who has none.
    # A positive diastolic with zero systolic stays a violation: that is a
    # trough without a peak, which is impossible rather than merely absent.
    if row.InitialSystolicBP < 0.0 or row.InitialDiastolicBP < 0.0:
        violations.append(
            Violation(
                code="R2_NEGATIVE_BLOOD_PRESSURE",
                rule=(
                    "Blood pressure cannot be negative; zero is the arrest case "
                    "and is valid."
                ),
                gdd_source=PHYSIOLOGICAL_INVARIANT,
                detail=(
                    f"InitialSystolicBP is {row.InitialSystolicBP:g} and "
                    f"InitialDiastolicBP is {row.InitialDiastolicBP:g}. Pressure "
                    "is measured against atmosphere; below zero is not a low "
                    "reading, it is not a reading at all."
                ),
            )
        )

    if row.InitialSystolicBP <= 0.0:
        if row.InitialDiastolicBP > 0.0:
            violations.append(
                Violation(
                    code="R2_BP_ORDER",
                    rule="Diastolic pressure cannot exist without a systolic pressure.",
                    gdd_source=PHYSIOLOGICAL_INVARIANT,
                    detail=(
                        f"InitialSystolicBP is {row.InitialSystolicBP:g} but "
                        f"InitialDiastolicBP is {row.InitialDiastolicBP:g}. Diastolic "
                        "is the trough of the same pressure waveform whose peak is "
                        "systolic; there cannot be a trough with no peak."
                    ),
                )
            )
    elif row.InitialDiastolicBP >= row.InitialSystolicBP:
        violations.append(
            Violation(
                code="R2_BP_ORDER",
                rule="Diastolic pressure must be strictly below systolic pressure.",
                gdd_source=PHYSIOLOGICAL_INVARIANT,
                detail=(
                    f"InitialDiastolicBP is {row.InitialDiastolicBP:g} and "
                    f"InitialSystolicBP is {row.InitialSystolicBP:g}. Diastolic is the "
                    "trough of the same pressure waveform whose peak is systolic, so "
                    "it cannot meet or exceed it."
                ),
            )
        )

    if row.InitialHeartRateBpm < 0.0:
        violations.append(
            Violation(
                code="R2_NEGATIVE_HEART_RATE",
                rule="Heart rate cannot be negative.",
                gdd_source=PHYSIOLOGICAL_INVARIANT,
                detail=f"InitialHeartRateBpm is {row.InitialHeartRateBpm:g}.",
            )
        )

    if row.InitialRespirationRateBpm < 0.0:
        violations.append(
            Violation(
                code="R2_NEGATIVE_RESPIRATION_RATE",
                rule=(
                    "Respiration rate cannot be negative; zero is the apnea case "
                    "and is valid."
                ),
                gdd_source=PHYSIOLOGICAL_INVARIANT,
                detail=f"InitialRespirationRateBpm is {row.InitialRespirationRateBpm:g}.",
            )
        )

    _band(
        violations,
        code="R2_INSULT_MAGNITUDE_RANGE",
        value=row.HemorrhageInsultMagnitude01,
        low=0.0,
        high=1.0,
        field="HemorrhageInsultMagnitude01",
        rule="Hemorrhage insult magnitude is a normalized 0..1 control input.",
        gdd_source="casualty-archetype-schema.md § Group 1 — Pulse-reference",
    )
    _band(
        violations,
        code="R2_CESSATION_MAGNITUDE_RANGE",
        value=row.HemorrhageCessationMagnitude01,
        low=0.0,
        high=1.0,
        field="HemorrhageCessationMagnitude01",
        rule="Hemorrhage cessation magnitude is a normalized 0..1 control input.",
        gdd_source="casualty-archetype-schema.md § Group 4 — Treatment / secure-event tuning",
    )
    _band(
        violations,
        code="R2_CONSCIOUSNESS_RANGE",
        value=intent.InitialConsciousness01,
        low=0.0,
        high=1.0,
        field="InitialConsciousness01",
        rule="ConsciousnessLevel01 is a normalized 0..1 physiology reading.",
        gdd_source="casualty-archetype-schema.md § Group 6 — Expression bands",
    )

    # ------------------------------------------------------------------
    # R3 — placeholder labelling.
    # ------------------------------------------------------------------
    if PLACEHOLDER_TOKEN not in intent.AuthoringNote.casefold():
        violations.append(
            Violation(
                code="R3_MISSING_PLACEHOLDER_LABEL",
                rule=(
                    "Every clinically-invented value must carry the 'clinically "
                    "plausible placeholder — SME validation pending' label "
                    "wherever it is surfaced, until an acting clinical SME "
                    "reviews it."
                ),
                gdd_source=(
                    "casualty-archetype-schema.md § Placeholder-labeled clinical "
                    "values and their sources"
                ),
                detail=(
                    "AuthoringNote does not mention 'placeholder'. Every vital sign "
                    "and threshold on a generated row is invented rather than "
                    "SME-authored, so the row must say so or a reader will mistake "
                    f"it for validated clinical data. AuthoringNote was: "
                    f"{intent.AuthoringNote!r}"
                ),
            )
        )

    # ------------------------------------------------------------------
    # R4 — schema integrity.
    # ------------------------------------------------------------------
    if row.Name in seen_names:
        violations.append(
            Violation(
                code="R4_DUPLICATE_NAME",
                rule="Every DataTable row key must be unique.",
                gdd_source=ROW_KEY_AUTHORITY,
                detail=(
                    f"Row name {row.Name!r} is already taken — either by a row "
                    "accepted earlier in this run, or by the row already in the "
                    "live table. Unreal keys DataTable rows by Name; a duplicate "
                    "silently overwrites the earlier row on import."
                ),
            )
        )

    if not NAME_PATTERN.match(row.Name):
        violations.append(
            Violation(
                code="R4_BAD_NAME",
                rule=(
                    "Row keys follow the Casualty_<Descriptor> convention "
                    "established by the existing table."
                ),
                gdd_source=ROW_KEY_AUTHORITY,
                detail=(
                    f"Row name {row.Name!r} does not match ^Casualty_[A-Za-z0-9_]+$ "
                    "(the shape of the existing row, Casualty_IED_LegHemorrhage_T1)."
                ),
            )
        )

    if not row.CasualtyCharacterAssetPath.startswith(UNREAL_CONTENT_ROOT):
        violations.append(
            Violation(
                code="R4_BAD_ASSET_PATH",
                rule=(
                    "CasualtyCharacterAssetPath must be an Unreal content path "
                    "rooted at /Game/."
                ),
                # § Group 7 defines this field but defaults it to `""` and names
                # no path root. The section that actually constrains the value is
                # § Type-restriction notes, which says the string holds "the
                # asset's content path (e.g. `/Game/GoldenHour/Data/
                # Trajectories/...`)".
                gdd_source="casualty-archetype-schema.md § Type-restriction notes",
                detail=(
                    f"CasualtyCharacterAssetPath is {row.CasualtyCharacterAssetPath!r}, "
                    f"which is not an Unreal content path (it does not start with "
                    f"{UNREAL_CONTENT_ROOT}). This field is "
                    "'a plain string nothing type-checks, breaking silently and "
                    "surfacing only in a packaged build' "
                    "(casualty-archetype-schema.md § Addendum 2026-07-26, second "
                    "correction), so the path shape is checked here instead. The "
                    "same section names the current fill value: "
                    "/Game/GoldenHour/Characters/CasualtyT1/Casualty_01."
                ),
            )
        )

    if not row.HemorrhageSiteTag.strip():
        violations.append(
            Violation(
                code="R4_EMPTY_SITE_TAG",
                rule="Every row must name the anatomical site of its hemorrhage.",
                gdd_source="casualty-archetype-schema.md § Group 2 — Shared wound descriptor",
                detail=(
                    "HemorrhageSiteTag is blank. Group 2 states this field 'drives "
                    "which limb's wound visual and tourniquet snap volume are active "
                    "on BP_Casualty' — a blank tag leaves the casualty with no wound "
                    "visual and no place to apply a tourniquet."
                ),
            )
        )

    # Free-text columns are the one place a model can put a character that
    # survives schema validation and then breaks the file it is written into.
    # `.claude/rules/data-files.md` notes that "Unreal's CSV importer has no
    # comment syntax — the first row is always literal headers"; it is a plain
    # line-oriented reader, and an embedded newline turns one row into two
    # malformed ones. A comma or a double quote forces the writer to quote and
    # escape the cell, which the importer reads back inconsistently.
    row_values = row.model_dump()
    for column in FREE_TEXT_COLUMNS:
        value = row_values[column]
        found = [char for char in CSV_UNSAFE_CHARS if char in value]
        if found:
            violations.append(
                Violation(
                    code="R4_UNSAFE_CSV_TEXT",
                    rule=(
                        "Free-text row columns must not contain characters that "
                        "change the shape of the CSV: carriage return, newline, "
                        "comma or double quote."
                    ),
                    gdd_source=(
                        "data-files.md § Carve-out: Unreal DataTable source files"
                    ),
                    detail=(
                        f"{column} is {value!r}, which contains "
                        f"{', '.join(repr(char) for char in found)}. Unreal's "
                        "DataTable importer reads the source line by line, so a "
                        "cell like this either splits one casualty across two "
                        "rows or imports with the punctuation swallowed."
                    ),
                )
            )

    return EvaluationResult(
        passed=not violations,
        derived_category=derived,
        violations=violations,
    )
