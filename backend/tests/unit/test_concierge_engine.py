"""Tests for the scripted Concierge engine — full happy path + classifiers."""

from app.schemas.onboarding import (
    ConversationStep,
    OnboardingSession,
)
from app.services.concierge_engine import (
    make_welcome_messages,
    process_answer,
    session_to_mandate_dict,
)


def _walk_through_express_path(session: OnboardingSession, answers: dict[ConversationStep, str]):
    """Helper — submit all 8 answers; return final session + readback."""
    final_summary = None
    for step in [
        ConversationStep.WELCOME,
        ConversationStep.Q1_GOAL,
        ConversationStep.Q2_HORIZON,
        ConversationStep.Q3_SCENARIO_DRAWDOWN,
        ConversationStep.Q4_SCENARIO_REGRET,
        ConversationStep.Q5_SCENARIO_CONCENTRATION,
        ConversationStep.Q6_MAX_DRAWDOWN,
        ConversationStep.Q7_CONSTRAINTS,
        ConversationStep.Q8_BRIEFING,
    ]:
        ans = answers[step]
        _next, _msg, readback = process_answer(session, step, ans)
        if readback is not None:
            final_summary = readback
    return final_summary


def test_welcome_message_has_chips():
    welcome, first_q = make_welcome_messages()
    assert welcome.step == ConversationStep.WELCOME
    assert welcome.chips, "welcome should offer accelerator chips"
    assert first_q.step == ConversationStep.Q1_GOAL
    assert "What's bringing you here?" in first_q.content


def test_happy_path_retirement_long_only():
    session = OnboardingSession()
    summary = _walk_through_express_path(
        session,
        {
            ConversationStep.WELCOME: "Yes, let's go",
            ConversationStep.Q1_GOAL: "Save for retirement",
            ConversationStep.Q2_HORIZON: "10+ years",
            ConversationStep.Q3_SCENARIO_DRAWDOWN: "Hold and wait",
            ConversationStep.Q4_SCENARIO_REGRET: "About the same",
            ConversationStep.Q5_SCENARIO_CONCENTRATION: "30% (balanced)",
            ConversationStep.Q6_MAX_DRAWDOWN: "30%",
            ConversationStep.Q7_CONSTRAINTS: "Long-only",
            ConversationStep.Q8_BRIEFING: "Yes, text only",
        },
    )
    assert summary is not None
    assert summary["primary_goal"] == "retirement"
    assert summary["horizon"] == "very_long"
    assert summary["path"] == "long_horizon"
    assert summary["risk_score"] == 3
    assert summary["max_drawdown_pct"] == 30
    assert summary["compliance"]["long_only"] is True
    assert summary["compliance"]["halal"] is False


def test_happy_path_halal_aggressive():
    session = OnboardingSession()
    summary = _walk_through_express_path(
        session,
        {
            ConversationStep.WELCOME: "Yes",
            ConversationStep.Q1_GOAL: "Build long-term wealth",
            ConversationStep.Q2_HORIZON: "3–10 years",
            ConversationStep.Q3_SCENARIO_DRAWDOWN: "Buy more — it's on sale",
            ConversationStep.Q4_SCENARIO_REGRET: "Missing out feels worse",
            ConversationStep.Q5_SCENARIO_CONCENTRATION: "60% (all-in)",
            ConversationStep.Q6_MAX_DRAWDOWN: "50%",
            ConversationStep.Q7_CONSTRAINTS: "Halal only",
            ConversationStep.Q8_BRIEFING: "Yes, with voice",
        },
    )
    assert summary is not None
    assert summary["risk_score"] == 5
    assert summary["max_drawdown_pct"] == 50
    assert summary["compliance"]["halal"] is True
    assert summary["daily_briefing"]["enabled"] is True
    assert summary["daily_briefing"]["voice_id"] == "default"


def test_happy_path_conservative_panic():
    session = OnboardingSession()
    summary = _walk_through_express_path(
        session,
        {
            ConversationStep.WELCOME: "yes",
            ConversationStep.Q1_GOAL: "Save for retirement",
            ConversationStep.Q2_HORIZON: "10+ years",
            ConversationStep.Q3_SCENARIO_DRAWDOWN: "Sell everything",
            ConversationStep.Q4_SCENARIO_REGRET: "Losing in feels worse",
            ConversationStep.Q5_SCENARIO_CONCENTRATION: "10% (cautious)",
            ConversationStep.Q6_MAX_DRAWDOWN: "10%",
            ConversationStep.Q7_CONSTRAINTS: "Long-only",
            ConversationStep.Q8_BRIEFING: "Not now",
        },
    )
    assert summary is not None
    assert summary["risk_score"] == 1
    assert summary["max_drawdown_pct"] == 10
    assert summary["daily_briefing"]["enabled"] is False


def test_messages_recorded_in_session():
    session = OnboardingSession()
    process_answer(session, ConversationStep.WELCOME, "Yes")
    process_answer(session, ConversationStep.Q1_GOAL, "Save for retirement")
    # answer recording happened
    assert session.answers["primary_goal"] == "retirement"


def test_session_to_mandate_dict_shape():
    """The mandate dict produced from a completed session has the right keys."""
    session = OnboardingSession()
    _walk_through_express_path(
        session,
        {
            ConversationStep.WELCOME: "yes",
            ConversationStep.Q1_GOAL: "retire",
            ConversationStep.Q2_HORIZON: "10+ years",
            ConversationStep.Q3_SCENARIO_DRAWDOWN: "Hold and wait",
            ConversationStep.Q4_SCENARIO_REGRET: "About the same",
            ConversationStep.Q5_SCENARIO_CONCENTRATION: "30%",
            ConversationStep.Q6_MAX_DRAWDOWN: "30%",
            ConversationStep.Q7_CONSTRAINTS: "Long-only",
            ConversationStep.Q8_BRIEFING: "Yes, text only",
        },
    )
    md = session_to_mandate_dict(session, user_id="test-user")
    required_keys = {
        "user_id",
        "version",
        "display_name",
        "locale",
        "timezone",
        "primary_goal",
        "horizon",
        "path",
        "risk_score",
        "risk_components",
        "max_drawdown_pct",
        "compliance",
        "learning_style",
        "daily_briefing",
        "plan",
        "created_at",
        "updated_at",
    }
    assert required_keys.issubset(md.keys())
    assert md["risk_score"] == 3
