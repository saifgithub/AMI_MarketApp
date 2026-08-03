"""Portfolio Health Finding (CR136 M06) — deterministic §F1–§F5 renderer with head disclosure, closed numeric allow-list validator + register check for the optional LLM narration path, and journal persistence with (portfolio_id, as_of) idempotency.

Every path ends in a complete, correct report. The LLM is optional, config-gated,
and only ever rewrites prose the engine already produced; any provider failure,
schema failure, unregistered number or register-lexicon leak discards the entire
model output and serves the deterministic rendering, which emits only registered
tokens and therefore validates by construction.

**The validator is a closed allow-list, not a digit rule.** Rev 3's
digit-sequence validator was measured and deleted: it rejected 10–13 of the 25
digit runs in the CR's OWN mandated §F3 content, flipped verdicts on the fourth
decimal of a rounding path, and rejected R3's own deterministic fallback. What
replaced it is built per Finding from the same stripped context the model saw —
every numeric leaf of every sufficient block, every value the rule engine
interpolated, plus a checked-in fixed set — rendered at each admissible dp under
both round-half-up and round-half-even, each ±1 ulp. Lookup is SCALE-AWARE and
never the union of the two sets: the union was measured to false-accept "Your
beta is 62." on a book whose 0.62 lives in the percent set.

**Stripping happens before anything else.** An insufficient block is dropped
entirely — key, metric name, every field — before template selection and before
any prompt string exists. The model never sees the metric's name, so there is
nothing to narrate. That is the only enforcement that survives contact with a
model (CR038: prompt instructions are not controls), and it is why the
uncertainty contract's `null` has to mean exactly one thing.

**§F5 is conditional-educational by construction.** Each item is a fired rule's
fixed template with the user's own number as the trigger — a general statement of
textbook practice, never an instruction. The publisher's exclusion is unavailable
to us and the live site states the product does not give investment advice, so
the speech act has to hold on every path, including this deterministic one.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP
from typing import Iterable, Sequence
from uuid import UUID

from app.core.config import settings
from app.core.logging import logger
from app.schemas.journal import JournalEntry, JournalEntryCreate
from app.services.portfolio_health_constants import (
    DISCLAIMER_SHORT,
    ENGINE_VERSION,
    ETF_OVERLAP_DISCLOSURE,
    F1_PARTIAL_MARKER,
    F5_FORBIDDEN_IMPERATIVES,
    F5_FORBIDDEN_PHRASES,
    HEADLINE_MAX_WORDS,
    METRIC_VALUE_UNIT,
    NON_STATIONARITY_CAVEAT,
    PERCENT_UNIT_KEYS,
    PORTFOLIO_HEALTH_ENTRY_TYPE,
    REGISTER_LEXICON,
    RULE_SLOT_SCALE,
    TIER2_MDD_WINDOW_SNAPSHOTS,
    UNIT_FRACTION,
    UNIT_PERCENT,
    VALIDATOR_FIXED_PCT,
    VALIDATOR_FIXED_RAW,
)
from app.services.portfolio_rules import RULE_TEMPLATES

PCT = "pct"
RAW = "raw"

_NUMBER_RE = re.compile(r"[−-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?|[−-]?\d+(?:\.\d+)?")
_PCT_SUFFIX_RE = re.compile(r"\s?(%|pp\b|percent\b|percentage point)")

_DISPLAY_NAMES = {
    "portfolio_volatility": "Portfolio volatility (annualised)",
    "beta": "Market sensitivity (beta vs the S&P 500)",
    "tracking_error": "Tracking error vs the S&P 500",
    "effective_bets": "Effective independent bets",
    "risk_contribution": "Risk contribution by holding",
    "mcr": "Marginal contribution to risk",
    "weight_concentration": "Invested weight concentration",
    "typical_bad_month": "A typical bad month",
    "scenario_panel": "Past-episode backcast",
    "realised_max_drawdown": "Deepest realised fall (rolling window)",
    "realised_return": "Realised return over the window",
}

_WHAT_IT_MEASURES = {
    "portfolio_volatility": (
        "How widely the whole book's daily value has swung, stated per year."
    ),
    "beta": (
        "How much the book has moved for each move in the market, and how much "
        "of its day-to-day motion the market accounts for."
    ),
    "tracking_error": (
        "How differently the book has moved from the market, rather than how "
        "much."
    ),
    "effective_bets": (
        "How many genuinely independent positions the book behaves like, which "
        "is not the same as how many it holds."
    ),
    "risk_contribution": (
        "Which holdings own the book's risk, as distinct from which own its "
        "money."
    ),
    "mcr": (
        "How much the book's risk changes per dollar moved in or out of each "
        "holding."
    ),
    "weight_concentration": (
        "How evenly the invested money is spread, counting weights only — this "
        "one is blind to whether the holdings move together."
    ),
    "typical_bad_month": (
        "A month bad enough to happen about one time in twenty, at the "
        "dispersion measured over this window."
    ),
    "scenario_panel": (
        "What today's holdings would have done in a named past episode, given "
        "only their market sensitivity."
    ),
    "realised_max_drawdown": (
        "The deepest peak-to-trough fall the book actually took inside the "
        "stated window."
    ),
    "realised_return": "What the book actually returned over the stated window.",
}

_CITATIONS = {
    "portfolio_volatility": "EWMA-weighted covariance; Markowitz (1952)",
    "beta": "CAPM; weighted least squares over the same covariance",
    "tracking_error": "Derived identity from the same covariance",
    "effective_bets": "Choueifaty & Coignard (2008), diversification ratio",
    "risk_contribution": "Euler decomposition of a homogeneous risk measure",
    "mcr": "Marginal contribution to risk, same decomposition",
    "weight_concentration": "Herfindahl–Hirschman index over invested weights",
    "typical_bad_month": "Gaussian quantile at the measured dispersion",
    "scenario_panel": "Market sensitivity applied to a named historical episode",
    "realised_max_drawdown": "Peak-to-trough over the stored value series",
    "realised_return": "Simple return over the stored value series",
}

_EPISODE_LABELS = {
    "covid_2020": "COVID crash (Feb–Mar 2020)",
    "drawdown_2022": "2022 drawdown (Jan–Oct 2022)",
}

_NO_SE_BY_DESIGN = {"effective_bets", "risk_contribution", "mcr"}

# retranslate:[ar,ms]
_ZERO_COST_LINE = (
    "A note beside any trimming thought: this simulation charges no "
    "commissions, spreads, or taxes. In measured brokerage data (Barber & "
    "Odean), about 97% of the penalty from frequent trading is invisible at "
    "zero cost."
)
# retranslate:[ar,ms]
_F5_NOTHING_FIRED = (
    "No review threshold was crossed this run. The sections above describe the "
    "measured book; nothing here rose to a textbook response."
)


class InsufficientContextError(Exception):
    """Not one metric block survived the strip. M07 maps this to the
    not-enough-data state; the copy naming OUR limit rather than the user's book
    belongs there, not here."""


@dataclass
class ValidationFailure:
    reason: str
    section: str
    tokens: list[str] = field(default_factory=list)


@dataclass
class Allowlist:
    pct: set[Decimal]
    raw: set[Decimal]


@dataclass
class FindingResult:
    entry: JournalEntry
    created: bool
    llm_used: bool
    llm_rejected_reason: str | None


# ── Formatting ──────────────────────────────────────────────────────────────


def _fmt(value: float, dp: int) -> str:
    """Round-half-up at `dp`. One of the two roundings the allow-list admits, so
    the deterministic rendering validates by construction."""
    quant = Decimal(1).scaleb(-dp)
    return str(Decimal(str(value)).quantize(quant, rounding=ROUND_HALF_UP))


def _pct(value: float, dp: int = 1) -> str:
    return _fmt(value * 100.0, dp)


# ── 3.2 Strip ───────────────────────────────────────────────────────────────


def build_stripped_context(metric_blocks: list[dict], *, as_of: str) -> dict:
    """Only the sufficient blocks, whole. An insufficient block is dropped
    entirely — the model never sees its name, so there is nothing to narrate."""
    kept = [b for b in metric_blocks if b.get("sufficient")]
    if not kept:
        raise InsufficientContextError(
            "no sufficient metric block survived the strip"
        )
    return {"as_of": as_of, "metrics": kept}


def _block(context: dict, metric: str) -> dict | None:
    for block in context["metrics"]:
        if block.get("metric") == metric:
            return block
    return None


# ── 3.3 Deterministic renderer ──────────────────────────────────────────────


def render_head_disclosure(context: dict) -> str:
    """Always deterministic, on both paths — the LLM never generates it (F19).

    Stored in the payload as well as rendered, because the journal entry is what
    survives and gets screenshotted, and an archived artefact has to carry its
    own disclosures forever.
    """
    anchor = _block(context, "portfolio_volatility") or _block(context, "beta")
    if anchor is None:
        anchor = context["metrics"][0]
    window_days = anchor.get("window_days") or 0
    n_obs = anchor.get("n_observations") or 0
    t_eff = anchor.get("t_eff")
    t_eff_text = _fmt(t_eff, 1) if t_eff else "—"
    return "\n".join([
        f"> **{DISCLAIMER_SHORT}**",
        "> All figures are gross of fees — this simulation charges no "
        "commissions, spreads, or taxes; live trading does.",
        "> Every forward-looking number below is a backcast: today's holdings "
        "weighted against past returns. It is not a forecast.",
        f"> Window: {window_days} trading days, {n_obs} observed returns; "
        f"estimator: EWMA-weighted covariance, λ=0.97, effective sample ≈ "
        f"{t_eff_text} days.",
        f"> {NON_STATIONARITY_CAVEAT}",
    ])


def _headlines(context: dict) -> list[str]:
    """3–5 one-liners, each one number and its plain meaning. Every template is
    ≤14 tokens so the partial marker's 2 keep it inside the 16-word cap."""
    out: list[str] = []

    def add(text: str, block: dict) -> None:
        out.append(text + (F1_PARTIAL_MARKER if block.get("partial") else ""))

    vol = _block(context, "portfolio_volatility")
    benchmark_vol = context.get("benchmark_vol_ann")
    if vol and benchmark_vol:
        add(
            f"Annualised volatility {_pct(vol['value'])}%; the S&P 500 measured "
            f"{_pct(benchmark_vol)}% over the same window.",
            vol,
        )
    elif vol:
        add(f"Annualised volatility {_pct(vol['value'])}% over the measured window.", vol)

    risk = _block(context, "risk_contribution")
    if risk and risk.get("top"):
        top = risk["top"]
        add(
            f"{top['ticker']} drives {_pct(top['risk_share'], 0)}% of risk while "
            f"holding {_pct(top['invested_weight'], 0)}% of invested money.",
            risk,
        )

    bets = _block(context, "effective_bets")
    weights = _block(context, "weight_concentration")
    if bets and weights:
        add(
            f"{weights['holdings_count']} holdings currently behave like "
            f"{_fmt(bets['value'], 1)} effective independent bets.",
            bets,
        )

    mdd = _block(context, "realised_max_drawdown")
    if mdd:
        add(
            f"Deepest fall in the last {TIER2_MDD_WINDOW_SNAPSHOTS} trading "
            f"days: {_fmt(mdd['value'], 1)}% peak-to-trough.",
            mdd,
        )

    beta = _block(context, "beta")
    if beta and beta.get("r_squared") is not None:
        only = "only " if beta.get("low_explanatory_power") else ""
        add(
            f"Moved about {_fmt(beta['value'], 2)}× the S&P 500; the market "
            f"explains {only}{_pct(beta['r_squared'], 0)}% of daily moves.",
            beta,
        )
    return out[:5]


