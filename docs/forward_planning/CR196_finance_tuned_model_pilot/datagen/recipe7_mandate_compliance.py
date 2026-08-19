#!/usr/bin/env python3
"""recipe7_mandate_compliance.py — CR196 §2 recipe 7: mandate-overlay compliance.

Modernizes the CR032/Silent_Scout salvaged `fundamentals_analyst.py` recipe's
"render a mandate overlay into the user turn" pattern for the Portfolio
Manager: every example pairs the REAL production mandate overlay (rendered by
the actual `app/agents/overlay_generator.py:generate_overlay()`) with a
proposed trade that either violates or satisfies ONE named mandate
constraint, and teaches the PM to name that constraint explicitly rather than
inventing or missing one (CR040 — no confident-false verdicts).

## Where the numbers/wording come from

- **Mandate schema fields** — imported directly from `backend/app/schemas/mandate.py`
  (pure pydantic, no DB — this import works standalone). Fields used, with the
  schema's own line numbers (read 2026-08-19, cite against that file if it moves):
    - `Mandate.risk_score` (mandate.py:146), `.risk_components` (147, itself
      `RiskComponents.concentration_tolerance` at mandate.py:94)
    - `Mandate.horizon` (141), `.path` (143), `.primary_goal` (140)
    - `Mandate.max_drawdown_pct` (149-151, `Literal[10, 20, 30, 50, 100]`)
    - `Mandate.sector_cap_pct` (162), `.single_name_cap_pct` (163)
    - `Mandate.post_loss_cooldown_hours` (181-183), `.max_open_positions` (187),
      `.max_trades_per_day` (191), `.max_trades_per_week` (192),
      `.max_open_risk_pct` (198)
    - `Mandate.compliance` (201) → `Compliance` (mandate.py:114-123): `.halal`,
      `.esg_lite`, `.no_tobacco_alcohol_gambling`, `.no_fossil_fuels`,
      `.long_only`, `.liquid_only`, `.ticker_blocklist`, `.ticker_allowlist`
    - `Mandate.learning_style` (204), `.plan` (216)
  NOT used: `target_outcome`, `risk_quotes`, `locale`/`timezone` beyond
  defaults, `credit_*`/`room_cooldown_until`/`resolved` (CLIENT_UNWRITABLE /
  server-stamped fields per mandate.py:57-63, out of scope for a user-set
  mandate overlay).

- **Overlay wording** — this file imports and calls the REAL
  `app.agents.overlay_generator.generate_overlay()`, not a hand-copy. Direct
  `from app.agents.overlay_generator import ...` would run
  `app/agents/__init__.py`, which imports `safety_floor.py`, which imports
  `app.services.sector_allocation`, which imports `app.db` (sqlalchemy,
  DB-coupled) — none of which this generator needs or has installed. So the
  `app.agents` PACKAGE is stubbed in `sys.modules` (an empty namespace with
  the right `__path__`) before `overlay_generator.py` is loaded by file path
  via `importlib`, which skips `app/agents/__init__.py` entirely.
  `overlay_generator.py` itself only imports `app.schemas` and
  `app.trading_math.*`, both pure — verified by this technique actually
  working (proof run below), not asserted.

- **Safety floor block** — same DB-dependency problem one file over
  (`safety_floor.py` imports `app.services.sector_allocation`), so instead of
  importing the module this file READS `SAFETY_FLOOR_BLOCK`'s literal text
  straight off `agents/safety_floor.py`'s own source via regex
  (`_read_safety_floor_template`) — byte-identical to production and
  re-extracted on every run, so it cannot silently drift the way a
  hand-copied string could. The `[[CAP]]` substitution mirrors
  `safety_floor.render_safety_floor_block` (safety_floor.py:152-155)
  exactly, using the same pure resolver
  (`app.trading_math.sizing.resolved_single_name_cap_pct`).

- **Ticker sector/screen facts (`TICKER_FACTS` below)** — a SYNTHETIC,
  hand-assigned table of 20 well-known names, built by this file for training
  variety. NOT the real AAOIFI/SPUS Sharia feed or AMI's real sourced
  sector/industry classification (`app.services.sharia_universe` /
  `classification_universe`) — those need network + a live snapshot this
  script deliberately has none of. Every ticker is cross-checked at import
  time against `train_universe.txt` / `eval_tickers.txt`
  (`common.load_eval_tickers()`) so this synthetic table can never
  accidentally leak an eval-only name into training data.

## Assistant format

Not the Room's JSON verdict contract (that's recipe8's subject — this is the
1-on-1 PM). The assistant uses the PM's own documented "## Output format"
block from `content/agents/portfolio_manager.md`
(`Verdict:` / `Reasoning:` / `Final trade:` / `Mandate compliance:` / `Tag:`),
reproduced verbatim in `_render_pm_block` below.

Usage: python3 recipe7_mandate_compliance.py --out out/recipe7.jsonl [--count 100]
Needs: pip install pydantic (the only backend dependency actually exercised —
see the import-stubbing note above).
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import types
from datetime import date, datetime, timezone
from typing import NamedTuple
from uuid import NAMESPACE_URL, uuid5

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from common import REPO, load_agent_prompt, load_eval_tickers, pick, write_jsonl  # noqa: E402

BACKEND = os.path.join(REPO, "backend")
sys.path.insert(0, BACKEND)

# ── Load the real overlay_generator.py without running app/agents/__init__.py
# (which pulls in DB deps this synthetic recipe has no use for — see the
# module docstring). ──────────────────────────────────────────────────────
_agents_pkg = types.ModuleType("app.agents")
_agents_pkg.__path__ = [os.path.join(BACKEND, "app", "agents")]
sys.modules.setdefault("app.agents", _agents_pkg)

_spec = importlib.util.spec_from_file_location(
    "app.agents.overlay_generator",
    os.path.join(BACKEND, "app", "agents", "overlay_generator.py"),
)
_overlay_mod = importlib.util.module_from_spec(_spec)
sys.modules["app.agents.overlay_generator"] = _overlay_mod
_spec.loader.exec_module(_overlay_mod)
generate_overlay = _overlay_mod.generate_overlay

from app.schemas import AgentId  # noqa: E402
from app.schemas.classification import (  # noqa: E402
    ClassificationKind,
    ClassificationStatus,
    ClassificationVerdict,
)
from app.schemas.mandate import (  # noqa: E402
    Compliance,
    Horizon,
    LearningStyle,
    Mandate,
)
from app.schemas.mandate import Path as MandatePath  # noqa: E402
from app.schemas.mandate import (  # noqa: E402
    Plan,
    PrimaryGoal,
    RiskComponents,
)
from app.schemas.sharia import ShariaStatus, ShariaVerdict  # noqa: E402
from app.trading_math.risk_limits import (  # noqa: E402
    position_risk_contribution,
    resolved_max_open_positions,
    resolved_max_open_risk_pct,
    resolved_max_trades_per_day,
    resolved_post_loss_cooldown_hours,
)
from app.trading_math.sizing import (  # noqa: E402
    resolved_sector_cap_pct,
    resolved_single_name_cap_pct,
)

PM_PROMPT_PATH = os.path.join(REPO, "content", "agents", "portfolio_manager.md")
SAFETY_FLOOR_PATH = os.path.join(BACKEND, "app", "agents", "safety_floor.py")

# common.load_agent_prompt() takes an optional path override (default is
# fundamentals_analyst.md, unused here) — reused rather than re-implemented.
SYSTEM_PROMPT = load_agent_prompt(PM_PROMPT_PATH)


def _read_safety_floor_template() -> str:
    """Byte-identical `SAFETY_FLOOR_BLOCK` text, read straight off
    safety_floor.py's own source (never imported — see module docstring)."""
    src = open(SAFETY_FLOOR_PATH).read()
    m = re.search(r'SAFETY_FLOOR_BLOCK = """(.*?)"""\n', src, re.S)
    if not m:
        raise SystemExit(
            "recipe7 is stale: SAFETY_FLOOR_BLOCK not found in safety_floor.py "
            "at the expected shape — update the regex in _read_safety_floor_template"
        )
    return m.group(1)


