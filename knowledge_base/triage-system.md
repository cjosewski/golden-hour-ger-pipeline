# Triage System

> **Status**: Draft
> **Author**: game-designer
> **Last Updated**: 2026-07-15
> **Last Verified**: 2026-07-15
> **Implements Pillar**: Pillar 1 (Clinical truth under pressure), Pillar 3 (Doctrine, not heroics), Pillar 5 (The scene listens — communication is a mechanic; casualty-response side: the SALT global sort gates casualty compliance on ground-truth physiology — per product-owner direction (2026-07-16))

## Summary

The Triage System is how the trainee sorts casualties by survivability and
urgency using **SALT** (Sort, Assess, Lifesaving Interventions,
Treatment/Transport) as the primary modeled algorithm, with **START** (Simple
Triage and Rapid Treatment) specified as a later config option, not built in
the POC. Every casualty carries a **ground-truth triage category** derived
live from their Pulse physiology state — not a static, author-placed tag — so
a casualty who is Yellow at first assessment can decay to Red while the
trainee is elsewhere, and the scoring system compares the trainee's called
category against that live ground truth at the moment of tagging. This system
is the mechanical spine of the whole scenario: it is what the trainee is
*doing* for most of the session.

> **Quick reference** — Layer: `Core` · Priority: `MVP` · Key deps: `Patient Assessment, Casualty Model, Voice Command System, Pulse Physiology Integration (indirect, via Casualty Model)`

## Overview

