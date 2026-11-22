# CR244 Part 2 — Room agent feeds: status and plan (AT:B1, 2026-11-22)

Plan only. Nothing here is built by this lane.

## Already shipped (verified against HEAD of `beta/cr267`)

1. Recent-filings index to Macro & Events (`news`) and Fundamentals lanes: `room_recent_filings_enabled` (default **False**, `config.py:1268`), rendered once in `room_prompts.py` (~3577). Filings are a PIT-windowed index, dates and form types only.
2. Insider ratio, 10b5-1 plan tag and cluster-buy flag reach the `news` lane and full-sheet agents: CR247 Phase 1D, flags ON since 2026-09-29 (`room_insider_*`, `config.py:1350-1352`), live-only (90-day SEC read, no historical store).

## Remaining: float and liquidity

| Data | Desk | Hook |
|---|---|---|
| `floatShares`, `sharesOutstanding`, float/outstanding ratio, average dollar volume | Execution Desk (`trader`) | Stop-size slippage and gap risk on a thin float |
| Float, insider and institutional ownership concentration | Conservative Risk Officer | Overhang and liquidity tail risk |

Reference implementation: `docs/tools/room_investigation_V2/library/data_feeds/float_liquidity.py` (live-verified NVDA, CROX). The Company Review `ownership` section already reads the same yfinance fields, so the Room should read the cached profile, not a second fetch.

Build, per the CR221 five-point pattern:

1. Extract float/liquidity onto the profile overlay in `company_profile.py` (state `live` / `not_available` with a reason, never imputed).
2. `field_state` key `float_liquidity`.
3. Lane-gated header disclosure bullet in `_format_profile`.
4. Lane-gated body line for `trader` and the Conservative Risk Officer only, rendered in code (AMI-computed figures, the LLM never computes one).
5. One persona sentence in each of the two `content/agents/*.md` `## Inputs` sections; update the anti-fabrication guards `test_agent_prompts.py:61` and `test_cr219_availability_guard.py:528-537`.

## WP-24 bank key obligation

Any new Room input must be classified, or the bank test fails and a stale banked Room replays across a data change:

1. Add the new setting (`room_float_liquidity_enabled`) to `ROOM_POLICY_SETTINGS` in `room_bank.py` (alongside `room_recent_filings_enabled`, line 139), so flipping it moves the policy version.
2. Add any new parameter of `RoomStartRequest`, `RoomRunner.start_run` or `RoomRunner.run` to `ROOM_INPUT_CLASSES` (`room_bank.py:174`) as `keyed:<part>` or `excluded:<why>`. A profile-overlay field read from the cached profile adds no parameter, so the setting entry is the whole obligation.
3. Float moves slowly, so the fetched figures themselves are not keyed; confirm that stance against the bank's `as_of`/trading-day key before build.

## Decisions for Saiful before build

1. Flip `room_recent_filings_enabled` to True? It is off, so the shipped filings feed is dark in the Room today (degrade-loudly: dark by default is a conscious choice, not a gap).
2. Float/liquidity to two desks only (new body line scoped to them), or to all full-sheet agents as insider data does (CR244 D2)?
