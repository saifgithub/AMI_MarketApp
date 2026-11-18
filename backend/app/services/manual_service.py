"""App-manual service — loads `content/manual/*.en.mdx` and retrieves entries.

CR022 / CR267 WP-39. The Concierge's knowledge of how the app works, authored
and parsed exactly like lessons (frontmatter + MDX body, `lessons_service`'s
frontmatter regex), kept in memory (immutable, tiny) and handed to the
Concierge through the same prompt seam as the lesson catalogue
(`concierge_prompts.build_concierge_messages`).

Retrieval is lexical: the question is tokenised, stop-worded and lightly
stemmed, then matched against each entry's title, tags, `questions` phrasings
and `short_answer`, weighted by field and by inverse document frequency so
that a word every entry uses ("portfolio", "tab") does not outvote the word
that identifies one ("reset", "journal"). No embedding model is needed for a
corpus this size; CR019's embedding mode remains the escape hatch if it grows.

Degrade loudly: a corpus that fails to parse raises at first use, and
`retrieve()` turns that into `available=False` plus an error log, so the
prompt tells AMI it cannot check the manual instead of improvising screens.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from threading import RLock

import yaml

from app.core.logging import logger
from app.schemas.manual import ManualEntry, ManualHit, ManualRetrieval
from app.services.lessons_service import _FRONTMATTER_RE

CONTENT_MANUAL_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent / "content" / "manual"
)

# A question must score at least this to count as "the manual covers it".
# Calibrated against the fixed question set in tests/fixtures (see
# test_manual_corpus.py): every real how-to clears it, off-topic questions
# ("what is a P/E ratio") do not.
MIN_SCORE = 9.0
# A second entry is supplied only when it is nearly as good as the first.
SECOND_HIT_RATIO = 0.75
MAX_HITS = 2

_FIELD_WEIGHT = {"title": 3.0, "tags": 2.0, "questions": 2.0, "answer": 1.0}
# Added in proportion to the share of the question's words an entry covers, so
# a short question that an entry fully covers ("where is my journal?") is not
# outscored by a long one that merely brushes several entries.
COVERAGE_BONUS = 6.0
# Words that name the same thing in the app's labels and in testers' mouths.
_SYNONYMS = {"maximum": "max", "minimum": "min", "login": "sign", "log": "sign"}

_STOPWORDS = frozenset(
    {
        "a", "an", "the", "is", "are", "was", "were", "be", "been", "and", "or",
        "but", "if", "then", "so", "of", "to", "in", "on", "at", "by", "for",
        "with", "from", "as", "this", "that", "these", "those", "i", "you",
        "we", "they", "it", "my", "your", "our", "their", "its", "me", "do",
        "does", "did", "have", "has", "had", "can", "could", "should", "would",
        "will", "may", "might", "what", "when", "where", "why", "how", "which",
        "who", "there", "about", "into", "up", "out", "get", "want", "need",
        "please", "tell", "show", "app", "ami", "go", "use",
    }
)
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_SUFFIXES = ("ing", "ed", "es", "s", "e")


def _stem(token: str) -> str:
    for suffix in _SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            return token[: -len(suffix)]
    return token


def tokenize(text: str) -> set[str]:
    return {
        _stem(_SYNONYMS.get(t, t))
        for t in _TOKEN_RE.findall(text.lower())
        if t not in _STOPWORDS and len(t) > 1
    }


def parse_entry(path: Path) -> ManualEntry:
    raw = path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RE.match(raw)
    if not m:
        raise ValueError(f"Missing frontmatter in {path.name}")
    fm = yaml.safe_load(m.group(1)) or {}
    try:
        return ManualEntry(
            id=fm["id"],
            title=fm["title"],
            section=fm["section"],
            topic=fm["topic"],
            tags=list(fm.get("tags") or []),
            questions=list(fm.get("questions") or []),
            short_answer=fm["short_answer"],
            screens=list(fm.get("screens") or []),
            arb_keys=list(fm.get("arb_keys") or []),
            literals=list(fm.get("literals") or []),
            locale_versions=list(fm.get("locale_versions") or ["en"]),
            translation_pending=list(fm.get("translation_pending") or []),
            created_at=str(fm.get("created_at", "")),
            updated_at=str(fm.get("updated_at", "")),
            body=m.group(2).strip(),
        )
    except KeyError as exc:
        raise ValueError(f"{path.name}: frontmatter is missing {exc}") from exc


class ManualService:
    def __init__(self, content_dir: Path = CONTENT_MANUAL_DIR) -> None:
        self._content_dir = content_dir
        self._lock = RLock()
        self._entries: dict[str, ManualEntry] = {}
        self._field_tokens: dict[str, dict[str, set[str]]] = {}
        self._idf: dict[str, float] = {}
        self._reload()

    def _reload(self) -> None:
        paths = sorted(self._content_dir.glob("*.en.mdx"))
        if not paths:
            raise ValueError(f"No manual entries found in {self._content_dir}")
        entries: dict[str, ManualEntry] = {}
        for path in paths:
            entry = parse_entry(path)
            if entry.id in entries:
                raise ValueError(f"Duplicate manual id {entry.id!r} ({path.name})")
            entries[entry.id] = entry

        field_tokens: dict[str, dict[str, set[str]]] = {}
        df: dict[str, int] = {}
        for entry in entries.values():
            fields = {
                "title": tokenize(entry.title),
                "tags": tokenize(" ".join(entry.tags)),
                "questions": tokenize(" ".join(entry.questions)),
                "answer": tokenize(entry.short_answer),
            }
            field_tokens[entry.id] = fields
            for tok in set().union(*fields.values()):
                df[tok] = df.get(tok, 0) + 1
        n = len(entries)
        idf = {tok: math.log(1 + n / count) for tok, count in df.items()}
        with self._lock:
            self._entries = entries
            self._field_tokens = field_tokens
            self._idf = idf
        logger.info("manual_corpus_loaded", entries=n)

    def all_entries(self) -> list[ManualEntry]:
        return sorted(self._entries.values(), key=lambda e: e.id)

    def get(self, entry_id: str) -> ManualEntry | None:
        return self._entries.get(entry_id)

    def search(self, query: str, limit: int = 5) -> list[ManualHit]:
        q = tokenize(query)
        if not q:
            return []
        hits: list[ManualHit] = []
        for entry_id, fields in self._field_tokens.items():
            score = 0.0
            matched = 0
            for tok in q:
                weight = max(
                    (_FIELD_WEIGHT[f] for f, toks in fields.items() if tok in toks),
                    default=0.0,
                )
                if weight:
                    matched += 1
                    score += weight * self._idf.get(tok, 0.0)
            if score > 0:
                score += COVERAGE_BONUS * (matched / len(q)) ** 2
                hits.append(ManualHit(entry=self._entries[entry_id], score=round(score, 3)))
        hits.sort(key=lambda h: (-h.score, h.entry.id))
        return hits[:limit]

    def retrieve(self, query: str) -> list[ManualHit]:
        """Entries the manual should answer this question from (0 to MAX_HITS)."""
        hits = self.search(query, limit=MAX_HITS)
        if not hits or hits[0].score < MIN_SCORE:
            return []
        top = hits[0].score
        return [h for i, h in enumerate(hits) if i == 0 or h.score >= top * SECOND_HIT_RATIO]


_service: ManualService | None = None
_service_lock = RLock()


def get_manual_service() -> ManualService:
    global _service
    with _service_lock:
        if _service is None:
            _service = ManualService()
        return _service


def retrieve_manual(query: str) -> ManualRetrieval:
    """Concierge-facing retrieval. Never raises; a broken corpus is loud and flagged."""
    try:
        return ManualRetrieval(available=True, hits=get_manual_service().retrieve(query))
    except Exception as exc:  # noqa: BLE001 — a bad corpus must not kill the chat turn
        logger.error("manual_corpus_unavailable", error=str(exc)[:300])
        return ManualRetrieval(available=False, hits=[])


def manual_citation(hits: list[ManualHit]) -> str:
    """The deterministic source line appended to a manual-grounded reply."""
    if not hits:
        return ""
    cited = "; ".join(f"{h.entry.title} ({h.entry.id})" for h in hits)
    return f"\n\n— Source: AMI app manual · {cited}"