Triage is the act of sorting many casualties by urgency when resources cannot
treat everyone immediately — it is the first and most decision-dense task the
trainee performs at every casualty cluster. In this game, triage happens in
two passes matching real SALT doctrine: a **global sort** across the whole
visible casualty group, driven by voice commands ("walk to me" / "wave your
arm"), which sorts casualties into rough response tiers before any hands-on
contact; and an **individual assessment** at each casualty, where the
trainee checks breathing, pulse/perfusion, mental status, and hemorrhage
control to arrive at one of five categories. The category is not fixed once
called — SALT explicitly allows and expects re-triage, and this game treats
that as core gameplay, not an edge case: a casualty's true state is always
live, computed by the physiology simulation, so time pressure and treatment
choices genuinely change who needs help most as the scenario unfolds.

Key facts driving this design:
- SALT is the current US national all-hazards MCI triage guideline (CDC/ACS/ACEP/NAEMSP-endorsed) and its global sort is voice-command-native ("walk/wave/still"), which maps directly onto this project's voice-input channel.
- SALT uses 5 categories (Immediate/Red, Delayed/Yellow, Minimal/Green, Expectant/Gray, Dead/Black) vs. START's 4 — the Expectant category is explicitly resource-dependent and still receives comfort care, which matters for Pillar 4 (safe to fail — the game must never frame "Expectant" as abandonment).
- START's RPM ("30-2-Can Do") thresholds — RR > 30, no radial pulse / cap refill > 2s, can't follow commands — are exactly the variables the Pulse Physiology Engine already computes, so triage logic is a direct read of physiology output, not a separate hand-authored system.
- Published benchmarks exist to score against: triage accuracy under-triage <5%, over-triage <50% (ACS COT); 30–60s per patient is standard, with one VR study measuring ~28s/patient in practice.

## Player Fantasy

You are the person who can look at a crowd of hurt strangers and, in seconds,
know who needs you *first*. It is not about saving everyone — it is about
making the hardest, fastest, most consequential judgment call in medicine,
correctly, again and again, while the scene refuses to hold still for you.
The tension is entirely diagnostic and moral, never combative: the enemy is
uncertainty and time, not a person. Getting it right feels like competence
under real pressure; getting it wrong is felt immediately (a casualty you
under-triaged visibly deteriorates) but never punished with shame — it
becomes the sharpest, most memorable line in your debrief.

## Detailed Design

### Core Rules

1. **Global sort (SALT Step 1) is voice-command-driven and happens once per
   casualty cluster**, before individual assessment begins:
   - Trainee issues (or the RTF/incident command issues on the trainee's
     behalf) the command "If you can hear me and need help, walk to me" —
     casualties whose ground-truth physiology supports ambulation (see
     `casualty-model.md` mobility state) walk toward the trainee's marked
     position. These are assessed **third**.
   - Trainee issues "Wave your arm" / "Make a purposeful movement" —
     casualties capable of purposeful movement but not walking respond. These
     are assessed **second**.
   - Casualties who do neither (still, or an obvious uncontrolled life
     threat visible at a distance, e.g., arterial bleeding) are assessed
     **first**.
   - This sort produces an **assessment order**, not a final category — it
     is a queue, not a tag.
2. **Individual assessment (SALT Step 2) follows a fixed decision sequence**
   at each casualty, performed via the Patient Assessment system's
   examine verbs:
   1. **Lifesaving Interventions first, if immediately available and within
      scope**: control major hemorrhage, open the airway (+ 2 rescue
      breaths if pediatric), needle decompression. These may be performed
      *before* a category is even assigned, per real SALT doctrine — the
      trainee is not required to withhold a life-saving action while
      completing a mental checklist. (SALT's lifesaving-interventions list
      also includes auto-injector antidotes, but that item is a CBRN
      countermeasure — it is explicitly non-actionable and not modeled in
      this ballistic active-shooter POC scenario; noted here only for
      doctrine completeness.)
   2. **Breathing check after airway opened**: if the casualty is not
      breathing even after airway repositioning, category = **Dead
      (Black)**. Stop.
   3. If breathing, the trainee (via examine verbs) checks four things:
      (a) obeys commands or shows purposeful movement, (b) peripheral pulse
      present, (c) not in respiratory distress, (d) major hemorrhage
      controlled.
   4. **All four true** → check for minor-injuries-only: if yes, category =
      **Minimal (Green)**; if no (injured but stable), category = **Delayed
      (Yellow)**.
   5. **Any of the four false** → apply the resource-availability check (see
      Formulas, Ground-Truth Category Derivation): likely to survive given
      currently available resources? If yes, category = **Immediate
      (Red)**; if no, category = **Expectant (Gray)**.
3. **The trainee's called category is a game action, separate from
   ground truth.** The trainee applies a ribbon (field triage, fast) or a
   full tag (at the Casualty Collection Point, secondary triage) that
   records *their* call. The scoring system (see `scoring-and-debrief.md`)
   compares this call against the casualty's live ground-truth category at
   the moment of tagging — it does not silently correct the trainee or
   block an incorrect tag. **Scoring-fairness rule**: per
   `casualty-model.md`'s scoring-fairness rule, a casualty is always
   promoted to Live LOD (full physiology reconciliation) before this
   comparison happens — the trainee's call is never scored against a merely
   pre-computed Baked-LOD checkpoint.
4. **Dynamic re-triage is always live, not a scripted event.** A casualty's
   ground-truth category is recomputed continuously from their Pulse
   physiology state (see Formulas below). A Yellow casualty with an
   unpacked internal injury can decay to Red while the trainee is treating
   someone else across the room; the game does not pause or notify the
   trainee of this — noticing it is the point.
5. **Full head-to-toe secondary assessment is out of scope during warm-zone
   triage.** Triage in the warm zone is a rapid pass; anything resembling a
   full workup during initial triage is a scored doctrine violation (see
   `scene-zone-director.md` zone-gated action rules).

### States and Transitions

| State | Entry Condition | Exit Condition | Behavior |
|-------|----------------|----------------|----------|
| Untriaged | Casualty spawns / trainee has not yet reached them | Trainee begins global sort or individual assessment | No tag applied; casualty AI runs ambient behavior (per `casualty-model.md`) — may call out, move, or lie still per ground-truth state |
| Sorted (queue position assigned) | Global sort command issued and casualty responds (walks/waves/still) | Trainee begins individual assessment on this casualty | Casualty has an assessment-order position but no category yet |
| Green / Minimal | Individual assessment resolves all-4-true + minor injuries only | Re-triage recomputation changes underlying physiology past a Green threshold | Ambulatory; self-directs to CCP if instructed; low animation/audio priority |
| Yellow / Delayed | Individual assessment resolves all-4-true + non-minor injuries | Re-triage recomputation decays to Red, or trainee/RTF extracts to CCP | Stable but requires monitoring; may deteriorate if untreated life threats remain |
| Red / Immediate | Individual assessment resolves any-4-false + survivable-with-resources | Extracted to CCP, stabilized (category may improve), or decays to Gray/Black if untreated past a time threshold | Highest visible distress (see `casualty-facial-animation.md`); RTF/trainee prioritizes extraction |
| Gray / Expectant | Individual assessment resolves any-4-false + not-survivable-given-resources | Resource availability changes (e.g., fewer competing Red casualties) may re-open Immediate eligibility; otherwise persists until scenario end | Still receives comfort care per doctrine; never abandoned in animation/audio framing — see Pillar 4 |
| Black / Dead | Not breathing after airway-opening attempt | Terminal — no exit | No further intervention; remains in scene for realism and doctrine-scoring purposes (e.g., CPR-on-traumatic-arrest-in-MCI is a scored doctrine violation, not a valid action) |

### Interactions with Other Systems

- **Patient Assessment** provides the examine verbs (check breathing, check
  pulse, check mental status, check hemorrhage) that the individual
  assessment decision tree in Core Rules Rule 2 consumes as input. Triage
  System does not implement its own sensing — it reads Patient Assessment's
  output.
- **Casualty Model** owns the casualty's ground-truth physiology state and
  the mobility/behavior state (ambulatory / purposeful-movement / still)
  that the global sort in Core Rules Rule 1 reads.
- **Voice Command System** resolves the global-sort commands ("walk to me",
  "wave your arm") and the trainee's spoken category call into game actions;
  Triage System defines the grammar's *meaning*, Voice Command System
  defines how the utterance is recognized and dispatched.
- **Treatment & Interventions** consumes the triage category and assessment
  findings to gate which MARCH-order interventions are contextually relevant
  next; conversely, treatment actions performed *during* SALT Step 2's
  lifesaving-interventions phase feed back into the physiology state this
  system reads.
- **Scene & Zone Director** gates *when* triage is permitted to happen at
  all (only in warm/cold zones) and can interrupt an in-progress assessment
  with a re-escalation event.
- **Scoring & Debrief** consumes every triage call (ribbon/tag applied,
  timestamp, ground-truth category at that moment) as its primary scored
  dataset — under-triage/over-triage rates and time-per-patient are computed
  entirely from this system's output.

## Formulas

### Ground-Truth Category Derivation

```
category = derive_salt_category(breathing, obeys_commands_or_purposeful_movement,
                                 peripheral_pulse_present, respiratory_distress,
                                 hemorrhage_controlled, survivable_with_resources,
                                 minor_injuries_only)
```

| Variable | Type | Range | Source | Description |
|----------|------|-------|--------|-------------|
| breathing | bool | true/false | Pulse Physiology Engine (respiration rate > 0 after airway-opened check) | Whether the casualty is breathing after one airway-reposition attempt |
| obeys_commands_or_purposeful_movement | bool | true/false | Pulse Physiology Engine (consciousness/LOC output) | SALT question (a) |
| peripheral_pulse_present | bool | true/false | Pulse Physiology Engine (perfusion output) | SALT question (b) |
| respiratory_distress | bool | true/false | Pulse Physiology Engine (respiratory rate, effort output) | SALT question (c) — inverted in the formula (question asks "NOT in distress") |
| hemorrhage_controlled | bool | true/false | Casualty Model (tracks whether an active-bleed injury has a successful intervention applied) | SALT question (d) |
| survivable_with_resources | bool | true/false | **[To be designed]** — needs an explicit resource model (see Open Questions) | Drives Immediate vs. Expectant split |
| minor_injuries_only | bool | true/false | Casualty Model injury loadout | Drives Minimal vs. Delayed split |

**Expected output range**: one of `{Green, Yellow, Red, Gray, Black}` (enum — see `proposed-registry-entries.md`)

**Worked example**: A casualty is breathing, does not obey commands
(unconscious), has a peripheral pulse, is not in respiratory distress, and
has an uncontrolled hemorrhage. Because one of the four SALT questions is
false (obeys_commands = false, hemorrhage_controlled = false), the formula
branches to the survivability check. If `survivable_with_resources = true`
(a tourniquet would very plausibly save this casualty), category = **Red**.

**Edge case**: `survivable_with_resources` is explicitly flagged
**[To be designed]** — SALT's real-world definition of this question is
resource- and judgment-based, not threshold-based (see Open Questions). Do
not hardcode this as always-true; it needs an explicit design decision before
the Expectant category can be authored honestly.

## Edge Cases

| Scenario | Expected Behavior | Rationale |
|----------|------------------|-----------|
| **If a casualty is untreated and their ground-truth category decays from Yellow to Red while the trainee is elsewhere**: | The casualty's visible state (facial animation, audio) updates immediately per the new category; no notification/alert is sent to the trainee | Dynamic re-triage is the point of the mechanic (Pillar 1) — the trainee must notice deterioration through observation, matching real MCI cognitive load, not through a UI nudge |
| **If the trainee attempts a full secondary assessment (head-to-toe workup) on a casualty while still in the warm zone**: | The action is permitted to execute (the trainee is never hard-blocked from an in-fiction action) but is logged as a scored doctrine violation and flagged in the debrief | Warm-zone scope is life-threats-only per TECC doctrine; blocking the action outright would remove player agency and contradict Pillar 4 (failure teaches, it doesn't gate) |
| **If two casualties are both Red and the trainee can only reach one before a re-escalation event forces extraction**: | Both remain Red; the untreated one's physiology continues to run and may decay to Gray/Black before extraction; this outcome is scored, not hidden or auto-resolved | Reflects real resource-scarcity consequences of MCI response; the scenario must not artificially rescue the trainee from the consequences of a real prioritization tradeoff |
| **If the trainee re-tags a casualty who already has a ribbon applied**: | Re-tagging is always permitted. A new ribbon overwrites the visible field call and is timestamped separately from the original; the trainee's LATEST call before extraction is what gets scored against ground truth. Every call (not just the latest) is retained in the session log for the debrief timeline. | Real SALT doctrine expects re-triage as conditions change; scoring only the final call before extraction matches how a real casualty is actually handed off, while retaining the full call history preserves the debrief's ability to show the trainee's reasoning arc, not just the outcome. |

## Dependencies

| System | Direction | Nature of Dependency |
|--------|-----------|---------------------|
| Patient Assessment | This depends on Patient Assessment | Individual-assessment decision tree consumes examine-verb outputs (breathing, pulse, mental status, hemorrhage checks) |
| Casualty Model | This depends on Casualty Model | Reads ground-truth physiology-derived state and mobility/behavior state for both global sort and individual assessment |
| Voice Command System | This depends on Voice Command System | Global-sort commands and spoken category calls are resolved through voice command grammar |
| Treatment & Interventions | Treatment & Interventions depends on this | Triage category and assessment findings gate which interventions are contextually surfaced next |
| Scene & Zone Director | This depends on Scene & Zone Director | Zone state gates whether triage/full-assessment actions are permitted or flagged as violations |
| Scoring & Debrief | Scoring & Debrief depends on this | Every triage call (ribbon/tag, timestamp, ground truth at that moment) is this system's primary scored data source |

## Tuning Knobs

| Parameter | Current Value | Safe Range | Effect of Increase | Effect of Decrease |
|-----------|--------------|------------|-------------------|-------------------|
| Respiratory rate "Red" threshold (RR) | 30 breaths/min | 25–35 | Fewer casualties trigger automatic Red via RR alone (more rely on the full 4-question check) | More casualties trigger automatic Red via RR alone, may over-triage |
| Capillary refill "poor perfusion" threshold | 2 seconds | 1.5–3.0 s | Stricter — more casualties flagged as poor perfusion (pushes toward Red) | Looser — fewer casualties flagged, may under-triage a shock casualty |
| Per-patient triage time target | 30–60 s | 20–90 s | More generous — trainee has more time before pacing pressure/scoring penalty | Tighter — closer to real field conditions but risks frustrating novice trainees |
| Tourniquet application pass window | ≤120 s | 60–180 s | More forgiving pass threshold | Matches "expert" real-world benchmarks more closely but may be unfairly strict for trainees |
| Re-triage recomputation cadence | **[To be designed]** — likely tied to Pulse's tick rate (~20–50 ms per `pulse-physiology-integration.md`), not a separate triage-specific value | — | — | — |

> **Provenance note (RR threshold)**: SALT's individual-assessment questions are qualitative ("is the casualty in respiratory distress?"), not numeric. The RR > 30 breaths/min threshold above is a START-protocol quantitative threshold, borrowed here as a reasonable, Pulse-computable operationalization of SALT's qualitative respiratory-distress question — pending acting SME confirmation that this operationalization is clinically appropriate for the SALT-primary model this game uses, since it is new to this product rather than carried over from prior SME-approved work (see Open Questions).

## Visual/Audio Requirements

| Event | Visual Feedback | Audio Feedback | Priority |
|-------|----------------|---------------|----------|
| Category called / ribbon applied | Colored ribbon with a distinct shape/pattern per category (colorblind-safe — shape/pattern/position redundancy, not color alone, since Red/Yellow/Green/Black/Gray is a known red-green-confusion palette) visibly ties onto casualty wrist/ankle; exact per-category shape/pattern is [To be designed] | Short confirmation tone distinct per category | High |
| Ground-truth category decays (e.g., Yellow → Red) while untreated | Casualty's facial/body animation state updates per `casualty-facial-animation.md` (no separate triage-specific VFX) | Casualty vocalization intensity increases per physiology state | High — this is the core "notice the deterioration" signal and must not be missed due to weak feedback |
| Doctrine violation logged (e.g., full workup attempted in warm zone) | **[To be designed]** — needs a decision on whether this is visible to the trainee in-the-moment at all, or debrief-only (see Pillar 4 — failure should not feel like a buzzer) | **[To be designed]** | Medium |

## Game Feel

### Feel Reference

Should feel like the triage sequence in a well-run mass-casualty *drill* —
fast, procedural, low-ceremony hand movements (tie a ribbon, check a pulse)
punctuated by moments of genuine diagnostic tension when a casualty's
presentation is ambiguous. NOT like a puzzle-game "identify the correct
answer" UI flow, and NOT like combat target-prioritization (no enemy-health-bar
framing).

### Input Responsiveness

| Action | Max Input-to-Response Latency (ms) | Frame Budget (at 90fps PC VR / 72fps Quest) | Notes |
|--------|-----------------------------------|------------------------|-------|
| Ribbon/tag application (hand interaction) | **[To be designed]** | **[To be designed]** | Should feel immediate — this is a physical grab-and-tie action, not a menu confirm |
| Voice-called category registers | **[To be designed]** — see `voice-command-system.md` latency budgets | — | Cross-reference — do not duplicate the authoritative number here |

### Animation Feel Targets

[To be designed]

### Impact Moments

| Impact Type | Duration (ms) | Effect Description | Configurable? |
|-------------|--------------|-------------------|---------------|
| Ribbon-tie confirmation | **[To be designed]** | Brief haptic pulse on the controller confirming a successful tie, distinct from a failed grab | Yes |
| Ground-truth decay crossing a category boundary | N/A — deliberately *not* punctuated with a strong effect | No jump-scare/alert; the trainee must notice through observation, not a triggered cue | No |

### Weight and Responsiveness Profile

- **Weight**: Light and fast for the physical ribbon-tie action itself; the *decision* leading up to it should feel weighty and consequential, not the hand motion.
- **Player control**: High — the trainee can always pause mid-assessment, back out, or re-approach; no committed/momentum-based interactions here.
- **Snap quality**: Crisp and binary for the tag-application confirmation; the underlying diagnosis is analog (a spectrum of physiology states), but the trainee's *call* is a discrete, binary action.
- **Acceleration model**: N/A — not a movement mechanic.
- **Failure texture**: An incorrect triage call must read as fair — the casualty's presentation genuinely supported a defensible (if wrong) call — and the correction happens in debrief, never via an in-scene penalty that feels arbitrary.

### Feel Acceptance Criteria

- [ ] Ribbon/tag application reads as a real, deliberate physical action, not a menu click, in VR controller mode (motion controllers only, per product-owner direction (2026-07-16) — see `vr-interaction-locomotion.md`)
- [ ] Playtesters can describe *why* they made a triage call without needing a tutorial prompt open
- [ ] No playtester describes a ground-truth deterioration as "the game changed the answer on me" — it should read as "I should have caught that sooner"

## UI Requirements

| Information | Display Location | Update Frequency | Condition |
|-------------|-----------------|-----------------|-----------|
| Current casualty's assessment findings (breathing/pulse/mental status/hemorrhage) as checked so far | World-space panel near the casualty (per project's world-space-only VR UI rule — no screen-space HUD) | On each examine-verb use | Only while actively assessing that casualty |
| Applied ribbon/tag color | Physical attachment on the casualty model itself — not a separate UI element | Once, on application | Persistent for the scenario |
| Running per-patient elapsed-time indicator | **[To be designed]** — needs a decision on whether trainees see a live timer (may add unwanted pressure/anxiety) or only see time-per-patient in the post-scenario debrief | — | — |