_SAFETY_FLOOR_TEMPLATE = _read_safety_floor_template()


def render_safety_floor_block(mandate: Mandate) -> str:
    """Mirrors safety_floor.py:152-155's `render_safety_floor_block` exactly:
    same `[[CAP]]` substitution, same resolver."""
    cap = resolved_single_name_cap_pct(mandate.risk_score, mandate.single_name_cap_pct)
    return _SAFETY_FLOOR_TEMPLATE.replace("[[CAP]]", f"{cap:.0f}")


# ── Synthetic ticker facts (ILLUSTRATIVE — see module docstring) ───────────
# 20 well-known S&P names. sin/fossil: True=EXCLUDED, False=PERMITTED,
# None=UNKNOWN (outside the synthetic classified universe). halal:
# True=PASS, False=SCREENED_OUT, None=UNKNOWN. MCD and PLD are deliberately
# left UNKNOWN on every screen, to exercise the "UNKNOWN is permitted, not a
# violation" lesson (mirrors ClassificationStatus.UNKNOWN / ShariaStatus.UNKNOWN,
# safety_floor.py's G3-resolved handling).
class Facts(NamedTuple):
    sector: str
    sin_excluded: bool | None
    fossil_excluded: bool | None
    halal_pass: bool | None


TICKER_FACTS: dict[str, Facts] = {
    "XOM":  Facts("Energy", False, True, False),
    "VLO":  Facts("Energy", False, True, False),
    "MO":   Facts("Consumer Staples", True, False, False),
    "PM":   Facts("Consumer Staples", True, False, False),
    "BAC":  Facts("Financials", False, False, False),
    "GS":   Facts("Financials", False, False, False),
    "CB":   Facts("Financials", False, False, False),
    "UNH":  Facts("Health Care", False, False, True),
    "MRK":  Facts("Health Care", False, False, True),
    "GILD": Facts("Health Care", False, False, True),
    "PG":   Facts("Consumer Staples", False, False, True),
    "MCD":  Facts("Consumer Discretionary", None, None, None),
    "SBUX": Facts("Consumer Discretionary", False, False, True),
    "WM":   Facts("Industrials", False, False, True),
    "NEM":  Facts("Materials", False, False, True),
    "NEE":  Facts("Utilities", False, False, True),
    "DUK":  Facts("Utilities", False, True, True),
    "PLD":  Facts("Real Estate", None, None, None),
    "DIS":  Facts("Communication Services", False, False, True),
    "INTC": Facts("Information Technology", False, False, True),
}


