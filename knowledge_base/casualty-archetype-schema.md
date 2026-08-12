# Casualty-Archetype Schema — Interim Decision (VERB-01)

> **Task**: VERB-01 (`production/dev-plan-7-weeks-2026-07-17.md`, W2 table)
> **Owner**: Chad Josewski (product owner) + CC — recorded 2026-07-24
> **Authority**: dev-plan §W2 row VERB-01; feeds VERB-02/PULSE-11
> (`DT_CasualtyArchetypes` authoring) and PULSE-12 (`BP_Casualty` spawn)
> **Format note**: this is an **INTERIM, explicitly PRE-ADR** decision record —
> the dev-plan row states the deliverable IS an "interim decision note,
> explicitly pre-ADR," not a formal architecture decision. It records what was
> decided and why, in the lightest format that lets W2 proceed; it does not
> pre-empt whatever the eventual Phase-3 ADR on casualty-data architecture
> decides. This note also does not itself constitute a GDD change — every
> numeric value below traces to an existing GDD tuning knob or is explicitly
> flagged as a new placeholder needing its own SME/GDD pass.

## Ruling

`F_CasualtyArchetypeRow` is defined as a **flat, dual-field struct** — every
row carries both a **Pulse-reference group** (fields PRIMARY/F1 need to
configure and fire a live physiology engine) and a **baked-trajectory group**
(fields F2 needs to play back pre-authored curves) side by side, always
present, regardless of which physiology path (`production/decisions/2026-07-24-pulse-path-gate.md`)
is currently active. Struct location: `/Game/GoldenHour/Data/` (single content
root, one notation, per the task row). This struct becomes the row type for
`DT_CasualtyArchetypes` (VERB-02/PULSE-11) — every field below is a table
column.

## Why dual-field satisfies "same schema loads unchanged under primary / F1 / F2"

The acceptance criterion requires the schema to load **unchanged** no matter
which Pulse path is active. A schema that only carried live-engine fields
would need a breaking change (new fields, new row type, or a re-export) the
day F2 ever activates — and per the dev-plan's own capacity-check rows, F2
activation is a live possibility this project explicitly plans a relief valve
around, not a closed door (PRIMARY is committed per the 2026-07-24 gate, but
F1 stays a "proven, inactive backup" and F2 remains a defined fallback).
Carrying both groups from day one means:

- **Under PRIMARY/F1** (current path): the Pulse-reference group is read by
  `BP_Casualty` (PULSE-12) to configure and fire the live engine; the
  baked-trajectory group's string fields are simply empty and ignored.
- **Under F2** (if ever activated): `BP_TrajectoryPlayback` (PULSE-14) reads
  the baked-trajectory group; the Pulse-reference group is ignored.
- **No row migration, no schema version bump, no re-authoring of
  `DT_CasualtyArchetypes`** is needed to switch paths — only which fields a
  given `BPI_PhysiologySource` implementation reads changes, never the row
  shape. This is the dual-field schema acting as its own fallback, exactly as
  the task row's Fallback column states.

## Field Specification

Types are restricted to what the Nwiro/VibeUE editor tooling supports: bool,
int, float, byte, string, name, text, plus Vector/Rotator/Transform/Vector2D/
LinearColor and existing project structs. Every clinical numeric value is
marked **PLACEHOLDER** (clinically plausible placeholder — SME validation
pending, per `.claude/docs/coding-standards.md` and Risk 5 in the dev-plan's
risk register) unless noted as GDD-sourced.

### Group 1 — Pulse-reference (PRIMARY / F1 live-engine configuration)

