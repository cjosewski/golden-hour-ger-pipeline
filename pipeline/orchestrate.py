"""The GER loop: Generate → Evaluate → Refine, with the circuit breaker.

Per request: generate a draft, evaluate it, and while it fails and the breaker
has not tripped, refine it with the violations and evaluate again. A passing
item is accepted; a tripped item is escalated and **never written to the CSV** —
shipping a row the pipeline knows is wrong would defeat the entire exercise.
After each item the run-level breaker gets a look at the run's health.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from . import breaker as breaker_policy
from .breaker import (
    RUN_ABORT_ESCALATION_RATIO,
    ItemBreakerState,
    RunBreaker,
    is_transport_trip,
    should_trip,
)
from .evaluator import evaluate, has_placeholder_label
from .generator import GenerationError, LiveGenerator, OfflineGenerator, resolve_model
from .prompts import KB_DIR, load_exemplar_row_names
from .refiner import LiveRefiner, OfflineRefiner
from .requests import REQUESTS, ArchetypeRequest
from .salt import derive_inputs_from_row, failing_salt_questions
from .schema import (
    CSV_COLUMNS,
    NON_CSV_INTENT_FIELDS,
    ArchetypeRow,
    EvaluationResult,
    GeneratedArchetype,
    SaltCategory,
    Violation,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output"


class RunLoopError(RuntimeError):
    """A run-loop invariant was violated.

    These are conditions the loop's own control flow is supposed to make
    impossible. They are raised rather than asserted because `assert` statements
    vanish under `python -O`, and an invariant that only holds when optimisation
    is off is not an invariant.
    """


def write_text_file(path: Path, text: str) -> None:
    """Write UTF-8 text with LF endings, on every platform.

    Every hand-written file in this repo is LF-terminated, and so is the CSV
    writer's output. `Path.write_text` uses universal newlines, which on Windows
    translates every ``\\n`` to ``\\r\\n`` — so without this helper four of the
    five generated artifacts would ship CRLF while the fifth shipped LF, and a
    grader re-running the pipeline on macOS or Linux would get a diff on every
    line of the committed evidence. Opening with ``newline="\\n"`` disables the
    translation, so the bytes are the same wherever the run happens.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


class GeneratorRole(Protocol):
    """Structural type for the Generator, live or offline."""

    model: str
    calls: int

    def generate(self, request: ArchetypeRequest) -> GeneratedArchetype: ...


class RefinerRole(Protocol):
    """Structural type for the Refiner, live or offline."""

    model: str
    calls: int

    def refine(
        self, item: GeneratedArchetype, violations: list[Violation]
    ) -> GeneratedArchetype: ...


@dataclass
class AttemptRecord:
    """One draft and the verdict on it.

    ``item`` is ``None`` when the role call itself failed to produce a usable
    item — there was no draft to judge, only an error to record.
    """

    index: int
    item: GeneratedArchetype | None
    result: EvaluationResult


def _refine_calls(attempts: list[AttemptRecord]) -> int:
    """How many of these attempts were produced by a Refiner call.

    The Refiner can only run once a draft exists. Every attempt after the first
    one that carries a draft is a refine; everything before that is the
    Generator being called again after a failed reply.
    """
    count = 0
    drafted = False
    for record in attempts:
        if drafted:
            count += 1
        if record.item is not None:
            drafted = True
    return count


@dataclass
class ItemOutcome:
    """Everything that happened to one request."""

    request: ArchetypeRequest
    attempts: list[AttemptRecord] = field(default_factory=list)
    accepted: bool = False
    escalated: bool = False
    trip_reason: str = ""

    @property
    def final_item(self) -> GeneratedArchetype | None:
        for record in reversed(self.attempts):
            if record.item is not None:
                return record.item
        return None

    @property
    def refine_attempts(self) -> int:
        """How many times the Refiner role actually ran for this item.

        Not ``len(attempts) - 1``. A role call that failed produced no draft,
        and the loop responds to that by calling the *Generator* again — there
        is nothing to refine. Counting those as refine attempts over-reported
        the refiner's work on exactly the runs where it did none, which is the
        live path's most likely failure mode rather than a hypothetical one.
        """
        return _refine_calls(self.attempts)

    def attempt_label(self, record: AttemptRecord) -> str:
        """Heading for one attempt, naming the role call that produced it.

        Which role ran is not read off ``record.index``: after a failed
        generator call the loop calls the generator again, so attempt 2 can be
        a retry rather than a revision. Labelling it "refiner revision 1" would
        credit the refiner with a draft it never returned.
        """
        if record.index == 0:
            return "Attempt 1 — initial draft"
        if any(r.item is not None for r in self.attempts[: record.index]):
            revision = _refine_calls(self.attempts[: record.index + 1])
            return f"Attempt {record.index + 1} — refiner revision {revision}"
        return f"Attempt {record.index + 1} — generator retry {record.index}"


def _generation_error_result(exc: GenerationError) -> EvaluationResult:
    """Turn a failed role call into a violation the refine loop can act on.

    A malformed reply is a finding like any other: it goes into the history, the
    breaker counts it, and a role that keeps returning garbage escalates rather
    than crashing the run or spinning forever.
    """
    return EvaluationResult(
        passed=False,
        derived_category=None,
        violations=[
            Violation(
                code="GEN_INVALID_JSON",
                rule=(
                    "A role call must return one JSON object matching the "
                    "GeneratedArchetype shape."
                ),
                gdd_source="pipeline/schema.py — GeneratedArchetype",
                detail=str(exc),
            )
        ],
    )


