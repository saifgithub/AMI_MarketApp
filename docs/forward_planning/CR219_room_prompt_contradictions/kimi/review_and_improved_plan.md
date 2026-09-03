# CR219 — independent review and improved plan

TRACK: K · ROLE: Kimi · INSTANCE: - · Session tag: AT:K1
Date: 2026-09-02 · Reviewed against repo HEAD with the uncommitted `trader_block_regex` hunk present.

Reviewer scope per Saiful: contradictions **and** data additions **and** anything else useful;
every limitation documented and explicitly decided, none quietly dropped. Acceptance is
citation recovery **plus a benchmark**.

---

## 1. Verdict

The investigation is sound. I re-ran all three load-bearing checks and read the primary
artifacts firsthand rather than trusting the doc:

| Check | Result |
|---|---|
| `analysis/verify_citations.py` | exit 0 — all 15 `file:line` citations resolve to the quoted text |
| `analysis/citation_rates.py` | reproduces: margin structure 95.5% vs margin trend 24.2% vs buybacks 13.3%; 1/66 explicit refusals |
| `analysis/aggregate_arms.py` | reproduces: 6 verdicts, contradiction matrix (FA 6/6 arms), 102 clustered requests |
| `evidence/rendered/fundamentals_analyst.txt` | both halves of the contradiction in one file: line 23 "never describe a margin as rising, falling, expanding" vs line 128 `Margin trend, YoY (LIVE)` |
| `content/agents/*.md` (all 4 analysts) | findings 1–8 quoted accurately |
| `overlay_generator.py:93,437,447` | `primary_goal` printed, only `horizon` branches, #15 demand live — all confirmed |
| `test_cr105_analyst_inputs_field_state_guard.py` | blind spots confirmed: `_inputs_section()` scans `## Inputs`→`## Output` only; the 2 negative claims are presence-checked, never truth-checked |
| `_AGENT_LANES` (`room_prompts.py:1771`) | Class D confirmed — only the 4 analysts are lane-gated; 8 downstream agents get `_ALL_DOMAINS` |

