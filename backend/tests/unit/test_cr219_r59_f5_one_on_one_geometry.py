"""CR219 R59-F5 (AT:R75) — numeric verification wired into the 1-on-1 surface.

Audit finding (`docs/forward_planning/CR219_room_prompt_contradictions/
dev_instructions/R59_numbers_audit.md` §3-F5): the 1-on-1 chat path had NO
verification of any kind — no geometry check, no R:R rewrite, no direction
check. `_verify_and_annotate_geometry` is already a pure function of
`(text, size_pct, reference_close)`; these tests prove it is now actually
called on the 1-on-1 reply path, at the FastAPI route
(`app/api/one_on_one.py::send_message`), not merely importable.

Three cases per the dispatch brief:
  1. A triple with an incoherent R:R gets annotated (`AMI verified`, ratio
     rewritten, drawdown contribution against the mandate's own cap).
  2. A clean/coherent reply passes untouched (no annotation noise).
  3. A reply with no full entry/stop/target triple is untouched (the gate —
     `_verify_and_annotate_geometry`'s own trigger condition, not something
     this wiring invents).

Plus one wiring-specific case: `reference_close` is sourced from
`compute_technicals(ticker)` (live-only, gated on `settings.use_real_market_data`)
rather than never populated at all — the 1-on-1 path builds no structured
`profile` dict the way the Room does, so this is a different (but equivalent)
plumbing path to the same number, proven independently.

Route-level (TestClient), not runner-level, because the wiring lives in
`one_on_one.py`'s `event_stream()`, one layer above `AgentRunner`. Mirrors the
`app.dependency_overrides[get_agent_runner]` fake-runner pattern already used
for this exact route in `test_def127_sse_framing_invariant.py`'s brief-router
sibling and `test_one_on_one_market_injection.py`'s `_FakeGateway`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.api.one_on_one import router as one_on_one_router
from app.schemas import AgentId, Mandate
from app.schemas.one_on_one import OneOnOneSession
from app.services.agent_runner import get_agent_runner
from app.services.rate_limit import one_on_one_message_rate_limit

# Same known-incoherent fixture `test_room_runner.py::test_def095_verify_and_
# annotate_geometry_unit` pins: 32.75/29.60/33.50 implies 0.2:1, narrated as
# 2.5:1. Reusing it verbatim means the expected annotation text below is not
# a fresh derivation — it is the Room's own already-proven output for this
# exact input, so a mismatch here can only be a 1-on-1 wiring defect, never a
# `_verify_and_annotate_geometry` math question.
_INCOHERENT_TRIPLE_REPLY = (
    "Instrument: SCHD\n"
    "Side: BUY\n"
    "Size: 10% of portfolio\n"
    "Entry: $32.75\n"
    "Target: $33.50\n"
    "Stop: $29.60 (10% below entry)\n"
    "R:R: 2.5:1\n"
    "Entering near the $33.5 resistance leaves minimal immediate upside."
)

# 100/94/113 implies ~2.2:1; a narrated 2:1 is within the 0.3 tolerance —
# same coherent fixture shape `test_room_runner.py` uses for its "no flag"
# case.
_COHERENT_TRIPLE_REPLY = "Entry: $100\nTarget: $113\nStop: $94\nSize: 3%\nR:R: 2:1"

_NO_TRIPLE_REPLY = "SCHD's dividend yield is attractive here and the sector is defensive."


class _FakeRunner:
    """Deterministic stand-in for `AgentRunner` — no real LLM, no network.
    `get_session` returns a fixed, valid session; `stream_one_on_one_message`
    yields the configured reply split into two chunks (proving the wiring
    buffers across chunk boundaries rather than only working on a
    single-chunk reply)."""

    def __init__(self, session: OneOnOneSession, reply: str):
        self._session = session
        self._reply = reply

    def get_session(self, session_id):
        return self._session if session_id == self._session.id else None

    async def stream_one_on_one_message(self, **_kwargs):
        mid = len(self._reply) // 2
        if mid:
            yield self._reply[:mid]
            yield self._reply[mid:]
        else:
            yield self._reply


def _session(mandate: Mandate, user_id) -> OneOnOneSession:
    return OneOnOneSession(
        id=uuid4(),
        agent_id=AgentId.TRADER,
        started_at=datetime.now(timezone.utc),
        mandate_used=mandate.model_dump(mode="json"),
        locale=mandate.locale,
        user_id=user_id,
    )


def _new_persisted_user():
    """A real, DB-persisted user + bearer id — `spend()` (called before
    `event_stream()` even opens) does `s.get(User, user_id)` and raises on a
    bare unpersisted `uuid4()` (the exact trap `test_def127_sse_framing_
    invariant.py`'s DEF205 comment already documents for this same route)."""
    from app.services.auth_service import AuthService
    persisted, _token, _ = AuthService().ensure_anonymous(device_user_id=None)
    return persisted.id


def _client_for(reply: str, mandate: Mandate) -> tuple[TestClient, str]:
    user_id = _new_persisted_user()
    session = _session(mandate, user_id)
    app = FastAPI()
    app.include_router(one_on_one_router)
    app.dependency_overrides[get_current_user] = lambda: _IdOnlyUser(user_id)
    app.dependency_overrides[get_agent_runner] = lambda: _FakeRunner(session, reply)
    return TestClient(app, raise_server_exceptions=False), str(session.id)


class _IdOnlyUser:
    def __init__(self, uid):
        self.id = uid


def _send(client: TestClient, session_id: str) -> str:
    r = client.post(
        "/v1/agents/one_on_one/message",
        json={"session_id": session_id, "user_message": "What's the trade on SCHD?"},
    )
    assert r.status_code == 200, r.text
    return r.text


@pytest.fixture(autouse=True)
def _reset_limiter():
    one_on_one_message_rate_limit.reset()
    yield
    one_on_one_message_rate_limit.reset()


@pytest.fixture(autouse=True)
def _market_data_off(monkeypatch):
    """Isolates the geometry-triple cases from live market data — these three
    assert the CHECK fires, not the reference-close plumbing (that has its
    own case below). `_verify_and_annotate_geometry` with `reference_close=
    None` degrades to its pre-DEF237 behaviour (still checks R:R coherence,
    skips the plausibility gate), matching the Room's own documented
    degradation."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "use_real_market_data", False)


# ── 1. Incoherent R:R triple gets annotated ──────────────────────────────


def test_incoherent_triple_is_annotated_on_the_1on1_path(base_mandate):
    client, session_id = _client_for(_INCOHERENT_TRIPLE_REPLY, base_mandate)
    wire = _send(client, session_id)

    assert "AMI verified" in wire
    assert "0.2:1" in wire, "the implied ratio must be the recomputed figure"
    assert "2.5:1" not in wire, "the wrong narrated ratio must not survive"
    # Exact match against the Room's own already-proven annotation for this
    # exact input/size_pct (`test_room_runner.py:803`) — `base_mandate` has
    # `risk_score=3`, which resolves to the same 3.0% single-name cap the
    # Room test passes explicitly, so the two must produce byte-identical
    # drawdown-contribution text.
    assert "drawdown contribution ≈ 0.29 pt at the mandate's 3.0% single-name cap" in wire


def test_incoherent_triple_is_also_annotated_in_the_journal_record(base_mandate):
    """The Journal write (`finally` block) must persist the SAME text the
    user was shown, not the raw pre-annotation reply — a diverging Journal
    entry would be a silent second copy of the exact defect this finding
    exists to close."""
    from app.services.journal_store import get_journal_store
    from app.services.auth_service import AuthService

    persisted, token, _ = AuthService().ensure_anonymous(device_user_id=None)
    session = _session(base_mandate, persisted.id)
    app = FastAPI()
    app.include_router(one_on_one_router)
    app.dependency_overrides[get_agent_runner] = lambda: _FakeRunner(
        session, _INCOHERENT_TRIPLE_REPLY
    )
    client = TestClient(app, raise_server_exceptions=False)

    r = client.post(
        "/v1/agents/one_on_one/message",
        json={"session_id": str(session.id), "user_message": "What's the trade on SCHD?"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text

    entries = get_journal_store().list_for_user(persisted.id)[0]
    assert entries, "no journal entry was written"
    payload = entries[0].payload
    assert "AMI verified" in payload["assistant_reply"]
    assert "2.5:1" not in payload["assistant_reply"]


# ── 2. Clean/coherent reply passes untouched ─────────────────────────────


def test_coherent_triple_passes_through_unannotated(base_mandate):
    client, session_id = _client_for(_COHERENT_TRIPLE_REPLY, base_mandate)
    wire = _send(client, session_id)

    # A coherent narration still gets its ratio rewritten IN PLACE to AMI's
    # computed figure (100/94/113 implies 2.2:1, not the narrated 2:1) — the
    # `_annotate_rr_against_levels` contract is "no CORRECTION NOTE on a
    # within-tolerance ratio", never "the text is untouched" (that's F5's own
    # `test_room_runner.py::test_def095_verify_and_annotate_geometry_unit`
    # `sig2 is None` case, which is exactly this shape). "Untouched" is
    # reserved for the no-triple gate (next section).
    assert "AMI verified" not in wire, "a coherent trade must not get correction noise"
    assert "2.2:1" in wire and "R:R: 2:1" not in wire
    assert "Entry: $100" in wire and "Target: $113" in wire and "Stop: $94" in wire


# ── 3. No full triple → the gate → untouched ─────────────────────────────


def test_reply_with_no_triple_is_untouched(base_mandate):
    client, session_id = _client_for(_NO_TRIPLE_REPLY, base_mandate)
    wire = _send(client, session_id)

    assert "AMI verified" not in wire
    assert _NO_TRIPLE_REPLY in wire


def test_concierge_reply_with_no_triple_is_also_untouched(base_mandate):
    """The wiring applies to every agent uniformly (no agent-id carve-out in
    `one_on_one.py`) — Concierge's ordinary conversational replies simply
    never match the triple gate, same as any Room debator that doesn't
    narrate one. Proves the universal call site doesn't misfire on the one
    agent whose 1-on-1 path takes a structurally different branch in
    `agent_runner.py` (`_stream_concierge`)."""
    user_id = _new_persisted_user()
    session = _session(base_mandate, user_id)
    session.agent_id = AgentId.CONCIERGE
    app = FastAPI()
    app.include_router(one_on_one_router)
    app.dependency_overrides[get_current_user] = lambda: _IdOnlyUser(user_id)
    app.dependency_overrides[get_agent_runner] = lambda: _FakeRunner(
        session, "Ask me about a lesson or an agent and I'll point you there."
    )
    client = TestClient(app, raise_server_exceptions=False)
    r = client.post(
        "/v1/agents/one_on_one/message",
        json={"session_id": str(session.id), "user_message": "hi"},
    )
    assert r.status_code == 200, r.text
    assert "AMI verified" not in r.text


# ── 4. reference_close plumbing: sourced from compute_technicals ────────


def test_reference_close_is_sourced_from_compute_technicals_when_live(base_mandate, monkeypatch):
    """Wiring-specific: proves `reference_close` is not permanently `None` —
    it is sourced from `compute_technicals(ticker)` when
    `settings.use_real_market_data` is on and a ticker resolves from the
    user's message, the same series `room_runner._reference_close` reads
    (`Technicals.price` = last close of the fetched OHLCV window). A level
    triple priced at ~6.7x a $75 close exceeds `_MAX_PLAUSIBLE_LEVEL_RATIO`
    (5.0) and must now be REFUSED entirely rather than annotated with a
    computed ratio — the DEF237 plausibility gate, proven reachable from
    this surface, which is unreachable with market data off (next test)."""
    from app.core.config import settings
    from app.api import one_on_one as one_on_one_mod
    from app.services.technicals import Technicals

    monkeypatch.setattr(settings, "use_real_market_data", True)
    # Patched where it's USED (`one_on_one.py` did `from app.services.
    # technicals import compute_technicals`, binding its own name at import
    # time), not where it's defined — patching `technicals_mod.
    # compute_technicals` leaves that already-bound name untouched and the
    # real function (network/provider call) runs instead.
    monkeypatch.setattr(
        one_on_one_mod, "compute_technicals",
        lambda t: Technicals(
            rsi=50, rsi_tone="neutral", trend="consolidating",
            volume_tone="in-line with 20-day average", support=70.0, breakout=80.0,
            price=75.0, sma_short=75.0, sma_long=75.0, volume_ratio=1.0,
        ),
    )

    # 500/75 = 6.67x the $75 close — over the 5.0 plausibility ratio.
    implausible_reply = (
        "Entry: $500.00\nTarget: $560.00\nStop: $450.00\nR:R: 2.5:1\n"
        "SCHD looks attractive here."
    )
    client, session_id = _client_for(implausible_reply, base_mandate)
    wire = _send(client, session_id)

    assert "AMI verified" not in wire, "an implausible level must be REFUSED, not computed"
    assert "2.5:1" not in wire, "the narrated ratio must not survive verbatim"
    assert "unverifiable" in wire, "the strike must say so, not go silent"


def test_reference_close_stays_none_when_market_data_disabled(base_mandate):
    """The `_market_data_off` fixture's own guarantee, pinned explicitly: the
    SAME level triple that the previous test refuses as implausible against
    a live $75 close is, with market data off, judged on R:R coherence
    alone (no reference close to compare against — `_reference_close`'s
    documented pre-DEF237 degradation). 500/450/560 implies ~1.2:1 against a
    narrated 2.5:1 — still incoherent, so it IS annotated, just via the
    coherence path rather than the plausibility refusal."""
    same_levels_market_data_off = (
        "Entry: $500.00\nTarget: $560.00\nStop: $450.00\nR:R: 2.5:1\n"
        "SCHD looks attractive here."
    )
    client, session_id = _client_for(same_levels_market_data_off, base_mandate)
    wire = _send(client, session_id)

    assert "could not verify" not in wire and "unverifiable" not in wire, (
        "with no reference close, a self-consistent-enough triple must be "
        "computed, never refused as implausible"
    )
    assert "AMI verified" in wire
    assert "1.2:1" in wire
    assert "2.5:1" not in wire
