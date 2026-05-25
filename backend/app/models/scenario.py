"""
scenario.py — Pydantic models for a crime scenario.

The scenario is the root document that drives an entire game.
It is the ONLY source of truth — the AI, session state, and
evidence board all derive from it. Nothing here is shown to
the player directly; it lives only in the backend.

Load path: backend/scenarios/<scenario_id>.json → ScenarioModel
"""

from pydantic import BaseModel, field_validator, model_validator
from typing import List


class CrimeModel(BaseModel):
    """The facts of the crime itself — what actually happened."""
    victim: str
    method: str           # e.g. "poisoned wine"
    time_of_death: str    # e.g. "11:45 PM"
    location: str         # e.g. "study"


class SuspectModel(BaseModel):
    """
    One suspect's full dossier — both their public cover story
    and their hidden truths. The AI receives this whole object
    in its system prompt; the player never sees the hidden fields.
    """
    id: str
    name: str
    cover_story: str          # What they claim publicly
    actual_location: str      # Where they really were
    alibi_hole: str           # The specific weak point in their story
    what_they_know: List[str] # Facts they are aware of (can hint at these)
    what_they_hide: List[str] # Secrets they actively conceal
    emotional_tells: str      # How to portray stress / nervousness in dialogue
    pressure_threshold: int   # Questions before they start slipping (culprit = higher)
    is_culprit: bool = False


class ScenarioModel(BaseModel):
    """
    Full crime scenario. Exactly one suspect must be the culprit.
    Loaded once per game session; stored in the hidden truth store.
    """
    scenario_id: str
    title: str            # Display name, e.g. "The Ashworth Manor Affair"
    setting: str          # Flavour text for the detective's briefing
    crime: CrimeModel
    culprit_id: str       # Must match one suspect's id
    true_motive: str
    suspects: List[SuspectModel]

    @field_validator("suspects")
    @classmethod
    def must_have_at_least_two_suspects(cls, v: List[SuspectModel]) -> List[SuspectModel]:
        if len(v) < 2:
            raise ValueError("A scenario must have at least 2 suspects")
        return v

    @model_validator(mode="after")
    def culprit_id_must_exist(self) -> "ScenarioModel":
        ids = {s.id for s in self.suspects}
        if self.culprit_id not in ids:
            raise ValueError(f"culprit_id '{self.culprit_id}' not found in suspects list")
        return self

    @model_validator(mode="after")
    def exactly_one_is_culprit_flag(self) -> "ScenarioModel":
        culprits = [s for s in self.suspects if s.is_culprit]
        if len(culprits) != 1:
            raise ValueError(f"Exactly one suspect must have is_culprit=True, found {len(culprits)}")
        if culprits[0].id != self.culprit_id:
            raise ValueError("is_culprit flag must match culprit_id field")
        return self