def _f2(context: dict, partial_note: str) -> str:
    sentences: list[str] = []
    vol = _block(context, "portfolio_volatility")
    te = _block(context, "tracking_error")
    benchmark_vol = context.get("benchmark_vol_ann")
    if vol and benchmark_vol:
        risk_posture = (
            f"Over the measured window this book swung "
            f"{_pct(vol['value'])}% a year against the S&P 500's "
            f"{_pct(benchmark_vol)}%."
        )
        if te:
            risk_posture += (
                f" Its movement apart from the market was "
                f"{_pct(te['value'])}% a year."
            )
        sentences.append(risk_posture)

    bets = _block(context, "effective_bets")
    weights = _block(context, "weight_concentration")
    if bets and weights:
        sentences.append(
            f"The {weights['holdings_count']} holdings behave like "
            f"{_fmt(bets['value'], 1)} independent ones; a low count can come "
            f"from holdings that move together or from one position much larger "
            f"or more volatile than the rest, so the contribution table below is "
            f"what tells the two apart."
        )

    risk = _block(context, "risk_contribution")
    if risk and risk.get("top"):
        top = risk["top"]
        sentences.append(
            f"{top['ticker']} carries {_pct(top['risk_share'], 0)}% of the "
            f"book's risk while holding {_pct(top['invested_weight'], 0)}% of "
            f"its invested money."
        )

    beta = _block(context, "beta")
    if beta and beta.get("r_squared") is not None:
        only = "only " if beta.get("low_explanatory_power") else ""
        sentences.append(
            f"The book moved about {_fmt(beta['value'], 2)} times the market, "
            f"and the market explains {only}{_pct(beta['r_squared'], 0)}% of its "
            f"day-to-day motion."
        )

    anchor = vol or beta or context["metrics"][0]
    sentences.append(
        f"Everything above is measured over {anchor.get('window_days', 0)} "
        f"trading days ({anchor.get('n_observations', 0)} observed returns) and "
        f"is a backcast — today's holdings weighted against past returns, not a "
        f"forecast{partial_note}."
    )
    return " ".join(sentences)