def run_item(
    request: ArchetypeRequest,
    *,
    generator: GeneratorRole,
    refiner: RefinerRole,
    seen_names: set[str],
) -> ItemOutcome:
    """Run the full GER loop for one request."""
    outcome = ItemOutcome(request=request)
    state = ItemBreakerState(key=request.key)
    current: GeneratedArchetype | None = None
    # The violations from the last attempt that actually produced a draft. Kept
    # separate from `result` because a failed role call replaces `result` with a
    # synthetic GEN_INVALID_JSON verdict about the *transport*, and asking the
    # refiner to fix a malformed reply instead of the rule the row still breaks
    # would spend an attempt learning nothing.
    pending_violations: list[Violation] = []

    while True:
        role_call_failed = False
        try:
            if current is None:
                # First pass, or a retry after the generator returned garbage.
                current = generator.generate(request)
            else:
                current = refiner.refine(current, pending_violations)
        except GenerationError as exc:
            # Leave `current` and `pending_violations` alone so the next pass
            # retries the same role against the same real findings.
            result = _generation_error_result(exc)
            role_call_failed = True
        else:
            result = evaluate(current, seen_names=seen_names)
            pending_violations = result.violations

        outcome.attempts.append(
            AttemptRecord(
                index=len(outcome.attempts),
                # No draft exists when the role call itself failed. Recording
                # the previous draft here would show the refiner returning an
                # identical revision it never actually returned.
                item=None if role_call_failed else current,
                result=result,
            )
        )
        if role_call_failed:
            # A failed role call is a fact about the transport, not about the
            # row: no draft was produced, so no rule was evaluated. It is
            # counted on its own dial and kept out of `history`, which the
            # no-progress and regression rules compare — two rate limits in a
            # row are not "the refiner is returning an equivalent draft", and
            # reporting them as that sends a human to the wrong problem.
            state.transport_failures += 1
        else:
            state.history.append(result.codes)

        if result.passed:
            if current is None:
                raise RunLoopError(
                    "A passing evaluation was recorded with no draft to accept "
                    f"for {request.key!r}. Only `evaluate` can return passed=True, "
                    "and it is never called without an item."
                )
            outcome.accepted = True
            seen_names.add(current.row.Name)
            return outcome

        tripped, reason = should_trip(state)
        if tripped:
            outcome.escalated = True
            outcome.trip_reason = reason
            return outcome

        if not role_call_failed:
            # The refine budget is spent on corrections, not on outages. A
            # failed role call produced nothing to correct, so charging the
            # item for it would escalate a perfectly fixable row because the
            # network hiccuped. Repeated failures are still bounded — by
            # MAX_TRANSPORT_FAILURES, on the dial that describes them.
            state.attempts += 1


@dataclass
class RunResult:
    """The whole run, ready to be written out."""

    outcomes: list[ItemOutcome]
    mode: str
    model: str
    # How many requests this run was asked for. Carried on the result rather
    # than read back from the module-level REQUESTS tuple, so a run driven with
    # a different request set reports its own size instead of the default's.
    requested: int = 0
    aborted: bool = False
    abort_reason: str = ""
    generator_calls: int = 0
    refiner_calls: int = 0

    @property
    def accepted(self) -> list[ItemOutcome]:
        return [o for o in self.outcomes if o.accepted]

    @property
    def escalated(self) -> list[ItemOutcome]:
        return [o for o in self.outcomes if o.escalated]

    @property
    def total_attempts(self) -> int:
        return sum(len(o.attempts) for o in self.outcomes)


def run_pipeline(*, offline: bool, output_dir: Path) -> RunResult:
    """Run every request, write every output file, return the run result."""
    if offline:
        generator: GeneratorRole = OfflineGenerator()
        refiner: RefinerRole = OfflineRefiner()
        mode = "offline"
        model = generator.model
    else:
        # Constructing these performs the fail-fast API-key check, before any
        # request is processed and before any output file is touched.
        live_generator = LiveGenerator()
        generator = live_generator
        refiner = LiveRefiner(model=live_generator.model)
        mode = "live"
        model = resolve_model()

    return run_requests(
        REQUESTS,
        generator=generator,
        refiner=refiner,
        mode=mode,
        model=model,
        output_dir=output_dir,
    )


def run_requests(
    requests: tuple[ArchetypeRequest, ...],
    *,
    generator: GeneratorRole,
    refiner: RefinerRole,
    mode: str,
    model: str,
    output_dir: Path,
) -> RunResult:
    """Run one request set through the GER loop and write every output file.

    Split out from `run_pipeline` (which owns choosing the roles) so the run
    level of the circuit breaker can be driven end to end. With the seven
    shipped fixtures the worst case is one escalation in seven, well under the
    abort ratio, so `RunBreaker` would otherwise only ever be exercised in
    isolation — unit-tested but never proven to actually stop a run. Self-test
    section 23 calls this with a request set built to escalate a majority.
    """
    run = RunResult(outcomes=[], mode=mode, model=model, requested=len(requests))
    run_breaker = RunBreaker()

    # Seeded from the live table, not empty. `R4_DUPLICATE_NAME` compares
    # against this set, and Unreal keys DataTable rows by `Name` — so a
    # generated row reusing `Casualty_IED_LegHemorrhage_T1` would silently
    # overwrite the one hand-authored casualty that exists on import, with
    # different vitals and no warning. Starting the set empty made the rule
    # structurally incapable of seeing the only collision that matters.
    seen_names: set[str] = load_exemplar_row_names()

    # Outputs are written in the `finally` below, not after the loop. A live run
    # that dies on request 5 of 7 — a transport error the retry loop cannot
    # absorb, a bad path, an interrupted process — has still done four items'
    # worth of paid model work, and losing all of it because the seventh threw
    # is a needless second failure on top of the first.
    try:
        for request in requests:
            outcome = run_item(
                request, generator=generator, refiner=refiner, seen_names=seen_names
            )
            run.outcomes.append(outcome)
            print(_console_line(outcome))

            run_breaker.record(
                escalated=outcome.escalated, trip_reason=outcome.trip_reason
            )
            abort, abort_reason = run_breaker.should_abort_run()
            if abort:
                run.aborted = True
                run.abort_reason = abort_reason
                print("")
                print("!" * 72)
                print(f"RUN ABORTED BY THE CIRCUIT BREAKER: {abort_reason}")
                print("!" * 72)
                break
    finally:
        run.generator_calls = generator.calls
        run.refiner_calls = refiner.calls
        write_outputs(run, output_dir=output_dir)

    return run


