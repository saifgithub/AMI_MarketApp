<!-- intake handoff from the Room-quality lane (AT:R59). CR105 amended + DEF129 filed; need laning. -->
# room-quality — CR105 (amended, descoped) + DEF129

PROPOSED-KIND: CR ×1 (**CR105**, already minted by track K, amended today) + Defect ×1
(**DEF129**, minted here — register regenerated; re-verify no collision at pickup, IDs move)
SOURCE: Saiful, 2026-07-28 — *"modify CR105 to deliver what is feasible and logical."*
TRIAGE: **READY-TO-LANE — both.** Same two files' worth of surface; batching into one worktree is
the obvious call.

## What changed and why it matters to whoever picks this up

CR105 was filed from a read of `content/agents/*.md`. Every item has now been re-checked against
**the code that reads the model's output**. Two of its four prompt edits sat on a live parser
contract. The amended CR is smaller, and the two removals are the important part of the hand-off —
if a lane "helpfully" does them anyway, it ships a regression with a green suite.

| Original finding | Disposition | The reason, in one line |
|---|---|---|
| 1 — PM verdict vocabulary | **prompt edit DROPPED**, doc half kept | The prohibition already ships closer to the model and is measurably ignored 31.7% of the time; the parser absorbs it at zero cost |
| 2 — Trader ticket / RM 3-part | **Trader DROPPED**, RM kept | `trader.md`'s `Entry:`/`Stop:`/`Target:`/`Size:` labels are what DEF095's `_LEVEL_PATTERNS` matches |
| 3 — unfulfillable instructions | kept | Delete, don't reword (CR038) |
| 4 — bare `50%` | kept + guard extended | Literal is currently *correct* (`sizing.py:26` = 50.0) — latent drift, not a live bug |
| 5 — stale docs | kept | `twelve_agents.md` contradicts `market_analyst.md` on MACD/Bollinger |
| 6 — anti-`MODIFY` copy-guard | **DROPPED** | Contradicts `test_room_prompt_parity.py:68`; would turn the suite red |
| 7 — alignment guard (was not in Scope) | **PROMOTED into Scope** | CR104's `field_state` makes it cheap; only item that prevents recurrence |
| Concierge claims | **SPLIT → DEF129** | Verified unwired *and* already fired on a real user |

## The measurement behind the biggest cut

`_PM_VERDICT_FORMAT` (`room_prompts.py:108-113`) — appended **last**, maximum recency — already
says *"Do NOT write 'MODIFY', 'MODIFY-AND-APPROVE' … they are discarded and your verdict is lost."*
Shipped with DEF067, `ea77bc5`, 2026-07-20 01:22 +0300.

`llm_audit`, `agent_id='portfolio_manager'`, strictly after that commit (7.8d, n=161), measured
2026-07-28: `pass` 101 · `approve` 41 · `modifyandapprove` 13 · `modify` 5 · `modifyapprove` 1.

**19 of 60 affirmative verdicts (31.7%) still emit a MODIFY-form.** All 19 parse correctly on the
first pass via `_PM_ACTION_SYNONYMS` — no reformatter, no loss. Editing the *more distant* base
prompt therefore has zero measurable upside and one concrete way to break a working guard.
`failure_patterns.md` P4 already rules on this: *"make the parser tolerant of everything any layer
offers."*

## Guardrails for the lane

- **Do not touch** `_PM_ACTION_SYNONYMS`, `_normalize_pm_action`, `_LEVEL_PATTERNS`,
  `test_room_prompt_parity.py`, or `trader.md`. Editing any of them means the lane has left scope —
  stop and re-file rather than proceeding.
- **A green suite is not acceptance for a prompt change.** CR105 items 1, 2 and 4 change
  assembled-prompt bytes; the acceptance requires a post-`/promote-to-alpha` re-run of the PM
  action-distribution query above over ≥50 live convenes. That is the P4 lesson verbatim: *"green
  tests, because no test builds the assembled prompt and checks it against the parser."*
- Both new guards (the extended cap-parity assertion, the analyst-inputs alignment guard) must be
  **demonstrated red** before they are accepted green — same discipline CR104's taint guard used.

## DEF129 in one paragraph

`content/agents/concierge.md:19-20` **and** `overlay_generator.py:484-485` both tell the Concierge
it can schedule briefings/reminders and mute/promote agents. `backend/app` has no scheduler, no
cron, no sender, **zero `mute` symbols**, and the Concierge has no tool layer at all.
`daily_briefing` is a mandate field echoed back at onboarding with nothing to deliver it. It has
already fired: 1 of 30 recorded Concierge turns told a real user *"Go to the **Agents** tab … Tap
the agent … **Mute** them (hide from the Room) or **Promote** them (boost priority in research)"* —
inventing the navigation path and the semantics, and opening by calling the absence *"by design."*
CR023 class on the product-help surface. Fix is deletion from **both** layers, ideally replaced by
an explicit negative in the style `market_analyst.md` / `social_media_analyst.md` already use.

## Suggested lanes

- `coder.api` (or `coder.room`) — CR105 + DEF129 together: `content/agents/*.md`,
  `overlay_generator.py`, three design docs, two test files. No production logic changes.
- Room-quality (me) — review the diff against the two dropped items, and re-run the PM
  action-distribution query after promotion. Not coding it.

## Audit rationale

**None required.** With the vocabulary edit and the Trader block removed, nothing here touches a
parser contract or the safety floor's inputs; the two new items are test-only. DEF129 is a
deletion of false copy. Architect review at merge is sufficient.

## Still outstanding from this lane (unrelated to the above)

- **DEF125** — flat `max_tokens=400` truncates the Research Manager mid-sentence in **66.1%** of
  convenes (bull 60.6%, bear 25.6%); the RM synthesis is the sole input to EXECUTION/RISK/VERDICT.
  Filed 2026-07-27, **still not laned.** Biggest unclaimed Room-quality win on the board.
- **CR104's true acceptance re-run** (DEF123's 178→0) needs a post-`/promote-to-alpha` measurement
  filtered to post-promotion timestamps. Saiful-gated.
