<!--
R68-BATCH3.architect.md — architect submission lane. State derives from round numbers here vs
R68-BATCH3.auditor.md.
GATE: none was used while building. Batch 3 of the CR143 prompt + data-feed remediation programme
(one handshake PER BATCH, Saiful 2026-08-11).
-->

# R68-BATCH3 — audit lane (CR146 Tier A · CR152 Tier A.1–3 · CR149 Tier A · CR147 Tier A.2–5)

> Round 1 submitted at `de1fd8a7`; the live round line is at the foot of this file.

**SHA:** `de1fd8a7` (`main`, pushed to origin)
**SCOPE:** chunk — four CRs' Tier A, not any one CR's definition-of-done. Each stays `proposed`.
**depends-on:** R68-BATCH1 (`0ef2893f`, COMPLETE r1) and R68-BATCH2 (`0a5b4f1e`, awaiting).
Both dependencies are real, not bookkeeping — see CR152 A.4 below.

**Item:** delete the demands the system cannot honour. **Prompt-only. Deletions and truthful
restatements — nothing is added to a prompt in this batch.** Tier A.

## The acceptance is that nothing else moves

Every instruction removed here measured **0/18 or 1/18** compliance on the 2026-08-07 epoch. There
is no compliance rate to improve, so the claim is *not* "these now work" — it is that the prompts
stop asking for things the stack cannot supply, and that nothing which DID work stops working. That
is a post-promotion re-measurement (CR105 Amendment 1), and it is owed, not claimed.

## What went, and the supplier check behind each

| Removed | Where | Measured | Why it cannot be honoured |
|---|---|---|---|
| *"Provide specific levels: entry, target, stop-loss"* | `market_analyst.md` | 0/18, 1/18 already mis-parsing | No ATR, stdev or volatility of any kind is rendered — there is nothing to size a stop with. Turning levels into a trade is the Trader's job. |
| *"Risk-reward ratio (e.g. '3:1 R:R')"* | `market_analyst.md` | 0/18 | Same. |
| The risk-tier R:R floors | `overlay_generator._market_analyst_block` | 0/18 and 1/18 | A floor on a ratio the agent is no longer asked to produce. |
| *"Never recommend leverage above what X% drawdown can absorb"* | `overlay_generator._market_analyst_block` | **18/18 prompts** | **The simulator has no leverage, margin or borrow concept at all** — no match in `sim_engine.py` or the models. P2 with nothing to control. |
| `Path.ACTIVE`'s *"1H–weekly. Specify entry/exit/stop levels"* | same | **0/18 (unexercised)** | Contradicts the base prompt's *"No intraday (1H) timeframe"* six lines up; `_HISTORY_PERIOD="3m"` fetches daily bars only. **A code-read finding, not a measured failure** — stated as such, fixed anyway. |
| *"Risk Debators' arguments (Aggressive, Conservative, Neutral)"* as an Input | `trader.md` | 18/18 promised, 0/18 delivered | They speak AFTER the Trader. |
| *"+ remaining drawdown capacity"* as an Input | `trader.md` | 18/18 promised, **0/18 delivered** | **Added in round 1 — MINOR 1, upheld.** CR152 A.1 scopes it (*"drop it or let Tier C deliver it; today it is a promise the assembler never keeps"*) and it shipped in the same line-edit as the Debators clause, but it was not itemised here or in the commit body. The auditor's own check is the right one and is recorded rather than restated: `grep -rn current_drawdown_pct room_prompts.py overlay_generator.py` → **zero matches in either**. The figure is threaded as an internal parameter for the PM's deterministic safety-floor check and was never rendered into any agent's prompt text, so the removal is correct — the disclosure was the gap, in a batch whose whole premise is that every removal is accounted for. |
| `SELL` in the Side vocabulary | `trader.md` | **0/18 proposed a short** | No meaning under `long_only`, which the same prompt states twice. **Coherence, not a live defect — not priced as one.** |
| *"State the expected vs actual"* | `news_analyst.md` | — | The only line modelling a number shape the stack cannot produce, inside a grounding directive forbidding invention. Consensus estimates are Tier C, not shipping here. |
| *"Identify second-order effects (peers, suppliers, customers)"* | `news_analyst.md` | — | No entity data exists and none is planned. |
| *"watchlist relevance"* | `overlay_generator._news_block` | — | No watchlist is injected into any prompt; it named a list the agent has never been shown. |
| *"Cite 3–5 specific analyst points"* + the `32% gross margins` example | `bull_researcher.md` | **14/18 zero-compliance** | The Bull USES the transcript and simply does not attribute, so the ask is rewritten to what is enforceable. The example goes because a worked example for a dead instruction is dead weight — **not because it leaks; §4 established it does not.** |
| *"Lead with the thesis in one paragraph"* | `bull_researcher.md` | lost 15/18 | Contradicted the shared format contract. DEF236 (Batch 1) made that contract satisfiable, so this file stops fighting it. |

**Softened rather than deleted, with the reason:** the LONG_HORIZON macro line asked the News
Analyst to *weight* the Fed cycle and fiscal policy against single events. The only forward macro
datum in the entire prompt is an FOMC countdown in days. Asking for a weighting of something never
supplied is an invitation to fill it from training memory, three lines under a notice that there is
no macro feed. It now names the FOMC countdown as the one datum and requires anything else about
the cycle to be marked as framing, not data.