class _StaticClassificationUniverse:
    """Duck-typed stand-in for `app.services.classification_universe`'s real
    resolver — same `.resolve(ticker, kind) -> ClassificationVerdict`
    interface `overlay_generator._exclusion_narration` consumes, backed by
    `TICKER_FACTS` instead of a live sourced feed."""

    AS_OF = date(2026, 8, 19)

    def resolve(self, ticker: str, kind: ClassificationKind) -> ClassificationVerdict:
        t = ticker.upper()
        facts = TICKER_FACTS.get(t)
        if facts is None:
            flag = None
        elif kind is ClassificationKind.SIN:
            flag = facts.sin_excluded
        elif kind is ClassificationKind.FOSSIL_FUELS:
            flag = facts.fossil_excluded
        else:  # ESG_LITE — curated proxy = sin ∪ fossil, same rule as production
            flag = None if facts.sin_excluded is None else (facts.sin_excluded or facts.fossil_excluded)
        status = (
            ClassificationStatus.UNKNOWN if flag is None
            else ClassificationStatus.EXCLUDED if flag
            else ClassificationStatus.PERMITTED
        )
        return ClassificationVerdict(status=status, ticker=t, kind=kind, as_of=self.AS_OF)


class _StaticHalalUniverse:
    """Duck-typed stand-in for `sharia_universe.HalalUniverse` — same
    `.resolve(ticker) -> ShariaVerdict` interface plus the `.stale` attribute
    `overlay_generator._halal_narration` checks (always False here — this
    recipe never renders the UNAVAILABLE/paused state)."""

    stale = False
    STANDARD = "AAOIFI-style (synthetic, CR196 recipe7 illustrative table)"
    SOURCE = "recipe7's own static ticker table — NOT the real AAOIFI/SPUS feed"
    AS_OF = date(2026, 8, 19)

    def resolve(self, ticker: str) -> ShariaVerdict:
        t = ticker.upper()
        facts = TICKER_FACTS.get(t)
        halal = facts.halal_pass if facts else None
        status = (
            ShariaStatus.UNKNOWN if halal is None
            else ShariaStatus.PASS if halal
            else ShariaStatus.SCREENED_OUT
        )
        return ShariaVerdict(status=status, ticker=t, standard=self.STANDARD, source=self.SOURCE, as_of=self.AS_OF)


_CLASSIFICATION_UNIVERSE = _StaticClassificationUniverse()
_HALAL_UNIVERSE = _StaticHalalUniverse()


def _tickers_by_status(kind: ClassificationKind) -> tuple[list[str], list[str], list[str]]:
    excluded, permitted, unknown = [], [], []
    for t, facts in TICKER_FACTS.items():
        v = _CLASSIFICATION_UNIVERSE.resolve(t, kind)
        (unknown if v.status is ClassificationStatus.UNKNOWN
         else excluded if v.status is ClassificationStatus.EXCLUDED
         else permitted).append(t)
    return excluded, permitted, unknown


def _tickers_by_halal_status() -> tuple[list[str], list[str], list[str]]:
    passed, screened_out, unknown = [], [], []
    for t in TICKER_FACTS:
        v = _HALAL_UNIVERSE.resolve(t)
        (unknown if v.status is ShariaStatus.UNKNOWN
         else screened_out if v.status is ShariaStatus.SCREENED_OUT
         else passed).append(t)
    return screened_out, passed, unknown


def _synthetic_price(ticker: str) -> float:
    """Deterministic, illustrative-only per-share price — no live quote."""
    h = int(hashlib.sha256(("price|" + ticker).encode()).hexdigest(), 16)
    return round(20 + (h % 38000) / 100, 2)


def _deterministic_uuid(mandate_id: str):
    return uuid5(NAMESPACE_URL, f"ami-trade:cr196:recipe7:{mandate_id}")


# ── Seed mandates (11 — spans the settable constraint space) ───────────────
_NOW = datetime(2026, 8, 19, tzinfo=timezone.utc)


def _base_mandate(mandate_id: str, **overrides) -> Mandate:
    defaults = dict(
        user_id=_deterministic_uuid(mandate_id),
        display_name="Training User",
        locale="en",
        timezone="UTC",
        primary_goal=PrimaryGoal.LONG_TERM_WEALTH,
        horizon=Horizon.LONG,
        target_outcome=None,
        path=MandatePath.LONG_HORIZON,
        risk_score=3,
        risk_components=RiskComponents(drawdown_response=3, regret_asymmetry=0, concentration_tolerance=3),
        max_drawdown_pct=20,
        compliance=Compliance(),
        learning_style=LearningStyle.QUICK,
        plan=Plan.TRADER,
        created_at=_NOW,
        updated_at=_NOW,
    )
    defaults.update(overrides)
    return Mandate(**defaults)


