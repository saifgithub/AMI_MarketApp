"""UAT area: Convene the Room (CR263, cases/room.yaml).

Goals under test, not just statuses: a funded run streams to a verdict that
names real desks and a decision; credits are debited by the documented price;
an unfunded run is refused with NO run and NO verdict (the DEF059 class — an
LLM/credit failure must never yield a confident APPROVE); and nobody can read,
retry or replay another user's run.

LLM budget: three Room streams for the whole file (floor_pass, trader,
floor_manager), each shared through a module-scoped fixture; every other case
is contract-only.
"""

from __future__ import annotations

import json
import time
import uuid

import httpx
import pytest

from client import new_client

KNOWN_EVENTS = {
    "started", "live_data_notice", "phase", "agent_token", "agent_done",
    "agent_withheld", "verdict", "done", "error",
}
REAL_AGENTS = {
    "fundamentals_analyst", "market_analyst", "news_analyst", "social_media_analyst",
    "bull_researcher", "bear_researcher", "research_manager", "trader",
    "aggressive_debator", "conservative_debator", "neutral_debator",
    "portfolio_manager", "risk_officer",
}
VERDICT_ACTIONS = {"APPROVE", "REJECT", "MODIFY", "PASS", "NO_VERDICT"}
BASIC_COST, PREMIUM_COST, SURCHARGE = 8, 25, 2
STREAM_TIMEOUT = httpx.Timeout(30.0, read=900.0)

_stream_posts: list[float] = []


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


def _pace() -> None:
    """The stream route allows 5/min per IP (shared with parallel suites)."""
    now = time.time()
    while _stream_posts and now - _stream_posts[0] > 62:
        _stream_posts.pop(0)
    if len(_stream_posts) >= 4:
        time.sleep(max(0.0, 62 - (now - _stream_posts[0])))
    _stream_posts.append(time.time())


def open_stream(user, path: str, body: dict | None, *, user_id: str | None = None):
    """POST an SSE route; returns (status, headers, events, json_body)."""
    for attempt in range(5):
        _pace()
        with new_client(user.token, timeout=STREAM_TIMEOUT) as c:
            with c.stream("POST", path, json=body) as r:
                if r.status_code == 429:
                    time.sleep(15 * (attempt + 1))
                    continue
                if r.status_code != 200:
                    r.read()
                    try:
                        payload = r.json()
                    except ValueError:
                        payload = None
                    return r.status_code, dict(r.headers), [], payload
                events = parse_sse(r.iter_lines())
                return r.status_code, dict(r.headers), events, None
    raise AssertionError("room stream rate-limited 5 times in a row")


def stream_room(user, ticker: str, *, user_id: str | None = None):
    return open_stream(
        user, "/v1/room/stream", {"user_id": user_id or user.id, "ticker": ticker},
    )


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
    """A user on `plan` holding exactly `balance` credits.

    The plan change re-grants the allowance lazily on the first balance read,
    so read once (GET mandate) BEFORE pinning the balance or the first spend
    would reset it.
    """
    u = _user(seed, plan)
    assert u.get(f"/v1/mandate/{u.id}").status_code == 200
    seed.add_credits(u, -100_000)
    if balance:
        seed.add_credits(u, balance)
    assert seed.detail(u)["credit_balance"] == balance
    return u


def balance(seed, u) -> int:
    return seed.detail(u)["credit_balance"]


def events_of(events, name):
    return [json.loads(d) if name != "error" else d for n, d in events if n == name]


def room_runs(u) -> list[dict]:
    r = u.get(f"/v1/room/user/{u.id}")
    assert r.status_code == 200
    return r.json()


class RoomResult:
    def __init__(self, user, plan, start_balance, status, headers, events):
        self.user, self.plan, self.start_balance = user, plan, start_balance
        self.status, self.headers, self.events = status, headers, events
        self.run_id = headers.get("x-room-run-id")
        done = events_of(events, "done")
        self.done = done[-1] if done else None
        verdicts = events_of(events, "verdict")
        self.verdict = verdicts[0] if verdicts else None
        self.verdict_count = len(verdicts)


def _run_room(seed, plan, ticker, balance_start):
    u = fund(seed, plan, balance_start)
    status, headers, events, _ = stream_room(u, ticker)
    return RoomResult(u, plan, balance_start, status, headers, events)


@pytest.fixture(scope="module")
def floor_run(seed):
    """Floor Pass holding exactly one Basic Room (8): too little for the
    live-data surcharge, so the debit must be exactly the base price."""
    return _run_room(seed, "floor_pass", "AAPL", BASIC_COST)


