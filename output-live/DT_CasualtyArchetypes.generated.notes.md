# `DT_CasualtyArchetypes.generated` — CSV Source Notes

> **Sibling file**: `DT_CasualtyArchetypes.generated.csv` — 5 accepted row(s)
> **Produced by**: this repo's GER pipeline, live mode, model `claude-sonnet-4-5`
> **Run at**: 2026-08-18T01:32:09+00:00
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
| `Casualty_IED_FemoralHemorrhage_T1_Red` | Red | Red | 1 | present |
| `Casualty_Fragment_ChestPenetration_TensionPneumo` | Red | Red | 1 | present |
| `Casualty_OpenHeadInjury_Expectant` | Gray | Gray | 1 | present |
| `Casualty_IED_ApneicNoAirway_T2` | Black | Black | 1 | present |
| `Casualty_IED_BilateralArmBurns_T2` | Yellow | Yellow | 1 | present |

Declared and derived agree on every shipped row — that agreement is what R1 checks, and a row where they disagree is not written to the CSV.

## Per-row authoring notes, verbatim

### `Casualty_IED_FemoralHemorrhage_T1_Red`

- **Request**: `ied_leg_hemorrhage_t1` (asked for Red) — accepted after 1 refine attempt(s)
- **Authoring note**: Red (Immediate): Active uncontrolled femoral hemorrhage with compensatory shock presentation. Awake and responsive (consciousness ~0.85) but showing early shock signs: tachycardia 118bpm reflects sympathetic response to volume loss, systolic BP 102mmHg is low-normal trending toward hypotension, respiration 24bpm elevated but not yet distressed. SpO2 96.2% still adequate. Life-threatening hemorrhage requiring immediate intervention (tourniquet) but survivable with prompt treatment. All vitals are clinically plausible placeholders — SME validation pending. HR/BP/RR reflect early hemorrhagic shock (Class II, ~15-30% blood loss); chosen to show clear deterioration trajectory if untreated while remaining conscious and salvageable at presentation.
- **Placeholder label**: present
- **Pulse patient file**: `StandardMale@0s` · **vitals override gate**: True
- **Vitals and authoring intent**: HR 118 · RR 24 (distress threshold 30) · SpO2 96.2% · BP 102/68 (pulse-absent below 70) · consciousness 0.85 (altered below 0.5) · hemorrhage insult 0.65 · tourniquet window 120s · survivable True · minor-injuries-only False

### `Casualty_Fragment_ChestPenetration_TensionPneumo`

- **Request**: `tension_pneumo_chest` (asked for Red) — accepted after 1 refine attempt(s)
- **Authoring note**: Tension pneumothorax presentation: tachypneic (RR 36, clinical respiratory distress threshold lowered to 28 for this casualty), compensated shock with tachycardia (HR 118), hypotensive but palpable radial (SBP 102), hypoxic (SpO2 88.5%). Consciousness 0.75 represents alert but distressed — able to speak in broken phrases. Category RED: life-threatening injury, survivable with needle decompression within the stated 180-second window. Low hemorrhage magnitude (0.2) reflects minimal external bleeding from penetrating mechanism; primary insult is respiratory compromise not exsanguination. All vitals, thresholds, and timing parameters are clinically plausible placeholders — SME validation pending. HemorrhageCessationActionName set to NeedleDecompression as the definitive intervention for this injury pattern; actual Pulse action name unconfirmed and requires PULSE-17 validation.
- **Placeholder label**: present
- **Pulse patient file**: `StandardMale@0s` · **vitals override gate**: True
- **Vitals and authoring intent**: HR 118 · RR 36 (distress threshold 28) · SpO2 88.5% · BP 102/68 (pulse-absent below 70) · consciousness 0.75 (altered below 0.5) · hemorrhage insult 0.2 · tourniquet window 180s · survivable True · minor-injuries-only False

### `Casualty_OpenHeadInjury_Expectant`