def _unit(metric: str) -> str:
    """A metric with no pinned unit is a renderer bug, not a default. Guessing
    the fraction convention on a Tier-2 block published a 15.34% drawdown as
    1534.00%, so the lookup raises rather than assumes."""
    unit = METRIC_VALUE_UNIT.get(metric)
    if unit is None:
        raise ValueError(
            f"no unit pinned for metric id {metric!r} — METRIC_VALUE_UNIT must "
            f"cover the engine's frozen metric-id set exactly; a default would "
            f"silently scale the value by 100 in one direction or the other"
        )
    return unit


def _f3_metric_block(block: dict, context: dict) -> str:
    metric = block["metric"]
    name = _DISPLAY_NAMES.get(metric)
    if name is None:
        raise ValueError(
            f"no display name for metric id {metric!r} — the renderer's map must "
            f"cover the engine's frozen metric-id set exactly, and a silent skip "
            f"would drop a measured number out of the report"
        )
    unit = _unit(metric)
    lines = [f"**{name}**"]

    value = block.get("value")
    if metric in {"weight_concentration"}:
        lines.append(
            f"Value: {_fmt(value, 3)} (effective holdings "
            f"{_fmt(block['effective_n'], 1)})."
        )
    elif metric in {"beta", "effective_bets"}:
        lines.append(f"Value: {_fmt(value, 2)}.")
    elif metric == "scenario_panel":
        for episode in block.get("episodes", []):
            label = _EPISODE_LABELS.get(episode["id"], episode["id"])
            lines.append(
                f"{label}: the market fell "
                f"{_pct(abs(episode['benchmark_return']))}%, which for this "
                f"book's measured sensitivity backcasts to "
                f"{_pct(abs(episode['implied_portfolio_return']))}%. A "
                f"what-if on today's holdings, not a prediction."
            )
    elif unit == UNIT_PERCENT:
        lines.append(f"Value: {_fmt(value, 2)}%.")
    else:
        lines.append(f"Value: {_pct(value, 2)}%.")

    se = block.get("standard_error")
    if se is not None:
        # The SE carries the metric's own unit. β = 1.19 with SE 0.093 read
        # "Standard error 9.27%", which is not 9.27% of anything — it is ±0.09
        # on the beta itself.
        if unit == UNIT_FRACTION:
            se_text = f"{_pct(se, 2)}%"
        elif unit == UNIT_PERCENT:
            se_text = f"{_fmt(se, 2)}%"
        else:
            se_text = _fmt(se, 2)
        lines.append(
            f"Standard error {se_text}, effective sample "
            f"{_fmt(block['t_eff'], 1)} days."
        )
    elif metric in _NO_SE_BY_DESIGN:
        lines.append(
            "Standard error: null by design — stability is handled by rule "
            "hysteresis rather than by a published interval."
        )

    lines.append(
        f"{block.get('n_observations', 0)} returns over "
        f"{block.get('window_days', 0)} trading days. "
        f"Method: {_CITATIONS.get(metric, 'see the estimator disclosure below')}."
    )
    lines.append(_WHAT_IT_MEASURES.get(metric, ""))

    if block.get("partial") and block.get("dropped_holdings"):
        excluded = ", ".join(d["ticker"] for d in block["dropped_holdings"])
        reasons = ", ".join(
            sorted({d.get("reason", "unknown") for d in block["dropped_holdings"]})
        )
        lines.append(f"Data quality: excludes {excluded} ({reasons}).")
    if metric == "weight_concentration" and block.get("contains_etfs"):
        lines.append(f"Note: this figure {ETF_OVERLAP_DISCLOSURE}")
    return "\n".join(line for line in lines if line)


