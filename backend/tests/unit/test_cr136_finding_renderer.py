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

from app.schemas.journal import JournalEntry
from app.services.portfolio_finding import (
    InsufficientContextError,
    build_stripped_context,
    generate_finding,
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
                {"scope": "name", "cap_pct": 35.0, "name": "AAA", "weight_pct": 41.2},
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

    def list_for_user(self, user_id, **kwargs):
        return list(self.entries), len(self.entries), None


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


# ── §F5 speech act ──────────────────────────────────────────────────────────


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
        "excess kurtosis", "square root of 252", "gross of fees",
        NON_STATIONARITY_CAVEAT, "M11 and M12",
    ):
        assert required in f3, required


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


def _generate(store, *, as_of: str, portfolio_id, user_id, captured: list):
    def _evaluate(prior_states):
        captured.append(prior_states)
        return _rules("R1"), {"R1": "fired", "R2": "cleared"}

    context_payload = compute_health(**_book())
    return asyncio.run(generate_finding(
        user_id=user_id,
        portfolio_id=portfolio_id,
        as_of=as_of,
        metric_blocks=list(context_payload["blocks"].values()),
        store=store,
        gateway=_SpyGateway(),
        evaluate=_evaluate,
    ))


def test_two_generates_on_the_same_day_write_one_entry() -> None:
    store = FakeJournalStore()
    user_id, portfolio_id = uuid4(), uuid4()
    captured: list = []

    first = _generate(store, as_of="2026-07-31", portfolio_id=portfolio_id,
                      user_id=user_id, captured=captured)
    assert first.created is True
    assert store.appends == 1

    second = _generate(store, as_of="2026-07-31", portfolio_id=portfolio_id,
                       user_id=user_id, captured=captured)
    assert second.created is False
    assert second.entry.id == first.entry.id
    assert store.appends == 1, "the idempotent replay must not write"
    assert len(captured) == 1, "...and must not re-run the rule engine"


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
        "engine_version", "portfolio_id", "as_of", "head_disclosure", "sections",
        "context", "rules_fired", "rule_states", "llm_used", "llm_rejected_reason",
    }
    assert payload["engine_version"] == ENGINE_VERSION
    assert payload["portfolio_id"] == str(portfolio_id)
    assert set(payload["sections"]) == {"f1", "f2", "f3", "f4", "f5"}
    # The archived artefact carries its own disclosures forever (F19).
    assert DISCLAIMER_SHORT in payload["head_disclosure"]
    assert NON_STATIONARITY_CAVEAT in payload["head_disclosure"]
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
