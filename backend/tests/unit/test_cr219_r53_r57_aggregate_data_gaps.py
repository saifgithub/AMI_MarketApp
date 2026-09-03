"""CR219 R53/R57 — `scripts/aggregate_data_gaps.py` on a fixture DB.

Modeled on `test_cr219_verdict_outcome_ledger.py`'s `_mk_user`/`_mk_run`
idiom (same autouse-sqlite-per-test fixture, `tests/conftest.py`), extended
with a `_mk_turn` helper that writes the exact `AgentMessage.model_dump
(mode="json")` shape the runner actually stores — so this test exercises the
script's own DICT-READING code (`isinstance(turn, dict)`, `turn.get(...)`)
against the real wire shape rather than a hand-rolled approximation of it.

Three things this file pins:

  1. The exclusion filter (`excluded_user_ids()`, reused — not re-derived)
     removes a CR035-synthetic user's runs from BOTH tallies, the same way it
     already removes them from the verdict-outcome ledger and every other
     Alpha report.
  2. `data_gaps=None` (never asked / asked-and-silent) and `data_gaps=[]`
     ("GAPS: none") are DISTINCT states in the R53 tally — an omission never
     collapses into "opted out, nothing missing" the way DEF059 warned a
     lazy renderer would.
  3. `envelope_parsed` emission is tallied per agent, `None` counted
     separately as `not_measured` rather than silently excluded from the
     denominator or misread as a `False`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from app.db import get_session, init_schema
from app.db.models import RoomRunRow, User
from scripts.aggregate_data_gaps import (
    ENVELOPE_AGENTS,
    GAPS_AGENTS,
    select_scoreable_runs,
    tally_data_gaps,
    tally_envelope_emission,
)


# ── Fixture helpers ─────────────────────────────────────────────────────────


def _mk_user(*, last_app_version: str | None = "0.1.0+70", created_at=None) -> UUID:
    init_schema()
    uid = uuid4()
    with get_session() as s:
        s.add(User(
            id=uid, plan="floor_pass", credit_balance=8, is_anonymous=True,
            last_app_version=last_app_version,
            created_at=created_at or datetime.now(timezone.utc),
        ))
    return uid


def _mk_turn(
    agent_id: str,
    *,
    data_gaps=None,
    envelope_parsed=None,
    role: str = "agent",
) -> dict:
    """The exact `AgentMessage.model_dump(mode='json')` shape — verified
    against a real instance in the design pass, not hand-approximated."""
    return {
        "agent_id": agent_id, "role": role, "content": "prose body",
        "timestamp": "2026-09-01T12:00:00Z",
        "token_count": None, "model": None,
        "stance": None, "conviction": None, "headline": None,
        "argued_size_pct": None,
        "data_gaps": data_gaps, "envelope_parsed": envelope_parsed,
    }


def _mk_run(
    user_id: UUID,
    *,
    ticker: str = "AAPL",
    transcript: list[dict] | None = None,
    triggered_at=None,
) -> UUID:
    rid = uuid4()
    with get_session() as s:
        s.add(RoomRunRow(
            id=rid, user_id=user_id, ticker=ticker,
            triggered_at=triggered_at or datetime.now(timezone.utc),
            mandate_version=1, model_tier="mid", status="completed",
            transcript=transcript or [],
        ))
    return rid


def _all_runs() -> list[RoomRunRow]:
    from sqlalchemy import select
    with get_session() as s:
        return list(s.execute(select(RoomRunRow)).scalars().all())


# ── Vacuity guards ───────────────────────────────────────────────────────────


def test_vacuity_gaps_agents_is_the_four_analysts():
    assert GAPS_AGENTS == {
        "fundamentals_analyst", "market_analyst", "news_analyst", "social_media_analyst",
    }


def test_vacuity_envelope_agents_is_the_eleven_prose_voices_minus_pm():
    assert len(ENVELOPE_AGENTS) == 11
    assert "portfolio_manager" not in ENVELOPE_AGENTS
    assert "concierge" not in ENVELOPE_AGENTS
    assert "risk_officer" not in ENVELOPE_AGENTS


# ── The exclusion filter is honored ─────────────────────────────────────────


def test_a_cr035_synthetic_users_runs_are_excluded_from_both_tallies():
    real_uid = _mk_user()
    synth_uid = _mk_user(last_app_version="room-benchmark")

    _mk_run(real_uid, transcript=[
        _mk_turn("fundamentals_analyst", data_gaps=["peer comps"], envelope_parsed=True),
    ])
    _mk_run(synth_uid, transcript=[
        _mk_turn("fundamentals_analyst", data_gaps=["segment split"], envelope_parsed=True),
    ])

    from app.services.verdict_outcomes import excluded_user_ids
    excluded = excluded_user_ids()
    assert synth_uid in excluded
    assert real_uid not in excluded

    scoreable, counts = select_scoreable_runs(
        _all_runs(), excluded, tickers=None, since=None,
    )
    assert counts["excluded_user"] == 1
    assert len(scoreable) == 1

    bucket_counts, examples, by_ita, agent_counts = tally_data_gaps(scoreable)
    assert sum(bucket_counts.values()) == 1
    # Only the real user's item made it through.
    assert examples["Peer / sector comparables"][1] == "peer comps"


def test_the_seed_burst_is_excluded_too():
    """The second half of the standing filter (`memory/
    feedback_user_report_exclusions.md`) — a device-less, app-version-less
    row created inside the 1-minute 2026-05-24 05:10 burst."""
    seed_uid = _mk_user(
        last_app_version=None,
        created_at=datetime(2026, 5, 24, 5, 10, 30, tzinfo=timezone.utc),
    )
    with get_session() as s:
        row = s.get(User, seed_uid)
        row.device_model = None  # already None by default; explicit for clarity

    _mk_run(seed_uid, transcript=[
        _mk_turn("market_analyst", data_gaps=["macro"], envelope_parsed=True),
    ])

    from app.services.verdict_outcomes import excluded_user_ids
    assert seed_uid in excluded_user_ids()


# ── R53 — None vs [] are distinct in the tally ───────────────────────────


def test_an_omitted_tail_and_an_explicit_none_are_counted_separately():
    uid = _mk_user()
    _mk_run(uid, transcript=[
        _mk_turn("fundamentals_analyst", data_gaps=None, envelope_parsed=True),  # silent
        _mk_turn("market_analyst", data_gaps=[], envelope_parsed=True),          # "GAPS: none"
        _mk_turn("news_analyst", data_gaps=["peer comps"], envelope_parsed=True),
    ])

    scoreable, _ = select_scoreable_runs(_all_runs(), set(), tickers=None, since=None)
    bucket_counts, examples, by_ita, agent_counts = tally_data_gaps(scoreable)

    assert agent_counts[("fundamentals_analyst", "asked")] == 1
    assert agent_counts[("fundamentals_analyst", "answered")] == 0  # never answered

    assert agent_counts[("market_analyst", "asked")] == 1
    assert agent_counts[("market_analyst", "answered")] == 1
    assert agent_counts[("market_analyst", "opted_out")] == 1  # DID answer: "nothing"

    assert agent_counts[("news_analyst", "asked")] == 1
    assert agent_counts[("news_analyst", "answered")] == 1
    assert agent_counts[("news_analyst", "opted_out")] == 0

    # Only the one real item reaches the bucket table.
    assert sum(bucket_counts.values()) == 1


def test_non_analyst_agents_never_contribute_to_the_gaps_tally_even_if_present():
    """A stray `data_gaps` value on a non-analyst turn (should never happen
    given room_runner.py's own gate, but the aggregator must not trust the
    stored shape blindly) is ignored — GAPS_AGENTS is the authority here,
    not whatever happens to be in the row."""
    uid = _mk_user()
    _mk_run(uid, transcript=[
        _mk_turn("bull_researcher", data_gaps=["should never count"], envelope_parsed=True),
    ])
    scoreable, _ = select_scoreable_runs(_all_runs(), set(), tickers=None, since=None)
    bucket_counts, *_ = tally_data_gaps(scoreable)
    assert sum(bucket_counts.values()) == 0


def test_items_are_bucketed_by_the_arms_taxonomy_and_ranked_by_ticker_and_agent():
    uid = _mk_user()
    _mk_run(uid, ticker="AAPL", transcript=[
        _mk_turn("fundamentals_analyst", data_gaps=["segment revenue split"], envelope_parsed=True),
    ])
    _mk_run(uid, ticker="MSFT", transcript=[
        _mk_turn("fundamentals_analyst", data_gaps=["segment revenue split"], envelope_parsed=True),
        _mk_turn("news_analyst", data_gaps=["segment revenue split"], envelope_parsed=True),
    ])

    scoreable, _ = select_scoreable_runs(_all_runs(), set(), tickers=None, since=None)
    bucket_counts, examples, by_ita, _ = tally_data_gaps(scoreable)

    assert bucket_counts["Segment / geographic revenue split"] == 3
    assert by_ita[("Segment / geographic revenue split", "AAPL", "fundamentals_analyst")] == 1
    assert by_ita[("Segment / geographic revenue split", "MSFT", "fundamentals_analyst")] == 1
    assert by_ita[("Segment / geographic revenue split", "MSFT", "news_analyst")] == 1


def test_an_item_matching_no_bucket_pattern_is_unbucketed_not_dropped():
    uid = _mk_user()
    _mk_run(uid, transcript=[
        _mk_turn("social_media_analyst", data_gaps=["a genuinely novel data class"], envelope_parsed=True),
    ])
    scoreable, _ = select_scoreable_runs(_all_runs(), set(), tickers=None, since=None)
    bucket_counts, *_ = tally_data_gaps(scoreable)
    assert bucket_counts["(unbucketed)"] == 1


# ── R57 — emission tally ─────────────────────────────────────────────────


def test_emission_is_tallied_per_agent_parsed_vs_unparsed_vs_not_measured():
    uid = _mk_user()
    _mk_run(uid, transcript=[
        _mk_turn("neutral_debator", envelope_parsed=True),
        _mk_turn("neutral_debator", envelope_parsed=True),
        _mk_turn("neutral_debator", envelope_parsed=False),
        # A pre-R57 stored row: the key exists on the dict (JSONB), value None.
        _mk_turn("neutral_debator", envelope_parsed=None),
    ])
    scoreable, _ = select_scoreable_runs(_all_runs(), set(), tickers=None, since=None)
    tally = tally_envelope_emission(scoreable)
    row = tally["neutral_debator"]
    assert row == {"parsed": 2, "unparsed": 1, "not_measured": 1}


def test_a_missing_key_entirely_pre_migration_row_shape_reads_as_not_measured():
    """R53/R57 ship with no schema migration (the WP's own framing) — a row
    stored before this shipped simply lacks the KEY, not merely a None value.
    `dict.get` must degrade the same way as an explicit None."""
    uid = _mk_user()
    turn = _mk_turn("trader", envelope_parsed=True)
    del turn["envelope_parsed"]  # simulate a genuinely pre-R57 stored dict
    _mk_run(uid, transcript=[turn])
    scoreable, _ = select_scoreable_runs(_all_runs(), set(), tickers=None, since=None)
    tally = tally_envelope_emission(scoreable)
    assert tally["trader"] == {"parsed": 0, "unparsed": 0, "not_measured": 1}


def test_the_pm_and_internal_agents_are_absent_from_the_envelope_table():
    uid = _mk_user()
    _mk_run(uid, transcript=[
        _mk_turn("portfolio_manager", envelope_parsed=None),
        _mk_turn("risk_officer", envelope_parsed=None, role="system"),
    ])
    scoreable, _ = select_scoreable_runs(_all_runs(), set(), tickers=None, since=None)
    tally = tally_envelope_emission(scoreable)
    assert "portfolio_manager" not in tally
    assert "risk_officer" not in tally


def test_only_agent_role_turns_are_counted_never_user_or_system_rows():
    uid = _mk_user()
    _mk_run(uid, transcript=[
        _mk_turn("neutral_debator", envelope_parsed=True, role="user"),
        _mk_turn("neutral_debator", envelope_parsed=True, role="system"),
        _mk_turn("neutral_debator", envelope_parsed=True, role="agent"),
    ])
    scoreable, _ = select_scoreable_runs(_all_runs(), set(), tickers=None, since=None)
    tally = tally_envelope_emission(scoreable)
    assert tally["neutral_debator"] == {"parsed": 1, "unparsed": 0, "not_measured": 0}


# ── Filters ────────────────────────────────────────────────────────────────


def test_the_ticker_filter_scopes_both_tallies():
    uid = _mk_user()
    _mk_run(uid, ticker="AAPL", transcript=[
        _mk_turn("market_analyst", data_gaps=["peer comps"], envelope_parsed=True),
    ])
    _mk_run(uid, ticker="TSLA", transcript=[
        _mk_turn("market_analyst", data_gaps=["macro rates"], envelope_parsed=True),
    ])
    scoreable, counts = select_scoreable_runs(
        _all_runs(), set(), tickers={"AAPL"}, since=None,
    )
    assert counts["ticker_filtered"] == 1
    assert len(scoreable) == 1
    assert scoreable[0].ticker == "AAPL"


def test_the_since_filter_excludes_older_runs():
    uid = _mk_user()
    old = _mk_run(
        uid, triggered_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        transcript=[_mk_turn("news_analyst", data_gaps=["old"], envelope_parsed=True)],
    )
    new = _mk_run(
        uid, triggered_at=datetime.now(timezone.utc),
        transcript=[_mk_turn("news_analyst", data_gaps=["new"], envelope_parsed=True)],
    )
    scoreable, counts = select_scoreable_runs(
        _all_runs(), set(), tickers=None,
        since=datetime.now(timezone.utc) - timedelta(days=7),
    )
    assert counts["too_old"] == 1
    assert {r.id for r in scoreable} == {new}


# ── An empty scoreable set degrades to zeros, never a crash ─────────────


def test_no_runs_at_all_yields_empty_tallies_not_an_exception():
    bucket_counts, examples, by_ita, agent_counts = tally_data_gaps([])
    assert bucket_counts == {}
    assert examples == {}
    tally = tally_envelope_emission([])
    assert all(v == {"parsed": 0, "unparsed": 0, "not_measured": 0} for v in tally.values())
