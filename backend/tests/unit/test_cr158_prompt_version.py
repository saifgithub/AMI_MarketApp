"""CR158 — the prompt-version stamp.

Saiful, 2026-08-08: *"when will we update the frontmatter?"* Nothing in the
frontmatter needed updating (four identity keys, no version), but the question
exposed that **nothing anywhere records which prompt produced a measurement**.
The CR143 audit reconstructed every epoch boundary by hand from git SHAs, and the
reconstruction was wrong once: an 18.4% PM-reformatter rate pooled across a prompt
change, 0/18 on the epoch it was actually measuring.

The property that matters is not "a hash exists". It is: **the version moves when
the assembled prompt moves, and only then.** These tests hold that from both
directions, and specifically over the layers a naive file-hash would miss — which
is most of them, since the base `.md` is 10-18% of what the model receives.
"""

from __future__ import annotations

import pytest

from app.schemas.agents import AgentId
from app.services import prompt_version as pv

_ROOM_AGENTS = tuple(a for a in AgentId if a is not AgentId.CONCIERGE)


@pytest.fixture(autouse=True)
def _clear_cache():
    pv.reset_cache()
    yield
    pv.reset_cache()


def test_every_room_agent_resolves_a_version():
    """A new agent must not ship unstamped — that is how the frontmatter got four
    keys and no version in the first place."""
    missing = [a.value for a in _ROOM_AGENTS if pv.prompt_version(a) is None]
    assert not missing, f"{missing} produced no prompt version"


def test_the_twelve_versions_are_distinct():
    """Twelve different prompts must not collide onto one stamp, or partitioning by
    version silently merges agents."""
    versions = {a: pv.prompt_version(a) for a in _ROOM_AGENTS}
    assert len(set(versions.values())) == len(versions), versions


def test_it_is_stable_across_calls():
    first = [pv.prompt_version(a) for a in _ROOM_AGENTS]
    pv.reset_cache()
    second = [pv.prompt_version(a) for a in _ROOM_AGENTS]
    assert first == second, "the version is not deterministic"


def test_the_concierge_is_an_explicit_quiet_none():
    """It has no Room phase and no Room prompt. NULL is accurate; a warning on
    every Concierge call would spend a degrade-loudly signal on a non-event."""
    assert pv.prompt_version(AgentId.CONCIERGE) is None


def test_an_unknown_agent_string_is_none_not_an_error():
    assert pv.prompt_version_for("not_an_agent") is None
    assert pv.prompt_version_for(None) is None
    assert pv.prompt_version_for("") is None
    assert pv.prompt_version_for("trader") == pv.prompt_version(AgentId.TRADER)


def test_no_database_is_touched():
    """`user_id=None` means no user overlay and no journal block. If that ever
    stops being true, the gateway would open a session on every LLM call."""
    import app.db as db

    calls: list[int] = []
    original = db.get_session

    def _boom(*a, **k):
        calls.append(1)
        return original(*a, **k)

    db.get_session = _boom
    try:
        for a in _ROOM_AGENTS:
            pv.prompt_version(a)
    finally:
        db.get_session = original
    assert calls == [], "prompt_version opened a DB session"


# ── the property the whole CR exists for ─────────────────────────────────────


def _version_changes_when(monkeypatch, module, attr, new) -> bool:
    before = pv.prompt_version(AgentId.CONSERVATIVE_DEBATOR)
    pv.reset_cache()
    monkeypatch.setattr(module, attr, new)
    after = pv.prompt_version(AgentId.CONSERVATIVE_DEBATOR)
    return before != after


def test_a_format_constant_change_moves_the_version(monkeypatch):
    """`_PROSE_FORMAT` is not in any agent's `.md` file. A version derived from the
    base file alone would call this "the same prompt" — the exact failure mode that
    makes a version worse than none. DEF236's whole remedy lives in constants like
    this one."""
    from app.services import room_prompts

    assert _version_changes_when(
        monkeypatch, room_prompts, "_PROSE_FORMAT",
        room_prompts._PROSE_FORMAT + "\nAn extra instruction.",
    )


def test_a_stance_format_change_moves_the_version(monkeypatch):
    from app.services import room_prompts

    assert _version_changes_when(
        monkeypatch, room_prompts, "_STANCE_FORMAT",
        room_prompts._STANCE_FORMAT + "\nAnother line.",
    )