def _seed_mandates() -> dict[str, Mandate]:
    return {
        "conservative_default": _base_mandate(
            "conservative_default", risk_score=2, max_drawdown_pct=10,
            risk_components=RiskComponents(drawdown_response=2, regret_asymmetry=-1, concentration_tolerance=2),
        ),
        "halal_strict": _base_mandate(
            "halal_strict", risk_score=3,
            compliance=Compliance(halal=True, long_only=True, liquid_only=True, no_tobacco_alcohol_gambling=True),
            learning_style=LearningStyle.STORY, primary_goal=PrimaryGoal.RETIREMENT, horizon=Horizon.VERY_LONG,
        ),
        "esg_fossil_free": _base_mandate(
            "esg_fossil_free", risk_score=3,
            compliance=Compliance(esg_lite=True, no_fossil_fuels=True, long_only=True),
        ),
        "aggressive_shorts_active": _base_mandate(
            "aggressive_shorts_active", risk_score=5, horizon=Horizon.SHORT, path=MandatePath.ACTIVE,
            primary_goal=PrimaryGoal.LEARNING_TO_TRADE, max_drawdown_pct=50,
            risk_components=RiskComponents(drawdown_response=5, regret_asymmetry=1, concentration_tolerance=5),
            compliance=Compliance(long_only=False, liquid_only=True),
        ),
        "sin_free_income": _base_mandate(
            "sin_free_income", risk_score=2, primary_goal=PrimaryGoal.INCOME_NOW, max_drawdown_pct=10,
            compliance=Compliance(no_tobacco_alcohol_gambling=True, long_only=True),
            risk_components=RiskComponents(drawdown_response=2, regret_asymmetry=-1, concentration_tolerance=2),
        ),
        "blocklist_investor": _base_mandate(
            "blocklist_investor", risk_score=3,
            compliance=Compliance(ticker_blocklist=["MCD", "INTC"], long_only=True),
        ),
        "allowlist_restricted": _base_mandate(
            "allowlist_restricted", risk_score=3,
            compliance=Compliance(ticker_allowlist=["UNH", "MRK", "GILD", "PG", "WM"], long_only=True),
        ),
        "tight_caps_daytrader": _base_mandate(
            "tight_caps_daytrader", risk_score=4, horizon=Horizon.SHORT, path=MandatePath.ACTIVE,
            max_drawdown_pct=30, single_name_cap_pct=2.0, max_open_positions=5,
            max_trades_per_day=3, post_loss_cooldown_hours=48,
            risk_components=RiskComponents(drawdown_response=4, regret_asymmetry=1, concentration_tolerance=3),
        ),
        "loose_caps_veteran": _base_mandate(
            "loose_caps_veteran", risk_score=4, max_drawdown_pct=50,
            single_name_cap_pct=12.0, max_open_risk_pct=15.0, max_trades_per_week=40, sector_cap_pct=55.0,
            risk_components=RiskComponents(drawdown_response=3, regret_asymmetry=0, concentration_tolerance=5),
        ),
        "halal_fossil_tight_dd": _base_mandate(
            "halal_fossil_tight_dd", risk_score=2, max_drawdown_pct=10,
            primary_goal=PrimaryGoal.RETIREMENT, horizon=Horizon.VERY_LONG,
            compliance=Compliance(halal=True, no_fossil_fuels=True, long_only=True),
            risk_components=RiskComponents(drawdown_response=2, regret_asymmetry=-1, concentration_tolerance=1),
        ),
        "halal_shorts_permitted": _base_mandate(
            "halal_shorts_permitted", risk_score=4, horizon=Horizon.SHORT, path=MandatePath.ACTIVE,
            primary_goal=PrimaryGoal.LEARNING_TO_TRADE, max_drawdown_pct=50,
            compliance=Compliance(halal=True, long_only=False, liquid_only=True),
            risk_components=RiskComponents(drawdown_response=4, regret_asymmetry=1, concentration_tolerance=4),
        ),
    }


# ── PM 1-on-1 output block (content/agents/portfolio_manager.md's own
# "## Output format" section, reproduced verbatim in shape) ────────────────
_TAG_LINE = "Tag:       Worked example — classroom simulation, not financial advice."


def _render_pm_block(action: str, reasoning: str, *, compliance_detail: str | None = None,
                      trade: str | None = None) -> str:
    lines = [f"Verdict:   {action}", f"Reasoning: {reasoning}"]
    if action == "APPROVE":
        lines.append("Final trade (if approved/modified):")
        lines.append(f"  {trade}")
        lines.append("Mandate compliance: PASS")
    else:
        lines.append(f"Mandate compliance: FAIL — {compliance_detail}")
    lines.append(_TAG_LINE)
    return "\n".join(lines)


def _build_example(mid: str, m: Mandate, constraint: str, case: str, ticker: str, *,
                    trade_line: str, portfolio_context: list[str] | None,
                    reasoning: str, compliance_detail: str | None = None,
                    size_pct: float | None = None,
                    entry: float | None = None, stop: float | None = None) -> dict:
    overlay = generate_overlay(
        AgentId.PORTFOLIO_MANAGER, m,
        halal_universe=_HALAL_UNIVERSE, ticker=ticker,
        classification_universe=_CLASSIFICATION_UNIVERSE, locale_allowed_universe=None,
    )
    floor = render_safety_floor_block(m)
    user_parts = [overlay, floor]
    if portfolio_context:
        user_parts.append("Portfolio context:\n" + "\n".join(f"  - {line}" for line in portfolio_context))
    user_parts.append(f"Proposed trade: {trade_line}\n\nIssue your verdict in the output format your prompt specifies.")
    user = "\n\n".join(user_parts)

    if case == "violation":
        assistant = _render_pm_block("PASS", reasoning, compliance_detail=compliance_detail)
    else:
        # `entry`/`stop` default to the standard synthetic derivation (matching
        # room_runner.py:1500-1501's PM-verdict fallback ratios, entry×0.94 /
        # entry×1.13) UNLESS the caller already committed to a specific stop in
        # `trade_line` (the open-risk test prices its own 10%-below-entry stop
        # to compute a risk contribution) — the Final trade line must never
        # restate a DIFFERENT stop than the one the proposal/reasoning used.
        entry = _synthetic_price(ticker) if entry is None else entry
        stop = round(entry * 0.94, 2) if stop is None else stop
        target = round(entry * 1.13, 2)
        trade = f"{ticker}, BUY, {size_pct}% of portfolio, Entry ${entry}, Target ${target}, Stop ${stop}, Horizon 60d"
        assistant = _render_pm_block("APPROVE", reasoning, trade=trade)

    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ],
        "_meta": {
            "recipe": "recipe7_mandate_compliance", "mandate_id": mid,
            "constraint_tested": constraint, "case": case, "ticker": ticker,
        },
    }


