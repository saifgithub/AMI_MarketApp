"""AICoachService — loads content/ai_coach/*.json, exposes substring/keyword
retrieval over the 280 Q&A library.

Two consumers:
  1. Concierge `scripted_reply` — when no keyword route hits, search the
     Q&A library and surface the top match's `short_answer` so the user
     gets a useful canned response even with the LLM offline.
  2. The in-app help screen — `/v1/ai_coach/search?q=...` and category
     browse endpoints feed a search UI.

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
        self._by_id: dict[str, CoachQA] = {}
        # Pre-computed token sets for fast scoring.
        self._tokens_by_id: dict[str, set[str]] = {}
        self._lock = RLock()
        self._reload()

    def _reload(self) -> None:
        with self._lock:
            self._by_id.clear()
            self._tokens_by_id.clear()
            for path in sorted(self._content_dir.glob("*.json")):
                try:
                    raw = json.loads(path.read_text(encoding="utf-8"))
                    for item in raw:
                        qa = CoachQA(**item)
                        self._by_id[qa.id] = qa
                        searchable = " ".join(
                            [qa.question, qa.short_answer, *qa.tags]
                        )
                        self._tokens_by_id[qa.id] = _tokens(searchable)
                except Exception as e:
                    logger.error(
                        "ai_coach_load_failed", path=str(path), error=str(e)
                    )
            logger.info("ai_coach_loaded", count=len(self._by_id))

    def get_by_id(self, qa_id: str) -> CoachQA | None:
        with self._lock:
            return self._by_id.get(qa_id)

    def by_category(self, category: str) -> list[CoachQA]:
        with self._lock:
            return sorted(
                (qa for qa in self._by_id.values() if qa.category == category),
                key=lambda x: x.id,
            )

    def categories(self) -> list[str]:
        with self._lock:
            return sorted({qa.category for qa in self._by_id.values()})

    def search(self, query: str, limit: int = 5) -> list[CoachSearchHit]:
        query_tokens = _tokens(query)
        if not query_tokens:
            return []
        with self._lock:
            scored: list[tuple[int, str, CoachQA]] = []
            for qa_id, qa in self._by_id.items():
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
