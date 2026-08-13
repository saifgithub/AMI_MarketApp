# CR179 — every number the Room can have, and a Room that agrees with itself

**Terminal build for agent data + prompts.** On close, `room_prompts.py`, `content/agents/*` and the four
fetchers are frozen, CR143/CR145–CR156/CR166 close as `done`, and CR160 (rename 6 agents) becomes
schedulable.

**ID note.** Filed as CR179 after **CR177 and CR178 were both found taken during minting** — CR177
(`307e75e1`, safety-floor journal) landed between this build's planning check and its ID reservation, and
`CR178_insights_segment/` was created by another session at 14:52 while this doc was being written. Both
were caught because the check was `folder + row file + git log --all --grep`, not `ls _registry | tail`,
which is how CR173 was overwritten once already. The folder was created to stake the claim **before** the
doc was written.

---

## Why

Nine batches and CR166 Stage 1 removed the contradictions the Room could not satisfy and supplied numbers
agents had been inventing. The instruments say it worked: **M1 role-identifiability 87.9% → 97.5%**, **M3
novel numbers 4.3% → 2.7%**, parsed-stance yield **85.3% → 100%**, over-budget turns **20.8% → 7.1%**.

Against that: **fourteen CRs (CR143, CR145–CR156, CR166) are open and not one is `done`**, and two defect
classes have provably recurred rather than closed.

- **The arithmetic class, four times.** DEF066 (the formula) → DEF235 (the parser) → DEF241 (the prose) →
  CR166 Tier D (*around the guard built for the prose case*). The Aggressive Debator stated a 0.30 pt
  drawdown contribution where its own prompt said 0.18, because `room_prompts.py:411` appends the worked
  figure only when the agent's size **differs** from the ceiling — and that agent argues *at* it.
- **The PM-rationale key, three times.** DEF232 → DEF239 → DEF264, the last finally structural.

Both share one shape: **a fix scoped to the observed instance leaves the class open.** This CR is scoped to
the classes.

And **every response-side rate that motivated CR145–CR156 is where it was**, because nothing has counted it
since: cross-lane citation (news 18/18), the 9/18 fabricated per-community attribution, the 83%-for-−48%
error class, wrong asymmetry 2/6, REJECT-inside-PASS. Fifteen claims shipped saying *"re-measure
post-promotion or it is the CR105 Amendment-1 trap"* and were not re-measured.

Saiful, 2026-08-13: *"a build that ends all the changes related to the data and the prompts sent to the
agent. Reconcile it all. (1) we have all the data needed. more is better, less is not acceptable. (2) Make
the room coherent."*

---

## Decisions taken (Saiful, 2026-08-13)

1. **Keep the lane firewall; fill every lane.** Four analysts keep lane + shared core; Bull/Bear/RM/Trader/PM
   keep the full sheet. Every lane gets every field that is its desk's own business — completeness *within*
   a lane. "More is better" applied *across* lanes would reverse CR145 Tier C, the shipped and measured
   decision behind the 97.5%.
2. **All four coherence categories in scope**: arithmetic matches supplied figures · verdict does not
   contradict its evidence · no fabricated attribution or dead claims · agents stop doing each other's jobs.
3. **Terminal, then freeze.** Absorbs the two still-`proposed` CRs (CR149 Bull, CR152 Trader) and the
   fundamentals TTL cache blocking CR145 Tier D and CR146 Tier C.

---

## The constraint that replaces "subtract before you add"

The old rule's premise is **dead**. It rested on DEF236's *"every prose agent is 61–100% over its length
guide"*; DEF236's own closure replaced that with **7.1%, nine of twelve agents at zero**. Four documents
still cite the retired figure (`CR167:323`, `CR168:145`, `CR169:117`, `OPEN_WORK_SURVEY:367`).

Measured 2026-08-13 against the committed 08-13 corpus (482 real production rows):

| axis | finding |
|---|---|
| **Input context** | **Not a constraint.** Largest real prompt **31,544 chars ≈ 6,600–9,000 tokens** against `ami-llm`'s **262,144**. Tripling every sheet puts the PM's worst case near 4% of context. **26× headroom.** |
| **Cost** | **Not a constraint.** No per-token accounting exists in `backend/app/`. Credits are flat per convene (`credit_service.py:65-97`); on-prem vLLM at 0.5 GPU utilisation with zero preemptions recorded. |
| **Output decode** | **This is what breaks, and it is already broken.** Truncation is **6/482 = 1.2%**: bull **5%**, bear **5%**, neutral **2.5%**, PM **2.5%**. Bull is at **107% of cap at p95**, neutral **100%**. Four agents hold only **1.27×–1.56×** headroom at the median. |

