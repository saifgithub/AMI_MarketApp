"""DEF220 — the six check-then-INSERT sites, raced for real, one test per OUTCOME.

`test_p15_check_then_insert_guard.py` asserts a handler EXISTS. That is a source rule and
it cannot tell `except IntegrityError: pass` from a correct answer — which is exactly the
failure DEF220's row warns about: *"Wrapping all six in the same `except IntegrityError:
pass` would satisfy the guard and answer none of those questions."* So the guard says the
handler is there, and this file says the handler is RIGHT.

The three outcomes actually chosen, and why they differ:

* **re-read and update** — `_upsert_user_device`, and the edit counter. The loser still has
  a change to apply: device ownership re-keys on claim adoption, and the counter feeds a
  paid cap where a dropped increment is a free edit.
* **retry, then raise** — `mandate_store.upsert`, `overlay_store.save_new_version`. Both
  hold text the user wrote. Skipping would discard an edit while every layer above reads
  success.
* **skip** — `_award_badge`, `_cache_write`. Idempotent by intent; the row's existence is
  the whole desired end state.

**These race the real constraint rather than mocking it.** Each test writes the conflicting
row through a SEPARATE committed session first, then calls the function — which is the
read-to-commit gap P15 describes, reproduced deterministically instead of with threads. A
thread race here would be flaky-green for the same reason the bug was invisible: the
auditor measured 0 races in 60 trials because one uvicorn holds an invariant nobody wrote
down.

Mac-safe: sqlite tempfile fixture, no backend, no network.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.db import get_session
from app.db.models import (
    AgentActivationRow,
    BadgeRow,
    MandateRow,
    OverlayEditCounter,
    SocialSentimentCacheRow,
    User,
    UserDeviceRow,
    UserOverlayRow,
)
from app.services.auth_service import _upsert_user_device
from app.services.mandate_store import MandateStore, MandateVersionConflictError
from app.services.overlay_store import OverlayStore
from app.services.brief_engine import hydrate_brief_mandate
from app.schemas import AgentId, Plan


def _make_user(**kw) -> UUID:
    uid = uuid4()
    with get_session() as s:
        s.add(User(
            id=uid,
            plan=kw.get("plan", "floor_pass"),
            is_anonymous=True,
            credit_balance=0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ))
    return uid


# ── outcome 1: re-read and update ────────────────────────────────────────────────


class _BlindOnce:
    """A session proxy whose FIRST `execute` reports nothing found.

    This is the read-to-commit gap of P15, reproduced deterministically: the pre-check
    SELECT lands before the other writer commits, so it misses — and then the real INSERT
    meets the real constraint. Everything else delegates to the genuine session, so the
    collision, the SAVEPOINT and the rollback are all real.

    Threads would not do this reliably. The auditor measured 0 races in 60 trials on this
    stack, because one uvicorn holds an invariant nobody wrote down.
    """

    def __init__(self, session):
        self._s = session
        self._blinded = False

    def execute(self, *a, **k):
        if not self._blinded:
            self._blinded = True

            class _Empty:
                def scalar_one_or_none(self):
                    return None

                def scalar(self):
                    return None

            return _Empty()
        return self._s.execute(*a, **k)

    def __getattr__(self, name):
        return getattr(self._s, name)




def test_a_device_that_loses_the_race_still_re_keys_its_owner():
    """The outcome that a `pass` would silently get wrong.

    Two bootstraps from one device: the first (an anonymous session) commits the row, the
    second (the claimed account) loses the INSERT. If the loser skips, the device stays
    owned by the pre-claim anonymous user — the account linkage the else-branch exists to
    perform, silently dropped.
    """
    anon = _make_user()
    claimed = _make_user()
    install_id = uuid4()

    with get_session() as s:  # the winner, committed before we run
        s.add(UserDeviceRow(
            user_id=anon,
            device_install_id=install_id,
            device_model="iPhone13,2",
            os_version="17.0",
            app_version="0.1.0+90",
            first_seen_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
        ))

    with get_session() as s:
        # Blinded pre-check: the SELECT lands before the winner commits, so the function
        # takes its INSERT path and meets the real UNIQUE constraint. Without this the
        # else-branch would run and the handler under test would never execute.
        _upsert_user_device(
            _BlindOnce(s), user_id=claimed, device_install_id=install_id,
            device_model="iPhone13,2", os_version="17.1", app_version="0.1.0+94",
        )

    with get_session() as s:
        rows = list(s.execute(
            select(UserDeviceRow).where(
                UserDeviceRow.device_install_id == install_id
            )
        ).scalars())

    assert len(rows) == 1, "the constraint held but a duplicate row appeared"
    assert rows[0].user_id == claimed, (
        "the device row still points at the pre-claim anonymous user — a lost race "
        "silently discarded the ownership re-key that claim adoption depends on"
    )
    assert rows[0].app_version == "0.1.0+94", "the context refresh was dropped too"


class _BlindSelectOn:
    """Session proxy that misses the FIRST select touching `table_name`.

    `save_new_version` opens its own session, so the constructor-injection `_BlindOnce`
    uses is not available — and blinding by call ORDER would break the moment a query is
    added above. Matching the statement's own text against the table is stable under that.
    """

    def __init__(self, session, table_name: str):
        self._s = session
        self._table = table_name
        self._blinded = False

    def execute(self, stmt, *a, **k):
        if not self._blinded and self._table in str(stmt) and "SELECT" in str(stmt):
            self._blinded = True

            class _Empty:
                def scalar_one_or_none(self):
                    return None

                def scalar(self):
                    return None

            return _Empty()
        return self._s.execute(stmt, *a, **k)

    def __getattr__(self, name):
        return getattr(self._s, name)


def test_the_overlay_edit_counter_survives_a_lost_race(monkeypatch):
    """The counter feeds `can_edit`, i.e. the Floor Pass lifetime cap.

    A dropped increment hands the user a free edit; a double-count charges them one they
    never spent. Neither is acceptable, and on collision the row demonstrably exists — so
    the only correct answer is to re-read it and apply the same `+1` the else-branch does.
    """
    import contextlib

    import app.services.overlay_store as overlay_mod

    uid = _make_user()
    agent = AgentId.MARKET_ANALYST
    aid = agent.value

    with get_session() as s:  # someone else created the counter first
        s.add(OverlayEditCounter(user_id=uid, agent_id=aid, count=1))

    real_get_session = overlay_mod.get_session

    @contextlib.contextmanager
    def _blinded_session():
        with real_get_session() as s:
            yield _BlindSelectOn(s, "overlay_edit_counts")

    monkeypatch.setattr(overlay_mod, "get_session", _blinded_session)

    OverlayStore().save_new_version(
        uid, agent, content="be more cautious", plain_english="cautious",
        plan=Plan.FLOOR_PASS,
    )

    with get_session() as s:
        counters = list(s.execute(
            select(OverlayEditCounter).where(
                OverlayEditCounter.user_id == uid,
                OverlayEditCounter.agent_id == aid,
            )
        ).scalars())

    assert len(counters) == 1
    assert counters[0].count == 2, (
        f"counter is {counters[0].count}, expected 2 — the edit was not counted, so the "
        "user keeps a lifetime edit they already spent"
    )


# ── outcome 2: retry, then raise ─────────────────────────────────────────────────


def test_a_mandate_write_that_loses_its_version_still_lands():
    """User-authored state: the edit must persist, at the next free version."""
    uid = _make_user()
    store = MandateStore()
    first = store.upsert(uid, hydrate_brief_mandate({"user_id": str(uid)}))
    assert first.version == 1

    # A concurrent writer took version 2 and left the CURRENT row at version 1 — the
    # arrangement that separates the fix from the bug. Pre-fix, `new_version` came from
    # `existing.version + 1`, i.e. the is_current row, which computes 2 and collides.
    # Deriving from MAX(version) computes 3 and lands. Had the taken row also been
    # is_current, both versions of the code would answer 3 and this test would prove
    # nothing.
    with get_session() as s:
        s.add(MandateRow(
            user_id=uid, version=2, is_current=False,
            snapshot=first.model_dump(mode="json"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ))

    second = store.upsert(uid, hydrate_brief_mandate({"user_id": str(uid)}))

    assert second.version == 3, (
        f"version {second.version}: the write did not retry past the taken version"
    )
    with get_session() as s:
        current = list(s.execute(
            select(MandateRow).where(
                MandateRow.user_id == uid, MandateRow.is_current.is_(True)
            )
        ).scalars())
    assert len(current) == 1 and current[0].version == 3


def test_a_mandate_write_that_cannot_land_raises_rather_than_vanishing(monkeypatch):
    """The third outcome must not be silence.

    Two consecutive collisions is a state a retry cannot fix, and
    `MandateVersionConflictError` is how the caller learns the edit did NOT persist —
    precisely the distinction a bare skip destroys. Reproduced by pinning the version
    probe one below a version that is already taken, so every attempt computes a number
    the constraint will reject.
    """
    import sqlalchemy

    import app.services.mandate_store as ms

    uid = _make_user()
    store = MandateStore()
    store.upsert(uid, hydrate_brief_mandate({"user_id": str(uid)}))

    taken = 50
    with get_session() as s:
        s.add(MandateRow(
            user_id=uid, version=taken, is_current=False,
            snapshot={}, created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ))

    monkeypatch.setattr(
        ms.func, "max", lambda _col: sqlalchemy.literal(taken - 1), raising=False
    )

    with pytest.raises(MandateVersionConflictError):
        store.upsert(uid, hydrate_brief_mandate({"user_id": str(uid)}))


def test_an_overlay_write_that_loses_its_version_still_lands(monkeypatch):
    """Same rule for the other user-authored surface.

    The version probe is blinded so attempt 1 computes a version that is already taken and
    genuinely collides; the retry then reads the real MAX and lands above it. Without the
    blinding the probe would simply return the right answer first time and the retry — the
    thing under test — would never run.
    """
    import contextlib

    import app.services.overlay_store as overlay_mod

    uid = _make_user()
    agent = AgentId.MARKET_ANALYST
    store = OverlayStore()
    store.save_new_version(uid, agent, content="v1", plain_english="v1", plan=Plan.TRADER)

    with get_session() as s:  # a concurrent writer takes version 2
        s.add(UserOverlayRow(
            user_id=uid, agent_id=agent.value, version=2,
            content="theirs", plain_english="theirs", is_active=False,
        ))

    real_get_session = overlay_mod.get_session

    @contextlib.contextmanager
    def _blinded_session():
        with real_get_session() as s:
            yield _BlindSelectOn(s, "user_overlays")

    monkeypatch.setattr(overlay_mod, "get_session", _blinded_session)

    result = store.save_new_version(
        uid, agent, content="mine", plain_english="mine", plan=Plan.TRADER,
    )

    assert result.version == 3, (
        f"version {result.version}: the overlay edit did not retry past the taken version"
    )
    with get_session() as s:
        mine = list(s.execute(
            select(UserOverlayRow).where(
                UserOverlayRow.user_id == uid, UserOverlayRow.version == 3
            )
        ).scalars())
    assert len(mine) == 1 and mine[0].content == "mine"


# ── outcome 3: skip ──────────────────────────────────────────────────────────────


def test_a_badge_that_loses_the_race_is_skipped_and_the_caller_survives():
    """Idempotent by intent — a badge awarded twice IS a skip.

    The load-bearing half is the second assertion. `_award_badge` runs inside
    `_grant_milestone`'s session, which is carrying a CREDIT grant. A bare `flush()` that
    raised would poison that transaction, so the loser of a cosmetic badge race would take
    a monetized credit grant down with it. The SAVEPOINT is what keeps the caller alive,
    and skipping is only safe because the credit half is guarded separately by the
    `reputation_events` ref row (DEF049's `_raise_on_race`).
    """
    from app.services.reputation_service import ReputationService

    uid = _make_user()
    with get_session() as s:
        user = s.get(User, uid)
        s.add(BadgeRow(
            id=uuid4(), user_id=uid, badge_key="streak_7",
            ref_type="streak_milestone", ref_id="streak-7",
            is_permanent_flair=False, earned_at=datetime.now(timezone.utc),
        ))
        s.flush()

        ReputationService()._award_badge(
            _BlindOnce(s), user=user, badge_key="streak_7", ref_id="streak-7",
            is_permanent_flair=False,
        )

        # The caller's transaction must still be usable — this is the credit grant.
        user.credit_balance = (user.credit_balance or 0) + 25

    with get_session() as s:
        rows = list(s.execute(
            select(BadgeRow).where(
                BadgeRow.user_id == uid, BadgeRow.badge_key == "streak_7"
            )
        ).scalars())
        balance = s.get(User, uid).credit_balance

    assert len(rows) == 1, "a duplicate badge row was written"
    assert balance == 25, (
        "the badge collision rolled back the caller's transaction, so a cosmetic race "
        "destroyed a credit grant — the exact reason this uses a SAVEPOINT"
    )


def test_a_lost_social_cache_write_is_not_reported_as_a_failure(monkeypatch):
    """The actual fix at this site, and it is about the LOG, not the row.

    An `except Exception` already swallowed the collision — so "no crash, one row" was
    true before the change and asserting only that would prove nothing. What was wrong is
    that a benign lost race logged `social_cache_write_failed` at WARN. Nothing failed. A
    warning that fires when the system is working correctly is how an operator learns to
    scroll past that line, which is the habit DEF277 and DEF300 exist to break.
    """
    import contextlib

    import app.db as db_mod
    from app.services import social_context

    with get_session() as s:
        s.add(SocialSentimentCacheRow(
            ticker="ZZZZ", found=False, payload=None,
            fetched_at=datetime.now(timezone.utc),
        ))

    class _BlindGet:
        """`_cache_write` reads with `session.get`, not `execute`."""

        def __init__(self, session):
            self._s = session
            self._blinded = False

        def get(self, *a, **k):
            if not self._blinded:
                self._blinded = True
                return None
            return self._s.get(*a, **k)

        def __getattr__(self, name):
            return getattr(self._s, name)

    real_get_session = db_mod.get_session

    @contextlib.contextmanager
    def _blinded_session():
        with real_get_session() as s:
            yield _BlindGet(s)

    monkeypatch.setattr(db_mod, "get_session", _blinded_session)

    events: list[tuple[str, str]] = []
    for level in ("info", "warn", "warning", "error"):
        monkeypatch.setattr(
            social_context.logger, level,
            lambda event, _lvl=level, **kw: events.append((_lvl, event)),
            raising=False,
        )

    social_context._cache_write("ZZZZ", None)

    names = [e for _lvl, e in events]
    assert "social_cache_write_lost_race" in names, (
        f"the lost race was not named as its own outcome; logged: {events}"
    )
    assert "social_cache_write_failed" not in names, (
        "a benign lost cache race is still logged as a FAILURE — the warning fires when "
        f"nothing is wrong: {events}"
    )
    assert all(lvl == "info" for lvl, _e in events), (
        f"the lost race is not an info-level event: {events}"
    )


def test_the_agent_unlock_savepoint_is_inside_the_loop_not_around_it():
    """`_check_agent_unlocks` adds several activations against ONE session, so WHERE the
    SAVEPOINT sits is the whole decision: around the loop, one lost race rolls back every
    other agent unlocked in the same pass — unlocks the user genuinely earned, dropped
    silently.

    Pinned structurally rather than raced. Driving the real function to a collision needs a
    full lesson corpus, gateway sets and passing progress rows, and a test that heavy would
    be asserting the fixture more than the placement. An earlier version of this test built
    its own `begin_nested()` inline and passed against every mutation — it was exercising
    SQLAlchemy, not our code, which is exactly what CLAUDE.md says not to write.
    """
    import ast
    import inspect
    import textwrap

    from app.services.lessons_service import LessonsService

    src = textwrap.dedent(inspect.getsource(LessonsService._check_agent_unlocks))
    fn = ast.parse(src).body[0]

    loops = [n for n in ast.walk(fn) if isinstance(n, ast.For)]
    assert loops, "the function no longer loops — re-read this test before changing it"

    def _has_begin_nested(node) -> bool:
        return any(
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "begin_nested"
            for n in ast.walk(node)
        )

    assert any(_has_begin_nested(loop) for loop in loops), (
        "no `begin_nested()` inside the per-agent loop: a collision on one agent now "
        "rolls back every other activation added in the same pass"
    )
    assert _has_begin_nested(fn), "the activation insert lost its SAVEPOINT entirely"
