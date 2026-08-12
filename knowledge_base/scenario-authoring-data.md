# Scenario Authoring & Data

> **Status**: Draft
> **Author**: game-designer
> **Last Updated**: 2026-07-15
> **Last Verified**: 2026-07-15
> **Implements Pillar**: Pillar 1 (Clinical truth under pressure)

## Summary

The data-driven layer that defines casualty archetypes and scenario
parameters: injury loadout → Pulse conditions/actions → pre-baked state +
trajectory, per casualty; casualty count/mix, injury severity distribution,
and environmental stressor parameters, per scenario. This is what keeps
every tuning knob named across the other 13 GDDs genuinely configurable
rather than hardcoded, per this project's coding standards.

> **Quick reference** — Layer: `Feature` · Priority: `MVP` · Key deps: `Casualty Model, Pulse Physiology Integration`

## Overview

Nothing about this scenario should live as a magic number buried in
Blueprint logic. This system is where casualty archetypes and scenario
parameters are authored as data, so that balancing, adding new casualties,
or building future scenarios never requires touching gameplay-system logic.

Key facts driving this design:
- A casualty archetype = injury loadout + Pulse patient file/conditions + a pre-baked state trajectory with authored treated/untreated branch points, mirroring how Pulse itself is authored (declarative JSON scenario/patient files).
- A scenario definition = casualty count/mix, injury severity distribution, environmental stressor parameters (ambient audio intensity, time-to-re-escalation), and zone timers — all data files per this project's `coding-standards.md` rule that gameplay values must be data-driven, never hardcoded.
- Two authoring paths mirror Pulse's own model: declarative JSON scenario/patient files for baseline authoring, or programmatic action injection at runtime for trainee-triggered branches (e.g., an intervention swapping a casualty onto a different pre-baked trajectory).
- **Scope note**: this GDD's MVP scope is deliberately minimal for the POC — a flat data table for the ~5–15 casualty archetypes and scenario tuning knobs, satisfying the data-driven coding-standards rule without building general-purpose tooling. The general-purpose, reusable, scenario-library authoring-pipeline ambition (this system as the natural home for future scenario-library content without engineering rework) is **Full Vision tier**, not POC/MVP scope, per `game-concept.md`'s Scope Tiers.
- Per product-owner direction (2026-07-16): casualty **staging height** is an authorable per-casualty property (ground-level vs. raised — litter/gurney/bench/car seat, 40–70cm) — a meaningful share of casualties in the POC's scenario are authored at raised heights, which is narratively natural for an MCI scene and also serves the Virtuix Omni treadmill's kneel-and-treat ergonomics accommodations (see `vr-interaction-locomotion.md`).

## Player Fantasy

*[Not applicable — this is an authoring/tooling system, not directly
player-facing.]* This system doesn't serve player fantasy directly; it
exists so every tuning knob named across the other GDDs is actually
configurable data, not a hardcoded number.

## Detailed Design

### Core Rules

[To be designed] — the casualty-archetype and scenario-definition structure above is the seed

### States and Transitions

[To be designed]

### Interactions with Other Systems

[To be designed]

## Formulas

[To be designed]

## Edge Cases

| Scenario | Expected Behavior | Rationale |
|----------|------------------|-----------|
| [To be designed] | | |

## Dependencies

| System | Direction | Nature of Dependency |
|--------|-----------|---------------------|
| Casualty Model | This depends on Casualty Model | Authors data consumed by the casualty actor's archetype composition |
| Pulse Physiology Integration | This depends on Pulse Physiology Integration | Casualty archetypes are authored as Pulse patient files/conditions and baked trajectories |
| Triage System | Triage System depends on this | Triage tuning knobs (RR threshold, cap-refill threshold, time targets) are authored here |
| Treatment & Interventions | Treatment & Interventions depends on this | Intervention pass windows are authored here |
| Scene & Zone Director | Scene & Zone Director depends on this | Zone timers and re-escalation triggers are authored here |

## Tuning Knobs

[To be designed] — this system is itself the home for other systems' tuning knobs, not a source of its own gameplay-facing knobs

## Visual/Audio Requirements

[To be designed] — this is a backend/tooling system with no direct trainee-facing visual/audio output

## Game Feel

### Feel Reference

[To be designed] — not applicable to a tooling/data system

### Input Responsiveness

[To be designed]

### Animation Feel Targets

[To be designed]

### Impact Moments

[To be designed]

### Weight and Responsiveness Profile

[To be designed]

### Feel Acceptance Criteria

- [ ] [To be designed]

## UI Requirements

[To be designed] — any authoring-tool UI is out of scope for this GDD, which specifies the data format/contract, not tooling

## Cross-References

| This Document References | Target GDD | Specific Element Referenced | Nature |
|--------------------------|-----------|----------------------------|--------|
| "Casualty archetypes authored as Pulse patient files + baked trajectories" | `design/gdd/pulse-physiology-integration.md` | Pulse patient file/condition format | Data dependency |
| "Casualty archetype data composes the casualty actor" | `design/gdd/casualty-model.md` | Casualty actor archetype composition | Ownership handoff |
| "Casualty staging height (raised litters/gurneys/benches, 40–70cm) is an authorable per-casualty property" | `design/gdd/vr-interaction-locomotion.md` | Kneel-and-treat ergonomics accommodations | Rule dependency |

## Acceptance Criteria

- [ ] GIVEN a new casualty archetype is authored as data, WHEN it is loaded, THEN no gameplay-system code changes are required to use it
- [ ] GIVEN a scenario tuning knob (e.g., RR threshold) is changed in data, WHEN the scenario runs, THEN the change takes effect without a rebuild
- [ ] Performance: Casualty archetype load completes within a frame-budget-safe threshold — [To be designed]
- [ ] No hardcoded values in implementation — this is the entire purpose of this system

## Open Questions

| Question | Owner | Deadline | Resolution |
|----------|-------|----------|-----------|
| Exact data format/schema for casualty archetypes and scenario definitions | ue-blueprint-specialist | Phase 3 (Technical Setup) | → ADR (Phase 3) — not a GDD-time decision |
| Whether an in-editor authoring tool is needed for the POC or hand-authored JSON/data assets are sufficient | producer / unreal-specialist | Before Phase 3 | [To be designed] |

## Build Agents

This system's build work is assigned to the Content pipeline crew: retrieval-grounded generation of casualty-archetype and scenario data files with registry/consistency checks (W2-W3), feeding the Tier-1 casualty. Mapped in the compiled GDD's build-time agent plan (§12.1).