A **+44%** fact-sheet increase historically bought **+14% to +102%** output and took truncation 0/216 → 6/482.

**Binding rule for every commit under this CR:**

> Add freely on the input side — context and cost do not care. **Any commit that grows a sheet must
> re-derive `_AGENT_MAX_TOKENS` for `bull_researcher`, `bear_researcher`, `neutral_debator`,
> `research_manager` and `portfolio_manager` in the same commit**, and carry a post-promotion
> `finish_reason == "length"` re-measure as its acceptance.

Raising the ceiling is **free on this host** — `room_prompts.py:167-186` retracted the KV-reservation
argument as asserted-not-measured: *"max_tokens is a ceiling, not an allocation, and decode is paid per
token actually generated."* Being twenty tokens short costs a stance (CR106) or a whole verdict
(DEF258/DEF261 — a clipped JSON envelope published raw JSON to the Room on a live sized APPROVE).

---

## Correction to this CR's own premise, made before building

The plan this CR executes asserted that the census is blind to *read-then-dropped* provider keys, citing
`totalCash` as the proof: read at `fundamentals.py:267`, folded into `net_cash`, reaching no agent, while the
census's source-regex (`fact_sheet_census.py:263-285`) counts it consumed.

**Measured before implementing, and the premise was wrong.** A perturbation probe over all 45 regex-consumed
keys — change one `.info` value, re-run the real fetcher, see whether any returned value moves — found
**zero genuinely inert keys**. `totalCash` *does* influence output (`net_cash`). The four keys that showed
inert are all correct: `pegRatio` and `regularMarketPrice` are fallbacks the all-keys fixture never triggers,
and `dividendRate`/`exDividendDate` are read in `market_data.py` and reach the profile via `EarningsInfo`.

The probe also caught **its own first version being wrong**: an additive perturbation reported `totalDebt` —
a demonstrably returned field — as inert, because `round(x / 1_000_000)` swallows a small delta. Fixed
multiplicatively. Stated because a guard that reports a known-good field as broken is the failure mode this
whole CR is about.

