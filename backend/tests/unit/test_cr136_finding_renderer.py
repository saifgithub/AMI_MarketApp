"""CR136 M06 — strip test, deterministic templates, §F1 word cap, §F5 speech act, head disclosure, idempotency.

The context fixture is real engine output rather than hand-written blocks: the
renderer's job is to be correct about what M04 actually produces, and a
hand-built fixture tests the fixture.
"""

from __future__ import annotations

import asyncio
import re
from uuid import uuid4

import pytest

from app.core.config import settings
from app.schemas.journal import JournalEntry
from app.services.portfolio_finding import (
    InsufficientContextError,
    build_stripped_context,
    generate_and_persist_finding,
    load_latest_finding,
    register_check,
    render_deterministic_sections,
    render_head_disclosure,
    validate_sections,
)
from app.services.portfolio_finding import build_allowlist
from app.services.portfolio_health_constants import (
    DISCLAIMER_SHORT,
    ENGINE_VERSION,
    F5_FORBIDDEN_IMPERATIVES,
    F5_FORBIDDEN_PHRASES,
    HEADLINE_MAX_WORDS,
    NON_STATIONARITY_CAVEAT,
    PORTFOLIO_HEALTH_ENTRY_TYPE,
)
from tests.unit.test_cr136_metrics_engine import _book  # real engine fixtures

from app.services.portfolio_health import compute_health


def _context(**overrides):
    payload = compute_health(**_book(**overrides))
    blocks = list(payload["blocks"].values())
    context = build_stripped_context(blocks, as_of=payload["as_of"])
    context["benchmark_vol_ann"] = payload["context"]["benchmark_vol_ann"]
    return context, payload


def _rules(*fired: str) -> list[dict]:
    slots = {
        "R0": {
            "breaches": [
                {
                    "scope": "name", "cap_pct": 35.0, "name": "AAA",
                    "weight_pct": 41.2, "weight_pct_raw": 41.2,
                },
            ],
            "etf_disclosure": False,
        },
        "R1": {"ticker": "AAA", "risk_share": 45.3, "weight": 33.3, "threshold_mention": 40},
        "R2": {"n": 8, "dr2": 1.7},
        "R2b": {"a": "AAA", "b": "BBB", "rho": 0.95},
        "R3": {"beta": 1.42, "r2_pct": 62, "window": 126},
        "R4": {"cash": 43.5},
        "R5": {"dropped": ["CCC"], "reasons": ["short history"], "covered": 70.0},
    }
    return [
        {
            "rule_id": rule_id,
            "fired": rule_id in fired,
            "state": "fired" if rule_id in fired else "cleared",
            "slots": slots[rule_id] if rule_id in fired else {},
            "based_on": [],
        }
        for rule_id in ("R0", "R1", "R2", "R2b", "R3", "R4", "R5")
    ]


class FakeJournalStore:
    """In-memory: the persistence contract under test is the payload shape and
    the idempotent replay, not the DB."""

    def __init__(self) -> None:
        self.entries: list[JournalEntry] = []
        self.appends = 0
        self.by_dedupe: dict[str, JournalEntry] = {}

    def append(self, draft) -> JournalEntry:
        self.appends += 1
        entry = JournalEntry(
            user_id=draft.user_id,
            entry_type=draft.entry_type,
            reference_id=draft.reference_id,
            title=draft.title,
            summary=draft.summary,
            payload=draft.payload,
        )
        self.entries.insert(0, entry)
        return entry

    def append_unique(self, draft):
        """Mirrors the real store: the dedupe key decides, and losing the race
        returns the winner's row rather than raising."""
        existing = self.by_dedupe.get(draft.dedupe_key)
        if existing is not None:
            return existing, False
        entry = self.append(draft)
        self.by_dedupe[draft.dedupe_key] = entry
        return entry, True

    def list_for_user(self, user_id, **kwargs):
        return list(self.entries), len(self.entries), None

    def latest_portfolio_health_entry(self, user_id, portfolio_id):
        """Mirrors the real store: newest first, soft-deleted INCLUDED."""
        for entry in self.entries:
            if str((entry.payload or {}).get("portfolio_id")) == str(portfolio_id):
                return entry
        return None


