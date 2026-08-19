"""CR177 — the app records that it stopped you.

Until this CR, `POST /v1/sim/submit`'s blocked branch returned the violation
and wrote nothing durable, so a working safety floor and an absent one
produced identical history. These tests pin the acceptance list of
`docs/forward_planning/CR177_safety_floor_journal/CR177.md`:

1. a floor-blocked trade writes EXACTLY ONE `compliance_block` entry naming
   the rule (`blocked_by` non-empty) — and removing the write reds this
   (acceptance 6, the mutation kill);
2. the entry is NOT a `SIM_TRADE`, so CR133's "how your trades ended"
   denominator is provably unchanged;
3. the happy path writes exactly what it wrote before — one SIM_TRADE,
   zero blocks;
4. the game path writes nothing — the §7.1 fence holds;
5. a MECHANICAL refusal (insufficient cash — `blocked_by=None`) is not the
   floor firing and stays unjournaled: the same distinction the spec draws
   for the game path ("a cash/limit refusal, not a mandate block");
6. the sweep's refused-at-fill — the block with no request in the call
   stack, which the spec predates (CR170 landed after it was written) —
   writes the same entry, carrying the order id;
7. §5.2's measured position: identical repeats are identical ROWS. The
   repetition is the teaching signal; the reader aggregates, the data stays
   honest.

Client half: `mobile/lib/models/journal.dart::fromWire` returns null for
`compliance_block` on every installed build, and DEF210 gave the journal
card an explicit `case null:` badge — the render is exhaustive over the
nullable enum, so inertness is a compile-time property there, pinned at the
model level in mobile/test/models/journal_entry_type_test.dart.
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select

from app.db import get_session
from app.db.models import JournalEntryRow
from app.schemas.journal import EntryType
from app.schemas.trade import OrderType, Side
from app.services import market_data as _md
from app.services.coach_engine import hydrate_coach_mandate
from app.services.sim_engine import SimEngine
from app.services.sim_resting_orders import sweep_resting_orders


class _Pinned:
    name = "pinned"
    source = "pinned"

    def __init__(self, prices: dict[str, float]) -> None:
        self.prices = dict(prices)

    def set(self, ticker: str, price: float) -> None:
        self.prices[ticker] = price

    def quote(self, ticker: str):
        return _md.Quote(price=self.prices.get(ticker, 100.0), source=self.source)

    def get_price(self, ticker: str):
        return self.prices.get(ticker, 100.0)

    def history(self, *a, **k):  # pragma: no cover
        return []

    def news(self, *a, **k):  # pragma: no cover
        return []

    def earnings(self, *a, **k):  # pragma: no cover
        return None


def _mandate(**over):
    base = {"plan": "trader", "single_name_cap_pct": 100.0,
            "max_open_risk_pct": 100.0}
    base.update(over)
    return hydrate_coach_mandate(base)


def _api(provider=None):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.sim import router as sim_router
    from app.services.auth_service import AuthService
    from app.services.sim_engine import get_sim_engine

    sim = SimEngine(provider=provider or _Pinned({"AAPL": 100.0}))
    app = FastAPI()
    app.include_router(sim_router)
    app.dependency_overrides[get_sim_engine] = lambda: sim
    user, token, _ = AuthService().ensure_anonymous(device_user_id=None)
    client = TestClient(app, raise_server_exceptions=False)
    return client, sim, user, token


def _journal_rows(user_id, entry_type: str | None = None):
    with get_session() as s:
        q = select(JournalEntryRow).where(JournalEntryRow.user_id == user_id)
        if entry_type is not None:
            q = q.where(JournalEntryRow.entry_type == entry_type)
        return s.execute(q).scalars().all()


def _submit(client, user, token, **over):
    body = {
        "user_id": str(user.id),
        "ticker": "AAPL",
        "side": "buy",
        "quantity": 1,
        "order_type": "market",
    }
    body.update(over)
    return client.post(
        "/v1/sim/submit", json=body,
        headers={"Authorization": f"Bearer {token}"},
    )


_BLOCKLIST_OVERRIDE = {"compliance": {"ticker_blocklist": ["AAPL"],
                                      "long_only": True, "liquid_only": True}}


# ── Acceptance 1 + 2 + 6: the block writes, names its rule, is not a trade ──


def test_a_blocked_trade_writes_exactly_one_entry_naming_the_rule():
    client, _sim, user, token = _api()
    r = _submit(client, user, token, mandate_override=_BLOCKLIST_OVERRIDE)
    assert r.status_code == 200
    assert r.json()["ok"] is False, "precondition: the floor must have fired"

    blocks = _journal_rows(user.id, EntryType.COMPLIANCE_BLOCK.value)
    assert len(blocks) == 1, (
        "a floor-blocked trade writes EXACTLY ONE compliance_block entry — "
        "removing the write in api/sim.py's blocked branch reds this line "
        "(acceptance 6)"
    )
    entry = blocks[0]
    assert entry.payload["blocked_by"], "the rule that stopped you, non-empty"
    assert entry.payload["violations"], "the violation sentences travel too"
    assert entry.payload["source"] == "ticket"
    assert entry.ticker == "AAPL"
    assert entry.outcome is None, (
        "a block has no win/loss and must never render as either"
    )

    # Acceptance 2 — NOT a SIM_TRADE: CR133's "how your trades ended" card
    # buckets SIM_TRADE rows, and a blocked attempt has no outcome to bucket.
    assert entry.entry_type != EntryType.SIM_TRADE.value
    assert _journal_rows(user.id, EntryType.SIM_TRADE.value) == [], (
        "the denominator of CR133's strongest card is provably unchanged"
    )


# ── Acceptance 3: the happy path is untouched ───────────────────────────────


def test_an_accepted_trade_writes_its_sim_trade_and_no_block_entry():
    client, _sim, user, token = _api()
    r = _submit(client, user, token,
                stop=94.0, target=113.0, horizon_days=30)
    assert r.status_code == 200
    assert r.json()["ok"] is True, r.text

    assert len(_journal_rows(user.id, EntryType.SIM_TRADE.value)) == 1
    assert _journal_rows(user.id, EntryType.COMPLIANCE_BLOCK.value) == []


# ── The discriminator: a mechanical refusal is not the floor ────────────────


def test_a_wrong_side_bracket_refusal_is_not_journaled_as_a_block():
    """`blocked_by=None` refusals — a wrong-side bracket, insufficient cash —
    are not a mandate decision. The spec draws this exact line for the game
    path ("a cash/limit refusal, not a mandate block"); it holds inside the
    training path too.

    The driver is the wrong-side bracket (a BUY whose stop is above the
    entry, DEF312's check) rather than insufficient cash, because cash
    cannot be reached without the floor firing first: any notional large
    enough to exceed $10k of cash also exceeds the single-name cap, and the
    cap is checked earlier."""
    client, _sim, user, token = _api()
    r = _submit(client, user, token, quantity=1, stop=110.0, target=113.0)
    assert r.status_code == 200
    assert r.json()["ok"] is False
    assert r.json()["compliance"]["blocked_by"] is None, (
        "precondition: this refusal must be mechanical, not the floor"
    )

    assert _journal_rows(user.id) == [], "nothing journaled for it"


# ── Acceptance 4: the game path writes nothing ──────────────────────────────


def test_a_refused_game_trade_writes_no_journal_entry_at_all():
    """Games deliberately never run the safety floor (§7.1 keeps two public
    entry points precisely so), and a game refusal is a cash refusal. The
    fence is structural — the recorder lives on the training path — and this
    pins it from the game side."""
    sim = SimEngine(provider=_Pinned({"AAPL": 100.0}))
    user_id, run_id = uuid4(), uuid4()
    result = sim.submit_game_trade(
        user_id=user_id, run_id=run_id, ticker="AAPL",
        side=Side.BUY, quantity=1_000_000,
    )
    assert result.accepted is False, "precondition: the game refused it"

    assert _journal_rows(user_id) == []


# ── The sweep: the block with no request in the call stack ──────────────────


def test_a_resting_order_refused_at_fill_writes_the_entry_with_the_order_id():
    """CR170's `fill_resting_order` re-runs the floor so a resting order is
    not a time-delayed bypass — which makes the sweep the SECOND place a
    block can happen, and the more invisible one: nobody is watching when it
    fires. The spec predates CR170; the recorder covers both sites so they
    cannot diverge."""
    prov = _Pinned({"AAPL": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    r = sim.submit(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=2,
        mandate=_mandate(), order_type=OrderType.LIMIT, limit_price=90.0,
    )
    assert r.accepted and r.resting, "precondition: the order must rest"
    order_id = r.resting_order.id

    # The mandate changes underneath the resting order (the A2 idiom from
    # test_cr170_resting_orders.py — set on `compliance` directly, because
    # hydrate_coach_mandate takes no flat ticker_blocklist).
    blocked = _mandate()
    blocked.compliance.ticker_blocklist = ["AAPL"]
    import app.services.sim_resting_orders as sro
    orig = sro.resolve_mandate
    sro.resolve_mandate = lambda uid, override: blocked
    try:
        prov.set("AAPL", 89.0)  # triggers the limit
        from datetime import datetime, timedelta, timezone
        from app.db.models import SimRestingOrderRow
        with get_session() as s:
            exp = s.get(SimRestingOrderRow, order_id).expires_at
        exp = exp if exp.tzinfo else exp.replace(tzinfo=timezone.utc)
        stats = sweep_resting_orders(
            user_id=user_id, now=exp - timedelta(minutes=5), engine=sim,
        )
    finally:
        sro.resolve_mandate = orig
    assert stats["rejected"] == 1, "precondition: the sweep must have refused"

    blocks = _journal_rows(user_id, EntryType.COMPLIANCE_BLOCK.value)
    assert len(blocks) == 1
    assert blocks[0].reference_id == order_id, (
        "with no request in the call stack, the entry itself must say which "
        "order it refused"
    )
    assert blocks[0].payload["source"] == "resting_order"
    assert blocks[0].payload["blocked_by"]


# ── §5.2: identical repeats are identical rows ──────────────────────────────


def test_three_identical_blocks_are_three_rows():
    """The measured position the spec asks for, stated as a test: every block
    is written, none deduped away. The repetition IS the teaching signal —
    "you attempted the same breach three times" is precisely the sentence
    the Journal exists to make visible — and the reader aggregates.

    Measured, not assumed (trade_ticket_sheet.dart:507-522): on a blocked
    response the sheet STAYS OPEN with the violation rendered — only
    `result.ok` pops — so a repeat costs one tap on a visible refusal, not a
    reopen. That makes hammering cheap, and the position is still to write
    every row: collapsing at write time destroys the signal, and if real
    data ever shows abuse, `JournalStore.append_unique`/`dedupe_key` already
    exists as the collapse mechanism — to be applied then, with numbers."""
    client, _sim, user, token = _api()
    for _ in range(3):
        r = _submit(client, user, token, mandate_override=_BLOCKLIST_OVERRIDE)
        assert r.json()["ok"] is False

    blocks = _journal_rows(user.id, EntryType.COMPLIANCE_BLOCK.value)
    assert len(blocks) == 3
    assert all(b.dedupe_key is None for b in blocks), (
        "dedupe_key stays NULL deliberately — collapsing repeats at write "
        "time is the position §5.2 rejects"
    )
