"""CR247 Phase 6 — the standing prompt-evolution digest
(scripts/prompt_evolution_digest.py).

What must hold:
  * aggregation math is exact: per-agent parse rates over ALL calls (empty
    responses are failures and their own counted state), stance/conviction
    distributions, truncation suspects against the EFFECTIVE ceiling
    (max(_AGENT_MAX_TOKENS[agent], provider floor) — the CR211 floor that
    silently rewrites caps must not manufacture suspect-free weeks), PM JSON
    parse rate + constraint_status distribution, the citation-grounding proxy;
  * verdict_outcome movement is keyed in score_verdict_outcomes' own
    vocabulary and the batch scorer's score_pending is NEVER called (the
    digest is read-only; the daily scorer remains the only writer);
  * baseline write/read/compare round-trips, thresholds fire only past
    MIN_BASELINE_N on both sides, and a serving-identity mismatch is flagged
    as cross-model, never silently diffed;
  * model-identity stamping works on the /v1/models fetch and degrades
    loudly (naming provider-only keying) when the fetch fails;
  * every flag kind produces a proposal block carrying the anomaly, a
    HYPOTHESIS, a pre-registered measurement plan, and the governance line —
    and the script's import surface + SQL stream prove it never writes
    product state;
  * cadence: weekly digest vs monthly conclusion (days or convene count).
"""

from __future__ import annotations

import ast
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import event, select

from app.db import get_engine, get_session
from app.db.models import LLMAuditRow, RoomRunRow, User, VerdictOutcomeRow
from app.services.room_runner import PM_LLM_UNAVAILABLE_REASON, PM_ROOM_INCOMPLETE_REASON
from scripts import prompt_evolution_digest as digest

_HOURS = 12
_RECENT = datetime.now(UTC) - timedelta(hours=_HOURS)
_OLD = datetime.now(UTC) - timedelta(days=60)

ENVELOPE_FOR = "The case is intact.\n\n[STANCE: for | CONVICTION: high | HEADLINE: x]"
ENVELOPE_AGAINST = (
    "Vulnerabilities dominate.\n\n[STANCE: against | CONVICTION: medium | HEADLINE: y]"
)
PM_JSON = '{"action": "APPROVE", "narration": "ok", "kill_criterion": "stop"}'


# ── fixtures ─────────────────────────────────────────────────────────────────


def _seed_user(*, last_app_version="1.0.0+42", device_model="iPhone 13") -> User:
    uid = uuid4()
    with get_session() as s:
        s.add(User(id=uid, created_at=datetime(2026, 6, 1, tzinfo=UTC),
                   device_model=device_model, last_app_version=last_app_version))
    return uid


def _seed_llm_row(user_id, agent_id, *, flow="room", provider="vllm",
                  created_at=None, response_text=None, system_prompt="sheet 150 12x",
                  output_tokens=None, constraint_status=None, prompt_version=None):
    with get_session() as s:
        s.add(LLMAuditRow(
            user_id=user_id, agent_id=agent_id, flow=flow, tier="standard",
            provider=provider, system_prompt=system_prompt,
            response_text=response_text, created_at=created_at or _RECENT,
            output_tokens=output_tokens, constraint_status=constraint_status,
            prompt_version=prompt_version,
        ))


def _verdict(action="APPROVE", **over):
    v = {
        "action": action, "size_pct": 5.0, "entry": 121.0, "target": 131.0,
        "stop": 112.0, "reason": "test verdict", "violations": [],
        "overridden_from_llm": False,
        "level_provenance": {"entry": "pm", "target": "pm", "stop": "trader"},
    }
    v.update(over)
    return v


def _seed_run(user_id, *, ticker="AAPL", triggered_at=None, status="completed",
              verdict=None, transcript=None, retry_count=0):
    rid = uuid4()
    with get_session() as s:
        s.add(RoomRunRow(
            id=rid, user_id=user_id, ticker=ticker,
            triggered_at=triggered_at or _RECENT,
            started_at=triggered_at or _RECENT,
            finished_at=(triggered_at or _RECENT) + timedelta(seconds=90),
            mandate_version=1, model_tier="standard",
            transcript=transcript or [], verdict=verdict, status=status,
            retry_count=retry_count,
        ))
    return rid


