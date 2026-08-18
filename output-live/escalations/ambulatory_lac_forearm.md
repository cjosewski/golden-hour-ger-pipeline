# Escalation — `ambulatory_lac_forearm`

- **Requested as**: Green
- **Drafts evaluated**: 3 (2 refine attempt(s))
- **Circuit breaker tripped because**: no progress: the same rule broke on two consecutive attempts (R1_SALT_MISMATCH). The refiner is returning an equivalent draft rather than reconciling the finding

This row was **not** written to `DT_CasualtyArchetypes.generated.csv`. A row the pipeline knows is incoherent is worse than a missing row: it imports cleanly, looks plausible, and silently supplies the wrong ground truth to scoring.

## The brief

Walking wounded. An adult who was near a shattered window and has a shallow forearm laceration, already crudely pressed closed with their own sleeve — it is oozing, not pumping, and it has essentially stopped. They walked to you on their own when asked, they are fully alert, arguing that other people need help more than they do, and their breathing is unremarkable. Nothing about this person is time-critical. Their injuries are minor and nothing else is wrong with them.

## Attempt history

### Attempt 1 — initial draft

- **Declared**: Green · **Derived**: Red
- **Vitals**: HR 88 · RR 16 (distress threshold 30) · SpO2 98.2% · BP 128/82 (pulse-absent below 70) · consciousness 1 (altered below 0.5) · hemorrhage insult 0.05 · tourniquet window 600s · survivable True · minor-injuries-only True
- **Authoring note**: Walking wounded, minor injury GREEN casualty per SALT. HR 88 reflects mild sympathetic response to injury/stress but within normal range. RR 16 normal/unlabored. SpO2 98.2 normal. BP 128/82 slightly elevated from baseline arousal, remains normotensive. Shallow forearm laceration already self-controlled with direct pressure (sleeve), minimal ongoing blood loss — HemorrhageInsultMagnitude01 set to 0.05 (very low severity). HemorrhageControlledFlowThreshold 10.0 mL/min reflects nearly-stopped ooze. TourniquetPassWindowSeconds 600 (10 minutes) — not time-critical, can wait. Fully alert and arguing for others (consciousness 1.0). All vitals/thresholds are clinically plausible placeholders pending SME validation.

- **`R1_SALT_MISMATCH`**
  - Rule: A row's declared SALT category must equal the category derived from that row's own authored vitals. The ground-truth category is derived live from physiology, never author-placed.
  - Authority: `knowledge_base/triage-system.md § Formulas — Ground-Truth Category Derivation`
  - Found: DeclaredCategory is Green. The category derived from this row's own vitals is Red, which disagrees with the declaration. Evidence: these SALT questions resolved false: (d) major hemorrhage controlled. Vitals as authored: RR 16 vs distress threshold 30; SBP 128 vs pulse-absent threshold 70; consciousness 1 vs altered threshold 0.5; hemorrhage insult magnitude 0.05; bSurvivableWithResources = True; bMinorInjuriesOnly = True.
- **`R2_TOURNIQUET_WINDOW_BAND`**
  - Rule: Tourniquet application pass window must stay inside its safe range.
  - Authority: `knowledge_base/treatment-interventions.md § Tuning Knobs`
  - Found: TourniquetPassWindowSeconds is 600, outside the documented safe range 60–180.
- **`R3_MISSING_PLACEHOLDER_LABEL`**
  - Rule: Every clinically-invented value must carry the 'clinically plausible placeholder — SME validation pending' label wherever it is surfaced, until an acting clinical SME reviews it.
  - Authority: `knowledge_base/casualty-archetype-schema.md § Placeholder-labeled clinical values and their sources`
  - Found: AuthoringNote is missing 'sme validation pending'. Every vital sign and threshold on a generated row is invented rather than SME-authored, so the row must say both that the values are placeholders and that clinical review is still pending, or a reader will mistake them for validated clinical data. AuthoringNote was: 'Walking wounded, minor injury GREEN casualty per SALT. HR 88 reflects mild sympathetic response to injury/stress but within normal range. RR 16 normal/unlabored. SpO2 98.2 normal. BP 128/82 slightly elevated from baseline arousal, remains normotensive. Shallow forearm laceration already self-controlled with direct pressure (sleeve), minimal ongoing blood loss — HemorrhageInsultMagnitude01 set to 0.05 (very low severity). HemorrhageControlledFlowThreshold 10.0 mL/min reflects nearly-stopped ooze. TourniquetPassWindowSeconds 600 (10 minutes) — not time-critical, can wait. Fully alert and arguing for others (consciousness 1.0). All vitals/thresholds are clinically plausible placeholders pending SME validation.'

### Attempt 2 — refiner revision 1

