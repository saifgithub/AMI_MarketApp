"""CR219 R58 — seeded RESEARCHERS debate order (`05_further_improvements.md`
§12).

Bull always speaks before Bear today (`PHASES` — RESEARCHERS phase);
`05_further_improvements.md` §12 names this a standing, unmeasured source of
decision variance: LLM judges anchor on order, and the Research Manager reads
both sides. This CR ships the SEEDABLE mechanism only — `room_debate_order_seeded`
defaults to False, and the default does not change here (WP13's replay measures
whether it should; Saiful decides).

Four things this file pins:

  1. `_researchers_order` is a pure, deterministic function of the run id —
     same id -> same order, forever (a replay of a stored run must reorder
     identically to the original, since the transcript's turn order IS the
     record).
  2. Distribution sanity — both orders occur across ids, roughly balanced
     (not a coin that always lands the same way).
  3. Flag OFF (the default) -> the real runner produces EXACTLY today's fixed
     Bull-then-Bear order, regardless of run id. Flag ON -> the real runner's
     emitted order follows `_researchers_order(run_id)` for that id.
  4. `PHASES` itself is never mutated (CR077 pins it as a frozen, singular
     source of truth for the parallel guard) — proven by identity, not just by
     value equality.

`test_cr077_phase_parallelism.py` is untouched by this CR and must stay green
on its own (verified separately, not re-asserted here — duplicating a guard
across files is how two versions of it silently drift).
"""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

from app.schemas import AgentId, agent_display_name
from app.services import room_runner as rr_mod
from app.services.coach_engine import hydrate_coach_mandate
from app.services.room_runner import PHASES, RoomRunner, _researchers_order

_RESEARCHER_IDS = (AgentId.BULL_RESEARCHER, AgentId.BEAR_RESEARCHER)

_REPLIES = {
    "fundamentals_analyst": "FA: P/E reasonable, growth steady.",
    "market_analyst": "MA: trend consolidating, RSI 58.",
    "news_analyst": "NA: recent catalyst noted.",
    "social_media_analyst": "SMA: retail sentiment mixed.",
    "bull_researcher": "Bull: thesis defended, 4% size.",
    "bear_researcher": "Bear: compression risk capped at 2%.",
    "research_manager": "RM: lean constructive, 3% start.",
    "trader": "Trader: BUY 3% at $150, stop $141, target $172.",
    "aggressive_debator": "Push to 4.5%.",
    "conservative_debator": "Cap at 2%.",
    "neutral_debator": "Hold at 3%.",
    "portfolio_manager": (
        '{"action": "APPROVE", "size_pct": 3.0, "entry": 150, "stop": 141, '
        '"target": 172, "horizon_days": 42, '
        '"narration": "PM: APPROVE; synthesis defended; mandate clears."}'
    ),
}


def _agent_key_from_prompt(system_prompt: str) -> str:
    low = system_prompt.lower()
    for k in _REPLIES:
        if f"speak as the {agent_display_name(k).lower()}" in low:
            return k
    return "portfolio_manager" if "single json object" in low else "default"


class _OrderProbeGateway:
    """Answers every desk and records, per call, which agent it matched — the
    direct read of what order the RESEARCHERS phase actually served, keyed off
    which system prompt asked, independent of the events the runner emits."""

    def __init__(self):
        self.call_order: list[str] = []

    def has_real_provider(self) -> bool:
        return True

    async def stream_chat(self, *, system_prompt, messages, model_tier,
                          locale="en", max_tokens=1024, **_audit):
        key = _agent_key_from_prompt(system_prompt)
        self.call_order.append(key)
        yield _REPLIES.get(key, "AMI agent live reply.")


def _run(runner, **kw) -> list:
    async def go():
        return [ev async for ev in runner.run(**kw)]
    return asyncio.run(go())


def _researcher_call_order(gw: _OrderProbeGateway) -> list[str]:
    return [c for c in gw.call_order if c in {"bull_researcher", "bear_researcher"}]


def _researcher_done_order(events: list) -> list[AgentId]:
    return [
        e.agent_id for e in events
        if e.kind == "agent_done" and e.agent_id in _RESEARCHER_IDS
    ]


# ── 1. Determinism + distribution sanity, at the pure-function level ────────


def test_researchers_order_is_deterministic_for_the_same_run_id():
    """Same run id -> same order, called twice. A stored run replayed later
    must reorder identically to how it was originally served."""
    run_id = uuid4()
    first = _researchers_order(run_id)
    second = _researchers_order(run_id)
    assert first == second
    assert set(first) == set(_RESEARCHER_IDS)