def _seed_outcome(user_id, *, status, scored_at=None, forward_return=None,
                  action="APPROVE", reason=None, ticker="AAPL"):
    with get_session() as s:
        s.add(VerdictOutcomeRow(
            id=uuid4(), room_run_id=uuid4(), user_id=user_id, ticker=ticker,
            verdict_action=action, reference_price=100.0,
            reference_at=_OLD, horizon_days=63, status=status,
            forward_return=forward_return, scored_at=scored_at,
            exclusion_reason=reason,
        ))


def _agent_block(agent: str, *, n_calls=40, parse_rate=0.8,
                 truncation_suspect_rate=0.0, n_pm_draws=None,
                 pm_json_parse_rate=None) -> dict:
    """A baseline-shaped per-agent record for compare_to_baseline tests."""
    return {
        "n_calls": n_calls,
        "n_empty": n_calls - int(n_calls * parse_rate),
        "n_parsed": int(n_calls * parse_rate),
        "parse_rate": parse_rate,
        "stance_shares": {"for": 0.7, "against": 0.2, "neutral": 0.1},
        "conviction_shares": {"low": 0.2, "medium": 0.4, "high": 0.4},
        "n_truncation_suspects": int(n_calls * truncation_suspect_rate),
        "truncation_suspect_rate": truncation_suspect_rate,
        "mean_output_tokens": 400.0,
        "grounding_rate": 0.9,
        "n_response_numbers": 100,
        "n_pm_draws": n_pm_draws or 0,
        "n_pm_json_ok": 0,
        "pm_json_parse_rate": pm_json_parse_rate,
        "pm_actions": {},
        "constraint_status": {},
    }


def _aggs(per_agent=None, convenes=25, final_stances=None, final_convictions=None,
          verdict_actions=None, gaps_buckets=None, scripted_share=0.0) -> dict:
    return {
        "convenes": convenes,
        "per_agent_llm": per_agent or {},
        "verdict_actions": verdict_actions or {},
        "scripted_share": scripted_share,
        "scripted_runs": 0,
        "final_stances": final_stances or {},
        "final_convictions": final_convictions or {},
        "gaps_buckets": gaps_buckets or {},
    }


def _baseline(aggs: dict, identity="qwen3.8-flash-next-abliterated") -> dict:
    return {
        "schema": digest.BASELINE_SCHEMA,
        "generated_at": "2026-09-23",
        "serving_identity": {"identity": identity},
        "aggregates": aggs,
    }


def _current(aggs: dict, identity="qwen3.8-flash-next-abliterated") -> dict:
    return {
        "serving_identity": {"identity": identity},
        "aggregates": aggs,
    }


# ── aggregation math ─────────────────────────────────────────────────────────


def test_parse_rate_counts_empty_as_failure_and_distributions() -> None:
    uid = _seed_user()
    _seed_llm_row(uid, "bull_researcher", response_text=ENVELOPE_FOR)
    _seed_llm_row(uid, "bull_researcher", response_text=ENVELOPE_AGAINST)
    _seed_llm_row(uid, "bull_researcher", response_text=None)          # empty — a real state
    _seed_llm_row(uid, "bull_researcher", response_text="no envelope here")
    with get_session() as s:
        rows = list(s.scalars(
            select(LLMAuditRow)))
    stats = digest.aggregate_llm_rows(rows)["bull_researcher"]
    assert stats.n_calls == 4
    assert stats.n_empty == 1
    assert stats.n_parsed == 2                       # over ALL calls, not non-empty
    assert stats.parse_rate() == pytest.approx(0.5)
    assert stats.stances == {"for": 1, "against": 1}
    assert stats.convictions == {"high": 1, "medium": 1}


def test_pm_json_parse_rate_and_constraint_distribution() -> None:
    uid = _seed_user()
    _seed_llm_row(uid, "portfolio_manager", response_text=PM_JSON + " trailing note",
                  constraint_status="enforced")
    _seed_llm_row(uid, "portfolio_manager", response_text="Verdict: PASS\nReasoning: nope",
                  constraint_status="enforced")
    _seed_llm_row(uid, "portfolio_manager", response_text=PM_JSON.replace("APPROVE", "PASS"),
                  constraint_status=None)  # pre-CR210 row: NULL means not requested
    with get_session() as s:
        rows = list(s.scalars(select(LLMAuditRow)))
    pm = digest.aggregate_llm_rows(rows)["portfolio_manager"]
    assert pm.n_pm_draws == 3
    assert pm.n_pm_json_ok == 2
    assert pm.pm_actions == {"APPROVE": 1, "PASS": 1, "UNPARSEABLE": 1}
    assert pm.constraint_status == {"enforced": 2}   # NULL counted as absence, not a category
    assert pm.pm_json_parse_rate() == pytest.approx(2 / 3)


