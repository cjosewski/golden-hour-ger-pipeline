# GER run log — DT_CasualtyArchetypes

- **Mode**: offline
- **Model**: `offline-deterministic-fixture`
- **Run at**: 2026-08-12T23:31:08+00:00
- **Requested**: 7 · **Accepted**: 6 · **Escalated**: 1
- **Breaker policy**: max 3 refine attempts per item; run aborts above 50% escalations

> **This was the offline harness.** The Generator and Refiner were deterministic fixtures, not model calls — the drafts below were hand-designed to break specific rules so the Evaluator, Refiner and Circuit Breaker can be observed working with no API key. The Evaluator, the SALT derivation and the Circuit Breaker are the real production code in both modes; only the two LLM roles are substituted. Draw no conclusions about model behaviour from this file.

---

## `ied_leg_hemorrhage_t1` — ACCEPTED

*Requested as:* Red. *Drafts evaluated:* 1 (0 refine attempt(s)).

### Attempt 1 — initial draft

- **Row**: `Casualty_IED_LegHemorrhage_T1_Gen`
- **Declared category**: Red
- **Derived from these vitals**: Red
- **Vitals**: HR 117 · RR 22 (distress threshold 30) · SpO2 94% · BP 96/58 (pulse-absent below 70) · consciousness 0.85 (altered below 0.5) · hemorrhage insult 0.6 · tourniquet window 120s · survivable True · minor-injuries-only False
- **Authoring note**: Tier-1 IED femoral hemorrhage. Vitals are a clinically plausible placeholder — SME validation pending; compensating shock picture with an uncontrolled arterial bleed, tourniquet-salvageable.

**Evaluator findings:**

- **No violations.** This draft satisfies every rule.

**Verdict: accepted.** The row passed every rule after 0 refine attempt(s) and is written to `DT_CasualtyArchetypes.generated.csv`.

---

## `ambulatory_lac_forearm` — ACCEPTED

*Requested as:* Green. *Drafts evaluated:* 2 (1 refine attempt(s)).

### Attempt 1 — initial draft

- **Row**: `Casualty_Ambulatory_ForearmLac`
- **Declared category**: Green
- **Derived from these vitals**: Green
- **Vitals**: HR 92 · RR 16 (distress threshold 30) · SpO2 99% · BP 124/78 (pulse-absent below 70) · consciousness 1 (altered below 0.5) · hemorrhage insult 0 · tourniquet window 120s · survivable True · minor-injuries-only True
- **Authoring note**: Walking wounded with a superficial forearm laceration, self-controlled with direct pressure. Fully alert and ambulatory.

**Evaluator findings:**

- **`R3_MISSING_PLACEHOLDER_LABEL`**
  - Rule: Every clinically-invented value must carry the 'clinically plausible placeholder — SME validation pending' label wherever it is surfaced, until an acting clinical SME reviews it.
  - Authority: `knowledge_base/casualty-archetype-schema.md § Placeholder-labeled clinical values and their sources`
  - Found: AuthoringNote is missing 'placeholder' and 'sme validation pending'. Every vital sign and threshold on a generated row is invented rather than SME-authored, so the row must say both that the values are placeholders and that clinical review is still pending, or a reader will mistake them for validated clinical data. AuthoringNote was: 'Walking wounded with a superficial forearm laceration, self-controlled with direct pressure. Fully alert and ambulatory.'

### Attempt 2 — refiner revision 1

- **Row**: `Casualty_Ambulatory_ForearmLac`
- **Declared category**: Green
- **Derived from these vitals**: Green
- **Vitals**: HR 92 · RR 16 (distress threshold 30) · SpO2 99% · BP 124/78 (pulse-absent below 70) · consciousness 1 (altered below 0.5) · hemorrhage insult 0 · tourniquet window 120s · survivable True · minor-injuries-only True
- **Authoring note**: Walking wounded with a superficial forearm laceration, self-controlled with direct pressure. Fully alert and ambulatory. All clinical values here are a clinically plausible placeholder — SME validation pending.
- **Changed since attempt 1**: AuthoringNote gained …' All clinical values here are a clinically plausible placeholder — SME validation pending.'

**Evaluator findings:**

- **No violations.** This draft satisfies every rule.

**Verdict: accepted.** The row passed every rule after 1 refine attempt(s) and is written to `DT_CasualtyArchetypes.generated.csv`.

---

## `tension_pneumo_chest` — ACCEPTED

