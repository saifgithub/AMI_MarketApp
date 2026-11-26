"""CR267 WP-24 — same inputs return the same Room.

Two things live here, both pure of the Room runner (the runner imports this):

1. **The frozen fact sheet.** A ticker's sheet is built once per trading day and
   stored; every later Room that day reads the stored copy, so the same day
   yields a byte-identical sheet and the sheet can be hashed. The stored form is
   the CR237 `encode_profile` codec, and the copy handed back is always decoded
   from the stored bytes, so the first reader and every later one see the same
   object graph.

2. **The Room key.** SHA-256 over (user, ticker, mandate digest, fact-sheet hash,
   policy version, model root). A convene whose key matches a finished Room is
   handed that Room. The key is per user: sharing Rooms across users is a later
   cost optimisation, not this programme's.

The key also carries what the desks read from the user's own account, so a Room
is never served after the user's position changed (Saiful's ruling, 2026-11-20):

- `portfolio`: the sim portfolio the desks' holdings block is built from: cash
  rounded to whole dollars, holdings, short and option legs, the open lots
  (ticker, quantity, entry, stop) and the trade history the risk-limit checks
  read (every trade's opened/closed time and status). Any trade gives a new Room.
- `journal`: the Decision Journal entries the Bull and Bear desks read for this
  ticker (the latest five), as (id, title, outcome, summary, user note).
  Room-run entries are left out: they are the Rooms' own output, so including
  them would make a Room's key change the moment it finished and no repeat
  convene could ever match.
- `alpaca`: a linked paper account's cash (whole dollars) and its positions'
  symbol and quantity.
- `brief` (DEF513): the user's active Brief Your Agent overlay for each of the
  twelve desks, as the text the prompt renders (stripped content; an empty
  overlay is the same as none). Editing a Brief, or rolling back to different
  text, gives a new Room; rolling back to identical text does not.
- `universe` (DEF513): the sourced compliance verdicts for this ticker (Sharia,
  fossil / sin / esg-lite exclusion, liquidity) with each snapshot's stale flag
  (not its as-of date, which advances daily with no change to a verdict: DEF517).
  These are global reference data refreshed daily without a
  deploy, and they feed both the prompts and the deterministic compliance check.
- `roster` (DEF513): which analyst desks the plan and tenure withheld.
- `tier` (DEF513): the model tier `pick_tier` gives the plan for every desk the
  Room runs. A plan change moves it, so an upgrade gets a new Room.

The policy version (`policy_version`) hashes the prompt generation, the revision
and every global setting that changes what a Room says or decides
(`ROOM_POLICY_SETTINGS`); settings are env-driven, so they can change on a
container recreate with no code deploy.

What the key deliberately does NOT contain: the credit balance, the plan, the
mandate's version counter and timestamps (re-saving an unchanged mandate is not a
new input). The "prior convene" comparison the CIO
reads is this ticker's previous Room, i.e. the bank's own output: keying it would
make every finished Room unkey its own repeat (the same trap as Room-run journal
entries). `ROOM_INPUT_CLASSES` classifies every parameter the Room is built from,
and a test fails on an unclassified one. Nor anything that is only a price times a holding: portfolio value,
drawdown, open-risk percent, unrealised P&L and the Alpaca market values move with
every tick, and the trading day is already keyed.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Callable
from uuid import UUID

from sqlalchemy import select

from app.core.logging import logger
from app.db import get_session
from app.db.ami_claim import claim
from app.db.models import RoomFactSheetRow, RoomRunRow
from app.schemas import TWELVE_AGENT_IDS, AgentId
from app.schemas.mandate import Mandate
from app.services.cio_snapshot_codec import decode_profile, encode_profile
from app.trading_math.market_calendar import trading_date as market_trading_date
from app.trading_math.markets import Market, market_for
from app.trading_math.risk_limits import (
    resolved_debt_horizon_months,
    resolved_min_debt_coverage,
    resolved_min_reward_risk,
)
from app.trading_math.session_calendar import last_us_session_date

# Bump when the Room's decision logic changes in a way the assembled prompts do
# not capture (a new aggregation rule, a changed compliance floor). The prompt
# generation is hashed in separately and moves on its own.
ROOM_POLICY_REVISION = "1"

# `Mandate` fields that are not part of what the user asked for. Plan state is
# stamped on at read time (never persisted on the row); `version`/`created_at`/
# `updated_at` move on a save that changed nothing.
MANDATE_KEY_EXCLUDED: frozenset[str] = frozenset({
    "version",
    "plan",
    "trial_expires_at",
    "credit_balance",
    "credit_allowance",
    "credits_reset_at",
    "room_cost",
    "room_live_data_surcharge_max",
    "room_cooldown_until",
    "resolved",
    "day_trader_preset",
    "created_at",
    "updated_at",
})


# Global settings that change what a Room says or decides. Env-driven, so they can
# change on a container recreate with no code deploy; they ride in `policy_version`.
ROOM_POLICY_SETTINGS: frozenset[str] = frozenset({
    "use_real_market_data",
    "output_guard_mode",
    "output_guard_max_turn_words",
    "training_preregistration_required",
    "prereg_applies_to_long_horizon",
    "pm_self_consistency_samples",
    "pm_option_ladder_enabled",
    "room_max_scripted_turns",
    "room_risk_officer_enabled",
    "room_factcheck_notes",
    "room_debate_order_seeded",
    "room_json_constraints_enabled",
    "room_trader_regex_enabled",
    "room_veto_review_enabled",
    "room_resurrection_review_enabled",
    "room_cards_envelope_enabled",
    "room_evidence_gate_enabled",
    "room_evidence_gate_thresholds_json",
    "room_evidence_contested_margin",
    "room_coded_rule_enabled",
    "room_grader",
    "room_coded_rule_policy_json",
    "room_debt_maturity_enabled",
    "room_cost_of_debt_enabled",
    "room_cashflow_bridge_enabled",
    "room_fcf_history_enabled",
    "room_fcf_conversion_enabled",
    "room_roe_history_enabled",
    "room_debt_split_enabled",
    "room_segment_revenue_enabled",
    "room_geographic_revenue_enabled",
    "room_executive_change_enabled",
    "room_recent_filings_enabled",
    "room_float_liquidity_enabled",
    "room_dividend_growth_enabled",
    "room_buyback_price_enabled",
    "room_sbc_enabled",
    "room_roic_enabled",
    "room_put_call_enabled",
    "room_peer_comparison_enabled",
    "room_wacc_enabled",
    "room_insider_ratio_enabled",
    "room_insider_plan_tag_enabled",
    "room_insider_cluster_enabled",
    "room_edgar_8k_flags_enabled",
})

# Settings the Room code reads that do not change a Room's content, with why.
ROOM_SETTINGS_NOT_KEYED: dict[str, str] = {
    "room_agent_timeout_s": "failure-mode timing, not content",
    "room_grader_deepinfra_base_url": "endpoint of the grader; the grader's identity (model, averaging) is keyed through the grader version in `coded_rule`",
    "room_grader_deepinfra_model": "keyed through the grader version in `coded_rule` (policy hash), not as a raw setting",
    "room_grader_deepinfra_api_key": "a credential, never keyed or logged",
    "room_grader_deepinfra_timeout_s": "failure-mode timing, not content",
    "room_grader_ling_timeout_s": "failure-mode timing, not content; the Ling model is keyed through the grader version in `coded_rule`",
    "room_grader_ling_terminal": "which terminal question the Ling grader asks; keyed through the grader version (`|term=v2`) in `coded_rule`",
    "room_char_delay_min_ms": "stream pacing",
    "room_char_delay_max_ms": "stream pacing",
    "room_turn_pace_cap_s": "stream pacing",
    "room_pace_cap_s": "stream pacing",
    "room_dedup_running_minutes": "reattach window, not content",
    "room_bank_enabled": "the bank's own off switch",
    "room_model_root_ttl_s": "cache lifetime of the keyed model root",
    "room_cio_retry_max_age_minutes": "retry eligibility, not content",
    "room_pullback_days_social": "decides the roster, which is keyed as `roster`",
    "room_pullback_days_news": "decides the roster, which is keyed as `roster`",
    "room_pullback_days_market": "decides the roster, which is keyed as `roster`",
    "vllm_base_url": "where the model is served; the served model root is keyed",
    "vllm_fallback_model": "backup slot identity; its root is keyed on a failover",
}

# Every parameter the Room is built from, by entry point, and where it lands.
# "keyed:<part>" is a key part; "excluded:<why>" is deliberately not. A test
# fails when a parameter of these functions is missing here.
ROOM_INPUT_CLASSES: dict[str, dict[str, str]] = {
    "RoomStartRequest": {
        "user_id": "keyed:user_id",
        "ticker": "keyed:ticker",
        "mandate_override": "keyed:mandate (only read when no mandate is stored; hydrated into the mandate)",
        "locale": "keyed:mandate (copied onto the mandate before the digest)",
        "alpaca": "keyed:alpaca",
    },
    "RoomRunner.start_run": {
        "user_id": "keyed:user_id",
        "ticker": "keyed:ticker",
        "mandate": "keyed:mandate",
        "portfolio_value": "excluded:price times holding, server-computed",
        "current_drawdown_pct": "excluded:price times holding, server-computed",
        "char_delay_min": "excluded:stream pacing",
        "char_delay_max": "excluded:stream pacing",
        "agent_timeout_s": "excluded:failure-mode timing",
        "on_complete": "excluded:callback",
        "backtest": "excluded:backtest runs never bank",
        "alpaca_snapshot": "keyed:alpaca (rendered from the payload alpaca_key hashes)",
        "bank_outcome": "excluded:out-parameter",
        "alpaca_key": "keyed:alpaca",
    },
    "RoomRunner.run": {
        "run_id": "excluded:identity",
        "user_id": "keyed:user_id",
        "ticker": "keyed:ticker",
        "mandate": "keyed:mandate",
        "portfolio_value": "excluded:price times holding, server-computed",
        "current_drawdown_pct": "excluded:price times holding, server-computed",
        "halal_universe": "keyed:universe (injected by tests only; production fetches it)",
        "classification_universe": "keyed:universe (injected by tests only; production fetches it)",
        "locale_allowed_universe": "excluded:always None in production",
        "char_delay_min": "excluded:stream pacing",
        "char_delay_max": "excluded:stream pacing",
        "agent_timeout_s": "excluded:failure-mode timing",
        "news_feed": "keyed:fact_sheet (the sheet variant)",
        "social_feed": "keyed:fact_sheet (the sheet variant)",
        "credit_cost": "excluded:billing",
        "roster": "keyed:roster",
        "backtest": "excluded:backtest runs never bank",
        "alpaca_snapshot": "keyed:alpaca",
        "frozen_profile": "keyed:fact_sheet",
        "bank": "excluded:the key itself",
    },
    "build_room_messages": {
        "agent_id": "excluded:the desk",
        "mandate": "keyed:mandate",
        "user_id": "keyed:brief (the Brief overlay) and journal (Bull/Bear history)",
        "ticker": "keyed:ticker",
        "profile": "keyed:fact_sheet",
        "transcript": "excluded:the Room's own output",
        "portfolio_snapshot": "keyed:portfolio and alpaca (price-times-holding drift excluded)",
        "plan": "keyed:journal (the lookback window) and tier (the model tier it picks)",
        "trade_proposal": "excluded:derived from the mandate and the frozen sheet's price",
        "halal_universe": "keyed:universe",
        "classification_universe": "keyed:universe",
        "locale_allowed_universe": "excluded:always None in production",
        "portfolio_value": "excluded:price times holding",
        "parallel_phase": "excluded:phase constant",
        "sector_weights": "excluded:holdings times price; the holdings are keyed",
        "agent_size_pct": "excluded:derived from the mandate",
        "current_drawdown_pct": "excluded:price times holding",
        "existing_open_risk_pct": "excluded:price times holding; the lots are keyed",
        "last_loss_closed_at": "keyed:portfolio (trade history)",
        "trade_open_timestamps": "keyed:portfolio (trade history)",
        "option_candidates": "excluded:derived from the mandate and the frozen sheet",
        "option_spot": "excluded:derived from the frozen sheet",
        "prior_convene": "excluded:the previous Room is the bank's own output",
        "cards_envelope": "keyed:policy (room_cards_envelope_enabled)",
        "evidence_gate": "excluded:derived from the transcript and keyed policy settings",
    },
}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def trading_date_for(now: datetime, ticker: str | None = None) -> date:
    """The session date `now` belongs to in the ticker's market (US by default;
    see `session_calendar` and `market_calendar`). Raises `CalendarUnavailable`
    for a market whose holiday table does not reach `now`."""
    if ticker is None or market_for(ticker) is Market.US:
        return last_us_session_date(now)
    return market_trading_date(market_for(ticker), now)


def mandate_digest(mandate: Mandate) -> str:
    """Hash of the mandate's content: every field except plan state, the
    version counter and timestamps."""
    data = mandate.model_dump(mode="json", exclude=set(MANDATE_KEY_EXCLUDED))
    # CR284: the floor the verdict was judged against, not just the raw field —
    # an unset floor follows risk_score through a table, so a retuned default (or
    # a changed score) must re-key a Room that a stored value alone would not.
    data["effective_min_reward_risk"] = resolved_min_reward_risk(
        mandate.risk_score, mandate.min_reward_risk
    )
    # CR285: the two debt-check numbers, as the check resolves them (the horizon default
    # follows `horizon`, the coverage default follows `risk_score`). They only exist for a Room
    # graded under `ROOM_GRADER_LING_TERMINAL=v2`; under v1 they are dropped so every banked key
    # stays byte-identical until that switch, which re-keys everything through the policy anyway.
    from app.core.config import settings

    data.pop("debt_horizon_months", None)
    data.pop("min_debt_coverage", None)
    if settings.room_grader_ling_terminal == "v2":
        data["effective_debt_horizon_months"] = resolved_debt_horizon_months(
            mandate.horizon, mandate.debt_horizon_months
        )
        data["effective_min_debt_coverage"] = resolved_min_debt_coverage(
            mandate.risk_score, mandate.min_debt_coverage
        )
    return _sha256(_canonical(data))


def policy_version() -> str | None:
    """The Room's policy generation: the derived prompt version of every agent
    that has one, plus `ROOM_POLICY_REVISION`. None when no prompt version can be
    computed at all, in which case the caller must not bank."""
    from app.services.prompt_version import prompt_version

    versions = {a.value: prompt_version(a) for a in AgentId}
    if not any(versions.values()):
        return None
    from app.core.config import settings

    parts: dict[str, Any] = {
        "revision": ROOM_POLICY_REVISION,
        "prompts": versions,
        "settings": policy_settings(),
    }
    if settings.room_coded_rule_enabled:
        parts["coded_rule"] = coded_rule_identity()
    return _sha256(_canonical(parts))[:16]


def coded_rule_identity() -> dict[str, str]:
    """Grader name + version + rule version + question-set version + ladder, so a
    rule, grader or question-set change re-keys Rooms (WP-23)."""
    from app.core.config import settings
    from app.services import room_decision_rule as rule
    from app.services.room_grader_registry import resolve_grader

    try:
        grader = resolve_grader(settings.room_grader)
    except Exception:  # noqa: BLE001 — an unbuildable grader must still key the Room
        grader = None
    name = grader.name if grader is not None else "unconfigured"
    version = grader.version if grader is not None else ""
    try:
        policy = rule.policy_for(settings.room_coded_rule_policy_json, name)
        return {"policy": rule.policy_version(name, version, policy)}
    except rule.PolicyConfigError:
        return {"policy": f"{name}@{version}|rule={rule.RULE_VERSION}|ladder=invalid"}


def policy_settings() -> dict[str, Any]:
    """The current value of every global setting that changes a Room's content."""
    from app.core.config import settings

    return {name: getattr(settings, name) for name in sorted(ROOM_POLICY_SETTINGS)}