| Field | Type | Default | Consumer | Purpose |
|---|---|---|---|---|
| `PulsePatientFileName` | string | `"StandardMale@0s"` | PULSE-12 | Named Pulse patient/state file this archetype initializes from. **Technical reference, not a clinical value** — string identifier, matches the exact patient proven live in the PULSE-07 W1 spike. *Open question: confirm this baseline patient matches the intended leg-hemorrhage casualty's demographics rather than being reused only because it's the proven spike identifier.* |
| `bApplyInitialVitalsOverride` | bool | `false` | PULSE-12, PULSE-15 | Gate: when true, the five `Initial*` fields below are applied over the patient file's own baseline at spawn; when false, the patient file's built-in baseline stands untouched. Exists so zeroed override fields are never silently misread as "start the casualty dead." |
| `InitialHeartRateBpm` | float | `71` — **PLACEHOLDER** (matches the proven PULSE-07 spike readout) | PULSE-12, PULSE-15 | Starting heart-rate override. |
| `InitialRespirationRateBpm` | float | `14` — **PLACEHOLDER** (invented, not spike-measured) | PULSE-12, PULSE-15 | Starting respiration-rate override. |
| `InitialSpO2Percent` | float | `97.4` — **PLACEHOLDER** (matches the proven PULSE-07 spike readout) | PULSE-12, PULSE-15 | Starting SpO2 override. |
| `InitialSystolicBP` | float | `114` — **PLACEHOLDER** (matches the proven PULSE-07 spike readout) | PULSE-12, PULSE-15 | Starting systolic blood-pressure override. |
| `InitialDiastolicBP` | float | `73` — **PLACEHOLDER** (matches the proven PULSE-07 spike readout) | PULSE-12, PULSE-15 | Starting diastolic blood-pressure override. |
| `HemorrhageInsultActionName` | name | `IED_Explosion` | PULSE-15 | The Pulse `ApplyAction` action name fired at scenario start to originate the hemorrhage insult. **Open question**: `IED_Explosion` is the only action proven live in the W1 spike (`production/decisions/2026-07-24-pulse-path-gate.md` PULSE-07 evidence) — confirm with the lead during PULSE-12/15 build whether this is the correct call for an isolated leg-hemorrhage archetype or whether a narrower hemorrhage-specific action exists in the Pulse action surface (tracked already as an open question in `treatment-interventions.md`). |
| `HemorrhageInsultMagnitude01` | float (0..1) | `0.6` — **PLACEHOLDER** | PULSE-15 | Magnitude passed to `ApplyAction` for the start-of-scenario hemorrhage insult; drives initial bleed severity. |

**Why five flat floats instead of one nested `F_VitalsSnapshot` field (revised
2026-07-24 during build)**: the original spec called for a single
`InitialVitalsOverride` field reusing the existing `F_VitalsSnapshot` struct.
The editor struct-creation tool does not actually support nested custom-struct
field types — it accepted the request and reported success, but silently
created the field as a plain `bool` instead (verified by reading the asset
back; there is no field-edit API to repair a wrong field in place, so the
struct was deleted and recreated). The lead's replacement — five explicit
scalar fields — turns out to be the better fit for this row's own job, not
merely a workaround: VERB-02's deliverable explicitly wants a CSV/JSON source
for `DT_CasualtyArchetypes`, and flat scalar columns are directly
CSV-authorable where a nested struct column is not. It also keeps the row flat,
which this schema's own design required throughout. `ConsciousnessLevel01` and
`PainLevel01` are deliberately **not** carried as initial-override fields: a
pre-insult baseline is definitionally alert and pain-free, and both are
physiology *outputs* of the pipeline (Stage 1 read / Stage 3 derived) rather
than archetype-authored inputs — carrying them here would misrepresent them as
authored config when they are computed state.

### Group 2 — Shared wound descriptor (read by both paths' presentation layer)

| Field | Type | Default | Consumer | Purpose |
|---|---|---|---|---|
| `HemorrhageSiteTag` | name | `LeftThigh_Femoral` — **PLACEHOLDER** | PULSE-12 (wound state), VERB-08 (tourniquet leg snap-volume placement) | Anatomical site of the hemorrhage; drives which limb's wound visual and tourniquet snap volume are active on `BP_Casualty`. Independent of which Pulse action fires — this is "where," the insult/cessation action names above are "what." |

### Group 3 — Baked-trajectory (F2 fallback configuration)

| Field | Type | Default | Consumer | Purpose |
|---|---|---|---|---|
| `UntreatedTrajectoryAssetPath` | string (soft-path workaround — see Type Notes) | `""` (empty — unused unless F2 activates) | PULSE-09, PULSE-14 | Path to the authored untreated curve-set asset (declining vitals, no intervention). |
| `TreatedTrajectoryAssetPath` | string (soft-path workaround) | `""` | PULSE-09, PULSE-14 | Path to the authored treated curve-set asset (post-tourniquet recovery branch). |
| `TrajectoryBranchPointSeconds` | float | `0.0` — **PLACEHOLDER** | PULSE-14 | Common-timebase point (seconds from trajectory start) at which `BP_TrajectoryPlayback.ApplyAction(tourniquet)` switches playback from the untreated to the treated curve set. |

### Group 4 — Treatment / secure-event tuning