*Requested as:* Red. *Drafts evaluated:* 2 (1 refine attempt(s)).

### Attempt 1 — initial draft

- **Row**: `Casualty_TensionPneumo_Chest`
- **Declared category**: Red
- **Derived from these vitals**: Red
- **Vitals**: HR 129 · RR 38 (distress threshold 30) · SpO2 84% · BP 98/62 (pulse-absent below 70) · consciousness 0.7 (altered below 0.5) · hemorrhage insult 0 · tourniquet window 240s · survivable True · minor-injuries-only False
- **Authoring note**: Penetrating chest wound with tension physiology. All vitals are a clinically plausible placeholder — SME validation pending. Needle decompression is the salvage intervention.

**Evaluator findings:**

- **`R2_TOURNIQUET_WINDOW_BAND`**
  - Rule: Tourniquet application pass window must stay inside its safe range.
  - Authority: `knowledge_base/treatment-interventions.md § Tuning Knobs`
  - Found: TourniquetPassWindowSeconds is 240, outside the documented safe range 60–180.

### Attempt 2 — refiner revision 1

- **Row**: `Casualty_TensionPneumo_Chest`
- **Declared category**: Red
- **Derived from these vitals**: Red
- **Vitals**: HR 129 · RR 38 (distress threshold 30) · SpO2 84% · BP 98/62 (pulse-absent below 70) · consciousness 0.7 (altered below 0.5) · hemorrhage insult 0 · tourniquet window 120s · survivable True · minor-injuries-only False
- **Authoring note**: Penetrating chest wound with tension physiology. All vitals are a clinically plausible placeholder — SME validation pending. Needle decompression is the salvage intervention.
- **Changed since attempt 1**: TourniquetPassWindowSeconds 240 → 120

**Evaluator findings:**

- **No violations.** This draft satisfies every rule.

**Verdict: accepted.** The row passed every rule after 1 refine attempt(s) and is written to `DT_CasualtyArchetypes.generated.csv`.

---

## `abdominal_evisceration` — ACCEPTED

*Requested as:* Yellow. *Drafts evaluated:* 2 (1 refine attempt(s)).

### Attempt 1 — initial draft

- **Row**: `Casualty_Abdominal_Evisceration`
- **Declared category**: Yellow
- **Derived from these vitals**: Red
- **Vitals**: HR 121 · RR 34 (distress threshold 30) · SpO2 91% · BP 68/44 (pulse-absent below 70) · consciousness 0.15 (altered below 0.5) · hemorrhage insult 0.45 · tourniquet window 120s · survivable True · minor-injuries-only False
- **Authoring note**: Abdominal evisceration, dressed by a bystander. Vitals are a clinically plausible placeholder — SME validation pending. Serious but currently stable; will decay without surgery.

**Evaluator findings:**

- **`R1_SALT_MISMATCH`**
  - Rule: A row's declared SALT category must equal the category derived from that row's own authored vitals. The ground-truth category is derived live from physiology, never author-placed.
  - Authority: `knowledge_base/triage-system.md § Formulas — Ground-Truth Category Derivation`
  - Found: DeclaredCategory is Yellow. The category derived from this row's own vitals is Red, which disagrees with the declaration. Evidence: these SALT questions resolved false: (a) obeys commands or shows purposeful movement; (b) peripheral pulse present; (c) not in respiratory distress; (d) major hemorrhage controlled. Vitals as authored: RR 34 vs distress threshold 30; SBP 68 vs pulse-absent threshold 70; consciousness 0.15 vs altered threshold 0.5; hemorrhage insult magnitude 0.45; bSurvivableWithResources = True; bMinorInjuriesOnly = False.

### Attempt 2 — refiner revision 1

- **Row**: `Casualty_Abdominal_Evisceration`
- **Declared category**: Yellow
- **Derived from these vitals**: Yellow
- **Vitals**: HR 104 · RR 18 (distress threshold 30) · SpO2 95% · BP 106/66 (pulse-absent below 70) · consciousness 0.8 (altered below 0.5) · hemorrhage insult 0 · tourniquet window 120s · survivable True · minor-injuries-only False
- **Authoring note**: Abdominal evisceration, dressed by a bystander. Vitals are a clinically plausible placeholder — SME validation pending. Serious but currently stable; will decay without surgery.
- **Changed since attempt 1**: InitialHeartRateBpm 121 → 104; InitialRespirationRateBpm 34 → 18; InitialSpO2Percent 91 → 95; InitialSystolicBP 68 → 106; InitialDiastolicBP 44 → 66; HemorrhageInsultActionName 'IED_Explosion' → 'None'; HemorrhageInsultMagnitude01 0.45 → 0; InitialConsciousness01 0.15 → 0.8