# ── Strip ───────────────────────────────────────────────────────────────────


def test_an_insufficient_metric_name_appears_nowhere() -> None:
    """The uncertainty contract's teeth. A stripped block is dropped entirely —
    key, metric name, every field — so the model has nothing to narrate and the
    templates have nothing to select."""
    payload = compute_health(**_book(126))          # 125 returns: short window
    blocks = list(payload["blocks"].values())
    context = build_stripped_context(blocks, as_of=payload["as_of"])

    assert [b["metric"] for b in context["metrics"]] == ["weight_concentration"]
    serialised = repr(context)
    for stripped in ("portfolio_volatility", "beta", "effective_bets", "mcr"):
        assert stripped not in serialised, stripped

    sections = render_deterministic_sections(context, _rules())
    everything = render_head_disclosure(context) + " " + " ".join(sections.values())
    for stripped in ("Portfolio volatility", "Market sensitivity", "Effective independent"):
        assert stripped not in everything, stripped


def test_zero_sufficient_blocks_raises() -> None:
    with pytest.raises(InsufficientContextError):
        build_stripped_context([{"metric": "x", "sufficient": False}], as_of="2026-07-31")


# ── Head disclosure ─────────────────────────────────────────────────────────


def test_head_disclosure_is_verbatim_and_carried_into_the_payload() -> None:
    context, _ = _context()
    head = render_head_disclosure(context)

    assert head.splitlines()[0] == f"> **{DISCLAIMER_SHORT}**"
    assert NON_STATIONARITY_CAVEAT in head
    assert "gross of fees" in head
    assert "backcast" in head
    assert "λ=0.97" in head


# ── §F1 ─────────────────────────────────────────────────────────────────────


def test_every_headline_is_inside_the_word_cap() -> None:
    """Including the partial marker, which is why the templates are sized to 14."""
    for kwargs in ({}, {"cash": 5000.0}):
        context, _ = _context(**kwargs)
        for block in context["metrics"]:
            block["partial"] = True
            block.setdefault("dropped_holdings", [{"ticker": "ZZZ", "reason": "short_history"}])
        sections = render_deterministic_sections(context, _rules())
        headlines = [
            line.lstrip("- ").strip()
            for line in sections["f1"].splitlines() if line.strip()
        ]
        assert 3 <= len(headlines) <= 5, headlines
        for headline in headlines:
            assert len(headline.split()) <= HEADLINE_MAX_WORDS, headline
            assert "(partial data)" in headline


def test_r_squared_is_never_written_as_r_squared_in_the_plain_register() -> None:
    """The F19 amendment: the literal form would trip the register check by
    design, so §F1 says what R² MEANS instead."""
    context, _ = _context()
    beta = next(b for b in context["metrics"] if b["metric"] == "beta")
    beta["low_explanatory_power"] = True
    beta["r_squared"] = 0.12

    sections = render_deterministic_sections(context, _rules())
    assert "the market explains only" in sections["f1"]
    for section in ("f1", "f2", "f5"):
        assert not re.search(r"R²|\bR\^?2\b", sections[section]), section


# ── Units ───────────────────────────────────────────────────────────────────


def _tier2_context():
    """Real M03 output, not hand-built blocks: the whole defect was a
    disagreement about what M03 actually stores."""
    from datetime import date, timedelta

    from app.services.portfolio_snapshot import SnapshotPoint, tier2_blocks

    values = [100.0] * 5 + [110.0, 118.0, 112.0, 105.0, 99.86] + [96.0] * 13
    start = date(2026, 1, 5)
    points = [
        SnapshotPoint(
            as_of=start + timedelta(days=i), total_value=v, cash=0.0,
            invested_value=v, drawdown_pct=0.0, source="test",
            predicted_vol_ann=None,
        )
        for i, v in enumerate(values)
    ]
    blocks = tier2_blocks(points)
    return build_stripped_context(list(blocks.values()), as_of="2026-08-02"), blocks


