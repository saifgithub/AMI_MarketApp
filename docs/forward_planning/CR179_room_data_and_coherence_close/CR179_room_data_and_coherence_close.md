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

---

## Leg 2 — findings (2026-08-13)

**The cache went where the cost is, not where the row pointed.** CR145 Tier D says *"a TTL fundamentals
cache ships in this tier or the tier does not ship"*, which reads as *cache `fetch_live_fundamentals`*.
Measured first: the Room calls it **once per convene** (`room_runner.py:521`), so a cache there saves
nothing on the surface that matters. What Tier D *adds* is two more network calls per ticker
(`.quarterly_income_stmt`, `.quarterly_cashflow`, **0.27–0.99s each** live) and those are what the TTL
is for. `.info` is deliberately left uncached: it carries the live price (`base_price` ←
`currentPrice`, and `low`/`high`/`support`/`breakout` derive from it), so a long TTL would freeze the
Room's reference price while `last_close` kept moving on its own 60s TTL — and `_reference_price_line`
would then narrate a **growing divergence between two figures that are the same instrument**. A
fabricated disagreement manufactured by a cache is a worse outcome than the fetch it saves.

**DEF289 — the token budgets were derived from an unmeasured constant, and it was wrong by ~34%.**
`room_prompts.py`'s *"~1,900 chars ≈ 400 tokens"* is 4.75 chars/token and was never measured. It is
measurable from our own committed data with no tokenizer: a truncated turn hit `max_tokens` exactly, so
its length ÷ its cap **is** the ratio. Six such turns in the 08-13 epoch give **3.14–4.03, mean 3.52** —
the PM lowest at 3.14 because it emits JSON. Consequences, all measured rather than inferred:

- 6/482 = **1.2% of turns amputated mid-word** (bull 5%, bear 5%, neutral 2.5%, PM 2.4%).
- DEF125's floor of 600 claimed *"~75% clear of the 1,531-char worst case"*. At 3.14 that worst case is
  **488 tokens**, so the real margin was ~23%, and `test_no_agent_is_budgeted_below_the_floor` had been
  asserting a 1.5× headroom the number could not deliver. Floor → **800**.
- DEF236's PM raise to 1100 was *"derived from the new ask, not measured"*; the answer is it was still
  short. PM → **1700**.

Caps are now `max_observed_chars ÷ 3.14 × factor`, factor **1.5 where the agent truncated** (its maximum
is CENSORED — the cap produced that number) and **1.25 where it did not**. Done FIRST, before any sheet
growth, so every later leg inherits headroom rather than competing for it.

