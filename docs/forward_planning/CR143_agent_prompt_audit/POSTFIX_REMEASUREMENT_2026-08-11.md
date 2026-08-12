# Post-promotion re-measurement — Batches 1–3 (AT:R68)

The acceptance CR105 Amendment 1 demands: *a prompt edit whose effect is not re-measured is the
trap.* Batches 1, 2 and 3 shipped to Alpha as `alpha-2026-08-11-4` (`ed1c387c`); this is what they
actually did.

**Method.** 12 tickers through `scripts.room_benchmark` (`--batch-id r68-batch123-postfix
--fresh-user`), the same set as the pre-fix `cr143-def247-postfix` baseline, so PRE and POST are
like-for-like. Both epochs read from `room_runs.transcript` and `llm_audit` on melehost Postgres,
split at `2026-08-11T10:58:50Z` — `ami_api_alpha`'s `StartedAt` for the promoted container, which is
the exact instant the new prompt bytes began serving. **PRE n=612 turns / 51 convenes, POST n=156
turns / 13 convenes.** POST is small; every rate below carries that.

---

## 1. Stance yield — DEF251 · PASSED

The debators were told to open their prose with a line the format block already owned, and the
stance line went missing when they obeyed. Batch 1 deleted the competing instruction.

| epoch | aggressive | conservative | neutral | total |
|---|---|---|---|---|
| PRE | 49/52 (94.2%) | 47/52 (90.4%) | 37/52 (71.2%) | **133/156 — 85.3%** |
| POST | 13/13 | 13/13 | 13/13 | **39/39 — 100%** |

Target was ≥95%; at 39 turns that allowed exactly one miss and there were none.
`neutral_debator`'s 71.2% pre-fix independently reproduces CR155's *"12/18, worst of 11"* from a
different epoch and a different extraction path, which is what validates the query rather than the
result.

## 2. Argument length must not shorten — PASSED

The opener carried role framing, so deleting it risked buying stance yield with content. It did not:
mean characters per turn rose on **eleven of twelve** agents.

| agent | PRE | POST | | agent | PRE | POST |
|---|---|---|---|---|---|---|
| aggressive_debator | 725 | **1358** | | portfolio_manager | 554 | **1236** |
| conservative_debator | 537 | **1130** | | research_manager | 1312 | **1765** |
| neutral_debator | 1037 | **1274** | | bull_researcher | 1803 | **1983** |
| bear_researcher | 1310 | **2022** | | market_analyst | 530 | **647** |
| fundamentals_analyst | 716 | **749** | | news_analyst | 574 | **818** |
| social_media_analyst | 476 | **627** | | trader | 914 | 872 |

The Trader is −4.6%, inside noise at n=13 and the only agent whose format block Batch 1 deliberately
left alone (`_NO_FENCE_CLAUSE` skips it). The PM's near-doubling is the narration ask landing:
pre-fix it emitted **0.00** bullets per turn, post-fix **3.38**.

## 3. Bullet budgets — DEF236 · IMPROVED, two agents still over

`_LENGTH_GUIDE` now states the budget in bullets, the unit the structure is already written in.
Rate of turns exceeding the agent's own stated cap:

| agent | cap | PRE | POST | | agent | cap | PRE | POST |
|---|---|---|---|---|---|---|---|
| fundamentals_analyst | 3 | 60.8% | **7.7%** | | trader | 3 | 35.3% | **0%** |
| neutral_debator | 3 | 56.9% | 30.8% | | research_manager | 4 | 29.4% | **15.4%** |
| aggressive_debator | 3 | 19.6% | **0%** | | market_analyst | 3 | 23.5% | **7.7%** |
| conservative_debator | 3 | 9.8% | **0%** | | bull_researcher | 4 | 23.5% | **30.8%** |
| bear_researcher | 4 | 9.8% | **0%** | | news_analyst | 3 | 2.0% | **0%** |
| social_media_analyst | 3 | 2.0% | **0%** | | portfolio_manager | 6 | 0% | **0%** |

**Overall 127/612 (20.8%) → 11/156 (7.1%).** Nine of twelve agents sit at zero.

Two caveats stated rather than buried. **The PRE column is counterfactual** — those turns were
written against a guide expressed in *sentences*, so they are not violations of an instruction that
existed; the comparison measures whether restating the budget in bullets makes it followable, and it
does. And **`bull_researcher` got worse** (3/13 → 4/13). At n=13 that difference is not
distinguishable from noise, so it is recorded as unresolved, not as a regression — it needs the
CR164 pinned batch to settle. `neutral_debator` improved by half and is still the worst agent.

## 4. Code fences — PASSED

`_NO_FENCE_CLAUSE`: **1 fenced turn PRE (the Trader), 0 POST across all 156.** The Trader is exempt
from the ban by design — its labelled block is what `_LEVEL_PATTERNS` parses — and it stopped fencing
anyway.

## 5. Truncation — FAILED, and it is Batch 1's own doing → **DEF258**

The regression this measurement existed to catch.

| | PRE | POST |
|---|---|---|
| turns at exactly `max_tokens` | **0 / 612** | **6 / 156 (3.8%)** |

`portfolio_manager` 2/14 (cap 1100) · `aggressive_debator` 2/13 · `neutral_debator` 1/13 (600) ·
`bear_researcher` 1/13 (800).

