<!--
R68-BATCH8.architect.md — architect submission lane. State derives from round numbers here vs
R68-BATCH8.auditor.md.
GATE: none was used while building. Batch 8 of the CR143 prompt + data-feed remediation programme
(one handshake PER BATCH, Saiful 2026-08-11).
-->

# R68-BATCH8 — audit lane (DEF239 · CR156 B · DEF255 · CR156 D)

**SHA:** `e7efd472` (`main`, pushed to origin)
**SCOPE:** chunk — the Portfolio Manager. DEF239 and DEF255 close; CR156 goes `in_progress`, not
`done`.
**depends-on:** R68-BATCH4 (`6b5fe052`, awaiting) — DEF239 and DEF258 touch the same function, and
two of this batch's four items were **found by Batch 4's measurement**, not by reading code.

**Batches 7 and 8 share one commit.** Both touch `room_prompts.py` and `room_runner.py`, so
splitting them would need partial-file staging and would risk committing a broken intermediate
state. Two lanes, one SHA, each scoped to its own items — stated here rather than papered over with
two SHAs that would not mean what they appear to.

**Item:** the one agent whose output is parsed into a structured `Verdict` and rendered on the
Verdict Board as the decision's justification. Prompt bytes change ⇒ **CR142 Tier A**.

---

## DEF239 — the rationale was read from one key

`_parse_pm_verdict` read `parsed.get("narration")` and nothing else, so a verdict whose prose arrived
under any other key published `_PM_NO_RATIONALE` — *"it wrote no rationale for the call"* — **over
real sentences**, on the surface CR106 renders as the justification.

`_pm_narration` now walks an **explicit allowlist**: `narration` first (the contracted key, so it
wins when several carry prose), then `narrational`, `rationale`, `reasoning`, `reason`,
`explanation`.

**`narrational` is not hypothetical.** It is what the model emitted on live Alpha, SLB,
`2026-08-11 11:27:36Z` — the same verdict that exposed DEF258. This defect had a real instance the
whole time; Batch 4's measurement is what surfaced it.

**Deliberately not a free-text scrape**, which is the faster and wrong fix: `_PM_NO_RATIONALE` exists
for genuinely unexplained decisions (DEF232), and scraping any string field would render
`{"ticker": "AAPL"}` as a defence — destroying the one signal that tells a user the decision was
never explained. Asserted in both directions, plus non-string values under a narration key.

## CR156 B — the vocabulary the REPLACES line left uncovered

`_PM_VERDICT_FORMAT` stated *"There are exactly two action values: APPROVE and PASS"* while the
Decision sequence **three lines above it** said REJECT, in both layers that carry one
(`portfolio_manager.md:27,32` and `overlay_generator.py:523,527`).

The parser always survived — `_normalize_pm_action` maps REJECT→PASS. **The user did not.** The wire
action colours the card; the prose is what they read. So a card marked PASS carried a narration
opening *"REJECT:"*. **Re-measured at 4 of 14 (28.6%)** on the 2026-08-11 post-promotion batch,
against the 6/18 CR156 was filed on.

Both layers now say PASS and name the rule that failed, and the REPLACES sentence was widened to
cover the **decision sequence**, not only the output block — so a later edit to either layer cannot
quietly reopen the gap.

### All three of Tier B's constraints held — checked, not assumed

1. **The MODIFY canary is green and UNEDITED.** `test_room_prompt_parity.py:68` asserts a MODIFY
   token survives in the assembled PM prompt, and its comment marks it a deliberate canary whose
   justification must be rewritten if it is ever changed. `MODIFY-AND-APPROVE` maps to APPROVE and
   was never the problem, so **only REJECT moved** — the canary needed no edit and no rewritten
   justification. That is the CR105 Amendment-1 trap avoided rather than paid.
2. **The `## Output format` block is kept.** `agent_runner.py` builds the PM's 1-on-1 prompt with no
   `_PM_VERDICT_FORMAT`, so that block is the only format instruction it has there; deleting it
   leaves the 1-on-1 PM un-formatted. A test pins its presence.