| Field | Type | Default | Consumer | Purpose |
|---|---|---|---|---|
| `HemorrhageCessationActionName` | name | `TourniquetApplied` — **PLACEHOLDER** | PULSE-17 + VERB-09 | The Pulse `ApplyAction` action name fired when the tourniquet secure event completes — the "real Pulse hemorrhage-cessation action (1:1)" the row must name. **Open question** (already tracked in `treatment-interventions.md`): confirm the current Pulse Blueprint API surfaces this action. |
| `HemorrhageCessationMagnitude01` | float (0..1) | `1.0` — **PLACEHOLDER, not GDD-sourced (control input, not a clinical measurement)** | PULSE-17 + VERB-09 | Magnitude passed to `ApplyAction` on secure — full cessation by default; kept data-driven rather than hardcoded in case a partial-effectiveness tuning pass is ever wanted. |
| `HemorrhageControlledFlowThreshold` | float (mL/min) | `50.0` — **PLACEHOLDER, unit unconfirmed** | PULSE-17 + VERB-09 | The "data-driven threshold" named in the dev-plan's merge ruling (line 44): `hemorrhage_controlled` = action acknowledged **AND** bleed flow below this value. Per that same ruling, this field is **conditionally consumed** — if bleed flow is not cheaply readable on the surviving Pulse path, PULSE-17/VERB-09 degrades to action-acknowledged alone and this field goes unused; it is kept in the schema so that path is available without a schema change if flow does turn out to be readable. |
| `TourniquetPassWindowSeconds` | float | `120.0` (GDD-sourced: `treatment-interventions.md` Tuning Knobs, safe range 60–180s; matches the `tourniquet_pass_window` proposed registry constant) | VERB-08, scoring/debrief (later) | The tourniquet application pass window named directly in the VERB-01 task row. |

### Group 5 — Assessment-verb bands

| Field | Type | Default | Consumer | Purpose |
|---|---|---|---|---|
| `RespirationRateDistressThresholdBpm` | float | `30.0` (GDD-sourced: `triage-system.md` Tuning Knobs, safe range 25–35; matches the `respiratory_rate_red_threshold` proposed registry constant) | VERB-06 | The RR band boundary named in the task row — above this, Check-Breathing's finding reads "rapid/distress" (matches the GDD's own worked example, "Breathing: rapid (RR 34)"). |
| `PulseQualityWeakThresholdSystolicBP` | float (mmHg) | `90.0` — **PLACEHOLDER, not GDD-sourced (new)** | VERB-07 | Below this systolic BP, Check-Radial-Pulse's quality classification reads "weak." Not currently named as a number anywhere in the GDDs — added because VERB-07's row explicitly requires a normal/weak/absent quality band and no GDD yet supplies the cut points; needs its own SME/GDD pass. |
| `PulseQualityAbsentThresholdSystolicBP` | float (mmHg) | `70.0` — **PLACEHOLDER, not GDD-sourced (new)** | VERB-07 | Below this systolic BP, quality reads "absent" (not palpable). Same new-addition flag as above. |

### Group 6 — Expression bands (ground-truth hard-override thresholds only)

| Field | Type | Default | Consumer | Purpose |
|---|---|---|---|---|
| `ConsciousnessAlteredThreshold01` | float (0..1) | `0.5` — **PLACEHOLDER, not GDD-sourced (new)** | FACE-07 | Below this ConsciousnessLevel01 (and above the Unconscious threshold), the facial pipeline's Stage 7 selects the "Weak" expression state. Fills a slot `casualty-facial-animation.md` names but leaves `[To be designed]` ("altered" threshold). |
| `ConsciousnessUnconsciousThreshold01` | float (0..1) | `0.2` — **PLACEHOLDER, not GDD-sourced (new)** | FACE-07 | Below this, the hard-override rule forces the Unconscious expression state regardless of appraisal/pain. Fills the GDD's `[To be designed]` unconsciousness-threshold slot. |

**Scope boundary (deliberate)**: these two ground-truth consciousness cutoffs
are the only "expression band" fields on this row. The Stage 4 appraisal-scalar
thresholds (distress/fear cutoffs), per-emotion weights (`w1`/`w2`/`w3`), pain
acute-decay rate, and persona weight sets are all named in
`casualty-facial-animation.md` as pipeline-internal tuning that FACE-03's own
`DT_FacialExpressionMap` schema is tasked with owning (W3). Duplicating them
here would create two divergent sources of truth for the same pipeline stage.
The two fields above are included because they gate directly off Stage 1
**raw** physiology (`ConsciousnessLevel01`, already a live field on
`F_VitalsSnapshot`) per-casualty, not off a derived appraisal scalar — that
makes them legitimately archetype-level, unlike the rest of the pipeline's
tuning.

### Group 7 — Spawn/visual reference

| Field | Type | Default | Consumer | Purpose |
|---|---|---|---|---|
| `CasualtyCharacterAssetPath` | string (soft-path workaround) | `""` (to be filled once ART-01 delivers the asset) | PULSE-12 | Reference to the MetaHuman/character Blueprint this archetype spawns as — required for `BP_Casualty` to "spawn entirely from its archetype row" per the PULSE-12 task row. |

### Type-restriction notes

The editor tooling used to author this struct does not support UE's native
soft-object-reference pin types. Every asset reference above
(`UntreatedTrajectoryAssetPath`, `TreatedTrajectoryAssetPath`,
`CasualtyCharacterAssetPath`) is therefore typed as a plain `string` holding
the asset's content path (e.g. `/Game/GoldenHour/Data/Trajectories/...`), to be
converted to a soft reference at the call site (`TSoftObjectPtr`/
`ConvertToSoftObjectReference` or the Blueprint `Load Asset` node) rather than
on the struct itself. This is a workaround, not the ideal representation —
flagged here so the eventual ADR can decide whether to promote these to native
soft-reference fields once the tooling limitation is resolved.