Truncation had been sitting at 0/198 **by headroom, not by design**. Batch 1 spent the headroom:
outputs grew 20–120% (§2). The plan predicted this would come back at the tail of a Trader turn. It
came back at the tail of the PM's, which is worse — a clipped JSON envelope is unparseable rather
than merely incomplete, so `_parse_pm_verdict` discarded the verdict, the caller failed safe to PASS
(DEF059), and the raw half-written JSON became the transcript turn. Live on Alpha, SLB,
`11:27:36Z`:

```
{ "action": "PASS", "narrational": "REJECT: Trade violates hard mandate enforcement…
```

— cut off mid-word, JSON source rendered to the user as an analyst's contribution. Filed and fixed
as **DEF258** (parser-side salvage with a CR040 disclosure; the budget deliberately left at 1100,
because the two clipped samples are censored and cannot size a cap — P16).

## 6. Two findings handed to Batch 8, not fixed here

Both visible in the same 14-verdict sample, both already in Batch 8's scope:

- **`"narrational"`** — the model typo'd the narration key on SLB. `_parse_pm_verdict` reads
  `narration` alone, so even after DEF258's salvage that verdict publishes *"it wrote no rationale"*
  over real prose. This is exactly DEF239, now with a live instance.
- **REJECT-inside-PASS** — 4 of 14 narrations open *"Verdict: PASS (REJECT)"*, *"REJECT: Trade
  violates…"* or *"I PASS… REJECT"* while `action` is `PASS`. CR156 B's vocabulary reconciliation,
  measured at 28.6% here against the 6/18 it was filed on.

---

## Reproducing this

```bash
ssh melehost "docker inspect ami_api_alpha --format '{{.State.StartedAt}}'"   # the epoch boundary
```

Then the three queries — stance yield, bullet/length, and cap-hit — against `room_runs.transcript`
and `llm_audit`, splitting on that timestamp. `llm_audit` has **no `finish_reason` column**;
truncation is detected as `output_tokens >= _AGENT_MAX_TOKENS[agent]`, which is exact because
`max_tokens` is a hard ceiling.

---

## Post-fix sweep — `r68-postfix`, 2026-08-12 (AT:R68)

26 convenes on `alpha-2026-08-12-3`, the build carrying DEF260–DEF268. Same pinned
recipe as `r68-postbatch9` (`--n-pairs 26 --repeat-pairs 0 --seed 164`), so the two
are comparable turn-for-turn. 338 agent turns.

### DEF264 — the false accusation is gone

| batch | n | `_PM_NO_RATIONALE` |
|---|---|---|
| `pit-pilot-2` (pre-Batch-4) | 126 | 0 (0.0%) |
| `r68-postbatch9` (pre-fix) | 25 | **6 (24.0%)** |
| `r68-postfix` | 26 | **0 (0.0%)** |

The rate the sweep found, closed by the fix the sweep motivated. No verdict in
this batch published *"it wrote no rationale"* over prose the PM had written.

### DEF263 — the suspicion I had, and the measurement that killed it

26 of 26 verdicts came back PASS, against 13/126 (10.3%) and 3/25 (12%) before.
The specific worry was that DEF263's fix had made an open-risk outage render
*"the safety floor is blocking on this … do not argue for added size"* on every
convene, which would be an anti-approval instruction added to the whole Room.

**Measured directly: 0 of 338 prompts carried the outage line; 338 of 338 carried
the real figure**, along with the corrected `Trades opened today:` pace line. The
mechanism is ruled out.

What remains is a distribution question with no answer at this n. P(0 of 26) at an
11% base rate is ~4.8%; against the immediately preceding batch (3/25 vs 0/26)
Fisher's exact is ~0.11. **Not significant, not dismissed** — it wants a larger
sample before anyone calls it a change, and it is recorded here so the next sweep
has something to compare against rather than rediscovering it.

### DEF258's cap-hit rate, re-measured per agent — the number Batch 7 owed

Batch 7 added ~+467 chars to all twelve agents and Batch 9 added +505 to nine of
them, and both lanes stated the cap-hit rate had to be re-checked. It has been.

**8 of 338 turns (2.4%)** finished at their own `_AGENT_MAX_TOKENS` ceiling:

| agent | cap | at cap |
|---|---|---|
| `neutral_debator` | 600 | 3 / 29 (10.3%) |
| `bear_researcher` | 800 | 2 / 28 (7.1%) |
| `aggressive_debator` | 600 | 2 / 28 (7.1%) |
| `bull_researcher` | 800 | 1 / 28 (3.6%) |
| **`portfolio_manager`** | 1100 | **0 / 26** |

Against DEF258's 6/156 (3.8%) on the pre-fix build, so the rate did **not** rise
with the added bytes — but it is **not zero**, and the honest reading is that
truncation is a standing property of this prompt/budget pair rather than an
incident that was fixed.

**The PM at 0 is the part that matters.** A clipped prose agent loses the tail of
a sentence; a clipped PM loses a decision, which is the whole of DEF258 and
DEF261. Every remaining cap-hit is on an agent whose output is prose, not parsed
JSON, so none of them can reach the Verdict Board.

**A wrong first cut, recorded because the number was nearly published:** the first
query counted `output_tokens >= 1100` for every agent — the PM's cap applied to
the whole roster — and returned a clean zero. Nine of twelve agents cap at 600 and
two at 800, so that query could only ever have found PM clipping. The per-agent
join above is the real measurement.