#: Bumped when the way a Bursa sheet is rendered or built changes in a way a frozen
#: `.KL` sheet cannot absorb (DEF533). It is part of the variant for `.KL` only, so
#: a new Room rebuilds the day's sheet and re-keys the bank; US keys are untouched.
#: 4 = the Malay Mail news feed (CR282 lane E2) changed the News sheet.
#: 5 = the sheet carries `macro_cpi_note` for Macro & Events' coded note (DEF546).
#: 6 = the sheet carries the Bursa PN17/GN3 status line and note (CR286).
#: 7 = the PN17 line states Bursa's own "Last updated" date and the issuer's trading status (CR286 follow-up).
MY_SHEET_REVISION = 7


def sheet_variant(
    *, news_state: str, social_state: str, market_withheld: bool, ticker: str | None = None,
) -> str:
    """What may legitimately differ between two users' sheets for one ticker on
    one day. The sheet a user gets depends on which live feeds they were
    entitled to and on whether the Market desk is pulled back."""
    variant = f"news={news_state}|social={social_state}|market={'withheld' if market_withheld else 'present'}"
    if ticker and market_for(ticker) is Market.MY:
        variant += f"|my_rev={MY_SHEET_REVISION}"
        # CR282 lane E2 — the Malay Mail feed changes the News sheet, so a Room built
        # while it is on must not reuse one banked while it was off (or the reverse).
        from app.core.config import settings

        if settings.my_news_rss_enabled:
            variant += "|my_news=on"
    return variant


