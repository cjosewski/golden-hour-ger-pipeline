# Escalation — `severe_tbi_expectant`

- **Requested as**: Gray
- **Drafts evaluated**: 2 (1 refine attempt(s))
- **Circuit breaker tripped because**: no progress: the same rule broke on two consecutive attempts (R1_SALT_MISMATCH). The refiner is returning an equivalent draft rather than reconciling the finding

This row was **not** written to `DT_CasualtyArchetypes.generated.csv`. A row the pipeline knows is incoherent is worse than a missing row: it imports cleanly, looks plausible, and silently supplies the wrong ground truth to scoring.

## The brief

An open head injury with visible brain matter. The casualty is still drawing occasional irregular gasping breaths but is completely unresponsive — no reaction to voice, no purposeful movement at all, nothing when you touch them. Their pressure is very low and you cannot feel anything at the wrist. Given what is on scene — no neurosurgery, no blood, a single responder and several other casualties who can be saved — this person cannot be saved with the resources actually available. They still receive comfort care.

## Attempt history

### Attempt 1 — initial draft

- **Declared**: Gray · **Derived**: Red
- **Vitals**: HR 44 · RR 6 (distress threshold 30) · SpO2 72% · BP 52/30 (pulse-absent below 70) · consciousness 0.02 (altered below 0.5) · hemorrhage insult 0 · survivable True · minor-injuries-only False
- **Authoring note**: Open head injury with agonal respirations. Vitals are a clinically plausible placeholder — SME validation pending. Expectant given the resources on scene; comfort care only.

- **`R1_SALT_MISMATCH`**
  - Rule: A row's declared SALT category must equal the category derived from that row's own authored vitals. The ground-truth category is derived live from physiology, never author-placed.
  - Authority: `knowledge_base/triage-system.md § Formulas — Ground-Truth Category Derivation`
  - Found: DeclaredCategory is Gray. The category derived from this row's own vitals is Red, which disagrees with the declaration. Evidence: these SALT questions resolved false: (a) obeys commands or shows purposeful movement; (b) peripheral pulse present. Vitals as authored: RR 6 vs distress threshold 30; SBP 52 vs pulse-absent threshold 70; consciousness 0.02 vs altered threshold 0.5; hemorrhage insult magnitude 0; bSurvivableWithResources = True; bMinorInjuriesOnly = False.

### Attempt 2 — refiner revision 1

- **Declared**: Gray · **Derived**: Red
- **Vitals**: HR 44 · RR 6 (distress threshold 30) · SpO2 72% · BP 52/30 (pulse-absent below 70) · consciousness 0.02 (altered below 0.5) · hemorrhage insult 0 · survivable True · minor-injuries-only False
- **Authoring note**: Open head injury with agonal respirations. Vitals are a clinically plausible placeholder — SME validation pending. Expectant given the resources on scene; comfort care only. Reviewed again (revision 1); the authored presentation is believed correct as written.

- **`R1_SALT_MISMATCH`**
  - Rule: A row's declared SALT category must equal the category derived from that row's own authored vitals. The ground-truth category is derived live from physiology, never author-placed.
  - Authority: `knowledge_base/triage-system.md § Formulas — Ground-Truth Category Derivation`
  - Found: DeclaredCategory is Gray. The category derived from this row's own vitals is Red, which disagrees with the declaration. Evidence: these SALT questions resolved false: (a) obeys commands or shows purposeful movement; (b) peripheral pulse present. Vitals as authored: RR 6 vs distress threshold 30; SBP 52 vs pulse-absent threshold 70; consciousness 0.02 vs altered threshold 0.5; hemorrhage insult magnitude 0; bSurvivableWithResources = True; bMinorInjuriesOnly = False.

## Where to look

- `knowledge_base/triage-system.md § Formulas — Ground-Truth Category Derivation`

This is a SALT coherence deadlock. The row's declared category and the category its own vitals derive disagree, and resolving it means deciding which of the two is authoritative for this casualty — a content judgement, not a mechanical fix.

The row's own numbers fail these SALT questions: (a) obeys commands or shows purposeful movement; (b) peripheral pulse present.

**Why the refiner could not close this.** The Refiner receives the failing row and the violations against it — nothing else. It does **not** receive the request brief that describes the casualty this row is meant to portray (see the module docstring in `pipeline/prompts.py`). Where a finding can only be settled from the brief, it is unresolvable from inside the loop by construction, however many attempts it is given. That is a deliberate boundary in this pipeline, not an accident, and it is what makes the circuit breaker reachable.

**And this one turns on the game's own open question.** The disagreement here is the Immediate-versus-Expectant split, which `triage-system.md` § Formulas decides with `survivable_with_resources` — a field that same section flags **[To be designed]**: "SALT's real-world definition of this question is resource- and judgment-based, not threshold-based ... Do not hardcode this as always-true; it needs an explicit design decision before the Expectant category can be authored honestly." The document's Open Questions table assigns that decision to the acting SME plus the game designer before Phase 2 closes. So even a refiner that *did* read the brief would find no rule in the knowledge base to reason from — only the brief's own assertion about this casualty.

**To resolve**: decide from the brief above whether this casualty is salvageable with what is on scene, set `bSurvivableWithResources` accordingly, and re-run. If the brief itself is ambiguous, that is the finding — it belongs in the open question, not in this row.