@pytest.fixture(scope="module")
def trader_run(seed):
    return _run_room(seed, "trader", "MSFT", 150)


@pytest.fixture(scope="module")
def manager_run(seed):
    return _run_room(seed, "floor_manager", "KO", 500)


@pytest.fixture(scope="module")
def stranger(seed):
    return _user(seed, "trader")


def get_run(r: RoomResult) -> dict:
    resp = r.user.get(f"/v1/room/{r.run_id}")
    assert resp.status_code == 200, resp.text
    return resp.json()


def assert_clean_stream(r: RoomResult):
    assert r.status == 200
    assert r.run_id, "no X-Room-Run-Id header"
    names = [n for n, _ in r.events]
    assert set(names) <= KNOWN_EVENTS, f"unknown/forged SSE event kinds: {set(names) - KNOWN_EVENTS}"
    assert "error" not in names, f"stream carried an error event: {events_of(r.events, 'error')}"
    assert names[0] == "started" and names[-1] == "done"
    assert r.verdict_count == 1, "exactly one verdict event expected"
    assert names.index("verdict") < names.index("done")


@pytest.mark.uat("UAT-ROOM-001")
@pytest.mark.llm
def test_funded_room_streams_to_a_real_verdict(floor_run):
    assert_clean_stream(floor_run)
    spoken = {e["agent_id"] for e in events_of(floor_run.events, "agent_token")}
    done_agents = {e["agent_id"] for e in events_of(floor_run.events, "agent_done")}
    assert spoken <= REAL_AGENTS and spoken, f"unknown speakers: {spoken - REAL_AGENTS}"
    assert "portfolio_manager" in done_agents, "the CIO never finished speaking"
    assert len(done_agents & REAL_AGENTS) >= 8, f"too few desks contributed: {sorted(done_agents)}"
    v = floor_run.verdict
    assert v["action"] in VERDICT_ACTIONS
    assert v["reason"].strip()

    run = get_run(floor_run)
    assert run["status"] == "completed"
    assert run["ticker"] == "AAPL"
    assert run["verdict"]["action"] == v["action"]
    assert run["verdict"]["reason"] == v["reason"]
    persisted = {m["agent_id"] for m in run["transcript"]}
    assert persisted <= REAL_AGENTS and "portfolio_manager" in persisted
    assert all(m["content"].strip() for m in run["transcript"]), "a desk in the transcript said nothing"


@pytest.mark.uat("UAT-ROOM-002")
@pytest.mark.llm
def test_floor_pass_room_debits_exactly_the_basic_price(seed, floor_run):
    assert_clean_stream(floor_run)
    done = floor_run.done
    after = balance(seed, floor_run.user)
    if done["refunded"]:
        assert after == BASIC_COST, "refunded run must restore the full price"
    else:
        assert done["credit_cost"] == BASIC_COST
        assert after == floor_run.start_balance - BASIC_COST == 0
    notice = events_of(floor_run.events, "live_data_notice")
    assert notice and notice[0]["surcharge_charged"] == 0, (
        "balance (8) could not cover a live-data surcharge — none may be charged"
    )
    assert get_run(floor_run)["credit_cost"] == BASIC_COST


@pytest.mark.uat("UAT-ROOM-003")
def test_room_price_per_plan_is_documented(seed):
    prices = {}
    for plan in ("floor_pass", "trader", "floor_manager"):
        u = _user(seed, plan)
        m = u.get(f"/v1/mandate/{u.id}").json()
        assert m["plan"] == plan
        prices[plan] = m["room_cost"]
    assert prices == {"floor_pass": BASIC_COST, "trader": BASIC_COST, "floor_manager": PREMIUM_COST}


@pytest.mark.uat("UAT-ROOM-004")
@pytest.mark.llm
def test_floor_manager_room_debits_the_premium_price(seed, manager_run):
    assert_clean_stream(manager_run)
    assert manager_run.done["refunded"] is False
    cost = manager_run.done["credit_cost"]
    assert cost in {PREMIUM_COST + SURCHARGE * n for n in (0, 1, 2)}, f"unexpected premium price {cost}"
    assert balance(seed, manager_run.user) == manager_run.start_balance - cost


