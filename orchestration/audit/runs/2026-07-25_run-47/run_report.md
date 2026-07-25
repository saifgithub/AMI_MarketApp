<!--
Auditor run report — run-47 (2026-07-25, session auditor.core/track U). Round-1 audit of
CR055. Audited SHA b1d4077 on lane/CR055.coder.room. Verdict COMPLETE. Owner: AUDITOR.
-->

# run-47 (round 1) — CR055 real portfolio holdings in every Room prompt → COMPLETE

- **Auditor session:** auditor.core (track U), 2026-07-25. Companion fix to CR056 (audited
  earlier today): CR056 was the behavioural defence-in-depth, CR055 is the structural fix for the
  same incident.
- **Audited SHA:** `b1d4077`, tip of `lane/CR055.coder.room`. Feature code is `259c826`,
  byte-identical (`b1d4077` only fixes a cwd-fragile test path, confirmed via an empty
  `git diff 259c826 b1d4077 -- backend/app/`). Audited in a fresh isolated worktree
  `.claude/worktrees/audit-CR055/`.
- **The item:** always inject the user's real sim-sourced portfolio holdings into every Room
  agent's prompt — closing the SCHD incident where a brand-new user's Trader refused to buy,
  citing a fabricated 10–15% holding that didn't exist, because the only holdings block that
  existed was gated on a linked Alpaca account no new user has.
- **Gate:** independent — fixes an already-happened, measured production incident.
- **Verdict:** COMPLETE (round 1) — zero BLOCKER. One MAJOR + one MINOR, both test-coverage gaps
  on claims independently confirmed TRUE for the shipped code, not functional defects.

## Verification

### Reproduced independently

| Check | Result |
|---|---|
| Scope | 6 files, no touches to CR056's file or `sim_engine.py`/`trading_math`. |
| Full suite from repo root | 1130 passed — specifically re-ran from the repo root (not `backend/`), the exact cwd this lane's round-1 submission originally failed under before the architect caught and the coder fixed it. Independently confirmed the fix holds, not just claimed. |
| No residual Alpaca param | Grepped every `build_room_messages(` call site — zero pass `alpaca_snapshot=`. |
| `risk_tier_cap` shared, not re-implemented | One definition, three identical call sites across the codebase. |

### Three clean mutation-test catches

Disabling the loud-failure fallback, dropping the PM's own `portfolio_snapshot=` argument, and
widening the researcher-cap gate to all agents each broke exactly the test named to catch it, then
were reverted.

### Finding 1 (MAJOR) — the weight-matching test doesn't pin the sentence it claims to verify

`_build_sim_holdings_block` computes the discussed ticker's weight **twice** — once in the
per-position list line, once in the standalone "You currently hold X%" sentence (the direct
replacement for the exact sentence that failed in the real incident). Both read the same
underlying values so they're mathematically identical today. Mutated **only** the second formula
(×1.5) and the test **still passed**, because its assertion is a bare substring search that the
first (untouched, correct) occurrence satisfies. A regression in the specific sentence this whole
CR exists to fix would ship silently. Code is correct today; the guard isn't independent.
Recommended a one-line assertion tightening, not blocking.

### Finding 2 (MINOR) — zero test coverage for the Alpaca-overlay precedence claim

`_compose_portfolio_block` — the function implementing "sim is authoritative, Alpaca is a labelled
overlay" — is never referenced in the test file at all. Verified its behaviour myself by direct
invocation (correct: sim first, Alpaca clearly subordinate-labelled, `None` passthrough exact) —
not a live defect, but an untested code path for a named adversarial-focus claim. Lower stakes than
Finding 1 (Alpaca-linked users are a minority; the always-present sim block is what every user
sees).

## Findings

One MAJOR, one MINOR — both test-coverage/guard-precision gaps on claims independently confirmed
true for the delivered code, not functional defects in what shipped.

## Verdict

**VERDICT: COMPLETE (round 1)**
