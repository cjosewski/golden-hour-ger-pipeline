"""The Refiner role.

* ``LiveRefiner``   — the real pipeline. Sends the failing item plus the
  violation list to Anthropic and parses the revision.
* ``OfflineRefiner`` — a deterministic fixture for CI and graders. It applies
  scripted repairs for the findings it knows how to resolve, and returns a
  semantically-equivalent draft for anything else — which is what makes the
  circuit breaker observable offline.

The refiner never receives the derived category and is never told what value to
write. See the `prompts.py` module docstring for why that separation is load
bearing rather than stylistic.
"""

from __future__ import annotations

from typing import Any

from .generator import PLACEHOLDER_LABEL, _AnthropicRole, parse_item
from .prompts import build_refiner_prompt
from .schema import GeneratedArchetype, Violation


class LiveRefiner(_AnthropicRole):
    """Refiner role backed by Anthropic. This is the real pipeline."""

    def refine(
        self, item: GeneratedArchetype, violations: list[Violation]
    ) -> GeneratedArchetype:
        return parse_item(self._complete(build_refiner_prompt(item, violations)))


# =========================================================================
# Offline harness
# =========================================================================
#
# A fixture, not a model. It stands in for refiner reasoning so the loop can be
# exercised without credentials; nothing about real model behaviour should be
# inferred from it.

# For an R1 SALT mismatch there are two legitimate resolutions — correct the
# declaration, or correct the vitals — and which one is right depends on the
# clinical brief the casualty is meant to portray. A scripted fixture cannot
# read a brief, so the one case where the answer is unambiguous from the brief
# is tabled here explicitly.
#
# `Casualty_Abdominal_Evisceration` is that case. Its brief describes a casualty
# who is "awake and tracking you", "breathing at an ordinary rate", whose "pulse
# is present at the wrist" and who is "not actively pouring blood right now".
# The draft's vitals (RR 34, SBP 68, unresponsive, active bleed) contradict that
# brief, and the declared Yellow matches it. So the vitals are what is wrong,
# and this repair brings them back to the picture the brief describes.
_VITALS_REPAIRS: dict[str, dict[str, Any]] = {
    "Casualty_Abdominal_Evisceration": {
        "row": {
            "InitialHeartRateBpm": 104.0,
            "InitialRespirationRateBpm": 18.0,
            "InitialSpO2Percent": 95.0,
            "InitialSystolicBP": 106.0,
            "InitialDiastolicBP": 66.0,
            "HemorrhageInsultMagnitude01": 0.0,
            # Zeroing the magnitude without clearing the action name would ship
            # a row that fires a bleeding action at zero strength — the kind of
            # half-corrected data that reads as deliberate to the next author.
            "HemorrhageInsultActionName": "None",
        },
        "triage_intent": {
            "InitialConsciousness01": 0.8,
        },
    },
}

# `treatment-interventions.md` § Tuning Knobs current value, and the value the
# existing hand-authored row already uses.
TOURNIQUET_WINDOW_DEFAULT = 120.0

# `casualty-archetype-schema.md` § Addendum 2026-07-26, second correction:
# "Fill path, current and final unless the row's asset changes again: fill
# `CasualtyCharacterAssetPath` with
# `/Game/GoldenHour/Characters/CasualtyT1/Casualty_01`".
CASUALTY_ASSET_PATH_DEFAULT = "/Game/GoldenHour/Characters/CasualtyT1/Casualty_01"


def _rebuild(
    item: GeneratedArchetype,
    row_changes: dict[str, Any],
    intent_changes: dict[str, Any],
) -> GeneratedArchetype:
    """Return a new item with the given field changes applied.

    Round-trips through the models so a repair that produced an invalid value
    fails here rather than silently reaching the evaluator as a malformed row.
    """
    row = item.row.model_dump()
    row.update(row_changes)
    intent = item.triage_intent.model_dump()
    intent.update(intent_changes)
    return GeneratedArchetype.model_validate({"row": row, "triage_intent": intent})


