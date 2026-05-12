"""Glossary service — loads content/glossary/terms.<locale>.json on boot.

The glossary feeds two surfaces: the standalone in-app dictionary screen
and the inline `<Term id="…"/>` tooltips inside lessons. Both want O(1)
lookup by id, so the service holds an immutable in-memory dict keyed by
`(locale, id)`. Files are small (~190 entries × ~3 locales at v1.0) so
loading every shipped locale at startup is cheap.

Locale fallback is intentional: a `terms.ar.json` may not yet contain
every English id while translation catches up. `get(locale, id)`
returns the requested locale, then English, then None — so a user on
Arabic still sees a definition even if it's the EN string. The Flutter
side mirrors this with bundled assets, but the API exists so a future
beta build can hot-swap glossary entries without an app release.

Mirrors the static-content-loader pattern in `lessons_service.py`:
singleton constructed lazily, RLock for thread safety, `_reload()`
glob-loads every locale file under a known content directory.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from threading import RLock

from app.core.logging import logger
from app.schemas.glossary import (
    GlossaryCatalogue,
    GlossaryCategory,
    GlossaryEntry,
)


CONTENT_GLOSSARY_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent / "content" / "glossary"
)

DEFAULT_LOCALE = "en"


# Stable category ordering for the in-app A–Z screen. Anything the JSON
# introduces that isn't listed here falls to the end alphabetically — so
# new categories don't crash the catalogue.
CATEGORY_ORDER = [
    "basics",
    "order_types",
    "technical",
    "fundamental",
    "ratios",
    "psychology",
    "strategy",
    "regime",
    "macro",
    "options_derivatives",
    "scam",
    "platform",
    "advanced",
]


class GlossaryService:
    def __init__(self, content_dir: Path = CONTENT_GLOSSARY_DIR) -> None:
        self._content_dir = content_dir
        self._entries: dict[str, dict[str, GlossaryEntry]] = {}
        self._lock = RLock()
        self._reload()

    def _reload(self) -> None:
        with self._lock:
            self._entries.clear()
            for path in sorted(self._content_dir.glob("terms.*.json")):
                locale = path.stem.split(".", 1)[1]
                try:
                    raw = json.loads(path.read_text(encoding="utf-8"))
                    by_id: dict[str, GlossaryEntry] = {}
                    for item in raw:
                        entry = GlossaryEntry(**item)
                        by_id[entry.id] = entry
                    self._entries[locale] = by_id
                except Exception as e:
                    logger.error(
                        "glossary_load_failed", path=str(path), error=str(e)
                    )
            logger.info(
                "glossary_loaded",
                locales=sorted(self._entries.keys()),
                counts={k: len(v) for k, v in self._entries.items()},
            )

    def locales(self) -> list[str]:
        with self._lock:
            return sorted(self._entries.keys())

    def get(self, locale: str, term_id: str) -> GlossaryEntry | None:
        with self._lock:
            bucket = self._entries.get(locale)
            if bucket and term_id in bucket:
                return bucket[term_id]
            if locale != DEFAULT_LOCALE:
                fallback = self._entries.get(DEFAULT_LOCALE)
                if fallback and term_id in fallback:
                    return fallback[term_id]
            return None

    def catalogue(self, locale: str = DEFAULT_LOCALE) -> GlossaryCatalogue:
        with self._lock:
            bucket = self._entries.get(locale) or self._entries.get(DEFAULT_LOCALE) or {}
            by_category: dict[str, list[GlossaryEntry]] = defaultdict(list)
            for entry in bucket.values():
                by_category[entry.category].append(entry)

            ordered_categories = [c for c in CATEGORY_ORDER if c in by_category] + sorted(
                c for c in by_category if c not in CATEGORY_ORDER
            )
            categories: list[GlossaryCategory] = []
            for cat in ordered_categories:
                entries = sorted(by_category[cat], key=lambda e: e.term.lower())
                categories.append(GlossaryCategory(category=cat, entries=entries))
            total = sum(len(c.entries) for c in categories)
            return GlossaryCatalogue(
                locale=locale,
                categories=categories,
                total_terms=total,
            )


_service: GlossaryService | None = None


def get_glossary_service() -> GlossaryService:
    global _service
    if _service is None:
        _service = GlossaryService()
    return _service
