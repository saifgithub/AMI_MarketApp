"""Tests for the scripted Concierge engine — full happy path + classifiers."""

from app.schemas.mandate import Compliance
from app.schemas.onboarding import (
    ConversationStep,
    OnboardingSession,
)
from app.services.concierge_engine import (
    _NEXT_STEP,
    Q7_CHIPS,
    Q7_TEXT,
    _parse_constraints,
    _question_message,
    make_welcome_messages,
    process_answer,
    session_to_mandate_dict,
)

# CR114: the chip a user taps IS the answer string the parser sees. Nothing
# links the two, so this table is the contract — rewording a chip without a
# matching parser token silently produces a mandate that ignores the tap.
_CHIP_TO_FLAG = {
    "ONLY halal / Sharia-compliant": "halal",
    "ONLY ESG-leaning": "esg_lite",
    "ONLY liquid names (no microcaps)": "liquid_only",
    "ONLY long positions (no shorting)": "long_only",
    "NEVER tobacco, alcohol or gambling": "no_tobacco_alcohol_gambling",
    "NEVER fossil fuels": "no_fossil_fuels",
    "No hard rules": None,
}
_BOOLEAN_FLAGS = {
    "halal",
    "esg_lite",
    "no_tobacco_alcohol_gambling",
    "no_fossil_fuels",
    "long_only",
    "liquid_only",
}


def _walk_through_express_path(session: OnboardingSession, answers: dict[ConversationStep, str]):
    """Helper — submit the welcome plus all 7 questions; return the readback."""
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
        },
    )
    assert summary is not None
    assert summary["risk_score"] == 5
    assert summary["max_drawdown_pct"] == 50
    assert summary["compliance"]["halal"] is True


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
        },
    )
    assert summary is not None
    assert summary["risk_score"] == 1
    assert summary["max_drawdown_pct"] == 10


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
        "plan",
        "created_at",
        "updated_at",
    }
    assert required_keys.issubset(md.keys())
    assert md["risk_score"] == 3


# ──────────────────────────────────────────────────────────────────────────
# CR114 — Q7's chips must mean what the question asks, and parse as they read
# ──────────────────────────────────────────────────────────────────────────


def test_cr114_every_shipped_chip_is_in_the_contract_table():
    """Vacuity guard. Every assertion below iterates `_CHIP_TO_FLAG`; if a chip
    is added to the app and not to the table, those loops would still pass while
    testing nothing. This is the check that notices."""
    assert set(Q7_CHIPS) == set(_CHIP_TO_FLAG), (
        "Q7_CHIPS and the contract table have drifted. A chip the table does "
        "not know about is a chip nothing below is testing."
    )


# The two RESTRICTION flags: `Compliance` defaults both to True, so they are
# in force unless the user opts out. CR220 — before it, `_parse_constraints`
# returned them as bare keyword hits, so "No hard rules" produced
# long_only=False/liquid_only=False and an ONBOARDED user came out LESS
# constrained than one who never onboarded at all.
_RESTRICTION_FLAGS = {"long_only", "liquid_only"}
_OPT_IN_FLAGS = _BOOLEAN_FLAGS - _RESTRICTION_FLAGS


def test_cr114_each_chip_sets_exactly_the_flag_it_names():
    """The defect CR114 fixes: the chip said one thing and the parser keyed off
    a substring that may or may not have survived a rewording. Tap each chip
    exactly as shipped and assert the compliance flags that come back.

    CR220 asserts against the RESOLVED `Compliance` object rather than the raw
    dict, because the raw dict is now deliberately partial — the restriction
    flags are omitted so the schema default stands. What is enforced is the
    resolved object, so that is what the chip contract must be pinned to."""
    for chip, expected_flag in _CHIP_TO_FLAG.items():
        resolved = Compliance(**_parse_constraints(chip))
        raised = {f for f in _OPT_IN_FLAGS if getattr(resolved, f)}
        expected = set() if expected_flag in (None, *_RESTRICTION_FLAGS) else {expected_flag}
        assert raised == expected, (
            f'chip "{chip}" raised {raised or "{}"}, expected '
            f'{expected or "{}"} — the chip text and _parse_constraints '
            f"have drifted apart"
        )
        # A restriction chip must leave its own flag ON; no chip may turn one OFF.
        for flag in _RESTRICTION_FLAGS:
            assert getattr(resolved, flag) is True, (
                f'chip "{chip}" turned {flag} OFF. No Q7 chip may loosen a '
                f"restriction — that is the CR220 defect."
            )


def test_cr220_no_hard_rules_matches_the_never_onboarded_default():
    """The CR220 defect, stated directly: a user who answers "No hard rules"
    must end up with exactly the compliance a user who never onboarded gets
    from `get_or_default()`. Before the fix they got long_only=False and
    liquid_only=False — strictly LESS constrained for having done the
    interview.

    Mutation check: restoring the bare `"long-only" in t` / `"liquid" in t`
    returns in `_parse_constraints` turns this red."""
    resolved = Compliance(**_parse_constraints("No hard rules"))
    assert resolved.model_dump() == Compliance().model_dump()
    assert resolved.long_only is True
    assert resolved.liquid_only is True