def test_grounding_proxy_counts_numbers_against_system_prompt() -> None:
    uid = _seed_user()
    _seed_llm_row(uid, "fundamentals_analyst",
                  response_text="PE of 150 with 12x sales, plus 99 invented",
                  system_prompt="fact sheet: PE 150, EV/EBITDA 12x")
    with get_session() as s:
        rows = list(s.scalars(select(LLMAuditRow)))
    st = digest.aggregate_llm_rows(rows)["fundamentals_analyst"]
    assert st.n_response_numbers == 3
    assert st.n_grounded_numbers == 2                # 150 and 12x grounded; 99 fabricated
    assert st.grounding_rate() == pytest.approx(2 / 3)


def test_truncation_suspects_use_effective_ceiling(monkeypatch) -> None:
    assert digest.is_truncation_suspect("bull_researcher", "vllm", 1600)   # cap 1600
    assert not digest.is_truncation_suspect("bull_researcher", "vllm", 1599)
    assert not digest.is_truncation_suspect("bear_researcher", "vllm", 1399)
    assert digest.is_truncation_suspect("bear_researcher", "vllm", 1400)
    assert digest.is_truncation_suspect("mystery_agent", "vllm", 800)      # flat fallback
    assert not digest.is_truncation_suspect("bull_researcher", "vllm", None)
    # CR211 floor: when the provider floor raises every cap, the ceiling moves
    monkeypatch.setattr(digest.settings, "vllm_max_tokens_floor", 5000)
    assert not digest.is_truncation_suspect("bull_researcher", "vllm", 1600)
    assert digest.is_truncation_suspect("bull_researcher", "vllm", 5000)
    assert digest.effective_ceiling("bull_researcher", "anthropic") == 1600  # no floor


def test_pm_json_action_balanced_span() -> None:
    assert digest.pm_json_action('pre {"action": "PASS", "nested": {"a": 1}} post') == "PASS"
    assert digest.pm_json_action('{"action": null}') is None
    assert digest.pm_json_action('{"no_action": 1}') is None
    assert digest.pm_json_action('unbalanced {"action": "X"') is None
    assert digest.pm_json_action(None) is None


# ── outcome ledger movement ──────────────────────────────────────────────────


def test_outcome_movement_uses_scorer_vocabulary() -> None:
    uid = _seed_user()
    _seed_outcome(uid, status="scored", scored_at=_RECENT, forward_return=0.10)
    _seed_outcome(uid, status="scored", scored_at=_RECENT, forward_return=-0.05,
                  action="PASS")
    _seed_outcome(uid, status="scored", scored_at=_OLD, forward_return=0.50)  # outside window
    _seed_outcome(uid, status="pending")
    _seed_outcome(uid, status="unscorable", scored_at=_RECENT, reason="mock_price_source")
    with get_session() as s:
        rows = list(s.scalars(select(VerdictOutcomeRow)))
    cutoff = datetime.now(UTC) - timedelta(days=7)
    m = digest.outcome_movement(rows, cutoff)
    assert m["vocabulary"] == {"scored": "scored", "pending": "pending",
                               "unscorable": "unscorable"}
    assert m["pending_total"] == 1
    assert m["window_decided"] == 3
    assert m["window_scored"] == 2
    assert m["window_unscorable_by_reason"] == {"mock_price_source": 1}
    assert m["window_scored_hit_rate"]["APPROVE"]["hit_rate"] == 1.0
    assert m["window_scored_hit_rate"]["PASS"]["hit_rate"] == 0.0


# ── baseline compare ─────────────────────────────────────────────────────────


