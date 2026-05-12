"""Glossary schemas.

Terms are flat JSON files in content/glossary/ keyed by locale
(terms.en.json, terms.ar.json, …). `id` is stable English snake_case and
is the join key both for cross-locale rendering and for inline
`<Term id="…"/>` references inside lesson MDX. Only `term` and
`definition` localise; structural fields (category, see_also,
related_lessons, related_agents, tags) stay locale-neutral.

The catalogue groups entries by category so the in-app glossary screen
can render a sectioned A–Z list without re-sorting on the client.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class GlossaryEntry(BaseModel):
    id: str
    term: str
    definition: str
    category: str
    see_also: list[str] = Field(default_factory=list)
    related_lessons: list[str] = Field(default_factory=list)
    related_agents: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class GlossaryCategory(BaseModel):
    category: str
    entries: list[GlossaryEntry]


class GlossaryCatalogue(BaseModel):
    locale: str
    categories: list[GlossaryCategory]
    total_terms: int