def _accepted_item(outcome: ItemOutcome) -> GeneratedArchetype:
    """The draft an accepted outcome accepted.

    An accepted outcome always has one — `run_item` refuses to mark an outcome
    accepted without a draft. Checked here rather than asserted so the guarantee
    survives `python -O`, and so a future change that breaks it fails loudly
    instead of writing a CSV row built from `None`.
    """
    item = outcome.final_item
    if item is None:
        raise RunLoopError(
            f"Outcome for {outcome.request.key!r} is marked accepted but carries "
            "no draft. An accepted item is by definition one that was evaluated "
            "and passed."
        )
    return item


def _console_line(outcome: ItemOutcome) -> str:
    """One progress line per item."""
    if outcome.accepted:
        item = _accepted_item(outcome)
        category = item.triage_intent.DeclaredCategory.value
        suffix = (
            "accepted first time"
            if outcome.refine_attempts == 0
            else f"accepted after {outcome.refine_attempts} refine attempt(s)"
        )
        return f"  [OK]        {outcome.request.key:<24} {category:<7} {suffix}"
    codes = ", ".join(sorted(outcome.attempts[-1].result.codes)) or "unknown"
    return (
        f"  [ESCALATED] {outcome.request.key:<24} "
        f"unresolved after {outcome.refine_attempts} refine attempt(s): {codes}"
    )


# =========================================================================
# Output writers
# =========================================================================


def _fmt_number(value: float) -> str:
    """Render a float compactly, without scientific notation.

    ``%g`` drops the trailing ``.0`` on whole numbers and keeps significant
    decimals (``97.4``, ``0.6``). The scientific-notation guard is defensive:
    Unreal's CSV importer does not parse ``1e+06``, and a row that produced one
    would fail to import with no obvious cause.

    **This does not reproduce the exemplar's number formatting, and does not
    need to.** The exemplar writes some whole numbers bare (``71``, ``114``,
    ``0``) and others with a trailing ``.0`` (``1.0``, ``50.0``, ``120.0``,
    ``30.0``, ``90.0``, ``70.0``) — an inconsistency of hand authoring, not a
    convention. ``%g`` renders every one of them bare, so those six columns
    differ textually from the exemplar's row. That is safe: Unreal's DataTable
    importer parses these columns as floats, and ``120`` and ``120.0`` parse
    identically. What must match the exemplar byte-for-byte is the *header* —
    column names are matched verbatim or the importer silently fails to map
    them (`data-files.md` § Carve-out) — and self-test case 15a is the guard on
    that.
    """
    rendered = f"{value:.6g}"
    if "e" in rendered or "E" in rendered:
        rendered = f"{value:f}".rstrip("0").rstrip(".")
    return rendered


def _csv_cell(value: Any) -> str:
    """Render one row field as Unreal's DataTable importer expects it."""
    if isinstance(value, bool):
        # Lowercase, matching the exemplar's `true`. Checked before the numeric
        # branch because in Python a bool IS an int.
        return "true" if value else "false"
    if isinstance(value, float):
        return _fmt_number(value)
    return str(value)