## Cross-References

| This Document References | Target GDD | Specific Element Referenced | Nature |
|--------------------------|-----------|----------------------------|--------|
| "Individual assessment consumes examine-verb outputs" | `design/gdd/patient-assessment.md` | Breathing/pulse/mental-status/hemorrhage check outputs | Data dependency |
| "Ground-truth category derives from live Pulse state" | `design/gdd/casualty-model.md` | Physiology-derived ground-truth state, mobility/behavior state | Data dependency |
| "Global sort and category calls resolved via voice grammar" | `design/gdd/voice-command-system.md` | Command grammar resolution | Rule dependency |
| "Triage category gates next relevant interventions" | `design/gdd/treatment-interventions.md` | Intervention contextual surfacing | State trigger |
| "Zone state gates whether triage actions are permitted" | `design/gdd/scene-zone-director.md` | Zone-gated action permissions | Rule dependency |
| "Every triage call feeds the scored dataset" | `design/gdd/scoring-and-debrief.md` | Under-triage/over-triage rate, time-per-patient calculation | Ownership handoff |
| "Ground-truth SALT variables (breathing, consciousness, pulse, respiratory distress) are read from live physiology output" | `design/gdd/pulse-physiology-integration.md` | Physiology output variables consumed by `derive_salt_category` | Data dependency |
| "A casualty is promoted to Live LOD before its ground-truth category is used for a scored comparison" | `design/gdd/casualty-model.md` | Scoring-fairness / LOD promotion rule | Rule dependency |