def test_parse_drop_flag_past_threshold_and_n_gate() -> None:
    agent = "bull_researcher"
    base = _baseline(_aggs({agent: _agent_block(agent, parse_rate=0.80)}))
    cur = _current(_aggs({agent: _agent_block(agent, parse_rate=0.74)}))
    flags = digest.compare_to_baseline(cur, base)
    assert [f.kind for f in flags] == ["PARSE_RATE_DROP"]
    assert flags[0].subject == agent
    # 4pp: below the 5pp bar — no flag
    cur2 = _current(_aggs({agent: _agent_block(agent, parse_rate=0.76)}))
    assert digest.compare_to_baseline(cur2, base) == []
    # small-n baseline: gated out, never flagged
    small = _baseline(_aggs({agent: _agent_block(agent, n_calls=10, parse_rate=0.80)}))
    assert digest.compare_to_baseline(cur, small) == []
    # no baseline at all: no flags, loudly reported by the renderer instead
    assert digest.compare_to_baseline(cur, None) == []


def test_truncation_doubling_and_stance_shift_flags() -> None:
    agent = "conservative_debator"
    base = _baseline(_aggs(
        {agent: _agent_block(agent, truncation_suspect_rate=0.05)},
        convenes=25,
        final_stances={agent: {"for": 17, "against": 5, "neutral": 3}},
    ))
    cur = _current(_aggs(
        {agent: _agent_block(agent, truncation_suspect_rate=0.11)},
        convenes=25,
        final_stances={agent: {"for": 6, "against": 5, "neutral": 3}},
    ))
    kinds = [f.kind for f in digest.compare_to_baseline(cur, base)]
    assert "TRUNCATION_SUSPECT_SURGE" in kinds
    assert "STANCE_DISTRIBUTION_SHIFT" in kinds
    # 0.05 -> 0.09 is not a doubling; 68% -> 60% on 'for' is inside the 10pp bar
    cur_ok = _current(_aggs(
        {agent: _agent_block(agent, truncation_suspect_rate=0.09)},
        convenes=25,
        final_stances={agent: {"for": 15, "against": 6, "neutral": 4}},
    ))
    assert digest.compare_to_baseline(cur_ok, base) == []


def test_truncation_zero_baseline_never_divides_by_zero() -> None:
    agent = "aggressive_debator"
    base = _baseline(_aggs({
        agent: {**_agent_block(agent, truncation_suspect_rate=0.0),
                "n_truncation_suspects": 0},
    }))
    # one suspect from a zero baseline: new information, but below the 2+
    # floor — no flag, and no ZeroDivisionError in the detail string
    one = _current(_aggs({
        agent: {**_agent_block(agent, truncation_suspect_rate=0.05),
                "n_truncation_suspects": 1},
    }))
    assert digest.compare_to_baseline(one, base) == []
    # two or more: fires, and the detail names the zero baseline
    two = _current(_aggs({
        agent: {**_agent_block(agent, truncation_suspect_rate=0.10),
                "n_truncation_suspects": 2},
    }))
    flags = digest.compare_to_baseline(two, base)
    assert [f.kind for f in flags] == ["TRUNCATION_SUSPECT_SURGE"]
    assert "baseline 0 suspects" in flags[0].detail


def test_conviction_shift_and_verdict_action_shift_flags() -> None:
    agent = "trader"
    base = _baseline(_aggs(
        convenes=30,
        final_convictions={agent: {"high": 21, "medium": 6, "low": 3}},
        verdict_actions={"APPROVE": 21, "PASS": 9},
    ))
    cur = _current(_aggs(
        convenes=30,
        final_convictions={agent: {"high": 9, "medium": 6, "low": 15}},
        verdict_actions={"APPROVE": 9, "PASS": 21},
    ))
    kinds = [f.kind for f in digest.compare_to_baseline(cur, base)]
    assert "CONVICTION_DISTRIBUTION_SHIFT" in kinds
    assert "VERDICT_ACTION_SHIFT" in kinds


def test_pm_json_parse_drop_flag() -> None:
    base = _baseline(_aggs({"portfolio_manager": _agent_block(
        "portfolio_manager", n_pm_draws=40, pm_json_parse_rate=0.95)}))
    cur = _current(_aggs({"portfolio_manager": _agent_block(
        "portfolio_manager", n_pm_draws=40, pm_json_parse_rate=0.88)}))
    kinds = [f.kind for f in digest.compare_to_baseline(cur, base)]
    assert kinds == ["PM_JSON_PARSE_DROP"]