#### PACKAGING EXPOSURE — string paths are invisible to the cooker

*(Recorded 2026-07-24 at VERB-01 review; must be closed before the **Fri Aug 21
W5 packaged-build gate**, QA-09/PROD-24.)*

Because these three fields are plain `string`s and not real references, the
Asset Registry and the cooker have **no knowledge that they point at content**.
A standard reference-driven package build will therefore **not stage the assets
they name**, and the failure appears only in a cooked build — never in the
editor — as a null load at spawn time. This is the same *category* of risk as
Consequence #1 in `2026-07-24-pulse-path-gate.md` (packaged Pulse data root,
logged there as the top integration risk), and it is tracked here so the two
get closed together.

The three fields are **not equally exposed**:

- `CasualtyCharacterAssetPath` — **the near-term one.** It is not F2-gated:
  PULSE-12 uses it on *every* path, and it gets populated as soon as ART-01
  lands (this week). *(This dated 2026-07-24 line is left standing as
  originally written, per this repo's practice for decision records; see the
  **Addendum — 2026-07-26** at the end of this document for what actually
  happened and the path-location divergence it created.)*
- `UntreatedTrajectoryAssetPath` / `TreatedTrajectoryAssetPath` — dormant while
  PRIMARY is the committed path; they only carry values if F2 activates.

**Near-term mitigation (cheap, do at QA-02 packaging first light):** add
`/Game/GoldenHour/Characters/` (and `/Game/GoldenHour/Data/Trajectories/` if F2
ever activates) to Project Settings → Packaging → *Additional Asset Directories
to Cook*, so the content is staged regardless of reference tracking.
**Eventual fix:** promote these fields to native soft-object references — see
open question 7.

## Build verification (recorded 2026-07-24, after struct creation)

`F_CasualtyArchetypeRow` has been created in the editor. Everything in this
spec was built verbatim except the `InitialVitalsOverride` field (see the
flattening note under Group 1 above). Three things surfaced during creation
that are load-bearing for VERB-02 and are recorded here rather than only in
chat history:

1. ~~**BLOCKING pre-step for VERB-02 — stray generated field must be deleted by
   hand first.**~~ **✅ CLEARED 2026-07-24** — Chad deleted `MemberVar_0` by
   hand and saved; verified by read-back (the struct now reports exactly **23**
   fields, beginning with `PulsePatientFileName`) and on disk (asset shrank
   30,957 → 29,848 bytes, fresh mtime). VERB-02 is unblocked. The original
   text is kept below because the underlying tooling defect is unfixed and will
   recur on the next struct created this way.
   The struct carried a 24th, engine-generated `MemberVar_0`
   bool that sorts as the struct's *first* field. There is no removal API for
   it; it must be deleted by hand in the struct editor. If VERB-02 authors
   `DT_CasualtyArchetypes` before this is deleted, `MemberVar_0` becomes a
   phantom first column in the table and in its CSV/JSON source — this is a
   blocking pre-step for VERB-02, not a cosmetic cleanup item.
   **Scope of the gate** (broadened at review): delete it before *any* of —
   (a) VERB-02/PULSE-11 authoring `DT_CasualtyArchetypes`, (b) any Blueprint
   wiring Break/Make nodes against this struct (PULSE-12 onward), or (c) the
   A4 content pipeline (VERB-03/PROD-13, due Aug 6) regenerating this data
   file and diffing it against the hand-authored row. The plan's own
   dependency order already puts VERB-02 first, so honouring the gate there
   protects all three — this is stated for a reader who hasn't traced the
   whole chain. *(Note: the same stray-field defect on `F_VitalsSnapshot` was
   correctly logged as merely cosmetic during PULSE-10 — that struct is only
   ever read live through Break nodes and never externalized to CSV. The
   escalation to blocking here is because this one becomes table columns.)*
2. **The dual-field acceptance path is proven end-to-end.** An editor-made
   struct of this shape IS accepted as a `DataTable` row type: a throwaway
   `DataTable` was created against `F_CasualtyArchetypeRow`, all 23 authored
   columns came through in the correct order and types, and the throwaway
   table was then deleted. This directly de-risks VERB-02/PULSE-11's build.
   Separately, the `search_row_structs` discovery tool does **not** list
   editor-made structs when searching for row-struct candidates — this is a
   tooling *discovery* blind spot, not a real DataTable-compatibility
   limitation, and VERB-02 should not read a missing search result as this
   struct being unusable as a row type.
3. **`ApplyAction`'s `ActionName` parameter is confirmed `Name`-typed** (set
   directly while wiring the struct). This resolves Open Question 1 below —
   `HemorrhageInsultActionName` and `HemorrhageCessationActionName` being
   typed `name` in this spec is correct as authored; no change needed.

