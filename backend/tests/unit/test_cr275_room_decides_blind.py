"""CR275 (CR267 WP-21a) — the Room decides blind: no Street view in any agent input.

The Beta programme scores the Room's verdict against the sell-side consensus.
That comparison is void if any desk, the CIO/PM, or a judge was shown the
consensus first. These tests build REAL prompts through the real assembly code
(`build_room_messages` for all twelve display agents, `build_risk_officer_messages`
for the structured officer) from a fact sheet that DOES carry every Street field,
and fail if any rating, price target, rating split, opinion count or per-firm
action reaches the text the model receives.

The Street data must stay on the profile for post-verdict code (WP-21b), so the
last tests pin that too: blinding is a read-side copy, never a deletion.
"""

from __future__ import annotations

import pytest

from app.schemas import AgentId
from app.schemas.room import SheetFieldTransition
from app.services import prompt_version, room_runner
from app.services.room_prompts import (
    _PHASE_FOR_AGENT,
    _analyst_line,
    _format_profile,
    build_risk_officer_messages,
    build_room_messages,
)
from app.services.street_view_blind import blind_profile, is_street_view_key

# Values chosen to be unmistakable in a prompt: none is a number the rest of the
# fact sheet could legitimately produce.
_RATING = "strong buy"
_TARGET_MEAN = 987.65
_TARGET_HIGH = 1234.56
_TARGET_LOW = 55.43
_TARGET_MEDIAN = 876.54
_OPINIONS = 47
_SCORE = 1.7
_FIRM = "Zzyzx Securities"
_TAPE_PT = 4321.0

_STREET_FIELD_STATE = {
    "analyst_target_price": "live",
    "analyst_rating": "live",
    "analyst_opinion_count": "live",
    "analyst_target_high": "live",
    "analyst_target_low": "live",
    "analyst_target_median": "live",
    "analyst_rating_score": "live",
    "analyst_rating_split": "live",
    "analyst_rating_split_history": "live",
    "analyst_tape": "live",
}

# The labels the renderers put in front of Street data. Checked alongside the
# values so a renderer that prints a label with the numbers rounded is caught.
_STREET_LABELS = (
    "Analyst consensus",
    "Analyst rating split",
    "Recent analyst actions",
    "Street view",
    "to the consensus target",
)

_STREET_VALUES = (
    _RATING, "987.65", "1234.56", "55.43", "876.54", "47 analysts", "1.7",
    _FIRM, "4321",
)


def _fixture_profile() -> dict:
    """A live fact sheet that carries every Street field the pipeline can emit."""
    return {
        "ticker": "MSFT",
        "run_date": "2026-11-18",
        "base_price": 400.0,
        "pe": 31.2,
        "rev_growth": 12.4,
        "profit_margin": 35.1,
        "net_cash": 20000,
        "last_close": 400.0,
        "field_state": {
            "run_date": "live",
            "base_price": "live",
            "pe": "live",
            "rev_growth": "live",
            "profit_margin": "live",
            "net_cash": "live",
            **_STREET_FIELD_STATE,
        },
        "analyst_target_price": _TARGET_MEAN,
        "analyst_rating": _RATING,
        "analyst_opinion_count": _OPINIONS,
        "analyst_target_high": _TARGET_HIGH,
        "analyst_target_low": _TARGET_LOW,
        "analyst_target_median": _TARGET_MEDIAN,
        "analyst_rating_score": _SCORE,
        "analyst_rating_split": {
            "strong_buy": 11, "buy": 22, "hold": 33, "sell": 44, "strong_sell": 55,
        },
        "analyst_rating_split_history": [
            {"period": "-1m", "strong_buy": 10, "buy": 21, "hold": 34, "sell": 44,
             "strong_sell": 55},
        ],
        "analyst_tape": [
            {"date": "2026-11-10", "firm": _FIRM, "to_grade": "Buy",
             "from_grade": "Hold", "action": "up", "pt_action": "Raises",
             "current_pt": _TAPE_PT, "prior_pt": 4000.0},
        ],
    }


def _mandate():
    return prompt_version._reference_mandates()[0]


def _assert_blind(text: str, who: str) -> None:
    for label in _STREET_LABELS:
        assert label not in text, f"{who}: Street label {label!r} reached the prompt"
    for value in _STREET_VALUES:
        assert value not in text, f"{who}: Street value {value!r} reached the prompt"


