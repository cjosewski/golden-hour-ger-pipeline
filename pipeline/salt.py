"""The GDD rule, as pure functions. ZERO LLM involvement in this module.

This is the rule the pipeline exists to enforce. It is a transcription of
`knowledge_base/triage-system.md`, specifically:

  * § Detailed Design → Core Rules → rule 2 (the individual-assessment
    decision sequence), and
  * § Formulas → Ground-Truth Category Derivation (the variable table, the
    worked example, and the `survivable_with_resources` edge case).

Every branch below carries the GDD line it implements. Nothing here infers a
value the GDD says must be authored, and nothing here is tuned — the numeric
cut points all come off the row itself, per `triage-system.md` Acceptance
Criteria: "No hardcoded values in implementation — RR threshold, cap-refill
threshold, and time targets are data-driven per this document's Tuning Knobs
table."

Why the pipeline needs this at all
----------------------------------
`triage-system.md` § Summary: "Every casualty carries a **ground-truth triage
category** derived live from their Pulse physiology state — not a static,
author-placed tag". A CSV row cannot carry a category column, so an author's
belief about what a casualty "is" only exists in their head — until it silently
disagrees with the vitals they typed, and `scoring-and-debrief.md` grades a
trainee against the wrong answer.

Deriving the seven SALT inputs from a row
-----------------------------------------
`derive_salt_category` takes booleans. A `DT_CasualtyArchetypes` row carries
numbers. `derive_inputs_from_row` is the bridge, and every mapping in it is
justified:

+----------------------------------+---------------------------------------------+--------------------------------------------------------------+
| SALT input                       | Derivation                                  | Justification                                                |
+==================================+=============================================+==============================================================+
| ``breathing``                    | ``InitialRespirationRateBpm > 0``           | `triage-system.md` § Formulas variable table: breathing is   |
|                                  |                                             | sourced from "respiration rate > 0 after airway-opened       |
|                                  |                                             | check".                                                      |
+----------------------------------+---------------------------------------------+--------------------------------------------------------------+
| ``respiratory_distress``         | ``InitialRespirationRateBpm >``             | `triage-system.md` § Tuning Knobs sets the RR "Red"          |
|                                  | ``RespirationRateDistressThresholdBpm``     | threshold at 30 bpm (safe range 25–35); the row carries its  |
|                                  |                                             | own copy of that threshold per `casualty-archetype-          |
|                                  |                                             | schema.md` § Group 5, whose stated purpose is "above this,   |
|                                  |                                             | Check-Breathing's finding reads 'rapid/distress'".           |
+----------------------------------+---------------------------------------------+--------------------------------------------------------------+
| ``peripheral_pulse_present``     | ``InitialSystolicBP >=``                    | `casualty-archetype-schema.md` § Group 5:                    |
|                                  | ``PulseQualityAbsentThresholdSystolicBP``   | "Below this systolic BP, quality reads 'absent' (not         |
|                                  |                                             | palpable)." Absent radial pulse is SALT question (b) false.  |
+----------------------------------+---------------------------------------------+--------------------------------------------------------------+
| ``obeys_commands_or_``           | ``InitialConsciousness01 >=``               | `casualty-archetype-schema.md` § Group 6: below the Altered  |
| ``purposeful_movement``          | ``ConsciousnessAlteredThreshold01``         | threshold the pipeline "selects the 'Weak' expression state" |
|                                  |                                             | and below Unconscious it "forces the Unconscious expression  |
|                                  |                                             | state" — neither reliably follows a command, so question (a) |
|                                  |                                             | is false at or below Altered.                                |
+----------------------------------+---------------------------------------------+--------------------------------------------------------------+
| ``hemorrhage_controlled``        | ``HemorrhageInsultMagnitude01 <= 0.0``      | A row describes the casualty **at spawn**, before any        |
|                                  |                                             | intervention exists. `treatment-interventions.md`            |
|                                  |                                             | § Acceptance Criteria: hemorrhage_controlled "becomes true"  |
|                                  |                                             | only WHEN "the trainee successfully applies a tourniquet".   |
|                                  |                                             | So an authored hemorrhage insult means uncontrolled bleeding.|
+----------------------------------+---------------------------------------------+--------------------------------------------------------------+
| ``survivable_with_resources``    | ``intent.bSurvivableWithResources``         | Authored, never inferred. `triage-system.md` § Formulas      |
|                                  |                                             | Edge case: "Do not hardcode this as always-true".            |
+----------------------------------+---------------------------------------------+--------------------------------------------------------------+
| ``minor_injuries_only``          | ``intent.bMinorInjuriesOnly``               | Authored. `triage-system.md` § Formulas variable table       |
|                                  |                                             | sources it from the "Casualty Model injury loadout", which   |
|                                  |                                             | no column on this row represents.                            |
+----------------------------------+---------------------------------------------+--------------------------------------------------------------+
"""

