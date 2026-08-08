# External review — bull_researcher (data sufficiency + supplier check)

> Reviewer: `kimi-for-coding` · Kimi track K session.
> Corpus reviewed: `docs/forward_planning/CR143_agent_prompt_audit/real_samples/bull_researcher.prompt.txt`
> (AMD, RESEARCHERS phase) and `real_samples/bull_researcher.reply.txt`.
> Unlike `external_review/room/bull_researcher.md` (blind prompt-coherence audit),
> this review had codebase access. Every availability claim below is verified against
> the actual fetch/assembly path — these are **findings, not hypotheses**.

## 1. Question

Does the Bull Researcher have enough data in the prompt to do its job to
~95% accuracy?

## 2. Answer

**Yes for the scoped deliverable — this is the best-supplied agent audited so far —
but two prompt-internal demands force invention, which the live reply confirms.**

The Bull's three declared inputs (`content/agents/bull_researcher.md:14-21`) are all
genuinely wired and present in the AMD corpus:

- **Analyst outputs:** the full four-analyst transcript is rendered
  (`room_prompts.py:470`, `_format_transcript` at `room_prompts.py:886-892`).
  RESEARCHERS run sequentially after the concurrent ANALYSTS phase commits
  (`room_runner.py:157`, `room_runner.py:3049-3051` — "RESEARCHERS onward see
  every analyst").
- **Mandate:** full financial profile + compliance + preferences block, plus a
  per-phase mandate snapshot and the enforced sizing ceiling
  (`overlay_generator.py:104-111`, `room_prompts.py:462-468`, `room_prompts.py:416-428`).
- **Decision Journal history:** real, ticker-scoped, plan-gated, max 5 entries
  (`journal_context.py:34`, `journal_context.py:48-50`), rendered with summaries
  (`journal_context.py:60-75`). Five real AMD entries are in the corpus.

Estimated accuracy on the scoped deliverable (thesis + cited analyst evidence +
Bear-counter + sized suggestion): **~90%** — docked because two instructions are
unsatisfiable from the data and each produced a defect in the live reply
(invented date-linkage on the price target; default-to-max sizing).

Against a full version of the job (horizon-calibrated price target, conviction-
calibrated sizing): **~70%**.

## 3. Data gaps (from the prompt)

| # | Gap | Impact |
|---|---|---|
| 1 | No conviction→size mapping | "End with a sizing suggestion based on conviction × user's risk tolerance" (base prompt line 28) gives no scale; only the hard 10.0% cap is provided (prompt line 121). The reply defaulted to the maximum — exactly the failure the cap note (CR055) was meant to bound, now expressed as "max cap = high conviction". |
| 2 | Consensus target has no date | "Frame upside numerically: '$X by Y'" (base prompt line 29) + horizon 3–10y, but the only target ($608.23, prompt line 112) is undated; the only dated anchors are earnings (+88d) and FOMC (+40d). The reply invented the linkage "$608.23 by 2026-11-03". |
| 3 | Ticker blocklist invisible when empty | Role guidance commands "Respect ticker_blocklist absolutely." (rendered unconditionally, `overlay_generator.py:358`) but the blocklist itself renders only when non-empty (`overlay_generator.py:143-144`). The agent cannot distinguish "empty blocklist" from "blocklist not attached". |
| 4 | No falsifier scaffolding | The task line demands "thesis + evidence + falsifier" (prompt line 153) but no analyst-risk summary or invalidation levels exist beyond the raw fact sheet; the reply omitted an explicit falsifier. Minor. |
| 5 | Analyst stance metadata not visible in transcript | The four analyst turns in the corpus carry no STANCE headers, so the Bull cannot weigh per-analyst conviction when citing them. (CR106 B2 stance tails exist in the format contract — `_STANCE_FORMAT`, `room_prompts.py:391-395` — but are absent from these transcript entries.) Minor. |

Note on the blind review's corpus: its prompt showed "Transcript so far: (You are
first to speak.)" — the empty-transcript sentinel (`room_prompts.py:888`). That is
a real state (all analysts withheld), not the AMD sample's state. Unfollowables it
derived from an empty transcript do not apply to this sample; its structural points
(example citation, blocklist line, sizing mapping, undated target, duplicate
mandate snapshot) are corpus-independent and all reproduce here.

