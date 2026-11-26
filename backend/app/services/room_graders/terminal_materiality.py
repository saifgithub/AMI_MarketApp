"""CR267: a deterministic materiality check on the `debt_default` terminal vulnerability (`term=v2`).

Why it exists. Ling's v2 terminal answer is a JSON reply whose fields code validates, but the
validation proves only "quoted from the Room", not "is terminal". On the blind-labelled 30-Room set
v2 had 8 false yes and 0 false no, and `debt_default` was 18 of 27 Bursa and 66 of 79 US v2 yes,
mostly an ordinary maturity schedule (Boeing: $8.35bn due within a year against $20.7bn of cash).
Whether a maturity wall is terminal is arithmetic, so code does it: principal due inside the
trade's horizon against the cash the company holds plus the free cash flow it earns over that
horizon.

The rule (only when the winning terminal answer is "yes" with `terminal_category == "debt_default"`):

    horizon        = the larger of YOUR debt-maturity horizon (mandate, months) and the
                     Execution Desk's own stated horizon (days)           [CR285]
    due_in_horizon = sum of the ladder buckets that START inside the horizon
    available      = cash + TTM free cash flow x (horizon_days / 365)
    coverage       = available / due_in_horizon
    the yes STANDS only if coverage < YOUR minimum coverage (mandate, x)  [CR285]

CR285: before it, the horizon was the runner's fixed 6 weeks (the desk's was never read, DEF551)
and the minimum a fixed 1.0x. Both are now the user's numbers: the mandate carries them
(`debt_horizon_months`, `min_debt_coverage`; defaults 6/18/24/24 months by mandate horizon and
1.5x/1.25x/1.0x by risk score), and the record and the reason text name them ("due within your
24-month horizon ... your minimum is 1.5x"). An input that omits them (an offline caller) is
read as before: the horizon it gives and a 1.0x minimum, recorded as such.

Ladder buckets (the EDGAR long-term-debt principal ladder, `debt_maturity.py`) are mapped by whole
years from the trade date: "Within 1 year" starts at day 0, "Year k" at day (k-1) x 365. A bucket
counts when its start day is strictly before `horizon_days`, so a horizon of 365 days or less counts
only the first bucket, and 366 days adds Year 2. The whole first bucket is counted even though only
part of a year falls inside the horizon (the conservative reading: it keeps the yes alive).

Cash is the profile's gross cash; when that is absent, total debt less net debt (total debt + net
cash); when neither, zero and `cash_source = "unknown"`. FCF absent counts as zero, recorded as
`fcf_source = "unknown"`. Negative FCF reduces what is available. The ladder excludes short-term
borrowings; their size is recorded on the check (`short_term_borrowings_not_counted`), not counted.

No ladder at all (every Bursa Room today: the schedule is dark for `.KL`) means the yes cannot be
evidenced and becomes "no". A yes whose horizon is unknown stands, recorded as skipped. Every
outcome is written to `terminal_check` on the answer, and a refused yes is written to
`terminal_rejected`. Other categories are untouched. The tag goes into the Ling grader version
(bound to `term=v2`, no separate switch: the check reads the category only v2 produces).
"""

from __future__ import annotations

import math
import re
from dataclasses import replace
from typing import Any, Mapping

from app.services.room_grader_contract import Answer, QuestionAnswer, QuestionId
from app.trading_math.risk_limits import debt_horizon_days

# The minimum an input that carries none is read with (an offline caller). The live Room always
# passes the user's own.
DEBT_DEFAULT_MIN_COVERAGE = 1.0
CHECKED_CATEGORY = "debt_default"
DAYS_PER_YEAR = 365
CHECK_REVISION = "d2"
# `d2` = horizon and minimum are the mandate's (CR285). `d1c1.00` was the fixed 6-week, 1.0x check;
# a Room graded under it is keyed apart from one graded under the user's numbers.
CHECK_TAG = f"termchk={CHECK_REVISION}"

_YEAR_N = re.compile(r"^year\s*(\d+)$", re.IGNORECASE)
_FIRST = re.compile(r"^(within\s*(1|one)\s*year|next\s*(12|twelve)\s*months)$", re.IGNORECASE)


def bucket_start_day(label: str) -> int | None:
    """The day, from the trade date, on which a ladder bucket begins; None for a label the
    mapping does not know (the caller counts it as due and records it)."""
    text = (label or "").strip()
    if _FIRST.match(text):
        return 0
    m = _YEAR_N.match(text)
    if m and int(m.group(1)) >= 1:
        return (int(m.group(1)) - 1) * DAYS_PER_YEAR
    return None


def _num(v: Any) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return None
    return float(v)


def _fmt(m: float) -> str:
    return f"${m:,.0f}M"


def _times(value: float, against: float) -> str:
    """Two decimals; four when the two figures in one sentence would print the same but differ."""
    text = f"{value:.2f}"
    return f"{value:.4f}" if value != against and text == f"{against:.2f}" else text


def _horizon_phrase(check: Mapping[str, Any]) -> str:
    """How the reason text names the horizon it counted: the user's own when theirs governed, the
    desk's (and that it outran the user's) when the desk's did."""
    months = check.get("mandate_horizon_months")
    if months is None:
        return f"the {check['horizon_days']:g}-day horizon"
    if check.get("horizon_basis") == "desk":
        return (f"the desk's {check['desk_horizon_days']:g}-day horizon "
                f"(longer than your {months:g}-month setting)")
    return f"your {months:g}-month horizon"


