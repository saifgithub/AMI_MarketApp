#!/usr/bin/env python3
"""Rerun a real IBM Room convene for a real user with the portfolio forced to
100% cash / no open positions — a what-if that ignores the user's actual
current holdings.

Follow-up to `ibm_room_divergence_probe.py` and `ibm_temperature_sweep.py`.
Those showed that most of the divergence between the two 2026-09-25 IBM runs
traced to each user's real mandate + real portfolio state (holdings, drawdown,
sector exposure). This script isolates the portfolio variable: same user,
same mandate, same ticker, but a synthetic "just opened the account, all
cash" portfolio in place of their real one, so their real holdings (and any
sector/risk-history baggage) can't leak into the reasoning.

Seam: `_build_sim_holdings_block` / `_build_room_sector_context` /
`_build_room_risk_limit_context` in `app.services.room_runner` are module-
level function references that `RoomRunner.run()` calls by name — the same
pattern already used by `tests/unit/test_cr055_room_holdings.py` and
`tests/unit/test_def136_room_convene_does_not_block_loop.py`. Rebinding them
on the imported module intercepts the read BEFORE it reaches the DB, so the
user's actual `SimPortfolioRow`/`SimTradeRow` are never touched — no DB write
to their real portfolio happens anywhere in this script.

Cost: calling `RoomRunner.run()` directly (not `start_run()`, which is the
`POST /v1/room/stream` path) never calls `spend()`/`refund()` — those only
live in `start_run()`. This run is credit-free by construction. It DOES still
write one real row to `room_runs` for this user_id/ticker (the run/verdict
record itself, via `_persist_run`) — that's the diagnostic's own record, left
in place deliberately so its output is inspectable the same way as the
original two runs, via the same `llm_audit`/`room_runs` tables.

Must run where `DATABASE_URL` points at melehost's Postgres (see
ibm_room_divergence_probe.py's docstring for why) and where the real vLLM
gateway is reachable (production wiring, not a test stub).

Usage:
    python3 -m scripts.ibm_cash_only_rerun --user-id <uuid> --ticker IBM \\
        --out /tmp/ibm_cash_only_rerun.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from uuid import UUID

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _install_cash_only_seam(ticker: str) -> None:
    """Rebind the three portfolio/risk-history readers `RoomRunner.run()` calls
    by module-level name, so every agent's prompt sees a brand-new, all-cash
    account instead of the user's real holdings/trade history. Text matches
    the genuinely-empty-portfolio branch of the real `_build_sim_holdings_block`
    verbatim (room_runner.py ~line 1919) so this isn't a new/different format
    the agents haven't seen before — just a different (synthetic) fact.
    """
    from app.services import room_runner as rr_mod

    ticker_u = ticker.upper()

    def _cash_only_holdings_block(user_id, tkr):  # noqa: ANN001 — matches original signature
        tkr_u = tkr.upper()
        return (
            f"{rr_mod._SIM_PORTFOLIO_HEADER}\n"
            f"Cash: $10,000.00 | Portfolio value: $10,000.00\n"
            f"Open positions: none — you hold nothing yet. You hold 0% of {tkr_u}. "
            f"Any BUY here opens a NEW position.\n"
            f"───"
        )

    def _cash_only_sector_context(user_id):  # noqa: ANN001
        # Real value, not the "not supplied" sentinel — an honestly-empty book
        # (`holdings=[]`), matching what `_build_sim_holdings_block` above claims.
        # `None` here would mean "couldn't read it", which is false: we know
        # exactly what this counterfactual portfolio holds (nothing).
        return [], {}, None, {}

    def _cash_only_risk_limit_context(user_id, *, portfolio_value, quotes):  # noqa: ANN001
        # (last_loss_closed_at, trade_open_timestamps, existing_open_risk_pct)
        # — a real "no history" value, not CONTEXT_NOT_SUPPLIED.
        return None, [], 0.0

    rr_mod._build_sim_holdings_block = _cash_only_holdings_block
    rr_mod._build_room_sector_context = _cash_only_sector_context
    rr_mod._build_room_risk_limit_context = _cash_only_risk_limit_context


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user-id", required=True, help="real user_id whose MANDATE to use (portfolio is overridden)")
    ap.add_argument("--ticker", default="IBM")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    _install_cash_only_seam(args.ticker)

    from app.services.llm_gateway import get_llm_gateway
    from app.services.mandate_store import resolve_mandate
    from app.services.room_runner import RoomRunner

    user_id = UUID(args.user_id)
    mandate = resolve_mandate(user_id, None)  # real stored mandate, read-only
    runner = RoomRunner(llm=get_llm_gateway())  # real production LLM wiring

    # RoomEvent.kind: 'started'|'live_data_notice'|'phase'|'agent_token'
    # |'agent_done'|'agent_withheld'|'verdict'|'error' (room_runner.py:4953).
    # agent_token carries the streamed text deltas; agent_done carries only
    # stance/conviction/headline, not the full text. Rather than reassemble
    # per-agent text from token deltas here, this script just drives the run
    # to completion and records phase/run_id/verdict — the full per-agent
    # text is read back afterward from `room_runs.transcript` (persisted by
    # `_persist_run`) the same way the original two runs were inspected via
    # `ibm_room_divergence_probe.py`, so both are comparable apples-to-apples.
    events = []
    verdict = None
    run_id = None
    async for ev in runner.run(user_id=user_id, ticker=args.ticker, mandate=mandate):
        if ev.run_id is not None:
            run_id = str(ev.run_id)
        if ev.kind in ("phase", "agent_done", "agent_withheld", "error", "verdict"):
            events.append({
                "kind": ev.kind, "phase": ev.phase, "agent_id": ev.agent_id,
                "stance": ev.stance, "conviction": ev.conviction, "headline": ev.headline,
            })
        if ev.kind == "verdict" and ev.verdict is not None:
            verdict = ev.verdict.model_dump() if hasattr(ev.verdict, "model_dump") else ev.verdict

    result = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "user_id": args.user_id,
        "ticker": args.ticker,
        "portfolio_override": "100% cash, no open positions, no trade history",
        "room_run_id": run_id,
        "event_count": len(events),
        "events": events,
        "verdict": verdict,
    }
    with open(args.out, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"Wrote {args.out} ({len(events)} events) — room_run_id={run_id}")
    print("Read full per-agent transcript with:")
    print(f"  SELECT transcript, verdict FROM room_runs WHERE id = '{run_id}';")


if __name__ == "__main__":
    asyncio.run(main())