def test_tier2_values_are_not_scaled_a_second_time() -> None:
    """M03 stores `realised_*` ALREADY IN PERCENT; Tier-1 stores fractions.
    Applying the Tier-1 convention to a Tier-2 block published a 19.69% fall as
    "1969.00%" in §F3 while §F1 rendered the same block as 19.7% — one Finding
    disagreeing with itself by two orders of magnitude."""
    context, blocks = _tier2_context()
    mdd = blocks["realised_max_drawdown"]["value"]
    assert 15.0 < mdd < 25.0, "fixture guard: the value must be a percent number"

    sections = render_deterministic_sections(context, [])
    assert f"Value: {mdd:.2f}%." in sections["f3"]
    assert "1969" not in sections["f3"] and f"{mdd * 100:.2f}" not in sections["f3"]
    assert f"{mdd:.1f}% peak-to-trough" in sections["f1"]


def test_the_double_scaled_reading_is_not_even_a_registered_token() -> None:
    """Structural, not cosmetic: the allow-list registered every leaf at BOTH
    scales, so the wrong number validated as 'in the payload'. A percent-unit
    value now registers into the percent set verbatim and nowhere else."""
    from decimal import Decimal

    context, blocks = _tier2_context()
    allow = build_allowlist(context, [])
    mdd = blocks["realised_max_drawdown"]["value"]

    assert Decimal(str(round(mdd, 2))).normalize() in allow.pct
    assert Decimal(str(round(mdd * 100, 2))).normalize() not in allow.pct
    assert validate_sections(
        render_deterministic_sections(context, []), allow,
    ) is None, "the deterministic rendering must validate by construction"


def test_a_standard_error_carries_its_own_metrics_unit() -> None:
    """β = 1.19 with SE 0.093 read "Standard error 9.27%", which is not 9.27% of
    anything — it is ±0.09 on the beta itself."""
    context, _ = _context()
    beta = next(b for b in context["metrics"] if b["metric"] == "beta")
    vol = next(b for b in context["metrics"] if b["metric"] == "portfolio_volatility")
    sections = render_deterministic_sections(context, _rules())

    assert f"Standard error {beta['standard_error']:.2f}," in sections["f3"]
    assert f"Standard error {vol['standard_error'] * 100:.2f}%," in sections["f3"], (
        "a fraction-unit metric still renders its SE as a percent"
    )


def test_an_unpinned_metric_id_raises_rather_than_guessing_a_unit() -> None:
    from app.services.portfolio_finding import _unit

    with pytest.raises(ValueError, match="no unit pinned"):
        _unit("some_new_metric")


# ── §F5 speech act ──────────────────────────────────────────────────────────


def test_a_fired_rule_with_no_template_raises_rather_than_vanishing() -> None:
    """§F5 is the only place a fired rule reaches the user. Skipping one
    silently publishes a Finding that says nothing fired when something did —
    the same silent-skip the §F3 unknown-metric branch already refuses."""
    context, _ = _context()
    rogue = [{"rule_id": "R9", "fired": True, "state": "fired", "slots": {},
              "based_on": []}]
    with pytest.raises(ValueError, match="no template"):
        render_deterministic_sections(context, rogue)


def test_f5_says_so_plainly_when_nothing_fired() -> None:
    context, _ = _context()
    sections = render_deterministic_sections(context, _rules())
    assert "No review threshold was crossed" in sections["f5"]


def test_f5_never_reads_as_an_instruction() -> None:
    """Rev 4's speech-act pin has to hold on the DETERMINISTIC path too — the
    live site says the product does not give investment advice, and this path
    ships whenever the LLM is off or rejected."""
    context, _ = _context()
    sections = render_deterministic_sections(
        context, _rules("R0", "R1", "R2", "R2b", "R3", "R4", "R5"),
    )
    f5 = sections["f5"]
    assert register_check(sections) is None

    lowered = f5.lower()
    for phrase in F5_FORBIDDEN_PHRASES:
        assert phrase not in lowered, phrase
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", f5):
        first = sentence.lstrip("-*• ").strip().split(" ")[0].strip(",.;:").lower()
        assert first not in F5_FORBIDDEN_IMPERATIVES, sentence


