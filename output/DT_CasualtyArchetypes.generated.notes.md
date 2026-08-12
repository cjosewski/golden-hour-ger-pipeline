# `DT_CasualtyArchetypes.generated` — CSV Source Notes

> **Sibling file**: `DT_CasualtyArchetypes.generated.csv` — 6 accepted row(s)
> **Produced by**: this repo's GER pipeline, offline mode, model `offline-deterministic-fixture`
> **Run at**: 2026-08-12T23:31:08+00:00
> **Schema authority**: `knowledge_base/casualty-archetype-schema.md` (`F_CasualtyArchetypeRow`, 23 authored fields in Groups 1–7; the DataTable adds the engine's own `Name` key column, which is why the CSV has 24)
> **Rule enforced on every row below**: `knowledge_base/triage-system.md` § Formulas — Ground-Truth Category Derivation

Why this is a sibling file rather than a comment block inside the CSV: `knowledge_base/data-files.md` § Carve-out states that "Unreal's CSV importer has no comment syntax — the first row is always literal headers", and instructs authors to "put per-value sourcing/placeholder documentation in a sibling `<Name>.notes.md`, never inline". The hand-authored table in the game repo ships one of these; the generated table now does too.

There is a second reason specific to this pipeline. Five things below are **not columns of the 24-column CSV**, and each is absent for its own documented reason, so all five live here instead, next to the file they describe.

1. `AuthoringNote`. Rule R3 requires every generated row to carry the "clinically plausible placeholder — SME validation pending" label on it, and the CSV has nowhere to put it.
2. The declared SALT category. Deliberately absent: `triage-system.md` § Summary keeps the ground-truth category "derived live from their Pulse physiology state — not a static, author-placed tag".
3. `InitialConsciousness01`. Also deliberately absent, and the one most likely to be misread as an oversight, because it is the **sole input to SALT question (a)** — whether the casualty obeys commands or shows purposeful movement. `knowledge_base/casualty-archetype-schema.md` § Group 1 excludes it from the row on purpose: "`ConsciousnessLevel01` and `PainLevel01` are deliberately **not** carried as initial-override fields: a pre-insult baseline is definitionally alert and pain-free, and both are physiology *outputs* of the pipeline (Stage 1 read / Stage 3 derived) rather than archetype-authored inputs — carrying them here would misrepresent them as authored config when they are computed state." So the value below is authoring *intent* used to derive ground truth, never a shipped column, and the per-row lists say "vitals and authoring intent" rather than "vitals" for that reason.
4. `bMinorInjuriesOnly` — the Green-vs-Yellow split. `triage-system.md` § Detailed Design — Core Rules, rule 2.4: "**All four true** → check for minor-injuries-only: if yes, category = **Minimal (Green)**; if no (injured but stable), category = **Delayed (Yellow)**." Nothing on the row represents the injury loadout that check reads, so it is authored per row.
5. `bSurvivableWithResources` — the Red-vs-Gray split, and the field this run's one escalation turns on. `triage-system.md` § Formulas flags it **[To be designed]**: "Do not hardcode this as always-true; it needs an explicit design decision before the Expectant category can be authored honestly." So it is authored per row and never inferred here.

## Placeholder-labelling status of every generated row

Every clinical value in the sibling CSV — every vital sign, every threshold band — was invented by a generator role. **No clinician has reviewed any of them.** They are clinically plausible placeholders with SME validation pending, and they must be treated as such until an acting clinical SME reviews them.

| Row | Declared | Derived from the row's own vitals | Refines | Placeholder label |
|---|---|---|---|---|
| `Casualty_IED_LegHemorrhage_T1_Gen` | Red | Red | 0 | present |
| `Casualty_Ambulatory_ForearmLac` | Green | Green | 1 | present |
| `Casualty_TensionPneumo_Chest` | Red | Red | 1 | present |
| `Casualty_Abdominal_Evisceration` | Yellow | Yellow | 1 | present |
| `Casualty_BlastApnea_Black` | Black | Black | 1 | present |
| `Casualty_FlashBurn_Forearms` | Yellow | Yellow | 1 | present |

Declared and derived agree on every shipped row — that agreement is what R1 checks, and a row where they disagree is not written to the CSV.

## Per-row authoring notes, verbatim

### `Casualty_IED_LegHemorrhage_T1_Gen`

- **Request**: `ied_leg_hemorrhage_t1` (asked for Red) — accepted on the first draft
- **Authoring note**: Tier-1 IED femoral hemorrhage. Vitals are a clinically plausible placeholder — SME validation pending; compensating shock picture with an uncontrolled arterial bleed, tourniquet-salvageable.
- **Placeholder label**: present
- **Pulse patient file**: `StandardMale@0s` · **vitals override gate**: True
- **Vitals and authoring intent**: HR 117 · RR 22 (distress threshold 30) · SpO2 94% · BP 96/58 (pulse-absent below 70) · consciousness 0.85 (altered below 0.5) · hemorrhage insult 0.6 · tourniquet window 120s · survivable True · minor-injuries-only False

### `Casualty_Ambulatory_ForearmLac`

- **Request**: `ambulatory_lac_forearm` (asked for Green) — accepted after 1 refine attempt(s)
- **Authoring note**: Walking wounded with a superficial forearm laceration, self-controlled with direct pressure. Fully alert and ambulatory. All clinical values here are a clinically plausible placeholder — SME validation pending.
- **Placeholder label**: present
- **Pulse patient file**: `StandardMale@0s` · **vitals override gate**: True
- **Vitals and authoring intent**: HR 92 · RR 16 (distress threshold 30) · SpO2 99% · BP 124/78 (pulse-absent below 70) · consciousness 1 (altered below 0.5) · hemorrhage insult 0 · tourniquet window 120s · survivable True · minor-injuries-only True

### `Casualty_TensionPneumo_Chest`

- **Request**: `tension_pneumo_chest` (asked for Red) — accepted after 1 refine attempt(s)
- **Authoring note**: Penetrating chest wound with tension physiology. All vitals are a clinically plausible placeholder — SME validation pending. Needle decompression is the salvage intervention.
- **Placeholder label**: present
- **Pulse patient file**: `StandardMale@0s` · **vitals override gate**: True
- **Vitals and authoring intent**: HR 129 · RR 38 (distress threshold 30) · SpO2 84% · BP 98/62 (pulse-absent below 70) · consciousness 0.7 (altered below 0.5) · hemorrhage insult 0 · tourniquet window 120s · survivable True · minor-injuries-only False

### `Casualty_Abdominal_Evisceration`

- **Request**: `abdominal_evisceration` (asked for Yellow) — accepted after 1 refine attempt(s)
- **Authoring note**: Abdominal evisceration, dressed by a bystander. Vitals are a clinically plausible placeholder — SME validation pending. Serious but currently stable; will decay without surgery.
- **Placeholder label**: present
- **Pulse patient file**: `StandardMale@0s` · **vitals override gate**: True
- **Vitals and authoring intent**: HR 104 · RR 18 (distress threshold 30) · SpO2 95% · BP 106/66 (pulse-absent below 70) · consciousness 0.8 (altered below 0.5) · hemorrhage insult 0 · tourniquet window 120s · survivable True · minor-injuries-only False

### `Casualty_BlastApnea_Black`

- **Request**: `blast_apnea_black` (asked for Black) — accepted after 1 refine attempt(s)
- **Authoring note**: Apneic after one airway-reposition attempt; the row represents arrest at spawn. Vitals are a clinically plausible placeholder — SME validation pending.
- **Placeholder label**: present
- **Pulse patient file**: `StandardMale@0s` · **vitals override gate**: True
- **Vitals and authoring intent**: HR 0 · RR 0 (distress threshold 30) · SpO2 0% · BP 0/0 (pulse-absent below 70) · consciousness 0 (altered below 0.5) · hemorrhage insult 0 · tourniquet window 120s · survivable False · minor-injuries-only False

### `Casualty_FlashBurn_Forearms`

- **Request**: `flash_burn_forearms` (asked for Yellow) — accepted after 1 refine attempt(s)
- **Authoring note**: Partial-thickness flash burns to both forearms and hands, no airway involvement. Vitals are a clinically plausible placeholder — SME validation pending. Painful and burn-centre bound, but physiologically stable at spawn.
- **Placeholder label**: present
- **Pulse patient file**: `StandardMale@0s` · **vitals override gate**: True
- **Vitals and authoring intent**: HR 95 · RR 18 (distress threshold 30) · SpO2 97% · BP 128/80 (pulse-absent below 70) · consciousness 0.95 (altered below 0.5) · hemorrhage insult 0 · tourniquet window 120s · survivable True · minor-injuries-only False

## Rows this run refused to ship

These items were escalated to a human and are deliberately **not** in the CSV. A row the pipeline knows is incoherent is worse than a missing row: it imports cleanly, looks plausible, and silently supplies the wrong ground truth to scoring.

- `Casualty_SevereTBI_Expectant` — request `severe_tbi_expectant`, asked for Gray. **Held back because**: no progress: the same rule broke on two consecutive attempts (R1_SALT_MISMATCH). The refiner is returning an equivalent draft rather than reconciling the finding. See `escalations/severe_tbi_expectant.md`.