## Acceptance Criteria

- [ ] GIVEN a casualty is not breathing after one airway-reposition attempt, WHEN the trainee completes the breathing check, THEN the system assigns ground-truth category Black and blocks no further interaction attempt (interaction remains available but produces a logged doctrine-violation for further intervention, e.g., attempted CPR)
- [ ] GIVEN a casualty's four SALT questions all resolve true and injuries are minor, WHEN the trainee completes individual assessment, THEN ground-truth category = Green
- [ ] GIVEN a casualty is untreated and their physiology crosses a category-boundary threshold, WHEN the trainee is not present at that casualty, THEN the ground-truth category updates silently (no notification) and is reflected correctly the next time the trainee assesses or observes that casualty
- [ ] GIVEN the trainee issues the "walk to me" global-sort command, WHEN one or more casualties have a mobility state supporting ambulation, THEN those casualties path to the designated point and are queued for third-priority assessment
- [ ] GIVEN a completed scenario, WHEN the debrief computes triage accuracy, THEN under-triage rate and over-triage rate are calculated by comparing each trainee's LATEST call per casualty (before extraction) against the ground-truth category recorded at the moment of that tagging
- [ ] GIVEN a casualty already has a ribbon applied, WHEN the trainee applies a new tag before extraction, THEN the new tag overwrites the visible field call, is timestamped separately, and only the latest call before extraction is used for the under-triage/over-triage scoring calculation — all prior calls remain in the session log for the debrief timeline
- [ ] GIVEN the trainee is in the warm zone, WHEN they attempt a full head-to-toe secondary assessment/workup during initial triage, THEN the action is permitted to execute but is logged as a scored doctrine violation and flagged in the debrief
- [ ] Performance: Ground-truth category recomputation for all active casualties completes within [X]ms per tick — [To be designed] (depends on `pulse-physiology-integration.md` tick-rate budget)
- [ ] No hardcoded values in implementation — RR threshold, cap-refill threshold, and time targets are data-driven per this document's Tuning Knobs table