## 4. Supplier check — what the codebase can actually deliver

Assembly path: `build_room_messages()` (`room_prompts.py:321-483`) → base overlay
(`overlay_generator._bull_block`, `overlay_generator.py:346-361`) + fact sheet
(`_format_profile`, `room_prompts.py:503`) + transcript + journal
(`journal_context.build_journal_context_block`) + sizing ceiling
(`trading_math/sizing.py:73-84`). Phase order: `room_runner.py:144-165`
(ANALYSTS parallel → RESEARCHERS sequential, Bull before Bear).

| # | Item | Verdict | Evidence / effort |
|---|---|---|---|
| — | Analyst transcript | **ALREADY WIRED** | Sequential RESEARCHERS see all committed analyst turns (`room_runner.py:3049-3051`); fixed emit order fundamentals→market→news→social (`room_runner.py:3026-3032`). |
| — | Decision Journal | **ALREADY WIRED** | DEF054/DEF055; ticker-filtered `list_for_user` (`journal_context.py:48-50`), plan-gated window, summaries rendered (DEF098, `journal_context.py:65-75`). |
| — | Sizing cap | **ALREADY WIRED** | Same `resolved_single_name_cap_pct` the safety floor enforces (`room_prompts.py:422`, `sizing.py:73-84`) — shown == enforced (CR046/CR055). |
| 1 | Conviction→size mapping | **NOT AVAILABLE — design gap, not a provider gap** | No conviction-sizing table exists anywhere; only risk-tier caps (`sizing.py`). Needs a policy table (e.g. low/med/high → fraction of cap) kept consistent with the safety-floor clamp. |
| 2 | Target date | **NOT AVAILABLE without a new provider; prompt-side fix available now** | `.info targetMeanPrice` carries no date (`fundamentals.py:277-279`); yfinance exposes no target horizon anywhere we read. Cheapest correct fix is a disclosure line in `_format_profile`: "consensus target carries no stated horizon" — killing the invented-date failure mode without new data. |
| 3 | Blocklist empty-state | **FETCHED, NOT SURFACED** | `mandate.compliance.ticker_blocklist` is in hand at render time (`overlay_generator.py:143`); when empty, no line renders. One-line fix: render "- Ticker blocklist: (none declared)". |
| 5 | Analyst stance in transcript | **ALREADY WIRED, RELIABILITY GAP** | Analysts are instructed via `_STANCE_FORMAT` (`room_prompts.py:391-395`); adherence is model-dependent and the corpus shows all four analysts omitting it. Not a fetch problem. |

## 5. Caveats

1. **Gap #1 is policy, not plumbing.** Any conviction→size table must route through
   the same `resolved_single_name_cap_pct` invariant or it re-creates the
   shown-vs-enforced incoherence CR055 closed.
2. **Gap #2's cheap fix is a disclosure, not data.** Wiring a real target horizon
   means a new provider (TipRanks/Zacks-class); out of scope for a prompt-audit CR.
3. The journal block costs one extra `list_for_user` DB read per researcher turn —
   already live, no new rate-limit exposure. Nothing proposed here touches Yahoo.

## 6. Recommended slice (if this becomes a CR)

1. Render blocklist empty-state line (gap 3) — one render change.
2. Add "consensus target is undated" disclosure to the fact sheet (gap 2) —
   `_format_profile` / `build_live_data_block` line, no provider work.
3. Add a conviction→size fraction table to `sizing.py` and narrate it in the
   researcher cap note (gap 1) — policy decision needed first.
4. Cut the "32% gross margins" example citation from
   `content/agents/bull_researcher.md:26` (blind-review CUT item this review
   endorses: it trains citation of numbers not in the block).

## 7. Relationship to the blind review (`../bull_researcher.md`)

**Confirmed:**
- "Cite 3–5 analyst points (e.g., '32% gross margins')" example is real and
  load-bearing-bad — sourced at `content/agents/bull_researcher.md:26`.