def test_fixture_really_carries_the_street_fields():
    """Positive control: the renderer WOULD print these if it were handed them,
    so a pass below means the fields were withheld, not that the fixture is dull."""
    line = _analyst_line(_fixture_profile())
    assert line and _RATING in line and "987.65" in line
    assert room_runner._analyst_view_from_profile(_fixture_profile()) is not None


@pytest.mark.parametrize("agent_id", sorted(_PHASE_FOR_AGENT, key=lambda a: a.value))
def test_no_display_agent_prompt_carries_the_street_view(agent_id):
    """All twelve agents, the CIO/PM (VERDICT phase) included."""
    system_prompt, messages = build_room_messages(
        agent_id=agent_id,
        mandate=_mandate(),
        user_id=None,
        ticker="MSFT",
        profile=_fixture_profile(),
        transcript=[],
        trade_proposal={"size_pct": 3.0, "entry": 100.0, "stop": 94.0},
    )
    text = "\n".join([system_prompt, *(str(getattr(m, "content", m)) for m in messages)])
    assert "Fact sheet as of 2026-11-18" in text, "the fact sheet itself must still render"
    _assert_blind(text, agent_id.value)


def test_risk_officer_prompt_carries_no_street_view():
    system_prompt, messages, _rows = build_risk_officer_messages(
        mandate=_mandate(),
        ticker="MSFT",
        profile=_fixture_profile(),
        transcript=[],
        trade_proposal={"size_pct": 3.0, "entry": 100.0, "stop": 94.0},
    )
    text = "\n".join([system_prompt, *(str(getattr(m, "content", m)) for m in messages)])
    assert "31.2" in text, "the fact sheet itself must still render"
    _assert_blind(text, "risk_officer")


@pytest.mark.parametrize("agent_id", [None, *_PHASE_FOR_AGENT])
def test_fact_sheet_is_blind_for_every_lane(agent_id):
    """The full sheet (agent_id=None) and each lane-filtered sheet."""
    _assert_blind(_format_profile(_fixture_profile(), agent_id), str(agent_id))


def test_a_new_analyst_prefixed_field_is_withheld_by_default():
    """Fail-closed: a Street field added next quarter must not leak until someone
    remembers to list it."""
    profile = _fixture_profile()
    profile["analyst_future_signal"] = "SENTINEL-FUTURE"
    profile["field_state"]["analyst_future_signal"] = "live"
    blind = blind_profile(profile)
    assert "analyst_future_signal" not in blind
    assert "analyst_future_signal" not in blind["field_state"]


def test_blinding_keeps_the_street_data_for_post_verdict_code():
    """WP-21b compares the verdict to the Street AFTER it is decided; the data
    must still be on the run's own profile, and blinding must not mutate it."""
    profile = _fixture_profile()
    before = {k: profile[k] for k in profile if is_street_view_key(k)}
    _format_profile(profile, AgentId.PORTFOLIO_MANAGER)
    after = {k: profile[k] for k in profile if is_street_view_key(k)}
    assert after == before and len(after) == 10
    assert profile["field_state"]["analyst_tape"] == "live"
    view = room_runner._analyst_view_from_profile(profile)
    assert view is not None
    assert view.rating == _RATING and view.target_mean == _TARGET_MEAN
    assert view.rating_split is not None and view.tape[0].firm == _FIRM


def test_blind_profile_leaves_every_non_street_field_alone():
    profile = _fixture_profile()
    blind = blind_profile(profile)
    for key, value in profile.items():
        if key == "field_state" or is_street_view_key(key):
            continue
        assert blind[key] == value
    assert blind["field_state"]["pe"] == "live"
    assert not any(is_street_view_key(k) for k in blind["field_state"])


def test_street_field_state_flips_are_not_told_to_the_pm():
    """The PM prompt renders the sheet-state transitions between convenes; one
    saying `analyst_tape: live -> unavailable` would tell the Room the Street's
    view exists."""
    prior = {
        "date": "2026-11-10", "action": "hold", "reference_price": 390.0,
        "sheet_state": {"pe": "live", "analyst_tape": "live", "analyst_rating": "live"},
    }
    this = {
        "field_state": {"pe": "unavailable", "analyst_tape": "unavailable",
                        "analyst_rating": "unavailable"},
        "last_close": 400.0,
    }
    delta = room_runner._build_next_convene_delta(prior, this_profile=this)
    assert delta is not None
    assert [t.field for t in delta.changed_fields] == ["pe"]
    assert all(isinstance(t, SheetFieldTransition) for t in delta.changed_fields)