Final built shape: **23 authored fields** (this spec originally called for
19; the `InitialVitalsOverride` flattening added 5 fields in place of 1,
net +4).

## Deliberately excluded (no named consumer in this task's scope)

- **Casualty staging height** (`scenario-authoring-data.md`: raised litter/
  gurney/bench, 40–70cm, per product-owner direction 2026-07-16) — clearly
  named as a per-casualty archetype property in that GDD, but its only named
  consumer (VR-15 grab-tolerance tuning, `vr-interaction-locomotion.md`
  kneel-and-treat ergonomics) is outside this task's researched task list.
  Excluded per the "every field serves a named downstream task" discipline
  rule, flagged here so it is not silently forgotten — likely belongs on this
  same row in a follow-up pass once VR-15 is in scope.
- **Persona/temperament weight-set selector** — `casualty-facial-animation.md`
  names casualty temperament (stoic/anxious/bravado/fatalism) as a per-casualty
  property expressed as Stage 5/6 weight-set bias. No W2–W4 build task in this
  plan (FACE-06, FACE-07) currently consumes a persona field — both are scoped
  to the pain model and consciousness/Unconscious-override logic only, with no
  persona branching. `PersonaTemperament` was considered as a `name` field but
  not added. Excluded for the same discipline reason; flagged for a later
  schema revision if/when persona weighting enters build scope.
- **Capillary refill threshold** (`triage-system.md` /
  `proposed-registry-entries.md`: `capillary_refill_poor_perfusion_threshold`,
  2.0s) — real and GDD-sourced, but PULSE-16's live-query function set is
  `GetRespiratoryRate` / `GetRadialPulse` only; no capillary-refill query or
  `F_VitalsSnapshot` field exists to threshold against yet. Excluded; flagged
  as a gap for whoever eventually builds a capillary-refill assessment path.
- **Multiple hemorrhage sites per casualty** — this row models exactly one
  hemorrhage site/insult/cessation triple, matching the POC's single Tier-1
  row and the "IED leg-hemorrhage casualty" scenario. If a later Tier-2
  archetype (T2-04, "+2 archetype rows") needs a casualty with more than one
  wound, this schema does not yet support it — flagged as an open question,
  not solved here.
- **Pulse engine tick rate / vitals-poll cadence** (PULSE-13) — confirmed
  system-level config, not named as a per-archetype property anywhere; no
  field added.

## Placeholder-labeled clinical values and their sources

| Value | Default | GDD source | Status |
|---|---|---|---|
| Tourniquet pass window | 120s | `treatment-interventions.md` Tuning Knobs; registry `tourniquet_pass_window` | GDD-sourced placeholder |
| RR distress threshold | 30 bpm | `triage-system.md` Tuning Knobs; registry `respiratory_rate_red_threshold` | GDD-sourced placeholder |
| Initial HR / RR / SpO2 / SBP / DBP (`InitialHeartRateBpm`, `InitialRespirationRateBpm`, `InitialSpO2Percent`, `InitialSystolicBP`, `InitialDiastolicBP`) | 71 bpm / 14 bpm / 97.4% / 114 mmHg / 73 mmHg | HR/SpO2/SBP/DBP match the PULSE-07 W1 spike measured readout (`2026-07-24-pulse-path-gate.md`); RR is invented, not spike-measured | Spike-measured (HR/SpO2/BP) or invented (RR), not clinically authored — still labeled placeholder pending SME review of whether it's the right *starting* point for this archetype |
| Hemorrhage insult magnitude | 0.6 | None — invented | New placeholder |
| Hemorrhage cessation magnitude | 1.0 | None — invented | New placeholder (a normalized control input to `ApplyAction`, not a clinical measurement — but listed here so no numeric default in this row escapes the labelling rule) |
| Hemorrhage-controlled flow threshold | 50 mL/min | None — invented, unit unconfirmed | New placeholder |
| Pulse-quality weak/absent SBP cut points | 90 / 70 mmHg | None — invented | New placeholder |
| Consciousness altered/unconscious cut points | 0.5 / 0.2 | Slot named (not valued) in `casualty-facial-animation.md` | New placeholder |

All of the above must carry the "clinically plausible placeholder — SME
validation pending" label wherever surfaced (per QA-08's audit and Risk 5 in
the dev-plan risk register) until an acting clinical SME reviews them.

## Open questions for the eventual ADR

> **Urgency tags** (added at review, 2026-07-24 — the pulse-path-gate decision
> ranks and dates its consequences; these do the same so nothing drifts):
> **Q2/Q3 are the soonest** — if those Pulse action names don't exist, PULSE-15
> and PULSE-17 break, so confirm them against the live action surface during
> PULSE-12 (this week), not at ADR time. **Q7 is gate-dated** — it is the
> permanent fix for the packaging exposure above and must at minimum have its
> cheap mitigation applied before the **Fri Aug 21** packaged-build gate.
> Q4/Q5/Q6/Q8 are genuinely ADR-time questions with no W2–W5 deadline.

