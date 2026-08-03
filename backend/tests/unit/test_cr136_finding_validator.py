"""CR136 M06 — allow-list validator: rounding paths, scale-aware lookup, register lexicon, LLM fallback.

Rev 3's digit-sequence validator was measured and deleted: it rejected 10–13 of
the 25 digit runs in the CR's own mandated §F3 content, flipped verdicts on the
fourth decimal of a rounding path, and rejected R3's own deterministic fallback.
The cases below are the ones that killed it, plus the union false-accept that
forced the scale-aware lookup.
"""

from __future__ import annotations

import asyncio
import json
import re
from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.config import settings
from app.services.portfolio_finding import (
    build_allowlist,
    build_slot_map,
    llm_render_sections,
    register_check,
    render_deterministic_sections,
    tokenize_numbers,
    validate_sections,
)
from tests.unit.test_cr136_finding_renderer import FakeJournalStore, _context, _rules


def _allowlist(context=None, rules=None):
    context = context or _context()[0]
    rules = rules if rules is not None else _rules("R1")
    return context, rules, build_allowlist(context, rules)


def _sections(**overrides) -> dict[str, str]:
    base = {"f1": "", "f2": "", "f3": "", "f4": "", "f5": ""}
    base.update(overrides)
    return base


# ── The case that killed the digit rule ─────────────────────────────────────


def test_the_mandated_f3_content_passes() -> None:
    """§F3 is the section Rev 4 REQUIRES to carry citation years, λ, √252, the
    kurtosis range and the BOK lesson numbers. A validator that cannot pass its
    own mandated content cannot ship."""
    context, rules, allowlist = _allowlist()
    sections = render_deterministic_sections(context, rules)
    assert validate_sections({"f3": sections["f3"], **_sections()}, allowlist) is None


def test_a_fabricated_number_is_rejected_with_the_evidence() -> None:
    _context_, rules, allowlist = _allowlist()
    failure = validate_sections(
        _sections(f2="The book moved about 1.9 times the market."), allowlist,
    )
    assert failure is not None
    assert failure.reason == "unregistered_number"
    assert failure.section == "f2"
    assert "1.9" in failure.tokens


# ── Rounding, ulp, scale ────────────────────────────────────────────────────


def _allow_value(value: float, scale: str):
    from app.services.portfolio_finding import Allowlist, _register_number

    allow = Allowlist(pct=set(), raw=set())
    _register_number(value, scale, allow)
    return allow


def test_both_rounding_paths_are_admitted() -> None:
    """Rev 4's acceptance pair. 0.6249 renders 62%, 0.6251 renders 63%, and a
    validator that admits only one of them flips its verdict on the fourth
    decimal of a number nobody controls."""
    assert validate_sections(
        _sections(f2="explains 62% of moves"), _allow_value(0.6249, "pct"),
    ) is None
    assert validate_sections(
        _sections(f2="explains 63% of moves"), _allow_value(0.6251, "pct"),
    ) is None

    # 0.625 sits exactly on the boundary: half-up gives 63, half-even gives 62,
    # and the renderer is entitled to either.
    half = _allow_value(0.625, "pct")
    assert validate_sections(_sections(f2="62%"), half) is None
    assert validate_sections(_sections(f2="63%"), half) is None


def test_the_ulp_window_is_the_documented_residual() -> None:
    """Rev 4 documents this rather than claiming it away: a +-1 ulp window is
    what makes the two rounding paths and the renderer's own dp choices all
    validate, and its price is that a neighbouring value is admitted too."""
    allow = _allow_value(1.0, "pct")
    assert validate_sections(_sections(f2="99.9%"), allow) is None, (
        "100.0 +- 1 ulp at 1 dp admits 99.9 — documented, not a leak"
    )


def test_the_ulp_window_is_one_unit_at_the_rendered_dp() -> None:
    allow = _allow_value(0.62, "pct")
    for accepted in ("61%", "62%", "63%"):
        assert validate_sections(_sections(f2=accepted), allow) is None, accepted
    failure = validate_sections(_sections(f2="60%"), allow)
    assert failure is not None and failure.reason == "unregistered_number"


