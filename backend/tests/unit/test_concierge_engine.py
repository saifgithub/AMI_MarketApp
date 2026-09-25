"""Tests for the scripted Concierge engine — full happy path + classifiers."""

from app.schemas.mandate import Compliance, Horizon, PrimaryGoal
from app.schemas.onboarding import (
    ConversationStep,
    OnboardingSession,
)
from app.services.concierge_engine import (
    _NEXT_STEP,
    Q6_CHIPS,
    Q7_CHIPS,
    Q7_TEXT,
    _build_readback_summary,
    _DRAWDOWN_PCT_TO_TIER,
    _GOAL_TIER,
    _HORIZON_TIER,
    _derive_risk_score,
    _parse_constraints,
    _question_message,
    make_welcome_messages,
    process_answer,
    q6_text,
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



# ──────────────────────────────────────────────────────────────────────────
# CR228 — _derive_risk_score widened beyond the three Q3-Q5 scenario answers
# ──────────────────────────────────────────────────────────────────────────


def test_cr228_q6_suggestion_uses_scenario_only_base():
    """The Q6 question is generated BEFORE the user answers it — `max_drawdown_pct`
    is not in `session.answers` yet, so the suggestion shown in `q6_text` must
    fall back to the scenario score with no drawdown nudge. `horizon` and
    `primary_goal` (from Q1/Q2) ARE already present at this call site, so this
    fixture deliberately picks NEUTRAL answers for both (`_HORIZON_TIER["long"]`
    and `_GOAL_TIER["retirement"]` both resolve to 3, the do-nothing nudge) so
    the suggestion isolates the scenario-only base rather than also exercising
    those two nudges."""
    session = OnboardingSession()
    for step, answer in [
        (ConversationStep.WELCOME, "yes"),
        (ConversationStep.Q1_GOAL, "Save for retirement"),
        (ConversationStep.Q2_HORIZON, "3–10 years"),
        (ConversationStep.Q3_SCENARIO_DRAWDOWN, "Hold and wait"),
        (ConversationStep.Q4_SCENARIO_REGRET, "About the same"),
        (ConversationStep.Q5_SCENARIO_CONCENTRATION, "30% (balanced)"),
    ]:
        _next, message, _readback = process_answer(session, step, answer)
    assert "max_drawdown_pct" not in session.answers
    # scenario-only base: drawdown_response=3, concentration=3, regret=0 -> 3
    # -> q6_text's suggestion table (:101) maps risk_score 3 to 30%. Audit round
    # 1 MINOR-1: the old `"30%" in x or "sounds like a fit" in x` was vacuously
    # true for every risk_score, since the second disjunct is unconditional text
    # in q6_text — this asserts the exact suggested figure instead.
    assert "30% sounds like a fit" in message.content


def test_cr228_q6_suggestion_differs_for_a_different_scenario_profile():
    """The other half of the MINOR-1 fix: a single profile passing is not proof
    the suggestion table is exercised at all. A maximally risk-averse scenario
    profile (drawdown_response=1, concentration=1, regret=-1 -> base score 1)
    must suggest a DIFFERENT figure than the balanced profile above. Q2 is
    "3-10 years" (neutral, not "10+ years"/very_long, which is itself a +1
    nudge) so this isolates the scenario-only base exactly as the test above
    does."""
    session = OnboardingSession()
    for step, answer in [
        (ConversationStep.WELCOME, "yes"),
        (ConversationStep.Q1_GOAL, "Save for retirement"),
        (ConversationStep.Q2_HORIZON, "3–10 years"),
        (ConversationStep.Q3_SCENARIO_DRAWDOWN, "Sell everything"),
        (ConversationStep.Q4_SCENARIO_REGRET, "Losing in feels worse"),
        (ConversationStep.Q5_SCENARIO_CONCENTRATION, "10% (cautious)"),
    ]:
        _next, message, _readback = process_answer(session, step, answer)
    assert "10% sounds like a fit" in message.content
    assert "30% sounds like a fit" not in message.content


def test_cr228_scenario_only_base_matches_the_pre_widening_rounding_order():
    """Audit round 1 MAJOR-1: Change 2 was described as adding bounded nudges
    'around the unchanged scenario-derived base', but an early version rounded
    (a+c)/2 and added asym in the opposite order, silently moving the score for
    10 of these 45 combinations with ZERO nudge inputs present — including a
    loss-averse profile (regret_asymmetry=-1) landing a HIGHER score, the wrong
    direction for CR228's own stated purpose. Pins the full reachable space
    (drawdown_response 1-5, regret_asymmetry -1/0/1, concentration_tolerance
    1/3/5 — the only values `_classify_drawdown_response`/`_classify_regret`/
    `_classify_concentration` can produce) against the pre-CR228 formula,
    with `session.answers` empty so no nudge can fire."""
    expected = {
        (1, -1, 1): 1, (1, -1, 3): 1, (1, -1, 5): 2,
        (1, 0, 1): 1, (1, 0, 3): 2, (1, 0, 5): 3,
        (1, 1, 1): 2, (1, 1, 3): 3, (1, 1, 5): 4,
        (2, -1, 1): 1, (2, -1, 3): 1, (2, -1, 5): 3,
        (2, 0, 1): 2, (2, 0, 3): 2, (2, 0, 5): 4,
        (2, 1, 1): 3, (2, 1, 3): 3, (2, 1, 5): 5,
        (3, -1, 1): 1, (3, -1, 3): 2, (3, -1, 5): 3,
        (3, 0, 1): 2, (3, 0, 3): 3, (3, 0, 5): 4,
        (3, 1, 1): 3, (3, 1, 3): 4, (3, 1, 5): 5,
        (4, -1, 1): 1, (4, -1, 3): 3, (4, -1, 5): 3,
        (4, 0, 1): 2, (4, 0, 3): 4, (4, 0, 5): 4,
        (4, 1, 1): 3, (4, 1, 3): 5, (4, 1, 5): 5,
        (5, -1, 1): 2, (5, -1, 3): 3, (5, -1, 5): 4,
        (5, 0, 1): 3, (5, 0, 3): 4, (5, 0, 5): 5,
        (5, 1, 1): 4, (5, 1, 3): 5, (5, 1, 5): 5,
    }
    assert len(expected) == 45
    for (drawdown_response, regret_asymmetry, concentration_tolerance), score in expected.items():
        session = OnboardingSession()
        session.risk_components_partial = {
            "drawdown_response": drawdown_response,
            "regret_asymmetry": regret_asymmetry,
            "concentration_tolerance": concentration_tolerance,
        }
        assert session.answers == {}
        assert _derive_risk_score(session) == score, (
            f"drawdown_response={drawdown_response} regret_asymmetry={regret_asymmetry} "
            f"concentration_tolerance={concentration_tolerance}: expected {score}, "
            f"got {_derive_risk_score(session)}"
        )


def test_cr228_nudge_tables_do_not_drift_from_their_source_vocabulary():
    """Audit round 1 MINOR-2: each of the three nudge lookup tables
    hand-restates a vocabulary owned elsewhere (the `Horizon`/`PrimaryGoal`
    enums, `_parse_drawdown_pct`'s five possible return values), and each
    lookup is `.get(value, 3)` — a value missing from the table silently
    becomes a neutral nudge, indistinguishable from a user who genuinely sits
    mid-scale. A later enum addition (e.g. a new `PrimaryGoal` member) would
    pass every other test in this file while silently going neutral here.
    This pins the key sets so that addition fails loudly instead."""
    assert set(_HORIZON_TIER) == {h.value for h in Horizon}
    assert set(_GOAL_TIER) == {g.value for g in PrimaryGoal}
    assert set(_DRAWDOWN_PCT_TO_TIER) == {10, 20, 30, 40, 50, 100}


def test_cr228_disagreeing_drawdown_answer_nudges_the_score_at_readback():
    """CR228's target: Q6's actual answer must be able to move the score, not
    only take a suggestion FROM it (the backwards-causality gap the CR
    documents). Scenario answers alone give risk_score=3 (as in
    test_happy_path_retirement_long_only); overriding Q6 to "No cap" (100%,
    the top drawdown tier) against those same mid scenario answers must push
    the readback score up from that scenario-only baseline.

    Audit round 2 MAJOR-2: this test's Q2 used to be "10+ years" (very_long,
    itself a +1 nudge tier), so it passed at round 2 for the WRONG reason —
    Q2 was carrying the movement while Q6's own contribution (after the /2
    damping) was too weak to cross a rounding boundary on its own. Q2 is now
    the neutral "3–10 years" so this test isolates Q6's own influence, as its
    docstring always claimed it did."""
    session = OnboardingSession()
    summary = _walk_through_express_path(
        session,
        {
            ConversationStep.WELCOME: "Yes, let's go",
            ConversationStep.Q1_GOAL: "Save for retirement",
            ConversationStep.Q2_HORIZON: "3–10 years",
            ConversationStep.Q3_SCENARIO_DRAWDOWN: "Hold and wait",
            ConversationStep.Q4_SCENARIO_REGRET: "About the same",
            ConversationStep.Q5_SCENARIO_CONCENTRATION: "30% (balanced)",
            ConversationStep.Q6_MAX_DRAWDOWN: "No cap",
            ConversationStep.Q7_CONSTRAINTS: "Long-only",
        },
    )
    assert summary is not None
    assert summary["max_drawdown_pct"] == 100
    assert summary["risk_score"] > 3, (
        "a user who accepted mid scenario answers but then asked for NO drawdown "
        "cap should read back a higher score than the scenario-only baseline — "
        "otherwise Q6's actual answer still has no path back into the score"
    )


def test_cr228_offered_50_picks_10_the_scores_moves():
    """Audit round 2 MAJOR-2, the CR's own stated purpose verbatim
    (README.md: 'A user offered 50% who picks 10% is saying the score is
    wrong, and nothing listens'). At neutral Q1/Q2 (both nudge-tier 3, the
    documented do-nothing value) and a scenario base that suggests 50% (risk
    score 5 -> q6_text's suggestion table maps 5 to 50), picking 10% instead
    must move the readback score DOWN from the suggestion-implied baseline —
    the exact behaviour round 1's fix silently made impossible (0/45
    reachable bases could move at neutral Q1/Q2, per the auditor's
    measurement) until the /2 damping was removed."""
    session = OnboardingSession()
    for step, answer in [
        (ConversationStep.WELCOME, "yes"),
        (ConversationStep.Q1_GOAL, "Save for retirement"),
        (ConversationStep.Q2_HORIZON, "3–10 years"),
        (ConversationStep.Q3_SCENARIO_DRAWDOWN, "Buy aggressively — it's on sale"),
        (ConversationStep.Q4_SCENARIO_REGRET, "About the same"),
        (ConversationStep.Q5_SCENARIO_CONCENTRATION, "60% (all-in)"),
    ]:
        _next, message, _readback = process_answer(session, step, answer)
    assert "50% sounds like a fit" in message.content, (
        "fixture must land on a base score of 5 (q6_text suggests 50%) for "
        "this test to actually probe the CR's own 'offered 50%, picks 10%' case"
    )
    baseline_score = _derive_risk_score(session)

    process_answer(session, ConversationStep.Q6_MAX_DRAWDOWN, "10%")
    process_answer(session, ConversationStep.Q7_CONSTRAINTS, "Long-only")
    summary = _build_readback_summary(session)
    assert summary["max_drawdown_pct"] == 10
    assert summary["risk_score"] < baseline_score, (
        f"offered a 50%-implying baseline (score={baseline_score}), picking 10% "
        f"instead must move the score down — got {summary['risk_score']}, unchanged"
    )


def test_cr228_scenario_answers_remain_the_dominant_signal():
    """The nudge must not let goal/horizon/drawdown alone override three
    scenario answers that all say "very conservative" — bounded influence, not
    a competing formula. All three new inputs pushed to their most aggressive
    values against the most conservative scenario answers must not reach the
    ceiling."""
    session = OnboardingSession()
    summary = _walk_through_express_path(
        session,
        {
            ConversationStep.WELCOME: "yes",
            ConversationStep.Q1_GOAL: "Learn to trade short-term",  # highest goal tier
            ConversationStep.Q2_HORIZON: "<1 year",  # highest horizon tier
            ConversationStep.Q3_SCENARIO_DRAWDOWN: "Sell everything",
            ConversationStep.Q4_SCENARIO_REGRET: "Losing in feels worse",
            ConversationStep.Q5_SCENARIO_CONCENTRATION: "10% (cautious)",
            ConversationStep.Q6_MAX_DRAWDOWN: "No cap",  # highest drawdown tier
            ConversationStep.Q7_CONSTRAINTS: "Long-only",
        },
    )
    assert summary is not None
    assert summary["risk_score"] <= 2, (
        "three maximally-aggressive non-scenario inputs pushed a scenario-only "
        "score of 1 no higher than 2 — the scenario answers must stay dominant"
    )


def test_def129_mandate_carries_no_briefing_field():
    """The field went with the question — nothing will be wired to send it."""
    from app.schemas.mandate import Mandate

    assert "daily_briefing" not in Mandate.model_fields


def test_def418_all_five_risk_tiers_have_distinct_suggestions_in_q6_chips():
    """DEF418: tiers 4 and 5 previously both suggested 50%, violating CR228's
    requirement for five distinct tiers. Saiful ruled 2026-09-24: '4→40%, 5→50%'.
    This test pins that all five suggestions (1→10%, 2→20%, 3→30%, 4→40%, 5→50%)
    are (a) strictly increasing, (b) each present in Q6_CHIPS, and (c) that the
    40% parser accepts the new chip."""
    import re
    suggestions = {}
    for risk_score in range(1, 6):
        text = q6_text(risk_score)
        m = re.search(r"(\d+)% sounds like a fit", text)
        assert m, f"could not find suggestion in q6_text({risk_score}): {text}"
        suggestions[risk_score] = int(m.group(1))

    assert suggestions == {1: 10, 2: 20, 3: 30, 4: 40, 5: 50}, (
        f"expected {{1: 10, 2: 20, 3: 30, 4: 40, 5: 50}}, got {suggestions}"
    )
    # All suggestions must be in the chip options (minus "No cap" which is parsed as 100)
    for risk_score, pct in suggestions.items():
        chip = f"{pct}%"
        assert chip in Q6_CHIPS, (
            f"tier {risk_score} suggests {pct}% but {chip} not in Q6_CHIPS={Q6_CHIPS}"
        )
    # Parser must accept the new 40% chip
    from app.services.concierge_engine import _parse_drawdown_pct
    assert _parse_drawdown_pct("40%") == 40
    assert _parse_drawdown_pct("40") == 40
    # Verify 40% maps to tier 4 in the nudge table
    assert _DRAWDOWN_PCT_TO_TIER[40] == 4


def test_def428_parse_drawdown_pct_reads_any_explicit_percentage():
    """DEF428: `_parse_drawdown_pct` used to substring-match only the six chip
    values and silently default to 30 for anything else — a typed "5%" or
    "45%" became an undisclosed 30% mandate. It must now parse ANY explicit
    1-100 percentage the user types, with or without "%"/"percent", decimals
    included.

    Round 2: a fractional answer rounds DOWN to a whole `int` (12.5 -> 12,
    not 12.5) — `Mandate.max_drawdown_pct` is now a whole-number percentage
    (U66 round-1 MAJOR-1: the old `Literal[10, 20, 30, 50, 100]` rejected
    every off-grid value, including every fraction, at claim/restart)."""
    from app.services.concierge_engine import _parse_drawdown_pct

    assert _parse_drawdown_pct("5%") == 5
    assert _parse_drawdown_pct("45%") == 45
    assert _parse_drawdown_pct("45") == 45
    assert _parse_drawdown_pct("12.5%") == 12
    assert _parse_drawdown_pct("12.5 percent") == 12
    assert _parse_drawdown_pct("12.9%") == 12  # floors, never rounds up
    assert _parse_drawdown_pct("83 percent") == 83
    assert _parse_drawdown_pct("no cap") == 100
    assert _parse_drawdown_pct("No Cap") == 100
    assert _parse_drawdown_pct("no limit") == 100
    assert isinstance(_parse_drawdown_pct("12.5%"), int)


def test_def428_parse_drawdown_pct_rejects_garbage_and_out_of_range():
    """Unparseable or out-of-range text must return None, never a fabricated
    value — the caller re-asks rather than storing a mandate the user never
    gave."""
    from app.services.concierge_engine import _parse_drawdown_pct

    assert _parse_drawdown_pct("not sure") is None
    assert _parse_drawdown_pct("whatever you think") is None
    assert _parse_drawdown_pct("") is None
    assert _parse_drawdown_pct("banana") is None
    assert _parse_drawdown_pct("150%") is None
    assert _parse_drawdown_pct("0%") is None
    assert _parse_drawdown_pct("-10%") is None


def test_def428_money_and_loose_numbers_are_not_read_as_a_percentage():
    """A number only becomes a drawdown when it is marked as a percentage or is
    the entire answer. Money and incidental numbers must re-ask, not become a
    silent 10% or 5% mandate."""
    from app.services.concierge_engine import _parse_drawdown_pct

    assert _parse_drawdown_pct("I could lose $10,000") is None
    assert _parse_drawdown_pct("5k") is None
    assert _parse_drawdown_pct("maybe 2 or 3 months of salary") is None
    assert _parse_drawdown_pct("about 20") is None
    assert _parse_drawdown_pct("$15%") is None
    assert _parse_drawdown_pct("I'd say 25%") == 25
    assert _parse_drawdown_pct("somewhere around 15 percent") == 15
    assert _parse_drawdown_pct("between 20% and 30%") == 20
    assert _parse_drawdown_pct("10-15%") == 10
    assert _parse_drawdown_pct("10% to 15%") == 10
    assert _parse_drawdown_pct("10 to 15 percent") == 10
    assert _parse_drawdown_pct(" 45 ") == 45


def test_def428_unparseable_q6_answer_re_asks_instead_of_defaulting_to_30():
    """The end-to-end fix: an unparseable Q6 answer must NOT silently become
    a 30% mandate. `process_answer` must keep the user on Q6 (current_step
    does not advance to Q7) and must NOT write `max_drawdown_pct` into
    `session.answers`."""
    session = OnboardingSession(current_step=ConversationStep.Q6_MAX_DRAWDOWN)

    next_step, message, readback = process_answer(
        session, ConversationStep.Q6_MAX_DRAWDOWN, "I dunno, whatever's fine"
    )

    assert next_step == ConversationStep.Q6_MAX_DRAWDOWN, (
        "unparseable Q6 answer must re-ask Q6, not silently advance to Q7"
    )
    assert readback is None
    assert "max_drawdown_pct" not in session.answers, (
        "an unparseable answer must never be stored as a mandate value"
    )
    assert message.step == ConversationStep.Q6_MAX_DRAWDOWN
    assert message.chips == Q6_CHIPS


def test_def428_explicit_percentage_typed_freeform_is_honoured_exactly():
    """A typed "5%" must become max_drawdown_pct=5, not the nearest chip (10%)
    and not the old silent default of 30."""
    session = OnboardingSession(current_step=ConversationStep.Q6_MAX_DRAWDOWN)

    next_step, message, readback = process_answer(session, ConversationStep.Q6_MAX_DRAWDOWN, "5%")

    assert next_step == ConversationStep.Q7_CONSTRAINTS
    assert session.answers["max_drawdown_pct"] == 5


def test_def428_explicit_percentage_45_is_honoured_not_snapped_to_40_or_50():
    session = OnboardingSession(current_step=ConversationStep.Q6_MAX_DRAWDOWN)

    process_answer(session, ConversationStep.Q6_MAX_DRAWDOWN, "45%")

    assert session.answers["max_drawdown_pct"] == 45


def test_def428_decimal_percentage_12_5_rounds_down_to_whole_percent():
    """Round 2: 12.5% floors to 12 (the stricter cap), not 12.5 — a
    fractional `max_drawdown_pct` can never be persisted (the schema is a
    whole-number int; U66 round-1 MAJOR-1 found the Literal rejecting it
    outright at claim/restart, which was worse: a silent fallback to 30%)."""
    session = OnboardingSession(current_step=ConversationStep.Q6_MAX_DRAWDOWN)

    process_answer(session, ConversationStep.Q6_MAX_DRAWDOWN, "12.5%")

    assert session.answers["max_drawdown_pct"] == 12
    assert isinstance(session.answers["max_drawdown_pct"], int)


def test_def428_no_cap_still_gives_100_after_the_fix():
    """DEF418/DEF428 regression guard: 'No cap' must keep mapping to 100."""
    session = OnboardingSession(current_step=ConversationStep.Q6_MAX_DRAWDOWN)

    next_step, _message, _readback = process_answer(
        session, ConversationStep.Q6_MAX_DRAWDOWN, "No cap"
    )

    assert next_step == ConversationStep.Q7_CONSTRAINTS
    assert session.answers["max_drawdown_pct"] == 100


def test_def428_chip_values_still_all_parse_and_advance():
    """Regression guard: every Q6 chip must still parse and advance the
    conversation exactly as before this fix."""
    expected = {"10%": 10, "20%": 20, "30%": 30, "40%": 40, "50%": 50, "No cap": 100}
    for chip, expected_pct in expected.items():
        session = OnboardingSession(current_step=ConversationStep.Q6_MAX_DRAWDOWN)
        next_step, _message, _readback = process_answer(
            session, ConversationStep.Q6_MAX_DRAWDOWN, chip
        )
        assert next_step == ConversationStep.Q7_CONSTRAINTS, f"chip {chip!r} must advance"
        assert session.answers["max_drawdown_pct"] == expected_pct


def test_def428_re_ask_then_valid_answer_completes_the_interview():
    """A garbage answer followed by a valid one must let the user proceed —
    the re-ask is not a dead end."""
    session = OnboardingSession(current_step=ConversationStep.Q6_MAX_DRAWDOWN)

    next_step, _message, _readback = process_answer(
        session, ConversationStep.Q6_MAX_DRAWDOWN, "garbage answer"
    )
    assert next_step == ConversationStep.Q6_MAX_DRAWDOWN
    assert "max_drawdown_pct" not in session.answers

    next_step, _message, _readback = process_answer(session, ConversationStep.Q6_MAX_DRAWDOWN, "25%")
    assert next_step == ConversationStep.Q7_CONSTRAINTS
    assert session.answers["max_drawdown_pct"] == 25


# ──────────────────────────────────────────────────────────────────────────
# DEF428 round 2 — U66 round-1 MAJOR-1: the parser accepted any 1-100 value
# but `Mandate.max_drawdown_pct` stayed `Literal[10, 20, 30, 50, 100]`, so an
# off-grid answer (including the pre-existing "40%" chip) raised
# ValidationError at claim/restart, silently reached as a permanent 30%. Fix:
# widen the schema to `int, ge=1, le=100`. These tests drive an off-grid Q6
# answer all the way through `session_to_mandate_dict` -> `Mandate.model_validate`
# — the "parser output subset schema" property U66 asked for, so a future
# reader can no longer just eyeball the parser and assume it's covered.
# ──────────────────────────────────────────────────────────────────────────


def _run_q6_then_q7(session: OnboardingSession, q6_answer: str) -> OnboardingSession:
    process_answer(session, ConversationStep.Q6_MAX_DRAWDOWN, q6_answer)
    process_answer(session, ConversationStep.Q7_CONSTRAINTS, "no hard rules")
    return session


def test_def428_round2_offgrid_45_survives_mandate_model_validate():
    """The exact regression U66 drove for real: '45%' must become a real,
    persistable Mandate — not a ValidationError swallowed into a silent 30%."""
    from uuid import uuid4

    from app.schemas.mandate import Mandate

    session = OnboardingSession(current_step=ConversationStep.Q6_MAX_DRAWDOWN)
    _run_q6_then_q7(session, "45%")
    session.completed = True

    mandate_dict = session_to_mandate_dict(session, user_id=uuid4())
    mandate = Mandate.model_validate(mandate_dict)  # must not raise

    assert mandate.max_drawdown_pct == 45


def test_def428_round2_every_q6_chip_and_offgrid_value_survives_model_validate():
    """Parser-output-subset-schema, driven as a property: every Q6 chip value
    AND a spread of off-grid values (including the "40%" chip, which the
    audit's 'Recorded, not scored' finding flagged as never persistable
    before this fix) must construct a valid Mandate."""
    from uuid import uuid4

    from app.schemas.mandate import Mandate

    for answer, expected in [
        ("10%", 10), ("20%", 20), ("30%", 30), ("40%", 40), ("50%", 50),
        ("No cap", 100), ("5%", 5), ("45%", 45), ("12.5%", 12), ("83%", 83),
        ("1%", 1), ("100%", 100),
    ]:
        session = OnboardingSession(current_step=ConversationStep.Q6_MAX_DRAWDOWN)
        _run_q6_then_q7(session, answer)
        session.completed = True

        mandate_dict = session_to_mandate_dict(session, user_id=uuid4())
        mandate = Mandate.model_validate(mandate_dict)

        assert mandate.max_drawdown_pct == expected, f"answer={answer!r}"


def test_def428_round2_max_drawdown_pct_out_of_bounds_still_rejected():
    """Widening the schema must not remove its floor/ceiling — 0 and 101 are
    still invalid `max_drawdown_pct` values (a PATCH client could try either
    even though the interview itself can never produce them)."""
    import pytest
    from pydantic import ValidationError
    from uuid import uuid4

    from app.schemas.mandate import Mandate

    session = OnboardingSession(current_step=ConversationStep.Q6_MAX_DRAWDOWN)
    _run_q6_then_q7(session, "25%")
    session.completed = True
    mandate_dict = session_to_mandate_dict(session, user_id=uuid4())

    for bad in (0, 101, -5, 999):
        with pytest.raises(ValidationError):
            Mandate.model_validate({**mandate_dict, "max_drawdown_pct": bad})


def test_def428_round2_offgrid_drawdown_nudges_by_nearest_lower_tier():
    """`_DRAWDOWN_PCT_TO_TIER.get(dd, 3)` used to send EVERY off-grid value to
    a flat neutral tier-3 nudge, indifferent to whether the user typed 11% or
    99%. It must now nudge by the tier of the nearest chip AT OR BELOW the
    typed value — the more conservative neighbour."""
    from app.services.concierge_engine import _drawdown_tier

    assert _drawdown_tier(10) == 1  # exact chip
    assert _drawdown_tier(15) == 1  # between 10 (tier 1) and 20 (tier 2) -> lower
    assert _drawdown_tier(19) == 1
    assert _drawdown_tier(20) == 2  # exact chip
    assert _drawdown_tier(45) == 4  # between 40 (tier 4) and 50 (tier 5) -> lower
    assert _drawdown_tier(99) == 5  # above the highest chip below 100
    assert _drawdown_tier(100) == 5  # exact chip
    assert _drawdown_tier(5) == 1  # below the lowest chip -> floors to tier 1
    assert _drawdown_tier(1) == 1


def test_def428_round2_readback_never_fabricates_a_missing_drawdown():
    """MINOR-1: `_build_readback_summary` must refuse to invent a default
    `max_drawdown_pct` (the old `.get(..., 30)`) — a session that somehow
    reaches it with no recorded answer must raise loudly, not silently
    manufacture a real mandate value nobody typed."""
    import pytest

    from app.services.concierge_engine import (
        MissingMandateAnswerError,
        _build_readback_summary,
    )

    session = OnboardingSession(current_step=ConversationStep.READBACK)
    session.answers["primary_goal"] = "retirement"
    session.answers["horizon"] = "long"
    # max_drawdown_pct deliberately never set.

    with pytest.raises(MissingMandateAnswerError):
        _build_readback_summary(session)