@pytest.mark.uat("UAT-ROOM-005")
def test_floor_pass_out_of_credits_is_refused_with_no_run_and_no_verdict(seed):
    u = fund(seed, "floor_pass", 0)
    status, headers, events, body = stream_room(u, "AAPL")
    assert status == 402, f"unfunded Room must be refused, got {status}"
    assert events == [], "a refused Room must not stream anything (no fake verdict)"
    detail = body["detail"]
    assert detail["code"] == "insufficient_credits"
    assert detail["cost"] == BASIC_COST and detail["plan"] == "floor_pass"
    assert "x-room-run-id" not in headers
    assert room_runs(u) == [], "a refused Room must not leave a run row behind"
    if detail.get("funnel"):
        assert detail["cooldown_until"] and detail["retry_after_seconds"] >= 0
        # Soft wall: still locked out while the cooldown runs, still no run.
        status2, _, events2, body2 = stream_room(u, "AAPL")
        assert status2 == 402 and events2 == []
        assert body2["detail"]["cooldown_until"]
        assert room_runs(u) == []


@pytest.mark.uat("UAT-ROOM-006")
def test_paid_plan_out_of_credits_hits_the_hard_wall(seed):
    u = fund(seed, "trader", 5)
    status, _, events, body = stream_room(u, "AAPL")
    assert status == 402 and events == []
    detail = body["detail"]
    assert detail["code"] == "insufficient_credits"
    assert detail["balance"] == 5 and detail["cost"] == BASIC_COST and detail["plan"] == "trader"
    assert "funnel" not in detail, "the Floor Pass soft wall must not apply to a paid plan"
    assert detail["resets_at"]
    assert balance(seed, u) == 5, "a refused Room must not touch the balance"
    assert room_runs(u) == []


@pytest.mark.uat("UAT-ROOM-007")
@pytest.mark.llm
def test_nobody_else_can_read_retry_or_replay_a_run(floor_run, stranger):
    run_id = floor_run.run_id
    assert stranger.get(f"/v1/room/{run_id}").status_code == 403
    assert stranger.get(f"/v1/room/user/{floor_run.user.id}").status_code == 403
    r = stranger.post(f"/v1/room/runs/{run_id}/cio-retry")
    assert r.status_code == 403
    status, _, events, body = stream_room(stranger, "AAPL", user_id=floor_run.user.id)
    assert status == 403 and events == []
    own = stranger.get(f"/v1/room/user/{stranger.id}")
    assert own.status_code == 200 and all(x["id"] != run_id for x in own.json())
    # The owner still can.
    assert floor_run.user.get(f"/v1/room/{run_id}").status_code == 200


@pytest.mark.uat("UAT-ROOM-008")
def test_room_request_validation_and_auth_never_charge(seed, api):
    u = fund(seed, "trader", 150)
    unknown = str(uuid.uuid4())
    assert u.get(f"/v1/room/{unknown}").status_code == 404
    assert u.post(f"/v1/room/runs/{unknown}/cio-retry").status_code == 404
    assert u.get("/v1/room/not-a-uuid").status_code == 422

    status, _, events, body = stream_room(u, "ZZZZZZ")
    assert status == 422 and events == [], "a nonexistent ticker must be refused before any spend"
    status, _, events, _ = stream_room(u, "   ")
    assert status in (400, 422) and events == []
    status, _, events, _ = stream_room(u, "AAPL", user_id=str(uuid.uuid4()))
    assert status == 403 and events == [], "body user_id must match the bearer"

    assert balance(seed, u) == 150, "refused requests must not charge"
    assert room_runs(u) == []

    assert api.get(f"/v1/room/{unknown}").status_code == 401
    assert api.get(f"/v1/room/user/{u.id}").status_code == 401
    assert api.post("/v1/room/stream", json={"user_id": u.id, "ticker": "AAPL"}).status_code == 401
    assert api.post(f"/v1/room/runs/{unknown}/cio-retry").status_code == 401


@pytest.mark.uat("UAT-ROOM-009")
@pytest.mark.llm
def test_cio_retry_contract(seed, trader_run):
    assert_clean_stream(trader_run)
    run = get_run(trader_run)
    before_balance = balance(seed, trader_run.user)
    offered = run["cio_retry_available"]
    assert offered == trader_run.done["cio_retry_available"]
    r_events = open_retry(trader_run)
    names = [n for n, _ in r_events]
    done = events_of(r_events, "done")[-1]
    assert names[-1] == "done"
    assert balance(seed, trader_run.user) == before_balance, "the CIO retry must be free"
    if not offered:
        assert "error" in names and "verdict" not in names, (
            "a run with a reasoned verdict must decline the retry loudly, not re-roll it"
        )
        assert done["cio_retry_available"] is False
        assert get_run(trader_run)["verdict"]["action"] == run["verdict"]["action"]
        assert get_run(trader_run)["verdict"]["reason"] == run["verdict"]["reason"]
    else:
        assert run["verdict"]["overridden_from_llm"] is True
        assert "verdict" in names or "error" in names