@dataclass(frozen=True)
class FrozenSheet:
    profile: dict[str, Any]
    # None when the sheet could not be frozen (a value the codec cannot encode,
    # or the store was unreachable): the Room still runs on `profile`, unbanked.
    sheet_hash: str | None
    trading_date: date
    variant: str


def freeze_fact_sheet(
    *,
    ticker: str,
    trading_date: date,
    variant: str,
    build: Callable[[], dict[str, Any]],
) -> FrozenSheet:
    """The stored sheet for (ticker, trading_date, variant), building and storing
    it on the first call. Concurrent first calls converge on one stored sheet:
    the loser of the unique constraint re-reads the winner's row."""
    sym = ticker.upper()
    existing = _read_sheet(sym, trading_date, variant)
    if existing is not None:
        return FrozenSheet(decode_profile(existing[0]), existing[1], trading_date, variant)

    profile = build()
    try:
        encoded = encode_profile(profile)
        canonical = _canonical(encoded)
    except (TypeError, ValueError) as exc:
        logger.error(
            "room_fact_sheet_not_freezable",
            ticker=sym,
            trading_date=trading_date.isoformat(),
            error=str(exc)[:300],
            detail="the Room runs on a fresh sheet and is not banked",
        )
        return FrozenSheet(profile, None, trading_date, variant)

    sheet_hash = _sha256(canonical)
    with get_session() as s:
        claimed = claim(
            s,
            RoomFactSheetRow,
            key={"ticker": sym, "trading_date": trading_date, "variant": variant},
            values={"sheet": json.loads(canonical), "sheet_hash": sheet_hash},
        )
        stored, stored_hash = claimed.row.sheet, claimed.row.sheet_hash
    if not claimed.created:
        logger.info(
            "room_fact_sheet_race_lost",
            ticker=sym, trading_date=trading_date.isoformat(), outcome="read the winner's sheet",
        )
    return FrozenSheet(decode_profile(stored), stored_hash, trading_date, variant)