def _f3_standing_disclosures(context: dict) -> str:
    """Appended to §F3 on BOTH paths — deterministically, even under LLM
    narration. Rev 4 mandates this content once per Finding, and prompt
    instructions are not controls (CR038), so appending it is what makes it
    structural."""
    anchor = _block(context, "portfolio_volatility") or context["metrics"][0]
    t_eff = anchor.get("t_eff")
    t_eff_text = _fmt(t_eff, 1) if t_eff else "—"
    return "\n".join([
        "**Method and its limits**",
        f"Estimator: EWMA-weighted sample covariance, λ=0.97 (RiskMetrics "
        f"Technical Document, 4th ed., §5.3.2), weighted-demeaned, over the "
        f"risky holdings plus the SPY benchmark leg; effective sample ≈ "
        f"{t_eff_text} days. Chosen because an equal-weight window re-prices an "
        f"old shock on the day it leaves the window — this one responds at the "
        f"event instead.",
        "No shrinkage is applied. Constant-correlation shrinkage (Ledoit & Wolf, "
        "2004) was measured to suppress the correlated-cluster alarm this report "
        "exists to raise, and it is undefined on a cash row; it is the remedy "
        "for inverting a covariance matrix, and nothing here inverts one.",
        "Related work: Markowitz (1952); Choueifaty & Coignard (2008); CAPM.",
        "Sampling error is understated by a normal assumption. At a "
        "window-realistic excess kurtosis of 3–6 the standard error is likely "
        "2.0–2.5pp, or 10–13% of the estimate; a crash-inclusive window (excess "
        "kurtosis near 30) raises the inflation factor to 4.0×.",
        "Annualisation multiplies by the square root of 252 trading days, which "
        "assumes days are independent. They are not exactly, and the same "
        "objection applies to every annualised figure here.",
        "All figures are gross of fees: this simulation charges no commissions, "
        "spreads, or taxes, and live trading does.",
        "Every forward-looking figure is a backcast of today's holdings against "
        "past returns.",
        NON_STATIONARITY_CAVEAT,
        "Related lessons: M11 and M12 in the Body of Knowledge.",
    ])


def _f4(context: dict) -> str:
    vol = _block(context, "portfolio_volatility")
    bets = _block(context, "effective_bets")
    risk = _block(context, "risk_contribution")
    anchor = vol or context["metrics"][0]
    parts: list[str] = []
    if vol and bets and risk and risk.get("top"):
        parts.append(
            f"Taken together: a book swinging {_pct(vol['value'])}% a year, "
            f"behaving like {_fmt(bets['value'], 1)} independent positions, with "
            f"{risk['top']['ticker']} carrying the largest share of the risk."
        )
    elif vol:
        parts.append(
            f"Taken together: a book swinging {_pct(vol['value'])}% a year over "
            f"the measured window."
        )
    parts.append(
        f"All of it is measured over {anchor.get('window_days', 0)} trading days "
        f"and describes the regime just past, not the one ahead."
    )
    return " ".join(parts)


def _f5(rule_results: Sequence[dict]) -> str:
    fired = [r for r in rule_results if r.get("fired")]
    if not fired:
        return _F5_NOTHING_FIRED

    items: list[str] = []
    for result in fired:
        rule_id = result["rule_id"]
        template = RULE_TEMPLATES.get(rule_id)
        if template is None:
            raise ValueError(
                f"rule {rule_id!r} fired but has no template — §F5 is the only "
                f"place a fired rule reaches the user, and dropping it silently "
                f"publishes a Finding that says nothing fired when something did"
            )
        slots = result.get("slots") or {}
        if rule_id == "R0":
            for breach in slots.get("breaches", []):
                text = template.format(
                    scope="holding" if breach["scope"] == "name" else "sector",
                    cap=_fmt(breach["cap_pct"], 1),
                    name=breach["name"],
                    weight=_fmt(breach["weight_pct"], 1),
                )
                if slots.get("etf_disclosure"):
                    text += f" This count {ETF_OVERLAP_DISCLOSURE}"
                items.append(text)
            continue
        if rule_id == "R5":
            items.append(template.format(
                dropped=", ".join(slots.get("dropped", [])),
                reasons=", ".join(slots.get("reasons", [])),
                covered=_fmt(slots.get("covered", 0.0), 1),
            ))
            continue
        try:
            items.append(template.format(**slots))
        except KeyError as exc:
            raise ValueError(
                f"rule {rule_id} fired without the slot its template needs: {exc}"
            ) from exc

    if any(r["rule_id"] in {"R0", "R1"} for r in fired):
        items.append(_ZERO_COST_LINE)
    return "\n\n".join(f"- {item}" for item in items)


def render_deterministic_sections(
    context: dict, rule_results: Sequence[dict],
) -> dict[str, str]:
    partial_blocks = [b for b in context["metrics"] if b.get("partial")]
    partial_note = ""
    if partial_blocks:
        dropped = sorted({
            d["ticker"]
            for b in partial_blocks
            for d in b.get("dropped_holdings", [])
        })
        r5 = next(
            (r for r in rule_results if r["rule_id"] == "R5" and r.get("fired")),
            None,
        )
        covered = (r5 or {}).get("slots", {}).get("covered")
        covered_text = f", {_fmt(covered, 1)}% of invested value covered" if covered else ""
        partial_note = f", excluding {', '.join(dropped)}{covered_text}"

    f3_parts = [
        _f3_metric_block(block, context) for block in context["metrics"]
    ]
    f3_parts.append(_f3_standing_disclosures(context))

    return {
        "f1": "\n".join(f"- {line}" for line in _headlines(context)),
        "f2": _f2(context, partial_note),
        "f3": "\n\n".join(f3_parts),
        "f4": _f4(context),
        "f5": _f5(rule_results),
    }