def _safe_size(m: Mandate) -> float:
    """A position size that never breaches the single-name cap on its own —
    used as the default trade size for every constraint test EXCEPT the ones
    that deliberately vary size/weight to probe that exact cap, so a
    'compliant' example is never accidentally also a single-name-cap
    violation for an unrelated reason."""
    cap = resolved_single_name_cap_pct(m.risk_score, m.single_name_cap_pct)
    return round(max(0.1, cap * 0.5), 2)


# ── Constraint test generators ──────────────────────────────────────────
_SECTOR_FLAGS = [
    ("no_tobacco_alcohol_gambling", ClassificationKind.SIN, "Exclude tobacco, alcohol, gambling"),
    ("no_fossil_fuels", ClassificationKind.FOSSIL_FUELS, "Exclude fossil fuels"),
    ("esg_lite", ClassificationKind.ESG_LITE, "ESG-lite screen"),
]


def _test_sector_exclusion(mid: str, m: Mandate):
    active = [(f, k, lbl) for f, k, lbl in _SECTOR_FLAGS if getattr(m.compliance, f)]
    if not active:
        return None
    flag_name, kind, label = pick(active, mid, "sector_exclusion_flag")
    excluded, permitted, unknown = _tickers_by_status(kind)
    case = pick(["violation", "compliant"], mid, "sector_exclusion", flag_name)
    size = _safe_size(m)
    if case == "violation":
        ticker = pick(excluded, mid, "sector_exclusion_ticker")
        reasoning = f"{ticker} fails the '{label}' screen your mandate requires."
        detail = f"{label} — {ticker} is classified as excluded under this screen; see the compliance constraints above."
        return _build_example(mid, m, "sector_exclusion", "violation", ticker,
                               trade_line=f"BUY {ticker} — {size}% of portfolio.",
                               portfolio_context=None, reasoning=reasoning, compliance_detail=detail)
    kind_case = pick(["permitted", "unknown"], mid, "sector_exclusion_compliant_kind", flag_name)
    pool = permitted if kind_case == "permitted" else unknown
    ticker = pick(pool, mid, "sector_exclusion_ticker_compliant")
    if kind_case == "unknown":
        reasoning = (f"{ticker} sits outside AMI's classified universe for the '{label}' screen — "
                     "that's not a ruling either way, so the trade is permitted.")
    else:
        reasoning = f"{ticker} clears the '{label}' screen your mandate requires."
    return _build_example(mid, m, "sector_exclusion", "compliant", ticker,
                           trade_line=f"BUY {ticker} — {size}% of portfolio.",
                           portfolio_context=None, reasoning=reasoning, size_pct=size)


def _test_halal(mid: str, m: Mandate):
    if not m.compliance.halal:
        return None
    screened_out, passed, unknown = _tickers_by_halal_status()
    case = pick(["violation", "compliant"], mid, "halal")
    size = _safe_size(m)
    if case == "violation":
        ticker = pick(screened_out, mid, "halal_ticker")
        reasoning = f"{ticker} is screened out under the halal standard your mandate requires."
        detail = f"halal — {ticker} does not pass the sourced Sharia screen named above."
        return _build_example(mid, m, "halal", "violation", ticker,
                               trade_line=f"BUY {ticker} — {size}% of portfolio.",
                               portfolio_context=None, reasoning=reasoning, compliance_detail=detail)
    kind_case = pick(["pass", "unknown"], mid, "halal_compliant_kind")
    pool = passed if kind_case == "pass" else unknown
    ticker = pick(pool, mid, "halal_ticker_compliant")
    if kind_case == "unknown":
        reasoning = (f"{ticker} isn't in the parent index the halal screen uses — that's not a ruling "
                     "either way, so the trade is permitted.")
    else:
        reasoning = f"{ticker} passes your halal screen."
    return _build_example(mid, m, "halal", "compliant", ticker,
                           trade_line=f"BUY {ticker} — {size}% of portfolio.",
                           portfolio_context=None, reasoning=reasoning, size_pct=size)


def _test_halal_short_advisory(mid: str, m: Mandate):
    """CR171 §6 — a halal + non-long-only mandate: shorting is ADVISORY, not
    blocking. This is the one case where the halal flag never produces a
    violation label, and the recipe must not invent one."""
    if not (m.compliance.halal and not m.compliance.long_only):
        return None
    ticker = pick(list(TICKER_FACTS), mid, "halal_short_advisory_ticker")
    size = _safe_size(m)
    reasoning = (f"Shorting {ticker} isn't blocked by your halal flag — AMI advises that short-selling is "
                 "widely considered impermissible under Sharia (it sells what you don't own, and the "
                 "borrow carries an interest-like cost), but does not stop the trade. The call is yours.")
    return _build_example(mid, m, "halal_short_advisory", "compliant", ticker,
                           trade_line=f"SELL {ticker} — {size}% of portfolio (none currently held; opens a short).",
                           portfolio_context=None, reasoning=reasoning, size_pct=size)


