"""CR260 / CR267 WP-21b — the Street comparison: computed after the verdict, never an agent input.

Pins, against a real `Verdict` and the real bank-site stamp:
  - agree / differ per the programme's rule (a reasoned PASS on a Street-Buy name is
    acceptable; APPROVING a Street Sell/Underperform name is the flagged error);
  - missing Street data is an explicit `unavailable` block, never an empty or zero
    rating dressed up as a reading;
  - the source label is always present;
  - the WP-22 reasons field exists and stays empty (nothing invents reasons);
  - the comparison reaches no agent: no prompt built after the stamp carries any of
    it, the profile is not mutated, and no prompt-building module references it
    (extends the CR275 blind guard, `test_cr275_room_decides_blind.py`).
"""

from __future__ import annotations

import copy
import re
from pathlib import Path

import pytest

from app.schemas import AgentId
from app.schemas.room import StreetComparison, Verdict
from app.services import room_runner
from app.services.room_prompts import (
    _PHASE_FOR_AGENT,
    build_risk_officer_messages,
    build_room_messages,
)
from app.services.street_comparison import STREET_SOURCE_LABEL, build_street_comparison
from tests.unit.test_cr275_room_decides_blind import _fixture_profile, _mandate


def _profile(rating: str = "buy", **overrides) -> dict:
    profile = _fixture_profile()
    profile["analyst_rating"] = rating
    profile.update(overrides)
    return profile


def _verdict(action: str) -> Verdict:
    return Verdict(action=action, reason="test", time_horizon_days=90, size_pct=0.0)


@pytest.mark.parametrize(
    "rating,action,agreement,flag",
    [
        ("strong buy", "APPROVE", "agree", False),
        ("buy", "APPROVE", "agree", False),
        ("buy", "MODIFY", "agree", False),
        ("buy", "PASS", "differ", False),  # a reasoned PASS on a Street-Buy name: not an error
        ("buy", "REJECT", "differ", False),
        ("hold", "APPROVE", "differ", False),
        ("hold", "PASS", "agree", False),
        ("sell", "APPROVE", "differ", True),  # the error
        ("underperform", "APPROVE", "differ", True),
        ("underperform", "MODIFY", "differ", True),
        ("sell", "PASS", "agree", False),
        ("underperform", "REJECT", "agree", False),
        ("buy", "NO_VERDICT", "not_comparable", False),
        ("sell", "NO_VERDICT", "not_comparable", False),
    ],
)
def test_agreement_and_the_single_flagged_error(rating, action, agreement, flag):
    c = build_street_comparison(_verdict(action), _profile(rating))
    assert c.status == "available"
    assert c.agreement == agreement
    assert c.approved_against_street_sell is flag
    assert c.room_action == action


def test_available_comparison_carries_the_street_figures_and_the_source():
    c = build_street_comparison(_verdict("PASS"), _profile("buy"))
    assert c.street_rating == "buy"
    assert c.street_stance == "buy"
    assert c.analyst_count == 47
    assert c.target_mean == 987.65
    assert c.as_of == "2026-11-18"
    assert c.source_label == STREET_SOURCE_LABEL
    assert "Yahoo Finance" in c.source_label and "yfinance" in c.source_label
    assert c.unavailable_reason is None


def test_rating_words_are_normalised_but_the_feeds_word_is_kept():
    c = build_street_comparison(_verdict("PASS"), _profile(" Strong Buy "))
    assert c.street_stance == "buy" and c.street_rating == "strong buy"


def test_reasons_from_narrow_answers_exists_and_is_empty_until_wp22():
    for action in ("APPROVE", "PASS"):
        for rating in ("buy", "sell"):
            c = build_street_comparison(_verdict(action), _profile(rating))
            assert c.reasons_from_narrow_answers == []
    assert "reasons_from_narrow_answers" in StreetComparison.model_fields


# ── missing data: explicit, never an empty or zero rating ────────────────


def _assert_unavailable(c: StreetComparison, reason: str) -> None:
    assert c.status == "unavailable"
    assert c.unavailable_reason == reason
    assert c.street_rating is None and c.street_stance is None
    assert c.analyst_count is None and c.target_mean is None
    assert c.agreement == "not_comparable"
    assert c.approved_against_street_sell is False
    assert c.source_label == STREET_SOURCE_LABEL  # still names the source that had nothing


def test_no_street_fields_on_the_sheet():
    profile = _profile()
    for key in [k for k in profile if k.startswith("analyst_")]:
        del profile[key]
    for key in [k for k in profile["field_state"] if k.startswith("analyst_")]:
        del profile["field_state"][key]
    _assert_unavailable(build_street_comparison(_verdict("APPROVE"), profile), "no_rating")


def test_rating_present_but_not_live_is_not_used():
    profile = _profile()
    profile["field_state"]["analyst_rating"] = "unavailable"
    _assert_unavailable(build_street_comparison(_verdict("APPROVE"), profile), "no_rating")


def test_empty_rating_is_not_a_reading():
    _assert_unavailable(
        build_street_comparison(_verdict("PASS"), _profile(rating="")), "no_rating",
    )


def test_unrecognised_rating_word_is_unavailable_not_guessed():
    _assert_unavailable(
        build_street_comparison(_verdict("PASS"), _profile(rating="accumulate")),
        "unrecognised_rating",
    )


