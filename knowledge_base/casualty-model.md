# Casualty Model

> **Status**: Draft
> **Author**: game-designer
> **Last Updated**: 2026-07-15
> **Last Verified**: 2026-07-15
> **Implements Pillar**: Pillar 1 (Clinical truth under pressure), Pillar 2 (The face is a vital sign), Pillar 5 (The scene listens — supplies the mobility/behavior state the voice-driven global sort reads — per product-owner direction (2026-07-16))

## Summary

The Casualty Model is the casualty actor itself: its injury loadout, its
ground-truth state derived live from Pulse physiology, its
mobility/behavior state (ambulatory / purposeful-movement / still), and —
critically — the **physiology-LOD arbiter** that decides which casualties
run a live physiology engine versus a pre-baked trajectory. Every other
gameplay system targets a casualty; this system defines what a casualty
*is*.

> **Quick reference** — Layer: `Foundation` · Priority: `MVP` · Key deps: `Pulse Physiology Integration`

## Overview

A casualty in this game is not a health bar with a skin on it — it is a
specific person with an authored injury loadout, a real physiology
simulation underneath, and a face and body that reflect that simulation
truthfully. This system is where those pieces come together into one actor
the rest of the game can query and act on.

Key facts driving this design:
- Each casualty actor owns a Pulse physiology component (see `pulse-physiology-integration.md`) plus an authored injury loadout (see `scenario-authoring-data.md`).
- This system owns the LOD/promotion decision referenced in `systems-index.md`'s Circular Dependencies note — it is the single point that decides whether a casualty is "live" (full physiology engine) or "baked" (pre-serialized trajectory), consuming trainee proximity/assessment-state as input.
- Mobility/behavior state (ambulatory, purposeful-movement, still) is what `triage-system.md`'s SALT global sort reads to route casualties into the walk/wave/still queue.
- Baseline POC target is a hand-managed pool of ~5–15 full-fidelity casualty archetypes; MetaHuman Collections (UE 5.8, Experimental) crowd tech is noted as a later stretch path for scaling casualty/bystander counts, not a POC requirement.

## Player Fantasy

Every casualty should read as a specific person having the worst day of
their life — never a target, never a puzzle piece. This system exists so
that impression is backed by real, consistent simulated state, not just art
direction.

## Detailed Design

### Core Rules

- A casualty archetype is defined by three linked pieces: an injury loadout, a Pulse patient file/conditions, and a pre-baked state trajectory with treated/untreated branches (all authored in `scenario-authoring-data.md`).
- LOD states: **Live** (full Pulse engine, assigned to near/actively-treated casualties) and **Baked** (pre-serialized trajectory playback, assigned to distant/untriaged casualties). This system is PC VR only for the POC — Meta Quest standalone live-physiology support is deferred to the Alpha milestone, feasibility-gated (see `systems-index.md` High-Risk Systems); Quest is not a POC design constraint here.
- **Scoring-fairness rule**: a casualty MUST be promoted to Live LOD before its ground-truth triage category is used for a scored comparison (see `scoring-and-debrief.md`). Scoring never grades a trainee's triage call against a merely pre-computed Baked-LOD checkpoint — if the trainee tags a casualty still on Baked LOD, this system promotes it to Live and reconciles its ground-truth state at that exact moment before the tag is scored. This is what makes dynamic re-triage (see `triage-system.md`) scoreable fairly.
- [To be designed] — exact promotion/demotion rules, and how mobility/behavior state (ambulatory/purposeful-movement/still) is derived from the physiology state for the SALT global sort.

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
| Pulse Physiology Integration | This depends on Pulse Physiology Integration | Owns the physiology component and LOD live/baked promotion within each casualty |
| Scenario Authoring & Data | This depends on Scenario Authoring & Data | Injury loadouts and casualty archetype definitions are authored data, not hardcoded |
| Patient Assessment | Patient Assessment depends on this | Examine verbs read this system's ground-truth and physiology state |
| Triage System | Triage System depends on this | Global sort reads mobility/behavior state; individual assessment reads ground-truth category inputs |
| Treatment & Interventions | Treatment & Interventions depends on this | Interventions apply against this actor's injury loadout and physiology component |
| Casualty Facial Animation | Casualty Facial Animation depends on this | Facial AnimBP is attached to this actor and reads its physiology outputs |
| Scene & Zone Director | Scene & Zone Director depends on this | Casualty placement and behavior respond to zone state |