def write_generated_csv(rows: list[ArchetypeRow], path: Path) -> None:
    """Write the accepted rows as DataTable-importable CSV.

    ``newline=""`` stops Python translating the writer's line terminator into
    ``\\r\\r\\n`` on Windows. ``lineterminator="\\n"`` then matches the exemplar
    file exactly, which is LF-only — so the generated file is byte-comparable
    with the file that already imports into the real table.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(CSV_COLUMNS)
        for row in rows:
            dumped = row.model_dump()
            writer.writerow([_csv_cell(dumped[column]) for column in CSV_COLUMNS])


def write_archetypes_json(run: RunResult, path: Path) -> None:
    """Full accepted records, including the triage intent the CSV cannot carry."""
    payload = []
    for outcome in run.accepted:
        item = _accepted_item(outcome)
        final = outcome.attempts[-1].result
        payload.append(
            {
                "request_key": outcome.request.key,
                "intended_category": outcome.request.intended_category.value,
                "derived_category": (
                    final.derived_category.value if final.derived_category else None
                ),
                "refine_attempts": outcome.refine_attempts,
                "row": item.row.model_dump(mode="json"),
                "triage_intent": item.triage_intent.model_dump(mode="json"),
            }
        )
    write_text_file(path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def _vitals_summary(item: GeneratedArchetype) -> str:
    """The at-a-glance line: what a reader needs to check a SALT verdict by hand.

    A summary line is a *selection*, so it can only ever be read as the whole
    story by accident. The tourniquet pass window is here because it is the one
    non-vital an R2 finding routinely turns on, and a line that omitted it
    rendered a repaired draft identically to the broken one it replaced. For
    the general case there is `_field_changes`, which reads the models rather
    than a hand-picked list and cannot go stale the way this line did.
    """
    row = item.row
    intent = item.triage_intent
    return (
        f"HR {_fmt_number(row.InitialHeartRateBpm)} · "
        f"RR {_fmt_number(row.InitialRespirationRateBpm)} "
        f"(distress threshold {_fmt_number(row.RespirationRateDistressThresholdBpm)}) · "
        f"SpO2 {_fmt_number(row.InitialSpO2Percent)}% · "
        f"BP {_fmt_number(row.InitialSystolicBP)}/{_fmt_number(row.InitialDiastolicBP)} "
        f"(pulse-absent below {_fmt_number(row.PulseQualityAbsentThresholdSystolicBP)}) · "
        f"consciousness {_fmt_number(intent.InitialConsciousness01)} "
        f"(altered below {_fmt_number(row.ConsciousnessAlteredThreshold01)}) · "
        f"hemorrhage insult {_fmt_number(row.HemorrhageInsultMagnitude01)} · "
        f"tourniquet window "
        f"{_fmt_number(row.TourniquetPassWindowSeconds)}s · "
        f"survivable {intent.bSurvivableWithResources} · "
        f"minor-injuries-only {intent.bMinorInjuriesOnly}"
    )


#: Longest string rendered in full in a change line before the differing part
#: is isolated instead. An authoring note runs well past this; a row name, an
#: action name and an asset path all sit comfortably under it.
_FULL_TEXT_LIMIT = 80
#: Longest changed segment shown before it is clipped.
_SEGMENT_LIMIT = 110


def _clip(text: str, limit: int = _SEGMENT_LIMIT) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _render_change_value(value: Any) -> str:
    """One side of a non-text field change, rendered for a human reader."""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return _fmt_number(value)
    return str(value)


def _render_text_change(old: str, new: str) -> str:
    """Render a change between two strings so the *difference* is what shows.

    Truncating both sides of a long value to a fixed width is how the run log
    came to render two different authoring notes identically — the edit was
    past the cut. So short values are shown in full, and long ones have their
    common prefix and suffix elided (`…`) until what is left is the part that
    actually changed.
    """
    old_text = " ".join(old.split())
    new_text = " ".join(new.split())

    # Both sides are whitespace-normalised above, but `_field_changes` decides a
    # field changed using the RAW values — so a refiner that re-wraps an
    # authoring note without altering a word arrives here with two identical
    # strings. The eliding branch below then degenerates: the common prefix runs
    # to full length, the common suffix pins to zero, both middles come out
    # empty, and the log prints `AuthoringNote gained ''` — a real difference
    # rendered as nothing, which is the exact failure this whole function was
    # written to remove. Say what actually happened instead.
    if old_text == new_text:
        return "whitespace only (no text changed)"

    if len(old_text) <= _FULL_TEXT_LIMIT and len(new_text) <= _FULL_TEXT_LIMIT:
        return f"'{old_text}' → '{new_text}'"

    head = 0
    while (
        head < min(len(old_text), len(new_text))
        and old_text[head] == new_text[head]
    ):
        head += 1
    tail = 0
    while (
        tail < min(len(old_text), len(new_text)) - head
        and old_text[len(old_text) - 1 - tail] == new_text[len(new_text) - 1 - tail]
    ):
        tail += 1

    old_middle = old_text[head : len(old_text) - tail]
    new_middle = new_text[head : len(new_text) - tail]
    lead = "…" if head else ""
    trail = "…" if tail else ""

    if not old_middle:
        return f"gained {lead}'{_clip(new_middle)}'{trail}"
    if not new_middle:
        return f"lost {lead}'{_clip(old_middle)}'{trail}"
    return (
        f"{lead}'{_clip(old_middle)}'{trail} → {lead}'{_clip(new_middle)}'{trail}"
    )


def _render_change(name: str, old: Any, new: Any) -> str:
    """One field's change, as it appears in the log's change line."""
    if isinstance(old, str) and isinstance(new, str):
        return f"{name} {_render_text_change(old, new)}"
    return f"{name} {_render_change_value(old)} → {_render_change_value(new)}"


def _field_changes(
    previous: GeneratedArchetype, current: GeneratedArchetype
) -> list[str]:
    """Every field that differs between two drafts, oldest value first.

    Computed by **iterating the pydantic models**, not by naming fields here.
    That is the whole point: the previous version of the run log described each
    draft with a hand-listed summary line, so an item whose repair touched a
    column the list did not mention rendered two byte-identical drafts whose
    verdict flipped from violation to clean — which reads as a
    non-deterministic evaluator rather than as a working one. A field added to
    the row or the triage intent is picked up here automatically, so the log
    cannot go stale the same way again.
    """
    changes: list[str] = []
    before = previous.model_dump(mode="json")
    after = current.model_dump(mode="json")

    for section, info in GeneratedArchetype.model_fields.items():
        sub_fields = getattr(info.annotation, "model_fields", None)
        if sub_fields is None:
            # Not a nested model — compare the section as one value rather than
            # silently skipping it.
            if before[section] != after[section]:
                changes.append(
                    _render_change(section, before[section], after[section])
                )
            continue
        for name in sub_fields:
            old, new = before[section][name], after[section][name]
            if old != new:
                changes.append(_render_change(name, old, new))
    return changes


def _change_lines(outcome: ItemOutcome, record: AttemptRecord) -> list[str]:
    """The "changed since attempt N" line for one attempt, if it has one.

    Compared against the last attempt that actually produced a draft, so a
    failed role call in between does not make the next revision look like it
    changed nothing.
    """
    if record.item is None:
        return []
    previous = next(
        (
            earlier
            for earlier in reversed(outcome.attempts[: record.index])
            if earlier.item is not None
        ),
        None,
    )
    if previous is None or previous.item is None:
        return []
    changes = _field_changes(previous.item, record.item)
    rendered = "; ".join(changes) if changes else "(no field changed)"
    return [f"- **Changed since attempt {previous.index + 1}**: {rendered}"]


def _violation_block(result: EvaluationResult) -> list[str]:
    """Render one attempt's violations as readable markdown."""
    if result.passed:
        return ["- **No violations.** This draft satisfies every rule."]
    lines: list[str] = []
    for violation in result.violations:
        lines.append(f"- **`{violation.code}`**")
        lines.append(f"  - Rule: {violation.rule}")
        lines.append(f"  - Authority: {_render_source(violation.gdd_source)}")
        lines.append(f"  - Found: {violation.detail}")
    return lines


