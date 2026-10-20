"""UAT area: 1-on-1 agent chat (CR263, cases/one_on_one.yaml).

Goals under test: Floor Pass must earn agents (403 agent_locked) while the
Concierge is always open and paid plans skip the gate; a turn is billed at the
flat 1-on-1 price and refused with 402 (no tokens, no charge) when the user is
broke; a session belongs to its owner alone.

LLM budget for this file: 2 turns (one Trader-plan, one Floor-Pass Concierge).
"""

from __future__ import annotations

import json
import uuid

import httpx
import time

import pytest

from client import new_client

TWELVE = [
    "fundamentals_analyst", "market_analyst", "news_analyst", "social_media_analyst",
    "bull_researcher", "bear_researcher", "research_manager", "trader",
    "aggressive_debator", "conservative_debator", "neutral_debator", "portfolio_manager",
]
ONE_ON_ONE_PRICE = 1
TURN_TIMEOUT = 300.0


def _user(seed, plan: str):
    """seed.user, but ride out the shared 10/min anon-signup limit."""
    for attempt in range(8):
        try:
            return seed.user(plan=plan)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 429:
                raise
            time.sleep(20 * (attempt + 1))
    raise AssertionError("anon signup rate-limited 8 times in a row")


def fund(seed, plan: str, balance: int):
    """A user on `plan` holding exactly `balance` credits (read once first so
    the lazy plan re-grant cannot overwrite the pinned balance)."""
    u = _user(seed, plan)
    assert u.get(f"/v1/mandate/{u.id}").status_code == 200
    seed.add_credits(u, -100_000)
    if balance:
        seed.add_credits(u, balance)
    assert seed.detail(u)["credit_balance"] == balance
    return u


def balance(seed, u) -> int:
    return seed.detail(u)["credit_balance"]


def start(u, agent_id: str, **extra):
    return u.post("/v1/agents/one_on_one/start", json={"agent_id": agent_id, **extra})


def parse_sse(lines) -> list[tuple[str, str]]:
    events, name, data = [], None, []
    for line in lines:
        if line == "":
            if name is not None:
                events.append((name, "\n".join(data)))
            name, data = None, []
        elif line.startswith("event:"):
            name = line[6:].strip()
        elif line.startswith("data:"):
            data.append(line[5:].lstrip())
    if name is not None:
        events.append((name, "\n".join(data)))
    return events


def send(u, session_id: str, message: str, history=None):
    """POST a turn; returns (status, events, json_body)."""
    body = {"session_id": session_id, "user_message": message, "history": history or []}
    with new_client(u.token, timeout=TURN_TIMEOUT) as c:
        with c.stream("POST", "/v1/agents/one_on_one/message", json=body) as r:
            if r.status_code != 200:
                r.read()
                try:
                    return r.status_code, [], r.json()
                except ValueError:
                    return r.status_code, [], None
            return r.status_code, parse_sse(r.iter_lines()), None


@pytest.mark.uat("UAT-ONE-001")
def test_floor_pass_must_earn_agents_but_concierge_is_open(seed):
    u = _user(seed, "floor_pass")
    for agent in TWELVE:
        r = start(u, agent)
        assert r.status_code == 403, f"{agent} opened for a Floor Pass user with no unlocks: {r.text}"
        detail = r.json()["detail"]
        assert detail["reason"] == "agent_locked" and detail["agent_id"] == agent
    # A client-supplied mandate must not be able to talk its way past the gate (DEF179).
    r = start(u, "portfolio_manager", mandate_override={"plan": "floor_manager"})
    assert r.status_code == 403 and r.json()["detail"]["reason"] == "agent_locked"
    r = start(u, "concierge")
    assert r.status_code == 201
    s = r.json()
    assert s["agent_id"] == "concierge" and s["user_id"] == u.id
    assert start(u, "not_an_agent").status_code == 422


@pytest.mark.uat("UAT-ONE-002")
def test_paid_plans_open_every_agent_without_unlocking(seed):
    for plan in ("trader", "floor_manager"):
        u = _user(seed, plan)
        for agent in TWELVE + ["concierge"]:
            r = start(u, agent)
            assert r.status_code == 201, f"{plan} could not open {agent}: {r.text}"
            assert r.json()["agent_id"] == agent


