"""DailyChallengeService — loads content/daily_challenges/YYYY_MM.json files.

The corpus is small (~6 monthly files, ~30 challenges each → 183 entries at
v1.0) so eager-loading at boot is cheap. Each challenge id is structured as
`dc_YYYY_MM_DD_<slug>`, which means "today's challenge" is a date-prefix
match — no separate index needed.

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


class DailyChallengeService:
    def __init__(self, content_dir: Path = CONTENT_DAILY_CHALLENGES_DIR) -> None:
        self._content_dir = content_dir
        self._by_id: dict[str, DailyChallenge] = {}
        self._lock = RLock()
        self._reload()

    def _reload(self) -> None:
        with self._lock:
            self._by_id.clear()
            for path in sorted(self._content_dir.glob("*.json")):
                try:
                    raw = json.loads(path.read_text(encoding="utf-8"))
                    for item in raw:
                        ch = DailyChallenge(**item)
                        self._by_id[ch.id] = ch
                except Exception as e:
                    logger.error(
                        "daily_challenge_load_failed",
                        path=str(path),
                        error=str(e),
                    )
            logger.info("daily_challenges_loaded", count=len(self._by_id))

    def get_by_id(self, challenge_id: str) -> DailyChallenge | None:
        with self._lock:
            return self._by_id.get(challenge_id)

    def for_date(self, d: date) -> DailyChallenge | None:
        """Return the (first) challenge whose id matches today's date prefix.

        IDs look like `dc_2026_06_01_*`; we match the date stem and pick
        the lexicographically-smallest matching id (deterministic) — most
        days have a single challenge but if a month ever gets two, the
        smaller slug wins for stability.
        """
        prefix = f"dc_{d.year:04d}_{d.month:02d}_{d.day:02d}_"
        with self._lock:
            matches = sorted(k for k in self._by_id if k.startswith(prefix))
            return self._by_id[matches[0]] if matches else None

    def today(self, tz: ZoneInfo = DEFAULT_TZ) -> tuple[DailyChallenge | None, date]:
        d = datetime.now(tz).date()
        return self.for_date(d), d

    def all_challenges(self) -> list[DailyChallenge]:
        with self._lock:
            return sorted(self._by_id.values(), key=lambda c: c.id)


_service: DailyChallengeService | None = None


def get_daily_challenge_service() -> DailyChallengeService:
    global _service
    if _service is None:
        _service = DailyChallengeService()
    return _service
