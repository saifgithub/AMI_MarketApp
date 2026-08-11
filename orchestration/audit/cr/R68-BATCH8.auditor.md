<!--
R68-BATCH8.auditor.md — audit lane. State derives from round numbers here vs R68-BATCH8.architect.md.
-->

# R68-BATCH8 — audit (auditor → architect)

## VERDICT: COMPLETE (round 2)

0 MAJOR, 0 BLOCKER. Both round-1 MAJORs reproduced fixed, each verified by
re-applying the original mutation/reproduction to the round-2 code.

Audited fix SHA `b6b17044` in the shared worktree
`.claude/worktrees/audit-R68-B4-9-r2-u66` (DEF159).

---

## MAJOR 1 — evaluative outcome with no bound — reproduced fixed, mutation re-run

`_horizon_coherence_note` (`room_runner.py:1203`) no longer asserts an
outcome — no "weeks-to-months instrument", "ordinary volatility", or "would
take the position out" anywhere in the function. It states the two numbers
and their tension: *"the exit is set N% below entry — the position closes on
a N% move against it, whenever that comes, so the M-day thesis is only
testable if the price never travels that far the wrong way in the
meantime."* Matches the sibling annotator's DEF240 standard, read directly.

Re-applied round 1's own MUT-5 (`stop_pct = 6.0`, hardcoded) to the current
code and re-ran `test_cr156_def239_def255_pm_verdict.py`: **4 failures** —
`test_the_stop_clause_states_the_pairing_and_predicts_nothing` plus three of
the four `test_the_printed_distance_is_the_real_one` parametrizations (1.9%,
15.8%, 90.0% — the 6.0% case is indistinguishable from the mutant by
construction). Matches "a hardcoded distance now fails four tests" exactly.
Reverted, worktree clean.

## MAJOR 2 — retracted sentence survived in `agent_prompts.py` — reproduced fixed

`agent_prompts.py:77-78`'s docstring no longer claims the floor "always
dominates instruction ordering for the PM" — replaced with the DEF267 note
explaining why position doesn't imply dominance in the Room, with the actual
composition (`system_prompt = base + room_addition`, floor at char 4,979 of
11,023) stated where the false claim used to be.

The new pin (`test_no_code_docstring_still_claims_the_floor_dominates_by_
position`) reads the SOURCE FILE directly, not the spec doc — exactly what
round 1 flagged as missing (the old pin only checked `safety_floor.md`).
Ran it clean, then reinserted the exact retracted sentence into the
docstring and re-ran: fails. Reverted, clean.

## Suite

Run once for all six R68-BATCH4–9 round-2 verdicts, at the shared fix HEAD
(`57c37fdc`, `b6b17044` is an ancestor) — cited in R68-BATCH9's verdict file.

## What I did not chase

Round 1's four MINORs: MINOR 3 (CR156 B vocabulary sweep not exhaustive) and
MINOR 4 (1-on-1 PM's REJECT unreconciled) are explicitly acknowledged in
round 2 as accepted-not-fixed, correctly scoped to CR156 Tier B. MINOR 1
(the note's "every input"/"Nothing on the fact sheet" oversells what it
enumerates — forward P/E, analyst consensus, and next-earnings EPS all exist
on the sheet and aren't named) and MINOR 2 (the note evaluates the PM's
possibly-AMI-defaulted `stop`, not `stop_raw`) are both unchanged — checked
directly (`room_runner.py:1412` still passes `stop`, not `stop_raw`) — and
round 2 doesn't claim otherwise. Both remain accurately MINOR: round 1 held
MINOR 2 there specifically on zero live incidence (`level_provenance->>'stop'
= 'pm'` in all 25 sampled approvals), a fact this round doesn't change.
