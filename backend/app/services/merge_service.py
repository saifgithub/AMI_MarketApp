"""BL16 (AT:R38) — account merge service.

When account-linking Phase 1 (AT:R32) silently adopts an existing email/sub
row, the pre-claim anon row is left orphaned with whatever the user did
while anonymous: journal entries, sim trades, lesson progress, mandate,
overlays, room runs, 1-on-1 history. This service re-keys all of that into
the adopting user when the client triggers the merge UX.

Single transactional pass per call. Idempotent — a second `execute()` on
the same pair finds nothing to move and returns zero counts.

Conflict rules (kept deliberately simple for the alpha MVP):
  - **mandate**: if the adopting user already has a mandate, keep it,
    delete the orphan's. Otherwise re-key the orphan's mandate rows.
  - **sim_portfolio**: each user owns at most one (UNIQUE on user_id).
    If the adopting user has none, re-key the orphan's portfolio. If
    both have one, keep the adopting user's and re-key only the orphan's
    sim_trades into it (we drop the orphan's holdings — too messy to
    sum without a UI for it).
  - **lessons_progress / agent_activations / sim_watchlists**: UNIQUE on
    (user_id, ...). Skip rows that would conflict; the orphan's "extra"
    rows move over, but a (lesson_id) already on the target stays as-is.
  - **user_overlays**: re-key, but mark as inactive when the target
    already has an active overlay for that agent. Counted separately.
  - **overlay_edit_counts**: UNIQUE on (user_id, agent_id). On conflict,
    sum the counts into the adopting row and delete the orphan row.
  - **billing (DEF099)**: `subscription_events` + `revenuecat_events` are
    re-keyed orphan→adopter (the audit/dedup trail must not dangle after the
    orphan row is deleted). The user-row billing fields (`plan`,
    `credit_balance`, `credits_period_start`, `credits_plan_at_grant`) are
    carried by `credit_service.carry_billing_on_merge` with a deliberate
    conflict rule — **higher-entitlement plan wins, credits sum** — so a
    pre-claim anonymous purchase survives the claim (anonymous-first is
    LOCKED). The RC customer alias is transferred orphan→adopter after commit
    so post-merge webhooks target the surviving account.

Defers the user-row delete to the very end after every other relation
is re-keyed.

The orphan's audit rows (`http_audit`, `llm_audit`, `auth_challenges`)
are intentionally left in place — they reflect what happened during the
anon session and re-keying them would lose forensic provenance.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from sqlalchemy import and_, delete, func, select, update

from app.core.logging import logger
from app.db import get_session
from app.db.models import (
    AgentActivationRow,
    BugReportRow,
    CareerEventRow,
    DailyChallengeAttemptRow,
    GameDuelRow,
    GameEntryRow,
    GameQueuedOrderRow,
    GameShortPositionRow,
    JournalEntryRow,
    LeagueMemberRow,
    LessonProgressRow,
    MandateRow,
    OneOnOneMessageRow,
    OverlayEditCounter,
    PortfolioNavDailyRow,
    ReputationEventRow,
    RevenueCatEventRow,
    RoomRunRow,
    SimHoldingRow,
    SimOptionLegRow,
    SimOptionTradeRow,
    SimPortfolioRow,
    SimTradeRow,
    SimWatchlistRow,
    SubscriptionEventRow,
    User,
    UserOverlayRow,
)
from app.services import credit_service, revenuecat_client
from app.services.league_service import week_end
from app.services.reputation_service import iso_week


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class _PreviewCounts:
    journal_entries: int = 0
    sim_trades: int = 0
    sim_holdings: int = 0
    sim_watchlists: int = 0
    lessons_progress: int = 0
    agent_activations: int = 0
    one_on_one_messages: int = 0
    room_runs: int = 0
    user_overlays: int = 0
    bug_reports: int = 0
    mandate_conflict: bool = False


class MergeError(ValueError):
    """Raised when a merge call fails a precondition (orphan gone, same
    user_id on both sides, etc.). The route layer translates to HTTP 4xx."""


class MergeService:
    """Stateless — opens its own session per call."""

    def preview(self, *, from_user_id: UUID, to_user_id: UUID) -> _PreviewCounts:
        """Read-only count of mergeable rows on the orphan side."""
        if from_user_id == to_user_id:
            raise MergeError("from_user_id and to_user_id must differ")
        with get_session() as s:
            return _PreviewCounts(
                journal_entries=_count(s, JournalEntryRow, from_user_id),
                sim_trades=_count(s, SimTradeRow, from_user_id),
                sim_holdings=_count_holdings(s, from_user_id),
                sim_watchlists=_count(s, SimWatchlistRow, from_user_id),
                lessons_progress=_count(s, LessonProgressRow, from_user_id),
                agent_activations=_count(s, AgentActivationRow, from_user_id),
                one_on_one_messages=_count(s, OneOnOneMessageRow, from_user_id),
                room_runs=_count(s, RoomRunRow, from_user_id),
                user_overlays=_count(s, UserOverlayRow, from_user_id),
                bug_reports=_count(s, BugReportRow, from_user_id),
                mandate_conflict=_has_mandate(s, from_user_id) and _has_mandate(s, to_user_id),
            )

    def execute(
        self,
        *,
        from_user_id: UUID,
        to_user_id: UUID,
    ) -> tuple[dict[str, int], Literal["target", "source", "neither"], int]:
        """Re-key every per-user row from orphan → adopter inside one
        transaction. Returns (counts, mandate_kept, overlays_deactivated).
        """
        if from_user_id == to_user_id:
            raise MergeError("from_user_id and to_user_id must differ")
        counts: dict[str, int] = {}
        overlays_deactivated = 0
        with get_session() as s:
            # Bail loudly if the adopter row doesn't exist — the merge has
            # nothing to land into.
            target = s.execute(
                select(User).where(User.id == to_user_id)
            ).scalar_one_or_none()
            if target is None:
                raise MergeError("adopting user not found")

            # ── Mandates ─────────────────────────────────────────────
            target_has_mandate = _has_mandate(s, to_user_id)
            source_has_mandate = _has_mandate(s, from_user_id)
            mandate_kept: Literal["target", "source", "neither"]
            if target_has_mandate and source_has_mandate:
                # Keep adopter's. Drop orphan's mandate rows.
                deleted = s.execute(
                    delete(MandateRow).where(MandateRow.user_id == from_user_id)
                )
                counts["mandates_dropped"] = int(deleted.rowcount or 0)
                mandate_kept = "target"
            elif source_has_mandate and not target_has_mandate:
                moved = s.execute(
                    update(MandateRow)
                    .where(MandateRow.user_id == from_user_id)
                    .values(user_id=to_user_id)
                )
                counts["mandates"] = int(moved.rowcount or 0)
                mandate_kept = "source"
            elif target_has_mandate and not source_has_mandate:
                mandate_kept = "target"
            else:
                mandate_kept = "neither"

            # ── Sim portfolio (TRAINING) + trades ────────────────────
            # CR109 slice 2: `sim_portfolios` now also holds GAME rows
            # (`kind="game"`, one per run) — scoped to `kind="training"`
            # here so this block keeps doing exactly what it always did;
            # game portfolios/trades are handled in their own block below,
            # because "keep adopter's, drop orphan's" (the training
            # conflict rule) does not apply to them — a user can hold many
            # game portfolios at once, keyed by run_id, so there is no
            # singleton to pick a winner between.
            target_portfolio = s.execute(
                select(SimPortfolioRow).where(
                    SimPortfolioRow.user_id == to_user_id,
                    SimPortfolioRow.kind == "training",
                )
            ).scalar_one_or_none()
            source_portfolio = s.execute(
                select(SimPortfolioRow).where(
                    SimPortfolioRow.user_id == from_user_id,
                    SimPortfolioRow.kind == "training",
                )
            ).scalar_one_or_none()
            sim_trades_moved = 0
            sim_holdings_moved = 0
            sim_options_moved = 0
            if source_portfolio is not None and target_portfolio is None:
                # Adopter has no portfolio — move orphan's wholesale.
                s.execute(
                    update(SimPortfolioRow)
                    .where(SimPortfolioRow.id == source_portfolio.id)
                    .values(user_id=to_user_id)
                )
                trades_moved = s.execute(
                    update(SimTradeRow)
                    .where(SimTradeRow.portfolio_id == source_portfolio.id)
                    .values(user_id=to_user_id)
                )
                sim_trades_moved = int(trades_moved.rowcount or 0)
                # DEF368 — the option rows carry their own `user_id` and were
                # never re-keyed here. The legs survived this branch (reads go
                # by `portfolio_id`, which does not change) but every
                # user_id-scoped option query was then pointing at the orphan.
                sim_options_moved = _rekey_options(
                    s, source_portfolio.id, to_user_id,
                )
                sim_holdings_moved = s.execute(
                    select(func.count()).select_from(SimHoldingRow).where(
                        SimHoldingRow.portfolio_id == source_portfolio.id
                    )
                ).scalar_one()
            elif source_portfolio is not None and target_portfolio is not None:
                # Both have portfolios — keep adopter's. Re-key only the
                # trades into the adopter's portfolio. Holdings get dropped
                # along with the orphan portfolio cascade.
                #
                # Scoped to `SimTradeRow.portfolio_id == source_portfolio.id`
                # rather than `user_id == from_user_id` (the pre-CR109-slice-2
                # shape) — the orphan may ALSO hold game trades under this
                # same user_id now, and those belong to the game-portfolio
                # block below, not here.
                trades_moved = s.execute(
                    update(SimTradeRow)
                    .where(SimTradeRow.portfolio_id == source_portfolio.id)
                    .values(user_id=to_user_id, portfolio_id=target_portfolio.id)
                )
                sim_trades_moved = int(trades_moved.rowcount or 0)
                # DEF368 — THE DESTRUCTIVE BRANCH. Equity trades are re-keyed
                # to the adopter's portfolio just above; option legs were not,
                # and `sim_option_legs.portfolio_id` is ondelete=CASCADE, so
                # the delete below removed every one of them. The user
                # consented to a structure, saw it on the portfolio card,
                # claimed their account, and it was gone — silently, because a
                # CASCADE is not a failure. Re-key BEFORE the delete.
                sim_options_moved = _rekey_options(
                    s, source_portfolio.id, to_user_id,
                    portfolio_id=target_portfolio.id,
                )
                # CASCADE on sim_holdings.portfolio_id wipes the orphan's
                # holdings when we delete the orphan portfolio.
                s.execute(
                    delete(SimPortfolioRow)
                    .where(SimPortfolioRow.id == source_portfolio.id)
                )
            counts["sim_trades"] = sim_trades_moved
            counts["sim_holdings"] = sim_holdings_moved
            # DEF368 — reported, not just moved. A merge that names what it
            # carried while silently dropping a table is the same class of
            # failure one layer up.
            counts["sim_option_legs"] = sim_options_moved

            # ── Game portfolios + trades (CR109 slice 2) ─────────────
            # Every game portfolio is its own row keyed by run_id — unlike
            # the training portfolio there is no "one per user" conflict
            # to resolve, so each orphan game-portfolio row (and its own
            # trades) simply moves wholesale. Holdings need no re-key:
            # `SimHoldingRow` has no `user_id` column, it follows
            # `portfolio_id`, which is unchanged here — this is what keeps
            # "a claimed account keeps its runs" true for game runs too.
            game_portfolios = s.execute(
                select(SimPortfolioRow).where(
                    SimPortfolioRow.user_id == from_user_id,
                    SimPortfolioRow.kind == "game",
                )
            ).scalars().all()
            game_portfolios_moved = 0
            game_trades_moved = 0
            for gp in game_portfolios:
                trades_moved = s.execute(
                    update(SimTradeRow)
                    .where(SimTradeRow.portfolio_id == gp.id)
                    .values(user_id=to_user_id)
                )
                game_trades_moved += int(trades_moved.rowcount or 0)
                gp.user_id = to_user_id
                game_portfolios_moved += 1
            counts["game_portfolios"] = game_portfolios_moved
            counts["game_trades"] = game_trades_moved

            # ── game_entries (UNIQUE on field_id+user_id) ────────────
            # A conflict is only possible if BOTH accounts already hold an
            # entry in the exact same field — rare, but possible (both an
            # anon session and the account it's about to be adopted into
            # separately entered the same weekly field). Same skip-on-
            # conflict shape as the other UNIQUE(user_id, ...) tables above.
            counts["game_entries"] = _rekey_skipping_conflicts(
                s, GameEntryRow,
                from_user_id, to_user_id,
                conflict_col=GameEntryRow.field_id,
            )

            # ── game_queued_orders — no uniqueness to conflict on ────
            counts["game_queued_orders"] = _rekey_all(
                s, GameQueuedOrderRow, from_user_id, to_user_id,
            )

            # ── career_events — the ledger IS the career ─────────────
            #
            # `career_points_total` is SUM(delta) over this table for a
            # user_id, so leaving these behind does not merely lose a
            # history: the adopted account's career-point total silently
            # becomes zero, and every title and rung with it. An anonymous
            # player who played a week and then claimed their account would
            # watch their score vanish at the moment of signing up — the
            # exact moment the product asks them to commit.
            counts["career_events"] = _rekey_career_events(
                s, from_user_id, to_user_id,
            )

            # ── game_duels — TWO user columns, not one ───────────────
            #
            # `_rekey_all` cannot serve here: a duel names a user on each
            # side, and the orphan may be either. Leaving them behind loses
            # the W-L record, and worse, `opponent_of()` decides which side
            # is "you" by comparing `user_a_id == user_id` — against a stale
            # id it returns the WRONG side, so a claimed account's duel card
            # would show the player their own book as the opponent.
            counts["game_duels"] = _rekey_game_duels(
                s, from_user_id, to_user_id,
            )

            # ── game_short_positions — plain user_id, no uniqueness ──
            #
            # The position itself keeps working either way (every read is by
            # `portfolio_id`, and the portfolio moved above), which is
            # exactly why this would have gone unnoticed — the row would
            # simply carry a dead owner until some future user-scoped query
            # needed it.
            counts["game_short_positions"] = _rekey_all(
                s, GameShortPositionRow, from_user_id, to_user_id,
            )

            # ── portfolio_nav_daily (UNIQUE on user_id+run_id+as_of_date) ─
            counts["portfolio_nav_daily"] = _rekey_nav_rows(s, from_user_id, to_user_id)

            # ── Sim watchlist (UNIQUE on user_id+ticker) ────────────
            counts["sim_watchlists"] = _rekey_skipping_conflicts(
                s, SimWatchlistRow,
                from_user_id, to_user_id,
                conflict_col=SimWatchlistRow.ticker,
            )

            # ── Lessons progress (UNIQUE on user_id+lesson_id) ──────
            counts["lessons_progress"] = _rekey_skipping_conflicts(
                s, LessonProgressRow,
                from_user_id, to_user_id,
                conflict_col=LessonProgressRow.lesson_id,
            )

            # ── Agent activations (UNIQUE on user_id+agent_id) ──────
            counts["agent_activations"] = _rekey_skipping_conflicts(
                s, AgentActivationRow,
                from_user_id, to_user_id,
                conflict_col=AgentActivationRow.agent_id,
            )

            # ── Challenge attempts (UNIQUE on user_id+challenge_id) ──
            counts["daily_challenge_attempts"] = _rekey_skipping_conflicts(
                s, DailyChallengeAttemptRow,
                from_user_id, to_user_id,
                conflict_col=DailyChallengeAttemptRow.challenge_id,
            )

            # ── League seats (UNIQUE on user_id+week) ────────────────
            counts["league_members"] = _rekey_skipping_conflicts(
                s, LeagueMemberRow,
                from_user_id, to_user_id,
                conflict_col=LeagueMemberRow.week,
            )

            # ── Reputation: move the ledger, sum the counter ─────────
            counts["reputation_events"] = _rekey_all(
                s, ReputationEventRow, from_user_id, to_user_id,
            )
            source_user = s.execute(
                select(User).where(User.id == from_user_id)
            ).scalar_one_or_none()
            if source_user is not None and source_user.reputation:
                target.reputation = (target.reputation or 0) + source_user.reputation

            # ── DEF040: recompute the adopter's current-week league
            # points from the now-merged ledger. The league-seat re-key
            # above (conflict_col=week) drops the orphan's league_members
            # row outright when both sides already hold a seat this week —
            # that silently lost whatever the orphan earned this week, even
            # though its reputation_events rows (just re-keyed above) now
            # belong to the adopter. A full resync from the ledger (not a
            # delta-add) keeps points correct regardless of which side's
            # seat survived the re-key.
            current_week = iso_week(_utcnow())
            adopter_seat = s.execute(
                select(LeagueMemberRow).where(
                    LeagueMemberRow.user_id == to_user_id,
                    LeagueMemberRow.week == current_week,
                )
            ).scalar_one_or_none()
            if adopter_seat is not None:
                week_end_at = week_end(current_week)
                week_start_at = week_end_at - timedelta(days=7)
                adopter_seat.points = int(s.execute(
                    select(func.coalesce(func.sum(ReputationEventRow.points), 0)).where(
                        ReputationEventRow.user_id == to_user_id,
                        ReputationEventRow.created_at >= week_start_at,
                        ReputationEventRow.created_at < week_end_at,
                    )
                ).scalar_one())

            # ── Overlay edit counts: sum on conflict ────────────────
            counts["overlay_edit_counts"] = _merge_overlay_counts(
                s, from_user_id, to_user_id,
            )

            # ── User overlays: re-key, deactivate if adopter has one ─
            counts["user_overlays"], overlays_deactivated = _rekey_user_overlays(
                s, from_user_id, to_user_id,
            )

            # ── Free-form re-keys (no uniqueness conflicts) ─────────
            counts["journal_entries"] = _rekey_all(
                s, JournalEntryRow, from_user_id, to_user_id,
            )
            counts["one_on_one_messages"] = _rekey_all(
                s, OneOnOneMessageRow, from_user_id, to_user_id,
            )
            counts["room_runs"] = _rekey_all(
                s, RoomRunRow, from_user_id, to_user_id,
            )
            counts["bug_reports"] = _rekey_all(
                s, BugReportRow, from_user_id, to_user_id,
            )

            # ── DEF099: billing state (was silently dropped) ─────────
            # (1) Re-key the audit/dedup trail. subscription_events is keyed by
            #     user_id (UUID); revenuecat_events is keyed by app_user_id
            #     (the RC id == our users.id in *string* form, NOT a FK). Both
            #     would dangle after the orphan row is deleted.
            counts["subscription_events"] = _rekey_all(
                s, SubscriptionEventRow, from_user_id, to_user_id,
            )
            rc_moved = s.execute(
                update(RevenueCatEventRow)
                .where(RevenueCatEventRow.app_user_id == str(from_user_id))
                .values(app_user_id=str(to_user_id))
            )
            counts["revenuecat_events"] = int(rc_moved.rowcount or 0)

            # (2) Carry plan + credits with a deliberate conflict rule
            #     (higher-entitlement plan wins, credits sum) — see
            #     credit_service.carry_billing_on_merge. source_user was fetched
            #     for the reputation carry above.
            if source_user is not None:
                billing = credit_service.carry_billing_on_merge(s, source_user, target)
                counts["billing_plan_carried"] = 1 if billing.plan_changed else 0

            # ── Subscription event ──────────────────────────────────
            s.add(SubscriptionEventRow(
                user_id=to_user_id,
                event_type="account_adoption_merged",
                from_value=str(from_user_id),
                to_value=str(to_user_id),
                source="app",
                note=json.dumps({k: v for k, v in counts.items() if v}),
            ))

            # ── Delete the now-empty orphan row ─────────────────────
            # user_devices was re-keyed in AT:R33 on the original adoption,
            # but a stray row could exist if the merge runs late; clean it
            # up too.
            from app.db.models import UserDeviceRow
            s.execute(
                update(UserDeviceRow)
                .where(UserDeviceRow.user_id == from_user_id)
                .values(user_id=to_user_id)
            )
            s.execute(delete(User).where(User.id == from_user_id))

            logger.info(
                "account_merge_executed",
                from_user_id=str(from_user_id),
                to_user_id=str(to_user_id),
                counts={k: v for k, v in counts.items() if v},
                mandate_kept=mandate_kept,
                overlays_deactivated=overlays_deactivated,
            )

        # DEF099 gap 3 — transfer the RC customer alias orphan→adopter, AFTER
        # the merge transaction has committed. This is best-effort external I/O:
        # keeping it out of the DB transaction means a slow/failed RC call never
        # rolls back the authoritative local entitlement carry, and the webhook's
        # merge-trail safety net re-targets any delivery that still arrives under
        # the old id. Degrades loudly on its own (CR040) when the RC key is unset.
        alias = revenuecat_client.transfer_alias(str(from_user_id), str(to_user_id))
        logger.info(
            "account_merge_rc_alias",
            from_user_id=str(from_user_id),
            to_user_id=str(to_user_id),
            alias_status=alias.status,
        )
        return counts, mandate_kept, overlays_deactivated


# ── Helpers ─────────────────────────────────────────────────────────────


def _count(s, model, user_id: UUID) -> int:
    return int(s.execute(
        select(func.count()).select_from(model).where(model.user_id == user_id)
    ).scalar_one())


def _count_holdings(s, user_id: UUID) -> int:
    """sim_holdings is keyed by portfolio_id, not user_id directly. Count
    by joining through sim_portfolios."""
    return int(s.execute(
        select(func.count())
        .select_from(SimHoldingRow)
        .join(SimPortfolioRow, SimHoldingRow.portfolio_id == SimPortfolioRow.id)
        .where(SimPortfolioRow.user_id == user_id)
    ).scalar_one())


def _has_mandate(s, user_id: UUID) -> bool:
    return s.execute(
        select(MandateRow.id).where(MandateRow.user_id == user_id).limit(1)
    ).scalar_one_or_none() is not None


def _rekey_options(s, source_portfolio_id, to_user_id, *, portfolio_id=None) -> int:
    """DEF368 — move an orphan's option legs and structures to the adopter.

    Both tables carry `user_id` AND `portfolio_id`, so both must move: the
    first keeps user-scoped queries correct, the second is what keeps the rows
    alive when the orphan portfolio is deleted (`ondelete="CASCADE"`).

    `portfolio_id` is passed only in the both-have-portfolios branch, where
    the orphan portfolio is about to be deleted and the rows must be adopted
    into the target. In the other branch the portfolio row itself changes
    owner, so its id is still correct and only `user_id` moves.

    Returns the number of LEGS moved — the unit a user would recognise as
    "my positions". Structures move with them and are not double-counted.
    """
    values = {"user_id": to_user_id}
    if portfolio_id is not None:
        values["portfolio_id"] = portfolio_id

    legs = s.execute(
        update(SimOptionLegRow)
        .where(SimOptionLegRow.portfolio_id == source_portfolio_id)
        .values(**values)
    )
    s.execute(
        update(SimOptionTradeRow)
        .where(SimOptionTradeRow.portfolio_id == source_portfolio_id)
        .values(**values)
    )
    return int(legs.rowcount or 0)


def _rekey_career_events(s, from_user_id: UUID, to_user_id: UUID) -> int:
    """Move the orphan's career-point ledger to the adopter.

    `UniqueConstraint(entry_id, reason)` is not user-scoped, so it cannot
    collide on a re-key. The partial index `uq_career_event_stipend_period`
    — UNIQUE(user_id, period_key) WHERE reason = 'finish_stipend' — can:
    both accounts may have claimed a finish stipend in the same cadence
    period. The adopter's claim wins and the orphan's is dropped, matching
    every other conflict on this path.

    Written as its own helper rather than reusing
    `_rekey_skipping_conflicts(conflict_col=period_key)` because that would
    be silently wrong here: `period_key` is NULL on every non-stipend row,
    and `NULL NOT IN (...)` evaluates to NULL — falsy — so every
    `run_close` and `duel_result` row would have been left behind. The bug
    would have looked like a partial fix and reported a non-zero count.
    """
    claimed = set(s.execute(
        select(CareerEventRow.period_key).where(
            CareerEventRow.user_id == to_user_id,
            CareerEventRow.reason == "finish_stipend",
            CareerEventRow.period_key.is_not(None),
        )
    ).scalars().all())

    conflicting = and_(
        CareerEventRow.reason == "finish_stipend",
        CareerEventRow.period_key.is_not(None),
        CareerEventRow.period_key.in_(claimed),
    ) if claimed else None

    if conflicting is not None:
        s.execute(
            delete(CareerEventRow).where(
                CareerEventRow.user_id == from_user_id, conflicting,
            )
        )
    moved = s.execute(
        update(CareerEventRow)
        .where(CareerEventRow.user_id == from_user_id)
        .values(user_id=to_user_id)
    )
    return int(moved.rowcount or 0)


def _rekey_game_duels(s, from_user_id: UUID, to_user_id: UUID) -> int:
    """Re-key every user reference in every duel the orphan is in, and
    return how many duels moved.

    THREE columns, not two. `user_a_id` and `user_b_id` say who played;
    `winner_user_id` says who won, and it is a SEPARATE pointer. Moving the
    sides while leaving the winner behind is worse than losing the row
    outright: the adopted account ends up in a duel it did not win, which
    reads as a settled loss.
    """
    moved = 0
    for col in (GameDuelRow.user_a_id, GameDuelRow.user_b_id):
        result = s.execute(
            update(GameDuelRow)
            .where(col == from_user_id)
            .values({col.key: to_user_id})
        )
        moved += int(result.rowcount or 0)
    s.execute(
        update(GameDuelRow)
        .where(GameDuelRow.winner_user_id == from_user_id)
        .values(winner_user_id=to_user_id)
    )
    return moved


def _rekey_all(s, model, from_user_id: UUID, to_user_id: UUID) -> int:
    """Free-form re-key; no UNIQUE conflicts to worry about."""
    result = s.execute(
        update(model)
        .where(model.user_id == from_user_id)
        .values(user_id=to_user_id)
    )
    return int(result.rowcount or 0)


def _rekey_skipping_conflicts(
    s, model,
    from_user_id: UUID, to_user_id: UUID,
    *, conflict_col,
) -> int:
    """Re-key orphan rows that wouldn't violate a UNIQUE(user_id, <col>)
    constraint on the adopter side. Conflicting orphan rows are deleted
    (we keep the adopter's version on collision).
    """
    # Find adopter's existing values to skip.
    target_values = set(s.execute(
        select(conflict_col).where(model.user_id == to_user_id)
    ).scalars().all())
    # Move non-conflicting orphan rows.
    moved = s.execute(
        update(model)
        .where(and_(
            model.user_id == from_user_id,
            conflict_col.notin_(target_values) if target_values else True,
        ))
        .values(user_id=to_user_id)
    )
    # Drop conflicting orphan rows so the user row can be deleted at the end.
    if target_values:
        s.execute(
            delete(model).where(and_(
                model.user_id == from_user_id,
                conflict_col.in_(target_values),
            ))
        )
    return int(moved.rowcount or 0)


def _rekey_nav_rows(s, from_user_id: UUID, to_user_id: UUID) -> int:
    """Re-key `portfolio_nav_daily` orphan -> adopter (CR109 slice 2 —
    not FK'd to `sim_portfolios` by design, so it needs its own re-key
    like every other user_id-keyed table here).

    GAME rows (`run_id` set) move wholesale: each `run_id` belongs to
    exactly one user by construction (`games_service.enter_field` mints a
    fresh UUID per entry), so no conflict is possible.

    TRAINING rows (`run_id IS NULL`) CAN collide on `as_of_date` — both an
    anonymous session and the account it's about to be adopted into get a
    daily training snapshot, so a same-date row can already exist on both
    sides. `_rekey_skipping_conflicts` doesn't fit directly here: its
    conflict column can't be `run_id` (NULL on both sides can't serve as
    the discriminator), so this reimplements the same skip-on-conflict
    shape keyed on `as_of_date` for the `run_id IS NULL` slice only.
    """
    game_moved = s.execute(
        update(PortfolioNavDailyRow)
        .where(
            PortfolioNavDailyRow.user_id == from_user_id,
            PortfolioNavDailyRow.run_id.isnot(None),
        )
        .values(user_id=to_user_id)
    )
    moved = int(game_moved.rowcount or 0)

    target_dates = set(s.execute(
        select(PortfolioNavDailyRow.as_of_date).where(
            PortfolioNavDailyRow.user_id == to_user_id,
            PortfolioNavDailyRow.run_id.is_(None),
        )
    ).scalars().all())
    training_moved = s.execute(
        update(PortfolioNavDailyRow)
        .where(and_(
            PortfolioNavDailyRow.user_id == from_user_id,
            PortfolioNavDailyRow.run_id.is_(None),
            (
                PortfolioNavDailyRow.as_of_date.notin_(target_dates)
                if target_dates else True
            ),
        ))
        .values(user_id=to_user_id)
    )
    moved += int(training_moved.rowcount or 0)
    if target_dates:
        s.execute(delete(PortfolioNavDailyRow).where(and_(
            PortfolioNavDailyRow.user_id == from_user_id,
            PortfolioNavDailyRow.run_id.is_(None),
            PortfolioNavDailyRow.as_of_date.in_(target_dates),
        )))
    return moved


def _merge_overlay_counts(s, from_user_id: UUID, to_user_id: UUID) -> int:
    """Sum lifetime edit counts per (user_id, agent_id) — if both sides
    have a row for an agent, add the orphan's count to the adopter's
    and delete the orphan row. Otherwise re-key the orphan row.
    """
    source_rows = s.execute(
        select(OverlayEditCounter).where(OverlayEditCounter.user_id == from_user_id)
    ).scalars().all()
    moved = 0
    for src in source_rows:
        target = s.execute(
            select(OverlayEditCounter).where(and_(
                OverlayEditCounter.user_id == to_user_id,
                OverlayEditCounter.agent_id == src.agent_id,
            ))
        ).scalar_one_or_none()
        if target is None:
            src.user_id = to_user_id
            moved += 1
        else:
            target.count = (target.count or 0) + (src.count or 0)
            s.delete(src)
            moved += 1
    return moved


def _rekey_user_overlays(
    s, from_user_id: UUID, to_user_id: UUID,
) -> tuple[int, int]:
    """Re-key overlays from orphan → adopter. When the adopter already has
    an active overlay for the same agent, mark the orphan's incoming
    overlays inactive (preserves history without auto-replacing). Returns
    (moved, deactivated).

    Versions matter: UNIQUE(user_id, agent_id, version). If both sides
    have a v1 for agent X, that collides — drop the orphan's version row.
    """
    agents_with_active_target = set(s.execute(
        select(UserOverlayRow.agent_id).where(and_(
            UserOverlayRow.user_id == to_user_id,
            UserOverlayRow.is_active.is_(True),
        ))
    ).scalars().all())

    # Collect all (agent_id, version) pairs already on the adopter so we
    # can drop colliding orphan version rows before re-keying.
    target_keys = set(s.execute(
        select(UserOverlayRow.agent_id, UserOverlayRow.version)
        .where(UserOverlayRow.user_id == to_user_id)
    ).all())

    source_rows = s.execute(
        select(UserOverlayRow).where(UserOverlayRow.user_id == from_user_id)
    ).scalars().all()
    moved = 0
    deactivated = 0
    for src in source_rows:
        if (src.agent_id, src.version) in target_keys:
            s.delete(src)
            continue
        src.user_id = to_user_id
        if src.agent_id in agents_with_active_target and src.is_active:
            src.is_active = False
            deactivated += 1
        moved += 1
    return moved, deactivated


# ── Singleton ───────────────────────────────────────────────────────────

_service: MergeService | None = None


def get_merge_service() -> MergeService:
    global _service
    if _service is None:
        _service = MergeService()
    return _service