def _read_sheet(
    ticker: str, trading_date: date, variant: str,
) -> tuple[dict[str, Any], str] | None:
    with get_session() as s:
        row = s.execute(
            select(RoomFactSheetRow)
            .where(RoomFactSheetRow.ticker == ticker)
            .where(RoomFactSheetRow.trading_date == trading_date)
            .where(RoomFactSheetRow.variant == variant)
        ).scalar_one_or_none()
        return (row.sheet, row.sheet_hash) if row is not None else None


def _digest(value: Any) -> str:
    return _sha256(_canonical(value))


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None


def _side(trade: Any) -> Any:
    side = getattr(trade, "side", None)
    return getattr(side, "value", side)


def portfolio_digest(portfolio: Any, trades: list[Any]) -> str:
    """Hash of the user's sim portfolio as the Room reads it. `portfolio` is a
    `Portfolio`, `trades` the user's full `SimTrade` history (open and closed)."""
    def _rows(rows: list[list[Any]]) -> list[list[Any]]:
        return sorted(rows, key=_canonical)

    data = {
        "cash": int(round(float(portfolio.current_cash))),
        "holdings": _rows([[h.ticker, h.quantity, h.avg_cost] for h in portfolio.holdings]),
        "shorts": _rows([[s.ticker, s.quantity, s.entry_price] for s in portfolio.shorts]),
        "options": _rows([[o.occ_symbol, o.quantity, o.avg_premium] for o in portfolio.options]),
        "open_lots": _rows([
            [t.ticker, _side(t), t.quantity, t.entry_price, t.stop]
            for t in trades if t.status == "open"
        ]),
        "history": _rows([
            [_iso(t.opened_at), _side(t), t.status, _iso(t.closed_at)]
            for t in trades
        ]),
    }
    return _digest(data)


