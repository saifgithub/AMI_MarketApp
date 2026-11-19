# CR260 — Analyst price targets in the Room

**Status:** in_progress (backend built 2026-10-19, AT:K3 — not yet promoted;
mobile render of `verdict.analyst_view` pending) · **Date:** 2026-10-18 · **Track:** AT:K3

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
with source attribution. Every count renders WITH its label ("6 strong
buy / 19 buy / …"), never as a bare positional sequence — the agent-side
line sets the wording precedent, and a stacked-bar mobile render carries a
keyed legend for the same reason. The action tape rows may render as recent-analyst-
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

---

## 7. WP-21b re-scope: the Street comparison after the verdict (AT:B1, 2026-11-19)

CR267 WP-21b re-scopes this CR to the display. CR275 (WP-21a) made the Room decide
blind: every `analyst_*` field is stripped from every agent input
(`street_view_blind.blind_profile`), while the profile keeps them for post-verdict
code. Sections 1–6 above describe the source and the fetch; this section is what
the user sees and how it is kept out of the Room.

**What the verdict payload carried before.** `Verdict.analyst_view`
(`schemas/room.py` `AnalystView`, built by `room_runner._analyst_view_from_profile`
at `_stamp_next_convene_basis`): rating, mean/median/high/low target, opinion count,
rating split, newest tape rows. No comparison with the Room's call, no source label,
no as-of. Mobile did not render it. It is unchanged.

**What WP-21b adds.** `Verdict.street_comparison` (`StreetComparison`), built by
`services/street_comparison.build_street_comparison` at the same single bank site,
after the verdict exists:

1. Street rating (the feed's word and a buy/hold/sell bucket), analyst count, mean
   target, as-of (the fact-sheet date), the Room's action and stance.
2. `agreement`: `agree` / `differ` / `not_comparable` (NO_VERDICT).
   Street Buy: APPROVE agrees, PASS/REJECT differs. Street Hold or Sell:
   PASS/REJECT agrees, APPROVE differs.
3. `approved_against_street_sell`: the Room approved a Sell/Underperform name. This
   is the one pairing counted as an error. A reasoned PASS on a Street-Buy name
   differs but is not flagged.
4. `source_label`: "Yahoo Finance via yfinance: sell-side analyst consensus"
   (`STREET_SOURCE_LABEL`; a source swap changes this one constant). Always present,
   including when unavailable. Public release needs a licensed source (CR007).
5. Missing data: `status="unavailable"` with a reason (`no_rating`,
   `unrecognised_rating`, `no_analysts`, `comparison_error`); every Street field is
   null. Never an empty or zero rating. A zero target is dropped.
6. `reasons_from_narrow_answers`: empty list. It is filled by WP-22's
   narrow-question judge, which does not exist yet. Nothing invents reasons.

**Kept out of the Room.** Computed only from the finished verdict plus the profile,
which it does not mutate. `tests/unit/test_cr260_street_comparison.py` builds every
agent prompt after the stamp and asserts none carries the comparison, and a static
fence fails if any module other than the schema, the builder, the provenance table
and the runner's import and stamp line names it.

**Mobile.** `RoomStreetCard` under the verdict ("How the Street rates it"), shown
when the server sent a comparison and the Settings switch is on; also on Journal
replays. The setting (`streetComparisonEnabledProvider`, key
`ami_street_comparison_enabled`) defaults ON: Beta plan §3a.3 says the rating is
"shown to Beta testers after the verdict, with a source label, behind a setting",
so testers see it unless they turn it off. Source label always visible; missing
data reads "No Street rating available for this run."

**Tests.** Backend `test_cr260_street_comparison.py`; widget
`mobile/test/widgets/room_street_comparison_test.dart`; UAT-ROOM-023 (API) and
UAT-ROOM-024 (device checklist, taps only).

**Open.** Not promoted to Alpha. WP-21b acceptance ("a Room on Alpha shows the
comparison after the verdict") needs the promotion and a live Room. AR/MS strings
are seeded English marked `retranslate:[ar,ms]`.