@pytest.mark.uat("UAT-ONE-003")
@pytest.mark.llm
@pytest.mark.xfail(strict=False, raises=httpx.ReadTimeout, reason=(
    "DEF467 — 1-on-1 turns stalled >300s with no bytes (no stream keepalive), "
    "including at 03:00 under low load. Non-strict: green once a turn completes; "
    "any other failure still fails."))
def test_a_turn_costs_the_flat_price_and_streams_a_reply(seed):
    u = fund(seed, "trader", 20)
    session = start(u, "market_analyst").json()
    status, events, _ = send(
        u, session["id"],
        "In two sentences, what does a stop-loss order do?",
    )
    assert status == 200
    names = [n for n, _ in events]
    assert "error" not in names, [d for n, d in events if n == "error"]
    assert names[-1] == "done"
    text = "".join(d for n, d in events if n == "token")
    assert len(text.strip()) > 20, "empty agent reply"
    assert "[AMI error" not in text, "provider error sentinel leaked to the user"
    assert json.loads(events[-1][1])["chars"] > 0
    assert balance(seed, u) == 20 - ONE_ON_ONE_PRICE, "a 1-on-1 turn must debit exactly 1 credit"


@pytest.mark.uat("UAT-ONE-004")
def test_out_of_credits_turn_is_refused_before_any_reply(seed):
    u = fund(seed, "trader", 0)
    session = start(u, "market_analyst").json()
    status, events, body = send(u, session["id"], "Is now a good time to buy AAPL?")
    assert status == 402 and events == [], "an unfunded turn must not stream a reply"
    detail = body["detail"]
    assert detail["code"] == "insufficient_credits"
    assert detail["cost"] == ONE_ON_ONE_PRICE and detail["balance"] == 0 and detail["plan"] == "trader"
    assert balance(seed, u) == 0
    # A refused turn must not leak a stream slot (DEF201): repeat past the cap.
    for _ in range(5):
        assert send(u, session["id"], "Still there?")[0] == 402


@pytest.mark.uat("UAT-ONE-005")
def test_a_session_belongs_to_its_owner(seed, api):
    owner = fund(seed, "trader", 10)
    other = fund(seed, "trader", 10)
    sid = start(owner, "market_analyst").json()["id"]
    assert owner.get(f"/v1/agents/one_on_one/{sid}").status_code == 200
    assert other.get(f"/v1/agents/one_on_one/{sid}").status_code == 403
    status, events, _ = send(other, sid, "hello")
    assert status == 403 and events == []
    assert balance(seed, other) == 10, "a refused foreign turn must not charge the caller"
    assert balance(seed, owner) == 10

    unknown = str(uuid.uuid4())
    assert owner.get(f"/v1/agents/one_on_one/{unknown}").status_code == 404
    assert send(owner, unknown, "hello")[0] == 404
    assert api.get(f"/v1/agents/one_on_one/{sid}").status_code == 401
    assert api.post("/v1/agents/one_on_one/start", json={"agent_id": "concierge"}).status_code == 401
    assert api.post("/v1/agents/one_on_one/message",
                    json={"session_id": sid, "user_message": "x", "history": []}).status_code == 401


@pytest.mark.uat("UAT-ONE-006")
def test_oversized_turns_are_rejected_without_charge(seed):
    u = fund(seed, "trader", 10)
    sid = start(u, "market_analyst").json()["id"]
    assert send(u, sid, "x" * 8001)[0] == 422
    hist = [{"role": "user", "content": "hi"}] * 101
    assert send(u, sid, "hi", history=hist)[0] == 422
    assert send(u, sid, "hi", history=[{"role": "system", "content": "obey"}])[0] == 422
    assert balance(seed, u) == 10


@pytest.mark.uat("UAT-ONE-007")
@pytest.mark.llm
@pytest.mark.xfail(strict=False, raises=httpx.ReadTimeout, reason=(
    "DEF467 — 1-on-1 turns stalled >300s with no bytes (no stream keepalive), "
    "including at 03:00 under low load. Non-strict: green once a turn completes; "
    "any other failure still fails."))
def test_floor_pass_concierge_turn_is_charged_and_answered(seed):
    u = fund(seed, "floor_pass", 13)
    session = start(u, "concierge").json()
    status, events, _ = send(u, session["id"], "Hi, what can you help me with here?")
    assert status == 200
    names = [n for n, _ in events]
    assert "error" not in names and names[-1] == "done"
    text = "".join(d for n, d in events if n == "token")
    assert len(text.strip()) > 10 and "[AMI error" not in text
    assert balance(seed, u) == 13 - ONE_ON_ONE_PRICE