def test_researchers_order_both_orders_occur_and_are_the_only_two_shapes():
    """Every returned order is one of exactly the two valid permutations, and
    across enough distinct ids both are actually produced — not a function
    that always returns the same permutation regardless of input."""
    bull_first = (AgentId.BULL_RESEARCHER, AgentId.BEAR_RESEARCHER)
    bear_first = (AgentId.BEAR_RESEARCHER, AgentId.BULL_RESEARCHER)

    seen = {_researchers_order(uuid4()) for _ in range(200)}
    assert seen <= {bull_first, bear_first}
    assert seen == {bull_first, bear_first}, (
        "200 random run ids produced only one order — the function is not "
        "actually keyed on the id, or the low bit it reads is not ~50/50"
    )


def test_researchers_order_distribution_is_roughly_balanced():
    """~50/50 across runs (the WP's acceptance wording), checked over a large
    enough sample that a badly-skewed bit (e.g. accidentally keying on a
    UUID field that is not uniformly random) would fail this."""
    n = 2000
    bull_first_count = sum(
        1 for _ in range(n)
        if _researchers_order(uuid4())[0] is AgentId.BULL_RESEARCHER
    )
    frac = bull_first_count / n
    assert 0.40 < frac < 0.60, f"Bull-first fraction {frac:.3f} over n={n} is not ~50/50"


def test_researchers_order_known_low_bit_examples():
    """Pin the actual rule (`run_id.int % 2`) against fixed UUIDs so the
    function's behaviour is legible from the test file alone, not just from
    its docstring."""
    even_low_bit = UUID(int=0)
    odd_low_bit = UUID(int=1)
    assert _researchers_order(even_low_bit) == (
        AgentId.BULL_RESEARCHER, AgentId.BEAR_RESEARCHER
    )
    assert _researchers_order(odd_low_bit) == (
        AgentId.BEAR_RESEARCHER, AgentId.BULL_RESEARCHER
    )


# ── 2. `PHASES` is read, never mutated ───────────────────────────────────────


def test_phases_table_is_untouched_by_this_feature(monkeypatch):
    """CR077 pins `PHASES` as the single frozen source of truth the parallel
    guard walks. This feature reorders at ITERATION time — `PHASES` itself,
    and specifically its RESEARCHERS entry, must be byte-identical before and
    after exercising the seeded path."""
    before = PHASES
    before_researchers = next(p for p in PHASES if p.label == "RESEARCHERS")
    assert before_researchers.agents == (
        AgentId.BULL_RESEARCHER, AgentId.BEAR_RESEARCHER
    )

    monkeypatch.setattr(rr_mod.settings, "room_debate_order_seeded", True)
    gw = _OrderProbeGateway()
    runner = RoomRunner(llm=gw)  # type: ignore[arg-type]
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
    _run(
        runner, user_id=uuid4(), ticker="AAPL", mandate=mandate,
        run_id=uuid4(), char_delay_min=0.0, char_delay_max=0.0,
    )

    # Identity, not just equality: nothing replaced the module-level tuple.
    assert PHASES is before
    after_researchers = next(p for p in PHASES if p.label == "RESEARCHERS")
    assert after_researchers is before_researchers
    assert after_researchers.agents == (
        AgentId.BULL_RESEARCHER, AgentId.BEAR_RESEARCHER
    )


# ── 3. End-to-end: flag OFF keeps today's order; flag ON follows the seed ──


def test_flag_off_researchers_always_bull_then_bear_regardless_of_run_id():
    """The default (False): the real runner's RESEARCHERS phase is exactly
    today's fixed order for every run id tried, including ids whose seeded
    order (were the flag on) would be Bear-first."""
    from app.core.config import settings as real_settings
    assert real_settings.room_debate_order_seeded is False  # the shipped default

    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})

    # Try several ids, including at least one that seeds Bear-first, to prove
    # the flag — not the id — is what's gating the behaviour.
    tried_a_bear_first_id = False
    for _ in range(6):
        run_id = uuid4()
        if _researchers_order(run_id)[0] is AgentId.BEAR_RESEARCHER:
            tried_a_bear_first_id = True

        gw = _OrderProbeGateway()
        runner = RoomRunner(llm=gw)  # type: ignore[arg-type]
        events = _run(
            runner, user_id=uuid4(), ticker="AAPL", mandate=mandate,
            run_id=run_id, char_delay_min=0.0, char_delay_max=0.0,
        )

        assert _researcher_call_order(gw) == ["bull_researcher", "bear_researcher"]
        assert _researcher_done_order(events) == [
            AgentId.BULL_RESEARCHER, AgentId.BEAR_RESEARCHER
        ]

    assert tried_a_bear_first_id, (
        "none of the sampled run ids seeded Bear-first — widen the sample; "
        "this test only proves something if a Bear-first id was actually tried"
    )