def test_the_zero_cost_line_appears_beside_trimming_talk() -> None:
    """Barber & Odean: about 97% of the measured activity penalty is invisible
    in a zero-cost sim, so any sentence that could read as "trim this" has to
    carry the disclosure."""
    context, _ = _context()
    with_r1 = render_deterministic_sections(context, _rules("R1"))
    assert "charges no commissions" in with_r1["f5"]

    without = render_deterministic_sections(context, _rules("R4"))
    assert "charges no commissions" not in without["f5"]


# ── §F3 ─────────────────────────────────────────────────────────────────────


def test_f3_carries_the_mandated_standing_disclosures() -> None:
    context, _ = _context()
    f3 = render_deterministic_sections(context, _rules())["f3"]
    for required in (
        "RiskMetrics", "§5.3.2", "No shrinkage is applied", "Ledoit & Wolf",
        "Markowitz (1952)", "Choueifaty & Coignard (2008)", "CAPM",
        "excess kurtosis", "Annualisation multiplies by the square root of",
        "gross of fees", NON_STATIONARITY_CAVEAT, "M11 and M12",
    ):
        assert required in f3, required
    # CR139: this used to pin the literal "square root of 252". That was a
    # name guard on a constant, not a guard on the disclosure — and when
    # CR139 made annualisation follow the book's own grid, the guard failed
    # for the right reason and would have been "fixed" by deleting it.
    # What F3 actually owes the reader is that annualisation is disclosed AND
    # that the disclosure describes the method the code runs, so the claim
    # must no longer assert a fixed 252.
    assert "square root of 252 trading days" not in f3, (
        "F3 still tells the reader annualisation multiplies by root-252. "
        "Since CR139 it multiplies by the book's own realised grid rate, "
        "which is 252 only when every holding priced every trading day — so "
        "this disclosure now describes a method the code does not run."
    )


def test_an_unknown_metric_id_raises_rather_than_being_skipped() -> None:
    context, _ = _context()
    context["metrics"].append({
        "metric": "invented_metric", "sufficient": True, "value": 1.0,
        "n_observations": 126, "window_days": 180,
    })
    with pytest.raises(ValueError, match="invented_metric"):
        render_deterministic_sections(context, _rules())


# ── The by-construction guarantee ───────────────────────────────────────────


def test_the_deterministic_rendering_validates_itself() -> None:
    """The closure guard on the FIXED constant sets. The deterministic renderer
    is never re-validated at runtime — there would be no fallback left — so this
    test is what makes "validates by construction" true rather than asserted.
    Any later template edit that adds a numeric literal fails here."""
    for fired in ((), ("R1", "R4"), ("R0", "R1", "R2", "R2b", "R3", "R4", "R5")):
        context, _ = _context()
        rules = _rules(*fired)
        sections = render_deterministic_sections(context, rules)
        allowlist = build_allowlist(context, rules)

        failure = validate_sections(sections, allowlist)
        assert failure is None, (fired, failure)
        assert register_check(sections) is None, fired


# ── Persistence + idempotency ───────────────────────────────────────────────


class _SpyGateway:
    def __init__(self) -> None:
        self.calls = 0

    def has_real_provider(self) -> bool:
        self.calls += 1
        return False


def _generate(store, *, as_of: str, portfolio_id, user_id, captured: list,
              gateway=None):
    def _evaluate(prior_states):
        captured.append(prior_states)
        return _rules("R1"), {"R1": "fired", "R2": "cleared"}

    context_payload = compute_health(**_book())
    return asyncio.run(generate_and_persist_finding(
        user_id=user_id,
        portfolio_id=portfolio_id,
        as_of=as_of,
        metric_blocks=list(context_payload["blocks"].values()),
        store=store,
        gateway=gateway if gateway is not None else _SpyGateway(),
        evaluate=_evaluate,
    ))


