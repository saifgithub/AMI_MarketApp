# DEF103 — CR083 AR translation tooling corrupted 36 lesson files

**Status:** open · **Session:** AT:architect · **Date:** 2026-07-24 · **Class:** content · **Owner:** Language Manager (CR083)
**Spotted:** during the CR087 (lesson locale serving) build — the coder measured the corpus, the
independent auditor reproduced the split from scratch, and this scan pinned the exact files.

## What

Of the **312 tracked AR lesson bodies** (`content/lessons/*.ar.mdx`, committed `95ac1ba`/`85f20f7`),
**36 are structurally damaged** by the CR083 translation tooling and cannot be served — CR087's
serving-time integrity gate degrades each to the English body (logged, no user harm). So AR
**effective** coverage is **276/342 ≈ 81%**, not the 312/342 ≈ 91% the file count implies.

Two failure modes, both from the tooling breaking MDX/frontmatter around `<Lesson/>` tags, quiz
option arrays, and nested quotes:

### A. Parse failures (18) — the `.ar.mdx` won't parse at all (`parse_mdx` raises)
```
068_forex_fx_trading_scams          100_kelly_criterion_simplified      107_drawdown_recovery_at_scale
135_money_flow_index_vs_rsi         144_adx_di_plus_minus_crosses       188_net_debt_to_ebitda
189_interest_coverage_ratio         204_sixty_minute_rule               209_system_delusion_lucky_vs_skilled
213_explain_to_a_six_year_old       219_breakout_volume_profile         243_this_time_is_different_trap
244_bear_market_rallies             253_mandate_adjustments_by_regime   260_regulated_vs_unregulated_jurisdictions
261_clone_firm_contact_match_deep_dive  323_gdp_what_the_economy_measures  334_capstone_from_policy_to_portfolio
```

### B. Quiz-option emptying (18) — parses, but a quiz's options are `[]` (gate rejects: `option_count loc=0`)
```
119_failed_breakouts_bull_traps     120_breakout_retest_entry           121_pullback_depth_fibonacci_zones
156_debt_maturity_ladder            157_short_term_vs_long_term_debt    158_off_balance_sheet_liabilities
159_when_high_debt_is_ok            160_three_cash_flow_statements      161_capex_intensity_and_working_capital
180_tangible_book_vs_reported_book  182_pb_for_asset_light_businesses   183_high_roe_low_pb_buffett_framing
185_roe_vs_roic                     186_sustainable_roe_mean_reversion  187_roe_inflation_via_buybacks
249_vvix_and_iv_rv_divergence       252_regime_change_realtime_vs_hindsight  328_capstone_reading_the_macro_machine
```

## Why it matters
This is the CR040 degrade-loudly family, but the loud fallback already ships (CR087) — the harm is
**silent under-coverage**: a user in Arabic sees 66 English lessons (36 here + 30 never-translated),
and without this ticket the 36 look "translated" (the file exists) while serving English. It also
means the CR083 tooling has a **systematic bug** (all 18 quiz failures are the identical
`option_count=0` pattern) that will re-damage the next batch (335+, currently being authored) unless
fixed at the tool, not per-file.

## Fix (Language Manager / CR083)
1. **Root-cause the tooling** — the `translate_*_lan.py` path emptied quiz `options` and broke
   frontmatter/MDX around `<Lesson/>` tags + nested quotes. Fix the tool first (the 335+ batch is
   landing now and will inherit the same bug).
2. **Re-translate the 36** with the fixed tool; re-validate each **parses** and **passes the CR087
   serving gate** (`_locale_quiz_servable`: quiz count + option count + answer_index match EN, no
   empty option).
3. Optional guard: fold the gate into a corpus pytest over tracked AR files once the cohort clears,
   so a re-damaged file fails the build (mirrors DEF064/065 quiz invariants).

## Detection (for re-verification)
Enumerable any time from the loader logs (`lesson_locale_parse_failed`,
`lesson_locale_quiz_integrity_failed`) or by running `parse_mdx` + `_locale_quiz_servable` over the
tracked `*.ar.mdx` set (the scan that produced the lists above).

## Not a CR087 blocker
CR087 serves the 276 clean AR lessons correctly and degrades these 36 to EN gracefully. DEF103
restores the lost 36 to raise effective AR coverage toward the file count.