1. ~~Does `BPI_PhysiologySource.ApplyAction`'s `ActionName` parameter take
   `FName` or `FString`?~~ **RESOLVED 2026-07-24** — confirmed `Name`-typed
   during struct build (see Build Verification above); this spec's `name`-typed
   action-name fields are correct as authored.
2. ~~Is `IED_Explosion` the correct Pulse action for an isolated leg-hemorrhage
   archetype, or does a narrower hemorrhage-only action exist in the Pulse
   action surface? (Carried from `treatment-interventions.md` Open Questions.)~~
   **CLOSED 2026-07-29 for the current wrapper — answer NO** (see the
   Addendum — 2026-07-29 at the end of this document, item 2).
3. ~~Does `HemorrhageCessationActionName`'s default (`TourniquetApplied`) exist
   as a callable Pulse action at all? Same open question, treatment side.~~
   **CLOSED 2026-07-29 for the current wrapper — answer NO** (Addendum —
   2026-07-29, item 3).
4. Should the two new pulse-quality SBP cut points and the two new
   consciousness cut points be promoted into
   `design/registry/entities.yaml`/`proposed-registry-entries.md` now that
   they have a concrete first value, or held until SME review?
5. Should staging height and persona/temperament be added to this same row in
   a follow-up pass, or live on a separate authoring table?
6. Multi-hemorrhage-site casualties (Tier 2, T2-04) — extend this row format,
   or introduce a second row/array-of-struct pattern once that need is real?
7. Soft-reference workaround fields (Group 3, Group 7) — promote to native
   soft-object-reference pins once/if the editor tooling supports authoring
   them directly?
8. Should the five flat `Initial*` vitals-override fields be re-consolidated
   into a nested struct field later, if/when the editor tooling gains real
   custom-struct-field support — or is the flat CSV-authorable shape the
   better permanent design regardless of tooling capability (see the Group 1
   flattening rationale)?
9. The struct-creation tool silently mistyping a nested-struct field as `bool`
   instead of erroring, and the still-unremovable stray `MemberVar_0` field,
   are both editor-tooling defects worth a bug report to whoever maintains the
   Nwiro/VibeUE tooling — not a schema question, but recorded here so it isn't
   lost.

None of the above change any GDD; they are implementation-detail and
prioritization questions for the Phase-3 ADR this note explicitly defers to.

## Addendum — 2026-07-26 (`CasualtyCharacterAssetPath` path location — found and resolved same day)

*(Added as a dated addendum rather than editing the 2026-07-24 lines above,
per this repo's practice for decision records. Heading corrected in place
2026-07-26 later the same day — see the second correction below — because a
heading has no "below" for a reader who reaches it via an outline, grep, or a
cross-reference; the earlier heading wording asserted a location problem that
is now resolved. The body text underneath is left untouched; nothing in the
history below is lost.)*

**Product-owner ruling, verbatim (2026-07-26)**: "Casualty assets are
preliminar[y] place-holders and still need work. But they are good enough to
free the blockers." Verified directly against `git show --stat e1d86fd`
("Prelim Casualty assets."): the committed files are
`Content/Metahumans/Casualty_01.uasset`, `Civilian02/03/04.uasset`, and
`HandsomeMan.uasset` — i.e. `/Game/Metahumans/...`.

**SUPERSEDED — see the two corrections below.** The next two paragraphs
record the divergence exactly as it was written the moment the ruling landed,
including a citation error in the second one — left standing for the record,
not because either is still accurate.

**This is not a future risk — the divergence exists today.** This document's
own §"PACKAGING EXPOSURE" above, and the dev-plan's ART-01 row
(`production/dev-plan-7-weeks-2026-07-17.md`), both name
`/Game/GoldenHour/Characters/CasualtyT1/` (or `/Game/GoldenHour/Characters/`)
as ART-01's specified delivery location. The assets that actually landed
2026-07-26 are under `/Game/Metahumans/`, not under either of those paths.
That divergence is present and documented now, not a contingency that "would"
happen if final art later landed somewhere different — the placeholders
already did.
*(CORRECTED below: the "(or `/Game/GoldenHour/Characters/`)" parenthetical in
this paragraph is itself the citation error — see the second correction.)*

**Consequence for the near-term mitigation above**: the "Additional Asset
Directories to Cook" entry recorded above (`/Game/GoldenHour/Characters/`)
does **not** cover where the placeholders currently sit
(`/Game/Metahumans/`). Whoever closes the QA-02 packaging step must add
`/Game/Metahumans/` (or whatever path is actually referenced in the CSV at
that time) alongside `/Game/GoldenHour/Characters/`, not instead of it — both
this document and the dev-plan still specify `/Game/GoldenHour/Characters/`
as ART-01's target, and that has not been amended.

