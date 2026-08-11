<!--
R68-BATCH1.architect.md — architect submission lane. State derives from round numbers here vs
R68-BATCH1.auditor.md.
GATE: none was used while building. This is Batch 1 of the CR143 prompt + data-feed remediation
programme, whose governing decision (Saiful, 2026-08-11) is ONE handshake PER BATCH rather than
per item — batches are sized so a single handshake covers several fixes on the same surface.
The rationale is CR038: prompt changes fail silently, so independent review is the control that
catches them.
-->

# R68-BATCH1 — audit lane (DEF236 · DEF251 · DEF256, + CR154 Tiers A1/C)

> Round 1 submitted at `0ef2893f`; the live round line is at the foot of this file.

**SHA:** `0ef2893fbb26...` (`main`, pushed to origin — `git branch -r --contains 0ef2893f` → `origin/main`)
**SCOPE:** chunk — one batch of three defects on one surface, not any CR's definition-of-done.
**depends-on:** none. Batches 6, 7 and 9 of the programme depend on THIS one (see "Why first").

**Item:** the prose output contract every Room agent receives, and the two parser consequences of
changing it.

## What was wrong

**DEF236.** `_LENGTH_GUIDE` counted SENTENCES while `_PROSE_FORMAT`, five lines below it in the
same assembled string, asked for *"a one-sentence thesis, then short bullet points"*. Two
instructions, two units. A stance envelope plus a thesis plus bullet *points* does not fit in the
two sentences the Aggressive Debator was told to write, and the model resolved it by discarding the
one `_AGENT_MAX_TOKENS` was sized on (DEF125) — neutral_debator median **5** sentences against a
guide of 2, research_manager median **9** against 4–6.

**DEF251.** `- Open your PROSE with: "…"` competed with `_STANCE_FORMAT` for line 1 in all three
debator files. DEF243 had already tried fixing this by rewording, and DEF251 measured the result:
displacement 28.9% → **33.3%**, with 20% of turns emitting no envelope at all — a class the DEF247
parser fix cannot recover, because there is nothing to strip.

**DEF256 (minted this session).** Latent, and made reachable by DEF236. `extract_json_object`
parsed with `json.loads`' default `strict=True`, which rejects raw control characters inside
strings. Asking the PM for bullets inside `narration` invites real line breaks, and one of those
made the WHOLE verdict unparseable — `_parse_pm_verdict` returned no verdict and the caller failed
safe to PASS (DEF059). A decided APPROVE, at the PM's own levels, lost over a whitespace character.

## What shipped

| | Change | File |
|---|---|---|
| DEF236 | `_LENGTH_GUIDE` restated in BULLETS — the unit the structure was already written in. `_PROSE_FORMAT` reduced to style, so the shape is stated once. | `room_prompts.py` |
| DEF236 | `_AGENT_MAX_TOKENS`: PM 900 → 1100. The **only** budget moved, and the only agent whose ask grew. | `room_prompts.py` |
| DEF236 | `_NO_FENCE_CLAUSE` — the no-code-fence ban is no longer asserted at the Trader. | `room_prompts.py` |
| DEF251 | The opener bullet **deleted** from all three debator files; role framing preserved in a bullet that says nothing about line 1; `## You DO NOT` names what owns the slot. | `content/agents/*_debator.md` |
| DEF256 | `json.loads(candidate, strict=False)`. | `llm_json.py` |
| — | The DEF058 reformatter no longer re-lengths narration to "3-4 sentences". | `room_runner.py` |

**The direction was Saiful's call**, taken before building, because DEF236's own row leaves it
open: *unify the unit* rather than *drop the bullets* or *raise the guide to the measured medians*.
Bullet counts are his (3 for debators, 6 for the PM).

**Note this asks the researchers and the RM for materially LESS than they write today** (medians 8
and 9). That is deliberate, not an oversight: the RM's turn is the single input the EXECUTION and
RISK phases reason from (DEF095), so its verbosity is inherited by every prompt downstream.

