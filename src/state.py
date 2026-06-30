"""Shared state and structured-output schemas."""

from __future__ import annotations

import operator
from typing import Annotated, Literal, TypedDict

from pydantic import BaseModel, Field

VerdictLiteral = Literal["supported", "refuted", "unverifiable"]


# --- Structured LLM outputs (one per contour) --------------------------------------


class ScreeningProfile(BaseModel):
    """Contour 1 output: a rhetorical-risk profile, NOT a truth verdict."""

    manipulation_probability: float = Field(
        ge=0.0, le=1.0, description="0..1 likelihood the text is rhetorically manipulative"
    )
    techniques: list[str] = Field(
        default_factory=list,
        description="Manipulation techniques detected (e.g. fear_appeal, bandwagon, selective_truth)",
    )
    triggers: list[str] = Field(
        default_factory=list,
        description="VERBATIM fragments copied exactly from the input that triggered the risk "
        "(so they can be highlighted in the original text)",
    )
    explanation: str = Field(
        default="",
        description="УКРАЇНСЬКОЮ, 1-2 речення: ЧОМУ ці фрагменти/техніки роблять текст маніпулятивним (риторика, не факти)",
    )
    confidence_band: Literal["low", "medium", "high"] = "medium"
    escalate: bool = Field(
        description="True if the message warrants the more expensive narrative + fact-check contours"
    )


class ClaimBundle(BaseModel):
    """Contour 2 output: the narrative/intent schema plus checkable claims."""

    narrative: str = Field(description="Canonical one-sentence storyline (not a summary)")
    actors_and_roles: list[str] = Field(
        default_factory=list, description="Key actors and the role assigned to them"
    )
    intent: str = Field(description="Communicative function: intimidate, discredit, mobilize, normalize, ...")
    claims: list[str] = Field(
        default_factory=list,
        description="Atomic, retrieval-ready checkable claims. Empty if nothing is verifiable.",
    )
    query_hints: list[str] = Field(
        default_factory=list, description="Entities/terms/dates to seed evidence retrieval"
    )


class EvidenceItem(BaseModel):
    source: str = Field(description="URL or source identifier")
    snippet: str = Field(description="Quoted fragment supporting/refuting the claim")


class FactVerdict(BaseModel):
    """Contour 3 output for a single claim, with evidence provenance."""

    claim: str
    verdict: VerdictLiteral
    evidence: list[EvidenceItem] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


class FinalDecision(BaseModel):
    """Final synthesis returned to the human analyst.

    Two distinct dimensions are reported separately:
    - manipulation = rhetorical FORM (techniques), regardless of factual truth;
    - disinformation = factual CONTENT (false claims), grounded in evidence.
    A text can be manipulative without being verifiable disinformation, and vice versa.
    """

    verdict: str = Field(description="Overall verdict, e.g. likely_disinformation / likely_reliable / unverified")
    confidence_band: Literal["low", "medium", "high"] = "medium"
    abstention: bool = Field(description="True when evidence is insufficient for a firm verdict")
    is_manipulative: bool = Field(description="Does the text use manipulative rhetoric (form)?")
    manipulation_explanation: str = Field(
        description="УКРАЇНСЬКОЮ: чому текст маніпулятивний чи ні — техніки і як вони змінюють інтерпретацію (НЕ про факти)"
    )
    is_disinformation: bool = Field(description="Are its factual claims false/misleading (content)?")
    disinformation_explanation: str = Field(
        description="УКРАЇНСЬКОЮ: чому це дезінформація чи ні — спираючись на докази; якщо доказів бракує — невизначеність"
    )


# --- Graph state -------------------------------------------------------------------


class DisinfoState(TypedDict, total=False):
    """Shared request state. ``total=False`` so nodes fill in their own blocks."""

    content: str
    content_id: str

    # contour 1
    manipulation_probability: float
    manipulation_techniques: list[str]
    screening_profile: dict

    # contour 2
    narrative: str
    intent: str
    claims: list[str]
    query_hints: list[str]

    # contour 3
    search_queries: list[str]
    search_results: list[dict]
    fact_check_results: list[dict]
    narrative_explanation: str

    # synthesis
    final_result: dict

    # service layer — append-only journal so parallel branches don't clobber it
    audit_log: Annotated[list[str], operator.add]