3. **`enforce_safety_floor` / `check_mandate_compliance` are untouched.** The floor is uncoachable by
   design and the sole vetoer; routing any of its flags into a verdict is out of scope by
   construction.

## DEF255 — the horizon and the stop must be the same trade

The PM emits `1095` — the `Horizon.LONG` label restated as a number — in **4 of 13 approvals**, while
the code's own fallback for the same field is **42 days**. A 26× disagreement inside one field, and
it is the number the stop is judged against.

**Two halves, because a prompt line is not a control (P2):**

- **The definition.** `horizon_days` is now stated as *"how long THIS trade needs to work out, not
  the user's investment horizon"*, anchored to the evidence actually supplied.
- **The control.** `_horizon_coherence_note` fires deterministically when a stated horizon exceeds
  `_MAX_EVIDENCED_HORIZON_DAYS = 365`. That boundary is **derived, not chosen** — 365 is the 52-week
  range, the longest-dated evidence on the sheet — and is stated as a boundary the *evidence*
  supports, **never as a rule about how long anyone should hold**, which would be advice.

When a stop is present the note names the pairing, which is the actual harm rather than the
untidiness: a 6%-below-entry stop is a weeks-to-months instrument, so over 1,095 days ordinary
volatility takes the position out long before the thesis can be judged.

**Flag, never veto.** The safety floor is the sole vetoer (DEF059); an incoherent horizon is a
reasoning flaw to disclose, not a mandate breach to block on — vetoing would discard a real verdict
over its arithmetic. Asserted: an APPROVE with a 1,095-day horizon still returns APPROVE and carries
the note in `verdict.reason`.

## CR156 D — the ordering claim was false on the surface that matters

`safety_floor.md` asserted *"By placing the safety floor last, we make it the dominant instruction."*

- **1-on-1: true.** `build_agent_prompt` ends with `append_safety_floor(...)`.
- **The Room: false.** `room_prompts.py` composes `system_prompt = base + room_addition`, and `base`
  is what already had the floor appended — so the entire CONVENE block (fact sheet, mandate snapshot,
  transcript, `_PM_VERDICT_FORMAT`, the turn instruction) renders **after** it. On the one surface
  where a verdict is parsed and acted on, the floor sits in the middle of the prompt.

**Documented, not reordered.** Reordering would put the JSON output contract before the transcript it
must summarise, and **ordering was never the control** — CR038 measured prompt-level instructions at
~30%, so *"it is last, therefore it wins"* is exactly the belief P2 forbids. `enforce_safety_floor()`
is the enforcement point and both the doc and the code now say so.

## Verification

- `backend/tests/unit/test_cr156_def239_def255_pm_verdict.py` — **20 tests**.
- Full shared-checkout suite at `e7efd472`: **3408 passed, 1 skipped**, 521.94s.

## What is NOT claimed

- **DEF231's direction-signal rate needs re-measuring**, because DEF239's fix **enlarges its input
  population**: verdicts that previously carried no readable narration now do.
- The REJECT-inside-PASS rate is a **response-side** figure. Removing the contradiction from three
  prompt layers is the necessary half; whether the PM stops writing "REJECT:" is the measurement, and
  P2 says a wording change is not a control — this one has no structural backstop, which is stated
  rather than glossed.
- **CR156 stays `in_progress`.** Tier C's three mandate figures beyond the risk state are not here.
- **A decision is owed by Saiful** (CR156 Tier B, "also here"): the classroom disclosure is currently
  a prompt instruction firing ~6% of the time *inside the justification field*. Either drop it from
  `SAFETY_FLOOR_BLOCK` and render it deterministically at the verdict surface — a new client string
  needing `retranslate:[ar,ms]` — or append it server-side after parse, putting a fixed sentence in
  every Journal row. Not decided here.
- The 811-row `pm_verdict_corpus.txt` re-run and the 5.6% re-derivation are **owed and not done**.

---

**SUBMITTED: round 1**