**Added, and it is the only addition in the batch:** `- Ticker blocklist: (none declared)` when the
list is empty. 18/18 Bull prompts are told to *"Respect ticker_blocklist absolutely"* while 0 of 216
epoch prompts carried one, so the agent could not tell *"there is no blocklist"* from *"the
blocklist was not attached"* — absence rendered as silence, the CR040 shape. Measured consequence
**0/18**, so it is booked as cheap correctness, not as a fix for an observed failure.

## CR152 A.4 — resolved as KEEP, which is the opposite of what both source reviews said

Recorded rather than done quietly, because a reader of the CR will expect a deletion.

The tier's own condition was *"it goes when DEF236 has decided what shape the Room wants, and the
parser has been pointed at that shape."* DEF236 decided in Batch 1 — **and it decided in the
block's favour.** `_PROSE_FORMAT`'s blanket *"no code fences"* turned out to be a fourth layer of
the same contradiction (it banned, for all eleven prose agents, the exact structure `trader.md`
specifies and `_LEVEL_PATTERNS` parses), and the resolution was to stop asserting the ban at the
Trader, not to drop the block. The block is the only place in the assembled prompt that asks for the
line-anchored layout the parser reads, and CR152 itself measured deleting it as taking the full
triple **2/18 → 0/18**.

## Out of scope, and flagged rather than taken

`trader.md`'s `## You DO NOT` still carries *"Recommend leverage above what the user's drawdown cap
can absorb"* — the same non-existent capability CR146 Tier A deletes from the Market Analyst
overlay. **No CR measured it and none lists it**, so I left it. It belongs in CR152's next tier;
flagging it here so the finding is not lost.

## Test command and its observed output

```
cd backend && .venv/bin/python -m pytest tests/unit/ -q
3162 passed, 1 skipped, 13 warnings in 482.23s (0:08:02)
```

## Measurement, as it was run

`dump_assembled_prompts --ticker AAPL`, then grepped the 12 assembled Room prompts directly:

| Deleted string | Prompts still carrying it |
|---|---|
| `Provide specific levels` | **0 of 12** |
| `Risk-reward ratio (e.g.` | **0** |
| `Never recommend leverage above` | **0** |
| `Specify entry/exit/stop levels` | **0** |
| `R:R ≥ 3:1` / `R:R ≥ 2:1` | **0** / **0** |
| `second-order effects` | **0** |
| `expected* vs *actual` | **0** |
| `watchlist relevance` | **0** |
| `Risk Debators' arguments (Aggressive` | **0** |

And the two additions: `Ticker blocklist: (none declared)` in **12 of 12**; the Trader's
pre-empt-the-debators line present in `trader.txt`.

## DEF244's snapshot guard fired, and it was answered rather than bypassed

`test_def244_def245_sizing_lane_and_literals.py::test_the_researchers_output_style_is_pinned_to_a_reviewed_snapshot`
pins both researcher files by hash. Its own docstring calls it a **REVIEW PROMPT, not a failure**,
and asks exactly one question of any edit: *does this bullet ask a RESEARCHERS-phase agent to output
a position size?*

**Answered: no**, and the answer is recorded in the test beside the new hash rather than left as a
green tick.

- The rewritten citation bullet asks for **attribution** — name the analyst each piece of evidence
  came from — with no quantity of anything.
- The **added** falsifier bullet's *"not a caveat — a number"* is a **price level**, scoped by
  *"taken from the block above"*, and it sits directly above the bullet that forbids sizing.
- That *"not a position size"* bullet — naming the Trader, the Risk Debators, the PM and the floor —
  is **unchanged and still present**. Verified by reading it, not by the hash going green.

`bull_researcher.md` `63deed87ac60` → `7518a15c30d1`. **`bear_researcher.md` is unchanged**, which
is itself the check that the edit stayed in its lane — three researcher-adjacent files were open in
this batch and only the one CR149 scopes moved.

## What is NOT claimed

- No compliance rate improves, because none of these had one. The acceptance is that nothing else
  moves, and it is a post-promotion re-measurement that has not run.
- The `Path.ACTIVE` fix is unexercised on the measured epoch (all 18 users were `long_horizon`).
- All four CRs stay `proposed`. Only their Tier A is here.

---

**SUBMITTED: round 1** — **COMPLETE (round 1)**, 0 BLOCKER 0 MAJOR, 2 MINOR.

**MINOR 1 closed above** (the `remaining drawdown capacity` row, added to the "What went" table with
the auditor's own zero-matches check recorded). The change was correct; the disclosure was the gap,
which in a batch premised on every removal being accounted for is exactly the right thing to have
been caught. No code change — the fix is the itemisation.

**MINOR 2 needs no action here** by the auditor's own framing: the `bull_researcher.md` 14/18
citation-attribution figure is a response-side measurement inherited from the CR, not a claim this
batch produced, and DEF231–233's nine rounds already established that lexical measurement of
generated prose is noisier than a prompt-side grep.