def _test_blocklist(mid: str, m: Mandate):
    block = m.compliance.ticker_blocklist
    if not block:
        return None
    case = pick(["violation", "compliant"], mid, "blocklist")
    size = _safe_size(m)
    if case == "violation":
        ticker = pick(block, mid, "blocklist_ticker")
        reasoning = f"{ticker} is on your ticker blocklist."
        detail = f"ticker {ticker} is on the mandate's blocklist."
        return _build_example(mid, m, "ticker_blocklist", "violation", ticker,
                               trade_line=f"BUY {ticker} — {size}% of portfolio.",
                               portfolio_context=None, reasoning=reasoning, compliance_detail=detail)
    others = [t for t in TICKER_FACTS if t not in block]
    ticker = pick(others, mid, "blocklist_ticker_compliant")
    reasoning = f"{ticker} isn't on your blocklist."
    return _build_example(mid, m, "ticker_blocklist", "compliant", ticker,
                           trade_line=f"BUY {ticker} — {size}% of portfolio.",
                           portfolio_context=None, reasoning=reasoning, size_pct=size)


def _test_allowlist(mid: str, m: Mandate):
    allow = m.compliance.ticker_allowlist
    if not allow:
        return None
    case = pick(["violation", "compliant"], mid, "allowlist")
    size = _safe_size(m)
    if case == "violation":
        others = [t for t in TICKER_FACTS if t not in allow]
        ticker = pick(others, mid, "allowlist_ticker_violation")
        reasoning = f"{ticker} isn't on your ticker allowlist — only {', '.join(allow)} are tradable."
        detail = f"ticker {ticker} is not in the mandate's allowlist ({', '.join(allow)})."
        return _build_example(mid, m, "ticker_allowlist", "violation", ticker,
                               trade_line=f"BUY {ticker} — {size}% of portfolio.",
                               portfolio_context=None, reasoning=reasoning, compliance_detail=detail)
    ticker = pick(allow, mid, "allowlist_ticker_compliant")
    reasoning = f"{ticker} is on your allowlist."
    return _build_example(mid, m, "ticker_allowlist", "compliant", ticker,
                           trade_line=f"BUY {ticker} — {size}% of portfolio.",
                           portfolio_context=None, reasoning=reasoning, size_pct=size)


def _test_long_only(mid: str, m: Mandate):
    if not m.compliance.long_only:
        return None
    case = pick(["violation", "compliant"], mid, "long_only")
    ticker = pick(list(TICKER_FACTS), mid, "long_only_ticker")
    size = _safe_size(m)
    if case == "violation":
        reasoning = f"Your mandate is long-only, and selling {ticker} with none held would open a short."
        detail = f"long_only — selling {ticker} with no existing position would open a short."
        return _build_example(mid, m, "long_only", "violation", ticker,
                               trade_line=f"SELL {ticker} — {size}% of portfolio (none currently held; opens a short).",
                               portfolio_context=None, reasoning=reasoning, compliance_detail=detail)
    reasoning = "Standard long BUY — no short exposure, consistent with your long-only mandate."
    return _build_example(mid, m, "long_only", "compliant", ticker,
                           trade_line=f"BUY {ticker} — {size}% of portfolio.",
                           portfolio_context=None, reasoning=reasoning, size_pct=size)


def _test_single_name_cap(mid: str, m: Mandate):
    cap = resolved_single_name_cap_pct(m.risk_score, m.single_name_cap_pct)
    case = pick(["violation", "compliant"], mid, "single_name_cap")
    ticker = pick(list(TICKER_FACTS), mid, "single_name_cap_ticker")
    if case == "violation":
        size = round(min(cap * 1.8, 95.0), 1)
        reasoning = f"{ticker} at {size}% breaches your single-name cap of {cap}%."
        detail = f"position size {size}% exceeds single-name cap {cap}%."
        return _build_example(mid, m, "single_name_cap_pct", "violation", ticker,
                               trade_line=f"BUY {ticker} — {size}% of portfolio.",
                               portfolio_context=None, reasoning=reasoning, compliance_detail=detail)
    size = _safe_size(m)
    reasoning = f"{ticker} at {size}% sits comfortably under your {cap}% single-name cap."
    return _build_example(mid, m, "single_name_cap_pct", "compliant", ticker,
                           trade_line=f"BUY {ticker} — {size}% of portfolio.",
                           portfolio_context=None, reasoning=reasoning, size_pct=size)


def _test_sector_concentration(mid: str, m: Mandate):
    cap_pct = resolved_sector_cap_pct(m.risk_components.concentration_tolerance, m.sector_cap_pct)
    sectors: dict[str, list[str]] = {}
    for t, facts in TICKER_FACTS.items():
        sectors.setdefault(facts.sector, []).append(t)
    multi = {s: ts for s, ts in sectors.items() if len(ts) >= 2}
    sector = pick(sorted(multi), mid, "sector_concentration_sector")
    existing_ticker, new_ticker = sorted(multi[sector])[:2]
    new_size = _safe_size(m)
    case = pick(["violation", "compliant"], mid, "sector_concentration")
    if case == "violation":
        existing_weight = round(max(0.0, cap_pct - new_size * 0.5), 1)
        reasoning = (f"Adding {new_ticker} would push {sector} sector weight to "
                     f"{round(existing_weight + new_size, 1)}%, over the {cap_pct}% sector-concentration cap.")
        detail = (f"sector concentration — {sector} would reach {round(existing_weight + new_size, 1)}% "
                  f"of portfolio, over the {cap_pct}% cap.")
        ctx = [f"Existing {sector} sector weight: {existing_weight}% (via {existing_ticker}); sector cap: {cap_pct}%."]
        return _build_example(mid, m, "sector_cap_pct", "violation", new_ticker,
                               trade_line=f"BUY {new_ticker} — {new_size}% of portfolio.",
                               portfolio_context=ctx, reasoning=reasoning, compliance_detail=detail)
    existing_weight = round(max(0.0, cap_pct - new_size * 4), 1)
    reasoning = (f"Adding {new_ticker} brings {sector} weight to {round(existing_weight + new_size, 1)}%, "
                 f"still under the {cap_pct}% sector cap.")
    ctx = [f"Existing {sector} sector weight: {existing_weight}% (via {existing_ticker}); sector cap: {cap_pct}%."]
    return _build_example(mid, m, "sector_cap_pct", "compliant", new_ticker,
                           trade_line=f"BUY {new_ticker} — {new_size}% of portfolio.",
                           portfolio_context=ctx, reasoning=reasoning, size_pct=new_size)