**Full detail, including the two live mitigation options for the CSV path
this creates, is recorded in
`assets/data/GoldenHour/DT_CasualtyArchetypes.notes.md` and
`production/session-state/active.md` (dated 2026-07-26 entries in both) — not
duplicated here to avoid drift between three copies.**
*(This "two live mitigation options" framing is also superseded — see the
second correction below for why only one path is now live.)*

### Correction — later the same day, 2026-07-26: the divergence above was resolved, not left standing

*(This corrects the addendum above forward rather than deleting it — the
sequence "divergence found, then resolved same day by moving the assets" is
the reason the risk cost nothing to close, and is worth keeping on the
record. **This entire subsection is itself further corrected below** — it
contains a citation error about what this document permits, and the assets
moved again after it was written.)*

Verified directly against `git status --short` and a folder check on disk at
the time: Chad moved all five placeholder assets. They were staged, at that
moment, as adds under `Content/GoldenHour/Characters/` (`Casualty_01`,
`Civilian02/03/04`, `HandsomeMan`) and staged as deletes from
`Content/Metahumans/`. **That intermediate staged state never itself became
a commit** — the assets moved again before commit (see the second correction
below); the permanent record is the eventual commit, not this transient
index state.

**~~The new location is in spec — with one small, non-defect nuance.~~
CORRECTED — this claim is wrong; see the second correction below.** This
paragraph originally asserted that "this document's own packaging-exposure
section (above) explicitly permits `/Game/GoldenHour/Characters/CasualtyT1/`
**or** `/Game/GoldenHour/Characters/`," citing that as pre-existing authority
for treating the parent folder as compliant. That citation does not hold up:
verified directly against `git show e1d86fd:production/decisions/2026-07-24-casualty-archetype-schema.md
| grep -n "GoldenHour/Characters"` (pinned to the commit this was actually
checked against — not `HEAD`, which contains this very addendum and would
return several hits, making the citation appear to disprove itself) — the
committed version of this document, as it stood at `e1d86fd`, names
`/Game/GoldenHour/Characters/` exactly once, in the **Additional Asset
Directories to Cook** cook-directory mitigation, not as a delivery-location
permission. That version of the doc specifies **no delivery folder at
all** for these assets; the dev-plan's ART-01 row is the only document that
names one, and it names `/Game/GoldenHour/Characters/CasualtyT1/` specifically,
not the parent. The "or the parent folder is also permitted" wording was
introduced by this same addendum, then cited back a paragraph later as if it
were pre-existing authority — a self-citation, not a source. Retracted; do
not cite "or `/Game/GoldenHour/Characters/`" as permitted by this document
going forward.

**It also lands inside the packaging mitigation already planned — planned,
not active.** The "Additional Asset Directories to Cook" entry described
earlier in this same section names `/Game/GoldenHour/Characters/` as a
directory to add at QA-02. Verified directly: `Config/` and
`UEAS_01.uproject` contain no cook-directory setting at all today — this
protection is **on the books for QA-02, not in effect**. Since the recorded
entry names the parent folder, and (on the ordinary reading of a
directories-to-cook setting) a parent-folder entry also covers its
subfolders, this entry would cover the assets' current subfolder location
too, once it is actually implemented at QA-02 — stated here as a reading to
confirm at that time, not as a fact already in force.

**It was done at the cheapest possible moment.** `CasualtyCharacterAssetPath`
is still empty in the CSV, so nothing referenced these assets yet — there was
nothing to redirect, and no leftover redirector stubs, since the old folder
is gone entirely rather than emptied. Moving these assets after the CSV path
had already been filled in would have been the expensive version of this
same move; doing it first is why it was free. *(This held for this move and
held again for the second move below — same reasoning both times.)*

**The mitigation guidance in the "Full detail, including the two live
mitigation options for the CSV path this creates..." paragraph of the
original Addendum above (not the paragraph immediately preceding this one)
is now obsolete** — there is no live path divergence to choose between
"pin the placeholder location" and "require a checklist step," because the
assets already sit inside `/Game/GoldenHour/Characters/`. **This paragraph is
itself further superseded — see the second correction below**, since the
assets moved one level deeper the same day, to the exact subfolder the
dev-plan names.

**ART-01 status is unaffected by this move.** These are still preliminary
placeholders, not signed-off look-dev art; ART-01 itself remains open and
its checklist item stays unticked. The move changed *where* the placeholders
live, not whether ART-01 is complete. *(Remains true after the second move
below as well.)*

### Second correction — later still the same day, 2026-07-26: moved again, now matching the dev-plan exactly; no divergence remains; now committed