**Evaluator findings:**

- **No violations.** This draft satisfies every rule.

**Verdict: accepted.** The row passed every rule after 1 refine attempt(s) and is written to `DT_CasualtyArchetypes.generated.csv`.

---

## `severe_tbi_expectant` — ESCALATED

*Requested as:* Gray. *Drafts evaluated:* 2 (1 refine attempt(s)).

### Attempt 1 — initial draft

- **Row**: `Casualty_SevereTBI_Expectant`
- **Declared category**: Gray
- **Derived from these vitals**: Red
- **Vitals**: HR 44 · RR 6 (distress threshold 30) · SpO2 72% · BP 52/30 (pulse-absent below 70) · consciousness 0.02 (altered below 0.5) · hemorrhage insult 0 · tourniquet window 120s · survivable True · minor-injuries-only False
- **Authoring note**: Open head injury with agonal respirations. Vitals are a clinically plausible placeholder — SME validation pending. Expectant given the resources on scene; comfort care only.

**Evaluator findings:**

- **`R1_SALT_MISMATCH`**
  - Rule: A row's declared SALT category must equal the category derived from that row's own authored vitals. The ground-truth category is derived live from physiology, never author-placed.
  - Authority: `knowledge_base/triage-system.md § Formulas — Ground-Truth Category Derivation`
  - Found: DeclaredCategory is Gray. The category derived from this row's own vitals is Red, which disagrees with the declaration. Evidence: these SALT questions resolved false: (a) obeys commands or shows purposeful movement; (b) peripheral pulse present. Vitals as authored: RR 6 vs distress threshold 30; SBP 52 vs pulse-absent threshold 70; consciousness 0.02 vs altered threshold 0.5; hemorrhage insult magnitude 0; bSurvivableWithResources = True; bMinorInjuriesOnly = False.

### Attempt 2 — refiner revision 1

- **Row**: `Casualty_SevereTBI_Expectant`
- **Declared category**: Gray
- **Derived from these vitals**: Red
- **Vitals**: HR 44 · RR 6 (distress threshold 30) · SpO2 72% · BP 52/30 (pulse-absent below 70) · consciousness 0.02 (altered below 0.5) · hemorrhage insult 0 · tourniquet window 120s · survivable True · minor-injuries-only False
- **Authoring note**: Open head injury with agonal respirations. Vitals are a clinically plausible placeholder — SME validation pending. Expectant given the resources on scene; comfort care only. Reviewed again (revision 1); the authored presentation is believed correct as written.
- **Changed since attempt 1**: AuthoringNote gained …' Reviewed again (revision 1); the authored presentation is believed correct as written.'

**Evaluator findings:**

- **`R1_SALT_MISMATCH`**
  - Rule: A row's declared SALT category must equal the category derived from that row's own authored vitals. The ground-truth category is derived live from physiology, never author-placed.
  - Authority: `knowledge_base/triage-system.md § Formulas — Ground-Truth Category Derivation`
  - Found: DeclaredCategory is Gray. The category derived from this row's own vitals is Red, which disagrees with the declaration. Evidence: these SALT questions resolved false: (a) obeys commands or shows purposeful movement; (b) peripheral pulse present. Vitals as authored: RR 6 vs distress threshold 30; SBP 52 vs pulse-absent threshold 70; consciousness 0.02 vs altered threshold 0.5; hemorrhage insult magnitude 0; bSurvivableWithResources = True; bMinorInjuriesOnly = False.

**Verdict: escalated.** The circuit breaker tripped — no progress: the same rule broke on two consecutive attempts (R1_SALT_MISMATCH). The refiner is returning an equivalent draft rather than reconciling the finding. This row is deliberately NOT written to the CSV; see `escalations/severe_tbi_expectant.md`.

---

## `blast_apnea_black` — ACCEPTED

*Requested as:* Black. *Drafts evaluated:* 2 (1 refine attempt(s)).

### Attempt 1 — initial draft

