"""CR176 — the push half of CR109's period arc (design §10.1).

Slice 5 (Amendment K) built the arc's in-app beats. §10.1's matrix marks four
of them as *needing* push, and Saiful's ruling was **in-app ceremony now, push
next**. Until that lands, every beat reaches only a player who already opened
the app — and §10 calls the final stretch *"the anticipation engine"*, which is
inert if nobody is told.

**CR176's filed premise was stale and is corrected here.** The row says *"No
push infrastructure exists at all"*, quoting §10.1's *"no tokens, no APNs, no
FCM"*. CR027 has since shipped all of it: the OneSignal SDK initialises in
`main.dart`, `notification_service.notify()` is the single write path with
per-user rate limits and a `uq_notifications_dedupe` constraint, and both
`price_alert_evaluator` and `daily_reminder` already deliver through it. So
this module is a **policy layer plus three beat queries**, not an integration.

**The reminder rule is the whole design constraint** (§10.1):

> Remind on events that need a DECISION. Never on events that only invite
> watching.

That is not restraint for its own sake. Ship *"AAPL is up 2%"* daily and the
user disables push — and then **the Close**, which carries the entire emotional
payoff of the period arc, never arrives. The cheap notification costs the
valuable one. Every beat below is a decision the player can still act on, or a
result they asked for by entering.

**Suppression, and the one place this reads §10.1 rather than quoting it.**
§10.1 says *"≤1 push/day, ≤4/week, quiet hours in the user's timezone. The
Close and a received challenge are exempt from suppression but never
duplicated."* Read literally, "exempt from suppression" would fire a Close at
03:00 local, since US settlement lands in the small hours across Asia — and a
push that wakes someone is the fastest way to lose the channel the rule exists
to protect. So exempt beats bypass the **caps** outright but are **deferred**
by quiet hours rather than dropped: the sweep is idempotent on a stable
`source_ref`, so the beat simply sends on the first tick after quiet hours end.
Nothing is suppressed; it arrives late instead of never, which is what "exempt
from suppression but never duplicated" is protecting.

**Deferral is correct only because these beats have no expiry.** A time-boxed
beat must NOT be deferred — *"entries close in 2h"* delivered three hours late
is false. Each beat therefore carries its own eligibility window and is simply
not eligible outside it, so quiet hours drop it by construction rather than by
a rule someone has to remember.

**Idempotency is DB-derived, never in-memory**, exactly as `daily_reminder`
learned to do it: `source_ref` is the beat's business key (the run or the
field), and the `(user_id, type, source_ref)` unique constraint is what makes
"at most once" a property of the data rather than of how many ticks happen to
overlap. A container restart mid-sweep is safe by construction.

**The rank-move beat, and what it took to make it honest.** §10.1 wants *"You
dropped out of the top 10 — once per run"*, which asserts a **change**. The
first cut of this module did not build it, because `games_board` ranked as of
the latest close and took no as-of date: a single observation can only say
where a player is now, never that they moved, and firing on "currently outside
the top 10" would report a drop that may never have happened — the `?? 0`
family, where an unmeasured value and a real one get collapsed. It is built
now, off `games_board.ranked_entrants(field_id, as_of=…)`, comparing two
**consecutive closes** rather than two calendar days: standings move once per
close, so a weekend or a missed snapshot would otherwise compare a close
against nothing.

Three conditions have to hold before it can fire at all, and each rules out a
different fabrication: the field needs **more than ten measured entrants** (in
a field of eight nobody can leave a top ten, so the beat is not merely quiet —
it is inapplicable), the player needs a rank at **both** observations (a rank
that appeared out of nothing is not a drop), and the drop must cross the
boundary. It fires at most once per run.

**The Wind-Up has no push and never will** — §10.1: *"a push telling someone
they are losing is cruel."* There is deliberately no beat for it below, so a
future edit would have to add one rather than merely flip a flag.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.core.logging import logger
from app.db import get_session, init_schema
from app.db.models import GameEntryRow, GameFieldRow, NotificationRow, User
from app.services import games_board
from app.services.games_arc import FINAL_STRETCH_DAYS
from app.services.notification_service import notify

# §10.1's caps. One a day is deliberately tight: the channel's value is the
# Close, and every other push spends against it.
MAX_PUSH_PER_DAY = 1
MAX_PUSH_PER_WEEK = 4

# Quiet hours in the user's OWN timezone (`users.timezone`, the column CR095
# already reuses — no second timezone field). 21:00 → 08:00 local.
QUIET_START_LOCAL_HOUR = 21
QUIET_END_LOCAL_HOUR = 8

# How long before `locks_at` the entry beat opens. §10.1's example is "entries
# close in 2h", and it calls this "the highest-value push in the design".
ENTRIES_CLOSING_LEAD = timedelta(hours=2)

TYPE_ENTRIES_CLOSING = "game_entries_closing"
TYPE_FINAL_STRETCH = "game_final_stretch"
TYPE_SETTLED = "game_settled"
TYPE_DUEL_CHALLENGED = "game_duel_challenged"
TYPE_RANK_MOVE = "game_rank_move"

# §10.1's "top 10". In a field of eight everybody is inside it by arithmetic —
# no rank can exceed the field's own size — so the beat is not merely quiet at
# alpha field sizes, it is inapplicable. That is a property of
# `dropped_out_of_top`, not of a size check, which is why the size check below
# is written as an early-out rather than as a control: removing it changes no
# outcome, only how many boards get computed. Mutation-verified.
RANK_MOVE_TOP_N = 10

# §10.1: "The Close and a received challenge are exempt from suppression but
# never duplicated." Exempt from the CAPS; see the module docstring on why
# quiet hours defer rather than drop.
EXEMPT_FROM_CAPS = frozenset({TYPE_SETTLED, TYPE_DUEL_CHALLENGED})

# Beats that expire: delivering them late is delivering something false, so
# they are never deferred out of quiet hours.
EXPIRES = frozenset({TYPE_ENTRIES_CLOSING})


def in_quiet_hours(local_now: datetime) -> bool:
    """Local-time quiet hours, wrapping midnight.

    Takes an already-localised datetime so the rule is pure and testable
    without a tz database lookup or a user row.
    """
    hour = local_now.hour
    if QUIET_START_LOCAL_HOUR > QUIET_END_LOCAL_HOUR:
        return hour >= QUIET_START_LOCAL_HOUR or hour < QUIET_END_LOCAL_HOUR
    return QUIET_START_LOCAL_HOUR <= hour < QUIET_END_LOCAL_HOUR


def may_send(
    beat_type: str,
    local_now: datetime,
    *,
    sent_today: int,
    sent_this_week: int,
) -> bool:
    """Whether policy permits this beat right now.

    Pure and argument-only: the caps arrive as counts rather than as a session,
    so every branch is testable without a database. Says nothing about whether
    the beat is *due* — that is each beat's own window — and nothing about
    duplication, which is the DB constraint's job, not a check-then-write.
    """
    if in_quiet_hours(local_now):
        return False
    if beat_type in EXEMPT_FROM_CAPS:
        return True
    return sent_today < MAX_PUSH_PER_DAY and sent_this_week < MAX_PUSH_PER_WEEK


def _local_now(now: datetime, tz_name: str) -> datetime:
    """`now` in the user's timezone, falling back to UTC on a bad tz string.

    A user row carrying an unknown zone must not take the whole sweep down with
    it, and must not silently be treated as if quiet hours did not apply — UTC
    still applies them, just on the wrong clock, which is the loud-and-degraded
    option rather than the silent-and-off one.
    """
    try:
        return now.astimezone(ZoneInfo(tz_name or "UTC"))
    except Exception:
        logger.warning("games_push_bad_timezone", timezone=tz_name)
        return now.astimezone(timezone.utc)


def _push_counts(session, user_id: UUID, local_now: datetime) -> tuple[int, int]:
    """How many game pushes this user has had today and this week, counted on
    the user's OWN local day — the same reasoning `daily_reminder` applies to
    its `source_ref`: a cap phrased "per day" means the user's day.
    """
    day_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = day_start - timedelta(days=6)
    rows = session.execute(
        select(NotificationRow.created_at).where(
            NotificationRow.user_id == user_id,
            NotificationRow.type.in_(
                (
                    TYPE_ENTRIES_CLOSING,
                    TYPE_FINAL_STRETCH,
                    TYPE_SETTLED,
                    TYPE_DUEL_CHALLENGED,
                    TYPE_RANK_MOVE,
                )
            ),
            NotificationRow.created_at >= week_start.astimezone(timezone.utc),
        )
    ).scalars().all()
    today = sum(
        1 for c in rows
        if c is not None and c.astimezone(local_now.tzinfo) >= day_start
    )
    return today, len(rows)


def _send(
    *, user_id: UUID, tz_name: str, beat_type: str, title: str, body: str,
    deep_link: dict, source_ref: str, now: datetime,
) -> bool:
    """One beat, policy-checked, through the single write path."""
    local_now = _local_now(now, tz_name)
    with get_session() as s:
        sent_today, sent_week = _push_counts(s, user_id, local_now)
    if not may_send(beat_type, local_now, sent_today=sent_today,
                    sent_this_week=sent_week):
        return False
    result = notify(
        user_id, beat_type, title, body, deep_link,
        source_ref=source_ref, created_at=now,
    )
    return not result.was_duplicate


# How far back the settled beat will look. **This is a blast guard, not a
# tuning knob.** `source_ref` makes each close send at most once ever, but
# "at most once" says nothing about WHEN: the first tick after this module
# ships would otherwise find every historical close in the table and push all
# of them, to every player, at once. That is the precise failure the reminder
# rule exists to prevent, delivered by the feature meant to protect it.
SETTLED_LOOKBACK = timedelta(days=2)


def _beat_entries_closing(now: datetime) -> int:
    """*"Entries close in 2h, and you are not entered."* §10.1's highest-value
    push, and the clearest decision-event in the design: it is actionable, it
    expires, and the player can do exactly one thing about it.

    Sent only to established players — someone with at least one prior entry.
    A user who has never played is not being reminded, they are being
    recruited, and that is a different product decision with a different
    consent story. Desks are excluded: they are filled by
    `games_desks.run_desk_fill_tick`, and nobody is behind them to notify.
    """
    sent = 0
    with get_session() as s:
        fields = s.execute(
            select(GameFieldRow).where(
                GameFieldRow.locks_at > now,
                GameFieldRow.locks_at <= now + ENTRIES_CLOSING_LEAD,
            )
        ).scalars().all()
        if not fields:
            return 0
        players = s.execute(
            select(User.id, User.timezone)
            .join(GameEntryRow, GameEntryRow.user_id == User.id)
            .where(User.is_desk.is_(False))
            .distinct()
        ).all()
        entered = {
            (row.field_id, row.user_id)
            for row in s.execute(
                select(GameEntryRow.field_id, GameEntryRow.user_id).where(
                    GameEntryRow.field_id.in_([f.id for f in fields])
                )
            ).all()
        }
    for field in fields:
        for user_id, tz_name in players:
            if (field.id, user_id) in entered:
                continue
            if _send(
                user_id=user_id, tz_name=tz_name,
                beat_type=TYPE_ENTRIES_CLOSING,
                title="Entries close in 2 hours",
                body=f"The {field.cadence} field locks soon. You are not in it.",
                deep_link={"screen": "games_lobby", "cadence": field.cadence},
                source_ref=str(field.id), now=now,
            ):
                sent += 1
    return sent


def _beat_final_stretch(now: datetime) -> int:
    """*"Your run closes tomorrow."* §10 calls this the anticipation engine,
    and it is the beat most damaged by having no push: it exists to bring
    someone back for a decision they still have time to make.

    Fires once per run (`source_ref` = the run), on entering the cadence's own
    final-stretch window — the same `FINAL_STRETCH_DAYS` table the in-app beat
    reads, so the push and the screen can never disagree about which beat the
    run is in.
    """
    today = now.astimezone(timezone.utc).date()
    sent = 0
    with get_session() as s:
        rows = s.execute(
            select(GameEntryRow.user_id, GameEntryRow.run_id, User.timezone,
                   GameFieldRow.cadence, GameFieldRow.ends_on)
            .join(GameFieldRow, GameEntryRow.field_id == GameFieldRow.id)
            .join(User, GameEntryRow.user_id == User.id)
            .where(
                # BOTH live states, and `entered` is the one that matters most.
                # `entered` becomes `active` only on the first trade
                # (`games_service.py:951`), so a player who entered and never
                # traded stays `entered` for the whole run — which is exactly
                # the person with a decision still open and the period running
                # out. Filtering on `active` alone would have sent this beat to
                # everyone except the player who most needs it.
                GameEntryRow.state.in_(("entered", "active")),
                User.is_desk.is_(False),
                GameFieldRow.ends_on >= today,
            )
        ).all()
    for user_id, run_id, tz_name, cadence, ends_on in rows:
        days_left = (ends_on - today).days
        if days_left > FINAL_STRETCH_DAYS.get(cadence, 2):
            continue
        day_word = "tomorrow" if days_left == 1 else (
            "today" if days_left == 0 else f"in {days_left} days"
        )
        if _send(
            user_id=user_id, tz_name=tz_name, beat_type=TYPE_FINAL_STRETCH,
            title="Final stretch",
            body=f"Your {cadence} run closes {day_word}.",
            deep_link={"screen": "games_run", "run_id": str(run_id)},
            source_ref=str(run_id), now=now,
        ):
            sent += 1
    return sent


def _beat_settled(now: datetime) -> int:
    """*"Your run has settled — results are ready."* The Close: the message
    the whole channel is being protected for, and the one beat exempt from the
    caps.

    Bounded by [`SETTLED_LOOKBACK`] rather than by state alone — see that
    constant for why an unbounded version would blast on first deploy.
    """
    today = now.astimezone(timezone.utc).date()
    sent = 0
    with get_session() as s:
        rows = s.execute(
            select(GameEntryRow.user_id, GameEntryRow.run_id, User.timezone,
                   GameFieldRow.cadence)
            .join(GameFieldRow, GameEntryRow.field_id == GameFieldRow.id)
            .join(User, GameEntryRow.user_id == User.id)
            .where(
                GameEntryRow.state == "finished",
                User.is_desk.is_(False),
                GameFieldRow.ends_on >= today - SETTLED_LOOKBACK,
            )
        ).all()
    for user_id, run_id, tz_name, cadence in rows:
        if _send(
            user_id=user_id, tz_name=tz_name, beat_type=TYPE_SETTLED,
            title="Your run has settled",
            body=f"Your {cadence} results are ready.",
            deep_link={"screen": "games_close", "run_id": str(run_id)},
            source_ref=str(run_id), now=now,
        ):
            sent += 1
    return sent


def dropped_out_of_top(
    previous_rank: int | None, current_rank: int | None, *, top_n: int,
) -> bool:
    """Did this player leave the top `top_n` between two closes?

    Pure, because every wrong answer here is a push that describes something
    that did not happen:

      * a player unranked at the earlier close was not *in* the top ten, so
        appearing below it now is arriving, not dropping;
      * a player unranked at the later close has no measured position, and
        "you dropped out" would be asserting one from its absence.
    """
    if previous_rank is None or current_rank is None:
        return False
    return previous_rank <= top_n < current_rank


def _beat_rank_move(now: datetime) -> int:
    """*"You dropped out of the top 10."* §10.1's daily beat, and the one that
    needs two observations rather than one.

    Not exempt from the caps, and deliberately last in the sweep: it is the
    least urgent of the four, so when the daily cap binds this is the message
    that yields the slot. A player who is told they slipped but never told
    their run settled has been served exactly backwards.
    """
    sent = 0
    with get_session() as s:
        field_ids = s.execute(
            select(GameFieldRow.id).where(GameFieldRow.state != "closed")
        ).scalars().all()
        tz_by_user = dict(
            s.execute(
                select(User.id, User.timezone).where(User.is_desk.is_(False))
            ).all()
        )
    for field_id in field_ids:
        dates = games_board.close_dates_for_field(field_id, limit=2)
        # A change needs two observations. One close (or none) is not a quiet
        # day for this beat — it is a question that cannot be asked yet.
        if len(dates) < 2:
            continue
        current = games_board.ranked_entrants(field_id, as_of=dates[0])
        measured = [r for r in current if r["rank"] is not None]
        # Early-out, not a control: with this many entrants no rank can exceed
        # the boundary, so `dropped_out_of_top` would return False for every
        # row anyway. It saves the second board, which is the expensive half.
        if len(measured) <= RANK_MOVE_TOP_N:
            continue
        previous = games_board.ranked_entrants(field_id, as_of=dates[1])
        prev_rank_by_run = {
            r[games_board.RUN_KEY]: r["rank"] for r in previous
        }
        for row in current:
            if row["is_desk"]:
                continue
            run_id = row[games_board.RUN_KEY]
            user_id = row[games_board.USER_KEY]
            # A desk is excluded above; anyone left who is not in the map is a
            # desk-flagged user this query did not return. Skipping is right —
            # nobody is behind a desk to notify.
            if user_id not in tz_by_user:
                continue
            if not dropped_out_of_top(
                prev_rank_by_run.get(run_id), row["rank"],
                top_n=RANK_MOVE_TOP_N,
            ):
                continue
            if _send(
                user_id=user_id, tz_name=tz_by_user[user_id],
                beat_type=TYPE_RANK_MOVE,
                title=f"You dropped out of the top {RANK_MOVE_TOP_N}",
                body=(
                    f"You are {row['rank']} of {len(measured)}. "
                    "There is still time in this run."
                ),
                deep_link={"screen": "games_board", "run_id": str(run_id)},
                source_ref=str(run_id), now=now,
            ):
                sent += 1
    return sent


def run_games_push_tick(*, now: datetime | None = None) -> dict[str, int]:
    """The sweep. Idempotent by construction — every beat keys on a stable
    `source_ref`, so re-running it sends nothing new.

    Beats are swept in ascending order of urgency-to-the-player so that when
    the daily cap binds, the message that survives is the one worth the slot:
    settled (exempt) always lands, then the expiring entry beat, then the
    final stretch, then the rank move — a player told they slipped but never
    told their run settled has been served exactly backwards.
    """
    init_schema()
    now = now or datetime.now(timezone.utc)
    stats = {
        "settled": _beat_settled(now),
        "entries_closing": _beat_entries_closing(now),
        "final_stretch": _beat_final_stretch(now),
        "rank_move": _beat_rank_move(now),
    }
    stats["total"] = sum(stats.values())
    return stats
