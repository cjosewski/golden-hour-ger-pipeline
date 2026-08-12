"""The Generator role.

Two implementations behind one interface:

* ``LiveGenerator``   — the real pipeline. Calls Anthropic, parses the reply.
* ``OfflineGenerator`` — a deterministic harness for CI and graders. No network,
  no API key. It replays fixed drafts, several of which deliberately break the
  rules, so the Evaluator, Refiner and Circuit Breaker can all be observed
  firing end to end on a machine with no credentials. It is a **test fixture
  standing in for a model**, not a second pipeline — nothing it produces is
  evidence about model behaviour.

This module also owns the pieces both roles share: model/key resolution, the
typed error the orchestrator converts into a retryable violation, and the JSON
extractor. `refiner.py` imports them from here.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
from typing import Any

from pydantic import ValidationError

from .prompts import build_generator_prompt
from .requests import ArchetypeRequest
from .schema import ArchetypeRow, GeneratedArchetype, SaltCategory, TriageIntent

DEFAULT_MODEL = "claude-sonnet-4-5"
MAX_TOKENS = 4096

# The placeholder label `casualty-archetype-schema.md` requires on every
# clinically-invented value. Used by the offline fixtures so they carry honest
# provenance, exactly as a real generated row must.
PLACEHOLDER_LABEL = "clinically plausible placeholder — SME validation pending"


class GenerationError(RuntimeError):
    """A role call produced something unusable.

    Raised for an unparseable reply, a reply that is not a JSON object, or a
    JSON object that fails schema validation. The orchestrator catches this and
    converts it into a synthetic ``GEN_INVALID_JSON`` violation, so a malformed
    reply feeds the refine loop as one more finding to fix rather than crashing
    the run. A model that returns prose on attempt 1 usually returns JSON on
    attempt 2; killing the whole run over it would be wasteful.
    """


class MissingApiKeyError(RuntimeError):
    """The live path was requested with no ``ANTHROPIC_API_KEY`` in the environment."""


def resolve_model() -> str:
    """Model id from the ``MODEL`` env var, defaulting to Sonnet."""
    return os.environ.get("MODEL", DEFAULT_MODEL) or DEFAULT_MODEL


def require_api_key() -> str:
    """Return the API key, or fail fast with an actionable message.

    Read from the process environment only — never from a file in the repo, and
    never logged. The message names the offline escape hatch because that is the
    single most likely thing the reader wants next.
    """
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise MissingApiKeyError(
            "ANTHROPIC_API_KEY is not set, so the live pipeline cannot run.\n"
            'Set it in PowerShell with:  $env:ANTHROPIC_API_KEY = "sk-ant-..."\n'
            "Or run the deterministic offline harness instead, which needs no "
            "key:  uv run python -m pipeline --offline"
        )
    return key


def extract_json_object(text: str) -> dict[str, Any]:
    """Pull the outermost balanced JSON object out of a model reply.

    Models wrap JSON in markdown fences, prefix it with "Here is the row:", or
    append a closing remark. This finds the first ``{`` and scans forward
    tracking brace depth, ignoring braces inside string literals and honouring
    backslash escapes, so a brace inside an AuthoringNote cannot terminate the
    scan early.
    """
    cleaned = text.strip()

    # Strip a leading markdown fence (```json / ```) and its closing partner.
    if cleaned.startswith("```"):
        newline = cleaned.find("\n")
        if newline != -1:
            cleaned = cleaned[newline + 1 :]
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[: -len("```")]
        cleaned = cleaned.strip()

    start = cleaned.find("{")
    if start == -1:
        raise GenerationError(
            "The reply contained no JSON object at all. First 200 characters: "
            f"{cleaned[:200]!r}"
        )

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(cleaned)):
        char = cleaned[index]

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                candidate = cleaned[start : index + 1]
                try:
                    parsed = json.loads(candidate)
                except json.JSONDecodeError as exc:
                    raise GenerationError(
                        f"Found a balanced JSON object but it did not parse: {exc}"
                    ) from exc
                if not isinstance(parsed, dict):
                    raise GenerationError(
                        f"Expected a JSON object, got {type(parsed).__name__}."
                    )
                return parsed

    raise GenerationError(
        "The reply contained an unterminated JSON object — brace depth never "
        "returned to zero. The model was most likely cut off by the token limit."
    )


def parse_item(text: str) -> GeneratedArchetype:
    """Model reply text → a validated ``GeneratedArchetype``."""
    payload = extract_json_object(text)
    try:
        return GeneratedArchetype.model_validate(payload)
    except ValidationError as exc:
        raise GenerationError(
            f"The JSON did not match the required shape: {exc}"
        ) from exc


class _AnthropicRole:
    """Shared Anthropic client plumbing for the live Generator and Refiner."""

    def __init__(self, *, model: str | None = None) -> None:
        # Imported here rather than at module top so that `--offline` and
        # `--selftest` work even in an environment where the SDK is present but
        # unusable, and so importing this module never touches the network.
        import anthropic

        self._anthropic = anthropic
        self.model = model or resolve_model()
        self.calls = 0
        self._client = anthropic.Anthropic(api_key=require_api_key())

    def _complete(self, prompt: str) -> str:
        """Send one prompt, return the concatenated text of the reply."""
        self.calls += 1
        try:
            message = self._client.messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            # Deliberately broad: transport errors, rate limits and status
            # errors all mean the same thing to this pipeline — this attempt
            # produced no usable content. Narrowing to the SDK's exception
            # hierarchy would couple the pipeline to SDK version details for no
            # behavioural gain. The message is preserved for the log; note that
            # the SDK does not put the API key in exception text.
            raise GenerationError(
                f"The model call failed: {type(exc).__name__}: {exc}"
            ) from exc

        parts = [
            block.text
            for block in message.content
            if getattr(block, "type", None) == "text"
        ]
        if not parts:
            raise GenerationError(
                "The reply contained no text blocks "
                f"(stop_reason={getattr(message, 'stop_reason', 'unknown')})."
            )
        return "\n".join(parts)


class LiveGenerator(_AnthropicRole):
    """Generator role backed by Anthropic. This is the real pipeline."""

    def generate(self, request: ArchetypeRequest) -> GeneratedArchetype:
        return parse_item(self._complete(build_generator_prompt(request)))


# =========================================================================
# Offline harness
# =========================================================================
#
# Everything below is a deterministic fixture. It exists so that
# `uv run python -m pipeline --offline` exercises the entire GER loop —
# generate, evaluate, refine, re-evaluate, trip, escalate, write outputs — on a
# machine with no API key and no network. The drafts are hand-designed to break
# specific rules, one from each rule family plus the escalation case:
#
#   ied_leg_hemorrhage_t1  → clean on the first attempt (the control)
#   ambulatory_lac_forearm → R3_MISSING_PLACEHOLDER_LABEL
#   tension_pneumo_chest   → R2_TOURNIQUET_WINDOW_BAND
#   abdominal_evisceration → R1_SALT_MISMATCH (the Pre-Build Declaration's
#                            own worked failure: RR 34, SBP 68, unresponsive,
#                            uncontrolled bleed, declared Yellow)
#   severe_tbi_expectant   → R1_SALT_MISMATCH the offline refiner cannot
#                            resolve, so the circuit breaker trips and
#                            escalates
#   blast_apnea_black      → R1_BLACK_CONTRADICTION
#   flash_burn_forearms    → R4_BAD_ASSET_PATH
#
# A note on the two Pulse action-name columns, because they look odd out of
# context. `HemorrhageInsultActionName` is `IED_Explosion` wherever a bleed
# actually exists: the 2026-07-29 addendum to `casualty-archetype-schema.md`
# records that the exposed Pulse Blueprint surface has exactly one bleeding
# action — "the only path to bleeding is the hardcoded, parameterless
# IED_Explosion()" — so naming anything else would ship a row referencing a
# call that provably does not exist. Casualties with no hemorrhage carry the
# literal `None`, which is Unreal's own spelling for an empty `name` value
# (these two columns are `name`-typed per Groups 1 and 4), not a stray string.
#
# These are fixtures, not model output. No claim about how a real model behaves
# should ever be drawn from them.


def _seeded_random(key: str) -> random.Random:
    """A deterministic RNG for one request key.

    Seeded from a SHA-256 digest rather than ``hash()``, because Python salts
    string hashing per process — ``hash()`` would make "deterministic" mode
    produce different numbers on every run.
    """
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def exemplar_shaped_row(**overrides: Any) -> ArchetypeRow:
    """An exemplar-shaped row with overrides applied.

    Defaults mirror `knowledge_base/DT_CasualtyArchetypes.exemplar.csv`, so a
    fixture only has to state what makes its casualty different.
    """
    values: dict[str, Any] = {
        "Name": "Casualty_Unnamed",
        "PulsePatientFileName": "StandardMale@0s",
        "bApplyInitialVitalsOverride": True,
        "InitialHeartRateBpm": 71.0,
        "InitialRespirationRateBpm": 11.0,
        "InitialSpO2Percent": 97.4,
        "InitialSystolicBP": 114.0,
        "InitialDiastolicBP": 73.0,
        "HemorrhageInsultActionName": "IED_Explosion",
        "HemorrhageInsultMagnitude01": 0.6,
        "HemorrhageSiteTag": "LeftThigh_Femoral",
        "UntreatedTrajectoryAssetPath": "",
        "TreatedTrajectoryAssetPath": "",
        "TrajectoryBranchPointSeconds": 0.0,
        "HemorrhageCessationActionName": "TourniquetApplied",
        "HemorrhageCessationMagnitude01": 1.0,
        "HemorrhageControlledFlowThreshold": 50.0,
        "TourniquetPassWindowSeconds": 120.0,
        "RespirationRateDistressThresholdBpm": 30.0,
        "PulseQualityWeakThresholdSystolicBP": 90.0,
        "PulseQualityAbsentThresholdSystolicBP": 70.0,
        "ConsciousnessAlteredThreshold01": 0.5,
        "ConsciousnessUnconsciousThreshold01": 0.2,
        "CasualtyCharacterAssetPath": (
            "/Game/GoldenHour/Characters/CasualtyT1/Casualty_01"
        ),
    }
    values.update(overrides)
    return ArchetypeRow(**values)


def _offline_draft(request: ArchetypeRequest) -> GeneratedArchetype:
    """The fixed first draft for one request key."""
    rng = _seeded_random(request.key)
    # Seeded jitter on heart rate only: it is the one vital no rule reads, so
    # varying it proves the seeding is live without perturbing any verdict.
    hr_jitter = rng.randint(-6, 6)

    if request.key == "ied_leg_hemorrhage_t1":
        # The control. Mirrors the existing hand-authored row and is coherent:
        # bleeding uncontrolled at spawn → question (d) false → survivable → Red.
        #
        # The `_Gen` suffix is load bearing. `Casualty_IED_LegHemorrhage_T1`
        # (unsuffixed) is the key of the row already in the live DataTable, and
        # Unreal keys rows by Name — importing a generated file carrying that
        # key would silently overwrite the hand-authored casualty with these
        # different vitals. This pipeline adds rows alongside the existing one;
        # it does not replace it. `run_pipeline` seeds `seen_names` from the
        # exemplar so `R4_DUPLICATE_NAME` catches the collision if a future
        # draft reintroduces it.
        return GeneratedArchetype(
            row=exemplar_shaped_row(
                Name="Casualty_IED_LegHemorrhage_T1_Gen",
                InitialHeartRateBpm=118.0 + hr_jitter,
                InitialRespirationRateBpm=22.0,
                InitialSpO2Percent=94.0,
                InitialSystolicBP=96.0,
                InitialDiastolicBP=58.0,
                HemorrhageInsultMagnitude01=0.6,
                HemorrhageSiteTag="LeftThigh_Femoral",
            ),
            triage_intent=TriageIntent(
                DeclaredCategory=SaltCategory.RED,
                InitialConsciousness01=0.85,
                bMinorInjuriesOnly=False,
                bSurvivableWithResources=True,
                AuthoringNote=(
                    "Tier-1 IED femoral hemorrhage. Vitals are a "
                    f"{PLACEHOLDER_LABEL}; compensating shock picture with an "
                    "uncontrolled arterial bleed, tourniquet-salvageable."
                ),
            ),
        )

    if request.key == "ambulatory_lac_forearm":
        # Coherent Green, but the authoring note never says the numbers are
        # invented → R3_MISSING_PLACEHOLDER_LABEL.
        return GeneratedArchetype(
            row=exemplar_shaped_row(
                Name="Casualty_Ambulatory_ForearmLac",
                InitialHeartRateBpm=88.0 + hr_jitter,
                InitialRespirationRateBpm=16.0,
                InitialSpO2Percent=99.0,
                InitialSystolicBP=124.0,
                InitialDiastolicBP=78.0,
                HemorrhageInsultActionName="None",
                HemorrhageInsultMagnitude01=0.0,
                HemorrhageSiteTag="RightForearm_Superficial",
                HemorrhageCessationActionName="DirectPressure",
            ),
            triage_intent=TriageIntent(
                DeclaredCategory=SaltCategory.GREEN,
                InitialConsciousness01=1.0,
                bMinorInjuriesOnly=True,
                bSurvivableWithResources=True,
                AuthoringNote=(
                    "Walking wounded with a superficial forearm laceration, "
                    "self-controlled with direct pressure. Fully alert and "
                    "ambulatory."
                ),
            ),
        )

    if request.key == "tension_pneumo_chest":
        # Coherent Red (RR above the distress threshold), but the tourniquet
        # pass window is authored at 240 s → R2_TOURNIQUET_WINDOW_BAND.
        return GeneratedArchetype(
            row=exemplar_shaped_row(
                Name="Casualty_TensionPneumo_Chest",
                InitialHeartRateBpm=132.0 + hr_jitter,
                InitialRespirationRateBpm=38.0,
                InitialSpO2Percent=84.0,
                InitialSystolicBP=98.0,
                InitialDiastolicBP=62.0,
                HemorrhageInsultActionName="None",
                HemorrhageInsultMagnitude01=0.0,
                HemorrhageSiteTag="RightChest_Penetrating",
                HemorrhageCessationActionName="ChestSealApplied",
                TourniquetPassWindowSeconds=240.0,
            ),
            triage_intent=TriageIntent(
                DeclaredCategory=SaltCategory.RED,
                InitialConsciousness01=0.7,
                bMinorInjuriesOnly=False,
                bSurvivableWithResources=True,
                AuthoringNote=(
                    "Penetrating chest wound with tension physiology. All vitals "
                    f"are a {PLACEHOLDER_LABEL}. Needle decompression is the "
                    "salvage intervention."
                ),
            ),
        )

    if request.key == "abdominal_evisceration":
        # THE PRE-BUILD DECLARATION'S OWN FAILURE, reproduced exactly:
        # RR 34, SBP 68, unresponsive, uncontrolled bleed — declared Yellow.
        # Valid CSV, imports clean, looks plausible, and is wrong.
        return GeneratedArchetype(
            row=exemplar_shaped_row(
                Name="Casualty_Abdominal_Evisceration",
                InitialHeartRateBpm=126.0 + hr_jitter,
                InitialRespirationRateBpm=34.0,
                InitialSpO2Percent=91.0,
                InitialSystolicBP=68.0,
                InitialDiastolicBP=44.0,
                HemorrhageInsultMagnitude01=0.45,
                HemorrhageSiteTag="Abdomen_Evisceration",
                HemorrhageCessationActionName="MoistDressingApplied",
            ),
            triage_intent=TriageIntent(
                DeclaredCategory=SaltCategory.YELLOW,
                InitialConsciousness01=0.15,
                bMinorInjuriesOnly=False,
                bSurvivableWithResources=True,
                AuthoringNote=(
                    "Abdominal evisceration, dressed by a bystander. Vitals are a "
                    f"{PLACEHOLDER_LABEL}. Serious but currently stable; will "
                    "decay without surgery."
                ),
            ),
        )

    if request.key == "severe_tbi_expectant":
        # THE ESCALATION ITEM. Declared Gray, but authored survivable=true,
        # which derives Red.
        #
        # Be precise about why the refiner cannot close this, because it is not
        # that the answer is unknowable. The answer is in the request brief:
        # "this person cannot be saved with the resources actually available",
        # i.e. bSurvivableWithResources should be false, and flipping it makes
        # the item pass as the intended Gray. The refiner never sees it. Both
        # roles get their own inputs and nothing else, and `build_refiner_prompt`
        # passes only the failing item and the violations — so the one fact that
        # settles this Immediate-versus-Expectant split sits outside the
        # refiner's information set by construction.
        #
        # A live refiner reasoning from the knowledge base alone would hit a
        # second wall behind that one: `triage-system.md` § Formulas flags
        # `survivable_with_resources` as [To be designed] with no resource model
        # behind it, so the GDD cannot adjudicate the split either. But the
        # operative cause here is the missing brief, not the open design
        # question.
        return GeneratedArchetype(
            row=exemplar_shaped_row(
                Name="Casualty_SevereTBI_Expectant",
                InitialHeartRateBpm=44.0 + hr_jitter,
                InitialRespirationRateBpm=6.0,
                InitialSpO2Percent=72.0,
                InitialSystolicBP=52.0,
                InitialDiastolicBP=30.0,
                HemorrhageInsultActionName="None",
                HemorrhageInsultMagnitude01=0.0,
                HemorrhageSiteTag="Head_OpenPenetrating",
                HemorrhageCessationActionName="None",
            ),
            triage_intent=TriageIntent(
                DeclaredCategory=SaltCategory.GRAY,
                InitialConsciousness01=0.02,
                bMinorInjuriesOnly=False,
                bSurvivableWithResources=True,
                AuthoringNote=(
                    "Open head injury with agonal respirations. Vitals are a "
                    f"{PLACEHOLDER_LABEL}. Expectant given the resources on "
                    "scene; comfort care only."
                ),
            ),
        )

    if request.key == "blast_apnea_black":
        # Apneic → Black is correct, but survivable=true contradicts a Dead
        # declaration → R1_BLACK_CONTRADICTION.
        return GeneratedArchetype(
            row=exemplar_shaped_row(
                Name="Casualty_BlastApnea_Black",
                bApplyInitialVitalsOverride=True,
                InitialHeartRateBpm=0.0,
                InitialRespirationRateBpm=0.0,
                InitialSpO2Percent=0.0,
                InitialSystolicBP=0.0,
                InitialDiastolicBP=0.0,
                # No bleed on this casualty (blast overpressure, not
                # fragmentation), so no insult action fires and both action
                # columns carry Unreal's empty-name literal.
                HemorrhageInsultActionName="None",
                HemorrhageInsultMagnitude01=0.0,
                HemorrhageSiteTag="Torso_BlastOverpressure",
                HemorrhageCessationActionName="None",
            ),
            triage_intent=TriageIntent(
                DeclaredCategory=SaltCategory.BLACK,
                InitialConsciousness01=0.0,
                bMinorInjuriesOnly=False,
                bSurvivableWithResources=True,
                AuthoringNote=(
                    "Apneic after one airway-reposition attempt. Vitals are a "
                    f"{PLACEHOLDER_LABEL} representing arrest at spawn."
                ),
            ),
        )

    if request.key == "flash_burn_forearms":
        # Clinically coherent Yellow — alert, breathing easily, radial pulse
        # present, no active hemorrhage, and explicitly not a minor-injuries
        # case — but the asset path is written as the on-disk content folder
        # (`Content/...`) instead of Unreal's content-root notation (`/Game/...`).
        # That is the single most common way this field is authored wrong: the
        # two paths name the same file and only one of them resolves at runtime,
        # and per the schema decision record the failure surfaces only in a
        # cooked build. → R4_BAD_ASSET_PATH, fixed on the first refine.
        return GeneratedArchetype(
            row=exemplar_shaped_row(
                Name="Casualty_FlashBurn_Forearms",
                InitialHeartRateBpm=96.0 + hr_jitter,
                InitialRespirationRateBpm=18.0,
                InitialSpO2Percent=97.0,
                InitialSystolicBP=128.0,
                InitialDiastolicBP=80.0,
                HemorrhageInsultActionName="None",
                HemorrhageInsultMagnitude01=0.0,
                HemorrhageSiteTag="BothForearms_PartialThicknessBurn",
                HemorrhageCessationActionName="None",
                CasualtyCharacterAssetPath=(
                    "Content/GoldenHour/Characters/CasualtyT1/Casualty_01"
                ),
            ),
            triage_intent=TriageIntent(
                DeclaredCategory=SaltCategory.YELLOW,
                InitialConsciousness01=0.95,
                bMinorInjuriesOnly=False,
                bSurvivableWithResources=True,
                AuthoringNote=(
                    "Partial-thickness flash burns to both forearms and hands, "
                    "no airway involvement. Vitals are a "
                    f"{PLACEHOLDER_LABEL}. Painful and burn-centre bound, but "
                    "physiologically stable at spawn."
                ),
            ),
        )

    raise GenerationError(
        f"The offline harness has no fixture for request key {request.key!r}. "
        "Every request in requests.py needs one, or --offline silently skips it."
    )


class OfflineGenerator:
    """Deterministic stand-in for the Generator role. No network, no API key."""

    def __init__(self) -> None:
        self.model = "offline-deterministic-fixture"
        self.calls = 0

    def generate(self, request: ArchetypeRequest) -> GeneratedArchetype:
        self.calls += 1
        return _offline_draft(request)