def test_the_two_scale_sets_are_never_unioned() -> None:
    """The measured union false-accept: a book whose 0.62 lives in the percent
    set would have made "Your beta is 62." pass, because 62 is a member of the
    union. Lookup is by scale, and a bare number is RAW."""
    allow = _allow_value(0.62, "pct")
    assert validate_sections(_sections(f2="explains 62% of moves"), allow) is None

    failure = validate_sections(_sections(f2="Your beta is 62."), allow)
    assert failure is not None
    assert failure.reason == "unregistered_number"
    assert "62" in failure.tokens


def test_thousands_separators_and_spaced_numbers() -> None:
    from decimal import Decimal

    tokens = tokenize_numbers("$10,000 of starting capital")
    assert [t.value for t in tokens] == [Decimal("10000")]

    two = tokenize_numbers("1, 2")
    assert [t.value for t in two] == [Decimal("1"), Decimal("2")], (
        "a comma that is not a thousands group must not glue two numbers together"
    )

    _context_, _rules_, allowlist = _allowlist()
    assert validate_sections(
        _sections(f2="a $10,000 starting book"), allowlist,
    ) is None


def test_percent_suffixes_all_select_the_percent_set() -> None:
    allow = _allow_value(0.62, "pct")
    for suffix in ("62%", "62 percent", "62pp"):
        assert validate_sections(_sections(f2=suffix), allow) is None, suffix


def test_a_rule_slot_registers_at_every_dp_the_renderer_uses() -> None:
    """Measured: a breach weight of 41.25 renders "41.3%" in §F5, and a ±0.01
    window around 41.25 does not contain it — so the engine's OWN sentence was
    rejected, pushing every R0 Finding with a non-round number onto the
    fallback for no reason."""
    context = _context()[0]
    rules = _rules("R0")
    rules[0]["slots"]["breaches"][0]["cap_pct"] = 33.333333333
    rules[0]["slots"]["breaches"][0]["weight_pct"] = 41.25

    sections = render_deterministic_sections(context, rules)
    assert "41.3%" in sections["f5"] and "33.3%" in sections["f5"]
    assert validate_sections(sections, build_allowlist(context, rules)) is None


# ── Register check ──────────────────────────────────────────────────────────


def test_a_seeded_technical_leak_is_caught() -> None:
    failure = register_check(
        _sections(f2="The EWMA covariance estimator says the book is calm.")
    )
    assert failure is not None
    assert failure.reason == "register_lexicon"
    assert failure.section == "f2"


def test_ten_plausible_plain_paragraphs_pass() -> None:
    """Rev 4 measured 0/10 false positives; a register check that fires on
    ordinary prose would push every Finding onto the fallback path."""
    paragraphs = [
        "Over the measured window this book swung more widely than the market did.",
        "Three holdings carry most of the risk, and one of them carries most of that.",
        "The book has moved roughly in step with the market, a little more sharply.",
        "Cash makes up a large share of the book and damps the whole-book swings.",
        "Two holdings have moved almost identically, so they count as less than two.",
        "The deepest fall inside the window was recovered over the months that followed.",
        "Nothing in the measured window suggests the book behaves unusually.",
        "A month bad enough to happen one time in twenty would be a noticeable fall.",
        "The largest position owns more of the risk than it owns of the money.",
        "These figures describe the window measured, and the window just ended.",
    ]
    for i, text in enumerate(paragraphs):
        assert register_check(_sections(f2=text)) is None, (i, text)


def test_f3_and_f4_are_exempt_by_design() -> None:
    """They name the estimator on purpose — that is what §F3 is for."""
    assert register_check(_sections(f3="EWMA covariance, standard error 1.2%")) is None
    assert register_check(_sections(f4="The covariance estimator's window")) is None


def test_a_seventeen_word_headline_is_rejected() -> None:
    long_headline = "- " + " ".join(f"word{i}" for i in range(17))
    failure = register_check(_sections(f1=long_headline))
    assert failure is not None
    assert failure.reason == "headline_length"


def test_an_imperative_f5_is_rejected_at_runtime() -> None:
    """The speech-act pin has to hold structurally — prompt instructions are not
    controls (CR038)."""
    failure = register_check(_sections(f5="Sell half the NVDA position."))
    assert failure is not None
    assert failure.reason == "imperative"

    failure = register_check(_sections(f5="You should consider reducing NVDA."))
    assert failure is not None
    assert failure.reason == "imperative"


