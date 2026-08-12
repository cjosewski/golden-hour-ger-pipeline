"""CLI entry point.

    uv run python -m pipeline --selftest        # offline checks, no API key
    uv run python -m pipeline --offline         # full GER loop, deterministic
    uv run python -m pipeline                   # live run against Anthropic
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import breaker
from .orchestrate import DEFAULT_OUTPUT_DIR, run_pipeline


def _make_console_printable() -> None:
    """Stop an unencodable character from killing a run on its way to the console.

    Found by deliberately breaking self-test 24a to check it fails loudly. It
    did not: the failure *message* named the leaked fingerprint with an arrow,
    and on a Windows console — cp1252 by default, and cp1252 has no U+2192 —
    printing it raised `UnicodeEncodeError`. The top-level guard turned that
    into "Error: 'charmap' codec can't encode character", the summary line never
    printed, and the one thing a failing check exists to produce was lost.

    Every rule name, GDD quotation and change line in this project uses em
    dashes, middots, ellipses and arrows, so this is not a corner case; the log
    *files* are written as UTF-8 explicitly and were never at risk, but stdout
    takes whatever the console offers. Replacing an unencodable character with a
    substitution mark degrades one glyph. Raising loses the whole report.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(errors="replace")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m pipeline",
        description=(
            "Generate casualty archetype rows for Golden Hour's "
            "DT_CasualtyArchetypes, enforcing the SALT ground-truth derivation "
            "rule from triage-system.md."
        ),
    )
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="Run the offline self-test and exit. Needs no API key.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help=(
            "Run the full GER loop with deterministic fixtures instead of model "
            "calls. Needs no API key."
        ),
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        metavar="N",
        help=(
            "Override the circuit breaker's per-item refine budget "
            f"(default {breaker.MAX_REFINE_ATTEMPTS})."
        ),
    )
    parser.add_argument(
        "--out",
        type=Path,
        metavar="DIR",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory (default {DEFAULT_OUTPUT_DIR}).",
    )
    return parser


def apply_max_attempts_override(value: int) -> None:
    """Point the circuit breaker's per-item budget at ``value``.

    Rebound on the module rather than passed down a call chain because
    `should_trip` reads the module-level constant at call time — that is what
    makes the override reach the breaker at all. A function rather than two
    lines inside `main` so the self-test can prove the flag actually lands on
    the policy dial instead of asserting that `argparse` parses an integer.
    """
    breaker.MAX_REFINE_ATTEMPTS = value


def main(argv: list[str] | None = None) -> int:
    _make_console_printable()
    args = build_parser().parse_args(argv)

    if args.selftest:
        # Imported lazily so a self-test run never constructs a role and never
        # touches the output directory. (Section 16 drives `run_item` directly
        # with its own fixtures, so `selftest` does import the orchestrator —
        # but importing it starts nothing and writes nothing.)
        from .selftest import run_selftest

        return run_selftest()

    if args.max_attempts is not None:
        if args.max_attempts < 1:
            print(
                "Error: --max-attempts must be at least 1. A budget of 0 would "
                "escalate every item without ever attempting a correction.",
                file=sys.stderr,
            )
            return 2
        apply_max_attempts_override(args.max_attempts)

    mode = "offline (deterministic fixtures)" if args.offline else "live (Anthropic)"
    print(f"Golden Hour GER pipeline — {mode}")
    print(f"Refine budget: {breaker.MAX_REFINE_ATTEMPTS} attempt(s) per item")
    print("")

    run = run_pipeline(offline=args.offline, output_dir=args.out)

    print("")
    print("=" * 72)
    print(
        f"Processed {len(run.outcomes)} item(s) · "
        f"accepted {len(run.accepted)} · escalated {len(run.escalated)} · "
        f"{run.total_attempts} draft(s) evaluated · "
        f"{run.generator_calls + run.refiner_calls} role call(s)"
    )
    print(f"Outputs written to {args.out}")
    if run.escalated:
        print("")
        print(
            f"{len(run.escalated)} item(s) escalated to a human. Reports: "
            + ", ".join(f"{o.request.key}.md" for o in run.escalated)
        )
    if run.aborted:
        print("")
        print(f"RUN ABORTED: {run.abort_reason}")
        return 1
    return 0


def _cli() -> int:
    """Top-level guard: report a clean message rather than a traceback."""
    try:
        return main()
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except Exception as exc:  # noqa: BLE001 — this IS the top-level guard
        print(f"\nError: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(_cli())