from __future__ import annotations

from dataclasses import dataclass

from .schema import ArchetypeRow, SaltCategory, TriageIntent


@dataclass(frozen=True)
class SaltInputs:
    """The seven booleans `derive_salt_category` consumes.

    Frozen because these are a snapshot of one casualty at spawn — recomputing
    them is the caller's job (the live game recomputes continuously per
    `triage-system.md` Core Rule 4); mutating them in place would hide which
    reading a verdict was based on.
    """

    breathing: bool
    obeys_commands_or_purposeful_movement: bool
    peripheral_pulse_present: bool
    respiratory_distress: bool
    hemorrhage_controlled: bool
    survivable_with_resources: bool
    minor_injuries_only: bool


def derive_salt_category(
    *,
    breathing: bool,
    obeys_commands_or_purposeful_movement: bool,
    peripheral_pulse_present: bool,
    respiratory_distress: bool,
    hemorrhage_controlled: bool,
    survivable_with_resources: bool,
    minor_injuries_only: bool,
) -> SaltCategory:
    """Return the ground-truth SALT category for one casualty.

    Keyword-only on purpose: seven positional booleans would be trivially
    transposable at a call site, and a silently transposed pair here produces a
    plausible-looking wrong answer — exactly the failure mode this whole
    pipeline exists to prevent.
    """

    # Core Rule 2.2 — "Breathing check after airway opened: if the casualty is
    # not breathing even after airway repositioning, category = Dead (Black).
    # Stop." The word "Stop" is why this returns before anything else is
    # considered: no other question is asked of a casualty who is not breathing.
    if not breathing:
        return SaltCategory.BLACK

    # Core Rule 2.3 — "If breathing, the trainee (via examine verbs) checks four
    # things: (a) obeys commands or shows purposeful movement, (b) peripheral
    # pulse present, (c) not in respiratory distress, (d) major hemorrhage
    # controlled."
    q_a = obeys_commands_or_purposeful_movement
    q_b = peripheral_pulse_present
    # NOTE THE INVERSION. The parameter is `respiratory_distress`, but SALT
    # question (c) asks the opposite. § Formulas variable table, row
    # `respiratory_distress`: "SALT question (c) — inverted in the formula
    # (question asks 'NOT in distress')". Getting this backwards would grade a
    # tachypneic casualty as Yellow, which is the single most dangerous
    # transcription error available in this function.
    q_c = not respiratory_distress
    q_d = hemorrhage_controlled

    if q_a and q_b and q_c and q_d:
        # Core Rule 2.4 — "All four true → check for minor-injuries-only: if
        # yes, category = Minimal (Green); if no (injured but stable), category
        # = Delayed (Yellow)."
        return SaltCategory.GREEN if minor_injuries_only else SaltCategory.YELLOW

    # Core Rule 2.5 — "Any of the four false → apply the resource-availability
    # check ... likely to survive given currently available resources? If yes,
    # category = Immediate (Red); if no, category = Expectant (Gray)."
    return SaltCategory.RED if survivable_with_resources else SaltCategory.GRAY


