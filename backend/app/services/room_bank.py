"""CR267 WP-24 — same inputs return the same Room.

Two things live here, both pure of the Room runner (the runner imports this):

1. **The frozen fact sheet.** A ticker's sheet is built once per trading day and
   stored; every later Room that day reads the stored copy, so the same day
   yields a byte-identical sheet and the sheet can be hashed. The stored form is
   the CR237 `encode_profile` codec, and the copy handed back is always decoded
   from the stored bytes, so the first reader and every later one see the same
   object graph.

2. **The Room key.** SHA-256 over (user, ticker, mandate digest, fact-sheet hash,
   policy version, model root). A convene whose key matches a finished Room is
   handed that Room. The key is per user: sharing Rooms across users is a later
   cost optimisation, not this programme's.

What the key deliberately does NOT contain: the credit balance, the plan, the
mandate's version counter and timestamps (re-saving an unchanged mandate is not a
new input), the user's holdings, and the Decision Journal. The first three change
without changing the Room; the last two are inputs the spec leaves out, and a
journal that gained the previous run's own entry would otherwise make every
repeat convene a miss.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.logging import logger
from app.db import get_session
from app.db.models import RoomFactSheetRow, RoomRunRow
from app.schemas import AgentId
from app.schemas.mandate import Mandate
from app.services.cio_snapshot_codec import decode_profile, encode_profile
from app.trading_math.session_calendar import last_us_session_date

# Bump when the Room's decision logic changes in a way the assembled prompts do
# not capture (a new aggregation rule, a changed compliance floor). The prompt
# generation is hashed in separately and moves on its own.
ROOM_POLICY_REVISION = "1"

# `Mandate` fields that are not part of what the user asked for. Plan state is
# stamped on at read time (never persisted on the row); `version`/`created_at`/
# `updated_at` move on a save that changed nothing.
MANDATE_KEY_EXCLUDED: frozenset[str] = frozenset({
    "version",
    "plan",
    "trial_expires_at",
    "credit_balance",
    "credit_allowance",
    "credits_reset_at",
    "room_cost",
    "room_live_data_surcharge_max",
    "room_cooldown_until",
    "resolved",
    "day_trader_preset",
    "created_at",
    "updated_at",
})


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def trading_date_for(now: datetime) -> date:
    """The US equities session date `now` belongs to (see `session_calendar`)."""
    return last_us_session_date(now)


def mandate_digest(mandate: Mandate) -> str:
    """Hash of the mandate's content: every field except plan state, the
    version counter and timestamps."""
    data = mandate.model_dump(mode="json", exclude=set(MANDATE_KEY_EXCLUDED))
    return _sha256(_canonical(data))


def policy_version() -> str | None:
    """The Room's policy generation: the derived prompt version of every agent
    that has one, plus `ROOM_POLICY_REVISION`. None when no prompt version can be
    computed at all, in which case the caller must not bank."""
    from app.services.prompt_version import prompt_version

    versions = {a.value: prompt_version(a) for a in AgentId}
    if not any(versions.values()):
        return None
    return _sha256(_canonical({"revision": ROOM_POLICY_REVISION, "prompts": versions}))[:16]


def sheet_variant(
    *, news_state: str, social_state: str, market_withheld: bool,
) -> str:
    """What may legitimately differ between two users' sheets for one ticker on
    one day. The sheet a user gets depends on which live feeds they were
    entitled to and on whether the Market desk is pulled back."""
    return f"news={news_state}|social={social_state}|market={'withheld' if market_withheld else 'present'}"


@dataclass(frozen=True)
class FrozenSheet:
    profile: dict[str, Any]
    # None when the sheet could not be frozen (a value the codec cannot encode,
    # or the store was unreachable): the Room still runs on `profile`, unbanked.
    sheet_hash: str | None
    trading_date: date
    variant: str


def freeze_fact_sheet(
    *,
    ticker: str,
    trading_date: date,
    variant: str,
    build: Callable[[], dict[str, Any]],
) -> FrozenSheet:
    """The stored sheet for (ticker, trading_date, variant), building and storing
    it on the first call. Concurrent first calls converge on one stored sheet:
    the loser of the unique constraint re-reads the winner's row."""
    sym = ticker.upper()
    existing = _read_sheet(sym, trading_date, variant)
    if existing is not None:
        return FrozenSheet(decode_profile(existing[0]), existing[1], trading_date, variant)

    profile = build()
    try:
        encoded = encode_profile(profile)
        canonical = _canonical(encoded)
    except (TypeError, ValueError) as exc:
        logger.error(
            "room_fact_sheet_not_freezable",
            ticker=sym,
            trading_date=trading_date.isoformat(),
            error=str(exc)[:300],
            detail="the Room runs on a fresh sheet and is not banked",
        )
        return FrozenSheet(profile, None, trading_date, variant)

    sheet_hash = _sha256(canonical)
    try:
        with get_session() as s:
            s.add(RoomFactSheetRow(
                ticker=sym, trading_date=trading_date, variant=variant,
                sheet=json.loads(canonical), sheet_hash=sheet_hash,
            ))
    except IntegrityError:
        winner = _read_sheet(sym, trading_date, variant)
        if winner is None:
            raise
        logger.info(
            "room_fact_sheet_race_lost",
            ticker=sym, trading_date=trading_date.isoformat(), outcome="re-read the winner's sheet",
        )
        return FrozenSheet(decode_profile(winner[0]), winner[1], trading_date, variant)
    return FrozenSheet(decode_profile(json.loads(canonical)), sheet_hash, trading_date, variant)