The evidence discipline in this folder (byte-identical prompts, honest "what the record does
NOT support" section, PM excluded from the contradiction count in code) is above the repo's
already-high bar. The findings stand. **What needs work is the plan** — the Scope and
Acceptance sections under-specify the fix in six places, and the stated product aim (best
possible evaluation of a ticker, driven by the user's risk profile) requires three additions
the CR currently defers or omits.

---

## 2. Assessment by finding class

### Class A (denials of LIVE fields) — solid, one caution

Findings 1–7 are exact and verified. #8 (social media) is genuinely weaker, as the doc says:
the persona restricts *sentiment* elevation ("no historical baseline… do not say sentiment is
elevated relative to normal"), the sheet supplies a *mention* trend. The fix must keep that
distinction — a careless rewrite would tell the agent it has a sentiment baseline it does not
have, trading one false denial for one false claim. Recommend: rewrite #8 to name exactly
what the mention trend does and does not baseline.

The measured cost (24.2% vs 95.5% on adjacent lines of identical sheets) is the strongest
datum in the CR and correctly framed as suppression-by-omission.

### Class B (instruction collisions) — real, but three need sharper treatment before coding

These rest on model self-reports, which the doc handles honestly. My read of the source:

- **#10 (Bull "End with your CONVICTION" vs stance line "at the top only")** — partially a
  false positive. `_build_stance_format` governs the *stance line*; the persona's "End with
  your CONVICTION and what would raise or lower it" governs the *prose*. A careful reader can
  distinguish them — but the agent didn't, and "conviction" names the same concept in both
  places. Fix by disambiguating the vocabulary ("End your prose with what would raise or
  lower your conviction"), not by deleting either instruction.
- **#12 (Trader WAIT vs mandatory stop)** — the doc's framing is inverted. The uncommitted
  `trader_block_regex` hunk deliberately keeps Entry/Target/Stop **out** of the HOLD/WAIT
  branch ("Entry/Target/Stop on a WAIT WOULD be fabrication") and restores only
  `Size: 0.00%`. The grammar is right; the stale half is `trader.md`, whose output template
  shows `Stop:` unconditionally and whose `## You DO NOT` says "Skip the stop-loss" with no
  WAIT carve-out. **The fix belongs in the persona, not the regex.** The CR should say so.
- **#13/#14 (Risk Officer drawdown arithmetic)** — needs a reproduction at HEAD before any
  rewrite. The code has moved through DEF241 → CR166 Tier D → DEF243: `room_prompts.py:1225-1238`
  now renders a per-role "YOUR position … AMI computed this" line computed from
  `agent_size_pct`, with the equality carve-out removed. If the convene ran at HEAD and the
  Aggressive RO still quoted a 2.5% figure while pushing 3.0%, the residual defect is that
  the *overlay* (`_aggressive_block`, "Push for full mandate-allowed sizing") names a size
  the snapshot didn't compute for. One diagnostic convene on the CAT profile settles which
  half is stale. Do not rewrite both blind.

### Class C (overlay demands unsupplied data) — confirmed, precedent exists

`overlay_generator.py:447` verified live. CR146 deleted four demands of exactly this shape
from `_market_analyst_block` with a measured 0/18 justification; the same standard applies.
Decision needed (§5, D2): delete outright, or keep a demand backed by the free data additions
(§3c) — earnings revisions/surprise history are **not** among the free ones, so "back it" is
a real fetch, not a CR218-style precompute.

### Class D (downstream agents hold the sheet unread) — confirmed structurally, decision deferred correctly

`_AGENT_LANES` gates only the four analysts; the other eight get the full sheet with no
`## Inputs` mention. The doc is right that this wants its own before/after measurement. My
recommendation (§4, Phase 2): yes, name the sheet in the eight downstream briefs, with a
one-line numbers rule ("quote the sheet's figures; do not re-derive") — the DEF066/DEF235/
DEF241 history shows what happens when agents recompute numbers in prose.

### Class E (1-on-1 lane gap) — confirmed

Room lanes gate; `build_live_data_block()` doesn't. Cheap fix, real confusion surface.

---

## 3. What the plan is missing

### a. No quality benchmark — acceptance #4 measures the wrong half

Citation-rate recovery proves suppression stopped. It says nothing about whether the Room's
*answer* got better — and the answer is the product. The arms section already demonstrates
why: its convene harness draws the PM verdict once, and at a measured ~19.7% n=1 flip rate
no single-draw verdict difference is attributable to anything. Propose (Phase 4):

- A benchmark harness beside `evidence/`: **4–5 cached profiles** spanning archetypes
  (mega-cap cyclical = existing CAT profile, high-growth, dividend payer, distressed, one
  halal-screened name), run through the production prompt assembly.
- The PM verdict drawn through the **production 5-way self-consistency vote** (CR214 —
  see §3b), so a verdict is a majority, not a single draw.
- A rubric scored per turn (mechanical where possible, model-judged where not): grounding
  (every number traceable to sheet/transcript), mandate adherence, lane discipline,
  contradiction-free output, JSON contract compliance.
- Run pre-fix and post-fix against the same cached profiles. The pre-fix arm already half
  exists — the banked `llm_audit` corpus.

### b. PM verdict sampling: production is fine, the harness is not

**Correction to the CR doc:** its arms section says `pm_self_consistency_samples` "defaults
to 1". That was true from CR197 until **CR214 raised the default to 5** (`config.py:751`,
with majority vote, median size among winners, ties falling safe, and `approve_votes` in
0..5 for the backtest). Production verdicts are already 5-way votes; the ~19.7% n=1 flip
rate is a *harness* property, not a product property. `convene_gemini.py` runs its own
single-draw PM, which is why the arms' verdict column is uninterpretable — the conclusion
stands, the stated cause is stale and should be corrected in the CR doc.

Decision (D3): the benchmark harness **mirrors the production vote** — reuse the production
sampling/voting path rather than single draws, so pre/post comparisons measure real product
behaviour.

### c. The data additions belong in this program, sequenced after the contradiction fixes

Per Saiful's ruling, scope extends to data. Ranking from the arms' 102 requests, weighted by
impact evidence:

| Priority | Addition | Cost | Evidence |
|---|---|---|---|
| 1 | **Interest coverage** (op. income ÷ interest expense) | **zero** — bytes already fetched, 6h TTL | #1 request: 21× from 9/12 agents; the Room built an insolvency narrative on CAT's $39.2B without it |
| 2 | **Capex line** | zero — implicit in rendered FCF, discarded | 9× from 4 agents |
| 3 | **Buyback pacing** (4-quarter series) | zero — fetched, summed, thrown away | 4× from 4 agents; complements CR218 |
| 4 | **Historical median multiples** (5/10-yr P/E, EV/EBITDA) | real fetch + cache | **flipped the CAT verdict** — PM's own words: proof 24.5x was mid-cycle "might have" changed PASS to APPROVE |
| 5 | Debt split industrial vs captive finance | SEC segment filings — **decided: build** (D5) | 4/12 + CIO; the Room's central CAT risk thesis rests on a misread of matched-book leasing debt |
| 6 | ATR / volatility for stop sizing | daily bars already fetched — computable | 4×; the Trader must set a stop with no volatility input at all |

Per D2, the #15/#16 short/medium-horizon demands are **backed, not deleted**: earnings
revisions, surprise history and guidance join this list as real fetches (they are not free —
a new data source, cache and fields), which removes the Class-C contradiction by supplying
the data rather than cutting the demand.

Items 1–3 are CR218's exact pattern and cheap. **Item 4 is the highest-value item in the
entire folder** — the only gap with demonstrated verdict impact — and should not wait behind
the free ones. Item 6 is computable from data already in memory and fixes a structural
absurdity (mandatory stop, no volatility measure).

Sequencing rule: **contradiction fixes land first.** Adding fields while personas still deny
existing ones is how CR219 happened; the new guard (Phase 1) must exist before Phase 3 adds
a single field, and each new field ships with its persona line and guard entries in the same
commit.

### d. #17 (`primary_goal` rendered, never branched) — wire it or cut it

Six goal values collected at onboarding, printed into every prompt, changing nothing. For the
stated aim — an answer driven by the user's risk profile — this is the largest single lever
in the folder after the data. Decision needed (§5, D4). If wired: `income_now` should shift
the fundamentals overlay toward dividend cover and capital-return sustainability (the fields
CR218 just shipped); `learning_to_trade` toward explanation. If not wired: delete the printed
line — a rendered-but-inert mandate field is precisely a DEF063-shaped contradiction waiting
for a thinking model to notice.

### e. The guard redesign is under-specified

Scope item 5 says "every negative claim checked TRUE against the rendered sheet, whole-file
scan." Two additions:

1. The guard must also cover the **overlay generator** — #15/#16 are negative-truth failures
   in code, not personas. An authored mapping of overlay demands → field_state keys, same
   pattern as `_CLAIMED_REAL_INPUTS`.
2. Accept and document the guard's own limit: it is an *authored* phrase↔mechanism mapping,
   so a brand-new denial phrase no one mapped stays invisible. That is acceptable — presence
   of the mapping forces the author to reckon with it — but say it in the test docstring so
   CR219's own "snapshot vs moving target" lesson isn't re-learned.

### f. Two open items deserve disposition now

- PM breaking its JSON-only contract under instruction pressure (Open item 3): file as its
  own DEF. Given DEF067's ~13% parser loss, an obedient-to-appendix gatekeeper is a real
  fragility, not a curiosity.
- The 26 unswept prompts (concierge, Brief Your Agent): the sweep is mechanical
  (`dump_sheets.py` + `assemble_room.py` already exist for the Room surface) — extend the
  same scripts rather than writing new ones.

---

## 4. Improved plan

### Phase 0 — diagnostics before edits (½ day)

1. One diagnostic convene on the cached CAT profile at HEAD to settle #13/#14 (which half
   is stale: overlay's pushed size or snapshot's computed size).
2. Class D decision — **taken (D1): name the sheet in the 8 downstream briefs + numbers rule**.
3. Dispositions: file DEF for PM JSON-contract fragility; correct the stale
   "defaults to 1" line in the CR doc's arms section (CR214 raised it to 5 — see §3b).

### Phase 1 — contradiction fixes + guard v2, one commit set

1. Rewrite the 7 false Class-A denials (keep the 3 true ones; #8 per §2's caution).
2. Disambiguate #10's "conviction" collision in vocabulary; fix #11 by bounding the
   date-pairing rule to the consensus-target line it was written about.
3. Fix #12 in `trader.md` (WAIT/HOLD carve-out for Stop), not the regex; land the
   uncommitted `trader_block_regex` hunk alongside it — they are one logical change.
4. Resolve #13/#14 per Phase-0 finding.
5. #15/#16 — **decided (D2): keep the demands, back them with real fetches** (Phase 3).
   Until those fields land, the demand text must be softened to not request what the sheet
   cannot carry — an unbacked demand in the interim is the live Class-C defect.
6. Guard v2 in the **same** commit: negative claims truth-checked against the rendered
   sheet, whole-file scan (fixture: false denial planted in `## Voice` must go red), overlay
   demands mapped to field_state keys. Acceptance #1/#2 as written, plus the overlay mapping.
7. Wire `primary_goal` into the overlays — **decided (D4)**. `income_now` shifts the
   fundamentals overlay toward dividend cover and capital-return sustainability (the CR218
   fields); `learning_to_trade` toward explanation. Guard entries for the new branches.

### Phase 2 — surfaces

1. Class D implementation (per D1) with before/after measurement (one convene pair per arm
   profile, PM vote mirroring production per D3).
2. Class E: lane-gate `build_live_data_block()` on the 1-on-1 surface.
3. Sweep concierge + Brief Your Agent (26 prompts) with the existing scripts, extended.

### Phase 3 — data additions (each its own commit, personas + guard entries included)

In priority order from §3c, with the D2/D5/D6 rulings folded in — **all filed under CR219**:

1. Interest coverage, capex, buyback pacing (free — CR218 pattern).
2. ATR / volatility for stop sizing (computable from fetched daily bars).
3. Historical median multiples, 5/10-yr P/E + EV/EBITDA — **in scope (D6)**; fetch + cache.
4. Earnings revisions, surprise history, guidance — **in scope (D2)**; backs #15/#16.
5. Debt split industrial vs captive finance from SEC segment filings — **in scope (D5)**.
   Scope it to captive-finance-heavy names; if the filings parse proves unreliable, the
   fallback is a documented limitation, not silent omission.

### Phase 4 — benchmark + acceptance

1. Build the benchmark harness (§3a): 4–5 cached profiles, PM voting **mirroring the
   production 5-way path** (D3), rubric.
2. Pre/post run. Success = citation recovery on post-fix Alpha traffic (existing acceptance
   #4) **and** rubric improvement on the fixed profiles with verdict stability measured
   through the same vote production uses.

---

## 5. Decisions — resolved with Saiful, 2026-09-02

| # | Decision | Ruling | Consequence |
|---|---|---|---|
| D1 | Class D — name the sheet in the 8 downstream briefs? | **Name + numbers rule** | Phase 2 item 1 proceeds |
| D2 | #15/#16 short/medium-horizon demand | **Back with real fetches** (against my recommendation to delete) | Earnings revisions / surprise history / guidance become Phase 3 build items; interim softening in Phase 1 |
| D3 | PM sampling | **Benchmark mirrors production's 5-way vote** (production already n=5 via CR214 — the CR doc's "defaults to 1" is stale) | §3b correction; harness reuses the production voting path |
| D4 | `primary_goal` rendered but inert | **Wire it into overlays** | Phase 1 item 7 |
| D5 | Debt split industrial vs captive | **Build the SEC filings source** (against my recommendation to document as limitation) | Phase 3 item 5; documented-limitation fallback if the parse proves unreliable |
| D6 | Historical median multiples | **Filed with CR219** | Phase 3 item 3, no separate CR needed |

## 6. Limits of this review

- I did not re-run a Gemini convene; Class B findings are assessed from source + the stored
  transcripts, not fresh reproduction (Phase 0 exists for exactly this).
- I verified the four analyst personas, the guard, the overlay builder, and the lane/snapshot
  machinery firsthand; the 8 downstream personas I read only as embedded in
  `evidence/convene_CAT_long_wealth/convene.json`.
- The rubric in §3a is a proposal, not a validated instrument; its model-judged halves need a
  calibration pass against the banked corpus before pre/post numbers are trusted.