# ── The LLM path always falls back to a complete report ─────────────────────


class _FakeGateway:
    def __init__(self, output: str) -> None:
        self.output = output
        self.calls = 0

    def has_real_provider(self) -> bool:
        return True

    def stream_chat(self, **kwargs):
        self.calls += 1
        output = self.output

        async def _gen():
            yield output

        return _gen()


def _run(gateway, monkeypatch, *, enabled: bool = True):
    monkeypatch.setattr(settings, "portfolio_health_llm_enabled", enabled)
    context, rules, _ = _allowlist()
    deterministic = render_deterministic_sections(context, rules)
    return asyncio.run(llm_render_sections(
        context, rules, gateway, user_id=uuid4(), deterministic=deterministic,
    )), deterministic


def test_a_real_payload_figure_quoted_against_the_wrong_metric_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AT:R66 — CR136-M06 audit BLOCKER B1 regression, the auditor's own attack.

    The old allow-list asked only "does this number appear in the payload",
    which measured ~50 of 101 whole percentages legal on an ordinary book — so
    a REAL figure quoted against the WRONG metric passed. This is that exact
    sentence shape: a small whole percentage that genuinely occurs in the
    payload, attached to portfolio volatility, which it is not the volatility
    of. It must now be rejected, because typing a digit at all is the
    violation — the model may only reference a slot, and a slot's value is by
    definition the value of the metric it names.
    """
    context, rules, allow = _allowlist()
    # The attack number is taken FROM the allow-list, not hard-coded, so this
    # keeps reproducing B1 as the fixture drifts. Any whole percentage in the
    # set is one the old membership check would have accepted in any sentence.
    legal = sorted(
        v for v in allow.pct if v == v.to_integral_value() and 0 <= v <= 100
    )
    assert legal, "vacuity guard — no whole percentage is legal, B1 not reproduced"
    wrong = legal[0]
    # ...and it must NOT be the true volatility, or the sentence is merely correct.
    true_vol = build_slot_map(context).get("vol_ann_pct")
    assert true_vol != f"{wrong}%", "pick a figure that is not the real answer"

    gateway = _FakeGateway(
        '{"f1": ["Your portfolio volatility is ' + str(wrong) + '%."],'
        ' "f2": "x", "f4": "z"}'
    )
    (sections, reason), _det = _run(gateway, monkeypatch)
    assert sections is None
    assert reason == "unsubstituted_digit"


def test_a_slot_reference_renders_exactly_the_deterministic_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The other half of B1: attribution is correct BY CONSTRUCTION. A slot
    renders the value of the metric it names, formatted by the same helper the
    deterministic path uses, so the two renderings cannot disagree."""
    context, rules, _ = _allowlist()
    slots = build_slot_map(context)
    assert "vol_ann_pct" in slots, "fixture must carry a sufficient volatility"

    gateway = _FakeGateway(
        '{"f1": ["Your book\'s volatility is {{vol_ann_pct}}."],'
        ' "f2": "Steady.", "f4": "That is the picture."}'
    )
    (sections, reason), _det = _run(gateway, monkeypatch)
    assert reason is None and sections is not None
    assert slots["vol_ann_pct"] in sections["f1"]
    assert "{{" not in sections["f1"]