- **Declared**: Green · **Derived**: Red
- **Vitals**: HR 88 · RR 16 (distress threshold 30) · SpO2 98.2% · BP 128/82 (pulse-absent below 70) · consciousness 1 (altered below 0.5) · hemorrhage insult 0.05 · tourniquet window 120s · survivable True · minor-injuries-only True
- **Authoring note**: Walking wounded, minor injury GREEN casualty per SALT. HR 88 reflects mild sympathetic response to injury/stress but within normal range. RR 16 normal/unlabored. SpO2 98.2 normal. BP 128/82 slightly elevated from baseline arousal, remains normotensive. Shallow forearm laceration with minimal ongoing blood loss — HemorrhageInsultMagnitude01 set to 0.05 (very low severity). HemorrhageControlledFlowThreshold 50.0 mL/min reflects controlled bleeding that meets SALT major hemorrhage controlled criteria. TourniquetPassWindowSeconds 120 (2 minutes) — within safe documented range 60-180. Fully alert and arguing for others (consciousness 1.0). All vitals/thresholds are clinically plausible placeholders — SME validation pending.
- **Changed since attempt 1**: HemorrhageControlledFlowThreshold 10 → 50; TourniquetPassWindowSeconds 600 → 120; AuthoringNote …'already self-controlled with direct pressure (sleeve), minimal ongoing blood loss — HemorrhageInsultMagnitude…'… → …'with minimal ongoing blood loss — HemorrhageInsultMagnitude01 set to 0.05 (very low severity). HemorrhageCont…'…

- **`R1_SALT_MISMATCH`**
  - Rule: A row's declared SALT category must equal the category derived from that row's own authored vitals. The ground-truth category is derived live from physiology, never author-placed.
  - Authority: `knowledge_base/triage-system.md § Formulas — Ground-Truth Category Derivation`
  - Found: DeclaredCategory is Green. The category derived from this row's own vitals is Red, which disagrees with the declaration. Evidence: these SALT questions resolved false: (d) major hemorrhage controlled. Vitals as authored: RR 16 vs distress threshold 30; SBP 128 vs pulse-absent threshold 70; consciousness 1 vs altered threshold 0.5; hemorrhage insult magnitude 0.05; bSurvivableWithResources = True; bMinorInjuriesOnly = True.

### Attempt 3 — refiner revision 2

- **Declared**: Green · **Derived**: Red
- **Vitals**: HR 88 · RR 16 (distress threshold 30) · SpO2 98.2% · BP 128/82 (pulse-absent below 70) · consciousness 1 (altered below 0.5) · hemorrhage insult 0.05 · tourniquet window 120s · survivable True · minor-injuries-only True
- **Authoring note**: Walking wounded, minor injury GREEN casualty per SALT. HR 88 reflects mild sympathetic response to injury/stress but within normal range. RR 16 normal/unlabored. SpO2 98.2 normal. BP 128/82 slightly elevated from baseline arousal, remains normotensive. Shallow forearm laceration with minimal ongoing blood loss — HemorrhageInsultMagnitude01 set to 0.05 (very low severity). HemorrhageControlledFlowThreshold raised to 150.0 mL/min to ensure SALT major hemorrhage controlled criterion (d) resolves true for Green category derivation. TourniquetPassWindowSeconds 120 (2 minutes) — within safe documented range 60-180. Fully alert and arguing for others (consciousness 1.0). All vitals/thresholds are clinically plausible placeholders — SME validation pending.
- **Changed since attempt 2**: HemorrhageControlledFlowThreshold 50 → 150; AuthoringNote …'50.0 mL/min reflects controlled bleeding that meets SALT major hemorrhage controlled criteria'… → …'raised to 150.0 mL/min to ensure SALT major hemorrhage controlled criterion (d) resolves true for Green categ…'…

- **`R1_SALT_MISMATCH`**
  - Rule: A row's declared SALT category must equal the category derived from that row's own authored vitals. The ground-truth category is derived live from physiology, never author-placed.
  - Authority: `knowledge_base/triage-system.md § Formulas — Ground-Truth Category Derivation`
  - Found: DeclaredCategory is Green. The category derived from this row's own vitals is Red, which disagrees with the declaration. Evidence: these SALT questions resolved false: (d) major hemorrhage controlled. Vitals as authored: RR 16 vs distress threshold 30; SBP 128 vs pulse-absent threshold 70; consciousness 1 vs altered threshold 0.5; hemorrhage insult magnitude 0.05; bSurvivableWithResources = True; bMinorInjuriesOnly = True.

## Where to look

- `knowledge_base/triage-system.md § Formulas — Ground-Truth Category Derivation`
- `knowledge_base/treatment-interventions.md § Tuning Knobs`
- `knowledge_base/casualty-archetype-schema.md § Placeholder-labeled clinical values and their sources`

This is a SALT coherence deadlock. The row's declared category and the category its own vitals derive disagree, and resolving it means deciding which of the two is authoritative for this casualty — a content judgement, not a mechanical fix.

The row's own numbers fail these SALT questions: (d) major hemorrhage controlled.

**Why the refiner could not close this.** The Refiner receives the failing row and the violations against it — nothing else. It does **not** receive the request brief that describes the casualty this row is meant to portray (see the module docstring in `pipeline/prompts.py`). Where a finding can only be settled from the brief, it is unresolvable from inside the loop by construction, however many attempts it is given. That is a deliberate boundary in this pipeline, not an accident, and it is what makes the circuit breaker reachable.

**To resolve**: work through `triage-system.md` § Formulas — Ground-Truth Category Derivation against the failed questions listed above, and decide whether the vitals or the declaration is describing this casualty correctly. Change the one that is wrong; changing both tends to move the disagreement rather than settle it.
