# Escalation — `abdominal_evisceration`

- **Requested as**: Yellow
- **Drafts evaluated**: 3 (2 refine attempt(s))
- **Circuit breaker tripped because**: no progress: the same rule broke on two consecutive attempts (R1_SALT_MISMATCH). The refiner is returning an equivalent draft rather than reconciling the finding

This row was **not** written to `DT_CasualtyArchetypes.generated.csv`. A row the pipeline knows is incoherent is worse than a missing row: it imports cleanly, looks plausible, and silently supplies the wrong ground truth to scoring.

## The brief

An abdominal wound with bowel exposed, covered with a moist dressing by a bystander before you arrived. It looks appalling but it is not actively pouring blood right now. The casualty is pale and quiet but awake and tracking you, answering questions, and breathing at an ordinary rate. Their pulse is present at the wrist. This is a serious injury that will get worse over the next hour without surgery, but at this moment they are holding steady, and they are definitely not a minor-injury patient.

## Attempt history

### Attempt 1 — initial draft

- **Declared**: Yellow · **Derived**: Red
- **Vitals**: HR 102 · RR 18 (distress threshold 30) · SpO2 96.2% · BP 98/62 (pulse-absent below 70) · consciousness 0.85 (altered below 0.5) · hemorrhage insult 0.35 · tourniquet window 300s · survivable True · minor-injuries-only False
- **Authoring note**: DELAYED/YELLOW: Abdominal evisceration with controlled hemorrhage. Vitals chosen to reflect compensated shock (tachycardia 102, low-normal systolic BP 98, mild tachypnea 18, adequate SpO2 96.2) consistent with slow internal bleeding and stress response but currently stable. Consciousness 0.85 reflects alert but quiet affect—awake, oriented, tracking, answering questions, but subdued by pain and shock. Not immediate/red because hemorrhage is controlled by bystander dressing, perfusion adequate (palpable radial pulse, SBP 98>90 weak threshold), respirations normal rate. Not minor/green because this is penetrating abdominal trauma with evisceration requiring surgical intervention. Category fits SALT delayed: serious injury, will deteriorate without definitive care within hours, but stable enough to wait for resource availability behind immediate casualties. HemorrhageInsultMagnitude 0.35 set lower than leg hemorrhage (0.6) to reflect controlled bleed state. TourniquetPassWindow extended to 300s because this is NOT a tourniquet-appropriate injury—represents general intervention window for moist dressing maintenance/monitoring. All clinical values are PLACEHOLDERS pending SME validation—no clinician review completed.

- **`R1_SALT_MISMATCH`**
  - Rule: A row's declared SALT category must equal the category derived from that row's own authored vitals. The ground-truth category is derived live from physiology, never author-placed.
  - Authority: `knowledge_base/triage-system.md § Formulas — Ground-Truth Category Derivation`
  - Found: DeclaredCategory is Yellow. The category derived from this row's own vitals is Red, which disagrees with the declaration. Evidence: these SALT questions resolved false: (d) major hemorrhage controlled. Vitals as authored: RR 18 vs distress threshold 30; SBP 98 vs pulse-absent threshold 70; consciousness 0.85 vs altered threshold 0.5; hemorrhage insult magnitude 0.35; bSurvivableWithResources = True; bMinorInjuriesOnly = False.
- **`R2_TOURNIQUET_WINDOW_BAND`**
  - Rule: Tourniquet application pass window must stay inside its safe range.
  - Authority: `knowledge_base/treatment-interventions.md § Tuning Knobs`
  - Found: TourniquetPassWindowSeconds is 300, outside the documented safe range 60–180.
