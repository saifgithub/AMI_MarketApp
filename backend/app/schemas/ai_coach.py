"""AI Coach Q&A schemas — categorised knowledge base for the Concierge to
retrieve from when the LLM is unavailable, and for an in-app help screen.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CoachQA(BaseModel):
    id: str
    category: str
    question: str
    short_answer: str
    long_answer: str
    related_lessons: list[str] = Field(default_factory=list)
    related_agents: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class CoachSearchHit(BaseModel):
    qa: CoachQA
    score: int  # token-overlap count


class CoachSearchResponse(BaseModel):
    query: str
    hits: list[CoachSearchHit]
    total: int


class CoachCategoryResponse(BaseModel):
    category: str
    items: list[CoachQA]
    total: int
