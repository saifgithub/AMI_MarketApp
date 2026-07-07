"""Weekly reputation leagues (CR004, D-060).

Cohorts of ≤ LEAGUE_COHORT_SIZE assembled every ISO week from users active
in the prior 7 days, ranked by reputation points earned THIS week (lifetime
totals feed nothing here — newcomers can compete week one). Top N promote,
bottom N relegate, one tier per outcome on the Apprentice → Floor Veteran
ladder. Zero P&L anywhere (D-060 hard rule).

Identity is a pseudonymous adjective+noun handle minted on first league
contact (`ensure_handle`), regenerable exactly once. Real names appear only
where the user opted in via `users.show_display_name`.

`weekly_roll()` is idempotent and cheap — safe to call hourly from the
lifespan tick so a container restart can't miss the Monday 00:00 UTC
boundary.
"""

from __future__ import annotations

import random
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select

from app.core.config import settings
from app.core.logging import logger
from app.db.models import LeagueMemberRow, LeagueRow, ReputationEventRow, User
from app.services.reputation_service import iso_week

# daily_and_streaks.md ladder — cosmetic + badge-earning, no functional gating.
TIERS: tuple[str, ...] = (
    "apprentice", "analyst", "trader", "senior", "floor_veteran",
)

# Cohorts smaller than this don't relegate (nowhere to fall fairly).
MIN_COHORT_FOR_RELEGATION = 10