# ── 3.4 Validator ───────────────────────────────────────────────────────────


def _register(target: set[Decimal], rendered: str, dp: int) -> None:
    value = Decimal(rendered)
    ulp = Decimal(1).scaleb(-dp)
    for candidate in (value, value + ulp, value - ulp):
        target.add(candidate.normalize())
        target.add((-candidate).normalize())


def _register_number(
    value: float, scale: str, allow: Allowlist, *, already_percent: bool = False
) -> None:
    """`already_percent` registers a Tier-2 value into the PERCENT set without
    the ×100: its unit is already percent, so 19.69 must be admitted as "19.7%"
    and 1969 must not be admitted at all."""
    target = allow.pct if scale == PCT else allow.raw
    number = value * 100.0 if scale == PCT and not already_percent else value
    dps = (0, 1, 2) if scale == PCT else (1, 2, 3, 4)
    for dp in dps:
        quant = Decimal(1).scaleb(-dp)
        for rounding in (ROUND_HALF_UP, ROUND_HALF_EVEN):
            _register(
                target,
                str(Decimal(str(number)).quantize(quant, rounding=rounding)),
                dp,
            )
    if scale == RAW:
        target.add(Decimal(str(number)).normalize())
        target.add((-Decimal(str(number))).normalize())


def _numeric_leaves(node) -> Iterable[float]:
    if isinstance(node, bool):
        return
    if isinstance(node, (int, float)):
        yield float(node)
    elif isinstance(node, dict):
        for value in node.values():
            yield from _numeric_leaves(value)
    elif isinstance(node, (list, tuple)):
        for value in node:
            yield from _numeric_leaves(value)


def build_allowlist(context: dict, rule_results: Sequence[dict]) -> Allowlist:
    """Every number the Finding is allowed to contain, built from the same
    stripped context the model saw. If it is not in the payload, it may not be
    said."""
    allow = Allowlist(pct=set(), raw=set())

    # (a) every numeric leaf of every sufficient block, at both scales — the
    # block does not know how the prose will render it. The one thing the block
    # DOES know is its unit: a percent-unit value is registered into the percent
    # set verbatim and never at the ×100 scale, so the double-scaled reading of
    # its own number is not a token this Finding may contain.
    for key, node in context.items():
        if key == "metrics":
            continue
        for value in _numeric_leaves(node):
            _register_number(value, PCT, allow)
            _register_number(value, RAW, allow)

    for block in context["metrics"]:
        percent_unit = _unit(block["metric"]) == UNIT_PERCENT
        for key, node in block.items():
            already = percent_unit and key in PERCENT_UNIT_KEYS
            for value in _numeric_leaves(node):
                _register_number(value, PCT, allow, already_percent=already)
                _register_number(value, RAW, allow)

    # (b) every value the rule engine interpolated into a template. Rule slots
    # are ALREADY in their display unit — a "pct" slot holds 45.3, not 0.453 —
    # so they register through the same dp ladder as everything else with the
    # ×100 suppressed. Registering them only at 2 dp was measured to reject the
    # engine's own §F5 line: a breach weight of 41.25 renders "41.3%", which a
    # ±0.01 window around 41.25 does not contain.
    for result in rule_results:
        scales = RULE_SLOT_SCALE.get(result["rule_id"], {})
        slots = result.get("slots") or {}
        for key, scale in scales.items():
            if key in slots and isinstance(slots[key], (int, float)):
                _register_number(
                    float(slots[key]), scale, allow, already_percent=scale == PCT,
                )
        for breach in slots.get("breaches", []) if isinstance(slots, dict) else []:
            for key in ("cap_pct", "weight_pct"):
                _register_number(
                    float(breach[key]), PCT, allow, already_percent=True,
                )

    # (c) the checked-in fixed sets.
    for token in VALIDATOR_FIXED_PCT:
        allow.pct.add(Decimal(token).normalize())
        allow.pct.add((-Decimal(token)).normalize())
    for token in VALIDATOR_FIXED_RAW:
        allow.raw.add(Decimal(token).normalize())
        allow.raw.add((-Decimal(token)).normalize())

    # (d) counts, verbatim.
    for block in context["metrics"]:
        for key in ("n_observations", "window_days", "holdings_count"):
            if isinstance(block.get(key), int):
                allow.raw.add(Decimal(block[key]).normalize())
    allow.raw.add(Decimal(TIER2_MDD_WINDOW_SNAPSHOTS).normalize())
    return allow


@dataclass
class NumToken:
    value: Decimal
    scale: str
    raw_text: str


def tokenize_numbers(text: str) -> list[NumToken]:
    tokens: list[NumToken] = []
    for match in _NUMBER_RE.finditer(text):
        raw = match.group(0)
        cleaned = raw.replace(",", "").replace("−", "-")
        try:
            value = Decimal(cleaned).normalize()
        except Exception:
            continue
        tail = text[match.end():match.end() + 20]
        scale = PCT if _PCT_SUFFIX_RE.match(tail) else RAW
        tokens.append(NumToken(value=value, scale=scale, raw_text=raw))
    return tokens


def validate_sections(
    sections: dict[str, str], allowlist: Allowlist,
) -> ValidationFailure | None:
    for section_id in ("f1", "f2", "f3", "f4", "f5"):
        text = sections.get(section_id) or ""
        bad: list[str] = []
        for token in tokenize_numbers(text):
            members = allowlist.pct if token.scale == PCT else allowlist.raw
            if token.value not in members:
                bad.append(token.raw_text)
        if bad:
            return ValidationFailure(
                reason="unregistered_number", section=section_id, tokens=bad,
            )
    return None


