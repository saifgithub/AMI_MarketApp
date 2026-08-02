"""CR136 M06 — allow-list validator: rounding paths, scale-aware lookup, register lexicon, LLM fallback.

Rev 3's digit-sequence validator was measured and deleted: it rejected 10–13 of
the 25 digit runs in the CR's own mandated §F3 content, flipped verdicts on the
fourth decimal of a rounding path, and rejected R3's own deterministic fallback.
The cases below are the ones that killed it, plus the union false-accept that
forced the scale-aware lookup.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from app.core.config import settings
from app.services.portfolio_finding import (
    build_allowlist,
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
    assert reason == "unregistered_number"


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


def test_the_fallback_report_is_still_complete(monkeypatch: pytest.MonkeyPatch) -> None:
    """CR040's real question: when the LLM path fails constantly and silently,
    what does the user end up with? A complete, correct report."""
    gateway = _FakeGateway('{"f1": ["Volatility was 47.3%."], "f2": "x", "f3": "y", "f4": "z", "f5": "w"}')
    (sections, _reason), deterministic = _run(gateway, monkeypatch)
    assert sections is None
    for key in ("f1", "f2", "f3", "f4", "f5"):
        assert deterministic[key].strip(), key