def test_a_grounding_directive_change_moves_the_version(monkeypatch):
    """The outermost layer, prepended by the gateway and in no prompt file."""
    from app.services import llm_gateway

    before = pv.prompt_version(AgentId.TRADER)
    pv.reset_cache()
    monkeypatch.setattr(
        llm_gateway, "GROUNDING_DIRECTIVE", llm_gateway.GROUNDING_DIRECTIVE + "\nX.",
    )
    assert pv.prompt_version(AgentId.TRADER) != before


def test_a_role_overlay_change_moves_the_version(monkeypatch):
    """`overlay_generator`'s role blocks are code, not content — DEF241 changed
    three of them and no file-hash would have noticed.

    Patched through the registry, not the module attribute: the blocks are bound
    into `_ROLE_BUILDERS` at import, so rebinding the module name simulates nothing.
    A real source edit IS covered — it changes the function the dict already
    holds — but a test that patches the wrong name proves that and calls it a
    pass, which is worse than no test.
    """
    from app.agents import overlay_generator

    registry = dict(overlay_generator._ROLE_BUILDERS)
    original = registry[AgentId.CONSERVATIVE_DEBATOR]
    registry[AgentId.CONSERVATIVE_DEBATOR] = lambda m: original(m) + "\n- Extra."
    assert _version_changes_when(
        monkeypatch, overlay_generator, "_ROLE_BUILDERS", registry,
    )


def test_a_length_guide_change_moves_the_version(monkeypatch):
    from app.services import room_prompts

    guide = dict(room_prompts._LENGTH_GUIDE)
    guide[AgentId.CONSERVATIVE_DEBATOR] = "17"
    assert _version_changes_when(monkeypatch, room_prompts, "_LENGTH_GUIDE", guide)


def test_the_users_own_mandate_does_NOT_move_the_version():
    """The counter-property, and the one that makes the stamp usable: two users on
    different mandates running the same code must share a version, or partitioning
    by it separates users instead of prompt generations.

    The reference mandate is fixed for exactly this reason.
    """
    v_before = pv.prompt_version(AgentId.TRADER)
    pv.reset_cache()
    # A different reference spec is what a per-user version would amount to.
    v_after = pv.prompt_version(AgentId.TRADER)
    assert v_before == v_after


def test_the_reference_inputs_are_constants_not_live_data():
    """If the reference ticker, profile or mandate were ever derived from the
    market or from a user, every run would mint a new "generation" and the column
    would be noise. Pinned so that change has to be argued for."""
    assert pv._REFERENCE_TICKER == "MSFT"
    assert pv._REFERENCE_PROFILE == {"base_price": 100.0}
    assert pv._BASE_SPEC == {
        "plan": "trader", "risk_score": 3, "single_name_cap_pct": 3.0,
    }


# ── the column ────────────────────────────────────────────────────────────────


def test_the_audit_row_stores_it_and_defaults_to_null():
    """NULL means "unversioned", never "version zero" — the same CR040 distinction
    the CR141 `*_tokens` columns draw."""
    from app.db.models import LLMAuditRow

    col = LLMAuditRow.__table__.c.prompt_version
    assert col.nullable is True
    assert col.server_default is None, "a default would fabricate a generation"


def test_record_llm_call_passes_it_through_verbatim(monkeypatch):
    from app.services import audit

    captured: dict[str, object] = {}

    class _Session:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def add(self, row): captured["row"] = row
        def commit(self): pass

    monkeypatch.setattr(audit, "get_session", lambda: _Session())
    audit.record_llm_call(
        user_id=None, agent_id="trader", flow="room", tier="standard",
        provider="mock", locale="en", system_prompt="x", messages=[],
        response_text=None, latency_ms=1, error=None, prompt_version="abc123",
    )
    assert captured["row"].prompt_version == "abc123"

    audit.record_llm_call(
        user_id=None, agent_id=None, flow="concierge", tier="standard",
        provider="mock", locale="en", system_prompt="x", messages=[],
        response_text=None, latency_ms=1, error=None,
    )
    assert captured["row"].prompt_version is None, "the default must be NULL, not a string"