def derive_inputs_from_row(row: ArchetypeRow, intent: TriageIntent) -> SaltInputs:
    """Bridge a `DT_CasualtyArchetypes` row + its authoring intent to SALT inputs.

    See the module docstring's derivation table for the justification of each
    line. The row's own threshold columns are used rather than any constant in
    this file, per `triage-system.md` § Acceptance Criteria ("No hardcoded
    values in implementation").

    **This output is only meaningful when `row.bApplyInitialVitalsOverride` is
    true.** Four of the five inputs computed here read the row's `Initial*`
    vitals, and `casualty-archetype-schema.md` § Group 1 makes that flag the
    gate over all five: "when true, the five `Initial*` fields below are applied
    over the patient file's own baseline at spawn; when false, the patient
    file's built-in baseline stands untouched." With the gate off these numbers
    never reach the casualty, so the booleans below describe nobody. This
    function does not check the gate itself — it is a pure derivation, and the
    caller owns the question of whether the inputs are worth deriving.
    `evaluator.py` checks it first and raises `R1_VITALS_GATE_OFF` instead of
    trusting this result.
    """

    # § Formulas variable table: breathing ← "respiration rate > 0 after
    # airway-opened check".
    breathing = row.InitialRespirationRateBpm > 0.0

    # § Tuning Knobs "Respiratory rate 'Red' threshold (RR) | 30 breaths/min",
    # operationalized per-row via Group 5's RespirationRateDistressThresholdBpm.
    respiratory_distress = (
        row.InitialRespirationRateBpm > row.RespirationRateDistressThresholdBpm
    )

    # casualty-archetype-schema.md § Group 5 — at or below the Absent cut point
    # the radial pulse "reads 'absent' (not palpable)", i.e. question (b) false.
    peripheral_pulse_present = (
        row.InitialSystolicBP >= row.PulseQualityAbsentThresholdSystolicBP
    )

    # casualty-archetype-schema.md § Group 6 — below the Altered threshold the
    # casualty is Weak or Unconscious and cannot reliably obey a command.
    obeys_commands_or_purposeful_movement = (
        intent.InitialConsciousness01 >= row.ConsciousnessAlteredThreshold01
    )

    # treatment-interventions.md § Acceptance Criteria — control is a state that
    # an intervention *achieves*; at spawn no intervention has been applied, so
    # any authored insult magnitude means the bleed is uncontrolled.
    hemorrhage_controlled = row.HemorrhageInsultMagnitude01 <= 0.0

    return SaltInputs(
        breathing=breathing,
        obeys_commands_or_purposeful_movement=obeys_commands_or_purposeful_movement,
        peripheral_pulse_present=peripheral_pulse_present,
        respiratory_distress=respiratory_distress,
        hemorrhage_controlled=hemorrhage_controlled,
        # Authored, per the GDD's explicit instruction not to infer these.
        survivable_with_resources=intent.bSurvivableWithResources,
        minor_injuries_only=intent.bMinorInjuriesOnly,
    )


def failing_salt_questions(inputs: SaltInputs) -> list[str]:
    """Name which of the four SALT questions resolved false.

    Used by the evaluator to explain a mismatch without handing over the answer:
    the refiner is told *which question* the row's own numbers fail, not what
    category to write. See `prompts.py` for why that separation matters.
    """
    failed: list[str] = []
    if not inputs.obeys_commands_or_purposeful_movement:
        failed.append("(a) obeys commands or shows purposeful movement")
    if not inputs.peripheral_pulse_present:
        failed.append("(b) peripheral pulse present")
    if inputs.respiratory_distress:
        # Reported in the GDD's own phrasing — the question is "not in distress",
        # so distress present is the question resolving false.
        failed.append("(c) not in respiratory distress")
    if not inputs.hemorrhage_controlled:
        failed.append("(d) major hemorrhage controlled")
    return failed