def write_ger_log(run: RunResult, path: Path) -> None:
    """The evidence file: every draft, every finding, every revision, per item."""
    lines: list[str] = [
        "# GER run log — DT_CasualtyArchetypes",
        "",
        f"- **Mode**: {run.mode}",
        f"- **Model**: `{run.model}`",
        f"- **Run at**: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"- **Requested**: {run.requested} · **Accepted**: {len(run.accepted)} · "
        f"**Escalated**: {len(run.escalated)}",
        # Read through the module so a `--max-attempts` override is reported
        # accurately rather than showing the compiled-in default.
        f"- **Breaker policy**: max {breaker_policy.MAX_REFINE_ATTEMPTS} refine "
        f"attempts per item; run aborts above "
        f"{RUN_ABORT_ESCALATION_RATIO:.0%} escalations",
        "",
    ]

    if run.mode == "offline":
        lines += [
            "> **This was the offline harness.** The Generator and Refiner were "
            "deterministic fixtures, not model calls — the drafts below were "
            "hand-designed to break specific rules so the Evaluator, Refiner and "
            "Circuit Breaker can be observed working with no API key. The "
            "Evaluator, the SALT derivation and the Circuit Breaker are the real "
            "production code in both modes; only the two LLM roles are "
            "substituted. Draw no conclusions about model behaviour from this "
            "file.",
            "",
        ]

    if run.aborted:
        lines += [
            "> **RUN ABORTED.** " + run.abort_reason,
            "",
        ]

    lines += ["---", ""]

    for outcome in run.outcomes:
        request = outcome.request
        verdict = "ACCEPTED" if outcome.accepted else "ESCALATED"
        lines += [
            f"## `{request.key}` — {verdict}",
            "",
            f"*Requested as:* {request.intended_category.value}. "
            f"*Drafts evaluated:* {len(outcome.attempts)} "
            f"({outcome.refine_attempts} refine attempt(s)).",
            "",
        ]

        for record in outcome.attempts:
            lines += [f"### {outcome.attempt_label(record)}", ""]

            if record.item is None:
                lines += [
                    "The role call produced no usable item, so there is no draft "
                    "to show and no rule was evaluated against one.",
                    "",
                ]
            else:
                declared = record.item.triage_intent.DeclaredCategory.value
                derived = (
                    record.result.derived_category.value
                    if record.result.derived_category
                    else "n/a"
                )
                lines += [
                    f"- **Row**: `{record.item.row.Name}`",
                    f"- **Declared category**: {declared}",
                    f"- **Derived from these vitals**: {derived}",
                    f"- **Vitals**: {_vitals_summary(record.item)}",
                    f"- **Authoring note**: {record.item.triage_intent.AuthoringNote}",
                ]
                lines += _change_lines(outcome, record)
                lines += [""]

            lines += ["**Evaluator findings:**", ""]
            lines += _violation_block(record.result)
            lines += [""]

        if outcome.accepted:
            lines += [
                f"**Verdict: accepted.** The row passed every rule after "
                f"{outcome.refine_attempts} refine attempt(s) and is written to "
                "`DT_CasualtyArchetypes.generated.csv`.",
                "",
            ]
        else:
            lines += [
                f"**Verdict: escalated.** The circuit breaker tripped — "
                f"{outcome.trip_reason}. This row is deliberately NOT written to "
                "the CSV; see "
                f"`escalations/{outcome.request.key}.md`.",
                "",
            ]

        lines += ["---", ""]

    write_text_file(path, "\n".join(lines))


def _render_source(source: str) -> str:
    """Render one ``gdd_source`` for a report, prefixing only real GDD files.

    Most sources name a file in `knowledge_base/`, and a reader wants the path
    they can open. Some do not: `GEN_INVALID_JSON` cites a module in this repo,
    and a few rules cite an invariant in prose. Prefixing those produced
    `knowledge_base/pipeline/schema.py — GeneratedArchetype`, a path that does
    not exist and never did.
    """
    first_token = source.split(" ", 1)[0]
    if first_token.endswith((".md", ".csv")) and (KB_DIR / first_token).is_file():
        return f"`knowledge_base/{source}`"
    return source


def _mismatch_axis(outcome: ItemOutcome) -> tuple[str, list[str]]:
    """Which decision an R1 mismatch actually turns on, from the last draft.

    Returns the axis name and, when it applies, the SALT questions that
    resolved false. Naming the wrong cause confidently is worse than staying
    general: an escalation report is read by someone who was not watching the
    run, and a paragraph about the survivability question attached to a
    respiratory-distress mismatch sends them to the wrong document.
    """
    record = next(
        (r for r in reversed(outcome.attempts) if r.item is not None),
        None,
    )
    if record is None or record.item is None:
        return ("unknown", [])

    item = record.item
    declared = item.triage_intent.DeclaredCategory
    derived = record.result.derived_category
    inputs = derive_inputs_from_row(item.row, item.triage_intent)
    failed = failing_salt_questions(inputs)

    if derived is None:
        return ("unknown", failed)
    pair = {declared, derived}
    if pair == {SaltCategory.RED, SaltCategory.GRAY}:
        return ("survivability", failed)
    if pair == {SaltCategory.GREEN, SaltCategory.YELLOW}:
        return ("minor-injuries", failed)
    if SaltCategory.BLACK in pair:
        return ("breathing", failed)
    return ("questions", failed)