class OfflineRefiner:
    """Deterministic stand-in for the Refiner role. No network, no API key."""

    def __init__(self) -> None:
        self.model = "offline-deterministic-fixture"
        self.calls = 0
        # Per-row attempt counter, used only to make each equivalent draft
        # textually distinct in the log. It never changes the violation set.
        self._attempts: dict[str, int] = {}

    def refine(
        self, item: GeneratedArchetype, violations: list[Violation]
    ) -> GeneratedArchetype:
        self.calls += 1
        codes = {v.code for v in violations}
        name = item.row.Name
        attempt = self._attempts.get(name, 0) + 1
        self._attempts[name] = attempt

        row_changes: dict[str, Any] = {}
        intent_changes: dict[str, Any] = {}

        # R3 — add the provenance label the schema decision requires.
        if "R3_MISSING_PLACEHOLDER_LABEL" in codes:
            note = item.triage_intent.AuthoringNote.rstrip()
            separator = " " if note.endswith(".") else ". "
            intent_changes["AuthoringNote"] = (
                f"{note}{separator}All clinical values here are a "
                f"{PLACEHOLDER_LABEL}."
            )

        # R2 — pull the tourniquet pass window back to the documented value.
        if "R2_TOURNIQUET_WINDOW_BAND" in codes:
            row_changes["TourniquetPassWindowSeconds"] = TOURNIQUET_WINDOW_DEFAULT

        # R4 — rewrite an on-disk content folder as an Unreal content path.
        # `Content/Foo` and `/Game/Foo` name the same file; only the second one
        # resolves at runtime, so this is a notation fix, not a guess about
        # which asset was meant.
        if "R4_BAD_ASSET_PATH" in codes:
            authored = item.row.CasualtyCharacterAssetPath
            if authored.startswith("Content/"):
                row_changes["CasualtyCharacterAssetPath"] = (
                    "/Game/" + authored[len("Content/") :]
                )
            else:
                row_changes["CasualtyCharacterAssetPath"] = (
                    CASUALTY_ASSET_PATH_DEFAULT
                )

        # R1 sub-rule — a casualty declared Dead is neither survivable nor a
        # minor-injuries case; the Black branch stops before either is consulted.
        if "R1_BLACK_CONTRADICTION" in codes:
            intent_changes["bSurvivableWithResources"] = False
            intent_changes["bMinorInjuriesOnly"] = False

        # R1 — reconcile the row's numbers with its declaration, where the
        # brief makes the direction unambiguous.
        if "R1_SALT_MISMATCH" in codes and name in _VITALS_REPAIRS:
            repair = _VITALS_REPAIRS[name]
            row_changes.update(repair.get("row", {}))
            intent_changes.update(repair.get("triage_intent", {}))

        if row_changes or intent_changes:
            return _rebuild(item, row_changes, intent_changes)

        # Nothing this fixture knows how to repair. It returns a
        # semantically-equivalent draft — reworded, but breaking exactly the
        # same rules — which is precisely the condition the circuit breaker's
        # no-progress policy exists to detect.
        #
        # This is the designed path for Casualty_SevereTBI_Expectant, and the
        # reason it cannot be repaired is worth stating exactly. The fact that
        # settles it is in the request brief — "this person cannot be saved with
        # the resources actually available", i.e. bSurvivableWithResources is
        # false — and the refiner never receives the brief. It gets the failing
        # item and the violations, nothing more (see `build_refiner_prompt`), so
        # the Immediate-versus-Expectant call is outside its information set by
        # construction, in this fixture and on the live path alike. Behind that,
        # a live refiner reasoning from the knowledge base would find no
        # adjudicator either: `triage-system.md` § Formulas flags
        # `survivable_with_resources` [To be designed] with no resource model.
        # Escalating to a human is the correct answer, not a harness shortcoming.
        note = item.triage_intent.AuthoringNote.rstrip()
        return _rebuild(
            item,
            {},
            {
                "AuthoringNote": (
                    f"{note} Reviewed again (revision {attempt}); the authored "
                    "presentation is believed correct as written."
                )
            },
        )