def test_an_invented_slot_name_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The model cannot reference its way to a number that does not exist."""
    gateway = _FakeGateway(
        '{"f1": ["Volatility is {{sharpe_ratio_pct}}."], "f2": "x", "f4": "z"}'
    )
    (sections, reason), _det = _run(gateway, monkeypatch)
    assert sections is None
    assert reason == "unknown_slot"


_SPELLED_OUT_NUMBERS = [
    "Your portfolio volatility is about twenty percent a year.",
    "Nearly ninety percent of the risk sits in one name.",
    "The market explains about two thirds of this book's moves.",
    "Your beta is roughly double the market.",
    "Your largest holding is about half of your risk.",
    "Roughly a fifth of your book moves with the market each year.",
    "About one in three of your holdings drives the risk.",
    "Your volatility is XX percent.",
]


@pytest.mark.parametrize("sentence", _SPELLED_OUT_NUMBERS)
def test_a_number_spelled_out_in_words_is_rejected(
    sentence: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AT:R66 — CR136-M06 audit round 2, MAJOR M3. The auditor's own accepted
    narrations, verbatim.

    B1's fix banned digits; these carry a quantity and no digit, so the digit
    rule passed every one of them. "Your beta is roughly double the market"
    was accepted against a true beta of 0.89 — a book slightly LESS volatile
    than the market published as twice as volatile. Same failure class as B1 at
    coarser resolution, and the prompt's own "plain language" instruction pushes
    toward exactly this notation.
    """
    # Vacuity guard: if a digit ever creeps into this table the test would pass
    # on the OLD rule and prove nothing about M3.
    assert not re.search(r"\d", sentence), "attack must carry no digit"

    gateway = _FakeGateway(
        json.dumps({"f1": [sentence], "f2": "Steady.", "f4": "That is the picture."})
    )
    (sections, reason), _det = _run(gateway, monkeypatch)
    assert sections is None
    assert reason == "number_word"