# ── 3.5 Register check ──────────────────────────────────────────────────────


def _lexicon_patterns() -> list[tuple[str, re.Pattern]]:
    patterns: list[tuple[str, re.Pattern]] = []
    for term in REGISTER_LEXICON:
        if term in {"eigen", "heteroskedastic"}:
            patterns.append((term, re.compile(rf"\b{term}\w*", re.I)))
        elif term == "R²":
            patterns.append((term, re.compile(r"R²|\bR\^?2\b")))
        else:
            patterns.append((term, re.compile(rf"\b{re.escape(term)}\b", re.I)))
    return patterns


_LEXICON = _lexicon_patterns()


def register_check(sections: dict[str, str]) -> ValidationFailure | None:
    """§F1/§F2/§F5 are the plain-language register; §F3/§F4 and the head block
    name the estimator by design and are exempt."""
    for section_id in ("f1", "f2", "f5"):
        text = sections.get(section_id) or ""
        for term, pattern in _LEXICON:
            if pattern.search(text):
                return ValidationFailure(
                    reason="register_lexicon", section=section_id, tokens=[term],
                )

    for line in (sections.get("f1") or "").splitlines():
        headline = line.lstrip("-* ").strip()
        if headline and len(headline.split()) > HEADLINE_MAX_WORDS:
            return ValidationFailure(
                reason="headline_length", section="f1", tokens=[headline],
            )

    f5 = sections.get("f5") or ""
    lowered = f5.lower()
    for phrase in F5_FORBIDDEN_PHRASES:
        if phrase in lowered:
            return ValidationFailure(
                reason="imperative", section="f5", tokens=[phrase],
            )
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", f5):
        first = sentence.lstrip("-*• ").strip().split(" ")[0].strip(",.;:").lower()
        if first in F5_FORBIDDEN_IMPERATIVES:
            return ValidationFailure(
                reason="imperative", section="f5", tokens=[first],
            )
    return None


# ── 3.5b Slot map — the attribution control (CR136-M06 audit BLOCKER B1) ────


_SLOT_RE = re.compile(r"\{\{([a-z_]+)\}\}")
_DIGIT_RE = re.compile(r"\d")


def build_slot_map(context: dict) -> dict[str, str]:
    """Every number the narration may contain, keyed by WHAT IT IS.

    This is the attribution control. The previous design handed the model the
    numbers and checked afterwards that whatever it typed appeared *somewhere*
    in the payload — which constrains vocabulary, not assignment, and measured
    ~50 of 101 whole percentages legal on an ordinary book (audit B1). The
    model now never types a digit at all: it writes `{{vol_ann_pct}}` and this
    map decides what that renders as, so a figure cannot land on a metric it
    does not belong to. Correct by construction rather than by check.

    Slot names carry NO DIGITS, which is what lets the guard be the flat rule
    "after removing slot spans, any remaining digit is a rejection" — `r2`
    would have made that rule ambiguous, hence `market_explains_pct`.

    Values are rendered with the SAME helpers the deterministic path uses, so
    the two renderings of one metric can never disagree.
    """
    slots: dict[str, str] = {}

    def put(name: str, value: str | None) -> None:
        if value is not None:
            slots[name] = value

    vol = _block(context, "portfolio_volatility")
    if vol and vol.get("value") is not None:
        put("vol_ann_pct", f"{_pct(vol['value'])}%")
    benchmark_vol = context.get("benchmark_vol_ann")
    if benchmark_vol is not None:
        put("benchmark_vol_ann_pct", f"{_pct(benchmark_vol)}%")

    beta = _block(context, "beta")
    if beta and beta.get("value") is not None:
        put("beta_ratio", _fmt(beta["value"], 2))
        if beta.get("r_squared") is not None:
            put("market_explains_pct", f"{_pct(beta['r_squared'], 0)}%")

    te = _block(context, "tracking_error")
    if te and te.get("value") is not None:
        put("tracking_error_pct", f"{_pct(te['value'])}%")

    risk = _block(context, "risk_contribution")
    if risk and risk.get("top"):
        top = risk["top"]
        put("top_risk_ticker", str(top["ticker"]))
        put("top_risk_share_pct", f"{_pct(top['risk_share'], 0)}%")
        put("top_risk_weight_pct", f"{_pct(top['invested_weight'], 0)}%")

    bets = _block(context, "effective_bets")
    if bets and bets.get("value") is not None:
        put("effective_bets", _fmt(bets["value"], 1))

    weights = _block(context, "weight_concentration")
    if weights and weights.get("holdings_count") is not None:
        put("holdings_count", str(weights["holdings_count"]))

    bad = _block(context, "typical_bad_month")
    if bad and bad.get("value") is not None:
        put("typical_bad_month_pct", f"{_pct(bad['value'])}%")

    mdd = _block(context, "realised_max_drawdown")
    if mdd and mdd.get("value") is not None:
        put("realised_max_drawdown_pct", f"{_fmt(mdd['value'], 1)}%")

    ret = _block(context, "realised_return")
    if ret and ret.get("value") is not None:
        put("realised_return_pct", f"{_fmt(ret['value'], 1)}%")

    cash = context.get("cash_pct_total")
    if cash is not None:
        put("cash_pct", f"{_fmt(cash, 1)}%")

    return slots


def substitute_slots(
    text: str, slots: dict[str, str],
) -> tuple[str | None, ValidationFailure | None]:
    """`{{name}}` → its value. Returns `(None, failure)` on any violation.

    Two rejections, both closed:
    - an unknown slot name (the model invented a reference), and
    - **any digit outside a slot span** — the model typed a number itself,
      which is the whole thing this design exists to prevent.
    """
    unknown = [n for n in _SLOT_RE.findall(text) if n not in slots]
    if unknown:
        return None, ValidationFailure(
            reason="unknown_slot", section=None, tokens=sorted(set(unknown)),
        )
    stripped = _SLOT_RE.sub("", text)
    stray = _DIGIT_RE.findall(stripped)
    if stray:
        return None, ValidationFailure(
            reason="unsubstituted_digit", section=None, tokens=[stripped.strip()[:120]],
        )
    return _SLOT_RE.sub(lambda m: slots[m.group(1)], text), None