def test_zero_analysts_is_not_a_consensus():
    _assert_unavailable(
        build_street_comparison(_verdict("PASS"), _profile(analyst_opinion_count=0)),
        "no_analysts",
    )


def test_zero_target_is_dropped_not_shown():
    c = build_street_comparison(_verdict("PASS"), _profile(analyst_target_price=0.0))
    assert c.status == "available" and c.target_mean is None


def test_malformed_input_degrades_loudly_to_unavailable():
    c = build_street_comparison(
        _verdict("PASS"), _profile(analyst_opinion_count="not-a-number"),
    )
    _assert_unavailable(c, "comparison_error")


def test_no_verdict_with_no_street_data_still_has_a_block():
    profile = {"field_state": {}}
    c = build_street_comparison(_verdict("NO_VERDICT"), profile)
    _assert_unavailable(c, "no_rating")
    assert c.room_stance == "no_call"


# ── the bank-site stamp ───────────────────────────────────────────────────


def test_stamped_verdict_carries_the_comparison_and_round_trips():
    stamped = room_runner._stamp_next_convene_basis(_verdict("APPROVE"), _profile("sell"), None)
    assert stamped.street_comparison is not None
    assert stamped.street_comparison.approved_against_street_sell is True
    again = Verdict.model_validate_json(stamped.model_dump_json())
    assert again.street_comparison == stamped.street_comparison


def test_stamp_without_street_data_still_says_so():
    profile = _profile()
    profile["field_state"] = {"run_date": "live"}
    stamped = room_runner._stamp_next_convene_basis(_verdict("PASS"), profile, None)
    assert stamped.street_comparison.status == "unavailable"


# ── never an agent input ──────────────────────────────────────────────────

# What a comparison would leave in a prompt if it leaked: its source label, its
# labels, and its enum words.
_LEAK_MARKERS = (
    STREET_SOURCE_LABEL, "sell-side analyst consensus", "approved_against_street_sell",
    "reasons_from_narrow_answers", "street_comparison", "How the Street rates",
)


def _all_prompts(profile: dict) -> list[tuple[str, str]]:
    out = []
    trade = {"size_pct": 3.0, "entry": 100.0, "stop": 94.0}
    for agent_id in sorted(_PHASE_FOR_AGENT, key=lambda a: a.value):
        system_prompt, messages = build_room_messages(
            agent_id=agent_id, mandate=_mandate(), user_id=None, ticker="MSFT",
            profile=profile, transcript=[], trade_proposal=trade,
        )
        out.append((agent_id.value, "\n".join(
            [system_prompt, *(str(getattr(m, "content", m)) for m in messages)])))
    system_prompt, messages, _rows = build_risk_officer_messages(
        mandate=_mandate(), ticker="MSFT", profile=profile, transcript=[], trade_proposal=trade,
    )
    out.append(("risk_officer", "\n".join(
        [system_prompt, *(str(getattr(m, "content", m)) for m in messages)])))
    return out


def test_no_prompt_built_after_the_stamp_carries_the_comparison():
    """Stamp a verdict (as the bank site does), then build every agent prompt from
    the SAME profile: nothing of the comparison, and still nothing of the Street."""
    profile = _profile("sell")
    stamped = room_runner._stamp_next_convene_basis(_verdict("APPROVE"), profile, None)
    assert stamped.street_comparison.status == "available"
    prompts = _all_prompts(profile)
    assert len(prompts) == len(_PHASE_FOR_AGENT) + 1
    for who, text in prompts:
        assert "Fact sheet as of 2026-11-18" in text or who == "risk_officer"
        for marker in _LEAK_MARKERS:
            assert marker not in text, f"{who}: {marker!r} reached the prompt"
        assert "987.65" not in text, f"{who}: Street target reached the prompt"


def test_building_the_comparison_does_not_touch_the_profile():
    profile = _profile("sell")
    before = copy.deepcopy(profile)
    build_street_comparison(_verdict("APPROVE"), profile)
    room_runner._stamp_next_convene_basis(_verdict("APPROVE"), profile, None)
    assert profile == before
    assert "street_comparison" not in profile


def test_only_the_post_verdict_modules_may_name_the_comparison():
    """Static fence: a prompt builder (or anything else) that starts reading the
    comparison fails here. Allowed: the schema, the builder, and the runner's two
    lines (import + the bank-site stamp)."""
    app = Path(__file__).resolve().parents[2] / "app"
    pattern = re.compile(r"street_comparison|StreetComparison|STREET_SOURCE_LABEL")
    allowed_whole = {
        app / "schemas" / "room.py",
        app / "services" / "street_comparison.py",
        app / "services" / "numeric_provenance.py",
    }
    runner = app / "services" / "room_runner.py"
    offenders = []
    for path in app.rglob("*.py"):
        if path in allowed_whole:
            continue
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            if not pattern.search(line):
                continue
            if path == runner and (
                line.startswith("from app.services.street_comparison import")
                or '"street_comparison": build_street_comparison(verdict, profile)' in line
                or line.lstrip().startswith("#")
            ):
                continue
            offenders.append(f"{path.relative_to(app)}:{lineno}: {line.strip()}")
    assert not offenders, "the Street comparison is post-verdict only:\n" + "\n".join(offenders)


def test_agent_ids_are_what_the_fence_expects():
    # Guards the guard: if the roster grows, _all_prompts must still cover it.
    assert AgentId.PORTFOLIO_MANAGER in _PHASE_FOR_AGENT