- No conviction scale or risk-to-size mapping exists — verified across
  `trading_math/sizing.py` and the overlay path. The live reply proves the
  failure: high conviction → straight to the 10.0% ceiling.
- "Respect ticker_blocklist absolutely" is rendered unconditionally while the
  blocklist itself is invisible when empty (`overlay_generator.py:358` vs 143-144).
- "$X by Y" vs undated target: confirmed; the reply did exactly the predicted
  invention (blind failure mode #3), attaching the undated $608.23 to the
  earnings date.
- Duplicate mandate snapshot: present in this corpus too (prompt lines 43-67
  vs 115-119).

**Killed / rescoped:**
- Failure mode #1 (hallucinated analyst attributions) did **not** materialise:
  the AMD corpus carries the full four-analyst transcript and every attribution
  in the reply checks out against it. The blind review's premise was an empty
  transcript — a real state (`room_prompts.py:888`) but not this sample's.
- "Unfollowable: no analyst outputs provided" — false for the RESEARCHERS phase
  in a full roster; the wiring guarantees researchers see every committed analyst
  (`room_runner.py:3049-3051`).
- Failure mode #2 (wrong/absent STANCE) did not materialise — header present,
  correct shape, written once, stance `for` consistent with the steelman role.

**Could not see (added by this review):** the reply's HEADLINE overflows the
32-char cap (36 chars); the 22.9% upside figure is an arithmetic slip (correct
≈23.0%); analyst STANCE tails absent from all four transcript entries.

## 8. Reply-sample verification (`real_samples/bull_researcher.reply.txt`)

Line-by-line against the AMD data block.

**Numbers.** Every figure traces to the prompt: 50% growth, 16% margin, $494.31,
strong buy, $608.23, $8,835M, 126.4, 73/100, 2026-11-03 (88 days), $584.73,
82.6x, 1.12, risk_score 3, 10.0%. Two **derived** numbers: $941.12 (= 10.0% ×
$9,411.21 — arithmetically correct) and **22.9%** — incorrect; ($608.23 −
$494.31) / $494.31 = **23.05%**. No training-memory leakage.

**Unlabeled inference.**
- "**$608.23 by 2026-11-03**" — the prompt never dates the consensus target;
  the earnings date is a separate field. Invented linkage, exactly blind failure
  mode #3.
- "no immediate distribution pressure" — spin on the Market Analyst's "lack of
  institutional conviction"; defensible steelmanning, not a quote.
- "momentum that can sustain price levels" — the Social Analyst's own read was
  reversion risk; reframed without saying so. Role-permitted, worth noting.

**Scope bleed.** None. Citing the four analysts is the Bull's defined job; all
attributions (Fundamentals on net cash/R&D, Social on buzz, Market on
volume/range) match the transcript verbatim in substance. Journal losses cited
correctly as the Bear-counter fodder.

**Stance-evidence tension.** `STANCE: for | CONVICTION: high` is consistent with
the body, but **high** conviction + sizing at the **10.0% maximum** sits on top of
two AMD stop-out losses nine sessions old in the same user's journal
($-497.70, $-55.30, both 2026-07-16). The reply acknowledges the losses yet
prices zero penalty from them — a calibration defect, not a fabrication.

**Format compliance.**
- STANCE line: correct shape, once, at top ✓ — but HEADLINE "50% Revenue Growth
  Justifies Premium" is **36 chars > 32 max** ✗.
- One-sentence thesis then bullets, bold on key metrics, no headings/tables ✓.
- Sizing suggestion present and within the enforced cap ✓.
- Falsifier: demanded by "thesis + evidence + falsifier" (line 153) — **absent**;
  bullet 4 addresses the Bear's counter but states no invalidation condition ✗.
- "3–5 sentences" vs bullets contradiction (blind review §2) — the reply followed
  the later, more specific bullet instruction.

**Net: GROUNDED on sourced facts — zero hallucinated numbers, zero fabricated
attributions — with three defects: one arithmetic slip (22.9%), one invented
date-linkage forced by the "$X by Y" instruction, one format overflow (HEADLINE).
The grounding directive held; the prompt's own unsatisfiable demands produced
every defect found.**