# ── 3.6 LLM path ────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You rewrite an already-computed portfolio risk report into plain language for the person who owns the book.

**NEVER WRITE A DIGIT.** Not one, anywhere, for any reason. Every number is inserted for you afterwards from the `slots` object you are given. To place a number, write its slot name in double braces — for example `{{vol_ann_pct}}` — and it will be replaced by the correct, already-formatted value. `slots` shows you each value so you can phrase the sentence around its size, but you must type the NAME, never the value.

Output containing any digit outside a slot reference is discarded in full and the reader gets a fixed template instead, so a single typed number costs the whole narration.

Use only slot names present in `slots`. Do not invent a slot name. Do not compute, compare, or combine values yourself — if a comparison is not already in the JSON, do not make it.

Number-bearing statements about volatility, beta, diversification and risk contribution describe the measured window only and are backcasts of today's holdings.

Sections f1, f2 and f4 are plain language: no statistics jargon, no estimator names, no "standard error", no "covariance", no "R-squared". Explanatory power is written ONLY as "the market explains {{market_explains_pct}} of this book's day-to-day moves".

f1: 3 to 5 headlines, each 16 words or fewer, one slot reference and its plain meaning each.
f2: 4 to 8 descriptive sentences. No advice. No claims about returns or performance.
f4: 2 to 4 sentences tying the picture together. No slot references it has not already used.