- **`R3_MISSING_PLACEHOLDER_LABEL`**
  - Rule: Every clinically-invented value must carry the 'clinically plausible placeholder — SME validation pending' label wherever it is surfaced, until an acting clinical SME reviews it.
  - Authority: `knowledge_base/casualty-archetype-schema.md § Placeholder-labeled clinical values and their sources`
  - Found: AuthoringNote is missing 'sme validation pending'. Every vital sign and threshold on a generated row is invented rather than SME-authored, so the row must say both that the values are placeholders and that clinical review is still pending, or a reader will mistake them for validated clinical data. AuthoringNote was: 'DELAYED/YELLOW: Abdominal evisceration with controlled hemorrhage. Vitals chosen to reflect compensated shock (tachycardia 102, low-normal systolic BP 98, mild tachypnea 18, adequate SpO2 96.2) consistent with slow internal bleeding and stress response but currently stable. Consciousness 0.85 reflects alert but quiet affect—awake, oriented, tracking, answering questions, but subdued by pain and shock. Not immediate/red because hemorrhage is controlled by bystander dressing, perfusion adequate (palpable radial pulse, SBP 98>90 weak threshold), respirations normal rate. Not minor/green because this is penetrating abdominal trauma with evisceration requiring surgical intervention. Category fits SALT delayed: serious injury, will deteriorate without definitive care within hours, but stable enough to wait for resource availability behind immediate casualties. HemorrhageInsultMagnitude 0.35 set lower than leg hemorrhage (0.6) to reflect controlled bleed state. TourniquetPassWindow extended to 300s because this is NOT a tourniquet-appropriate injury—represents general intervention window for moist dressing maintenance/monitoring. All clinical values are PLACEHOLDERS pending SME validation—no clinician review completed.'

### Attempt 2 — refiner revision 1

- **Declared**: Yellow · **Derived**: Red
- **Vitals**: HR 102 · RR 18 (distress threshold 30) · SpO2 96.2% · BP 98/62 (pulse-absent below 70) · consciousness 0.85 (altered below 0.5) · hemorrhage insult 0.25 · tourniquet window 120s · survivable True · minor-injuries-only False
- **Authoring note**: Clinically plausible placeholder — SME validation pending. DELAYED/YELLOW: Abdominal evisceration with controlled hemorrhage. Vitals chosen to reflect compensated shock (tachycardia 102, low-normal systolic BP 98, mild tachypnea 18, adequate SpO2 96.2) consistent with slow internal bleeding and stress response but currently stable. Consciousness 0.85 reflects alert but quiet affect—awake, oriented, tracking, answering questions, but subdued by pain and shock. Not immediate/red because hemorrhage is controlled by bystander dressing, perfusion adequate (palpable radial pulse, SBP 98>90 weak threshold), respirations normal rate. Not minor/green because this is penetrating abdominal trauma with evisceration requiring surgical intervention. Category fits SALT delayed: serious injury, will deteriorate without definitive care within hours, but stable enough to wait for resource availability behind immediate casualties. HemorrhageInsultMagnitude 0.25 set low to reflect controlled bleed state with effective initial intervention. TourniquetPassWindow 120s represents general intervention monitoring window.
- **Changed since attempt 1**: HemorrhageInsultMagnitude01 0.35 → 0.25; TourniquetPassWindowSeconds 300 → 120; AuthoringNote 'DELAYED/YELLOW: Abdominal evisceration with controlled hemorrhage. Vitals chosen to reflect compensated shock…'… → 'Clinically plausible placeholder — SME validation pending. DELAYED/YELLOW: Abdominal evisceration with contro…'…

- **`R1_SALT_MISMATCH`**
  - Rule: A row's declared SALT category must equal the category derived from that row's own authored vitals. The ground-truth category is derived live from physiology, never author-placed.
  - Authority: `knowledge_base/triage-system.md § Formulas — Ground-Truth Category Derivation`
  - Found: DeclaredCategory is Yellow. The category derived from this row's own vitals is Red, which disagrees with the declaration. Evidence: these SALT questions resolved false: (d) major hemorrhage controlled. Vitals as authored: RR 18 vs distress threshold 30; SBP 98 vs pulse-absent threshold 70; consciousness 0.85 vs altered threshold 0.5; hemorrhage insult magnitude 0.25; bSurvivableWithResources = True; bMinorInjuriesOnly = False.