**Two guards had to invert, both kept verbatim with the evidence that killed them (DEF243's corollary).**
`BULL == BEAR` was a proxy for *"neither case is cut while the other runs on"*, and the proxy had started
producing the opposite of what it stood for: the Bull's censored maximum is 3,220 chars against the
Bear's 2,769, so an **equal** budget binds the Bull first. Restated as the property, not relaxed. And
DEF125's floor assertion divided by the retired 4.75.

**The census cannot see a statements field, and neither could parity until it was made to.** Direction 1
walks `.info` keys; direction 2 walks the `Technicals`/`Quote`/`EarningsInfo` NamedTuples. The six new
fields come from a third endpoint and are on neither, so **`test_prompt_data_parity` is the only guard
standing between them and a silent drop**. It was passing vacuously — the fake yfinance had no statement
frames, so the fetch raised `AttributeError`, `fetch_statement_facts` swallowed it, and the fields were
never produced. Fixture extended, guard confirmed red on all six, then green. Same shape as the four
stale omission entries Leg 0 deleted, and the second time this build has caught a guard passing on
absence.

**An absent buyback row is not a zero.** Measured: NBIS and KTOS carry **no** `Repurchase Of Capital
Stock` row while SNOA, a microcap, does — and GRAB reports a literal `0.0`. Those are different claims
and only the second is ours to make, so an absent row renders nothing rather than `Buybacks: $0M`.

### Not shipped in Leg 2, and why

- **CR147 Tier C (`.earnings_dates`) is BLOCKED on a new dependency.** It raises
  `ImportError: Import lxml failed` — `lxml` is neither installed nor declared in
  `backend/pyproject.toml`. Wiring it anyway would have put the feature behind a `try/except` that
  swallows the ImportError and runs **silently dark in production**, which is DEF038/DEF063 exactly.
  Flagged for Saiful rather than added: CLAUDE.md forbids introducing a dependency without flagging.
- **CR146 Tier C (2-year history window) moves to Leg 3.** It needs no new dependency —
  `_PERIOD_MAP["2y"]` already exists — but it is a *technicals-lane* fill, which is Leg 3's job. The
  incoherence it closes is live and unchanged: `overlay_generator.py:317` still asks 18/18 prompts to
  *"Emphasise monthly/quarterly trend"* against `_HISTORY_PERIOD = "3m"` ≈ 65 candles.

---

## Leg 3a — the `.info` keys nobody read (2026-08-13)

Fourteen fields, all from the `yf.Ticker(t).info` call the fetcher already makes, all measured **6/6
available** across NVDA/GRAB/KTOS/SNOA/NBIS/BAC before any code was written.

**Technicals lane** — `day_change_pct` + `market_state`, `sma_200` + `price_vs_sma_200_pct`,
`volume_today` + `volume_avg_3m`, and the 52-week relative-strength triple. *"200-day"* had **zero hits
anywhere in either register**: no agent could discuss the primary trend, and `compute_technicals`
cannot derive one from a 65-bar window. **Bear/Trader** — `beta`, `short_pct_float`,
`short_days_to_cover`, `short_interest_date` (CR150). **Fundamentals** — `total_cash`.

**"More is better" is bounded by the second half of the mandate, and three keys were refused on that
ground** — each recorded in the census with its reason, so the refusal is auditable rather than a gap:

- **`previousClose`** — the sheet already carries a reference price *and* a last close, and
  `_reference_price_line` exists because one live turn read those two as two facts. A third price is
  that defect again. The day **move** is the actual gap, and a percentage closes it without a second
  price.
- **`fiftyDayAverage`** — we already compute and render `sma_long` from the history. Two 50-day
  averages on two bases is the same defect. The 200-day has no counterpart, so it is pure gain.
- **a second volume ratio** — `volume_tone` already states the comparison off the history. The
  absolutes are taken because they answer a different question (scale: SNOA trades ~75k shares/day,
  NVDA ~45M) and the mandate's *"Liquid only. Avoid microcaps"* is a sizing constraint market cap alone
  cannot settle.

**A zero short interest is treated as absent.** BAC returns `sharesShort` 3,122 against billions of
shares outstanding with `shortPercentOfFloat` 0.0 — which would have rendered *"0.0% of float short"*, a
confident claim that nobody is short a mega-cap bank. Not a tuned threshold (that would be P16); the
boundary of the domain, since a listed equity does not have zero short interest.

**These render independently of `field_state["technicals"]`, deliberately.** That state is
all-or-nothing because `compute_technicals` cannot return "RSI but not trend". These arrive from a
different endpoint, so an OHLCV outage must not also hide a 200-day average that is genuinely live.
Still lane-gated to the technicals desk — DOMAIN, not provenance, the same rule `week52` is placed by.

### Both Leg 0 guards fired, on their first real exercise

- **The stale-exemption guard caught all 11** keys whose census exemptions had become lies about the
  code, and refused to pass until each was removed or rewritten.
- **The perturbation guard caught `marketState` as inert** — correctly. It is value-constrained
  (unrecognised session states are dropped), so the multiplicative numeric perturbation never fired its
  branch. Fixed in the FIXTURE, not the expectation: the perturbation for a constrained key has to be a
  different *valid* value. `exchange` was the first such key (CR168); this is the second, and the
  fixture's own docstring had predicted it — *"any future value-constrained key needs the same
  treatment."*

That is two guards built in Leg 0 catching two real problems in Leg 3, which is the argument for having
built the instruments before the data work rather than alongside it.

---

## Leg 3b — the screen that was enforced and never spoken (2026-08-13)

**CR152 D7.** DEF061 built a four-state resolver (PERMITTED / EXCLUDED / UNKNOWN / UNAVAILABLE) over a
sourced classification of the parent index. It is fetched on **every** run, it is **enforced** by the
mandate check, and it reached no agent. `_compliance_block` printed the boolean intent — *"Exclude
fossil fuels (oil & gas majors, coal)"* — while the identically-shaped halal constraint, **two lines
above it in the same function**, got a full sourced three-state narration with standard, source and
as-of date.

That asymmetry is a defect rather than a gap because the enforcement is real. An agent told only the
rule, with no way to ask what the screen said about *this* name, has two options and both are wrong:
assume it cleared (DEF084-ROOM's failure exactly, where narration claimed something enforcement never
decided) or state a verdict it never received. Its silence tracks nothing.

`_exclusion_narration` is single-sourced from the same object the mandate check resolves against, so
narration and enforcement cannot contradict each other — the constraint `_halal_narration` was written
to satisfy, now applied to the constraint that had been left out of it. UNKNOWN carries the heaviest
wording and both halves of its meaning (permitted **and** unreviewed), because an agent handed only one
will supply the other itself.

**The guard that mattered was the end-to-end one.** The defect was never that the narration was wrong
— it was that the object never arrived. Sixteen unit tests against `_compliance_block` would all have
passed with the universe still stranded four call frames away in `room_runner`. So one test drives the
real builder from `build_room_messages` down, and it was mutation-checked: severing a single threading
line turns it red while the other sixteen stay green. **A test that cannot fail for the reason the
defect happened is not a guard for that defect**, which is the same lesson as Leg 2's vacuous parity
pass, arriving from the opposite direction.

---

## Leg 3c — the news feed's own words, and a plan item struck (2026-08-13)

**CR147 B.2 — `summary` reaches the prompt.** Measured present on **40 of 40** articles across
NVDA/GRAB/KTOS/BAC (median 183 chars, max 500), parsed past for the entire life of the feed. It rides
in `format_headline`, the **one** renderer all three call sites share, so the Room and the 1-on-1 block
cannot state a different amount about the same article.

The reason a headline alone was not enough is visible in the data rather than argued: BAC's top item
reads *"New Study Reveals Strongest State Economies, Only 1 State Was Better Than Texas"*, and only the
summary reveals it is a CNBC ranking rather than anything about the bank. An agent asked to separate
signal from noise on titles like that is being asked to guess. **Not truncated** — this module already
reasons that *"a headline is an ASSERTION, and a truncated assertion can invert its meaning"*, and a
summary is the same object at greater length.

**`DEFAULT_HEADLINE_LIMIT` 3 → 5.** Three headlines was the News Analyst's entire payload against a
1,342-char sheet — the desk with the thinnest evidence was the one asked to judge signal. Measured, the
block runs 772–1,130 chars at 3 and 1,203–1,836 at 5. **Not 10, which is what yfinance returns:**
relevance decays down the feed and decays into *off-ticker* material, so the tail mostly buys articles
the analyst must discard, each one a chance to reason about the wrong company.

### D4 (social `sample_snippets`) — STRUCK, after checking the reason

The plan listed this as *"fetched, rendered on the 1-on-1 surface, never stored in the Room profile —
**while the prompt claims excerpts**"*. Both halves of that premise are now false:

1. **Leg 1 already deleted the excerpt claim** from `social_media_analyst.md`, so the prompt no longer
   asserts something it does not have. The incoherence was resolved in the other direction.
2. **The omission has a documented safety reason, and it verifies.** Parity's entry reads: *"raw Reddit
   post text — deliberately never stored in the Room profile dict, which also feeds the scripted
   non-LLM fallback shown to users."* Checked rather than taken on trust: `_TEMPLATES` are format
   strings interpolated with the profile (`**formatter`) and streamed to the user through
   `_typewriter`, so **the Room profile is a user-visible surface** on that path. Putting raw
   user-generated Reddit text there would put unmoderated third-party text on a user's screen verbatim.

Shipping D4 would have traded a coherence problem that no longer exists for a content-safety one that
does. **Third plan item struck after measuring** — the census rewrite and `Quote`-as-parity-source were
the first two.

---

## Leg 3d — the two constraints that could veto in silence (2026-08-13)

**D8 — the locale universe.** `safety_floor.py:336` blocks any proposal whose ticker falls outside
`locale_allowed_universe` with `blocked_by="locale"`, and no agent was told the set exists. Twelve
agents could argue a name to a sized APPROVE with no way to know it was not purchasable at all — the
same unfollowable-by-construction shape as the microcap rule before CR145 Tier A supplied market cap,
and worse in one respect, because that rule at least appeared in the prompt. The empty case is stated
rather than omitted (CR149 A.4): `None` is the alpha default, but silence cannot distinguish *no
restriction* from *the restriction was not attached*.

**D9 — the sector allocation eleven agents never saw.** All twelve are told the sector-concentration
RULE; only the PM was told the current STATE. Worse than a plain gap, because CR055 injects the real
holdings into every prompt unconditionally — an agent could read `GME ×500` a few lines above and still
not know that is 95% of one sector. **It held the evidence and not the aggregate.**

Widened to the **full-sheet set**, gated on `_lane_for(agent_id) == _ALL_DOMAINS` rather than by naming
agents — cross-lane portfolio context belongs to the agents whose job is the cross-lane join and who
propose or veto a size, and a thirteenth agent fails OPEN in the direction `_lane_for` already chose.
The four analysts stay firewalled, with a test that says so, because CR145 Tier C's 97.5% is what that
firewall bought and a widening like this is exactly how it would quietly reverse.

**DEF238's trap was checked before the gate opened, not after.** That defect was `sector_weights` never
reaching a call site, so the PM read *"no open positions yet (0% in every sector)"* in 18/18 prompts, 8
of which listed real holdings a few lines above — a confident false statement, not a silent gap.
Widening a gate onto an argument that does not arrive would have multiplied it by seven, so both call
sites were verified to pass `ctx.sector_weights` first.

---

## Leg 3e — CR146 Tier C, without the fetch it was gated on (2026-08-13)

Tier C's cost note was a **second `.history()` call per ticker per convene**, with the cheaper
alternative being to soften the overlay line to the window that exists. Neither was necessary. Most of
what the 2-year window was wanted for now arrives from `.info` at zero cost (Leg 3a) — the 200-day
average and price's distance from it, the 52-week change, relative strength versus the index. What
remained was the quarter, and **the 3-month series was already being fetched and read exactly one
candle deep.**

`return_period_pct` is first close to last close over that same series. No new call, no new provider,
and `compute_technicals`' all-or-nothing UNAVAILABLE contract is untouched. The **candle count** renders
beside the return rather than the nominal period, because the window is trading days: a
holiday-shortened quarter and a full one both answer to "3 months" and are not the same measurement.
Measured, it is 64 candles — not the ~65 `_HISTORY_PERIOD`'s own comment estimates.

**What it closes, shown rather than argued.** `overlay_generator.py:317` asks 18/18 prompts to
*"Emphasise monthly/quarterly trend"*, against one day's price and two smoothed levels. Live on
2026-08-13:

| ticker | `trend` (20/50 alignment) | window trend |
|---|---|---|
| NVDA | **uptrend** | **flat** (+0.03% over the quarter) |
| KTOS | **consolidating** | **up 20.0%** |

Both labels are true and both point away from the quarter-scale move. The agent had only the label.
Rendered *flat* rather than *up 0.0%* — a sentence that argues with itself — via `window_trend_phrase`,
which **both** surfaces call so one measurement cannot be worded two ways.

**Census direction 2 caught the two new `Technicals` fields the moment they existed** and refused to
pass until each was registered. That is the gating Leg 0 added, doing the job it was added for — and
the same run surfaced two neighbouring exemptions (`market_state`, `change_pct`) whose stated reasons
had gone stale when Leg 3a supplied those facts from `.info`.

**D2/D3 resolved, not the way the plan proposed.** The plan said to route `.quote()` or lift the two
fields onto the profile, because the Room's price comes from `.info` and it never calls `.quote()`.
Neither was needed: `.info` carries `regularMarketChangePercent` and `marketState` in the call the Room
*already makes*. Routing `Quote` as well would put a second source behind one fact and invite the two
to disagree — the defect `_reference_price_line` exists to reconcile. The fact reaches the sheet; the
NamedTuple field stays unrouted, deliberately, with that reason recorded in the census.

---

## Leg 3f — CR166 Tier C, one item of three already done (2026-08-13)

The tier asked for three derived figures. **The 50-day range HIGH was already rendered** — `_range_line`
has printed `50-day range: $low–$high` since DEF228 — so a third of the item was stale. Recorded rather
than re-shipped; that is the fourth plan item struck after checking.

**The 20-day distance.** `_moving_average_line` stated only the distance to the 50-day. The 20-day is
the one a near-term entry or invalidation is argued against, so leaving it out meant the agent either
dropped the argument or did the subtraction itself — and doing the subtraction itself is the class Leg 4
exists to close. Both distances now share **one** naming clause, which is not cosmetic: the anchor is
the same number for both, and naming it twice invites the reading that they were measured against two
different prices.

**Position size in dollars and shares.** `shares_for_size` has lived in `trading_math/portfolio.py`
since CR046 and is called by the mandate **check** only, never by a prompt. So the agent proposing a
size and the code enforcing it were working in different units, and *a percentage of an unstated base
is not a quantity*. The sizing ceiling now reads: *"At this portfolio's value that cap is $1,500, about
6 shares at the last close of $225.64."*

Precomputed rather than handed over as three operands and an instruction to multiply and divide — this
is a **new** figure being born outside the DEF066 → DEF235 → DEF241 → CR166 Tier D class, rather than an
old one being rescued from it.

Two CR104 degrades, both asserted: no portfolio value → no dollars and no shares; a portfolio value with
no **live** price anchor → the dollar cap but no share count, because a share count against a price that
is not live is a fabricated quantity and worse than the abstraction it replaces.

---

## Leg 3g — DEF291, found by reading the item it replaced (2026-08-13)

Leg 3's last listed item was **CR147 B.3, watchlist injection**. Reading that tier's own row to check
its rationale — the discipline that struck D4 — surfaced something in the same tier that outranked it.

**B.3 is struck.** Its own sizing measurement is *"29 rows / 10 users / mean 2.9 tickers against 58
distinct Room users, i.e. **17% reach**"*, and the incoherence that motivated it — a prompt line telling
the agent to *"filter to the watchlist"* it had never been shown — was already resolved by deleting that
half of the line and repointing it at holdings.

**DEF291 is what was standing beside it.** `profile["catalyst"]` was `news_items[0]`, the most recent
headline, and the feed has no relevance ranking — `_merge_headlines` sorts by recency alone. CR147's own
row records the consequence: **the top headline is off-ticker in 9 of 18 convenes (50%)**. AVGO's Room
led with *"The Toughest Questions AMD Faced On Its Latest Call"*.

That is not feed noise an agent routes around, because **the label does the asserting**: *"Catalysts —
recent"* states this IS the catalyst for the name under discussion. A fabricated fact at the data layer,
on the one field that reaches all twelve agents identically. Fixing a 17%-reach nicety while that stood
in the same tier was the wrong order.

**The error direction is the design.** A false negative labels a real article "not confirmed on-ticker"
— honest, costs a caveat. A false positive asserts an attribution that is not there, which *is* the
defect. Both false positives were found by measuring against live feeds rather than by reasoning, and
both are now regression tests:

1. A first pass took every non-stopword name token, and `Kratos Defense & Security Solutions` matched
   *"Ondas Wins Israeli Defense Tender"* on **Defense**. An industry word is not an issuer, and a
   defence company's feed is full of it.
2. Plain substring matching made `BAC` match the word **back**, putting an oil-market article under Bank
   of America's catalyst line. A three-letter ticker is a substring of ordinary English often enough
   that this manufactures the exact attribution the function prevents.

**Measured, with its limits stated.** One live sample of 8 tickers: top-headline on-ticker **3/8**,
catalyst on-ticker **8/8**. That is a single point on a rotating feed — it visibly changed between two
calls minutes apart during the measurement itself — **not** a rate, and explicitly not a claim that
CR147's 9/18 figure is fixed. Re-measuring that is Leg 5's job.

**Known residual, recorded rather than hidden:** abbreviations are missed. *"BofA picks AMD and Nvidia
as AI chip winners"* is Bank of America and would be labelled unconfirmed. Safe direction, unmeasured
rate.

---

## Leg 4 — the arithmetic class, measured before it was widened (2026-08-13)

The leg was planned as four fixes. **Three of the four were struck after measuring, and the two
things actually worth fixing were not on the list.** That ratio is the finding, not an aside: every
one of the planned items was scoped from an epoch that predates the fixes already shipped in this
build, and re-deriving each rate against the committed 2026-08-13 corpus is what separated them.

### Struck after measuring

**DEF241's residue.** The plan said to widen the phase gate so the Bull (RESEARCHERS) and Research
Manager (SYNTHESIS) receive the worked contribution figure. The premise was checked first: **across
80 bull_researcher and research_manager turns, ZERO state a pt-or-cap-consumption figure of any
kind.** The evidence that motivated the widening — the Bull writing *33 pt* where the truth was 48.3
of a 50 pt cap — is 2026-08-07, before `_risk_state_block` shipped. DEF241's own row called that block
*"the half that is real"*, and it is what closed the residue: given the budget's **consumption** at
every phase, the two agents stopped minting drawdown arithmetic rather than doing it better. So the
gate stays, CR151's adjudication stands unreversed, and the test pinning the deferral stays green
instead of being inverted. Inverting it would have handed both agents a figure derived from a −6%
stop nobody proposed, to solve prose that no longer exists.

**CR166 Tier D.** Already shipped in `0f8a4113`, with its reasoning recorded in place. Verified two
ways rather than from the commit message: the `abs(agent_size_pct - size) > 0.01` carve-out is not in
the file, and on the epoch **every prompt carrying the reference line also carries a YOUR-position
line**, the Aggressive at 5.0% against a 3.0% ceiling included.

**CR149 Tier C, the upside half.** Its finding was *2 of 11 Bull upside figures wrong* — GRAB's
**44%** against a true **60.49%**. Re-measured by replaying every Bull and RM turn against **its own
system prompt**: **22 upside claims, 0 stating a figure absent from the prompt AMI handed it.** The
agents quote now — *"52.8% upside to consensus"*, *"+26.9% upside vs. −14.3%"* — because
`_asymmetry_line` shipped on 2026-08-11 and renders that distance as AMI's arithmetic. The test's
limit is stated rather than hidden: presence-in-prompt is weaker than correctness, and the stronger
read is Leg 5's judge pass.

### What the class actually became

**The subtraction.** `_risk_state_block` hands every agent the headroom *before* the trade
(*"Drawdown USED: 0.0 pt of the 30 pt cap — 30.0 pt of headroom remains"*) and
`_drawdown_snapshot_line` hands it the position's contribution. The figure an agent argues from is the
difference, and **nothing supplied it**. Of the 92 epoch turns stating a pt-or-cap figure, **7 state
that subtraction or a rescaling of it**, and one is wrong in a way that shows the shape of the error:
a Conservative arguing 1.5% wrote *"a **5.0%** size at the proposed 6.0% stop distance; this leaves
**29.82 pt** of headroom"* — that is `30 − 0.18`, the **reference** line's figure, attached to the
**Aggressive's** size, while its own line said 0.09. Three numbers in one sentence, each read off a
line addressed to someone else.

The remainder is now precomputed and handed over, on whichever line describes the position that agent
is arguing, and on one line only. When `current_drawdown_pct` is not supplied it renders **nothing** —
assuming a flat book would manufacture the exact reading DEF292 found below.

**DEF292 — the share of the cap.** Both contribution lines rendered `~{share:.0f}% of it`. On a 30 pt
cap that format has **two reachable outputs**. Over the 240 contribution lines in 160 epoch prompts:

| | measured |
|---|---|
| lines stating `(~0% of it)` for a **nonzero** contribution | **40** |
| prompts printing two **different** pt figures under the **same** `~1%` | **40** (a quarter of those carrying the line) |

The first is DEF053 broken loudly — the Aggressive handed `0.09 pt … (~0% of it)` opened with *"the
risk budget is effectively empty and ours to fill"*. The second destroys the only thing DEF241's
second line exists to say: that YOUR position is **not** the reference one. **The fix for DEF241 was
re-creating DEF241's reading in a quarter of prompts.** Now one decimal with a `<0.1%` floor, rendered
by one function both lines call.

**DEF288, and DEF293 found underneath it.** Sweeping the production patterns over all 482 turns rather
than over invented strings: **16 turns narrate a real R:R and 3 bold it** — exactly what
`_PROSE_FORMAT` asks for — and none was ever rewritten. Two worse things came out of the same sweep.

1. The ratio group ended at a literal `1`, so rewriting `1:1.6` would have produced `2.1:1` plus a
   stranded `.6` — **`2.1:1.6`, a number neither side computed**. The missing `**` allowance was the
   only thing preventing a fabrication.
2. `_PM_RR_KEYWORD` had no word boundary, so the **rr** in *cu**rr**ent*, *co**rr**ectly*, *e**rr**or*
   and *ove**rr**ide* matched and the next figure became the "narrated" ratio: *"current **122.6x**
   trailing P/E"* extracted a 122.6 reward multiple. **19 turns across 8 agents**, and **2 of the only
   3 PM turns** that fed `_pm_rr_coherence_signal` anything — M06 `rr_is_coherent` was two-thirds
   noise on the only path that reads it.

The comment above that pattern read *"a spurious one would be telemetry noise."* It is kept verbatim
in the source, because it was true when written and stopped being true when
`_annotate_rr_against_levels` was built on top of the extractor afterwards. **A function is a control
because of who calls it, not because of what its docstring says**, and nothing rechecks the docstring
when a caller arrives. That belongs beside P2.

**The tail now reports rather than asserts.** `_annotate_rr_against_levels` claimed *"a narrated ratio
that differed has been replaced with AMI's computed figure"* whenever a ratio was **extracted** — and
the extractor matches phrasings the rewriter deliberately does not. **2 of the 36 turns the annotator
fires on carried that claim with nothing replaced**, under *"These are the figures of record"*. The
fix is `rewritten_inline = annotated != text`, not a wider regex: widening is the fix that keeps
needing to be made again. The refusal branch got the same treatment — an unverifiable ratio the inline
strike cannot reach is now marked by an appended note instead of standing unmarked, which is what that
branch's own docstring said it existed to prevent.

**Post-fix on the same corpus:** spurious extractions **19 → 0**; real ratios found **16 → 19** (the
risk-first `1:X` forms it had been reading as 1.0); turns claiming a replacement that did not happen
**2 → 0**.

### Verification

35 new guards in `test_cr179_leg4_arithmetic.py`, every one asserting a value or a relationship rather
than a label. **Five mutations, five kills**: severing `current_drawdown_pct` at its call site,
restoring the `:.0f` share, dropping the word boundary, dropping the markdown allowance, and replacing
the `rewritten_inline` check with a constant each turn a guard red. The threading test drives
`build_room_messages` end to end rather than the helper — Leg 3b's lesson, and DEF238's, is that a
helper passing says nothing about whether the argument arrives.

**Token budgets, measured rather than waved through.** The remainder clause is **162 chars ≈ 52
tokens** and the DEF292 rewording is **+1 char per line, two lines**, so the whole leg adds ~164 chars
to the five agents that carry a proposal — 0.5% of the 31,544-char worst-case prompt. DEF289's caps
are **output** decode ceilings and this growth is input-side, so no re-derivation is owed by the
binding rule; the `finish_reason == "length"` re-measure that would actually prove it stays Leg 5's,
and is named here so it is not mistaken for having been done.

**One note for Leg 5's instrument, recorded now so the re-measure is not wrong in the flattering
direction.** The "is this figure in the agent's own prompt?" test used throughout this leg is exact
string presence with digit-boundary lookarounds. The remainder renders at two decimals (`29.70 pt`,
matching the contribution's precision) and an agent that writes `29.7` would fail that test while
quoting correctly. Leg 5 must normalise trailing zeros before counting, or it will report a
regression that is a formatting artefact.

---

## Leg 5 — the closing measurement (2026-08-14)

**The corpus is a controlled comparison, which is the only reason any number below means anything.**
39 convenes on the 13 held-constant tickers (3 each), `room_benchmark.py --fresh-user`, live against
Alpha at `c79d873c` / `alpha-2026-08-14-1`. **468 turns, all twelve agents at exactly 39** — no
dropped turn, no partial convene. The committed 08-13 baseline turns out to be the **same 13 tickers,
3 each** (ANET 4 → 40 convenes) with a near-identical verdict split (31/5/4 vs 30/5/4), so the
before/after is matched on the one variable DEF230 warns about. Both corpora were re-scored with the
**current** sweep — the Leg 0 build added M8 and the older published figures came out of older code,
so quoting them side by side would have compared two instruments, not two epochs.

| | 08-13 baseline | Leg 5 (08-14) |
|---|---|---|
| M1 role identifiability | 97.5% | **95.6%** |
| M2 role signal − ticker signal | +0.163 | **+0.151** (role still wins) |
| M3 novel numbers, all agents | 2.7% | **3.5%** |
| M6 stance entropy · unanimous convenes | 1.45 bits · 0 | **1.42 bits · 0** |
| M7 date mismatch | 0.0% (67 pairs) | **2.2%** (1 of 45) |
| M8 cross-lane citation | 2.5% | **2.6%** |
| Truncation | 1.2% (6/482) | **0.2% (1/468)** |
| Derived-% inconsistency | 13.8% (4/29) | **12.5% (5/40)** |
| CR156 Tier B conflicting verdict word | 2.5% | **2.6%** (from 6/18 at filing) |

### The gate fired, and reading it correctly is the whole job

Acceptance 5 says a lane whose novel rate rises is **partially reverted rather than extended**. Novel
rose on **seven** lanes — bear 4.8 → 7.4, conservative 1.2 → 3.8, bull 2.8 → 4.3, social 0.0 → 1.4,
trader 4.7 → 5.8, neutral 1.6 → 2.3, market 0.6 → 0.7 — and fell on the three the plan named as its
own unrun gates: **fundamentals 3.6 → 3.1, aggressive 2.7 → 2.4, research_manager 2.8 → 1.1.**

Two artefacts were ruled out before the number was believed. Leg 4's own warning — that the remainder
renders `29.70` and an agent writing `29.7` would score novel — **does not apply**: the sweep's
`_norm_num` canonicalises through `%g`, so `29.70` and `29.7` are the same token. And the mix-shift
confound is excluded by the matched ticker sets above.

**So the rise is real, and hand-reading says it is not the fabrication class.** The Bear's novel
numbers are downside scenarios with their inputs on the page — `$0.17 trailing EPS × 20 = $3.40, a
-94.6% downside` off a `$62.79` close, `$203.62 × 0.9 = $183.26`, `548.84/949.83 − 1 = −42.2%` — each
one correct, each one minted by *reasoning from* an anchor rather than reciting it. Several ride
anchors this build supplied: the 200-day average (`Primary trend (LIVE): 200-day average $548.84,
price 73.1% above it`) had **zero mentions in either register** before Leg 3 and is now the reference
in a dozen turns. M3's own docstring is the tie-breaker: *"grounded-only near 100% is readback, not
analysis."* A wider sheet gave the prose desks more to reason from, and the ratio moved because the
numerator is "computed", not "invented".

**The measurement that actually tests fabrication is flat.** M3 cannot distinguish a fabricated −94.6%
from a correct one — both are `novel` — so the derived-percentage check was built to ask the question
M3 structurally cannot: recompute every claim whose reference is the close/entry. **12.5% inconsistent
against the baseline's 13.8%.** Not better, not worse. The lanes that widened did not get less correct.

### DEF279's lesson, re-learned in the same session it was cited

The first form of that check reported **26.5%**. Hand-reading every hit showed most were the
checker's fault: `$339.96 is 16.4% below the $406.63 200-day average` is *correct* arithmetic against
a named level, and the checker had scored it against the close. Pinning the reference — and excluding
80 pairs anchored to an SMA, a 52-week extreme or a consensus target rather than dropping them
silently — took it to 15.0%, and hand-reading the survivors removed one more (`Stop Distance: $18.99
(8.4% below entry)` is a *distance*, not a level, and 18.99/225.30 is exactly 8.4%). **26.5% → 12.5%,
all of it instrument error.** M7's 13.4%-on-a-0%-corpus is the standing precedent and it very nearly
repeated with a fresh metric in the same document that cites it.

### What the survivors are — DEF302

The five that survive are **risk-critical and they launder**. The Trader renders `Stop: $164.70 (-5%
below entry)` against a `$203.62` entry — truly **−19.1%** — and the Neutral Debator repeats `-5%`
verbatim. The Conservative argues a `6.0% below entry` stop that is really **−23.1%**. Leg 4 supplied
an anchor for the upside half (`_asymmetry_line`) and for the drawdown arithmetic
(`_drawdown_snapshot_line`, `_share_of_cap_phrase`), and built `_annotate_rr_against_levels` for R:R —
**but nothing precomputes "N% below entry"**, which is the figure that sets stop distance and therefore
position size. Filed as **DEF302**, open. It is flat against baseline, so it is a standing hole this
build did not introduce and did not close.

### Truncation — acceptance 6 met

**1 turn of 468 at or over cap (0.2%)**, against 1.2% before. Every agent gained headroom; the four
analysts sit at 2.3–2.9×, the researchers at 1.6–2.1×. The single at-cap turn is the
**conservative_debator at exactly 800**, headroom **1.00×** — the one budget still worth re-deriving.
**Instrument caveat, stated rather than buried:** `llm_audit` has no `finish_reason` column, so this is
`output_tokens >= cap` as a proxy. It is sound in the direction that matters (a decode that reaches the
ceiling stopped for length) but it is not the same instrument that produced 6/482, and the two should
not be quoted as if they were.

### Still open after this leg

- **M7 went 0.0% → 2.2%** — one mismatched pair of 45. One turn, not a trend, but it is the CR169 gate
  and it is the only metric that moved in the wrong direction without a hand-read explanation.
- **M1 −1.9pt and M2 −0.012.** Both still far above chance (M1 lift 10.5×) and the roles remain
  distinguishable, but a wider shared sheet is the obvious candidate and it is the direction CR145
  Tier C exists to defend.
- **DEF302**, above.