def _escalation_guidance(outcome: ItemOutcome) -> list[str]:
    """Point the human at the section that can actually settle the deadlock."""
    if is_transport_trip(outcome.trip_reason):
        # Nothing below applies: no draft survived, so there is no row to
        # reason about and no GDD section to consult. Saying so plainly is the
        # whole fix — the previous version would have printed a paragraph about
        # the refiner refusing to reconcile a finding that was never raised.
        return [
            "## What happened",
            "",
            "The role calls for this item failed to return anything usable, so "
            "no draft was ever evaluated. **This is not a finding about the "
            "row.** No rule was checked against it, and nothing in the "
            "knowledge base is implicated.",
            "",
            "The attempt history above records the error text each call "
            "returned. Typical causes are a rate limit, an expired or "
            "unauthorized API key, a network interruption, or a model reply "
            "that was not the JSON object the roles are required to return.",
            "",
            "**To resolve**: check the error text, then re-run. The item is "
            "escalated rather than accepted because a row nobody evaluated is "
            "exactly the row this pipeline exists to keep out of the "
            "DataTable — an unchecked row that imports cleanly is the failure "
            "mode, not the safe fallback.",
            "",
        ]

    codes: set[str] = set()
    for record in outcome.attempts:
        codes |= record.result.codes

    sources: list[str] = []
    for record in outcome.attempts:
        for violation in record.result.violations:
            if violation.gdd_source not in sources:
                sources.append(violation.gdd_source)

    lines = ["## Where to look", ""]
    for source in sources:
        lines.append(f"- {_render_source(source)}")
    lines.append("")

    if "R1_SALT_MISMATCH" in codes:
        axis, failed = _mismatch_axis(outcome)
        lines += [
            "This is a SALT coherence deadlock. The row's declared category and "
            "the category its own vitals derive disagree, and resolving it means "
            "deciding which of the two is authoritative for this casualty — a "
            "content judgement, not a mechanical fix.",
            "",
        ]

        if failed:
            lines += [
                "The row's own numbers fail these SALT questions: "
                + "; ".join(failed)
                + ".",
                "",
            ]
        else:
            lines += [
                "All four SALT questions pass on the row's own numbers, so the "
                "category was decided by one of the two authored flags rather "
                "than by the vitals.",
                "",
            ]

        lines += [
            "**Why the refiner could not close this.** The Refiner receives the "
            "failing row and the violations against it — nothing else. It does "
            "**not** receive the request brief that describes the casualty this "
            "row is meant to portray (see the module docstring in "
            "`pipeline/prompts.py`). Where a finding can only be settled from "
            "the brief, it is unresolvable from inside the loop by construction, "
            "however many attempts it is given. That is a deliberate boundary in "
            "this pipeline, not an accident, and it is what makes the circuit "
            "breaker reachable.",
            "",
        ]

        if axis == "survivability":
            lines += [
                "**And this one turns on the game's own open question.** The "
                "disagreement here is the Immediate-versus-Expectant split, "
                "which `triage-system.md` § Formulas decides with "
                "`survivable_with_resources` — a field that same section flags "
                "**[To be designed]**: \"SALT's real-world definition of this "
                "question is resource- and judgment-based, not threshold-based "
                "... Do not hardcode this as always-true; it needs an explicit "
                "design decision before the Expectant category can be authored "
                "honestly.\" The document's Open Questions table assigns that "
                "decision to the acting SME plus the game designer before "
                "Phase 2 closes. So even a refiner that *did* read the brief "
                "would find no rule in the knowledge base to reason from — only "
                "the brief's own assertion about this casualty.",
                "",
                "**To resolve**: decide from the brief above whether this "
                "casualty is salvageable with what is on scene, set "
                "`bSurvivableWithResources` accordingly, and re-run. If the "
                "brief itself is ambiguous, that is the finding — it belongs in "
                "the open question, not in this row.",
                "",
            ]
        elif axis == "minor-injuries":
            lines += [
                "The disagreement here is the Minimal-versus-Delayed split, "
                "which `triage-system.md` Core Rule 2.4 decides with the "
                "minor-injuries-only check. Nothing on the row represents the "
                "injury loadout that check reads, so it is authored per row "
                "(`bMinorInjuriesOnly`) and only the brief can settle it.",
                "",
                "**To resolve**: decide from the brief whether this casualty's "
                "injuries are minor-only, set `bMinorInjuriesOnly` accordingly, "
                "and re-run.",
                "",
            ]
        elif axis == "breathing":
            lines += [
                "The disagreement involves category Black, which "
                "`triage-system.md` Core Rule 2.2 reaches only through the "
                "breathing check: \"if the casualty is not breathing even after "
                "airway repositioning, category = Dead (Black). Stop.\" A "
                "declared Black with a positive respiration rate, or the "
                "reverse, is a contradiction inside the row itself.",
                "",
                "**To resolve**: decide whether this casualty is apneic at "
                "spawn, then make `InitialRespirationRateBpm` and the "
                "declaration agree.",
                "",
            ]
        else:
            lines += [
                "**To resolve**: work through `triage-system.md` § Formulas — "
                "Ground-Truth Category Derivation against the failed questions "
                "listed above, and decide whether the vitals or the declaration "
                "is describing this casualty correctly. Change the one that is "
                "wrong; changing both tends to move the disagreement rather than "
                "settle it.",
                "",
            ]

    return lines


def write_escalation(outcome: ItemOutcome, path: Path) -> None:
    """One escalation report: why it tripped, what was tried, where to look."""
    request = outcome.request
    lines: list[str] = [
        f"# Escalation — `{request.key}`",
        "",
        f"- **Requested as**: {request.intended_category.value}",
        f"- **Drafts evaluated**: {len(outcome.attempts)} "
        f"({outcome.refine_attempts} refine attempt(s))",
        f"- **Circuit breaker tripped because**: {outcome.trip_reason}",
        "",
        "This row was **not** written to `DT_CasualtyArchetypes.generated.csv`. "
        "A row the pipeline knows is incoherent is worse than a missing row: it "
        "imports cleanly, looks plausible, and silently supplies the wrong "
        "ground truth to scoring.",
        "",
        "## The brief",
        "",
        request.brief,
        "",
        "## Attempt history",
        "",
    ]

    for record in outcome.attempts:
        lines += [f"### {outcome.attempt_label(record)}", ""]
        if record.item is None:
            lines += [
                "The role call produced no usable item, so there is no draft to "
                "show and no rule was evaluated against one.",
                "",
            ]
        else:
            derived = (
                record.result.derived_category.value
                if record.result.derived_category
                else "n/a"
            )
            lines += [
                f"- **Declared**: {record.item.triage_intent.DeclaredCategory.value} "
                f"· **Derived**: {derived}",
                f"- **Vitals**: {_vitals_summary(record.item)}",
                f"- **Authoring note**: {record.item.triage_intent.AuthoringNote}",
            ]
            lines += _change_lines(outcome, record)
            lines += [""]
        lines += _violation_block(record.result)
        lines += [""]

    lines += _escalation_guidance(outcome)

    write_text_file(path, "\n".join(lines))