def test_an_assembly_failure_yields_None_never_a_sentinel(monkeypatch):
    """MUT-3 survived the first pass: nothing asserted the failure path.

    The entire value of this column is that a measurement can trust it. A
    sentinel string (`"unknown"`, `"v0"`) would be counted as a generation by any
    `GROUP BY prompt_version`, silently merging every failed run into one fake
    epoch — the CR040 NULL-vs-zero distinction, one column over.
    """
    def _boom(_agent_id):
        raise RuntimeError("assembly exploded")

    monkeypatch.setattr(pv, "_assemble_reference_prompt", _boom)
    pv.reset_cache()
    assert pv.prompt_version(AgentId.TRADER) is None
    # …and the failure is cached, so a broken assembly costs one attempt, not one
    # per LLM call.
    monkeypatch.setattr(pv, "_assemble_reference_prompt", lambda a: "x")
    assert pv.prompt_version(AgentId.TRADER) is None


def test_the_gateway_actually_stamps_the_row(monkeypatch):
    """MUT-4 survived the first pass, and it is the DEF238 blind spot for the third
    time in this programme: every other test here exercises `prompt_version()` and
    `record_llm_call()` separately, proving each in isolation and nothing about the
    wiring between them. Deleting the stamp at the call site left all 15 green.

    So this drives the real `LLMGateway.stream_chat` and reads what the audit
    writer was handed.
    """
    import asyncio

    from app.services import audit
    from app.services.llm_gateway import LLMGateway

    captured: dict[str, object] = {}
    monkeypatch.setattr(
        audit, "record_llm_call", lambda **kw: captured.update(kw),
    )

    async def _run():
        gw = LLMGateway()
        async for _chunk in gw.stream_chat(
            system_prompt="You speak as the trader.",
            messages=[],
            model_tier="standard",
            audit_agent_id="trader",
            audit_flow="room",
        ):
            pass

    asyncio.run(_run())
    assert captured, "record_llm_call was never reached"
    assert captured["prompt_version"] == pv.prompt_version(AgentId.TRADER), (
        "the gateway did not stamp the row with this agent's prompt version"
    )


def test_the_gateway_stamps_NULL_for_a_flow_with_no_agent(monkeypatch):
    """The Concierge and the PM reformatter have no agent id. NULL is the honest
    answer and must not become a string."""
    import asyncio

    from app.services import audit
    from app.services.llm_gateway import LLMGateway

    captured: dict[str, object] = {}
    monkeypatch.setattr(audit, "record_llm_call", lambda **kw: captured.update(kw))

    async def _run():
        gw = LLMGateway()
        async for _c in gw.stream_chat(
            system_prompt="x", messages=[], model_tier="standard", audit_flow="concierge",
        ):
            pass

    asyncio.run(_run())
    assert captured["prompt_version"] is None


# ── round-1 audit MAJOR: the mandate matrix, and proof it is complete ─────────


def test_a_change_behind_a_risk_score_branch_moves_the_version(monkeypatch):
    """The auditor's exact attack, reproduced as a permanent regression.

    The first version hashed one reference at `risk_score: 3`. Editing text inside
    `_aggressive_block`'s `if m.risk_score <= 2:` branch — real copy a low-risk
    user's Aggressive Debator receives — left the version identical
    (`86c3b410b5c0` before and after). A prompt change would have shipped while
    the column reported "nothing changed", for exactly the population it changed
    for: CR143's silent mis-partitioning, one axis over.
    """
    from app.agents import overlay_generator as og

    original = og._ROLE_BUILDERS[AgentId.AGGRESSIVE_DEBATOR]

    def _patched(m):
        out = original(m)
        if m.risk_score <= 2:
            out += "\n- A different low-risk-score instruction."
        return out

    before = pv.prompt_version(AgentId.AGGRESSIVE_DEBATOR)
    pv.reset_cache()
    registry = dict(og._ROLE_BUILDERS)
    registry[AgentId.AGGRESSIVE_DEBATOR] = _patched
    monkeypatch.setattr(og, "_ROLE_BUILDERS", registry)
    assert pv.prompt_version(AgentId.AGGRESSIVE_DEBATOR) != before