def test_two_generates_on_the_same_day_write_one_entry(monkeypatch) -> None:
    # Explicit, not inherited from the default: this test's subject is that the
    # generating run consults the gateway and the idempotent replay does not,
    # which only says anything while the LLM path is ON. The default went OFF
    # in AT:R66 (CR136-M06 audit BLOCKER B1), and a test that asserts
    # "calls == 1" must own that precondition rather than depend on a config
    # default that can move under it.
    monkeypatch.setattr(settings, "portfolio_health_llm_enabled", True)
    store = FakeJournalStore()
    user_id, portfolio_id = uuid4(), uuid4()
    captured: list = []

    first_gateway, second_gateway = _SpyGateway(), _SpyGateway()
    first = _generate(store, as_of="2026-07-31", portfolio_id=portfolio_id,
                      user_id=user_id, captured=captured, gateway=first_gateway)
    assert first.created is True
    assert store.appends == 1
    assert first_gateway.calls == 1, "the generating run does consult the gateway"

    second = _generate(store, as_of="2026-07-31", portfolio_id=portfolio_id,
                       user_id=user_id, captured=captured, gateway=second_gateway)
    assert second.created is False
    assert second.entry.id == first.entry.id
    assert store.appends == 1, "the idempotent replay must not write"
    assert len(captured) == 1, "...and must not re-run the rule engine"
    # The spy has to be READ, not merely constructed: the version of this test
    # that built a throwaway gateway asserted nothing about the LLM at all, so a
    # replay that called the model on every refresh would have passed it.
    assert second_gateway.calls == 0, "...and must not reach the LLM at all"


def test_the_prior_findings_rule_states_reach_the_engine() -> None:
    """One journal read serves both the idempotency check and the hysteresis
    state — they are the same question about the same prior entry."""
    store = FakeJournalStore()
    user_id, portfolio_id = uuid4(), uuid4()
    captured: list = []

    _generate(store, as_of="2026-07-30", portfolio_id=portfolio_id,
              user_id=user_id, captured=captured)
    assert captured[0] == {}, "a first Finding starts every rule cleared"

    _generate(store, as_of="2026-07-31", portfolio_id=portfolio_id,
              user_id=user_id, captured=captured)
    assert captured[1] == {"R1": "fired", "R2": "cleared"}


def test_the_payload_is_the_frozen_artefact() -> None:
    store = FakeJournalStore()
    user_id, portfolio_id = uuid4(), uuid4()
    result = _generate(store, as_of="2026-07-31", portfolio_id=portfolio_id,
                       user_id=user_id, captured=[])

    payload = result.entry.payload
    assert set(payload) == {
        "engine_version", "portfolio_id", "as_of", "sections",
        "context", "rules_fired", "rule_states", "llm_used", "llm_rejected_reason",
    }
    assert payload["engine_version"] == ENGINE_VERSION
    assert payload["portfolio_id"] == str(portfolio_id)
    # `head` lives INSIDE sections, per the seam register's pinned payload
    # shape. The earlier version of this test asserted the shipped-but-diverged
    # shape instead, so the suite certified the drift rather than catching it —
    # a consumer built to the pin would have hit KeyError with everything green.
    assert set(payload["sections"]) == {"head", "f1", "f2", "f3", "f4", "f5"}
    # The archived artefact carries its own disclosures forever (F19).
    assert DISCLAIMER_SHORT in payload["sections"]["head"]
    assert NON_STATIONARITY_CAVEAT in payload["sections"]["head"]
    assert payload["llm_used"] is False


def test_load_latest_finding_is_scoped_to_the_portfolio() -> None:
    store = FakeJournalStore()
    user_id = uuid4()
    mine, theirs = uuid4(), uuid4()

    _generate(store, as_of="2026-07-31", portfolio_id=theirs,
              user_id=user_id, captured=[])
    assert load_latest_finding(store, user_id, mine) is None

    _generate(store, as_of="2026-07-31", portfolio_id=mine,
              user_id=user_id, captured=[])
    found = load_latest_finding(store, user_id, mine)
    assert found is not None
    assert found.payload["portfolio_id"] == str(mine)