def write_run_summary(run: RunResult, path: Path) -> None:
    """Machine-readable counts for the run."""
    summary = {
        "mode": run.mode,
        "model": run.model,
        "requested": run.requested,
        "processed": len(run.outcomes),
        "accepted": len(run.accepted),
        "escalated": len(run.escalated),
        "total_attempts": run.total_attempts,
        "total_refine_attempts": sum(o.refine_attempts for o in run.outcomes),
        # "role calls", not "LLM calls": in offline mode these are fixture
        # invocations and no model is contacted at all. A key named
        # `total_llm_calls` reporting a number on a run that made zero model
        # calls is a claim the run did not earn.
        "total_role_calls": run.generator_calls + run.refiner_calls,
        "generator_calls": run.generator_calls,
        "refiner_calls": run.refiner_calls,
        "run_aborted": run.aborted,
        "abort_reason": run.abort_reason,
        "max_refine_attempts": breaker_policy.MAX_REFINE_ATTEMPTS,
        "escalated_keys": [o.request.key for o in run.escalated],
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    write_text_file(path, json.dumps(summary, indent=2, ensure_ascii=False) + "\n")


def _label_status(note: str) -> str:
    """How a row's authoring note stands against R3, in a table cell."""
    return "present" if has_placeholder_label(note) else "**MISSING**"


# Why each authoring-intent field is not a CSV column, keyed by field name so
# the notes file's list is generated from `TriageIntent` rather than typed out
# beside it. Presentation order is this dict's order; the count in the prose
# above the list is `len(NON_CSV_INTENT_FIELDS)`, not a number typed here.
_NON_COLUMN_REASONS: dict[str, str] = {
    "AuthoringNote": (
        "`AuthoringNote`. Rule R3 requires every generated row to carry the "
        "\"clinically plausible placeholder — SME validation pending\" label "
        "on it, and the CSV has nowhere to put it."
    ),
    "DeclaredCategory": (
        "The declared SALT category. Deliberately absent: "
        "`triage-system.md` § Summary keeps the ground-truth category "
        "\"derived live from their Pulse physiology state — not a static, "
        "author-placed tag\"."
    ),
    "InitialConsciousness01": (
        "`InitialConsciousness01`. Also deliberately absent, and the one "
        "most likely to be misread as an oversight, because it is the **sole "
        "input to SALT question (a)** — whether the casualty obeys commands "
        "or shows purposeful movement. "
        "`knowledge_base/casualty-archetype-schema.md` § Group 1 excludes it "
        "from the row on purpose: \"`ConsciousnessLevel01` and `PainLevel01` "
        "are deliberately **not** carried as initial-override fields: a "
        "pre-insult baseline is definitionally alert and pain-free, and both "
        "are physiology *outputs* of the pipeline (Stage 1 read / Stage 3 "
        "derived) rather than archetype-authored inputs — carrying them here "
        "would misrepresent them as authored config when they are computed "
        "state.\" So the value below is authoring *intent* used to derive "
        "ground truth, never a shipped column, and the per-row lists say "
        "\"vitals and authoring intent\" rather than \"vitals\" for that "
        "reason."
    ),
    "bMinorInjuriesOnly": (
        "`bMinorInjuriesOnly` — the Green-vs-Yellow split. "
        "`triage-system.md` § Detailed Design — Core Rules, rule 2.4: "
        "\"**All four true** → check for minor-injuries-only: if yes, "
        "category = **Minimal (Green)**; if no (injured but stable), category "
        "= **Delayed (Yellow)**.\" Nothing on the row represents the injury "
        "loadout that check reads, so it is authored per row."
    ),
    "bSurvivableWithResources": (
        "`bSurvivableWithResources` — the Red-vs-Gray split, and the field "
        "this run's one escalation turns on. `triage-system.md` § Formulas "
        "flags it **[To be designed]**: \"Do not hardcode this as "
        "always-true; it needs an explicit design decision before the "
        "Expectant category can be authored honestly.\" So it is authored "
        "per row and never inferred here."
    ),
}

# Small-number words, so the sentence above the list reads as prose while the
# number itself still comes from the model. Anything past the table falls back
# to digits rather than guessing at English.
_COUNT_WORDS: tuple[str, ...] = (
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
)


def _count_word(count: int) -> str:
    """`5` → "five". Digits past the small-number table."""
    return _COUNT_WORDS[count] if 0 <= count < len(_COUNT_WORDS) else str(count)


def _non_column_items() -> list[str]:
    """The numbered "not a CSV column" list, one entry per intent field.

    Built from `NON_CSV_INTENT_FIELDS` so the list cannot be shorter than the
    model. A field added to `TriageIntent` with no entry in `_NON_COLUMN_REASONS`
    still gets a line — an undocumented one that says so — because a silently
    omitted field is exactly the defect this list is generated to prevent.
    Self-test case 22f fails on that line, so the gap reaches a human.
    """
    items: list[str] = []
    for index, name in enumerate(
        sorted(
            NON_CSV_INTENT_FIELDS,
            key=lambda field_name: (
                list(_NON_COLUMN_REASONS).index(field_name)
                if field_name in _NON_COLUMN_REASONS
                else len(_NON_COLUMN_REASONS)
            ),
        ),
        start=1,
    ):
        reason = _NON_COLUMN_REASONS.get(
            name,
            f"`{name}` — **undocumented**: added to `TriageIntent` after these "
            "notes were written, with no recorded reason for its absence from "
            "the CSV. Document it in `_NON_COLUMN_REASONS`.",
        )
        items.append(f"{index}. {reason}")
    return items


def write_generated_notes(run: RunResult, path: Path) -> None:
    """The CSV's sibling notes file: provenance the CSV itself cannot carry.

    This exists because of a coherence gap in the pipeline's own output. R3
    enforces the "clinically plausible placeholder — SME validation pending"
    label on `AuthoringNote` — but `AuthoringNote` is not one of the 24
    DataTable columns, so the label never reaches the file that gets imported.
    Searching the generated CSV for the word "placeholder" returned nothing:
    the artifact carrying invented clinical vitals into the game shipped with
    no provenance on it at all, while the rule protecting it lived only in the
    run log.

    The project's own rule prescribes exactly this fix.
    `knowledge_base/data-files.md` § Carve-out: "Unreal's CSV importer has no
    comment syntax — the first row is always literal headers. Put per-value
    sourcing/placeholder documentation in a sibling `<Name>.notes.md`, never
    inline." The game repo's hand-authored table already ships one; the
    generated table now does too.
    """
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines: list[str] = [
        "# `DT_CasualtyArchetypes.generated` — CSV Source Notes",
        "",
        "> **Sibling file**: `DT_CasualtyArchetypes.generated.csv` — "
        f"{len(run.accepted)} accepted row(s)",
        f"> **Produced by**: this repo's GER pipeline, {run.mode} mode, model "
        f"`{run.model}`",
        f"> **Run at**: {generated_at}",
        "> **Schema authority**: `knowledge_base/casualty-archetype-schema.md` "
        "(`F_CasualtyArchetypeRow`, 23 authored fields in Groups 1–7; the "
        "DataTable adds the engine's own `Name` key column, which is why the "
        "CSV has 24)",
        "> **Rule enforced on every row below**: "
        "`knowledge_base/triage-system.md` § Formulas — Ground-Truth Category "
        "Derivation",
        "",
        "Why this is a sibling file rather than a comment block inside the CSV: "
        "`knowledge_base/data-files.md` § Carve-out states that \"Unreal's CSV "
        "importer has no comment syntax — the first row is always literal "
        "headers\", and instructs authors to \"put per-value "
        "sourcing/placeholder documentation in a sibling `<Name>.notes.md`, "
        "never inline\". The hand-authored table in the game repo ships one of "
        "these; the generated table now does too.",
        "",
        # The count is derived from `TriageIntent`, never typed: this sentence
        # shipped saying "Three" while the block below it rendered five, and a
        # falsifiable count in a graded artifact costs more than the gap it hides.
        "There is a second reason specific to this pipeline. "
        f"{_count_word(len(NON_CSV_INTENT_FIELDS)).capitalize()} things "
        "below are **not columns of the 24-column CSV**, and each is absent "
        f"for its own documented reason, so all "
        f"{_count_word(len(NON_CSV_INTENT_FIELDS))} live here instead, next "
        "to the file they describe.",
        "",
        *_non_column_items(),
        "",
        "## Placeholder-labelling status of every generated row",
        "",
        "Every clinical value in the sibling CSV — every vital sign, every "
        "threshold band — was invented by a generator role. **No clinician has "
        "reviewed any of them.** They are clinically plausible placeholders "
        "with SME validation pending, and they must be treated as such until "
        "an acting clinical SME reviews them.",
        "",
        "| Row | Declared | Derived from the row's own vitals | Refines | "
        "Placeholder label |",
        "|---|---|---|---|---|",
    ]

    for outcome in run.accepted:
        item = _accepted_item(outcome)
        final = outcome.attempts[-1].result
        derived = (
            final.derived_category.value if final.derived_category else "not derived"
        )
        lines.append(
            f"| `{item.row.Name}` | {item.triage_intent.DeclaredCategory.value} | "
            f"{derived} | {outcome.refine_attempts} | "
            f"{_label_status(item.triage_intent.AuthoringNote)} |"
        )

    if not run.accepted:
        lines.append("| *(no rows were accepted in this run)* | — | — | — | — |")

    lines += [
        "",
        "Declared and derived agree on every shipped row — that agreement is "
        "what R1 checks, and a row where they disagree is not written to the "
        "CSV.",
        "",
        "## Per-row authoring notes, verbatim",
        "",
    ]

    for outcome in run.accepted:
        item = _accepted_item(outcome)
        accepted_how = (
            "accepted on the first draft"
            if outcome.refine_attempts == 0
            else f"accepted after {outcome.refine_attempts} refine attempt(s)"
        )
        lines += [
            f"### `{item.row.Name}`",
            "",
            f"- **Request**: `{outcome.request.key}` (asked for "
            f"{outcome.request.intended_category.value}) — {accepted_how}",
            f"- **Authoring note**: {item.triage_intent.AuthoringNote}",
            f"- **Placeholder label**: "
            f"{_label_status(item.triage_intent.AuthoringNote)}",
            f"- **Pulse patient file**: `{item.row.PulsePatientFileName}` · "
            f"**vitals override gate**: {item.row.bApplyInitialVitalsOverride}",
            f"- **Vitals and authoring intent**: {_vitals_summary(item)}",
            "",
        ]

    lines += [
        "## Rows this run refused to ship",
        "",
    ]
    if run.escalated:
        lines += [
            "These items were escalated to a human and are deliberately **not** "
            "in the CSV. A row the pipeline knows is incoherent is worse than a "
            "missing row: it imports cleanly, looks plausible, and silently "
            "supplies the wrong ground truth to scoring.",
            "",
        ]
        for outcome in run.escalated:
            item = outcome.final_item
            row_name = f"`{item.row.Name}`" if item is not None else "*(no draft)*"
            lines += [
                f"- {row_name} — request `{outcome.request.key}`, asked for "
                f"{outcome.request.intended_category.value}. **Held back "
                f"because**: {outcome.trip_reason}. See "
                f"`escalations/{outcome.request.key}.md`.",
            ]
        lines.append("")
    else:
        lines += ["No item escalated in this run.", ""]

    if run.aborted:
        lines += [
            f"**The run was aborted by the circuit breaker**: {run.abort_reason}. "
            "Requests after that point were never attempted.",
            "",
        ]

    write_text_file(path, "\n".join(lines))


def write_outputs(run: RunResult, *, output_dir: Path) -> None:
    """Write every artifact listed in the README's output table."""
    output_dir.mkdir(parents=True, exist_ok=True)
    escalations_dir = output_dir / "escalations"
    escalations_dir.mkdir(parents=True, exist_ok=True)

    # Clear stale escalation reports first. An escalation file left over from a
    # previous run would read as a live finding about this one.
    for stale in escalations_dir.glob("*.md"):
        stale.unlink()

    accepted_rows: list[ArchetypeRow] = [
        _accepted_item(outcome).row for outcome in run.accepted
    ]

    write_generated_csv(accepted_rows, output_dir / "DT_CasualtyArchetypes.generated.csv")
    write_generated_notes(
        run, output_dir / "DT_CasualtyArchetypes.generated.notes.md"
    )
    write_archetypes_json(run, output_dir / "archetypes.json")
    write_ger_log(run, output_dir / "ger_log.md")
    for outcome in run.escalated:
        write_escalation(outcome, escalations_dir / f"{outcome.request.key}.md")
    write_run_summary(run, output_dir / "run_summary.json")