Chad moved the assets one level down, and the move is **committed as
`142b1c4`** ("chore(assets): relocate preliminary casualty placeholders to
CasualtyT1") — verified directly via `git show --stat 142b1c4`: **5 adds + 5
deletes** (`Content/GoldenHour/Characters/CasualtyT1/Casualty_01.uasset`,
`Civilian02/03/04.uasset`, `HandsomeMan.uasset` added; `Content/Metahumans/`'s
five matching files removed). Also verified directly via
`find Content/GoldenHour/Characters -type f`: all five assets sit under
`CasualtyT1/` on disk; nothing remains at the parent
`Content/GoldenHour/Characters/` level; `Content/Metahumans/` is gone.
This matches the dev-plan's ART-01 row exactly
(`/Game/GoldenHour/Characters/CasualtyT1/`, `production/dev-plan-7-weeks-2026-07-17.md`
row 94). **No path divergence remains.**

**The honest three-step sequence, recorded in full rather than collapsed**:

1. Placeholders first landed under `/Game/Metahumans/` — out of spec (matched
   neither the dev-plan row nor this document, which specifies no delivery
   folder at all).
2. Moved to `/Game/GoldenHour/Characters/` — closer, but still not the
   `CasualtyT1/` subfolder the dev-plan row names. (The Correction section
   above incorrectly called this step "in spec" by citing this document as
   permitting the parent folder; this document permits no delivery folder,
   so that step was still a divergence from the dev-plan row, just a
   smaller one than step 1. Retracted above.)
3. Moved to `/Game/GoldenHour/Characters/CasualtyT1/` — in spec, matches the
   dev-plan row exactly.

**Fill path, current and final unless the row's asset changes again**: fill
`CasualtyCharacterAssetPath` with
`/Game/GoldenHour/Characters/CasualtyT1/Casualty_01` — still naming that
asset specifically, since the other four committed placeholders
(`Civilian02/03/04`, `HandsomeMan`) are other MetaHuman samples, not this
row's casualty. ART-01's eventual completion checklist should confirm the
final, signed-off art lands at this same path so the reference does not
break later; the underlying hazard is unchanged (a plain string nothing
type-checks, breaking silently and surfacing only in a packaged build) —
only today's specific mismatch is gone. ART-01 itself remains open and not
complete; only the path location changed.

## Addendum — 2026-07-29 (PULSE-12 build: Group 1 gate semantics corrected; Open Q2/Q3 closed for the current wrapper)

*(Dated addendum per this repo's practice; the earlier text is left
standing. Authority: `production/decisions/2026-07-29-pulse-12-build-spec.md`
(v2, adversarially reviewed), which builds `BP_Casualty` against the live
plugin surface.)*

1. **`bApplyInitialVitalsOverride` (Group 1) — the documented
   apply-over-baseline semantics are NOT implementable on the current Pulse
   BP surface.** The exposed component API initializes from whole
   state/patient files only; there is no per-vital setter. At PULSE-12 the
   gate's live semantics are **validate-warn only**: when true,
   `BP_Casualty` warn-logs any divergence between the live engine's
   first-step vitals and the row's five `Initial*` values (>10% relative,
   row units); nothing is applied. The five values remain useful as the
   authored expectation record; rows wanting genuinely different starting
   vitals need a new Pulse state file until a vendor-side setter lands
   (tracked in the vendor-feedback doc). `DT_CasualtyArchetypes.notes.md`
   carries the matching addendum. Also recorded there: the row's
   `InitialRespirationRateBpm` was aligned 14 → 11 (spike-measured baseline)
   so the validate-warn is silent on a clean spawn.
2. **Open Q2 — CLOSED for the current wrapper (answer: NO).** No narrower
   hemorrhage action exists on the exposed surface; the only path to
   bleeding is the hardcoded, parameterless `IED_Explosion()`
   (vendor-feedback Finding 1). `HemorrhageInsultActionName` stays correct
   as data; the magnitude field is inert until the vendor ask lands.
3. **Open Q3 — CLOSED for the current wrapper (answer: NO)**, confirming
   the urgency tag's fear: `TourniquetApplied` does not exist as a callable
   action. `BP_Casualty.ApplyAction` rejects it (returns not-accepted) with
   a log; PULSE-17 owns cessation semantics when the vendor exposes the
   call (headline ask in the vendor-feedback doc).
4. **Group 7 `CasualtyCharacterAssetPath` discovery**: the filled asset
   (`/Game/GoldenHour/Characters/CasualtyT1/Casualty_01`) is an
   **unassembled `MetaHumanCharacter` authoring asset**, not the "character
   Blueprint this archetype spawns as" this field anticipated — no such
   Blueprint exists yet. `BP_Casualty` registry-classifies the reference
   and falls back to a placeholder visual until MetaHuman assembly produces
   a spawnable output (PULSE-12 spec §3.5; product decision 2026-07-29).
