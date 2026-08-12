"""Pydantic v2 models for the casualty-archetype GER pipeline.

The row model mirrors `F_CasualtyArchetypeRow`, the Unreal struct defined in
`knowledge_base/casualty-archetype-schema.md` (VERB-01 interim decision,
2026-07-24). That decision record's "Build verification" section records the
struct as having **23 authored fields**; the DataTable adds the engine's own
`Name` key column in front of them, which is why the CSV header carries 24
columns and `ArchetypeRow` declares 24 fields.

Field names are deliberately PascalCase Python identifiers rather than the
snake_case a Python project would normally use. `.claude/rules/data-files.md`
in the game repo carves DataTable sources out of the usual key-casing rule and
states the reason: "Column headers must match the row struct's field names
verbatim (PascalCase), or Unreal's importer silently fails to map them." The
model IS the column list, so the names have to round-trip byte-for-byte.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict


class SaltCategory(str, Enum):
    """The five SALT triage categories.

    Source: `knowledge_base/triage-system.md` § Overview — "SALT uses 5
    categories (Immediate/Red, Delayed/Yellow, Minimal/Green, Expectant/Gray,
    Dead/Black)".
    """

    GREEN = "Green"
    YELLOW = "Yellow"
    RED = "Red"
    GRAY = "Gray"
    BLACK = "Black"


class ArchetypeRow(BaseModel):
    """One row of `DT_CasualtyArchetypes`.

    Declaration order IS the CSV column order — see `CSV_COLUMNS` below, which
    is derived from this class rather than typed out a second time, so the two
    cannot drift apart.

    Field groups follow `casualty-archetype-schema.md`:
      * Group 1  — Pulse-reference (live-engine configuration)
      * Group 2  — Shared wound descriptor
      * Group 3  — Baked-trajectory (F2 fallback; empty while PRIMARY is active)
      * Group 4  — Treatment / secure-event tuning
      * Group 5  — Assessment-verb bands
      * Group 6  — Expression bands (consciousness hard-override thresholds)
      * Group 7  — Spawn/visual reference
    """

    # `extra="forbid"` is load-bearing: a generator that invents an extra field
    # would otherwise silently produce a row that no longer matches the struct.
    # Rejecting it here turns the mistake into a retryable validation error.
    model_config = ConfigDict(extra="forbid")

    # DataTable key column (engine-supplied, not one of the struct's 23 fields).
    Name: str

    # Group 1 — Pulse-reference.
    PulsePatientFileName: str
    bApplyInitialVitalsOverride: bool
    InitialHeartRateBpm: float
    InitialRespirationRateBpm: float
    InitialSpO2Percent: float
    InitialSystolicBP: float
    InitialDiastolicBP: float
    HemorrhageInsultActionName: str
    HemorrhageInsultMagnitude01: float

    # Group 2 — Shared wound descriptor.
    HemorrhageSiteTag: str

    # Group 3 — Baked-trajectory. Default empty: these only carry values if the
    # F2 fallback physiology path is ever activated.
    UntreatedTrajectoryAssetPath: str = ""
    TreatedTrajectoryAssetPath: str = ""
    TrajectoryBranchPointSeconds: float = 0.0

    # Group 4 — Treatment / secure-event tuning.
    HemorrhageCessationActionName: str
    HemorrhageCessationMagnitude01: float
    HemorrhageControlledFlowThreshold: float
    TourniquetPassWindowSeconds: float

    # Group 5 — Assessment-verb bands.
    RespirationRateDistressThresholdBpm: float
    PulseQualityWeakThresholdSystolicBP: float
    PulseQualityAbsentThresholdSystolicBP: float

    # Group 6 — Expression bands.
    ConsciousnessAlteredThreshold01: float
    ConsciousnessUnconsciousThreshold01: float

    # Group 7 — Spawn/visual reference.
    CasualtyCharacterAssetPath: str


# The CSV column order, derived from the model so it cannot drift from the
# struct. `selftest.py` case 11 asserts this tuple equals the exemplar CSV's
# header exactly — that assertion is the guard that keeps generated output
# importable into the real DataTable.
CSV_COLUMNS: tuple[str, ...] = tuple(ArchetypeRow.model_fields)


class TriageIntent(BaseModel):
    """The SALT inputs the 24-column CSV cannot carry.

    Every field here exists because `derive_salt_category` needs it and the row
    struct deliberately does not have it:

    * ``DeclaredCategory`` — what the author says this casualty presents as.
      The DataTable has no category column at all, and that is correct:
      `triage-system.md` § Summary states the ground-truth category is "derived
      live from their Pulse physiology state — not a static, author-placed
      tag". The declared category is therefore authoring *intent*, checked
      against the derivation, never shipped as data.

    * ``InitialConsciousness01`` — 0..1 consciousness level.
      `casualty-archetype-schema.md` § Group 1 excludes this from the row on
      purpose: "``ConsciousnessLevel01`` and ``PainLevel01`` are deliberately
      **not** carried as initial-override fields ... both are physiology
      *outputs* of the pipeline ... rather than archetype-authored inputs".
      Carried here as authoring intent only, so the pipeline can reason about
      SALT question (a) without misrepresenting an output as authored config.

    * ``bMinorInjuriesOnly`` — the Green-vs-Yellow split.
      `triage-system.md` Core Rule 2.4: all four true → "check for
      minor-injuries-only: if yes, category = Minimal (Green); if no (injured
      but stable), category = Delayed (Yellow)".

    * ``bSurvivableWithResources`` — the Red-vs-Gray split.
      `triage-system.md` § Formulas flags this **[To be designed]** and states
      plainly: "Do not hardcode this as always-true; it needs an explicit design
      decision before the Expectant category can be authored honestly." So it is
      authored per row and never inferred by this pipeline.

    * ``AuthoringNote`` — provenance / placeholder labelling.
      `casualty-archetype-schema.md` § "Placeholder-labeled clinical values and
      their sources" requires every invented clinical value to carry the
      "clinically plausible placeholder — SME validation pending" label
      "wherever surfaced". Rule R3 enforces that on this field.
    """

    model_config = ConfigDict(extra="forbid")

    DeclaredCategory: SaltCategory
    InitialConsciousness01: float
    bMinorInjuriesOnly: bool
    bSurvivableWithResources: bool
    AuthoringNote: str


class GeneratedArchetype(BaseModel):
    """One complete generated item: the shippable row plus its authoring intent."""

    model_config = ConfigDict(extra="forbid")

    row: ArchetypeRow
    triage_intent: TriageIntent


class Violation(BaseModel):
    """A single rule break found by the evaluator.

    ``gdd_source`` names the file and section in ``knowledge_base/`` that the
    rule comes from, so a human reading an escalation report can go straight to
    the authority rather than taking the pipeline's word for it.
    """

    model_config = ConfigDict(extra="forbid")

    code: str
    rule: str
    gdd_source: str
    detail: str


class EvaluationResult(BaseModel):
    """The verdict on one draft."""

    model_config = ConfigDict(extra="forbid")

    passed: bool
    derived_category: SaltCategory | None
    violations: list[Violation]

    @property
    def codes(self) -> frozenset[str]:
        """The set of violation codes raised, used by the circuit breaker.

        The breaker compares these sets across attempts to detect "no progress"
        — the same rule breaking twice running — so it must be a set, not a
        list: two attempts that raise the same rule in a different order have
        made no progress.
        """
        return frozenset(v.code for v in self.violations)