- **Row**: `Casualty_BlastApnea_Black`
- **Declared category**: Black
- **Derived from these vitals**: Black
- **Vitals**: HR 0 · RR 0 (distress threshold 30) · SpO2 0% · BP 0/0 (pulse-absent below 70) · consciousness 0 (altered below 0.5) · hemorrhage insult 0 · tourniquet window 120s · survivable True · minor-injuries-only False
- **Authoring note**: Apneic after one airway-reposition attempt; the row represents arrest at spawn. Vitals are a clinically plausible placeholder — SME validation pending.

**Evaluator findings:**

- **`R1_BLACK_CONTRADICTION`**
  - Rule: The survivability and minor-injuries flags only decide splits reached by a breathing casualty; neither can be true for a casualty declared Dead (Black).
  - Authority: `knowledge_base/triage-system.md § Detailed Design — Core Rules, rule 2`
  - Found: DeclaredCategory is Black but bSurvivableWithResources = True and bMinorInjuriesOnly = False. The Black branch stops before either flag is consulted, so a true value here contradicts the declaration.

### Attempt 2 — refiner revision 1

- **Row**: `Casualty_BlastApnea_Black`
- **Declared category**: Black
- **Derived from these vitals**: Black
- **Vitals**: HR 0 · RR 0 (distress threshold 30) · SpO2 0% · BP 0/0 (pulse-absent below 70) · consciousness 0 (altered below 0.5) · hemorrhage insult 0 · tourniquet window 120s · survivable False · minor-injuries-only False
- **Authoring note**: Apneic after one airway-reposition attempt; the row represents arrest at spawn. Vitals are a clinically plausible placeholder — SME validation pending.
- **Changed since attempt 1**: bSurvivableWithResources True → False

**Evaluator findings:**

- **No violations.** This draft satisfies every rule.

**Verdict: accepted.** The row passed every rule after 1 refine attempt(s) and is written to `DT_CasualtyArchetypes.generated.csv`.

---

## `flash_burn_forearms` — ACCEPTED

*Requested as:* Yellow. *Drafts evaluated:* 2 (1 refine attempt(s)).

### Attempt 1 — initial draft

- **Row**: `Casualty_FlashBurn_Forearms`
- **Declared category**: Yellow
- **Derived from these vitals**: Yellow
- **Vitals**: HR 95 · RR 18 (distress threshold 30) · SpO2 97% · BP 128/80 (pulse-absent below 70) · consciousness 0.95 (altered below 0.5) · hemorrhage insult 0 · tourniquet window 120s · survivable True · minor-injuries-only False
- **Authoring note**: Partial-thickness flash burns to both forearms and hands, no airway involvement. Vitals are a clinically plausible placeholder — SME validation pending. Painful and burn-centre bound, but physiologically stable at spawn.

**Evaluator findings:**

- **`R4_BAD_ASSET_PATH`**
  - Rule: CasualtyCharacterAssetPath must be an Unreal content path rooted at /Game/.
  - Authority: `knowledge_base/casualty-archetype-schema.md § Type-restriction notes`
  - Found: CasualtyCharacterAssetPath is 'Content/GoldenHour/Characters/CasualtyT1/Casualty_01', which is not an Unreal content path (it does not start with /Game/). This field is 'a plain string nothing type-checks, breaking silently and surfacing only in a packaged build' (casualty-archetype-schema.md § Addendum 2026-07-26, second correction), so the path shape is checked here instead. The same section names the current fill value: /Game/GoldenHour/Characters/CasualtyT1/Casualty_01.

### Attempt 2 — refiner revision 1

- **Row**: `Casualty_FlashBurn_Forearms`
- **Declared category**: Yellow
- **Derived from these vitals**: Yellow
- **Vitals**: HR 95 · RR 18 (distress threshold 30) · SpO2 97% · BP 128/80 (pulse-absent below 70) · consciousness 0.95 (altered below 0.5) · hemorrhage insult 0 · tourniquet window 120s · survivable True · minor-injuries-only False
- **Authoring note**: Partial-thickness flash burns to both forearms and hands, no airway involvement. Vitals are a clinically plausible placeholder — SME validation pending. Painful and burn-centre bound, but physiologically stable at spawn.
- **Changed since attempt 1**: CasualtyCharacterAssetPath 'Content/GoldenHour/Characters/CasualtyT1/Casualty_01' → '/Game/GoldenHour/Characters/CasualtyT1/Casualty_01'

**Evaluator findings:**

- **No violations.** This draft satisfies every rule.

**Verdict: accepted.** The row passed every rule after 1 refine attempt(s) and is written to `DT_CasualtyArchetypes.generated.csv`.

---