def test_identity_mismatch_flagged_first() -> None:
    base = _baseline(_aggs(), identity="qwen3.8-flash-next-abliterated")
    cur = _current(_aggs(), identity="qwen3.9-next")
    flags = digest.compare_to_baseline(cur, base)
    assert flags[0].kind == "MODEL_IDENTITY_MISMATCH"


def test_gaps_movement_and_surge_flags() -> None:
    base = _baseline(_aggs(gaps_buckets={
        "Debt: maturity / fixed-vs-floating / interest coverage": 10,
        "Peer / sector comparables": 8,
    }))
    cur = _current(_aggs(gaps_buckets={
        "Debt: maturity / fixed-vs-floating / interest coverage": 5,
        "Peer / sector comparables": 3,
        "Macro series (rates, CPI, Fed path, commodity)": 9,
    }))
    kinds = {f.kind for f in digest.compare_to_baseline(cur, base)}
    assert "GAPS_WANTLIST_MOVEMENT" in kinds      # macro enters the top-3 asks
    assert "GAPS_WANTLIST_SURGE" not in kinds     # 10->5 / 8->3 are declines
    base2 = _baseline(_aggs(gaps_buckets={"Peer / sector comparables": 2}))
    cur2 = _current(_aggs(gaps_buckets={"Peer / sector comparables": 5}))
    kinds2 = {f.kind for f in digest.compare_to_baseline(cur2, base2)}
    assert "GAPS_WANTLIST_SURGE" in kinds2


# ── serving-model identity ───────────────────────────────────────────────────


def test_fetch_identity_success_uses_root_never_alias(monkeypatch) -> None:
    class _Resp:
        @staticmethod
        def json():
            return {"data": [{"id": "ami-llm", "root": "qwen3.8-flash-next-abliterated"}]}

    monkeypatch.setattr(httpx, "get", lambda url, timeout: _Resp())
    ident = digest.fetch_serving_identity("http://192.168.20.74:8000/")
    assert ident["identity"] == "qwen3.8-flash-next-abliterated"
    assert ident["source"] == "http://192.168.20.74:8000/v1/models"
    assert ident["error"] is None


def test_fetch_identity_failure_degrades_loudly(monkeypatch) -> None:
    def _boom(url, timeout):
        raise httpx.ConnectError("refused")
    monkeypatch.setattr(httpx, "get", _boom)
    ident = digest.fetch_serving_identity("http://127.0.0.1:9/")
    assert ident["identity"] is None
    assert "ConnectError" in ident["error"]
    # no base url configured: same loud degradation, provider-only keying
    ident2 = digest.fetch_serving_identity(None)
    assert ident2["identity"] is None
    assert "provider-only" in ident2["error"]


# ── cadence ──────────────────────────────────────────────────────────────────


def test_cadence_classification() -> None:
    assert digest.classify_cadence(7, 5) == "weekly digest"
    assert digest.classify_cadence(29, 99) == "weekly digest"
    assert digest.classify_cadence(30, 5) == "monthly conclusion"
    assert digest.classify_cadence(7, 100) == "monthly conclusion"   # per-N-convenes


# ── proposal blocks ──────────────────────────────────────────────────────────


ALL_KINDS = [
    "PARSE_RATE_DROP", "TRUNCATION_SUSPECT_SURGE", "STANCE_DISTRIBUTION_SHIFT",
    "CONVICTION_DISTRIBUTION_SHIFT", "PM_JSON_PARSE_DROP", "VERDICT_ACTION_SHIFT",
    "SCRIPTED_TURNS_SURGE", "GAPS_WANTLIST_MOVEMENT", "GAPS_WANTLIST_SURGE",
    "MODEL_IDENTITY_MISMATCH", "SOMETHING_UNTEMPLATED",
]


