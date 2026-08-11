<!--
R68-BATCH7.architect.md — architect submission lane. State derives from round numbers here vs
R68-BATCH7.auditor.md.
GATE: none was used while building. Batch 7 of the CR143 prompt + data-feed remediation programme
(one handshake PER BATCH, Saiful 2026-08-11).
-->

# R68-BATCH7 — audit lane (CR153 B ≡ CR154 B ≡ CR155 C ≡ CR156 C · DEF241 residue)

**SHA:** `e7efd472` (`main`, pushed to origin)
**SCOPE:** chunk — one deduped tier across four CRs, plus a recorded deferral. All four CRs stay
`in_progress`; **DEF241 stays `open` on purpose.**
**depends-on:** R68-BATCH1 (`0ef2893f`, COMPLETE r1) — hard gate: this batch ADDS prompt bytes, and
Batch 1 is what made the output contract satisfiable. R68-BATCH5/6 awaiting.

**Batches 7 and 8 share one commit.** Both touch `room_prompts.py` and `room_runner.py`, so
splitting them would need partial-file staging and would risk committing a broken intermediate
state. Two lanes, one SHA, each scoped to its own items — stated here rather than papered over with
two SHAs that would not mean what they appear to.

**Item:** render the risk state. **The only batch in this programme that supplies genuinely new
information** rather than rendering something already fetched or subtracting something unusable.
Prompt bytes change ⇒ **CR142 Tier A**.

---

## What was wrong

Four CRs filed the same finding against four different agents. CR156 states the dedupe rule, so this
ships **once** into the shared mandate snapshot rather than four times.

The snapshot carried only the **limits** — `max_drawdown_pct: 20`, the single-name cap — and never
the **consumption**. So every agent argued about how much risk to add while blind to how much was
already spent, which makes "sized against the cap" literally unanswerable: **3% more is prudent at
2% drawdown and reckless at 19%.**

The numbers were not missing. They had been on `_RoomContext` since CR101-BE2 threaded them for the
safety floor, and they reached **no prompt at all**.

## What ships

`_risk_state_block`, rendered into every agent's mandate snapshot:

- **Drawdown USED** and the **headroom remaining** — *"size against the headroom, not against the
  cap"*. The cap alone was never the actionable number.
- **Open risk already committed**, labelled *"across open positions carrying a stop"*.
- **Last stop-out**, and the count of recently-opened trades (the pace an over-trading limit counts).
- **Per-position stops** in `_build_sim_holdings_block`.

**Deliberately NOT phase-gated**, unlike `trade_proposal`: the consumption figures are real at every
phase, and all four source CRs filed this against a *different* agent — a gate would just recreate
the gap for whoever fell outside it.

### The absences are the batch's real risk

Three of them, and the lazy implementation renders `0.0` for all three — wrong in the **most
dangerous direction**, telling the Room the book is flat when the computation actually failed.

| input | renders as |
|---|---|
| `CONTEXT_NOT_SUPPLIED` | *"COULD NOT BE COMPUTED — treat it as unknown, not as zero"* |
| `None` (caller supplied nothing) | **nothing** — never a fabricated zero |
| a real `0.0` | *"Open risk already committed: 0.0%"*, stated as fact |

`CONTEXT_NOT_SUPPLIED`, `0.0`, `None` and `[]` are **all falsy**, so a single `if not value` would
collapse every one of them into one branch. `test_the_sentinel_is_not_confused_with_a_falsy_value`
asserts the three renderings are mutually distinct — that is the test that would catch the mistake.

**Open risk carries a qualifier because the figure is partial.** `_risk_limit_context` sums only
positions carrying a stop, so an unqualified *"open risk 4.2%"* reads as complete when the book may
hold unstopped positions the number cannot see. The holdings block now names those individually.

### Per-position stops (CR040)

Multiple lots **list** their stops rather than averaging them — a mean of two stops is a level nobody
set, and minting one is the DEF235 class. An unstopped lot renders *"NO stop recorded (this position
is unprotected)"*, never silence: before this, the holdings block stated size and unrealised P&L and
said nothing about protection, so a Room reasoning about open risk could not tell a fully-stopped
book from a naked one.

## DEF241 residue — reviewed and DEFERRED, and the row stays open

`proposal = trade_proposal if phase in ("RISK","VERDICT") else None` still leaves `bull_researcher`
and `research_manager` byte-identical to pre-fix. Batch 7 considered widening it and **did not**, for
a structural reason:

At RESEARCHERS and SYNTHESIS **the Trader has not spoken, so there is no proposal.** Any figure would
be minted from an invented stop and read as a measurement — the DEF235 class. **CR151 already
adjudicated exactly this and rejected it** (its rejected item 2: extending the deterministic
reference position to SYNTHESIS *"would hand the RM a drawdown-contribution figure derived from a
−6% stop nobody proposed, labelled as a reference and read as a measurement"*).

What those two phases actually lacked was the **consumption**, and `_risk_state_block` gives it to
them ungated. That is the half that is real, and it shipped.

**DEF241 does not close on this batch.** Its row's own rule is that a re-scope must not pass as a
fix. The deferral is pinned by `test_the_researchers_still_get_no_worked_contribution_figure` so a
later reader finds a decision, not an oversight.

## Verification

- `backend/tests/unit/test_cr153_risk_state_in_prompt.py` — **21 tests**.
- **The call site, not just the builder.** `test_the_runner_actually_threads_the_risk_state` drives
  the real `RoomRunner.run()` and asserts every agent's prompt carries the block. This is not
  decoration: DEF241's mutation proof showed MUT-1/MUT-2 die **only** under a real run, because every
  other test passes the kwarg itself and therefore proves the builder while saying nothing about the
  caller — the exact blind spot that let **DEF238** ship a PM-only feature that never worked once in
  production while its tests passed for the feature's entire life.
- Full shared-checkout suite at `e7efd472`: **3408 passed, 1 skipped**, 521.94s.

## What is NOT claimed

- **Whether agents actually size against the headroom is unmeasured.** Supplying the number is the
  necessary half; a post-promotion batch is the sufficient one.
- **This batch adds prompt bytes to all twelve agents**, including the eight full-sheet ones that
  clipped in DEF258. Unlike Batch 6, this is genuinely new content rather than a few derived figures.
  The post-promotion re-measure must re-check the cap-hit rate.
- CR152 C and CR150 A4–A6 were listed for this batch in the plan and are **not** here — they are
  separate render items, not part of the deduped risk-state tier, and lumping them in would have made
  one audit cover two unrelated changes.
- The safety floor is untouched. It reads `ctx` directly and never this string.

---

**SUBMITTED: round 1**