**So the census needs no rewrite, and the real finding is narrower and different:** perturbing `totalDebt`
moves `net_cash` **and** `total_debt`; perturbing `totalCash` moves **only** `net_cash`. Gross debt is
rendered, gross cash is not — and `fundamentals.py:271-273` argues explicitly why gross matters beside net
(*"$40B cash against $45B debt and $1B against $6B both render as net debt $5,000M, and they are not the
same balance sheet"*) while implementing only the debt half. That is a **Leg 3 render gap**, not a Leg 0
census gap, and it is invisible to both guards: parity only sees returned keys and `total_cash` is not one;
the census sees `totalCash` in source and counts it consumed. Both are right; neither asks the question.

---

## Scope

### Leg 0 — the instruments (nothing ships until these can see)

*"Less is not acceptable" needs a guard that can detect "less"; coherence category 4 has no metric at all.*

- **Census**: print **and gate** direction 2 — `unreachable_computed_fields` is computed (`:321`) and
  returned (`:335`) but `main()` prints only direction 1 (`:351-370`) and the exit code (`:371`) ignores it,
  so it is enforced by one unit test and invisible to an operator. Refresh the stale docstring (`:12-13`
  still claims *"180 keys, 132 numeric, we read 23"*; the manifest holds **184** and the fetcher reads
  **45**). Add the **dead-exemption** guard — `"revenueQuarterlyGrowth"` (`:150`) exempts a key the provider
  no longer sends; only the opposite direction is guarded (`:326`). Add the **perturbation influence check**
  as a test, keeping the regex as the candidate set: the census's contract says *"we pull it and drop it is
  not a third option"*, and only an influence test can enforce that.
- **Parity** (`test_prompt_data_parity.py`): add **`Quote`** to `_SURFACES_BY_SOURCE` (`:208-215`) —
  `change_pct` and `market_state` cannot fail parity today because parity does not know they exist. Purge the
  **four stale `INTENTIONALLY_OMITTED` entries** (`:317-336`) that now assert the opposite of the code
  (CR166 Stage 1 renders ex-date and dividend rate on both surfaces). Add the missing guard: **an omission
  entry whose field IS rendered must fail** — `test_registry_entries_are_valid:609` checks only that the
  reason is non-empty, so a stale omission is silently permanent.
- **CR104 violations** — `industry` (`room_prompts.py:1392`, no `_field_is_live` check while `sector` at
  `:1390` has one) and `net_cash` (`_net_position_line:1333`) render under a `(LIVE)` label over an
  `unavailable` state. Both write a `field_state` key that is never read.
- **M8 — per-turn cross-lane domain-citation count.** New metric in `prompt_quality_sweep.py`. This is
  CR145 Tier C's entire acceptance and POSTBATCH9 states plainly that *"no current metric computes"* it.
  Without M8, "agents stop doing each other's jobs" is unfalsifiable and Legs 1 and 3 cannot be graded.
- **CI sweep smoke test** — run the sweep against the committed epoch. DEF271's row names this as the honest
  fix and records it unbuilt; the sweep was dead on import for four days across the entire Batch 1–9
  programme and nobody noticed.

### Leg 1 — the free correctness wins (prompt bytes only, no new data)

`overlay_generator.py:88-91`'s hard-coded *"1/30th of a 30% cap"* under `Max acceptable drawdown:
{mandate.max_drawdown_pct}%` (**wrong in 8/18 mandates, seen by all 12 agents** — CR154 A3) · the debator
`## Inputs` blocks naming agents who speak later (`aggressive_debator.md:17-18,25` at **0/18** compliance,
`conservative_debator.md:18`; the Trader's identical bug is already fixed at `trader.md:17-18,44`) ·
`aggressive_debator.md:24`'s unsubstituted literal `X%` · `trader.md:39`'s leverage line (**the simulator has
no leverage, margin or borrow concept**; the identical line was deleted from the Market Analyst with that
reasoning at `overlay_generator.py:303-304` — **unfiled, needs a DEF**) · `research_manager.md:27`'s *"lean
short"* inside LONG-ONLY (CR151 C) · `overlay_generator.py:425`'s imperative 3-part output with no Room
carve-out (**13/18 leak**, CR151 B) · `LearningStyle.QUICK`'s *"tabular"* against `room_prompts.py:311`'s
*"no tables"* (**unowned, needs an ID**) · the PM's action vocabulary in **four** mutually-inconsistent forms,
reconciled by deletion at every site — noting `agent_prompts.py:94-109` gives the 1-on-1 surface no
`_PM_VERDICT_FORMAT`, so `REJECT` is still operative there (CR156) · `social_media_analyst.md` (**the only
prompt file the programme never opened**, dated Jul 13) and its three asks with no data dimension (CR148 C) ·
`neutral_debator.md:26`'s *"hedge"* with no `option_chain` anywhere (CR155 B) ·
`conservative_debator.md:36`'s unmapped *"clearly supports"* · `_bear_block`'s dead short clause (CR150 C) ·
`news_analyst.md:19`'s blanket macro denial beside a rendered FOMC countdown.

### Leg 2 — the fundamentals TTL cache

`fundamentals.py` has **no cache of any kind**, and CR145 Tier D's row is explicit: *"a TTL fundamentals
cache ships in this tier or the tier does not ship."* Ships the cache, then margin **trend** and buybacks
(`.income_stmt`/`.cashflow`, CR145 D), the **2-year history window** for *"emphasise monthly/quarterly
trend"* — asked in 18/18 prompts against a ~65-candle 3-month fetch (CR146 C) — and `.earnings_dates`
(CR147 C).

### Leg 3 — fill every lane

Lane-assigned; **every field names the rule or role-line it serves or it does not ship**;
`_AGENT_MAX_TOKENS` re-derived in the same commits.

**Technicals** (26 keys exempted as *"CR166 stage 3"*): `twoHundredDayAverage` — **zero hits for "200-day"
anywhere in either register**, and `compute_technicals` cannot derive one (`_HISTORY_PERIOD = "3m"` ≈ 65
bars) though the value is already in the dict · `previousClose` + `regularMarketChangePercent` — **the sheet
states a price and never says whether it moved** · `52WeekChange` + `SandP52WeekChange` · volume absolutes ·
`fiftyDayAverage` as a cross-check on our own SMA. **`Quote.change_pct` and `Quote.market_state`** are
computed on every quote and structurally invisible because the Room never calls `.quote()`.

**Bear/Trader**: beta, the 8 short-interest keys, ATR/realised vol — **ATR to Trader and Bear only**, CR146
having explicitly rejected it for the Market Analyst. **Fundamentals**: gross `total_cash` (see the
correction above). **News**: `summary` (73/73 articles carry it), watchlist injection (`WatchlistStore`
exists and is never read), and `DEFAULT_HEADLINE_LIMIT` — the News Analyst's sheet is **1,342 chars, ~1/3 of
any downstream agent's**, and 3 headlines is its entire payload. **Social**: `sample_snippets`, fetched and
rendered on 1-on-1, never stored for the Room, while the prompt claims excerpts.

**Compliance**: the sourced no-fossil-fuels / no-tobacco-alcohol-gambling verdict is fetched **every run**
(`room_runner.py:3706`), enforced (`safety_floor.py:322`) and **narrated to nobody**, while the
identically-shaped halal verdict gets a full three-state sourced narration. Same for
`locale_allowed_universe`. **Sector allocation** reaches only the PM (`room_prompts.py:764`) — eleven of
twelve agents argue position size with no sector picture. **CR166 Tier C derived figures**: % distance to the
20-day SMA and the 50-day range **high**, and size in shares and dollars at the mandate cap.

### Leg 4 — kill the arithmetic class structurally

*"We do not let the agent calculate" is a prompt instruction today, and P2 says those are not controls; four
recurrences prove it.* Every derived figure precomputed and handed over. **DEF241 residue** —
`room_prompts.py:694` gates the worked figure to RISK/VERDICT, so Bull and Research Manager are byte-identical
to pre-fix and still carry the raw `P×S/100` formula. **CR166 Tier D** — `room_prompts.py:411` withholds it
from the agent arguing *at* the ceiling, which is the Aggressive Debator and the 0.30-vs-0.18 case.
**CR149 Tier C** — the backstop for upside % and drawdown contribution (**2 of 11 Bull figures wrong**: GRAB
*"44%"* against a true 60.49%, laundered onward by the RM). **`_RR_CLAIM_RE`** (`room_runner.py:1651-1655`)
has no `**` bold allowance while `_PROSE_FORMAT` asks for bold — **unfiled, needs a DEF**.

### Leg 5 — the closing measurement

40 convenes, the **same 13 tickers** held constant (DEF230's mix-shift warning), `room_benchmark.py
--fresh-user`, **live mode not the CR164 harness** — `AsOfContext` skips the news and social probes entirely
(`asof_context.py:9`), so the replay instrument is structurally blind to feed work at any n. Runs
**M1·M2·M3(per-agent)·M5·M6·M7·M8**, the `finish_reason == "length"` rate against today's 6/482, and a
hand-read or judge pass for the four things no numeric metric can see. Closes CR166 Stage 1's own unrun gate,
DEF255's acceptance, DEF231's direction-signal rate, and CR156 Tier B's REJECT-inside-PASS rate.

---

## Acceptance

1. Census exits 0 in **both** directions, with direction 2 printed and gated.
2. Parity covers `Quote`; no `INTENTIONALLY_OMITTED` entry names a field that is rendered.
3. M8 exists and produces a per-agent cross-lane citation rate on the committed epoch.
4. Every Leg 1 item is deleted or corrected, and `dump_assembled_prompts --verify` agrees with live.
5. **Per-agent M3 is the gate on every widened lane** — if novel rises on a lane this build widened, that
   lane is **partially reverted rather than extended** (CR166's own rule, applied to its successor).
6. Truncation does not rise above today's 1.2% for any agent.
7. Full suite green, run and quoted, per leg.

**NOT claimed on merge:** that reasoning improved. M1/M2 measure distinguishability; M3 measures where
numbers came from. Twelve agents can be perfectly distinguishable, perfectly grounded, and all wrong.

---

## Risks

1. **"More numbers is not more reasoning."** CR166's own second-order warning — *"a wider sheet could as
   easily yield twelve agents reciting sixty"* — and POSTBATCH9 already shows `fundamentals_analyst` novel
   **rising 2.3 → 3.6%** and `research_manager` **1.0 → 2.8%** *while their sheets grew*. Acceptance 5 is the
   pre-agreed decision procedure, not a post-hoc judgement.
2. **Output truncation is the real ceiling**, already live at 1.2%. The `_AGENT_MAX_TOKENS` re-derivation is
   not deferrable to a follow-up commit.
3. **Size** — six legs, ~14 CRs, ~3 new DEFs. If cut short, cut Leg 3's tail, never Leg 5: an unmeasured
   terminal build is the CR105 Amendment-1 trap at maximum scale.
4. **Promotion collisions with the games lane** — it owns migrations and store builds, and DEF278 was caused
   by a promotion landing between two of its migration-editing commits. Check `git log --oneline -5` before
   each promote. File-level collision risk is nil (Saiful stopped the other agents 2026-08-13).