def test_proposal_block_shape_for_every_kind() -> None:
    flags = [digest.Flag(kind=k, subject="subj", baseline=1, current=2,
                         detail="detail") for k in ALL_KINDS]
    blocks = digest.build_proposal_blocks(
        flags, stamp="2026-09-30", window_days=7, window_start="2026-09-23",
        cadence="weekly digest")
    assert len(blocks) == len(ALL_KINDS)
    for block in blocks:
        assert block.startswith("### PED-2026-09-30-")
        assert "- anomaly:" in block
        assert "HYPOTHESIS" in block
        assert "- pre-registered measurement plan:" in block
        assert "- benchmark:" in block
        assert "- passes when:" in block
        assert "governance: PROPOSAL ONLY" in block
        assert "personas, flags, or config" in block


def test_import_surface_reuses_the_loop_and_imports_no_mutators() -> None:
    """The digest must build ON CR157/CR219's loop (imports it) and must not
    import any of the repo's known state-mutating scripts."""
    source = Path(digest.__file__).read_text()
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
            imported.update(node.module.split(".")[0])
            imported.update(f"{node.module}.{a.name}" for a in node.names)
    mutators = {
        "scripts.cr220_backfill_compliance_defaults",
        "scripts.def110_backfill",
        "scripts.cr129_backfill_journal",
        "scripts.cr136_backfill_portfolio_snapshots",
        "scripts.backfill_price_history",
        "scripts.prune_bug_attachments",
        "scripts.send_notification",
    }
    assert not (imported & mutators), imported & mutators
    for required in ("scripts.aggregate_data_gaps", "scripts.weekly_room_retro",
                     "app.services.verdict_outcomes"):
        assert required in imported, required


# ── end-to-end against the fixture DB ────────────────────────────────────────


def _run_main(tmp_path, *extra) -> tuple[int, Path]:
    out = tmp_path / "digest_out"
    rc = digest.main(["--out", str(out), *extra])
    return rc, out


def test_dry_run_prints_and_writes_nothing(tmp_path, capsys) -> None:
    uid = _seed_user()
    _seed_llm_row(uid, "bull_researcher", response_text=ENVELOPE_FOR)
    rc, out = _run_main(tmp_path, "--dry-run")
    assert rc == 0
    assert not out.exists()
    text = capsys.readouterr().out
    assert "weekly digest" in text
    assert "--dry-run" in text
    assert "UNIDENTIFIED" in text        # no vLLM base url in the test env — loud, not silent


def test_full_run_writes_baseline_then_flags_against_it(tmp_path, capsys, monkeypatch):
    uid = _seed_user()
    # 40 bull rows at 80% parse → the first run establishes the baseline
    for i in range(40):
        _seed_llm_row(uid, "bull_researcher",
                      response_text=ENVELOPE_FOR if i % 5 else "no envelope",
                      output_tokens=100)
    rc, out = _run_main(tmp_path)
    assert rc == 0
    baseline_path = out / digest.BASELINE_FILENAME
    assert baseline_path.exists()
    baseline = json.loads(baseline_path.read_text())
    assert baseline["schema"] == digest.BASELINE_SCHEMA
    assert baseline["serving_identity"]["identity"] is None   # fetch failed loudly
    assert baseline["aggregates"]["per_agent_llm"]["bull_researcher"]["n_calls"] == 40
    assert (out / f"digest_{digest.date_today_iso()}.md").exists()
    assert "establishes one" in capsys.readouterr().out

    # second window: parse collapses to 50% on the same volume → flag + proposal
    for i in range(40):
        _seed_llm_row(uid, "bull_researcher",
                      response_text=ENVELOPE_FOR if i % 2 else "no envelope",
                      output_tokens=100)
    rc, out = _run_main(tmp_path)
    assert rc == 0
    text = capsys.readouterr().out
    assert "PARSE_RATE_DROP" in text
    proposals = (out / digest.PROPOSALS_FILENAME).read_text()
    assert "PARSE_RATE_DROP: bull_researcher" in proposals
    assert "pre-registered measurement plan" in proposals
    # the previous baseline is backed up before being overwritten
    backups = list(out.glob("baseline_2026-*.json"))
    assert backups, "previous baseline must be preserved, not silently replaced"