def test_the_wire_value_is_the_pinned_one() -> None:
    assert PORTFOLIO_HEALTH_ENTRY_TYPE == "portfolio_health_analysis"


def test_an_evaluator_is_required_not_defaulted() -> None:
    """No default is possible: a no-rules default publishes a Finding whose §F5
    says nothing fired, with no signal that the rules never ran."""
    with pytest.raises(TypeError):
        asyncio.run(generate_and_persist_finding(
            user_id=uuid4(), portfolio_id=uuid4(), as_of="2026-07-31",
            metric_blocks=[], store=FakeJournalStore(),
        ))


# ── The orchestrator's own assembly, under a REAL provider ──────────────────


class _NarratingGateway:
    """`has_real_provider()` True — the branch every earlier test skipped."""

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


_CLEAN_NARRATION = (
    '{"f1": ["The book has been calm."], "f2": "Nothing unusual.",'
    ' "f3": "MODEL WROTE THIS", "f4": "In short, calm.",'
    ' "f5": "Nothing rose to a textbook response."}'
)


def test_an_accepted_narration_is_what_gets_persisted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "portfolio_health_llm_enabled", True)
    store = FakeJournalStore()
    gateway = _NarratingGateway(_CLEAN_NARRATION)
    result = _generate(store, as_of="2026-07-31", portfolio_id=uuid4(),
                       user_id=uuid4(), captured=[], gateway=gateway)

    assert gateway.calls == 1
    assert result.llm_used is True
    assert result.llm_rejected_reason is None
    sections = result.entry.payload["sections"]
    assert sections["f2"] == "Nothing unusual."
    assert result.entry.payload["llm_used"] is True
    # §F3 stays deterministic even on the accepted path (CR038).
    assert "MODEL WROTE THIS" not in sections["f3"]
    assert "λ=0.97" in sections["f3"]
    assert DISCLAIMER_SHORT in sections["head"]


def test_a_rejected_narration_persists_the_deterministic_report_and_the_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The assembly step is what CR040's question lands on: when the LLM path
    fails constantly, the archived artefact must be the complete deterministic
    report AND must say why it is not narrated."""
    monkeypatch.setattr(settings, "portfolio_health_llm_enabled", True)
    store = FakeJournalStore()
    gateway = _NarratingGateway(
        '{"f1": ["Volatility was 47.3%."], "f2": "x", "f3": "y", "f4": "z", "f5": "w"}'
    )
    result = _generate(store, as_of="2026-07-31", portfolio_id=uuid4(),
                       user_id=uuid4(), captured=[], gateway=gateway)

    assert result.llm_used is False
    assert result.llm_rejected_reason == "unsubstituted_digit"
    payload = result.entry.payload
    assert payload["llm_rejected_reason"] == "unsubstituted_digit"
    assert "47.3" not in payload["sections"]["f1"]
    for key in ("head", "f1", "f2", "f3", "f4", "f5"):
        assert payload["sections"][key].strip(), key


def test_a_partial_merge_of_the_two_renderings_never_reaches_the_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rejection discards the WHOLE narration. A merge that kept four accepted
    sections and swapped one would leave no way to know which sentence the bad
    number infected."""
    monkeypatch.setattr(settings, "portfolio_health_llm_enabled", True)
    store = FakeJournalStore()
    gateway = _NarratingGateway(
        '{"f1": ["The book has been calm."], "f2": "The covariance estimator agrees.",'
        ' "f3": "y", "f4": "In short, calm.", "f5": "Nothing fired."}'
    )
    result = _generate(store, as_of="2026-07-31", portfolio_id=uuid4(),
                       user_id=uuid4(), captured=[], gateway=gateway)

    assert result.llm_rejected_reason == "register_lexicon"
    sections = result.entry.payload["sections"]
    assert "The book has been calm." not in sections["f1"], (
        "the clean-looking headline came from the same rejected narration"
    )
    assert "In short, calm." not in sections["f4"]