def _read_sheet(
    ticker: str, trading_date: date, variant: str,
) -> tuple[dict[str, Any], str] | None:
    with get_session() as s:
        row = s.execute(
            select(RoomFactSheetRow)
            .where(RoomFactSheetRow.ticker == ticker)
            .where(RoomFactSheetRow.trading_date == trading_date)
            .where(RoomFactSheetRow.variant == variant)
        ).scalar_one_or_none()
        return (row.sheet, row.sheet_hash) if row is not None else None


def key_parts(
    *,
    user_id: UUID,
    ticker: str,
    mandate: Mandate,
    sheet_hash: str,
    policy: str,
    model_root: str,
    trading_date: date,
) -> dict[str, str]:
    return {
        "user_id": str(user_id),
        "ticker": ticker.upper(),
        "mandate": mandate_digest(mandate),
        "fact_sheet": sheet_hash,
        "policy": policy,
        "model_root": model_root,
        # Hashed in its own right: a new trading day is a changed input even if
        # a sheet's content happened to come out identical.
        "trading_date": trading_date.isoformat(),
    }


_HASHED_PARTS = (
    "user_id", "ticker", "mandate", "fact_sheet", "policy", "model_root", "trading_date",
)


def key_from_parts(parts: dict[str, str]) -> str:
    return _sha256(_canonical({k: parts[k] for k in _HASHED_PARTS}))


def with_model_root(parts: dict[str, str], model_root: str) -> tuple[str, dict[str, str]]:
    """The key and parts for the same Room under a different model: a Room
    restarted on the backup slot is keyed by the backup's root, never the
    primary's."""
    new = {**parts, "model_root": model_root}
    return key_from_parts(new), new


@dataclass(frozen=True)
class BankedRoom:
    run_id: UUID
    finished_at: datetime | None
    running: bool
    # Only meaningful while `running`: whether a process is plausibly still
    # executing it (not marked interrupted, started inside the running window).
    live: bool = True


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None or dt.tzinfo is not None:
        return dt
    return dt.replace(tzinfo=timezone.utc)


def find_banked_room(key: str, *, running_cutoff: datetime) -> BankedRoom | None:
    """The Room holding `key`: a finished one (hand it over) or a running one
    (reattach to it). Failed, cancelled and outage Rooms hold no key.

    A `running` row that no process is executing (marked interrupted, or older
    than `running_cutoff`) is reported `live=False` so the caller releases its
    key instead of attaching to a dead Room."""
    with get_session() as s:
        row = s.execute(
            select(RoomRunRow).where(RoomRunRow.bank_key == key)
        ).scalar_one_or_none()
        if row is None:
            return None
        if row.status == "running":
            started = _aware(row.started_at)
            live = row.interrupted_at is None and (
                started is not None and started >= running_cutoff
            )
            return BankedRoom(row.id, None, True, live)
        if row.status == "completed" and row.verdict is not None:
            return BankedRoom(row.id, _aware(row.finished_at), False)
        return None


def release_key(run_id: UUID) -> None:
    """Drop a Room's key so the same inputs can start a fresh one."""
    with get_session() as s:
        row = s.get(RoomRunRow, run_id)
        if row is not None:
            row.bank_key = None
    logger.warning("room_bank_key_released", run_id=str(run_id))