def journal_digest(entries: list[Any], *, limit: int = 5) -> str:
    """Hash of the Decision Journal entries the Bull/Bear desks read for a
    ticker: the latest `limit` that are not Room-run entries. `entries` must be
    newest-first, as `JournalStore.list_for_user` returns them."""
    kept = [
        e for e in entries
        if getattr(e.entry_type, "value", e.entry_type) != "room_run"
    ][:limit]
    return _digest([
        [
            str(e.id), e.title, getattr(e.outcome, "value", e.outcome),
            e.summary, e.user_note,
        ]
        for e in kept
    ])


def alpaca_digest(payload: Any | None) -> str:
    """Hash of a linked Alpaca paper account as the device reported it: cash to
    whole dollars and each position's symbol and quantity. "none" when no
    account is linked."""
    if payload is None:
        return "none"
    return _digest({
        "cash": int(round(float(payload.cash))),
        "positions": sorted(
            ([p.symbol, p.qty] for p in payload.positions), key=_canonical,
        ),
    })


def brief_digest(overlays: dict[str, str | None]) -> str:
    """Hash of the Brief overlay each desk's prompt renders. `overlays` maps an
    agent id to its active overlay content (None when it has none). Content is
    stripped, and blank counts as none, exactly as the prompt builder treats it."""
    return _digest({
        agent: (text or "").strip()
        for agent, text in sorted(overlays.items())
        if (text or "").strip()
    })


