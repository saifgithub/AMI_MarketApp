"""App-manual schemas (CR022 / CR267 WP-39).

The manual is the Concierge's "how the app works" knowledge base: MDX files in
`content/manual/` with YAML frontmatter, authored and loaded the same way as
lessons (`lessons_service.parse_mdx`) but a far smaller corpus (tens of
entries, not hundreds).

Three frontmatter fields exist only so the corpus can be checked against the
app instead of trusted: `screens` (Flutter files the entry describes),
`arb_keys` (l10n keys whose text the body quotes in **bold**) and `literals`
(bold labels that are hard-coded in those Dart files). `test_manual_corpus`
fails the build when any of them stops matching the app.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ManualEntry(BaseModel):
    id: str
    title: str
    section: str
    topic: str
    tags: list[str] = Field(default_factory=list)
    # Natural phrasings a tester would type; the retrieval index.
    questions: list[str] = Field(default_factory=list)
    # One or two sentences; the whole answer on the scripted (LLM-offline) path.
    short_answer: str
    screens: list[str] = Field(default_factory=list)
    arb_keys: list[str] = Field(default_factory=list)
    literals: list[str] = Field(default_factory=list)
    # Beta is English-only. `translation_pending` is the flag the i18n lane
    # reads to know which locales still owe a translation of this entry.
    locale_versions: list[str] = Field(default_factory=lambda: ["en"])
    translation_pending: list[str] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    body: str = ""


class ManualHit(BaseModel):
    entry: ManualEntry
    score: float


class ManualRetrieval(BaseModel):
    """What the Concierge got for one question.

    `available=False` means the corpus failed to load — distinct from "loaded,
    nothing matched" so the prompt can tell AMI to say it cannot check the
    manual rather than improvise screens (degrade loudly, CR040).
    """

    available: bool = True
    hits: list[ManualHit] = Field(default_factory=list)