## Tuning Knobs

| Parameter | Current Value | Safe Range | Effect of Increase | Effect of Decrease |
|-----------|--------------|------------|-------------------|-------------------|
| Casualty pool size (POC) | 5–15 archetypes | [To be designed] | More scene complexity, higher perf cost | Simpler scene, less cognitive load |
| LOD promotion distance | [To be designed] | [To be designed] | | |

## Visual/Audio Requirements

| Event | Visual Feedback | Audio Feedback | Priority |
|-------|----------------|---------------|----------|
| Casualty promoted from Baked to Live LOD | [To be designed] — should be seamless/invisible to the trainee | [To be designed] | Medium |

## Game Feel

### Feel Reference

[To be designed]

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

[To be designed]

## Cross-References

| This Document References | Target GDD | Specific Element Referenced | Nature |
|--------------------------|-----------|----------------------------|--------|
| "Owns physiology component and LOD promotion" | `design/gdd/pulse-physiology-integration.md` | Live/baked physiology engine state | Data dependency |
| "Injury loadouts authored as data" | `design/gdd/scenario-authoring-data.md` | Casualty archetype definitions | Data dependency |
| "Global sort reads mobility/behavior state" | `design/gdd/triage-system.md` | Ambulatory/purposeful-movement/still state | Data dependency |
| "A casualty is promoted to Live LOD before its ground-truth category is used in a scored comparison" | `design/gdd/scoring-and-debrief.md` | Scored triage comparison | Rule dependency |
| "Casualty state/behavior model is part of a future external-platform plug-in deliverable" | `design/gdd/addendum-physiology-response-plugin.md` | Packaged casualty-response stack (Full Vision addendum, out of POC scope) | Ownership handoff |

## Acceptance Criteria

- [ ] GIVEN a casualty is untriaged and far from the trainee, WHEN the scenario is running, THEN that casualty runs on Baked LOD
- [ ] GIVEN the trainee approaches or begins assessing a casualty, WHEN the promotion trigger fires, THEN that casualty is promoted to Live LOD at the correct point in its trajectory
- [ ] GIVEN a casualty is on Baked LOD, WHEN the trainee applies a triage tag to it, THEN the casualty is promoted to Live LOD and its ground-truth category is reconciled from live physiology BEFORE the tag is scored
- [ ] Performance: System update completes within [X]ms — [To be designed]
- [ ] No hardcoded values in implementation — injury loadouts and archetype data are authored in `scenario-authoring-data.md`, not hardcoded in this system

## Open Questions

| Question | Owner | Deadline | Resolution |
|----------|-------|----------|-----------|
| Exact LOD promotion/demotion trigger (distance threshold vs. explicit action) | game-designer | Before Detailed Design is finalized | [To be designed] |
| Which UE construct implements the casualty actor (Blueprint class hierarchy, data asset composition)? | ue-blueprint-specialist | Phase 3 (Technical Setup) | → ADR (Phase 3) — not a GDD-time decision |
| Pillar-5 gating constraint (per product-owner direction (2026-07-16)): the ambulatory / purposeful-movement / still behavior-state derivation must gate on consciousness and hearing capability, not physical ambulation alone — a deaf or unconscious casualty must not auto-comply with a spoken global-sort command just because their legs work (see `game-concept.md` Pillar 5 design test; `triage-system.md` Core Rules) | game-designer | Before the mobility/behavior-state derivation ([To be designed]) is resolved | [To be designed] |

## Build Agents

The Engineering pair builds the casualty actor and its Tier-2 LOD arbiter, including the promote-on-approach trigger. The Content pipeline crew generates the casualty data file (W2-W3), which the Tier-2 archetype variants reuse. Mapped in the compiled GDD's build-time agent plan (§12.1).