## Open Questions

| Question | Owner | Deadline | Resolution |
|----------|-------|----------|-----------|
| What is the explicit resource model behind `survivable_with_resources` — how does the system decide a casualty is Expectant rather than Immediate? | acting SME (project lead) + game-designer | Before Phase 2 (Systems Design) closes | [To be designed] |
| Should START be a fully modeled alternate algorithm in the POC, or only a documented future config option? | Producer / game-designer | Before this GDD is approved | Currently scoped as: SALT only in POC, START noted as later config (per `game-concept.md` MVP Definition) |
| Whether CCP secondary triage (re-triage at the Casualty Collection Point) has any additional mechanical distinction beyond a normal field re-tag — e.g., a distinct "secondary triage" action or UI treatment | game-designer | Before Detailed Design is finalized | [To be designed] |
| Which UE subsystem/data structure implements the ground-truth category state machine (Blueprint state machine vs. a data asset-driven approach)? | unreal-specialist / ue-blueprint-specialist | Phase 3 (Technical Setup) | → ADR (Phase 3) — not a GDD-time decision |
| Exact edition/date of the SALT guideline being modeled, for doctrine-currency purposes | acting SME (project lead) | Before any triage threshold is locked | [To be designed] |

## Build Agents

This system's Tier-2 build scope — ribbon application, the walk/wave/still
global sort, and one decay moment — is assigned to the Engineering pair. The
Design-review agent crew re-reviews the MVP scoring-semantics design work in
this document before that build work proceeds. Mapped in the compiled GDD's
build-time agent plan (§12.1).
