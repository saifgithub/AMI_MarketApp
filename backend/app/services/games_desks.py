"""CR109 slice 3c — the house strategy desks (design §11.2).

A field of one is not a competition. At alpha every open field is below the
placement threshold, so the flagship competitive surface is inert exactly when
the product most needs a player to feel something. Desks fix that structurally:
they fill the field, they supply a duel opponent (slice 3b), and they give a
Close something to be measured against other than an index line.

**Three properties define a desk, and all three are load-bearing.**

1. **A desk is disclosed.** It competes under its strategy name with its rule
   published. Saiful's argument, and it is the decisive one: *"if we do not
   disclose that it's a bot, then if the copy happens (and it can happen off
   app) the user is copying what they thought is a person!"* An undisclosed
   house account makes the user's belief about the source false, and once a
   screenshot leaves the app there is no disclosure surface left. Disclosure
   also dissolves the title tell — "desks are ranked but hold no titles" is a
   published rule rather than an exclusion a player can notice and decode.

2. **A desk's performance is real.** Its basket is selected from real price
   history by a stated rule, its orders ride the same queue and pay the same
   fee as a human's, and its NAV series is produced by the same snapshot tick.

   > A desk's P&L is never generated, sampled, or tuned to look plausible.

   This is not stylistic. §11.2 lets desk results feed real users' career
   points, so a fabricated return propagates into a real person's permanent
   Record — the DEF059 shape, and the exact failure CR040 exists to prevent.
   Every read in this module therefore checks provenance and **abstains** when
   the data is not real: `_MarketView` rejects a `mock_walk` bar series and a
   `mock_walk` quote outright, and a desk that cannot build its basket from
   real data does not enter the field at all. A field short one desk is
   honest; a desk trading on a synthetic walk is a scoring defect.

3. **A desk is subtracted from every real-user metric.** `users.is_desk` joins
   the CR035 room-benchmark synthetics and the seed rows in that filter. A
   design that inflates Saiful's own numbers is a design that deceives him.

**Why there is no desk execution path.** Desks enter with `games_service.
enter_field`, size with `quote_trade`, and submit with `submit_trade` — the
same three calls the iPhone makes. Because they act while the field is
`locked` (US market shut), their orders QUEUE and fill at Monday's open
through `process_queued_orders`, which is precisely what a human who traded
over the weekend gets. That parity is the point: there is no second code path
to keep honest, and the fee, the FIFO drain and the refusal-on-insufficient-
cash rules apply to a desk exactly as written.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Sequence
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app.core.config import settings
from app.core.logging import logger
from app.db import get_session
from app.db.models import GameEntryRow, GameFieldRow, User
from app.schemas.trade import Side
from app.services.market_data import (
    Candle,
    MarketDataProvider,
    get_market_data_provider,
    history_with_source,
)

# ── Provenance ───────────────────────────────────────────────────────────────

# A source whose bars/quotes are fabricated rather than observed. `market_data`
# falls through to `MockWalkProvider` — which derives a plausible-looking price
# from `hash(ticker)` — whenever the live feed 429s or errors. That fallback is
# correct for a chart (the user sees a MOCK pill) and catastrophic for a desk:
# it would select a basket from invented history and then have that basket's
# return score a real player. Matched by PREFIX so a future `mock_*` leaf is
# rejected by default rather than silently admitted.
_FABRICATED_SOURCE_PREFIXES = ("mock", "unavailable", "stale")


def _is_real_source(source: str | None) -> bool:
    if not source:
        return False
    return not source.lower().startswith(_FABRICATED_SOURCE_PREFIXES)


class DeskDataUnavailable(Exception):
    """A desk could not build its basket from REAL market data, so it does not
    enter. Raised, never swallowed into a default — the whole point is that
    there is no plausible-looking substitute for a real selection."""


# ── The published universe ───────────────────────────────────────────────────

# The names every desk selects from. Published with the rules, so a player can
# reproduce any desk's basket by hand — which is what makes copying a desk
# education (studying a stated method) rather than signal-chasing (following an
# anonymous winner), the distinction `rejected_features_register.md` turns on.
#
# Large, liquid US names across sectors. Breadth matters more than count: a
# universe of one sector makes Momentum and Contrarian pick the same names from
# opposite ends of the same move, which is a narrower spread than a real field.
DESK_UNIVERSE: tuple[str, ...] = (
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO",
    "ORCL", "CRM", "AMD", "ADBE", "CSCO", "QCOM", "TXN", "INTC",
    "JPM", "BAC", "WFC", "GS", "MS", "V", "MA", "AXP",
    "JNJ", "UNH", "PFE", "MRK", "ABBV", "LLY", "TMO",
    "XOM", "CVX", "COP",
    "WMT", "COST", "HD", "PG", "KO", "PEP", "MCD", "NKE",
    "CAT", "BA", "HON", "GE", "T", "VZ",
)

BENCHMARK_TICKER = "SPY"

# Fraction of the 10,000 stake a desk deploys. The remainder is not strategy —
# it is the gap between the price that sized the order on Friday and the price
# that fills it at Monday's open, plus the fee. A desk that deployed 100% would
# have its last order refused for insufficient cash on any up-gap, which is a
# real rule (the same one a human hits) but a silly way to lose a leg every
# time the market rises over a weekend.
DEPLOY_FRACTION = 0.97

_STAKE = 10_000.0


# ── The market view a strategy is allowed to see ─────────────────────────────


@dataclass(frozen=True)
class _Bars:
    ticker: str
    candles: tuple[Candle, ...]

    def total_return(self) -> float:
        """Price-only return across the whole window, as a fraction."""
        first = self.candles[0].c
        last = self.candles[-1].c
        if first <= 0:
            raise DeskDataUnavailable(f"{self.ticker}: non-positive first close")
        return (last - first) / first

    def trailing_return(self, sessions: int) -> float:
        """Price-only return over the last `sessions` bars."""
        if len(self.candles) <= sessions:
            return self.total_return()
        window = self.candles[-(sessions + 1):]
        first = window[0].c
        if first <= 0:
            raise DeskDataUnavailable(f"{self.ticker}: non-positive close")
        return (window[-1].c - first) / first


class _MarketView:
    """Real prices only. Every accessor here either returns observed data or
    omits the ticker — there is no code path that invents a number, which is
    what lets `test_cr109_house_desks.py` assert the fence rather than trust it.
    """

    _MIN_BARS = 30

    def __init__(self, provider: MarketDataProvider | None = None) -> None:
        self._provider = provider or get_market_data_provider()
        self._bars: dict[str, _Bars | None] = {}
        self._prices: dict[str, float | None] = {}
        self._yields: dict[str, float | None] = {}

    def bars(self, ticker: str, period: str = "1y") -> _Bars | None:
        key = f"{ticker}:{period}"
        if key not in self._bars:
            candles, source = history_with_source(self._provider, ticker, period)
            if not candles or not _is_real_source(source) or len(candles) < self._MIN_BARS:
                logger.info(
                    "desk_bars_rejected", ticker=ticker, period=period,
                    source=source, bar_count=len(candles or []),
                )
                self._bars[key] = None
            else:
                self._bars[key] = _Bars(ticker=ticker, candles=tuple(candles))
        return self._bars[key]

    def price(self, ticker: str) -> float | None:
        if ticker not in self._prices:
            q = self._provider.quote(ticker)
            if q is None or not _is_real_source(q.source) or q.price <= 0:
                logger.info(
                    "desk_quote_rejected", ticker=ticker,
                    source=getattr(q, "source", None),
                )
                self._prices[ticker] = None
            else:
                self._prices[ticker] = float(q.price)
        return self._prices[ticker]

    def dividend_yield(self, ticker: str) -> float | None:
        """Trailing annual dividend / price. `None` for a non-payer AND for a
        payer whose rate we could not read — the Dividend Desk treats both as
        "not selectable" rather than guessing a yield of zero, which would
        quietly rank a data gap as a non-payer."""
        if ticker not in self._yields:
            info = self._provider.earnings(ticker)
            rate = getattr(info, "dividend_rate", None) if info is not None else None
            px = self.price(ticker)
            if rate is None or px is None or px <= 0:
                self._yields[ticker] = None
            else:
                self._yields[ticker] = float(rate) / px
        return self._yields[ticker]

    def ranked(
        self, tickers: Sequence[str], key: Callable[[str], float | None], *, top: bool,
    ) -> list[str]:
        scored = [(t, key(t)) for t in tickers]
        usable = [(t, v) for t, v in scored if v is not None]
        usable.sort(key=lambda tv: (-tv[1], tv[0]) if top else (tv[1], tv[0]))
        return [t for t, _ in usable]


# ── The desks ────────────────────────────────────────────────────────────────


Basket = list[tuple[str, float]]


@dataclass(frozen=True)
class Desk:
    key: str
    name: str
    rule: str
    build: Callable[[_MarketView], Basket]


def _equal_weight(tickers: Sequence[str]) -> Basket:
    if not tickers:
        raise DeskDataUnavailable("no selectable tickers")
    w = 1.0 / len(tickers)
    return [(t, w) for t in tickers]


def _require(tickers: list[str], n: int, why: str) -> list[str]:
    if len(tickers) < n:
        raise DeskDataUnavailable(f"{why}: need {n} names with real data, got {len(tickers)}")
    return tickers[:n]


def _index_basket(view: _MarketView) -> Basket:
    if view.price(BENCHMARK_TICKER) is None:
        raise DeskDataUnavailable(f"no real price for {BENCHMARK_TICKER}")
    return [(BENCHMARK_TICKER, 1.0)]


def _momentum_basket(view: _MarketView) -> Basket:
    def score(t: str) -> float | None:
        b = view.bars(t, "1y")
        return None if b is None else b.total_return()

    ranked = view.ranked(DESK_UNIVERSE, score, top=True)
    return _equal_weight(_require(ranked, 5, "momentum"))


def _contrarian_basket(view: _MarketView) -> Basket:
    def score(t: str) -> float | None:
        b = view.bars(t, "1y")
        return None if b is None else b.trailing_return(63)  # ~3 months of sessions

    ranked = view.ranked(DESK_UNIVERSE, score, top=False)
    return _equal_weight(_require(ranked, 5, "contrarian"))


def _concentrated_basket(view: _MarketView) -> Basket:
    def score(t: str) -> float | None:
        b = view.bars(t, "1y")
        return None if b is None else b.trailing_return(21)  # ~1 month of sessions

    ranked = view.ranked(DESK_UNIVERSE, score, top=True)
    return _equal_weight(_require(ranked, 2, "concentrated"))


def _dividend_basket(view: _MarketView) -> Basket:
    ranked = view.ranked(DESK_UNIVERSE, view.dividend_yield, top=True)
    return _equal_weight(_require(ranked, 5, "dividend"))


def _equal_weight_basket(view: _MarketView) -> Basket:
    selectable = [t for t in DESK_UNIVERSE[:10] if view.price(t) is not None]
    return _equal_weight(_require(selectable, 8, "equal weight"))


DESK_ROSTER: tuple[Desk, ...] = (
    Desk(
        key="index",
        name="Index Desk",
        rule=f"Holds the benchmark ({BENCHMARK_TICKER}) for the whole run. Never trades again.",
        build=_index_basket,
    ),
    Desk(
        key="momentum",
        name="Momentum Desk",
        rule=(
            "Equal-weights the 5 names in the published universe with the "
            "highest trailing 12-month price return, measured at the open."
        ),
        build=_momentum_basket,
    ),
    Desk(
        key="dividend",
        name="Dividend Desk",
        rule=(
            "Equal-weights the 5 names in the published universe with the "
            "highest trailing annual dividend yield, measured at the open."
        ),
        build=_dividend_basket,
    ),
    Desk(
        key="equal_weight",
        name="Equal Weight Desk",
        rule=(
            "Equal-weights the first 10 names of the published universe. "
            "Selects nothing — the control against which selection is judged."
        ),
        build=_equal_weight_basket,
    ),
    Desk(
        key="contrarian",
        name="Contrarian Desk",
        rule=(
            "Equal-weights the 5 names in the published universe with the "
            "WORST trailing 3-month price return, measured at the open."
        ),
        build=_contrarian_basket,
    ),
    # Deliberately last, and deliberately narrow. A roster of only diversified
    # strategies produces a suspiciously tight spread — real fields have
    # blowups and moonshots, and this is where the tail comes from (§11.2).
    Desk(
        key="concentrated",
        name="Concentrated Desk",
        rule=(
            "Holds just 2 names — the strongest trailing 1-month performers in "
            "the published universe. High conviction, and it will sometimes be wrong."
        ),
        build=_concentrated_basket,
    ),
)

DESKS_BY_KEY: dict[str, Desk] = {d.key: d for d in DESK_ROSTER}


# ── Desk identities ──────────────────────────────────────────────────────────


def ensure_desk_users() -> dict[str, UUID]:
    """Create-or-fetch the roster's user rows. Idempotent on `desk_key`, which
    carries a DB unique constraint — so two containers starting at once cannot
    mint a second Momentum Desk.

    A desk row is deliberately a NORMAL user row with `is_desk=True` rather
    than a separate table: everything downstream (portfolios, NAV rows,
    entries, fills) already keys on `user_id`, and a parallel identity type
    would mean a second version of each of those paths — which is exactly how
    a fabricated-return path gets built by accident.
    """
    ids: dict[str, UUID] = {}
    with get_session() as s:
        for desk in DESK_ROSTER:
            row = s.execute(
                select(User).where(User.desk_key == desk.key)
            ).scalar_one_or_none()
            if row is None:
                row = User(
                    id=uuid4(),
                    is_desk=True,
                    desk_key=desk.key,
                    display_name=desk.name,
                    handle=desk.name,
                    is_anonymous=False,
                    plan="floor_pass",
                )
                s.add(row)
                s.flush()
                logger.info("desk_user_created", desk_key=desk.key, user_id=str(row.id))
            ids[desk.key] = row.id
    return ids


def desk_key_for(user_id: UUID) -> str | None:
    with get_session() as s:
        return s.execute(
            select(User.desk_key).where(User.id == user_id, User.is_desk.is_(True))
        ).scalar_one_or_none()


def entrant_identity(user_id: UUID) -> dict:
    """The ONE renderer for "who is this entrant" (§11.2's engineering fence:
    a desk is visibly a desk on every surface — board, duel, Close, share
    card). Every entrant-facing payload builds its name/flag from here, so a
    surface added later cannot forget to disclose."""
    with get_session() as s:
        row = s.execute(
            select(User.handle, User.display_name, User.is_desk, User.desk_key)
            .where(User.id == user_id)
        ).first()
    if row is None:
        return {"handle": None, "is_desk": False, "desk_key": None, "desk_rule": None}
    handle, display_name, is_desk, desk_key = row
    desk = DESKS_BY_KEY.get(desk_key or "")
    return {
        "handle": handle or display_name,
        "is_desk": bool(is_desk),
        "desk_key": desk_key,
        "desk_rule": desk.rule if desk else None,
    }


# ── Filling a field ──────────────────────────────────────────────────────────


def _field_cadence(field_id: UUID) -> str:
    """The field's OWN cadence. `enter_field`'s `cadence` argument drives the
    one-live-run-per-cadence check, so passing the default "week" while
    entering a monthly field would check the wrong ledger — a desk could then
    hold two monthly runs, or be refused a monthly entry because it already
    holds a weekly one."""
    with get_session() as s:
        return s.execute(
            select(GameFieldRow.cadence).where(GameFieldRow.id == field_id)
        ).scalar_one()


def _desks_already_in(field_id: UUID) -> set[str]:
    with get_session() as s:
        rows = s.execute(
            select(User.desk_key)
            .join(GameEntryRow, GameEntryRow.user_id == User.id)
            .where(GameEntryRow.field_id == field_id, User.is_desk.is_(True))
        ).scalars().all()
    return {r for r in rows if r}


def _human_entrant_count(field_id: UUID) -> int:
    with get_session() as s:
        return int(s.execute(
            select(func.count(GameEntryRow.id))
            .join(User, User.id == GameEntryRow.user_id)
            .where(GameEntryRow.field_id == field_id, User.is_desk.is_(False))
        ).scalar_one() or 0)


def desks_needed(human_count: int, already: int, target: int) -> int:
    """Fill TO a target field size, never a fixed count — so desks taper
    automatically as real entrants arrive and eventually stop appearing
    altogether (§11.2 "scaling and control"). Never negative: a field that has
    outgrown the target keeps the desks already in it (removing a live entrant
    mid-week would be a worse lie than one extra opponent) but adds none."""
    return max(0, min(len(DESK_ROSTER), target - human_count - already))


def _place_basket(
    user_id: UUID, run_id: UUID, basket: Basket, *, now: datetime,
) -> tuple[int, int]:
    """Size each leg by NOTIONAL through the same `quote_trade` the ticket uses,
    then submit through `submit_trade`. Outside market hours (which is always,
    because desks act while the field is `locked`) that queues the order —
    identical treatment to a human who traded over the weekend."""
    from app.services import games_service

    placed = 0
    skipped = 0
    for ticker, weight in basket:
        notional = _STAKE * DEPLOY_FRACTION * weight
        try:
            quote = games_service.quote_trade(
                user_id, run_id, ticker=ticker, side=Side.BUY, notional=notional,
            )
            if not _is_real_source(quote.get("price_source")):
                # Sizing off a fabricated price would put a real share count on
                # a desk's book from a number nobody observed. Skip the leg.
                logger.warning(
                    "desk_leg_skipped_fabricated_price",
                    ticker=ticker, source=quote.get("price_source"),
                )
                skipped += 1
                continue
            qty = float(quote["quantity"])
            if qty <= 0:
                skipped += 1
                continue
            games_service.submit_trade(
                user_id, run_id, ticker=ticker, side=Side.BUY, quantity=qty, now=now,
            )
            placed += 1
        except Exception:
            logger.exception("desk_leg_failed", ticker=ticker, run_id=str(run_id))
            skipped += 1
    return placed, skipped


def fill_field_with_desks(
    field_id: UUID, *, now: datetime | None = None, view: _MarketView | None = None,
) -> dict:
    """Enter as many desks as the field is short of `games_desk_target_field_size`,
    and place each one's opening basket.

    Runs while the field is `locked` — after entries close, so the taper is
    computed against the FINAL human count, and before the market opens, so
    every desk order queues and fills at the same open a human's weekend order
    does. A desk that cannot build a real basket is skipped and the next one is
    tried; it is never entered with an empty book, because an entrant that
    holds nothing all week is a fake 0% opponent.
    """
    from app.services import games_service

    now = now or datetime.now(timezone.utc)
    if not settings.games_desks_enabled:
        return {"entered": 0, "skipped": 0, "reason": "kill switch off"}

    already = _desks_already_in(field_id)
    humans = _human_entrant_count(field_id)
    want = desks_needed(humans, len(already), settings.games_desk_target_field_size)
    if want <= 0:
        return {"entered": 0, "skipped": 0, "humans": humans, "desks_present": len(already)}

    ids = ensure_desk_users()
    cadence = _field_cadence(field_id)
    view = view or _MarketView()
    entered = 0
    skipped = 0
    for desk in DESK_ROSTER:
        if entered >= want:
            break
        if desk.key in already:
            continue
        try:
            basket = desk.build(view)
        except DeskDataUnavailable as exc:
            # Loud, and it does NOT fall back to a plausible basket. §11.2's
            # integrity line: a desk with no real data does not play.
            logger.warning("desk_abstained", desk_key=desk.key, reason=str(exc))
            skipped += 1
            continue

        user_id = ids[desk.key]
        try:
            entry = games_service.enter_field(
                user_id, cadence=cadence, now=now, as_desk=True, field_id=field_id,
            )
        except games_service.GamesServiceError as exc:
            logger.warning("desk_entry_failed", desk_key=desk.key, reason=str(exc))
            skipped += 1
            continue

        placed, legs_skipped = _place_basket(user_id, entry.run_id, basket, now=now)
        if placed == 0:
            logger.warning("desk_entered_with_no_legs", desk_key=desk.key)
        logger.info(
            "desk_entered", desk_key=desk.key, field_id=str(field_id),
            run_id=str(entry.run_id), legs=placed, legs_skipped=legs_skipped,
        )
        entered += 1

    return {"entered": entered, "skipped": skipped, "humans": humans, "target": want}


def fields_in_lock_window(now: datetime) -> list[UUID]:
    """Fields whose entries have closed but whose market open has not arrived —
    the desk-fill window.

    Derived from each row's OWN `locks_at` / `starts_on` rather than from its
    `state` column. `ensure_weekly_field` only refreshes the state of the field
    it is currently targeting, and in exactly this window that is NEXT week's
    field — so this week's row can still read `entry_open` while it is in fact
    locked. Filtering on the stale column would have found nothing, every week,
    silently.
    """
    from app.services.games_service import _as_utc, _market_open_et

    today_et = now.astimezone(ZoneInfo("America/New_York")).date()
    with get_session() as s:
        rows = s.execute(
            select(GameFieldRow.id, GameFieldRow.starts_on, GameFieldRow.locks_at)
            .where(GameFieldRow.kind == "open", GameFieldRow.starts_on >= today_et)
        ).all()
    return [
        fid for fid, starts_on, locks_at in rows
        if _as_utc(locks_at) <= now < _market_open_et(starts_on)
    ]


def run_desk_fill_tick(*, now: datetime | None = None) -> dict:
    """Background entry point. Idempotent: `_desks_already_in` is the guard, so
    a restart mid-fill resumes rather than double-entering, and a tick that
    finds every locked field already populated does nothing.

    A field whose lock window was missed entirely (container down for the 30
    minutes before the open) simply runs without desks — a short field is
    honest, whereas a desk that started trading after the market moved is not
    the same contest the humans entered.
    """
    from app.services.games_service import _SUPPORTED_CADENCES, ensure_field

    now = now or datetime.now(timezone.utc)
    if not settings.games_desks_enabled:
        return {"fields": 0, "entered": 0}

    # Roll every cadence, not just weekly — a monthly or quarterly field that
    # was never created has no lock window for the desks to fill.
    with get_session() as s:
        for cadence in _SUPPORTED_CADENCES:
            ensure_field(s, cadence, now=now)

    locked = fields_in_lock_window(now)
    entered = 0
    for field_id in locked:
        stats = fill_field_with_desks(field_id, now=now)
        entered += stats.get("entered", 0)
    return {"fields": len(locked), "entered": entered}


def is_desk_user(user_id: UUID) -> bool:
    with get_session() as s:
        return bool(s.execute(
            select(User.is_desk).where(User.id == user_id)
        ).scalar_one_or_none())


def desk_user_ids() -> list[UUID]:
    """Every desk's user id — the handle every real-user metric filters on."""
    with get_session() as s:
        return list(s.execute(select(User.id).where(User.is_desk.is_(True))).scalars().all())


def published_roster() -> list[dict]:
    """What the rules surface renders. Disclosure is the feature, so this is a
    first-class payload rather than a comment in a doc nobody opens."""
    return [
        {"key": d.key, "name": d.name, "rule": d.rule, "universe": list(DESK_UNIVERSE)}
        for d in DESK_ROSTER
    ]


__all__ = [
    "BENCHMARK_TICKER",
    "DESK_ROSTER",
    "DESK_UNIVERSE",
    "DESKS_BY_KEY",
    "Desk",
    "DeskDataUnavailable",
    "desk_key_for",
    "desk_user_ids",
    "desks_needed",
    "ensure_desk_users",
    "entrant_identity",
    "fill_field_with_desks",
    "is_desk_user",
    "published_roster",
    "run_desk_fill_tick",
]