def open_retry(r: RoomResult):
    with new_client(r.user.token, timeout=STREAM_TIMEOUT) as c:
        with c.stream("POST", f"/v1/room/runs/{r.run_id}/cio-retry") as resp:
            assert resp.status_code == 200, resp.read()
            return parse_sse(resp.iter_lines())


@pytest.mark.uat("UAT-ROOM-010")
@pytest.mark.llm
def test_no_confident_approval_without_a_real_cio(seed, floor_run, trader_run, manager_run):
    """DEF059 class: an outage must degrade to a refunded PASS, never an APPROVE
    with canned reasoning. Checked on every completed run this file produced."""
    for r in (floor_run, trader_run, manager_run):
        assert_clean_stream(r)
        run = get_run(r)
        v = run["verdict"]
        scripted = v.get("scripted_agents") or []
        if v["action"] == "APPROVE":
            assert "portfolio_manager" not in scripted, "APPROVE issued by a scripted CIO"
            assert "trader" not in scripted, "APPROVE built on a scripted Execution Desk proposal"
            assert v["reason"].strip()
        outage = bool(v.get("overridden_from_llm")) and (
            "unavailable" in v["reason"].lower() or v["action"] == "NO_VERDICT"
        )
        if outage:
            # DEF059 / DEF432: too few live desks => no call, and the price comes back.
            assert v["action"] in ("PASS", "NO_VERDICT"), "an outage verdict must never be a trade call"
            assert run["refunded"] is True
            assert balance(seed, r.user) == r.start_balance, "outage run must be refunded in full"
            assert (v.get("scripted_turns") or 0) > 0 or "unavailable" in v["reason"].lower()
        assert run["status"] == "completed"


@pytest.mark.uat("UAT-ROOM-011")
@pytest.mark.llm
def test_new_accounts_get_the_full_analyst_roster(floor_run, trader_run):
    for r in (floor_run, trader_run):
        assert not events_of(r.events, "agent_withheld"), "a day-0 account must not have analysts withheld"
        assert r.verdict["opinions_not_included"] == []
        analysts = {e["agent_id"] for e in events_of(r.events, "agent_done")}
        assert {"fundamentals_analyst", "market_analyst"} <= analysts


@pytest.mark.uat("UAT-ROOM-012")
@pytest.mark.llm
def test_reconnecting_to_a_finished_run_replays_it_for_free(seed, floor_run):
    """The floor-pass user holds 0 credits now: if dedup failed this would 402."""
    assert_clean_stream(floor_run)
    status, headers, events, body = stream_room(floor_run.user, "AAPL")
    assert status == 200, body
    assert headers["x-room-run-id"] == floor_run.run_id
    assert headers.get("x-room-cached") == "true"
    replay = events_of(events, "verdict")
    assert len(replay) == 1 and replay[0]["action"] == floor_run.verdict["action"]
    assert [n for n, _ in events][-1] == "done"
    assert len(room_runs(floor_run.user)) == 1
    refunded = floor_run.done["refunded"]
    assert balance(seed, floor_run.user) == (BASIC_COST if refunded else 0)


@pytest.mark.uat("UAT-ROOM-013")
@pytest.mark.llm
def test_live_data_surcharge_is_disclosed_and_matches_the_debit(seed, trader_run):
    assert_clean_stream(trader_run)
    notice = events_of(trader_run.events, "live_data_notice")
    assert notice, "no live_data_notice — the surcharge must be disclosed structurally"
    charged = notice[0]["surcharge_charged"]
    assert charged in (0, SURCHARGE, 2 * SURCHARGE)
    assert trader_run.done["credit_cost"] == BASIC_COST + charged
    run = get_run(trader_run)
    assert run["credit_cost"] == BASIC_COST + charged
    if trader_run.done["refunded"]:
        # Outage-shaped run (DEF432): the whole charge, surcharge included, comes back.
        assert run["refunded"] is True and run["verdict"]["action"] in ("PASS", "NO_VERDICT")
        assert balance(seed, trader_run.user) == 150
    else:
        assert balance(seed, trader_run.user) == 150 - (BASIC_COST + charged)