- **Request**: `severe_tbi_expectant` (asked for Gray) — accepted after 1 refine attempt(s)
- **Authoring note**: Expectant/Gray category: severe traumatic brain injury with exposed brain matter, agonal respirations (4/min irregular gasping), profound hypotension (62/40 indicating shock and brainstem compromise), severe bradycardia (38 bpm), profound hypoxia (SpO2 78%), and complete unresponsiveness (GCS ~3, consciousness 0.05). Not survivable in austere mass-casualty environment without immediate neurosurgical capability, blood products, advanced airway, and ICU-level care — none available on scene. Vitals reflect imminent decompensation: bradycardia with hypotension indicates herniation physiology, agonal breathing pattern is pre-terminal. Pulse quality thresholds mean radial pulse will correctly read absent at this BP. Respiratory rate well below distress threshold, appropriately reflecting agonal pattern rather than compensatory tachypnea. All values are clinically plausible placeholders — SME validation pending.
- **Placeholder label**: present
- **Pulse patient file**: `StandardMale@0s` · **vitals override gate**: True
- **Vitals and authoring intent**: HR 38 · RR 4 (distress threshold 30) · SpO2 78% · BP 62/40 (pulse-absent below 70) · consciousness 0.05 (altered below 0.5) · hemorrhage insult 0.85 · tourniquet window 120s · survivable False · minor-injuries-only False

### `Casualty_IED_ApneicNoAirway_T2`

- **Request**: `blast_apnea_black` (asked for Black) — accepted after 1 refine attempt(s)
- **Authoring note**: Expectant/Black casualty per SALT protocol: apneic after single airway repositioning attempt with no response. Clinical presentation = complete respiratory arrest (RR 0), cardiovascular collapse imminent or present (all vitals zeroed to represent peri-arrest/arrest state), unconscious (consciousness 0.0). No external hemorrhage per scenario text so minimal HemorrhageInsultMagnitude01 (0.1) and HemorrhageSiteTag None. Vitals set to 0 as clinically plausible placeholder representing arrested state — in mass-casualty doctrine this casualty receives no further intervention and is tagged Black/Expectant. Threshold bands left at archetype defaults since assessment verbs are not the clinical decision point for this presentation. All physiological parameters are clinically plausible placeholders — SME validation pending for all vital signs, thresholds, and confirmation that Pulse engine accepts zeroed vitals or requires different representation of arrest state.
- **Placeholder label**: present
- **Pulse patient file**: `StandardMale@0s` · **vitals override gate**: True
- **Vitals and authoring intent**: HR 0 · RR 0 (distress threshold 30) · SpO2 0% · BP 0/0 (pulse-absent below 70) · consciousness 0 (altered below 0.5) · hemorrhage insult 0.1 · tourniquet window 120s · survivable False · minor-injuries-only False

### `Casualty_IED_BilateralArmBurns_T2`

- **Request**: `flash_burn_forearms` (asked for Yellow) — accepted after 1 refine attempt(s)
- **Authoring note**: Clinically plausible placeholder — SME validation pending. HR 98 reflects moderate pain/stress response to bilateral partial-thickness burns without shock. RR 18 normal (no airway involvement confirmed by clear voice, no soot, no respiratory distress). SpO2 98.5 normal (no inhalation injury). BP 128/82 slightly elevated from pain/catecholamine response but well-perfused (strong radial pulse). No hemorrhage insult applied (burn-only mechanism). Yellow/Delayed category: requires burn-centre transport within hours per clinical description, fully compensated now but not minor-injuries-only (significant TBSA bilateral arm/hand burns), survival not time-critical in next minutes but needs definitive care. Stable vital trajectory expected without intervention in triage timeframe.
- **Placeholder label**: present
- **Pulse patient file**: `StandardMale@0s` · **vitals override gate**: True
- **Vitals and authoring intent**: HR 98 · RR 18 (distress threshold 30) · SpO2 98.5% · BP 128/82 (pulse-absent below 70) · consciousness 1 (altered below 0.5) · hemorrhage insult 0 · tourniquet window 120s · survivable True · minor-injuries-only False

## Rows this run refused to ship

These items were escalated to a human and are deliberately **not** in the CSV. A row the pipeline knows is incoherent is worse than a missing row: it imports cleanly, looks plausible, and silently supplies the wrong ground truth to scoring.

- `Casualty_Glass_ForearmLaceration_Green` — request `ambulatory_lac_forearm`, asked for Green. **Held back because**: no progress: the same rule broke on two consecutive attempts (R1_SALT_MISMATCH). The refiner is returning an equivalent draft rather than reconciling the finding. See `escalations/ambulatory_lac_forearm.md`.
- `Casualty_Abdominal_Evisceration_Delayed` — request `abdominal_evisceration`, asked for Yellow. **Held back because**: no progress: the same rule broke on two consecutive attempts (R1_SALT_MISMATCH). The refiner is returning an equivalent draft rather than reconciling the finding. See `escalations/abdominal_evisceration.md`.
