"""The seven archetype requests the pipeline is asked to author.

`casualty-model.md` § Overview sets the target: "Baseline POC target is a
hand-managed pool of ~5–15 full-fidelity casualty archetypes". The real
`DT_CasualtyArchetypes` has exactly one row today. These seven requests span the
whole SALT space so the evaluator has genuine work to do rather than seven
variations on the one casualty that already exists.

The briefs are written the way a content author's ticket would be written: the
injury, the scene, roughly how the casualty presents. What they deliberately do
NOT contain is the SALT decision tree, the derivation thresholds, or any hint of
which vitals produce which category. That omission is the whole experiment — see
the comment at the top of `prompts.py`.
"""

from __future__ import annotations

from dataclasses import dataclass

from .schema import SaltCategory


@dataclass(frozen=True)
class ArchetypeRequest:
    """One content request handed to the Generator role.

    ``intended_category`` is the pipeline operator's expectation, used only for
    reporting in the run log — it is never shown to the generator and never used
    by the evaluator, which derives ground truth from the row's own vitals.
    Keeping it out of both paths means a generator that authors a coherent row
    of a *different* category still passes, which is correct: the rule is
    internal coherence, not obedience to a wish list.

    There is deliberately no retrieval-terms field. Every prompt gets the same
    statically-sliced excerpt of the schema decision record (see `prompts.py`);
    nothing here retrieves, ranks or selects knowledge-base passages per
    request. Carrying a per-request keyword list that nothing reads would imply
    a retrieval step this pipeline does not have.
    """

    key: str
    intended_category: SaltCategory
    brief: str


REQUESTS: tuple[ArchetypeRequest, ...] = (
    ArchetypeRequest(
        key="ied_leg_hemorrhage_t1",
        intended_category=SaltCategory.RED,
        brief=(
            "The scenario's Tier-1 casualty. An adult caught by IED fragmentation "
            "in an active-shooter/blast warm zone, with a deep upper-leg wound "
            "bleeding heavily and steadily from the femoral region. Nothing has "
            "been done for them yet — no dressing, no tourniquet. They are on the "
            "ground, awake and frightened, able to answer you, and the bleeding is "
            "the thing that will kill them if nobody reaches it. A tourniquet is "
            "on the responder's belt and would very plausibly save this person. "
            "This is the archetype the existing hand-authored row describes; keep "
            "it close to that one."
        ),
    ),
    ArchetypeRequest(
        key="ambulatory_lac_forearm",
        intended_category=SaltCategory.GREEN,
        brief=(
            "Walking wounded. An adult who was near a shattered window and has a "
            "shallow forearm laceration, already crudely pressed closed with their "
            "own sleeve — it is oozing, not pumping, and it has essentially "
            "stopped. They walked to you on their own when asked, they are fully "
            "alert, arguing that other people need help more than they do, and "
            "their breathing is unremarkable. Nothing about this person is "
            "time-critical. Their injuries are minor and nothing else is wrong "
            "with them."
        ),
    ),
    ArchetypeRequest(
        key="tension_pneumo_chest",
        intended_category=SaltCategory.RED,
        brief=(
            "A penetrating wound to the upper chest from a fragment. The casualty "
            "is working hard to breathe — panting, shallow, far faster than a "
            "resting adult, visibly struggling and getting worse minute by minute. "
            "They are still awake and can talk to you in short broken phrases. "
            "There is no dramatic external pool of blood; the emergency is the "
            "breathing. Needle decompression is within the responder's scope and "
            "on scene, and this person would very plausibly survive if it happens "
            "soon."
        ),
    ),
    ArchetypeRequest(
        key="abdominal_evisceration",
        intended_category=SaltCategory.YELLOW,
        brief=(
            "An abdominal wound with bowel exposed, covered with a moist dressing "
            "by a bystander before you arrived. It looks appalling but it is not "
            "actively pouring blood right now. The casualty is pale and quiet but "
            "awake and tracking you, answering questions, and breathing at an "
            "ordinary rate. Their pulse is present at the wrist. This is a serious "
            "injury that will get worse over the next hour without surgery, but at "
            "this moment they are holding steady, and they are definitely not a "
            "minor-injury patient."
        ),
    ),
    ArchetypeRequest(
        key="severe_tbi_expectant",
        intended_category=SaltCategory.GRAY,
        brief=(
            "An open head injury with visible brain matter. The casualty is still "
            "drawing occasional irregular gasping breaths but is completely "
            "unresponsive — no reaction to voice, no purposeful movement at all, "
            "nothing when you touch them. Their pressure is very low and you "
            "cannot feel anything at the wrist. Given what is on scene — no "
            "neurosurgery, no blood, a single responder and several other "
            "casualties who can be saved — this person cannot be saved with the "
            "resources actually available. They still receive comfort care."
        ),
    ),
    ArchetypeRequest(
        key="blast_apnea_black",
        intended_category=SaltCategory.BLACK,
        brief=(
            "A casualty found face-down close to the seat of the blast. The "
            "responder has already rolled them and repositioned the airway once, "
            "which is the one attempt doctrine allows. There is still no air "
            "movement at all — no chest rise, no breath sounds, nothing. No "
            "external bleeding worth naming. Author this archetype as the "
            "casualty who is not breathing after that airway attempt."
        ),
    ),
    ArchetypeRequest(
        key="flash_burn_forearms",
        intended_category=SaltCategory.YELLOW,
        brief=(
            "Flash burns to both forearms and the backs of both hands from the "
            "initial fireball — blistered, weeping, extremely painful, but the "
            "face is clean, there is no soot around the mouth or nose, the voice "
            "is normal and there is no coughing or hoarseness. The casualty is "
            "sitting up, fully alert, answering everything you ask, breathing "
            "comfortably, with a strong pulse at the wrist and no bleeding "
            "anywhere. Burns this size need burn-centre care within hours, so "
            "this is not somebody you can wave off with the walking wounded, but "
            "nothing about them is going to change in the next few minutes."
        ),
    ),
)
