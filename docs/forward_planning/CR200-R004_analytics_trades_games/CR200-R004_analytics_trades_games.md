# CR200-R004 — Analytics: add trades + game-players series

**Date:** 2026-10-17 · **Status:** in_progress · **Track:** AT:K1
**Parent:** CR200 (Management Console) — extends the CR200 slice-1 ANALYTICS
module. Grouped sub-CR per the CR200-R### convention.

**Filed from:** Saiful, using the AMI Ops console (2026-10-17): *"analytics —
missing the number of trades done, number of users played games."*

## What

Two additions to the existing analytics surface, nothing else:

1. `services/admin_analytics.py::timeseries(days)` gains two per-day,
   zero-filled series:
   - `trades` — count of `sim_trades` bucketed by `opened_at`.
   - `game_players` — distinct `user_id` of `game_entries` bucketed by
     `entered_at` (a user entering two fields the same day counts once —
     "users who played", not entries).
2. `summary()` gains the matching all-time scalars: `total_trades`,
   `total_game_players`.
3. `api/admin_chart.py` series whitelist extended: `trades`, `game_players`
   (same Literal pattern; renderer untouched).
4. `infra/dify/admin-agent/tools-openapi.yaml`: chart enum + timeseries
   summary text updated; Dify tool provider re-imported after promotion.

## Why

The console answers "how is the app growing" (signups, actives) but not
"are people trading" or "are people playing" — the two core loops the
product is built around (CR046/CR054 sim trading, CR109 the Game). An
operator asking AMI Ops "how many trades this month?" gets nothing.

## Out of scope

- Trade P&L, notional, or win-rate series (a real-money-flavoured metric
  set that deserves its own CR, not a quick add).
- Per-game/per-ticker breakdowns (CR200-R001 covers ticker interest).
- Mobile surfaces.

## Acceptance

1. `timeseries` returns the two new series zero-filled over the window;
   game_players dedupes same-day re-entries by one user.
2. `summary` returns the two scalars.
3. `chart.svg?series=trades` and `?series=game_players` render (422 still
   on unknown series).
4. Existing series + summary fields unchanged (byte-level where pinned by
   tests).
5. `pytest backend/tests/unit/ -q` green on the touched files; Dify
   `ami_trade_admin` provider lists the updated chart enum after
   re-import; a live "trades last 30 days" question via AMI Ops returns a
   tool-shaped answer.