def universe_digest(halal: Any, classification: Any, ticker: str) -> str:
    """Hash of the sourced compliance verdicts the Room reads for `ticker`: the
    Sharia verdict, each exclusion kind, liquidity (status only: the live-price
    leg is price drift), and each snapshot's stale flag.

    Not the snapshots' as-of dates (DEF517): they advance with every daily
    refresh whatever the user did, so keying them re-priced every banked Room
    once a day even when no verdict for this ticker had moved. A verdict that
    does move changes its status; a snapshot gone stale changes both its
    statuses and the flag."""
    from app.schemas.classification import ClassificationKind

    def _status(verdict: Any) -> Any:
        return getattr(verdict.status, "value", verdict.status)

    t = ticker.upper().strip()
    # CR282 lane D: a `.KL` ticker's halal state (and staleness) is its own market's.
    halal = halal.for_ticker(t) if hasattr(halal, "for_ticker") else halal
    return _digest({
        "halal": [
            _status(halal.resolve(t)), bool(halal.stale),
        ],
        "classification": {
            "kinds": {
                kind.value: _status(classification.resolve(t, kind))
                for kind in ClassificationKind
            },
            "liquidity": _status(classification.resolve_liquidity(t)),
            "stale": bool(classification.stale),
        },
    })


def tier_digest(plan: Any) -> str:
    """The model tier `pick_tier` assigns `plan` for every desk the Room runs (the
    twelve desks and the Risk Officer). Ruled 2026-11-21: a plan change is a changed
    input even where a single-model provider makes the tiers equivalent."""
    from app.services.tier_policy import pick_tier

    return _digest({
        a.value: pick_tier(plan, a) for a in (*TWELVE_AGENT_IDS, AgentId.RISK_OFFICER)
    })