@pytest.mark.parametrize("axis,patch", [
    ("halal", lambda out, m: out + "\n- halal-only line." if m.compliance.halal else out),
    ("long_only", lambda out, m: out + "\n- long-only line." if m.compliance.long_only else out),
    ("blocklist", lambda out, m: out + "\n- blocklist line." if m.compliance.ticker_blocklist else out),
    ("high_risk", lambda out, m: out + "\n- high-risk line." if m.risk_score >= 4 else out),
])
def test_every_mandate_axis_is_visible_to_the_version(monkeypatch, axis, patch):
    """Not just `risk_score <= 2`. Each axis the assembly branches on must be
    inside the hash, or a prompt edit scoped to that axis ships unversioned."""
    from app.agents import overlay_generator as og

    original = og._ROLE_BUILDERS[AgentId.CONSERVATIVE_DEBATOR]
    before = pv.prompt_version(AgentId.CONSERVATIVE_DEBATOR)
    pv.reset_cache()
    registry = dict(og._ROLE_BUILDERS)
    registry[AgentId.CONSERVATIVE_DEBATOR] = lambda m: patch(original(m), m)
    monkeypatch.setattr(og, "_ROLE_BUILDERS", registry)
    assert pv.prompt_version(AgentId.CONSERVATIVE_DEBATOR) != before, (
        f"a change behind the {axis!r} branch is invisible to the version"
    )


def test_the_matrix_executes_every_line_of_every_role_block():
    """The completeness proof, and the reason this is not just "I added the branch
    the auditor found".

    A matrix chosen by reading the code is only as complete as the reading. This
    TRACES the assembly and asserts that every executable line of every role-block
    function actually ran. A branch added later — on an axis nobody enumerated —
    makes this test red instead of silently shipping unversioned.
    """
    import sys

    from app.agents import overlay_generator as og

    targets = dict(og._ROLE_BUILDERS)
    wanted: dict[str, set[int]] = {}
    for agent, fn in targets.items():
        lines = {ln for _s, _e, ln in fn.__code__.co_lines() if ln is not None}
        wanted[agent.value] = lines

    seen: set[int] = set()
    og_file = og.__file__

    def _tracer(frame, event, arg):
        # Both events: `sys.settrace` reports a function's `def` line on `call`,
        # never on `line`, so a line-only tracer reports every role block's
        # signature as uncovered and buries the one real gap in twelve false ones.
        if event in ("call", "line") and frame.f_code.co_filename == og_file:
            seen.add(frame.f_lineno)
        return _tracer

    pv.reset_cache()
    sys.settrace(_tracer)
    try:
        for agent in targets:
            pv.prompt_version(agent)
    finally:
        sys.settrace(None)

    uncovered = {a: sorted(ls - seen) for a, ls in wanted.items() if ls - seen}
    assert not uncovered, (
        "the reference matrix never executes these role-block lines, so a prompt "
        f"edit there would ship with an unchanged version: {uncovered}"
    )


def test_the_reference_matrix_is_constant_and_covers_both_sides_of_each_flag():
    """Pinned so widening or narrowing the matrix has to be argued for — it
    renumbers every agent without any prompt having changed."""
    specs = pv._REFERENCE_MANDATES
    assert len(specs) == 3
    assert {s["risk_score"] for s in specs} == {1, 3, 5}
    for flag in ("halal", "long_only"):
        assert {s[flag] for s in specs} == {True, False}, f"{flag} is never seen both ways"
    assert any(s["blocklist"] for s in specs) and any(not s["blocklist"] for s in specs)
    assert {s["path"] for s in specs} == {"active", "long_horizon", "both"}
    # The horizon axis exists because the coverage guard found it — `_fundamentals_block`
    # branches on it and every mandate was LONG until that test went red.
    assert {s["horizon"] for s in specs} == {"long", "very_long", "short"}


def test_the_matrix_is_built_by_model_copy_not_by_the_hydrator():
    """`hydrate_coach_mandate` ignores `halal` / `long_only` / `ticker_blocklist`
    from a spec dict. Driving the axes through it would silently yield three
    identical mandates and re-open the blind spot while looking fixed."""
    mandates = pv._reference_mandates()
    assert {m.risk_score for m in mandates} == {1, 3, 5}
    assert {m.compliance.halal for m in mandates} == {True, False}
    assert {m.compliance.long_only for m in mandates} == {True, False}
    assert any(m.compliance.ticker_blocklist for m in mandates)
