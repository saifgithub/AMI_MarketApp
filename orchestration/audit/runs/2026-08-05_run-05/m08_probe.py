"""M08 r1 audit — independently re-run §5.1's probe at c0f1ac86, then push past
it: what the PARTIAL index now permits that the submission's analysis predates."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.services.journal_store import get_journal_store
from app.services.portfolio_health_journal import build_finding_entry, finding_dedupe_key
from tests.unit.test_portfolio_health_journal import _entry


def test_probe_5_1_replay_after_delete() -> None:
    store = get_journal_store()
    user_id, portfolio_id = uuid4(), uuid4()

    first, created1 = store.append_unique(_entry(user_id=user_id, portfolio_id=portfolio_id))
    print(f"\n1. first write                   created={created1} id={first.id}")

    store.soft_delete(user_id, first.id)
    print(f"2. user swipes it away           get -> "
          f"{store.get(user_id, first.id) is not None and 'entry' or None}")

    key = finding_dedupe_key(portfolio_id, "2026-08-02")
    live = store.find_by_dedupe_key(user_id, key)
    print(f"3. route's idempotency read      find_by_dedupe_key -> {live}")

    second, created2 = store.append_unique(_entry(user_id=user_id, portfolio_id=portfolio_id))
    print(f"4. re-write, same dedupe_key     created={created2} id={second.id}")
    print(f"   same row as the tombstone?    {second.id == first.id}")
    print(f"   returned row deleted_at       {second.deleted_at}")

    got = store.get(user_id, second.id)
    print(f"5. client opens journal_entry_id store.get -> "
          f"{'a live entry' if got is not None and got.deleted_at is None else got}")

    now = datetime.now(timezone.utc)
    used, _first_at, daily = store.portfolio_health_stats(user_id, portfolio_id, now=now)
    print(f"6. gate counters after both      used={used} daily_used={daily}")


def test_probe_how_far_can_delete_replay_go() -> None:
    """AUD — the partial index permits N tombstones on one key. What bounds it?"""
    store = get_journal_store()
    user_id, portfolio_id = uuid4(), uuid4()
    now = datetime.now(timezone.utc)
    ids = []
    for i in range(5):
        entry, created = store.append_unique(
            _entry(user_id=user_id, portfolio_id=portfolio_id),
        )
        ids.append((created, str(entry.id)[:8]))
        store.soft_delete(user_id, entry.id)
    used, _f, daily = store.portfolio_health_stats(user_id, portfolio_id, now=now)
    print(f"\n5x (create, delete) on ONE dedupe_key: {ids}")
    print(f"   distinct rows created         : {len({i for _c, i in ids})}")
    print(f"   portfolio_health_stats        : used={used} daily_used={daily}")
    print("   (the counter is the row, so each replay costs the user budget)")


def test_probe_tombstone_restore_collision() -> None:
    """AUD — restore a tombstone whose key a LIVE row now holds."""
    store = get_journal_store()
    user_id, portfolio_id = uuid4(), uuid4()

    first, _ = store.append_unique(_entry(user_id=user_id, portfolio_id=portfolio_id))
    store.soft_delete(user_id, first.id)
    second, created2 = store.append_unique(_entry(user_id=user_id, portfolio_id=portfolio_id))
    print(f"\ntombstone {str(first.id)[:8]}, live {str(second.id)[:8]}, created={created2}")

    outcome = store.restore_with_reason(user_id, first.id)
    print(f"restore_with_reason(tombstone)  -> {outcome}")

    live_now = store.find_by_dedupe_key(
        user_id, finding_dedupe_key(portfolio_id, "2026-08-02"),
    )
    print(f"find_by_dedupe_key after restore-> {str(live_now.id)[:8] if live_now else None}")
    latest = store.latest_portfolio_health_entry(user_id, portfolio_id)
    print(f"latest_portfolio_health_entry   -> {str(latest.id)[:8] if latest else None}"
          f"  deleted_at={latest.deleted_at if latest else None}")
