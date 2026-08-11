<!--
R68-BATCH6.auditor.md — audit lane. State derives from round numbers here vs R68-BATCH6.architect.md.
-->

# R68-BATCH6 — audit (auditor → architect)

## VERDICT: COMPLETE (round 2)

0 MAJOR, 0 BLOCKER. All three round-1 MAJORs accepted and addressed — one by
retraction (corrected, independently re-derived, holds), two by code fix
(both reproduced fixed, mutation-verified). One new MINOR: the fix for MAJOR
3 is correct on direct read but has no test pinning it — reverting it causes
zero failures anywhere in the suite.

Audited fix SHA `b6b17044` in the shared worktree
`.claude/worktrees/audit-R68-B4-9-r2-u66` (DEF159; two additional throwaway
worktrees at `350c5ae2` (BATCH6's parent) and `19cb0e3c` (BATCH6's original,
pre-fix submission) for the byte-count re-derivation, both reaped after use).

---

## MAJOR 1 — byte-cost retraction — independently re-derived, holds

Built a realistic profile (the test fixture's `profile`, plus the
`sma_short`/`sma_long`/`volume_ratio`/`market_cap`/`free_cash_flow`/
`total_debt` fields production always sets alongside `technicals: "live"` —
exactly the fields round 1 found missing from the original mismeasurement)
and rendered it through `_format_profile` in two fresh worktrees: BATCH6's
parent (`350c5ae2`) and BATCH6's original pre-fix submission (`19cb0e3c`).

```
                    FULL   fundamentals  market  news  social
agree    (mine)     +262   +148          +182    +0    +0
agree    (claimed)  +266   +152          +182    +0    +0
diverge  (mine)     +450   +336          +370    +189  +189
diverge  (claimed)  +456   +342          +372    +190  +190
```

Market lane exact match in the agree case; every other cell within single
digits, attributable to different numeric field values in my synthetic
fixture (different digit counts on `sma_short`/`market_cap`/etc. than
whatever the retraction used) rather than a real disagreement. The retraction
holds: the original +141/+84/+57/+0/+0 claim was wrong, the corrected
+266..+456 range is right, market is the largest lane not the smallest, and
news/social's "+0" in the original claim was MAJOR 2's leak wearing a
measurement, not a real zero.

## MAJOR 2 — the leak, and the second instance it found — reproduced fixed

`_reference_price_line`'s reconciliation clause is now gated on
`technicals_live and _in_lane("technicals")` (`room_prompts.py:1083`, the
function itself takes a plain `technicals_live: bool` at `:1345` — the
lane-gating is applied at the call site). Ran
`test_a_firewalled_analyst_never_gets_the_last_close_even_when_prices_diverge`
and `test_an_in_lane_agent_still_gets_the_reconciliation` clean, both pass.

The second instance (`_week52_line`'s anchor silently pulling `last_close`
into the Fundamentals sheet through a dual-lane line) is fixed via
`_price_anchor(profile, technicals_in_lane=...)` threaded through
`_week52_line` (`:1421`) and called with `technicals_in_lane=_in_lane
("technicals")` (`:1147`). Verified empirically — a firewalled
`FUNDAMENTALS_ANALYST` with diverging prices now gets *"from the reference
price $189.31"* on its 52-week line, not *"from the last close"*. Reverted
`_price_anchor`'s call site back to the unqualified form and re-ran the full
`cr145`/`cr150`/`cr146`/`room_prompts`/`prompt_data_parity` slice: 1 failure
(`test_a_firewalled_analyst_sees_only_its_own_lane[fundamentals_analyst]`) —
caught, via the widened `_DOMAIN_FINGERPRINTS["technicals"]` list picking up
"last close" now included in the fingerprint table, not a dedicated new test.
Reverted, worktree clean.

## MAJOR 3 — anchor-name hardcoding fixed, but genuinely unpinned (new MINOR)

`_moving_average_line` now prints `name` (`room_prompts.py:1452`) instead of
the literal `"last close"`, read directly and correct.

**Mutation-reverted to confirm coverage, and there is none.** Reverted the
line back to the hardcoded string and ran every test file touching this
renderer (`cr145`, `cr150`, `cr146`, `room_prompts`, plus a keyword sweep for
"anchor"): **138 passed, 0 failed.** Nothing in the suite exercises the
scenario this line's fix matters for.

Why: `_moving_average_line` only renders inside the
`elif technicals_live:` branch, which is itself inside `if not
_in_lane("technicals"): pass` — i.e. it is *only ever called for an agent
that already has technicals in lane*. The round-2 text's framing ("the
fallback is now reachable in production" because the anchor is lane-aware)
describes `_price_anchor`'s OTHER caller (`_week52_line`, dual-lane, genuinely
reachable via MAJOR 2's fix) — it doesn't describe this call site, which
still only reaches the pre-existing "technicals live, `last_close` absent"
edge case round 1 called latent and non-production-reachable. That framing
in the round-2 text is loose, not wrong about the fix itself.

**MINOR — round 1's own stated fix direction was two things ("`_name` plus a
test that keeps technicals live and drops `last_close`") and round 2 shipped
one.** The code is right on direct read; it just isn't protected. Flagging
for the record, not gating: the scenario remains latent by the same
reasoning round 1 used to explain why it graded MAJOR despite being
unreachable today (the submission's own verification claim, not live risk).

## Suite

Run once for all six R68-BATCH4–9 round-2 verdicts, at the shared fix HEAD
(`57c37fdc`, `b6b17044` is an ancestor) — cited in R68-BATCH9's verdict file.

## What I did not chase

The four round-1 MINORs (market-cap reaching 9/12 not 12/12 agents, the
rounding straddling the $500M threshold, the unsigned negative-FCF rendering,
and the unguarded new negative-capability claim) are not addressed in round 2
and round 2 doesn't claim they are — correctly out of scope for a
MAJOR-focused round-2 response.
