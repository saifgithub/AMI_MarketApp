# M06 — Risk/reward ratio

**Origin:** CR046 MODE-A audit finding F2 (AT:R62) · **Status:** done

## What
The reward-to-risk ratio (the "R" in "R:R = R:1") of a long setup, computed from its entry, stop, and
target — so the Trader states a ratio that actually matches its own levels instead of asserting one
the LLM made up. Plus a coherence check a caller can use to flag a *stated* R:R that contradicts the
levels.

## The problem this fixed
In the scripted path the ratio was computed inline (`(target−entry)/max(0.01, entry−stop)`); in the
live path the Trader LLM invented entry/stop/target **and** the R:R with nothing checking that
`(target−entry)/(entry−stop)` equalled the stated ratio. A Trader could assert "R:R = 3:1" while its
own levels implied 1.5:1, and the PM verdict's stop/target carried an implied R:R nothing recomputed.

## Formula
- `risk_reward(entry, stop, target) = (target − entry) / (entry − stop)`, 1 dp. Long setups only —
  returns None unless both the reward (target > entry) and the risk (stop < entry) are positive.
- `trade_asymmetry` (M08) is the sibling percentage view.
- `rr_is_coherent(entry, stop, target, stated_rr, tol=0.3)` — True only when the implied ratio and a
  stated ratio both exist and differ by ≤ tol; a missing stated ratio or an incoherent setup is not
  coherent (never a silent pass).

## Source data
The Trader's / PM's own entry, stop, target price levels.

## Consumed by
Trader (emits it — scripted render now library-computed). `rr_is_coherent` is wired into the **live
PM verdict path**: on every PM APPROVE, `room_runner._pm_rr_coherence_signal` extracts any R:R the PM
narrated in prose and, when it contradicts the approved entry/stop/target, logs the structural signal
`room_pm_rr_incoherent` (flag only — the safety floor owns vetoes). Research Manager, Risk Debators
read the ratio downstream from the transcript.

## Computed in
`app/trading_math/trade.py::risk_reward` / `rr_is_coherent`. Wired into the Room scripted formatter
and the PM APPROVE branch (`room_runner.py::_pm_rr_coherence_signal`, `_extract_stated_rr`).

## Guard test
`tests/unit/test_trading_math.py` — `risk_reward` on a known setup (100/94/113 → 2.2), rejection of
non-long setups, and `rr_is_coherent` flagging a stated 3:1 against levels that imply 2.2:1.
`tests/unit/test_room_runner.py::test_pm_rr_incoherent_narration_produces_a_signal` (+ degenerate-
levels and coherent/silent cases) — the wired behaviour: incoherent narration → signal payload.

## Changelog
- 2026-07-21 (CR046, AT:R62): created from audit finding F2. Scripted R:R now library-computed; the
  live Trader's free-prose R:R remains its own words (a verdict-contract change to force structured
  Trader output is logged in the CR046 backlog), but the coherence check now exists to validate it.
- 2026-07-21 (CR046, AT:R62): **wired the previously-dead `rr_is_coherent`.** A verification pass found
  it defined + tested but with zero app callers. Chose (a) WIRE IT over (b) delete: the PM APPROVE
  branch now extracts a narrated R:R from PM prose (`_extract_stated_rr`, precision-biased regex) and
  logs `room_pm_rr_incoherent` when it disagrees with the approved levels — telemetry, never a veto.
  No dead code remains.
