"""price_alert_evaluator — CR027 §4. Evaluates active price alerts on a
5-minute background tick and fires `notification_service.notify()` for
each breach — the first automated consumer of that shared write path.

One price fetch per ticker (not per alert). Never fires on missing price
data (a fetch failure just skips that ticker for this cycle — the next
tick is the retry, no backoff loop needed). A fire is an atomic
conditional UPDATE (`WHERE status='active'`), which is the actual
duplicate-fire guard — not just "the Python loop only saw ACTIVE rows" —
so an overlapping cycle or a concurrent user cancel can never double-fire.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update

from app.agents.safety_floor import check_mandate_compliance
from app.core.logging import logger
from app.db import get_session, init_schema
from app.db.models import PriceAlertRow
from app.schemas import Mandate
from app.schemas.agents import AgentId
from app.schemas.trade import OrderType, ProposedTrade, Side
from app.services.agent_prompts import build_agent_prompt
from app.services.classification_universe import default_classification_universe_async
from app.services.entitlements import effective_plan_for_user
from app.services.llm_gateway import ChatMessage, get_llm_gateway
from app.services.mandate_store import get_mandate_store
from app.services.market_data import get_market_data_provider
from app.services.notification_service import notify
from app.services.sharia_universe import default_halal_universe_async
from app.services.tier_policy import pick_tier

_COMMENTARY_MAX_CHARS = 280

_COMMENTARY_FRAMING = {
    "stop": "risk-management framing — this is a downside stop breach",
    "manual_below": "risk-management framing — this is a downside breach",
    "target": "profit-taking framing — this is an upside target breach",
    "manual_above": "profit-taking framing — this is an upside breach",
}


@dataclass(frozen=True)
class _AlertSnapshot:
    id: UUID
    user_id: UUID
    ticker: str
    threshold_type: str
    threshold_price: float
    trade_ref: UUID | None


def _threshold_breached(threshold_type: str, price: float, threshold: float) -> bool:
    if threshold_type in ("stop", "manual_below"):
        return price < threshold
    if threshold_type in ("target", "manual_above"):
        return price > threshold
    return False


def _implies_short_entry(alert: _AlertSnapshot, mandate: Mandate) -> bool:
    """Best-effort heuristic, not a discovered existing check — long_only
    enforcement is delegated elsewhere in this codebase (`safety_floor.py`'s
    own step 3 is a documented no-op for sells) and needs real holdings
    context this loop doesn't cheaply have. Only the one alert shape
    CR027's own doc names as plausibly implying a short entry under a
    long-only mandate: a manual downside-breakout watch with nothing
    linked to protect.
    """
    return (
        mandate.compliance.long_only
        and alert.trade_ref is None
        and alert.threshold_type == "manual_below"
    )


def _alert_mandate_check(alert: _AlertSnapshot, mandate: Mandate, halal_universe, classification_universe):
    """Ticker-eligibility-only reuse of check_mandate_compliance. Framed as
    a zero-context SELL so every position-sizing/cooldown/max-positions/
    open-risk branch (each gated on `proposed.is_buy`) never engages;
    `trade_open_timestamps=[]` (not None) dodges the one branch — the
    over-trading brake — that isn't is_buy-gated, since an empty list can
    never manufacture a false block (0 is never >= a real per-day/week
    cap). Only allowlist/blocklist/halal/classification/locale run.
    """
    proposed = ProposedTrade(
        ticker=alert.ticker, side=Side.SELL, quantity=1, order_type=OrderType.MARKET,
    )
    return check_mandate_compliance(
        proposed,
        portfolio_value=0.0,
        current_drawdown_pct=0.0,
        mandate=mandate,
        halal_universe=halal_universe,
        classification_universe=classification_universe,
        trade_open_timestamps=[],
    )


async def generate_alert_commentary(alert: _AlertSnapshot, current_price: float, mandate: Mandate) -> str:
    """Portfolio Manager-sourced commentary — not the "Risk Analyst" the
    original design named, which doesn't exist in the 13-agent roster
    (same fabricated-citation root cause CR026 already corrected once).
    LLM failure never blocks the fire — falls back to a short template.
    """
    framing = _COMMENTARY_FRAMING.get(alert.threshold_type, "neutral framing")
    fallback = f"{alert.ticker} crossed your {alert.threshold_type} level of ${alert.threshold_price:.2f}."
    try:
        system_prompt = build_agent_prompt(
            AgentId.PORTFOLIO_MANAGER, mandate, user_id=alert.user_id, ticker=alert.ticker,
        )
        user_msg = (
            f"{alert.ticker} just crossed the user's {alert.threshold_type} alert level of "
            f"${alert.threshold_price:.2f} (current price ${current_price:.2f}). Write ONE short "
            f"push-notification line, plain text, no markdown, under 240 characters, with {framing}. "
            f"This is a notification, not a new trade proposal."
        )
        plan = effective_plan_for_user(alert.user_id)
        tier = pick_tier(plan, AgentId.PORTFOLIO_MANAGER)
        chunks: list[str] = []
        async for chunk in get_llm_gateway().stream_chat(
            system_prompt=system_prompt,
            messages=[ChatMessage(role="user", content=user_msg)],
            model_tier=tier,
            max_tokens=200,
            audit_user_id=alert.user_id,
            audit_agent_id=AgentId.PORTFOLIO_MANAGER.value,
            audit_flow="price_alert",
        ):
            chunks.append(chunk)
        text = "".join(chunks).strip()
    except Exception:
        logger.exception("price_alert_commentary_failed", alert_id=str(alert.id))
        text = ""
    return (text or fallback)[:_COMMENTARY_MAX_CHARS]


def _fire_alert(alert_id: UUID, commentary: str) -> bool:
    with get_session() as s:
        result = s.execute(
            update(PriceAlertRow)
            .where(PriceAlertRow.id == alert_id, PriceAlertRow.status == "active")
            .values(status="fired", fired_at=datetime.now(timezone.utc), agent_commentary=commentary)
        )
        return (result.rowcount or 0) > 0


def _fetch_active_alerts_by_ticker() -> dict[str, list[_AlertSnapshot]]:
    init_schema()
    grouped: dict[str, list[_AlertSnapshot]] = {}
    with get_session() as s:
        rows = s.execute(
            select(PriceAlertRow).where(PriceAlertRow.status == "active")
        ).scalars().all()
        for row in rows:
            grouped.setdefault(row.ticker, []).append(_AlertSnapshot(
                id=row.id, user_id=row.user_id, ticker=row.ticker,
                threshold_type=row.threshold_type,
                threshold_price=float(row.threshold_price),
                trade_ref=row.trade_ref,
            ))
    return grouped


async def evaluate_price_alerts() -> dict[str, int]:
    stats = {
        "tickers": 0, "alerts_evaluated": 0, "fired": 0,
        "skipped_price_error": 0, "mandate_blocked": 0, "errors": 0,
    }
    grouped = _fetch_active_alerts_by_ticker()
    if not grouped:
        return stats
    stats["tickers"] = len(grouped)

    halal_universe = await default_halal_universe_async()
    classification_universe = await default_classification_universe_async()
    provider = get_market_data_provider()

    for ticker, alerts in grouped.items():
        stats["alerts_evaluated"] += len(alerts)
        try:
            # Real network I/O (Yahoo/mock) — must not block the shared
            # event loop this tick runs on (DEF116/DEF120 class).
            quote = await asyncio.to_thread(provider.quote, ticker)
        except Exception:
            logger.exception("price_alert_quote_error", ticker=ticker)
            quote = None
        if quote is None:
            stats["skipped_price_error"] += len(alerts)
            logger.warning(
                "price_alert_quote_unavailable", ticker=ticker, alert_count=len(alerts),
            )
            continue

        for alert in alerts:
            try:
                if not _threshold_breached(alert.threshold_type, quote.price, alert.threshold_price):
                    continue

                mandate = get_mandate_store().get_or_default(alert.user_id)
                compliance = _alert_mandate_check(alert, mandate, halal_universe, classification_universe)
                if not compliance.passed or _implies_short_entry(alert, mandate):
                    stats["mandate_blocked"] += 1
                    logger.warning(
                        "price_alert_mandate_blocked",
                        alert_id=str(alert.id), user_id=str(alert.user_id),
                        ticker=ticker, violations=compliance.violations,
                    )
                    continue

                commentary = await generate_alert_commentary(alert, quote.price, mandate)
                if not _fire_alert(alert.id, commentary):
                    continue  # raced with another tick/user cancel — not an error
                stats["fired"] += 1
                # Real network I/O (OneSignal, up to 10s timeout) — to_thread
                # for the same reason as the quote fetch above.
                await asyncio.to_thread(
                    notify, alert.user_id, "price_alert", f"Price Alert: {ticker}",
                    commentary, {"route": "open_holding_detail", "ticker": ticker},
                    str(alert.id),
                )
            except Exception:
                stats["errors"] += 1
                logger.exception(
                    "price_alert_evaluation_error", alert_id=str(alert.id), ticker=ticker,
                )

    return stats