def roster_digest(withheld: Any) -> str:
    """Which analyst desks the plan and tenure withheld from this Room."""
    return ",".join(sorted(getattr(a, "value", str(a)) for a in withheld)) or "none"


def key_parts(
    *,
    user_id: UUID,
    ticker: str,
    mandate: Mandate,
    sheet_hash: str,
    policy: str,
    model_root: str,
    trading_date: date,
    portfolio: str,
    journal: str,
    alpaca: str,
    brief: str,
    universe: str,
    roster: str,
    tier: str,
) -> dict[str, str]:
    return {
        "user_id": str(user_id),
        "ticker": ticker.upper(),
        "mandate": mandate_digest(mandate),
        "fact_sheet": sheet_hash,
        "policy": policy,
        "model_root": model_root,
        "portfolio": portfolio,
        "journal": journal,
        "alpaca": alpaca,
        "brief": brief,
        "universe": universe,
        "roster": roster,
        "tier": tier,
        # Hashed in its own right: a new trading day is a changed input even if
        # a sheet's content happened to come out identical.
        "trading_date": trading_date.isoformat(),
    }


_HASHED_PARTS = (
    "user_id", "ticker", "mandate", "fact_sheet", "policy", "model_root", "trading_date",
    "portfolio", "journal", "alpaca", "brief", "universe", "roster", "tier",
)

# Parts added after the first Rooms were banked: a Room banked before them has no
# such entry in `bank_inputs`, and re-keying it (a backup-slot restart) must not
# raise. Its key can then never equal a new convene's, which is the right outcome.
_LATE_PARTS = frozenset({"brief", "universe", "roster", "tier"})


def key_from_parts(parts: dict[str, str]) -> str:
    return _sha256(_canonical({
        k: (parts.get(k, "") if k in _LATE_PARTS else parts[k]) for k in _HASHED_PARTS
    }))


def with_model_root(parts: dict[str, str], model_root: str) -> tuple[str, dict[str, str]]:
    """The key and parts for the same Room under a different model: a Room
    restarted on the backup slot is keyed by the backup's root, never the
    primary's."""
    new = {**parts, "model_root": model_root}
    return key_from_parts(new), new


@dataclass(frozen=True)
class BankedRoom:
    run_id: UUID
    finished_at: datetime | None
    running: bool
    # Only meaningful while `running`: whether a process is plausibly still
    # executing it (not marked interrupted, started inside the running window).
    live: bool = True


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None or dt.tzinfo is not None:
        return dt
    return dt.replace(tzinfo=timezone.utc)


def find_banked_room(key: str, *, running_cutoff: datetime) -> BankedRoom | None:
    """The Room holding `key`: a finished one (hand it over) or a running one
    (reattach to it). Failed, cancelled and outage Rooms hold no key.

    A `running` row that no process is executing (marked interrupted, or older
    than `running_cutoff`) is reported `live=False` so the caller releases its
    key instead of attaching to a dead Room."""
    with get_session() as s:
        row = s.execute(
            select(RoomRunRow).where(RoomRunRow.bank_key == key)
        ).scalar_one_or_none()
        if row is None:
            return None
        if row.status == "running":
            started = _aware(row.started_at)
            live = row.interrupted_at is None and (
                started is not None and started >= running_cutoff
            )
            return BankedRoom(row.id, None, True, live)
        if row.status == "completed" and row.verdict is not None:
            return BankedRoom(row.id, _aware(row.finished_at), False)
        return None


def release_key(run_id: UUID) -> None:
    """Drop a Room's key so the same inputs can start a fresh one."""
    with get_session() as s:
        row = s.get(RoomRunRow, run_id)
        if row is not None:
            row.bank_key = None
    logger.warning("room_bank_key_released", run_id=str(run_id))