def _test_drawdown(mid: str, m: Mandate):
    cap = float(m.max_drawdown_pct)
    case = pick(["violation", "compliant"], mid, "drawdown")
    ticker = pick(list(TICKER_FACTS), mid, "drawdown_ticker")
    size = _safe_size(m)
    if case == "violation":
        current = cap
        ctx = [f"Current portfolio drawdown: {current}% (mandate cap: {cap}%)."]
        reasoning = f"Current drawdown {current}% is already at your {cap}% cap — no new BUY until it recovers."
        detail = f"current drawdown {current}% already at/exceeds cap {cap}%."
        return _build_example(mid, m, "max_drawdown_pct", "violation", ticker,
                               trade_line=f"BUY {ticker} — {size}% of portfolio.",
                               portfolio_context=ctx, reasoning=reasoning, compliance_detail=detail)
    current = round(cap * 0.3, 1)
    ctx = [f"Current portfolio drawdown: {current}% (mandate cap: {cap}%)."]
    reasoning = f"Current drawdown {current}% leaves clear room under the {cap}% cap."
    return _build_example(mid, m, "max_drawdown_pct", "compliant", ticker,
                           trade_line=f"BUY {ticker} — {size}% of portfolio.",
                           portfolio_context=ctx, reasoning=reasoning, size_pct=size)


def _test_max_open_positions(mid: str, m: Mandate):
    cap = resolved_max_open_positions(m.risk_score, m.max_open_positions)
    case = pick(["violation", "compliant"], mid, "max_open_positions")
    ticker = pick(list(TICKER_FACTS), mid, "max_open_positions_ticker")
    size = _safe_size(m)
    if case == "violation":
        held = cap
        ctx = [f"Currently holding {held} distinct tickers (cap: {cap}); {ticker} is not one of them."]
        reasoning = f"{held} of {cap} position slots are already used — {ticker} would open a new one over the cap."
        detail = f"opening {ticker} would exceed the max open positions cap ({cap}) — {held} already held."
        return _build_example(mid, m, "max_open_positions", "violation", ticker,
                               trade_line=f"BUY {ticker} — {size}% of portfolio (new position).",
                               portfolio_context=ctx, reasoning=reasoning, compliance_detail=detail)
    held = max(0, cap - 3)
    ctx = [f"Currently holding {held} distinct tickers (cap: {cap}); {ticker} is not one of them."]
    reasoning = f"{held} of {cap} position slots used — {ticker} fits under the cap."
    return _build_example(mid, m, "max_open_positions", "compliant", ticker,
                           trade_line=f"BUY {ticker} — {size}% of portfolio (new position).",
                           portfolio_context=ctx, reasoning=reasoning, size_pct=size)


def _test_trades_per_day(mid: str, m: Mandate):
    cap = resolved_max_trades_per_day(m.risk_score, m.max_trades_per_day)
    case = pick(["violation", "compliant"], mid, "trades_per_day")
    ticker = pick(list(TICKER_FACTS), mid, "trades_per_day_ticker")
    size = _safe_size(m)
    if case == "violation":
        today = cap
        ctx = [f"Trades submitted today (UTC calendar day): {today} (cap: {cap}/day)."]
        reasoning = f"{today} of {cap} trades today are already used — the daily cap is reached."
        detail = f"max trades per day ({cap}) already reached ({today} today, UTC calendar day)."
        return _build_example(mid, m, "max_trades_per_day", "violation", ticker,
                               trade_line=f"BUY {ticker} — {size}% of portfolio.",
                               portfolio_context=ctx, reasoning=reasoning, compliance_detail=detail)
    today = max(0, cap - 2)
    ctx = [f"Trades submitted today (UTC calendar day): {today} (cap: {cap}/day)."]
    reasoning = f"{today} of {cap} trades used today — this one fits under the daily cap."
    return _build_example(mid, m, "max_trades_per_day", "compliant", ticker,
                           trade_line=f"BUY {ticker} — {size}% of portfolio.",
                           portfolio_context=ctx, reasoning=reasoning, size_pct=size)