def test_report_counts_outages_scripted_and_gaps(tmp_path, capsys) -> None:
    uid = _seed_user()
    _seed_run(uid, verdict=_verdict(action="APPROVE"))
    _seed_run(uid, verdict=_verdict(action="PASS", overridden_from_llm=True,
                                    reason=PM_LLM_UNAVAILABLE_REASON))
    _seed_run(uid, verdict=_verdict(action="APPROVE", scripted_turns=2,
                                    scripted_agents=["news_analyst", "trader"],
                                    reason="thin"))
    _seed_run(uid, verdict=_verdict(
        action="NO_VERDICT", overridden_from_llm=True,
        reason=PM_ROOM_INCOMPLETE_REASON + " 9 of 12 desks responded"))
    transcript = [{
        "agent_id": "fundamentals_analyst", "role": "agent", "content": "c",
        "timestamp": _RECENT.isoformat(),
        "data_gaps": ["debt maturity schedule please"],
    }]
    _seed_run(uid, verdict=_verdict(action="PASS"), transcript=transcript)
    rc, _ = _run_main(tmp_path, "--dry-run")
    assert rc == 0
    text = capsys.readouterr().out
    assert "outage fail-safes excluded from the distribution: 1" in text
    assert "thin-Room NO_VERDICT discards (CR219 R51): 1" in text
    assert "scripted-fallback convenes: 1/5" in text
    # outage PASS must not be in the action distribution
    actions_line = next(line for line in text.splitlines()
                        if line.startswith("- actions"))
    assert "'NO_VERDICT': 1" in actions_line
    assert "Debt: maturity" in text                      # GAPS bucket via aggregate_data_gaps


def test_empty_window_is_loud_and_preserves_baseline(tmp_path, capsys) -> None:
    out = tmp_path / "digest_out"
    out.mkdir()
    (out / digest.BASELINE_FILENAME).write_text(json.dumps(_baseline(_aggs())))
    rc = digest.main(["--out", str(out), "--dry-run"])
    assert rc == 0
    assert "NOTHING MEASURED" in capsys.readouterr().out
    # baseline untouched by the empty week
    assert json.loads((out / digest.BASELINE_FILENAME).read_text())["aggregates"] == _aggs()


def test_monthly_conclusion_tallies_proposal_trend(tmp_path, capsys) -> None:
    uid = _seed_user()
    _seed_llm_row(uid, "bull_researcher", response_text=ENVELOPE_FOR)
    out = tmp_path / "digest_out"
    out.mkdir()
    today = digest.date_today_iso()
    window_start = (datetime.now(UTC) - timedelta(days=30)).date().isoformat()
    earlier = (datetime.now(UTC) - timedelta(days=60)).date().isoformat()
    blocks = [
        f"### PED-{today}-1 — weekly digest — PARSE_RATE_DROP: bull_researcher\n"
        f"- raised: {today} (window {window_start} .. {today}, 7d)\n",
        f"### PED-{today}-2 — weekly digest — PARSE_RATE_DROP: bear_researcher\n"
        f"- raised: {today} (window {window_start} .. {today}, 7d)\n",
        f"### PED-{earlier}-1 — weekly digest — PM_JSON_PARSE_DROP: portfolio_manager\n"
        f"- raised: {earlier} (window x .. {earlier}, 7d)\n",
    ]
    (out / digest.PROPOSALS_FILENAME).write_text("\n".join(blocks))
    rc = digest.main(["--out", str(out), "--days", "30", "--dry-run"])
    assert rc == 0
    text = capsys.readouterr().out
    assert "monthly conclusion" in text
    assert "PARSE_RATE_DROP: RECURRING (2x)" in text
    # the out-of-window PM block is not tallied
    trend_lines = [line for line in text.splitlines()
                   if line.startswith("- PM_JSON_PARSE_DROP:")]
    assert trend_lines == [] or "RECURRING" not in trend_lines[0]


def test_never_writes_product_tables(tmp_path) -> None:
    uid = _seed_user()
    _seed_llm_row(uid, "bull_researcher", response_text=ENVELOPE_FOR)
    _seed_run(uid, verdict=_verdict())
    _seed_outcome(uid, status="pending")

    statements: list[str] = []

    def spy_sql(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.strip().upper())

    engine = get_engine()
    event.listen(engine, "before_cursor_execute", spy_sql)
    try:
        rc, _ = _run_main(tmp_path)
    finally:
        event.remove(engine, "before_cursor_execute", spy_sql)
    assert rc == 0
    writes = [s for s in statements
              if s.startswith(("INSERT", "UPDATE", "DELETE"))]
    assert writes == []