@pytest.mark.parametrize("glyph", ["½", "²", "Ⅻ", "٢", "２"])
def test_a_numeral_that_is_not_a_decimal_digit_is_rejected(
    glyph: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AT:R66 — CR136-M06 audit round 2, MAJOR M3, the character half.

    `\\d` is Unicode category Nd, which already covered Arabic-Indic and
    fullwidth forms — the last three here — but not `½`/`²` (No) or `Ⅻ` (Nl).
    The rule is now the Unicode NUMERIC VALUE property, which is what actually
    defines "this glyph means a number"."""
    gateway = _FakeGateway(
        json.dumps({"f1": [f"Your volatility is {glyph} of the market."],
                    "f2": "Steady.", "f4": "That is the picture."})
    )
    (sections, reason), _det = _run(gateway, monkeypatch)
    assert sections is None
    assert reason == "unsubstituted_digit"


@pytest.mark.parametrize("malformed", [
    "{{ vol_ann_pct }}", "{{VOL_ANN_PCT}}", "{{vol-ann-pct}}", "{vol_ann_pct}",
    "{{vol_ann_pct2}}",
])
def test_malformed_slot_syntax_is_never_published_verbatim(
    malformed: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AT:R66 — CR136-M06 audit round 2, MAJOR M4.

    `_SLOT_RE` matches exactly one form. Anything else is not a slot for the
    unknown-name check and carries no digit for the numeral check, so it used to
    pass straight through into a permanently archived financial report. Padding
    spaces are an ordinary thing for a model to do with a template. The near-miss
    the auditor flagged — `{{vol_ann_pct2}}` — was caught only because the typo
    happened to contain a digit, which is luck, not design."""
    gateway = _FakeGateway(
        json.dumps({"f1": [f"Your volatility has been {malformed} a year."],
                    "f2": "Steady.", "f4": "That is the picture."})
    )
    (sections, reason), _det = _run(gateway, monkeypatch)
    assert sections is None
    assert reason == "malformed_slot"


def test_a_slot_placed_in_the_wrong_sentence_cannot_read_as_a_true_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AT:R66 — CR136-M06 audit round 3, BLOCKER B2, the auditor's own attack.

    Re-injection made fabrication unrepresentable and left attribution wide
    open: the model still writes the sentence and still picks which slot lands
    in it. The published example was "CCC drives 33% of your risk" — 33% is
    CCC's invested WEIGHT, its risk share is 38% — undetectable by any reader.

    The fix does not reject this. It removes its ability to be FALSE: a slot
    renders the metric's name and value as one token, so the wrong slot in the
    wrong sentence is a visible non-sequitur instead of a plausible lie.
    """
    context, _rules, _allow = _allowlist()
    slots = build_slot_map(context)
    share, weight = slots.get("top_risk_share_pct"), slots.get("top_risk_weight_pct")
    assert share and weight, "fixture must carry a top risk contributor"
    # Vacuity guard: if the two ever render identically the swap proves nothing.
    assert share != weight, "the attack needs two distinguishable figures"

    gateway = _FakeGateway(json.dumps({
        # The realistic swap: weight cited as if it were the risk share.
        "f1": ["{{top_risk_ticker}} drives {{top_risk_weight_pct}} of your risk."],
        # The loud swap: beta cited as if it were an annualised volatility.
        "f2": "Your portfolio volatility has been {{beta_ratio}} a year.",
        "f4": "That is the picture.",
    }))
    (sections, reason), _det = _run(gateway, monkeypatch)
    assert reason is None and sections is not None

    assert "an invested weight of" in sections["f1"], (
        "the misplaced figure must carry its own metric's name, or the sentence "
        "reads as a true risk-share claim — which is B2"
    )
    assert share not in sections["f1"], "the true risk share was never cited"
    assert "a beta of" in sections["f2"]


@pytest.mark.parametrize("compound", [
    "twofold", "tenfold", "hundredfold", "quintuple", "decuple",
    "score", "naught", "unity",
])
def test_the_number_word_set_is_closed_over_the_multiplier_family(
    compound: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AT:R66 — CR136-M06 audit round 3, MAJOR M5.

    `\\b` cannot see inside a compound word, so `twofold` — "roughly double",
    the very example that produced the M3 fix — walked straight through the set
    that fix created. `\\btwo\\b` does not match inside `twofold`. The
    multiplier run also stopped at `quadruple`."""
    gateway = _FakeGateway(json.dumps({
        "f1": [f"Your risk is {compound} what it looks like."],
        "f2": "Steady.", "f4": "That is the picture.",
    }))
    (sections, reason), _det = _run(gateway, monkeypatch)
    assert sections is None
    assert reason == "number_word"


def test_the_number_screens_still_admit_ordinary_prose(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The availability side of M3/M4. Blunt screens that reject everything are
    indistinguishable from a broken LLM path, so pin that a narration written the
    way the prompt asks for still gets through."""
    context, _rules, _allow = _allowlist()
    slots = build_slot_map(context)
    assert "vol_ann_pct" in slots and "top_risk_ticker" in slots

    gateway = _FakeGateway(json.dumps({
        "f1": ["Your book has swung {{vol_ann_pct}} a year.",
               "{{top_risk_ticker}} carries {{top_risk_share_pct}} of the risk."],
        "f2": "Your holdings move together more than their names suggest, so the"
              " book behaves like a narrower bet than it looks.",
        "f4": "Concentration, not market exposure, is what drives this book.",
    }))
    (sections, reason), _det = _run(gateway, monkeypatch)
    assert reason is None and sections is not None
    assert slots["vol_ann_pct"] in sections["f1"]


def test_f5_is_never_taken_from_the_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AT:R66 — CR136-M06 audit MAJOR M1. §F5 is the compliance perimeter and
    its denylist let 9 of 10 ordinary advice paraphrases through. The fence is
    structural: the model is not asked for §F5 and cannot supply one, so the
    stored §F5 is always the rule-engine rendering."""
    gateway = _FakeGateway(
        '{"f1": ["Calm."], "f2": "x", "f4": "z",'
        ' "f5": "It would be prudent to trim AAA."}'
    )
    (sections, reason), deterministic = _run(gateway, monkeypatch)
    assert reason is None and sections is not None
    assert sections["f5"] == deterministic["f5"]
    assert "prudent" not in sections["f5"]


def test_a_fabricated_number_discards_the_whole_model_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Never a partial merge: one bad number and the entire narration goes,
    because there is no way to know which other sentence it infected."""
    gateway = _FakeGateway(
        '{"f1": ["Volatility was 47.3%."], "f2": "x", "f3": "y", "f4": "z", "f5": "w"}'
    )
    (sections, reason), _det = _run(gateway, monkeypatch)
    assert sections is None
    # AT:R66 — reason changed with the B1 fix. A typed digit is now caught by
    # the slot contract (stronger, and before the allow-list is consulted at
    # all) rather than by allow-list membership.
    assert reason == "unsubstituted_digit"


def test_a_register_leak_discards_the_model_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = _FakeGateway(
        '{"f1": ["Calm book."], "f2": "The covariance estimator agrees.",'
        ' "f3": "y", "f4": "z", "f5": "w"}'
    )
    (sections, reason), _det = _run(gateway, monkeypatch)
    assert sections is None
    assert reason == "register_lexicon"


def test_non_json_output_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    (sections, reason), _det = _run(_FakeGateway("I'm afraid I can't do that"), monkeypatch)
    assert sections is None
    assert reason == "schema"


def test_a_missing_section_key_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    (sections, reason), _det = _run(
        _FakeGateway('{"f1": ["ok"], "f2": "x"}'), monkeypatch,
    )
    assert sections is None
    assert reason == "schema"


def test_a_provider_exception_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Broken:
        def has_real_provider(self):
            return True

        def stream_chat(self, **kwargs):
            raise RuntimeError("vLLM down")

    (sections, reason), _det = _run(_Broken(), monkeypatch)
    assert sections is None
    assert reason == "provider_error"


def test_the_config_flag_stops_the_gateway_being_called(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = _FakeGateway("{}")
    (sections, reason), _det = _run(gateway, monkeypatch, enabled=False)
    assert sections is None
    assert reason is None
    assert gateway.calls == 0


def test_the_mock_provider_never_narrates(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Finding narrated by the mock provider would read exactly like a real
    one and mean nothing."""
    class _MockOnly:
        def has_real_provider(self):
            return False

        def stream_chat(self, **kwargs):
            raise AssertionError("the mock provider must never narrate a Finding")

    (sections, reason), _det = _run(_MockOnly(), monkeypatch)
    assert sections is None
    assert reason is None


def test_a_clean_narration_is_accepted_and_f3_stays_deterministic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """§F3's mandated content is appended deterministically on BOTH paths —
    prompt instructions are not controls, so the only way to guarantee the
    disclosures is to not let the model own them."""
    gateway = _FakeGateway(
        '{"f1": ["The book has been calm."], "f2": "Nothing unusual.",'
        ' "f3": "MODEL WROTE THIS", "f4": "In short, calm.", "f5": "Nothing fired."}'
    )
    (sections, reason), deterministic = _run(gateway, monkeypatch)
    assert reason is None
    assert sections is not None
    assert sections["f2"] == "Nothing unusual."
    assert sections["f3"] == deterministic["f3"]
    assert "MODEL WROTE THIS" not in sections["f3"]


def test_every_rejection_path_logs_at_error_level(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """M11's live verification greps ERROR. Two of the four paths logged WARN,
    so a vLLM outage and a persistently malformed model — the two failure modes
    an operator most needs to see — produced no ERROR-level signal at all."""
    import structlog

    class _Broken:
        def has_real_provider(self):
            return True

        def stream_chat(self, **kwargs):
            raise RuntimeError("vLLM down")

    cases = {
        "provider_error": _Broken(),
        "schema": _FakeGateway("I'm afraid I can't do that"),
        "unsubstituted_digit": _FakeGateway(
            '{"f1": ["Volatility was 47.3%."], "f2": "x", "f3": "y", "f4": "z", "f5": "w"}'
        ),
        "register_lexicon": _FakeGateway(
            '{"f1": ["Calm."], "f2": "The covariance estimator agrees.",'
            ' "f3": "y", "f4": "z", "f5": "w"}'
        ),
    }
    for expected_reason, gateway in cases.items():
        with structlog.testing.capture_logs() as captured:
            (sections, reason), _det = _run(gateway, monkeypatch)
        assert sections is None and reason == expected_reason
        errors = [e for e in captured if e.get("log_level") == "error"]
        assert errors, f"{expected_reason} produced no ERROR-level line"
        assert errors[-1].get("reason") == expected_reason, errors[-1]


def test_the_fallback_report_is_still_complete(monkeypatch: pytest.MonkeyPatch) -> None:
    """CR040's real question: when the LLM path fails constantly and silently,
    what does the user end up with? A complete, correct report."""
    gateway = _FakeGateway('{"f1": ["Volatility was 47.3%."], "f2": "x", "f3": "y", "f4": "z", "f5": "w"}')
    (sections, _reason), deterministic = _run(gateway, monkeypatch)
    assert sections is None
    for key in ("f1", "f2", "f3", "f4", "f5"):
        assert deterministic[key].strip(), key