def _test_post_loss_cooldown(mid: str, m: Mandate):
    hours = resolved_post_loss_cooldown_hours(m.risk_score, m.post_loss_cooldown_hours)
    if hours <= 0:
        return None  # an explicit 0h override is a no-op, not a testable block (DEF196)
    case = pick(["violation", "compliant"], mid, "post_loss_cooldown")
    ticker = pick(list(TICKER_FACTS), mid, "post_loss_cooldown_ticker")
    size = _safe_size(m)
    if case == "violation":
        since = round(hours * 0.4, 1)
        ctx = [f"Last stop-out closed {since}h ago (cooldown: {hours}h after a stop-out)."]
        reasoning = f"Only {since}h have passed since the last stop-out; the {hours}h cooldown is still active."
        detail = f"post-loss cooldown active — {since}h elapsed, {hours}h required."
        return _build_example(mid, m, "post_loss_cooldown_hours", "violation", ticker,
                               trade_line=f"BUY {ticker} — {size}% of portfolio.",
                               portfolio_context=ctx, reasoning=reasoning, compliance_detail=detail)
    since = round(hours * 2.5 + 1, 1)
    ctx = [f"Last stop-out closed {since}h ago (cooldown: {hours}h after a stop-out)."]
    reasoning = f"{since}h have passed since the last stop-out, clear of the {hours}h cooldown."
    return _build_example(mid, m, "post_loss_cooldown_hours", "compliant", ticker,
                           trade_line=f"BUY {ticker} — {size}% of portfolio.",
                           portfolio_context=ctx, reasoning=reasoning, size_pct=size)


def _test_open_risk(mid: str, m: Mandate):
    cap = resolved_max_open_risk_pct(m.risk_score, m.max_drawdown_pct, m.max_open_risk_pct)
    case = pick(["violation", "compliant"], mid, "open_risk")
    ticker = pick(list(TICKER_FACTS), mid, "open_risk_ticker")
    size = _safe_size(m)
    entry = _synthetic_price(ticker)
    stop = round(entry * 0.90, 2)  # a fixed 10% stop for this constraint's own arithmetic
    contribution = round(position_risk_contribution(size, entry, stop), 3)
    if case == "violation":
        existing = round(max(0.0, cap - contribution + 0.05), 3)
        total = round(existing + contribution, 3)
        ctx = [f"Existing total open risk: {existing}% (cap: {cap}%). This trade at {size}% size with a "
               f"10%-below-entry stop contributes {contribution}pt."]
        reasoning = f"Existing open risk {existing}% plus this trade's {contribution}pt contribution reaches {total}%, over the {cap}% cap."
        detail = f"total open risk {total}% exceeds cap {cap}%."
        return _build_example(mid, m, "max_open_risk_pct", "violation", ticker,
                               trade_line=f"BUY {ticker} — {size}% of portfolio, stop ${stop} (10% below entry ${entry}).",
                               portfolio_context=ctx, reasoning=reasoning, compliance_detail=detail)
    existing = round(cap * 0.2, 3)
    total = round(existing + contribution, 3)
    ctx = [f"Existing total open risk: {existing}% (cap: {cap}%). This trade at {size}% size with a "
           f"10%-below-entry stop contributes {contribution}pt."]
    reasoning = f"Existing open risk {existing}% plus this trade's {contribution}pt contribution stays at {total}%, under the {cap}% cap."
    return _build_example(mid, m, "max_open_risk_pct", "compliant", ticker,
                           trade_line=f"BUY {ticker} — {size}% of portfolio, stop ${stop} (10% below entry ${entry}).",
                           portfolio_context=ctx, reasoning=reasoning, size_pct=size,
                           entry=entry, stop=stop)


_CONSTRAINT_TESTS = [
    _test_sector_exclusion,
    _test_halal,
    _test_halal_short_advisory,
    _test_blocklist,
    _test_allowlist,
    _test_long_only,
    _test_single_name_cap,
    _test_sector_concentration,
    _test_drawdown,
    _test_max_open_positions,
    _test_trades_per_day,
    _test_post_loss_cooldown,
    _test_open_risk,
]


def build_all() -> list[dict]:
    mandates = _seed_mandates()
    buckets: dict[str, list[dict]] = {}
    for mid, m in mandates.items():
        for test in _CONSTRAINT_TESTS:
            ex = test(mid, m)
            if ex is not None:
                buckets.setdefault(ex["_meta"]["constraint_tested"], []).append(ex)
    return buckets


def _round_robin(buckets: dict[str, list[dict]], count: int) -> list[dict]:
    out: list[dict] = []
    keys = sorted(buckets)
    idx = {k: 0 for k in keys}
    while len(out) < count and any(idx[k] < len(buckets[k]) for k in keys):
        for k in keys:
            if idx[k] < len(buckets[k]):
                out.append(buckets[k][idx[k]])
                idx[k] += 1
                if len(out) >= count:
                    break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "out", "recipe7.jsonl"))
    ap.add_argument("--count", type=int, default=100)
    args = ap.parse_args()

    bad = set(TICKER_FACTS) & load_eval_tickers()
    if bad:
        raise SystemExit(f"DECONTAMINATION VIOLATION: {sorted(bad)} in recipe7's static ticker table")

    buckets = build_all()
    total_available = sum(len(v) for v in buckets.values())
    rows = _round_robin(buckets, args.count) if args.count else [e for v in buckets.values() for e in v]

    n = write_jsonl(args.out, rows)
    by_case: dict[str, int] = {}
    by_constraint: dict[str, int] = {}
    for e in rows:
        by_case[e["_meta"]["case"]] = by_case.get(e["_meta"]["case"], 0) + 1
        by_constraint[e["_meta"]["constraint_tested"]] = by_constraint.get(e["_meta"]["constraint_tested"], 0) + 1

    print(f"wrote {n} examples → {args.out} (of {total_available} available)")
    print(f"by case: {json.dumps(by_case, indent=2)}")
    print(f"by constraint: {json.dumps(by_constraint, indent=2)}")


if __name__ == "__main__":
    main()
