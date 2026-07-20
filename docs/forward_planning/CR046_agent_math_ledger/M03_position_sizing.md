# M03 — Position sizing (per-risk-tier cap + absolute backstop)

**Origin:** pre-existing scatter, reconciled by CR046 (AT:R62) · **Status:** done

## What
The single-name position-size cap by risk tier, and the flat absolute single-name ceiling. This is
the calc that made the CR's whole thesis concrete: **the number an agent is shown must equal the
number the system enforces.**

## The incoherence this fixed
Sizing was defined three different, mutually-inconsistent ways:

| Where | What it was | Values |
|-------|-------------|--------|
| `overlay_generator._max_position_pct` | what the **Trader is told** (narration) | 5 / 10 / 15 / 25 / 40 by risk 1–5 |
| `room_runner._risk_tier_size_ceiling` | what the **PM is clamped to** (enforcement) | 1.5 / 1.5 / 3.0 / 4.5 / 4.5 |
| `safety_floor.SINGLE_NAME_CAP_PCT` | flat compliance **backstop** | 50 |

A risk-5 user's Trader was told "up to 40% per name", proposed 40%, and the system silently clamped
to 4.5% — a ~9× gap between shown and enforced.

## Formula / policy
- `DEFAULT_RISK_TIER_CAPS = {1: 1.5, 2: 1.5, 3: 3.0, 4: 4.5, 5: 4.5}` — AMI's live enforced policy
  (exactly the values the PM already clamped to, so **no enforced behaviour changed** — only the
  Trader's narration was corrected from a false 40% to the true 4.5%).
- `risk_tier_cap(risk_score, caps=None)` — table-driven, total (clamps out-of-range scores).
- `SINGLE_NAME_ABSOLUTE_CAP_PCT = 50.0` — every tier cap ≤ this.
- `clamp_size(proposed, cap)` — clamp a proposed size down to its cap.

Reusability: the numbers are **product policy**, not universal math — another project passes its own
`caps` table to `risk_tier_cap`.

## Consumed by
Trader (overlay narration), Portfolio Manager (verdict clamp + pre-debate display sizes), safety
floor (compliance backstop).

## Computed in
`app/trading_math/sizing.py`. The three call sites now delegate to it.

## Guard test
`tests/unit/test_position_sizing.py` — the **coherence guard**: for every risk tier, what the Trader
is *told* (`_max_position_pct`) equals what the PM *clamps to* (`_risk_tier_size_ceiling`), and both
≤ the absolute backstop. Verified **red** against the pre-fix values (40 ≠ 4.5 on all 5 tiers).
`tests/unit/test_trading_math.py` covers the library functions. This is the enforcing check for
failure-patterns **P5**.

## Changelog
- 2026-07-20 (CR046, AT:R62): three divergent scales reconciled into one canonical source; coherence
  guard added. Canonical scale chosen = the enforced 1.5/3.0/4.5 (correcting the lie, not the
  enforcement). **Open for Saiful:** if the *enforced* caps themselves should be higher, that's a
  position-sizing policy change (a new changelog line here), not a bug.