### Attempt 3 — refiner revision 2

- **Declared**: Yellow · **Derived**: Red
- **Vitals**: HR 102 · RR 18 (distress threshold 30) · SpO2 96.2% · BP 98/62 (pulse-absent below 70) · consciousness 0.85 (altered below 0.5) · hemorrhage insult 0.05 · tourniquet window 120s · survivable True · minor-injuries-only False
- **Authoring note**: Clinically plausible placeholder — SME validation pending. DELAYED/YELLOW: Abdominal evisceration with controlled hemorrhage. Vitals chosen to reflect compensated shock (tachycardia 102, low-normal systolic BP 98, mild tachypnea 18, adequate SpO2 96.2) consistent with slow internal bleeding and stress response but currently stable. Consciousness 0.85 reflects alert but quiet affect—awake, oriented, tracking, answering questions, but subdued by pain and shock. Not immediate/red because hemorrhage is controlled by bystander dressing, perfusion adequate (palpable radial pulse, SBP 98>90 weak threshold), respirations normal rate. Not minor/green because this is penetrating abdominal trauma with evisceration requiring surgical intervention. Category fits SALT delayed: serious injury, will deteriorate without definitive care within hours, but stable enough to wait for resource availability behind immediate casualties. HemorrhageInsultMagnitude 0.05 and HemorrhageCessationMagnitude 0.95 set to reflect effectively controlled hemorrhage state with initial intervention reducing flow below controlled threshold of 30.0. TourniquetPassWindow 120s represents general intervention monitoring window.
- **Changed since attempt 2**: HemorrhageInsultMagnitude01 0.25 → 0.05; HemorrhageCessationMagnitude01 0.7 → 0.95; AuthoringNote …'25 set low to reflect controlled bleed state with effective initial intervention'… → …'05 and HemorrhageCessationMagnitude 0.95 set to reflect effectively controlled hemorrhage state with initial …'…

- **`R1_SALT_MISMATCH`**
  - Rule: A row's declared SALT category must equal the category derived from that row's own authored vitals. The ground-truth category is derived live from physiology, never author-placed.
  - Authority: `knowledge_base/triage-system.md § Formulas — Ground-Truth Category Derivation`
  - Found: DeclaredCategory is Yellow. The category derived from this row's own vitals is Red, which disagrees with the declaration. Evidence: these SALT questions resolved false: (d) major hemorrhage controlled. Vitals as authored: RR 18 vs distress threshold 30; SBP 98 vs pulse-absent threshold 70; consciousness 0.85 vs altered threshold 0.5; hemorrhage insult magnitude 0.05; bSurvivableWithResources = True; bMinorInjuriesOnly = False.

## Where to look

- `knowledge_base/triage-system.md § Formulas — Ground-Truth Category Derivation`
- `knowledge_base/treatment-interventions.md § Tuning Knobs`
- `knowledge_base/casualty-archetype-schema.md § Placeholder-labeled clinical values and their sources`

This is a SALT coherence deadlock. The row's declared category and the category its own vitals derive disagree, and resolving it means deciding which of the two is authoritative for this casualty — a content judgement, not a mechanical fix.

The row's own numbers fail these SALT questions: (d) major hemorrhage controlled.

**Why the refiner could not close this.** The Refiner receives the failing row and the violations against it — nothing else. It does **not** receive the request brief that describes the casualty this row is meant to portray (see the module docstring in `pipeline/prompts.py`). Where a finding can only be settled from the brief, it is unresolvable from inside the loop by construction, however many attempts it is given. That is a deliberate boundary in this pipeline, not an accident, and it is what makes the circuit breaker reachable.

**To resolve**: work through `triage-system.md` § Formulas — Ground-Truth Category Derivation against the failed questions listed above, and decide whether the vitals or the declaration is describing this casualty correctly. Change the one that is wrong; changing both tends to move the disagreement rather than settle it.
