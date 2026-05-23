"""AICoachService — loads content/ai_coach/*.json + content/ai_coach/<locale>/*.json,
exposes substring/keyword retrieval over the 280 Q&A library.

Two consumers:
  1. Concierge `scripted_reply` — when no keyword route hits, search the
     Q&A library and surface the top match's `short_answer` so the user
     gets a useful canned response even with the LLM offline.
  2. The in-app help screen — `/v1/ai_coach/search?q=...` and category
     browse endpoints feed a search UI.

Locale layout (AT:R37):
  content/ai_coach/*.json                  # canonical EN
  content/ai_coach/<locale>/*.json         # translated (ar, ms, ...)

EN is always loaded from the root flat layout. Each `<locale>/` subdir
contains the same shape (translated `question` + `short_answer` + tags
left as-is since they're search keys). Lookups fall back to EN when a
locale is missing or a specific id wasn't translated. The keyword
retriever's pre-computed token sets are EN-only — non-EN search is a
future problem (BL4 / embedding pipeline at Beta).

Scoring: token-overlap between the lowercased, punctuation-stripped query
and each entry's `question + tags`. Ties broken by lex order on id. A full
embedding pipeline lands at Beta — this keyword retriever is the cheap-and-
correct floor that ships at Alpha.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from threading import RLock

from app.core.logging import logger
from app.schemas.ai_coach import CoachQA, CoachSearchHit


CONTENT_AI_COACH_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent / "content" / "ai_coach"
)
DEFAULT_LOCALE = "en"

# Common english stop words that hurt retrieval more than they help.
_STOPWORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "and", "or", "but", "if", "then", "so", "of", "to", "in", "on", "at",
    "by", "for", "with", "from", "as", "this", "that", "these", "those",
    "i", "you", "we", "they", "it", "my", "your", "our", "their", "its",
    "do", "does", "did", "have", "has", "had", "can", "could", "should",
    "would", "will", "may", "might", "what", "when", "where", "why", "how",
})

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return {
        t for t in _TOKEN_RE.findall(text.lower())
        if t not in _STOPWORDS and len(t) > 1
    }


class AICoachService:
    def __init__(self, content_dir: Path = CONTENT_AI_COACH_DIR) -> None:
        self._content_dir = content_dir
        # locale -> id -> CoachQA. "en" is canonical; others fall back to it.
        self._by_locale: dict[str, dict[str, CoachQA]] = {}
        # Pre-computed token sets for fast scoring (EN-only — search runs EN).
        self._tokens_by_id: dict[str, set[str]] = {}
        self._lock = RLock()
        self._reload()

    def _load_dir(self, directory: Path) -> dict[str, CoachQA]:
        out: dict[str, CoachQA] = {}
        for path in sorted(directory.glob("*.json")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                for item in raw:
                    qa = CoachQA(**item)
                    out[qa.id] = qa
            except Exception as e:
                logger.error(
                    "ai_coach_load_failed", path=str(path), error=str(e)
                )
        return out

    def _reload(self) -> None:
        with self._lock:
            self._by_locale.clear()
            self._tokens_by_id.clear()
            # EN — flat root layout.
            en = self._load_dir(self._content_dir)
            self._by_locale[DEFAULT_LOCALE] = en
            for qa in en.values():
                searchable = " ".join([qa.question, qa.short_answer, *qa.tags])
                self._tokens_by_id[qa.id] = _tokens(searchable)
            # Translated locales — one subdir per locale, same file shape.
            for sub in sorted(p for p in self._content_dir.iterdir() if p.is_dir()):
                self._by_locale[sub.name] = self._load_dir(sub)
            logger.info(
                "ai_coach_loaded",
                locales=sorted(self._by_locale.keys()),
                en_count=len(en),
                locale_counts={
                    loc: len(items)
                    for loc, items in self._by_locale.items()
                    if loc != DEFAULT_LOCALE
                },
            )

    def _en(self) -> dict[str, CoachQA]:
        return self._by_locale.get(DEFAULT_LOCALE, {})

    def get_by_id(
        self, qa_id: str, locale: str = DEFAULT_LOCALE
    ) -> CoachQA | None:
        with self._lock:
            localized = self._by_locale.get(locale, {}).get(qa_id)
            if localized is not None:
                return localized
            return self._en().get(qa_id)

    def by_category(
        self, category: str, locale: str = DEFAULT_LOCALE
    ) -> list[CoachQA]:
        with self._lock:
            # Iterate EN to define the universe; substitute localized rows.
            loc_dict = self._by_locale.get(locale, {})
            return sorted(
                (
                    loc_dict.get(qa.id, qa)
                    for qa in self._en().values()
                    if qa.category == category
                ),
                key=lambda x: x.id,
            )

    def categories(self) -> list[str]:
        with self._lock:
            return sorted({qa.category for qa in self._en().values()})

    def search(self, query: str, limit: int = 5) -> list[CoachSearchHit]:
        query_tokens = _tokens(query)
        if not query_tokens:
            return []
        with self._lock:
            scored: list[tuple[int, str, CoachQA]] = []
            for qa_id, qa in self._en().items():
                tokens = self._tokens_by_id.get(qa_id, set())
                score = len(query_tokens & tokens)
                if score > 0:
                    scored.append((score, qa_id, qa))
            # Higher score first; tie-break by id ascending for stability.
            scored.sort(key=lambda t: (-t[0], t[1]))
            return [CoachSearchHit(qa=qa, score=s) for s, _, qa in scored[:limit]]

    def top_hit(self, query: str, *, min_score: int = 2) -> CoachQA | None:
        """One-shot helper for the Concierge fallback. Returns the top
        match only if its score >= min_score, otherwise None — so a
        weak match doesn't surface as a confident-looking answer.
        """
        hits = self.search(query, limit=1)
        if not hits:
            return None
        return hits[0].qa if hits[0].score >= min_score else None


_service: AICoachService | None = None


def get_ai_coach_service() -> AICoachService:
    global _service
    if _service is None:
        _service = AICoachService()
    return _service