def debt_default_check(inputs: Mapping[str, Any] | None) -> dict:
    """Decide a `debt_default` yes from the inputs. Returns `terminal_check`: `stands` (bool),
    `reason`, and the numbers. Pure and deterministic.

    Inputs beyond the balance sheet: `horizon_days` (the Execution Desk's stated horizon, with
    `horizon_source` / `horizon_phrase` saying where it came from), `mandate_horizon_months` and
    `min_coverage` (the user's, with `mandate_horizon_source` / `min_coverage_source`)."""
    i = inputs or {}
    ladder = i.get("ladder") or []
    desk_days = _num(i.get("horizon_days"))
    months = _num(i.get("mandate_horizon_months"))
    mandate_days = float(debt_horizon_days(months)) if months is not None and months > 0 else None
    given = [d for d in (desk_days, mandate_days) if d is not None and d > 0]
    horizon = max(given) if given else None
    basis = None
    if horizon is not None:
        basis = "desk" if mandate_days is None or (desk_days or 0) > mandate_days else "mandate"
    min_cov = _num(i.get("min_coverage"))
    min_cov_source = i.get("min_coverage_source") if min_cov is not None else "check_default"
    if min_cov is None:
        min_cov = DEBT_DEFAULT_MIN_COVERAGE
    check: dict[str, Any] = {
        "category": CHECKED_CATEGORY, "min_coverage": min_cov,
        "min_coverage_source": min_cov_source,
        "horizon_days": horizon, "horizon_basis": basis,
        "desk_horizon_days": desk_days,
        "desk_horizon_source": i.get("horizon_source"),
        "desk_horizon_phrase": i.get("horizon_phrase"),
        "mandate_horizon_months": months,
        "mandate_horizon_days": mandate_days,
        "mandate_horizon_source": i.get("mandate_horizon_source") if months is not None else None,
        "due_in_horizon": None, "available": None,
        "coverage": None, "cash": None, "cash_source": None, "fcf_ttm": None,
        "fcf_source": None, "buckets_counted": [], "buckets_not_counted": [],
        "unmapped_labels": [], "ladder_period_end": i.get("ladder_period_end"),
        "short_term_borrowings_not_counted": _num(i.get("short_term_borrowings")),
    }
    if not ladder:
        check.update(stands=False, reason=(
            "debt_default not evidenced: no debt-maturity schedule on the sheet"))
        return check
    if horizon is None:
        check.update(stands=True, skipped=True, reason=(
            "debt_default materiality check skipped: the trade horizon is unknown"))
        return check

    due = 0.0
    for label, value in ladder:
        start = bucket_start_day(label)
        v = _num(value)
        if v is None:
            continue
        if start is None:
            check["unmapped_labels"].append(label)
            check["buckets_counted"].append(label)
            due += v
        elif start < horizon:
            check["buckets_counted"].append(label)
            due += v
        else:
            check["buckets_not_counted"].append(label)
    check["due_in_horizon"] = due

    cash, cash_source = _num(i.get("total_cash")), "total_cash"
    if cash is None:
        debt, net_cash = _num(i.get("total_debt")), _num(i.get("net_cash"))
        if debt is not None and net_cash is not None:
            cash, cash_source = debt + net_cash, "total_debt_less_net_debt"
        else:
            cash, cash_source = 0.0, "unknown"
    fcf = _num(i.get("fcf_ttm"))
    fcf_source = (i.get("fcf_field") or "fcf_ttm") if fcf is not None else "unknown"
    available = cash + (fcf or 0.0) * horizon / DAYS_PER_YEAR
    check.update(cash=cash, cash_source=cash_source, fcf_ttm=fcf, fcf_source=fcf_source,
                 available=available)

    where = _horizon_phrase(check)
    own = "your" if min_cov_source != "check_default" else "the"
    amounts = f"cash {_fmt(cash)}, available {_fmt(available)}"
    if due <= 0:
        check.update(stands=False, coverage=None, reason=(
            f"debt_default covered: no principal falls due within {where} ({amounts})"))
        return check
    coverage = available / due
    check["coverage"] = coverage
    if coverage >= min_cov:
        check.update(stands=False, reason=(
            f"debt_default covered: {_fmt(due)} due within {where}; cash and cash flow cover "
            f"{_times(coverage, min_cov)}×, {own} minimum is {min_cov:.2f}× ({amounts})"))
    else:
        check.update(stands=True, reason=(
            f"debt_default stands: {_fmt(due)} due within {where}; cash and cash flow cover "
            f"{_times(coverage, min_cov)}×, {own} minimum is {min_cov:.2f}× ({amounts})"))
    return check


def apply_materiality(answer: QuestionAnswer, inputs: Mapping[str, Any] | None) -> QuestionAnswer:
    """The terminal answer after the materiality check. Anything other than a winning
    `debt_default` yes passes through unchanged. A refused yes becomes a "no" that keeps Ling's
    fields (so a reviewer sees what was named), carries the reason in `terminal_rejected` and the
    numbers in `terminal_check`, and is not "close": code, not a split vote, decided it."""
    detail = dict(answer.detail or {})
    if (answer.question is not QuestionId.TERMINAL_VULNERABILITY or answer.answer is not Answer.YES
            or detail.get("terminal_category") != CHECKED_CATEGORY):
        return answer
    check = debt_default_check(inputs)
    detail["terminal_check"] = check
    if check["stands"]:
        return replace(answer, detail=detail)
    earlier = detail.get("terminal_rejected")
    detail["terminal_rejected"] = f"{check['reason']}; {earlier}" if earlier else check["reason"]
    return replace(
        answer, answer=Answer.NO, close=False, detail=detail,
        rationale=f"{answer.rationale}; yes refused: {check['reason']}".strip("; "),
    )