def test_flag_on_researchers_order_follows_the_seed_bull_first_id(monkeypatch):
    run_id = UUID(int=0)  # pinned: _researchers_order -> Bull-first
    assert _researchers_order(run_id) == (
        AgentId.BULL_RESEARCHER, AgentId.BEAR_RESEARCHER
    )
    monkeypatch.setattr(rr_mod.settings, "room_debate_order_seeded", True)
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
    gw = _OrderProbeGateway()
    runner = RoomRunner(llm=gw)  # type: ignore[arg-type]
    events = _run(
        runner, user_id=uuid4(), ticker="AAPL", mandate=mandate,
        run_id=run_id, char_delay_min=0.0, char_delay_max=0.0,
    )

    assert _researcher_call_order(gw) == ["bull_researcher", "bear_researcher"]
    assert _researcher_done_order(events) == [
        AgentId.BULL_RESEARCHER, AgentId.BEAR_RESEARCHER
    ]


def test_flag_on_researchers_order_follows_the_seed_bear_first_id(monkeypatch):
    run_id = UUID(int=1)  # pinned: _researchers_order -> Bear-first
    assert _researchers_order(run_id) == (
        AgentId.BEAR_RESEARCHER, AgentId.BULL_RESEARCHER
    )
    monkeypatch.setattr(rr_mod.settings, "room_debate_order_seeded", True)
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
    gw = _OrderProbeGateway()
    runner = RoomRunner(llm=gw)  # type: ignore[arg-type]
    events = _run(
        runner, user_id=uuid4(), ticker="AAPL", mandate=mandate,
        run_id=run_id, char_delay_min=0.0, char_delay_max=0.0,
    )

    # The debate genuinely reordered — Bear is called and committed FIRST,
    # so the Bull turn that follows is the one built on the live transcript,
    # not merely a relabelling of who is "first" in a UI sense.
    assert _researcher_call_order(gw) == ["bear_researcher", "bull_researcher"]
    assert _researcher_done_order(events) == [
        AgentId.BEAR_RESEARCHER, AgentId.BULL_RESEARCHER
    ]


def test_flag_on_seeded_run_replayed_reorders_identically(monkeypatch):
    """The same run id, run twice with the flag on, produces the same served
    order both times — the replay guarantee the WP names explicitly."""
    run_id = uuid4()
    monkeypatch.setattr(rr_mod.settings, "room_debate_order_seeded", True)
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})

    orders = []
    for _ in range(2):
        gw = _OrderProbeGateway()
        runner = RoomRunner(llm=gw)  # type: ignore[arg-type]
        _run(
            runner, user_id=uuid4(), ticker="AAPL", mandate=mandate,
            run_id=run_id, char_delay_min=0.0, char_delay_max=0.0,
        )
        orders.append(_researcher_call_order(gw))

    assert orders[0] == orders[1]


# ── 4. The audit log line ────────────────────────────────────────────────────


def test_researchers_phase_logs_the_served_order(monkeypatch):
    """One structured log line names the order actually chosen, so a batch can
    be audited without parsing every transcript — fires whether or not the
    flag is on, since the served order (today's fixed order, flag off) is
    exactly as much "the order chosen" as a seeded one."""
    calls = []
    monkeypatch.setattr(
        rr_mod.logger, "info",
        lambda event, **kw: calls.append((event, kw)),
    )
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
    gw = _OrderProbeGateway()
    runner = RoomRunner(llm=gw)  # type: ignore[arg-type]
    run_id = uuid4()
    _run(
        runner, user_id=uuid4(), ticker="AAPL", mandate=mandate,
        run_id=run_id, char_delay_min=0.0, char_delay_max=0.0,
    )

    order_calls = [(e, kw) for e, kw in calls if e == "room_researchers_order"]
    assert len(order_calls) == 1, "expected exactly one order log line per run"
    _, kw = order_calls[0]
    assert kw["run_id"] == str(run_id)
    assert kw["seeded"] is False
    assert kw["order"] == ["bull_researcher", "bear_researcher"]
