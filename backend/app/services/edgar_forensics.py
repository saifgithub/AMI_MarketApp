"""CR247 Phase 1D — forensic metadata flags for the Room sheet.

Four deterministic flags, all computed in Python from data CR244 already
fetches (the LLM never computes a figure — standing rule, DEF066→DEF241):

  1. Insider open-market buy/sell ratio (90d) — Form 4/5 transaction codes
     P (open-market purchase) and S (open-market sale) only. M (option
     exercise), F (tax withholding), A (grant) and every other code are
     excluded by REUSING `edgar_ownership`'s own direction classification
     (`InsiderTransaction.direction` is "buy"/"sell" ONLY for P/S — the
     CR244 extraction layer decided this, verified live against NVDA/AAPL
     filings; this module does not re-classify).
  2. Rule 10b5-1 plan tag on insider sales — the `plan_type` structural tag
     CR244 reads from the Form 4's own `aff10b5One` checkbox (never inferred
     from footnotes or by a model). Consumed here as a sheet label.
  3. Cluster-buy flag — ≥3 DISTINCT insiders with code-P transactions whose
     filing dates fall inside a 14-day window (max−min ≤ 14 days). Absence
     is information: the sheet renders "no cluster buying", never omits.
  4. 8-K timing/item flags (180d) — (a) 8-Ks accepted Friday at/after 4:00 pm
     ET ("Friday-after-close filing"), (b) Item 4.01 (change of auditor),
     (c) Item 4.02 (non-reliance on previously issued financial statements).
     Item 4.02 additionally feeds the safety floor: a hard deterministic
     block on BUY, narrated in the verdict reason (never a silent refusal).

Window basis: FILING date, not transaction date — a fact is knowable to the
Room on the date the Form 4/5 or 8-K was filed, which is also the PIT-correct
choice for as-of runs (CR040).

Live-only split: flags 1–3 read `edgar_ownership.get_insider_activity`,
whose 90-day window is anchored to the wall clock (it has no as-of parameter
and there is no historical insider store) — past-dated sheets get
`not_available` with that reason, the same contract `put_call`/`peer_basket`
follow (DEF334 shape). Flag 4 goes through
`edgar_filings_feed.fetch_8k_item_flags`, which takes `as_of` explicitly and
re-implements the feed's own point-in-time windowing (including the
`filings.files` page coverage, audit B2), so as-of runs DO get it.

Every string lifted from fetched data passes `sanitize_for_prompt` at the
render seam (DEF370), the same discipline `edgar_8k.executive_change_line`
and `edgar_filings_feed.recent_filings_line` apply.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.schemas.company_profile import InsiderTransaction
from app.services.prompt_safety import sanitize_for_prompt

INSIDER_WINDOW_DAYS = 90
CLUSTER_MIN_INSIDERS = 3
CLUSTER_SPAN_DAYS = 14
EIGHT_K_WINDOW_DAYS = 180
_FRIDAY_CUTOFF_HOUR_ET = 16  # 4:00 pm ET
_ET = ZoneInfo("America/New_York")

INSIDER_RATIO_LABEL = "Insider open-market buy/sell ratio (90d)"
INSIDER_PLAN_TAG_LABEL = "Insider sales under Rule 10b5-1 plans"
CLUSTER_BUY_LABEL = "Cluster buying"
EIGHT_K_FLAGS_LABEL = "8-K forensic flags"

_MAX_FLAG_DATES_LISTED = 3


# ── Flag 1 — insider open-market buy/sell ratio ──────────────────────────────


@dataclass(frozen=True)
class InsiderRatio:
    window_start: date
    window_end: date
    buys: int
    sells: int
    ratio: float | None  # None when there is no sell side to ratio against


def _filed_on_or_after(t: InsiderTransaction, window_start: date) -> bool:
    try:
        return date.fromisoformat(t.filed_date) >= window_start
    except ValueError:
        return False


def _windowed_ps(
    transactions: list[InsiderTransaction], *, window_start: date, window_end: date,
) -> tuple[list[InsiderTransaction], list[InsiderTransaction]]:
    """The P/S rows whose FILING date sits inside [window_start, window_end].

    The caller's feed already windows by filed date; this re-asserts the
    bound so an as-of overlay can narrow further (and so a hand-built
    transaction list cannot smuggle an out-of-window row past the math)."""
    buys: list[InsiderTransaction] = []
    sells: list[InsiderTransaction] = []
    for t in transactions:
        if not _filed_on_or_after(t, window_start):
            continue
        try:
            filed = date.fromisoformat(t.filed_date)
        except ValueError:
            continue
        if filed > window_end:
            continue
        if t.direction == "buy":
            buys.append(t)
        elif t.direction == "sell":
            sells.append(t)
    return buys, sells


def insider_ratio(
    transactions: list[InsiderTransaction], *, window_start: date, window_end: date,
) -> InsiderRatio:
    buys, sells = _windowed_ps(transactions, window_start=window_start, window_end=window_end)
    return InsiderRatio(
        window_start=window_start, window_end=window_end,
        buys=len(buys), sells=len(sells),
        ratio=round(len(buys) / len(sells), 2) if sells else None,
    )


def insider_ratio_line(r: InsiderRatio, *, live: bool, partial_reason: str | None = None) -> str:
    marker = " (LIVE)" if live else ""
    basis = "AMI-computed from the issuer's SEC Form 4/5 filings"
    caveat = f" (incomplete feed: {sanitize_for_prompt(partial_reason)})" if partial_reason else ""
    if r.sells == 0 and r.buys == 0:
        return (
            f"{INSIDER_RATIO_LABEL}{marker}: no open-market insider purchases or sales "
            f"filed between {r.window_start.isoformat()} and {r.window_end.isoformat()} "
            f"(transaction codes P/S only — option exercises (M), tax withholdings (F) "
            f"and every other code excluded), {basis}.{caveat}"
        )
    if r.sells == 0:
        return (
            f"{INSIDER_RATIO_LABEL}{marker}: {r.buys} open-market buy{'s' if r.buys != 1 else ''} "
            f"and no open-market sales filed between {r.window_start.isoformat()} and "
            f"{r.window_end.isoformat()} (codes P/S only) — no sell side to ratio "
            f"against, {basis}.{caveat}"
        )
    return (
        f"{INSIDER_RATIO_LABEL}{marker}: {r.buys} open-market buy{'s' if r.buys != 1 else ''} "
        f"vs {r.sells} open-market sale{'s' if r.sells != 1 else ''} filed between "
        f"{r.window_start.isoformat()} and {r.window_end.isoformat()} (codes P/S only) "
        f"— {r.ratio:.2f} buy{'s' if r.ratio != 1 else ''} per sale, {basis}.{caveat}"
    )


# ── Flag 2 — 10b5-1 plan tag on insider sales ───────────────────────────────


@dataclass(frozen=True)
class InsiderPlanTag:
    window_start: date
    window_end: date
    sales: int
    scheduled: int   # plan_type == "scheduled_10b5-1" (the checkbox, ticked)
    discretionary: int
    unstated: int    # pre-2023 forms carry no aff10b5One element at all


def insider_plan_tag(
    transactions: list[InsiderTransaction], *, window_start: date, window_end: date,
) -> InsiderPlanTag:
    _, sells = _windowed_ps(transactions, window_start=window_start, window_end=window_end)
    return InsiderPlanTag(
        window_start=window_start, window_end=window_end, sales=len(sells),
        scheduled=sum(1 for t in sells if t.plan_type == "scheduled_10b5-1"),
        discretionary=sum(1 for t in sells if t.plan_type == "discretionary"),
        unstated=sum(1 for t in sells if t.plan_type == "unstated"),
    )


def insider_plan_tag_line(p: InsiderPlanTag, *, live: bool, partial_reason: str | None = None) -> str:
    marker = " (LIVE)" if live else ""
    caveat = f" (incomplete feed: {sanitize_for_prompt(partial_reason)})" if partial_reason else ""
    if p.sales == 0:
        return (
            f"{INSIDER_PLAN_TAG_LABEL}{marker}: none — no open-market insider sales filed "
            f"between {p.window_start.isoformat()} and {p.window_end.isoformat()}, so the "
            f"plan tag has nothing to attach to.{caveat}"
        )
    return (
        f"{INSIDER_PLAN_TAG_LABEL}{marker}: of the {p.sales} open-market sale{'s' if p.sales != 1 else ''} "
        f"in the window, {p.scheduled} "
        f"{'were' if p.scheduled != 1 else 'was'} pre-scheduled under Rule 10b5-1 plans "
        f"(flag read from the Form 4's own 10b5-1 checkbox, never inferred), "
        f"{p.discretionary} discretionary, {p.unstated} unstated — a scheduled plan sale "
        f"is not fresh conviction; a non-plan or unstated sale is the stronger signal.{caveat}"
    )


# ── Flag 3 — cluster buying ──────────────────────────────────────────────────


@dataclass(frozen=True)
class ClusterBuy:
    window_start: date
    window_end: date
    cluster: bool
    insiders: int
    span_start: date | None
    span_end: date | None


def cluster_buy(
    transactions: list[InsiderTransaction], *, window_start: date, window_end: date,
    min_insiders: int = CLUSTER_MIN_INSIDERS, span_days: int = CLUSTER_SPAN_DAYS,
) -> ClusterBuy:
    """≥`min_insiders` DISTINCT insiders with code-P rows whose filing dates
    fit inside a `span_days`-day span (max−min ≤ span_days). Deterministic
    tie-break: most insiders, then earliest span, then shortest span."""
    buys, _ = _windowed_ps(transactions, window_start=window_start, window_end=window_end)
    by_date: dict[date, set[str]] = {}
    for t in buys:
        try:
            filed = date.fromisoformat(t.filed_date)
        except ValueError:
            continue
        by_date.setdefault(filed, set()).add(t.insider_name)
    dates = sorted(by_date)
    best: tuple[int, date, date] | None = None  # (insiders, span_start, span_end)
    for i, start in enumerate(dates):
        insiders: set[str] = set()
        end = start
        for d in dates[i:]:
            if (d - start).days > span_days:
                break
            insiders |= by_date[d]
            end = d
        if len(insiders) < min_insiders:
            continue
        candidate = (len(insiders), start, end)
        if (
            best is None
            or candidate[0] > best[0]
            or (candidate[0] == best[0] and (candidate[1], candidate[2]) < (best[1], best[2]))
        ):
            best = candidate
    if best is None:
        return ClusterBuy(window_start, window_end, False, 0, None, None)
    return ClusterBuy(window_start, window_end, True, best[0], best[1], best[2])


def cluster_buy_line(c: ClusterBuy, *, live: bool, partial_reason: str | None = None) -> str:
    caveat = f" (incomplete feed: {sanitize_for_prompt(partial_reason)})" if partial_reason else ""
    if c.cluster and c.span_start is not None and c.span_end is not None:
        return (
            f"{CLUSTER_BUY_LABEL} (LIVE): YES — {c.insiders} distinct insiders bought in the "
            f"open market between {c.span_start.isoformat()} and {c.span_end.isoformat()} "
            f"(code P; window {c.window_start.isoformat()} to {c.window_end.isoformat()}), "
            f"AMI-computed from the issuer's SEC Form 4/5 filings.{caveat}"
        )
    return (
        f"{CLUSTER_BUY_LABEL}: none — no cluster buying in the last "
        f"{(c.window_end - c.window_start).days} days (fewer than {CLUSTER_MIN_INSIDERS} "
        f"distinct insiders with code-P open-market buys inside any "
        f"{CLUSTER_SPAN_DAYS}-day window between {c.window_start.isoformat()} and "
        f"{c.window_end.isoformat()}).{caveat}"
    )


# ── Flag 4 — 8-K timing/item flags ───────────────────────────────────────────


@dataclass(frozen=True)
class EightKFiling:
    form: str
    filed: date
    accession: str
    items: tuple[str, ...]
    acceptance: datetime | None  # UTC acceptance timestamp, when the index carried one


@dataclass(frozen=True)
class EightKFlags:
    window_start: date
    window_end: date
    friday_after_close: tuple[EightKFiling, ...]
    friday_timing_determinable: bool  # False when the index carried no acceptance times at all
    item_401: tuple[EightKFiling, ...]
    item_402: tuple[EightKFiling, ...]


def eight_k_flags(filings: list[EightKFiling], *, window_start: date, window_end: date) -> EightKFlags:
    in_window = [f for f in filings if window_start <= f.filed <= window_end]
    friday: list[EightKFiling] = []
    for f in in_window:
        if f.acceptance is None:
            continue
        local = f.acceptance.astimezone(_ET)
        if local.weekday() == 4 and (local.hour, local.minute) >= (_FRIDAY_CUTOFF_HOUR_ET, 0):
            friday.append(f)
    return EightKFlags(
        window_start=window_start, window_end=window_end,
        friday_after_close=tuple(sorted(friday, key=lambda f: f.filed, reverse=True)),
        friday_timing_determinable=any(f.acceptance is not None for f in filings) or not filings,
        item_401=tuple(sorted(
            (f for f in in_window if "4.01" in f.items), key=lambda f: f.filed, reverse=True,
        )),
        item_402=tuple(sorted(
            (f for f in in_window if "4.02" in f.items), key=lambda f: f.filed, reverse=True,
        )),
    )


def _et_hhmm(acceptance: datetime) -> str:
    local = acceptance.astimezone(_ET)
    hour12 = local.hour % 12 or 12
    return f"{hour12}:{local.minute:02d} {'am' if local.hour < 12 else 'pm'} ET"


def _dated_flag_line(
    label: str, filings: tuple[EightKFiling, ...], *, window: EightKFlags, none_phrase: str,
    tail: str = "",
) -> str:
    if not filings:
        return (
            f"{label}: {none_phrase} between {window.window_start.isoformat()} and "
            f"{window.window_end.isoformat()}."
        )
    shown = filings[:_MAX_FLAG_DATES_LISTED]
    parts = [
        f"{sanitize_for_prompt(f.filed.isoformat())} ({_et_hhmm(f.acceptance)})" if f.acceptance
        else sanitize_for_prompt(f.filed.isoformat())
        for f in shown
    ]
    if len(filings) > len(shown):
        parts.append(f"+{len(filings) - len(shown)} more")
    return (
        f"{label}: {len(filings)} — " + ", ".join(parts)
        + f" — AMI-computed from the issuer's SEC filings index.{tail}"
    )


def eight_k_flags_lines(f: EightKFlags) -> list[str]:
    """The three 8-K flag lines, all AMI-computed; absence rendered, not omitted."""
    if not f.friday_timing_determinable:
        friday_line = (
            f"8-K Friday-after-close filings ({EIGHT_K_WINDOW_DAYS}d): not determinable — the "
            f"filings index carried no acceptance times, so Friday-after-4pm-ET timing "
            f"cannot be computed."
        )
    else:
        friday_line = _dated_flag_line(
            f"8-K Friday-after-close filings ({EIGHT_K_WINDOW_DAYS}d)",
            f.friday_after_close, window=f,
            none_phrase="none filed Friday at/after 4:00 pm ET",
        )
    item_401_line = _dated_flag_line(
        f"8-K Item 4.01 (change of auditor) ({EIGHT_K_WINDOW_DAYS}d)",
        f.item_401, window=f, none_phrase="none filed",
        tail=" A change of auditor is a flag, not proof of wrongdoing — report the date, "
             "do not infer a cause.",
    )
    item_402_line = _dated_flag_line(
        f"8-K Item 4.02 (non-reliance on prior financials) ({EIGHT_K_WINDOW_DAYS}d)",
        f.item_402, window=f, none_phrase="none filed",
        tail=" While an Item 4.02 filing stands in this window, AMI's safety floor "
             "hard-blocks new BUY proposals on this name — the block is narrated in "
             "the verdict, never silent.",
    )
    return [friday_line, item_401_line, item_402_line]


def item_402_block_reason(f: EightKFlags) -> str | None:
    """The safety-floor narration for the newest in-window Item 4.02 filing,
    or None when there is nothing to block on. Computed in code; the floor
    embeds this verbatim in the REJECT reason."""
    if not f.item_402:
        return None
    newest = f.item_402[0]
    return (
        f"an 8-K Item 4.02 (non-reliance on previously issued financial statements) "
        f"was filed on {newest.filed.isoformat()} (accession {sanitize_for_prompt(newest.accession)}), "
        f"inside the {EIGHT_K_WINDOW_DAYS}-day window ending {f.window_end.isoformat()} — "
        f"AMI does not open a new BUY while the issuer's reported figures are under "
        f"non-reliance; wait for the restated or re-audited statements before buying"
    )


# ── Shared degrade line ──────────────────────────────────────────────────────


def forensic_not_available_line(label: str, reason: str) -> str:
    return (
        f"{label}: not available this call — {sanitize_for_prompt(reason)}. "
        "Do not estimate insider or filing activity from memory."
    )


def parse_acceptance_datetime(raw: Any) -> datetime | None:
    """`filings.recent.acceptanceDateTime` → tz-aware UTC, or None when absent
    or unparseable. The index ships ISO-8601 with a Z suffix; both that and a
    numeric-offset form are accepted, nothing is guessed."""
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed
