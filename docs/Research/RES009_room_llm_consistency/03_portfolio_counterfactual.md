# 03 — Portfolio counterfactual: does holdings state change the verdict?

## Method

`backend/scripts/ibm_cash_only_rerun.py` drives a **real, full 12-agent Room
convene** — not a prompt replay, an actual fresh call through
`RoomRunner.run()` — with the user's portfolio, sector context, and trade history
monkeypatched to a clean-slate "$10,000, all cash, no positions, no trade history"
state at the module level (`app.services.room_runner._build_sim_holdings_block` /
`_build_room_sector_context` / `_build_room_risk_limit_context`), rebinding the
same three functions the test suite already patches for exactly this purpose
(`backend/tests/unit/test_cr055_room_holdings.py`,
`backend/tests/unit/test_def136_room_convene_does_not_block_loop.py`). No DB write
ever touches a real user's `SimPortfolioRow`/`SimTradeRow` — the monkeypatch
intercepts the read before it reaches `get_session()`.

Run against a synthetic `user_id` (not a real user) — Saiful's explicit choice when
the same test against a real user's identity was flagged as a genuinely different,
higher-risk action than a prompt replay. Real production LLM wiring
(`get_llm_gateway()`), and calling `RoomRunner.run()` directly (not `start_run()`)
means this is credit-free by construction — `spend()`/`refund()` only exist on the
`start_run()`/API path. Result: `room_run_id=96ca4774-7599-4d0d-be36-39d1864aabfe`,
a real row in `room_runs`. Full transcript + verdict:
[`out/03_cash_only_counterfactual.json`](out/03_cash_only_counterfactual.json).

## Result

**Verdict: PASS, 0/5 approve votes** — identical action to both original runs
(Run A and Run B, both real-holdings, both PASS/0-votes).

The reasoning text cites the same fact-sheet numbers as the two real runs (6.2%
FCF yield, 1% TTM revenue growth, −160bps operating margin YoY, 26 days to Q4
earnings) and reaches the same risk/reward conclusion (unfavorable asymmetry ahead
of a binary earnings event). Holdings state visibly changed *framing* in a couple
of agents' narrative (a real-holdings run mentions "preserve the $X cash and
existing $Y portfolio"; the cash-only run has no such line to make), but did not
change the trading call.

## Read

For this ticker, at this moment, portfolio state is not what is driving the
verdict — the underlying market facts (earnings risk, weak growth, margin
compression) are doing the work, and the PM's decision is stable to a
counterfactual that zeroes out the one variable (holdings) that differs most
between real users. This is a useful, if narrow, robustness check: it rules out
"different users get different verdicts because of their portfolios" as an
explanation for anything observed elsewhere in this investigation.