**A fourth layer of the same contradiction was found while fixing the three.** `_PROSE_FORMAT` told
all eleven prose agents *"no code fences"* while `content/agents/trader.md:24-33` specifies a fenced
labelled block as the Trader's output structure — and `_LEVEL_PATTERNS` reads the levels back out of
it. `room_runner.py:1243-1249` had recorded this and left it to DEF236. Resolved the other way for
that one agent: the block is load-bearing, so the ban stops being asserted rather than the block
being dropped. **Whether the block is the right contract at all is CR152 Tier A.4, and that is gated
on DEF242/DEF237 which had not shipped when this was written** (they are Batch 2, submitted
separately). Deleting it first takes the full level triple 2/18 → 0/18.

## Why first

Every later batch in the programme ADDS prompt bytes (Batch 6 renders fundamentals, Batch 7 renders
risk state, Batch 9 renders feed depth). `_AGENT_MAX_TOKENS` was calibrated against a guide the
model cannot meet, and truncation currently sits at **0/198 by headroom, not by design**. Phase 5:
*"Adding blocks before resolving DEF236 buys truncation."*

## Test command and its observed output

Run in a **detached worktree at the submitted SHA**, not in my shared checkout:

```
git worktree add --detach .claude/worktrees/audit-R68-BATCH1 0ef2893f
cd .claude/worktrees/audit-R68-BATCH1/backend
"/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python" -m pytest tests/unit/ -q
```

```
3140 passed, 1 skipped, 13 warnings in 492.74s (0:08:12)
```

My shared checkout was clean of foreign SOURCE at commit time — `git status --short` showed only
`.claude/settings.local.json` (another lane's Claude Code settings) and `docs/benchmark/kimi/`
(track K, untracked). Neither is on the backend import path, and neither was committed. The
pathspec commit named all 14 files explicitly.

## Measurement, as it was run

**Assembled bytes** — `dump_assembled_prompts --ticker AAPL`, then read directly:

| Check | Result |
|---|---|
| room prompts still carrying *"lead with a one-sentence thesis"* | **0 of 12** |
| room prompts still carrying *"Open your PROSE with"* | **0 of 12** |
| no-fence clause present | **10 of 12** — absent exactly at `trader` and `portfolio_manager` |
| each agent's `Write …` line matches its new guide | 12 of 12, read individually |

**DEF256** — measured, not asserted. The exact string
`{"action":"APPROVE",…,"narration":"Approving at reduced size.<LF>- Valuation supports it: **P/E
18.2**…"}` raises `Invalid control character at: line 1 column 146 (char 145)` under `strict=True`
and parses cleanly under `strict=False`.

## Builder's own revert-proof QA

`tests/unit/test_def256_json_control_chars.py` — reverting `strict=False` to `strict=True` fails
**4 of its 5** tests and leaves `test_genuinely_malformed_json_is_still_rejected` green. That is the
correct signature: the fix is load-bearing for the newline class and does nothing for the malformed
class, which is what stops `strict=False` being read as "accept anything".

## Where I inverted an existing guard, and why

`test_def241_def243_debator_arithmetic_and_stance.py::test_def243_no_debator_claims_the_first_line_for_prose`
asserted **`"Open your PROSE with:" in text`** — it pinned DEF243's remedy in place, and DEF251 is
the measurement that that remedy did not work. Renamed to
`test_def251_no_debator_dictates_its_own_first_line`; it now asserts the string is absent and the
ownership line present. The 12-file scope test was widened to catch **both** spellings.

**This is the one change in the batch that weakens nothing but looks like it might**, so it is
called out rather than buried: `test_cr106_stance_envelope.py` and
`test_def247_displaced_stance_envelope.py` are **unmodified and green** (the CR155 constraint).

## What is NOT claimed

The acceptance for DEF236 and DEF251 is a **post-promotion re-measurement** and it has not run.
Both rows therefore stay `open`, deliberately — booking a prompt fix as `fixed` on the strength of
green unit tests is the CR105 Amendment-1 trap and, concretely, the DEF241 mistake (booked
mostly-fixed, reopened by a round-2 auditor, still byte-identical to pre-fix for two of its five
agents). Owed:

- parsed-stance yield **≥95%** of debator turns, residual hand-read;
- argument length must **not** shorten — the deleted bullet also carried the role's framing;
- DEF236's six over-budget rates re-measured on one epoch;
- the CR164 pinned regression batch (`--n-pairs 26 --repeat-pairs 0 --seed 164`).

DEF256 is booked `fixed`: its acceptance is deterministic code with a revert-proof test, not a
live measurement.

---

**SUBMITTED: round 1**