Output ONLY this JSON object and nothing else:
{"f1": ["..."], "f2": "...", "f4": "..."}"""


async def llm_render_sections(
    context: dict,
    rule_results: Sequence[dict],
    gateway,
    *,
    user_id: UUID,
    deterministic: dict[str, str],
) -> tuple[dict[str, str] | None, str | None]:
    """Returns `(sections, rejected_reason)`. `None` sections means the caller
    serves the deterministic rendering — which is a complete, correct report,
    not a degraded one."""
    if not settings.portfolio_health_llm_enabled:
        logger.info("portfolio_finding_llm_skipped", reason="disabled_by_config")
        return None, None
    if gateway is None or not gateway.has_real_provider():
        logger.info("portfolio_finding_llm_skipped", reason="no_real_provider")
        return None, None

    slots = build_slot_map(context)
    if not slots:
        # Nothing citable survived sufficiency, so there is nothing for the
        # model to place. The deterministic rendering already says so plainly.
        logger.info("portfolio_finding_llm_skipped", reason="no_slots")
        return None, None

    # §F5 is NOT sent and NOT accepted back (CR136-M06 audit MAJOR M1): its
    # advice denylist let 9 of 10 ordinary paraphrases through, and it is the
    # compliance perimeter (15 U.S.C. §80b-2(a)(11)(D) / Lowe v. SEC). It ships
    # rule-engine-templated on both paths, so the model cannot phrase it at all.
    # A classifier-based control is future work, deliberately not MVP.
    payload = {
        "context": context,
        "slots": slots,
        "f3": deterministic["f3"],
        "fired_rule_ids": [r["rule_id"] for r in rule_results if r.get("fired")],
    }

    try:
        from app.services.llm_gateway import ChatMessage

        chunks: list[str] = []
        async for chunk in gateway.stream_chat(
            system_prompt=_SYSTEM_PROMPT,
            messages=[ChatMessage(role="user", content=json.dumps(payload))],
            model_tier="mid",
            max_tokens=4096,
            audit_user_id=user_id,
            audit_agent_id="portfolio_health",
            audit_flow="portfolio_health_finding",
        ):
            chunks.append(chunk)
        raw = "".join(chunks)
    except Exception as exc:
        # ERROR, not WARN, and it keeps its own event name: "nothing came back"
        # is a different operational fact from "what came back was rejected".
        # Both must be ERROR — a vLLM outage that only ever logs WARN is a
        # silent degrade, which is the exact shape CR040 exists to surface, and
        # M11's live verification greps at ERROR.
        logger.error(
            "portfolio_finding_llm_failed", reason="provider_error", error=str(exc),
        )
        return None, "provider_error"

    from app.services.llm_json import extract_json_object

    parsed = extract_json_object(raw)
    if not isinstance(parsed, dict) or not all(
        key in parsed for key in ("f1", "f2", "f4")
    ):
        logger.error(
            "portfolio_finding_llm_rejected",
            reason="schema", section=None, tokens=[],
        )
        return None, "schema"
    if not isinstance(parsed["f1"], list) or not all(
        isinstance(item, str) for item in parsed["f1"]
    ):
        logger.error(
            "portfolio_finding_llm_rejected",
            reason="schema", section=None, tokens=[],
        )
        return None, "schema"
    if not all(isinstance(parsed[key], str) for key in ("f2", "f4")):
        logger.error(
            "portfolio_finding_llm_rejected",
            reason="schema", section=None, tokens=[],
        )
        return None, "schema"

    # Substitute BEFORE anything else looks at the text: until every slot is
    # resolved the sections are not a report, and a stray digit at this point
    # is a rejection of the whole narration.
    raw_sections = {
        "f1": "\n".join(f"- {item}" for item in parsed["f1"]),
        "f2": parsed["f2"],
        "f4": parsed["f4"],
    }
    substituted: dict[str, str] = {}
    for section_id, text in raw_sections.items():
        rendered, failure = substitute_slots(text, slots)
        if failure is not None:
            logger.error(
                "portfolio_finding_llm_rejected",
                reason=failure.reason, section=section_id, tokens=failure.tokens,
            )
            return None, failure.reason
        substituted[section_id] = rendered

    sections = {
        "f1": substituted["f1"],
        "f2": substituted["f2"],
        # §F3's mandated content and §F5's rule sentences are deterministic on
        # both paths — F3 by CR038, F5 by the M1 fence above.
        "f3": deterministic["f3"],
        "f4": substituted["f4"],
        "f5": deterministic["f5"],
    }

    # Defence in depth. After substitution every figure came from a slot, so
    # these cannot fail on numbers the model chose — they catch a substitution
    # bug on our side, and the register/headline rules still apply to prose the
    # model did write.
    failure = validate_sections(sections, build_allowlist(context, rule_results))
    if failure is None:
        failure = register_check(sections)
    if failure is not None:
        logger.error(
            "portfolio_finding_llm_rejected",
            reason=failure.reason, section=failure.section, tokens=failure.tokens,
        )
        return None, failure.reason
    return sections, None


# ── 3.7 Orchestrator + persistence ──────────────────────────────────────────


def load_latest_finding(store, user_id: UUID, portfolio_id: UUID):
    """Newest prior Finding for this portfolio — delegates to the store.

    The read itself is `JournalStore.latest_portfolio_health_entry`, which the
    seam register pins as M08-owned precisely because it must bypass two filters
    `list_for_user` applies unconditionally: the Floor Pass 30-day retention
    window, which would let a rule silently restart `cleared` because the entry
    holding its state aged out of a plan's view, and the soft-delete filter,
    which would do the same the moment a user tidies their journal.

    This wrapper stays as the name M06's own call sites and tests use, but it
    owns no query: two implementations of "the newest Finding for this
    portfolio" is how the daily cap and the hysteresis memory drift apart.
    """
    return store.latest_portfolio_health_entry(user_id, portfolio_id)


async def generate_and_persist_finding(
    *,
    user_id: UUID,
    portfolio_id: UUID,
    as_of: str,
    metric_blocks: list[dict],
    store,
    evaluate,
    gateway=None,
) -> FindingResult:
    """Render, validate, persist. One journal read serves both the idempotency
    check and the hysteresis state — they are the same question about the same
    prior entry.

    `evaluate(prior_states) -> (rule_results, updated_states)` is REQUIRED and
    has no default: M06 renders rules, it does not own their inputs (mandate,
    holdings, ρ) — those live in M04's context and M07 binds M05's
    `evaluate_rules` to them. A default would have to be either a silent
    no-rules render or a runtime raise, and the first ships a Finding with §F5
    empty and no signal that anything was skipped.
    """
    context = build_stripped_context(metric_blocks, as_of=as_of)

    prior = load_latest_finding(store, user_id, portfolio_id)
    # The prior read includes soft-deleted entries, and the two things it feeds
    # treat that differently on purpose: the hysteresis state below is taken
    # unconditionally (a deleted Finding is still something that happened),
    # while replaying one to the caller would answer "regenerate" with a journal
    # id pointing at a row the user cannot open.
    if (
        prior is not None
        and prior.deleted_at is None
        and (prior.payload or {}).get("as_of") == as_of
    ):
        logger.info(
            "portfolio_finding_idempotent_hit",
            portfolio_id=str(portfolio_id), as_of=as_of,
        )
        return FindingResult(
            entry=prior, created=False, llm_used=False, llm_rejected_reason=None,
        )

    prior_states = ((prior.payload if prior else None) or {}).get("rule_states") or {}
    rule_results, updated_states = evaluate(prior_states)

    deterministic = render_deterministic_sections(context, rule_results)
    head = render_head_disclosure(context)

    sections = deterministic
    llm_used = False
    rejected_reason: str | None = None
    llm_sections, rejected_reason = await llm_render_sections(
        context, rule_results, gateway, user_id=user_id, deterministic=deterministic,
    )
    if llm_sections is not None:
        sections = llm_sections
        llm_used = True

    headlines = [
        line.lstrip("- ").strip()
        for line in sections["f1"].splitlines() if line.strip()
    ]
    # The entry's shape lives in M08's mapper, not in a dict literal here: it is
    # the artefact M07, M09 and CR137 all read, and it validates that no section
    # — the head disclosure included — reaches storage empty.
    from app.services.portfolio_health_journal import build_finding_entry

    draft = build_finding_entry(
        user_id=user_id,
        portfolio_id=portfolio_id,
        as_of=as_of,
        # The head disclosure lives INSIDE sections, per the seam register's
        # pinned payload shape — one place, not two. It is joined here rather
        # than upstream so the validator and register check keep seeing exactly
        # the five model-narratable sections.
        sections={"head": head, **sections},
        context=context,
        fired_rules=[
            {
                "rule_id": r["rule_id"],
                "slots": r.get("slots", {}),
                "based_on": r.get("based_on", []),
            }
            for r in rule_results if r.get("fired")
        ],
        rule_states=updated_states,
        engine_version=ENGINE_VERSION,
        summary=headlines[0] if headlines else None,
        llm_used=llm_used,
        llm_rejected_reason=rejected_reason,
    )

    # The write is the serialisation point, not the read above it: two
    # concurrent callers both pass the idempotency check, and only the unique
    # constraint can decide between them. Losing means someone else wrote the
    # Finding this call was about to write, so the winner's row is the correct
    # answer — measured before the constraint existed, five concurrent requests
    # produced five Findings against a daily cap of two, and five LLM bills.
    entry, created = store.append_unique(draft)
    if not created:
        logger.info(
            "portfolio_finding_lost_write_race",
            portfolio_id=str(portfolio_id), as_of=as_of,
        )
    return FindingResult(
        entry=entry, created=created, llm_used=llm_used,
        llm_rejected_reason=rejected_reason,
    )