HANDLE_ADJ: tuple[str, ...] = (
    "Cobalt", "Amber", "Vector", "Crimson", "Onyx", "Silver", "Copper",
    "Indigo", "Slate", "Golden", "Cyan", "Violet", "Emerald", "Scarlet",
    "Steel", "Quartz", "Titan", "Nickel", "Iron", "Platinum", "Azure",
    "Umber", "Ivory", "Jade", "Garnet", "Bronze", "Neon", "Nova",
    "Prime", "Apex", "Delta", "Sigma", "Vertex", "Zenith", "Radial",
    "Axial", "Binary", "Cipher", "Static", "Lucid",
)
HANDLE_NOUN: tuple[str, ...] = (
    "Falcon", "Ledger", "Signal", "Harrier", "Compass", "Beacon", "Drift",
    "Anchor", "Circuit", "Osprey", "Kestrel", "Marlin", "Condor", "Lynx",
    "Panther", "Orca", "Raven", "Heron", "Basis", "Margin", "Hedge",
    "Tape", "Pivot", "Spread", "Breaker", "Channel", "Summit", "Ridge",
    "Meridian", "Quorum", "Vault", "Relay", "Prism", "Lattice", "Grid",
    "Hexagon", "Vertex", "Column", "Gauge", "Index",
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def week_end(week: str) -> datetime:
    """UTC end (exclusive) of an ISO 'YYYY-Www' week — Monday 00:00."""
    year, wk = int(week[:4]), int(week[6:])
    monday = datetime.fromisocalendar(year, wk, 1).replace(tzinfo=timezone.utc)
    return monday + timedelta(days=7)


def _tier_index(tier: str) -> int:
    try:
        return TIERS.index(tier)
    except ValueError:
        return 0


def _next_tier(tier: str, outcome: str | None) -> str:
    idx = _tier_index(tier)
    if outcome == "promoted":
        idx = min(idx + 1, len(TIERS) - 1)
    elif outcome == "relegated":
        idx = max(idx - 1, 0)
    return TIERS[idx]


class LeagueService:
    """Stateless except for the 60s standings cache."""

    def __init__(self) -> None:
        self._standings_cache: dict[UUID, tuple[float, dict[str, Any]]] = {}
        self._standings_ttl = 60.0

    # ── Handles ──────────────────────────────────────────────────────────

    def ensure_handle(self, session, user: User) -> str:
        """Mint the pseudonymous handle on first league contact."""
        if user.handle:
            return user.handle
        user.handle = self._mint_handle(session)
        session.flush()
        return user.handle

    def regenerate_handle(self, session, user: User) -> str:
        """One self-service regeneration, ever."""
        if user.handle_regenerated_at is not None:
            raise HandleAlreadyRegenerated()
        user.handle = self._mint_handle(session)
        user.handle_regenerated_at = _utcnow()
        session.flush()
        return user.handle

    def _mint_handle(self, session) -> str:
        for attempt in range(20):
            candidate = f"{random.choice(HANDLE_ADJ)} {random.choice(HANDLE_NOUN)}"
            if attempt >= 10:
                candidate = f"{candidate} {random.randint(2, 99)}"
            exists = session.execute(
                select(User.id).where(User.handle == candidate).limit(1)
            ).scalar_one_or_none()
            if exists is None:
                return candidate
        raise RuntimeError("handle space exhausted")  # pragma: no cover

    # ── Weekly roll ──────────────────────────────────────────────────────

    def weekly_roll(self, session) -> bool:
        """Finalize past weeks + assemble the current week's cohorts.

        Idempotent: returns False (no-op) when the current ISO week's
        leagues already exist.
        """
        current = iso_week(_utcnow())
        exists = session.execute(
            select(LeagueRow.id).where(LeagueRow.week == current).limit(1)
        ).scalar_one_or_none()
        if exists is not None:
            return False

        self._finalize_past_weeks(session, current)
        created = self._assemble_week(session, current)
        session.flush()
        self._standings_cache.clear()
        logger.info("league_weekly_roll", week=current, leagues_created=created)
        return True

    def _finalize_past_weeks(self, session, current: str) -> None:
        """Stamp rank_final + outcome on every unfinalized past-week league."""
        past_league_ids = session.execute(
            select(LeagueMemberRow.league_id)
            .join(LeagueRow, LeagueMemberRow.league_id == LeagueRow.id)
            .where(LeagueRow.week != current)
            .where(LeagueMemberRow.rank_final.is_(None))
            .distinct()
        ).scalars().all()
        for league_id in past_league_ids:
            members = session.execute(
                select(LeagueMemberRow)
                .where(LeagueMemberRow.league_id == league_id)
                .order_by(
                    LeagueMemberRow.points.desc(), LeagueMemberRow.joined_at,
                )
            ).scalars().all()
            promote_n = settings.league_promote_count
            relegate_n = (
                settings.league_relegate_count
                if len(members) >= MIN_COHORT_FOR_RELEGATION else 0
            )
            for rank, member in enumerate(members, start=1):
                member.rank_final = rank
                if rank <= promote_n:
                    member.outcome = "promoted"
                elif relegate_n and rank > len(members) - relegate_n:
                    member.outcome = "relegated"
                else:
                    member.outcome = "stay"

    def _assemble_week(self, session, week: str) -> int:
        """Group eligible users by tier, shuffle, chunk, mint cohorts."""
        cutoff = _utcnow() - timedelta(days=7)
        active_ids = session.execute(
            select(ReputationEventRow.user_id)
            .where(ReputationEventRow.created_at >= cutoff)
            .distinct()
        ).scalars().all()
        if not active_ids:
            return 0

        by_tier: dict[str, list[User]] = {}
        for user_id in active_ids:
            user = session.execute(
                select(User).where(User.id == user_id)
            ).scalar_one_or_none()
            if user is None:
                continue
            if (
                settings.league_eligible_plans
                and user.plan not in settings.league_eligible_plans
            ):
                continue
            self.ensure_handle(session, user)
            by_tier.setdefault(self._current_tier(session, user_id), []).append(user)

        created = 0
        for tier, users in by_tier.items():
            random.shuffle(users)
            size = settings.league_cohort_size
            for i in range(0, len(users), size):
                chunk = users[i:i + size]
                league = LeagueRow(week=week, tier=tier)
                session.add(league)
                session.flush()
                for user in chunk:
                    session.add(LeagueMemberRow(
                        league_id=league.id, user_id=user.id,
                        week=week, points=0,
                    ))
                created += 1
        return created

    def _current_tier(self, session, user_id: UUID) -> str:
        """Tier for the coming week = last finalized seat's tier moved one
        step by its outcome. Never competed → Apprentice."""
        row = session.execute(
            select(LeagueMemberRow, LeagueRow.tier)
            .join(LeagueRow, LeagueMemberRow.league_id == LeagueRow.id)
            .where(LeagueMemberRow.user_id == user_id)
            .where(LeagueMemberRow.rank_final.isnot(None))
            .order_by(LeagueMemberRow.week.desc())
            .limit(1)
        ).first()
        if row is None:
            return TIERS[0]
        member, tier = row
        return _next_tier(tier, member.outcome)

    # ── Reads ────────────────────────────────────────────────────────────

    def membership(self, session, user_id: UUID) -> LeagueMemberRow | None:
        return session.execute(
            select(LeagueMemberRow)
            .where(LeagueMemberRow.user_id == user_id)
            .where(LeagueMemberRow.week == iso_week(_utcnow()))
        ).scalar_one_or_none()

    def standings(self, session, user_id: UUID) -> dict[str, Any] | None:
        """My cohort's board, points desc. None when unassigned this week.
        Cached 60s per league; is_me stamped per caller after cache read."""
        member = self.membership(session, user_id)
        if member is None:
            return None

        cached = self._standings_cache.get(member.league_id)
        if cached is not None and cached[0] > time.monotonic():
            board = cached[1]
        else:
            board = self._build_board(session, member.league_id)
            self._standings_cache[member.league_id] = (
                time.monotonic() + self._standings_ttl, board,
            )

        members = [
            {**m, "is_me": m["user_id"] == str(user_id)} for m in board["members"]
        ]
        return {**board, "members": members}

    def _build_board(self, session, league_id: UUID) -> dict[str, Any]:
        league = session.execute(
            select(LeagueRow).where(LeagueRow.id == league_id)
        ).scalar_one()
        rows = session.execute(
            select(LeagueMemberRow, User)
            .join(User, LeagueMemberRow.user_id == User.id)
            .where(LeagueMemberRow.league_id == league_id)
            .order_by(LeagueMemberRow.points.desc(), LeagueMemberRow.joined_at)
        ).all()
        members = []
        for rank, (member, user) in enumerate(rows, start=1):
            members.append({
                "rank": rank,
                "user_id": str(user.id),
                "handle": user.handle or "—",
                "display_name": user.display_name if user.show_display_name else None,
                "points": member.points,
            })
        return {
            "league_id": str(league.id),
            "week": league.week,
            "tier": league.tier,
            "ends_at": week_end(league.week).isoformat(),
            "members": members,
        }

    def history(self, session, user_id: UUID) -> list[dict[str, Any]]:
        rows = session.execute(
            select(LeagueMemberRow, LeagueRow.tier)
            .join(LeagueRow, LeagueMemberRow.league_id == LeagueRow.id)
            .where(LeagueMemberRow.user_id == user_id)
            .where(LeagueMemberRow.rank_final.isnot(None))
            .order_by(LeagueMemberRow.week.desc())
        ).all()
        return [
            {
                "week": member.week,
                "tier": tier,
                "rank_final": member.rank_final,
                "outcome": member.outcome,
                "points": member.points,
            }
            for member, tier in rows
        ]


class HandleAlreadyRegenerated(Exception):
    """The one allowed self-service handle regeneration was already used."""


# ── Singleton ───────────────────────────────────────────────────────────

_service: LeagueService | None = None


def get_league_service() -> LeagueService:
    global _service
    if _service is None:
        _service = LeagueService()
    return _service