def test_cr220_restriction_flags_are_omitted_not_falsified():
    """The mechanism behind the fix: `_parse_constraints` must OMIT a
    restriction flag it has no evidence about, so the schema default applies.
    Returning it as `False` is what made the guard at the call site useless."""
    parsed = _parse_constraints("No hard rules")
    assert "long_only" not in parsed
    assert "liquid_only" not in parsed


def test_cr220_an_explicit_opt_out_is_still_honoured():
    """The fix must not make the restrictions uncoachable — the interview is
    the one place a user can loosen them. An explicit request still lands."""
    assert Compliance(**_parse_constraints("I want to short stocks")).long_only is False


def test_cr220_ambiguous_short_language_does_not_loosen():
    """"I don't want shorting" contains the word "short" but is a request FOR
    the restriction. Inferring the opt-out from the bare word would be the
    mirror image of the CR220 defect."""
    assert Compliance(**_parse_constraints("I don't want shorting")).long_only is True


def test_cr220_readback_still_names_a_restriction_that_is_in_force():
    """Promise-vs-mechanism (the DEF158 shape). `_parse_constraints` now omits
    the restriction keys, so the readback summary must resolve them through the
    schema — otherwise "long-only" silently drops out of the flags the user
    confirms while still being ENFORCED."""
    session = OnboardingSession()
    summary = _walk_through_express_path(
        session,
        {
            ConversationStep.WELCOME: "yes",
            ConversationStep.Q1_GOAL: "retire",
            ConversationStep.Q2_HORIZON: "10+ years",
            ConversationStep.Q3_SCENARIO_DRAWDOWN: "Hold and wait",
            ConversationStep.Q4_SCENARIO_REGRET: "About the same",
            ConversationStep.Q5_SCENARIO_CONCENTRATION: "30%",
            ConversationStep.Q6_MAX_DRAWDOWN: "30%",
            ConversationStep.Q7_CONSTRAINTS: "No hard rules",
        },
    )
    assert summary["compliance"]["long_only"] is True
    assert summary["compliance"]["liquid_only"] is True


def test_cr114_every_compliance_flag_is_reachable_from_some_chip():
    """A flag no chip can set is a rule the interview cannot capture."""
    reachable = {f for f in _CHIP_TO_FLAG.values() if f is not None}
    assert reachable == _BOOLEAN_FLAGS


def test_cr114_question_asks_for_both_directions():
    """The old text asked only what you'd NEVER invest in while five of seven
    chips were inclusions — picking "Halal only" literally answered the
    inverse of the question."""
    assert "ONLY" in Q7_TEXT and "NEVER" in Q7_TEXT
    assert "NEVER want to invest in" not in Q7_TEXT
    only_chips = [c for c in Q7_CHIPS if c.startswith("ONLY")]
    never_chips = [c for c in Q7_CHIPS if c.startswith("NEVER")]
    assert only_chips and never_chips, "both directions must be offered"


# ──────────────────────────────────────────────────────────────────────────
# DEF129 — onboarding must not promise a daily briefing it cannot send
# ──────────────────────────────────────────────────────────────────────────


def test_def129_no_step_offers_a_briefing():
    """Structural, not textual: there is no step left that could ask."""
    assert not hasattr(ConversationStep, "Q8_BRIEFING")
    assert "q8_briefing" not in {s.value for s in ConversationStep}


def test_def129_q7_is_the_last_question():
    assert _NEXT_STEP[ConversationStep.Q7_CONSTRAINTS] == ConversationStep.READBACK


def test_def129_every_question_step_still_renders():
    """Removing a step from the map must not leave one that raises when asked."""
    session = OnboardingSession()
    for step in ConversationStep:
        if step in (ConversationStep.WELCOME, ConversationStep.READBACK,
                    ConversationStep.COMPLETE):
            continue
        assert _question_message(step, session).content


def test_def129_readback_promises_no_briefing():
    """The readback is the screen the user is asked to confirm as correct. It
    used to close with "🎙️ Briefing: 07:00 daily briefing with voice" — a time
    the user never chose and a voice mode that cannot exist."""
    session = OnboardingSession()
    last_message = None
    for step, answer in [
        (ConversationStep.WELCOME, "yes"),
        (ConversationStep.Q1_GOAL, "retire"),
        (ConversationStep.Q2_HORIZON, "10+ years"),
        (ConversationStep.Q3_SCENARIO_DRAWDOWN, "Hold and wait"),
        (ConversationStep.Q4_SCENARIO_REGRET, "About the same"),
        (ConversationStep.Q5_SCENARIO_CONCENTRATION, "30%"),
        (ConversationStep.Q6_MAX_DRAWDOWN, "30%"),
        (ConversationStep.Q7_CONSTRAINTS, "ONLY halal / Sharia-compliant"),
    ]:
        _next, message, _readback = process_answer(session, step, answer)
        last_message = message

    assert last_message is not None
    assert last_message.step == ConversationStep.READBACK
    text = last_message.content.lower()
    for promise in ("briefing", "07:00", "voice", "🎙️"):
        assert promise not in text, f"readback still promises {promise!r}"
    assert "Edit briefing" not in last_message.chips
    # The readback still has to say something, or this guard passes on a blank.
    assert "halal-compliant only" in last_message.content


def test_def129_mandate_carries_no_briefing_field():
    """The field went with the question — nothing will be wired to send it."""
    from app.schemas.mandate import Mandate

    assert "daily_briefing" not in Mandate.model_fields
