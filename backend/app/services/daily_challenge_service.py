"""DailyChallengeService — loads content/daily_challenges/YYYY_MM.json files
(plus translated content/daily_challenges/<locale>/YYYY_MM.json overlays).

The corpus is small (~6 monthly files, ~30 challenges each → 183 entries at
v1.0) so eager-loading at boot is cheap. Each challenge id is structured as
`dc_YYYY_MM_DD_<slug>`, which means "today's challenge" is a date-prefix
match — no separate index needed.

Locale layout (AT:R37):
  content/daily_challenges/*.json                  # canonical EN
  content/daily_challenges/<locale>/*.json         # translated (ar, ms, ...)

EN is canonical. Locale lookups fall back to EN per-id when a translation
is missing for that specific challenge.

Selection timezone is fixed to Asia/Kuala_Lumpur (Saiful's tz) for now;
when per-user timezones are wired, this becomes a parameter and the API
gets a `?tz=` override.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from threading import RLock
from zoneinfo import ZoneInfo

from app.core.logging import logger
from app.schemas.daily_challenge import DailyChallenge


CONTENT_DAILY_CHALLENGES_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "content"
    / "daily_challenges"
)

DEFAULT_TZ = ZoneInfo("Asia/Kuala_Lumpur")
DEFAULT_LOCALE = "en"


class DailyChallengeService:
    def __init__(self, content_dir: Path = CONTENT_DAILY_CHALLENGES_DIR) -> None:
        self._content_dir = content_dir
        # locale -> id -> DailyChallenge. "en" is canonical.
        self._by_locale: dict[str, dict[str, DailyChallenge]] = {}
        self._lock = RLock()
        self._reload()

    def _load_dir(self, directory: Path) -> dict[str, DailyChallenge]:
        out: dict[str, DailyChallenge] = {}
        for path in sorted(directory.glob("*.json")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                for item in raw:
                    ch = DailyChallenge(**item)
                    out[ch.id] = ch
            except Exception as e:
                logger.error(
                    "daily_challenge_load_failed",
                    path=str(path),
                    error=str(e),
                )
        return out

    def _reload(self) -> None:
        with self._lock:
            self._by_locale.clear()
            self._by_locale[DEFAULT_LOCALE] = self._load_dir(self._content_dir)
            for sub in sorted(p for p in self._content_dir.iterdir() if p.is_dir()):
                self._by_locale[sub.name] = self._load_dir(sub)
            logger.info(
                "daily_challenges_loaded",
                locales=sorted(self._by_locale.keys()),
                en_count=len(self._by_locale[DEFAULT_LOCALE]),
                locale_counts={
                    loc: len(items)
                    for loc, items in self._by_locale.items()
                    if loc != DEFAULT_LOCALE
                },
            )

    def _en(self) -> dict[str, DailyChallenge]:
        return self._by_locale.get(DEFAULT_LOCALE, {})

    def get_by_id(
        self, challenge_id: str, locale: str = DEFAULT_LOCALE
    ) -> DailyChallenge | None:
        with self._lock:
            localized = self._by_locale.get(locale, {}).get(challenge_id)
            if localized is not None:
                return localized
            return self._en().get(challenge_id)

    def for_date(
        self, d: date, locale: str = DEFAULT_LOCALE
    ) -> DailyChallenge | None:
        """Return the (first) challenge whose id matches today's date prefix.

        IDs look like `dc_2026_06_01_*`; we match the date stem and pick
        the lexicographically-smallest matching id (deterministic) — most
        days have a single challenge but if a month ever gets two, the
        smaller slug wins for stability.
        """
        prefix = f"dc_{d.year:04d}_{d.month:02d}_{d.day:02d}_"
        with self._lock:
            matches = sorted(k for k in self._en() if k.startswith(prefix))
            if not matches:
                return None
            return self.get_by_id(matches[0], locale=locale)

    def today(
        self,
        tz: ZoneInfo = DEFAULT_TZ,
        locale: str = DEFAULT_LOCALE,
    ) -> tuple[DailyChallenge | None, date]:
        d = datetime.now(tz).date()
        return self.for_date(d, locale=locale), d

    def all_challenges(
        self, locale: str = DEFAULT_LOCALE
    ) -> list[DailyChallenge]:
        with self._lock:
            loc_dict = self._by_locale.get(locale, {})
            return sorted(
                (loc_dict.get(ch.id, ch) for ch in self._en().values()),
                key=lambda c: c.id,
            )


_service: DailyChallengeService | None = None


def get_daily_challenge_service() -> DailyChallengeService:
    global _service
    if _service is None:
        _service = DailyChallengeService()
    return _service
