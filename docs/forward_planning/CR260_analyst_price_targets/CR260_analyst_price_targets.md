# CR260 — Analyst price targets in the Room

**Status:** proposed · **Date:** 2026-10-18 · **Track:** AT:K3

> "Tell the users the target prices (buy and sell) announced by the internet
> market analysts of the tickers in the room they convened." — Saiful, 2026-10-18

---

## 1. What the user gets

Per convened ticker, the Room agents (and later the 1-on-1 surface) can cite:

1. **Consensus band** — current price vs. mean / median / high / low analyst
   price target ("Wall Street's buy/sell range: $215–$405, mean $329").
2. **Rating distribution** — strong-buy / buy / hold / sell / strong-sell
   counts, with the trailing 3-month history (shows momentum: sells dropping
   off, upgrades clustering).
3. **The action tape** — dated per-firm rows: *firm, to/from grade,
   Raises/Lowers/Maintains, prior → current PT* ("JP Morgan raised to $360
   from $340, 2026-10-12"). This is what makes "the analysts convened" real.

## 2. Source research (measured 2026-10-18)

| Source | Price targets? | Verdict |
|---|---|---|
| **yfinance (Yahoo)** | Full: band + counts + per-firm tape, free | **BUILD PATH** — already our provider |
| Alpha Vantage `OVERVIEW` | Mean + counts, snapshot only | Premium-only now (verified live on our free key: "This is a premium endpoint"); $49.99/mo+ |
| Finnhub | Counts free; PTs premium | $3,500/mo All-In-One, no middle tier — NO-GO |
| EODHD | Snapshot (rating + target + counts) | $59.99/mo; viable fallback |
| Benzinga | Consensus + full action tape, licensed | The production-licensing path; quote via contact form; Massive resells at $99/mo **individual-use-only** (not an in-app display license) |
| TipRanks | PTs with analyst track records | Consumer = dashboard/CSV, no API; enterprise unpriced |
| S&P Capital IQ (`sp_data` plugin) | **None exposed** | Estimates module = EPS/Revenue/EBITDA/CFO consensus only; no PT/recommendation items in any module. Great fundamentals depth, dead end for this feature. |

## 3. Measured basis (48/48 DESK_UNIVERSE, 2026-10-18)

- **Coverage: 100%** — every name returned band + counts + tape, zero errors.
- **Depth** — 23–63 analysts per name; 177–994 dated firm actions per ticker.
- **Material is already interesting** — ORCL mean PT +85% vs price; AAPL
  trading 4% *above* its mean PT; TSLA genuine disagreement (4/15/21, 4 sells);
  NVDA near-unanimous buy (10/49/2). Divergence IS the room debate.

## 4. Design

1. **New service** `backend/app/services/analyst_targets.py`, beside
   `fundamentals.py`. One fetch surface (e.g. `get_analyst_view(ticker)`) that
   internally pulls the three yfinance attributes; TTL cache (start: 6–24 h —
   PTs don't move intraday); gated on `settings.use_real_market_data` so tests
   stay deterministic.
2. **Injection points** — Room runner live-data payload per convened ticker
   (same path as the fundamentals overlay); 1-on-1 live-data block later.
3. **Degrade loudly (CR040)** — fetch failure → structlog ERROR + the block is
   omitted with disclosure; per-field absence dropped (DEF053 "absent beats
   meaningless"); NEVER a synthetic or stale-as-fresh number. Test-double seam
   matches `market_data`'s pattern.
4. **No new dependency** — yfinance 1.3.0 already ships. No new env settings
   in v1 (reuses `use_real_market_data`); if a separate gate is ever added it
   must be compose-forwarded (compose-parity gate).
5. **Source abstraction** — the service owns the yfinance call; a Benzinga
   swap later is a backend change only, invisible to prompts/app.
5. **LANE ASSIGNMENT (Saiful ruling 2026-10-18: lane-pure)** — the payload
   alone is not enough: `room_prompts._format_profile` withholds per lane
   (CR145 Tier C), so each new field needs an explicit domain tag.
   - **Split counts** (strong-buy/buy/hold/sell/strong-sell + 3-month
     history) → `fundamentals` domain → **Fundamentals Analyst** + all
     full-sheet agents. Sits beside the existing consensus line; same
     `suppress_analyst_consensus` ablation gate.
   - **Action tape** (dated per-firm rows: firm, grade change,
     Raises/Lowers/Maintains, prior→current PT) → `news` domain →
     **News Analyst** + all full-sheet agents. Rationale: upgrades/
     downgrades are dated *events* (the blueprint already routes
     `next_earnings` to news on the same "scheduled event" logic), and the
     News Analyst currently has the weakest numeric grounding of the four
     analysts. Bounded render (e.g. latest N=5 rows per ticker) to keep
     prompts compact.

## 5. User-facing delivery (Saiful ruling 2026-10-18)

The analyst data is NOT prompt-internal only — it must reach the user. The
SB/B/H/S/SS counts and the consensus attributes (mean/median/high/low price
target, analyst count, rating) are displayed to the customer as part of the
Room delivery (the rendered report/board the user reads after a Convene),
with source attribution. The action tape rows may render as recent-analyst-
action entries in the same delivery. Exact placement/copy is a mobile/UX
decision; the backend obligation is that these fields exist in the Room
result payload the delivery renders from — which makes the
`test_prompt_data_parity`-style guard (acceptance #2) a user-visible
correctness gate, not just a prompt one.

## 6. Licensing position

- yfinance/Yahoo scraping is the build + Alpha path — same source and same
  posture as the fundamentals overlay already displayed to users.
- The redistribution question (sell-side research is the firms' IP) is not
  settled by any source above; a **Benzinga free-trial request** (startup
  pricing + in-app display license) runs in parallel. Trial request is a
  business action, not a code dependency.

## 6. Acceptance

1. Unit tests on fixture data (cached shapes; absent-field dropping; gate off =
   no network).
2. `test_prompt_data_parity`-style guard: whatever renders in prompts exists in
   the payload schema.
3. Staging probe: all 48 DESK_UNIVERSE tickers return band + counts via the
   service (measured sweep already passed directly against yfinance).
4. Room prompt copy review — the numbers must be quotable without the model
   inventing analyst names (the payload carries real firm names from the tape).
