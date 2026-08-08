# CR152 — Trader — the agent the parser was written for barely feeds it

**Filed:** 2026-08-08 · **Status:** proposed · **Decision:** Saiful, 2026-08-08 — *"book CRs one for
each agent."* One CR per agent so each remedy is decided on its own evidence rather than bundled.
**Source:** CR143 Phase 1/3b plus two independent reviews of the Trader — a blind prompt-coherence
audit ([`external_review/room/trader.md`](../CR143_agent_prompt_audit/external_review/room/trader.md))
and a codebase-verified data-sufficiency audit
([`external_review/room/kimi/trader_data_sufficiency.md`](../CR143_agent_prompt_audit/external_review/room/kimi/trader_data_sufficiency.md)).
Both processed as **hypotheses**: every claim gated on a supplier check (does the code inject what the
prompt claims?) and a parser check (does anything read the output this instruction shapes?), per
CR105's Amendment 1, where 2 of 4 prompt-only findings were wrong once checked against the parser.

**Corpus.** `corpus/room_runs_2026-08-07-epoch.json` (18 convenes) and
`corpus/llm_audit_2026-08-07-epoch.json` (216 turns with verbatim `system_prompt`), replayed against
HEAD in-session. Every rate below is epoch-scoped with its n stated, and **never pooled by ticker** —
the epoch contains two AMD, two GRAB, two NVDA, two SNDK and two KTOS convenes under *different*
mandate caps, and pooling them is the partition error CR153 already had to withdraw a claim over.

---

## Why

The Trader is the only prose agent whose base prompt (`content/agents/trader.md:21-34`) contains a
code-fenced ticket with line-anchored `Entry:` / `Stop:` / `Target:` labels — and
`_LEVEL_PATTERNS` (`room_runner.py:1151-1155`) was written against exactly that layout. `_PROSE_FORMAT`
(`room_prompts.py:210-215`) then tells the same agent *"no headings, no tables, no code fences"*. That
conflict is **DEF236** (open) and is CR145's to resolve. What is the Trader's own is what the conflict
has left behind, and it is worse than the format story alone predicts.

**Finding 1 — the geometry parser sees almost nothing, and most of what it sees is not a level.**
Replayed over the 18 Trader turns at HEAD:

| `_match_level` | fires | of which a genuine proposed level |
|---|---|---|
| `entry` | 6/18 | **2** (KTOS `$60.65`, BAC `$63.15`) |
| `stop` | 3/18 | 2 |
| `target` | 3/18 | 2 |
| full triple — the only thing `_verify_and_annotate_geometry` acts on | **2/18** | 1 |

The four bad `entry` extractions, with their verbatim match spans:

- AVGO — `'entry signal (RSI **73'` → **entry = 73.0**. An RSI read as an entry price.
- TSLA — `'entry at **$327.27'` → the reference price the Trader is explicitly *refusing* to pay.
- ANET — `'entry at **$188.62'` → same shape (*"Current entry at $188.62 carries a 62% position within
  the 50-day range"* — a description of where price sits, not a proposal).
- SNDK — `'Entry:          $0'` → **0.0**, from a WAIT ticket that fills every field with a placeholder.

And on the AMD convene the reviews were written from, `target` captured **0.00** out of
`'target, creating a **0.00'` — i.e. out of the fabricated `0.00:1.00` ratio string in the very
sentence the reply's thesis rests on.

**The consequence, measured now that DEF235 is fixed:** the epoch's committed transcripts contain
**2** `[AMI verified the trade geometry…]` annotations, **both on the neutral_debator** (AMD, ANET) —
**Trader 0/18. Confirmed, and the reason is precise:** of the Trader's 2 triples, SNDK's
(`0 / 0 / 2116.64`) forms no valid long setup so `risk_reward` returns `None`, and BAC's *is* valid
(0.9:1) but the Trader narrated *"~1:1"*, inside `_annotate_rr_against_levels`' 0.3 tolerance, so
nothing was appended. Nothing misfired — but the one control built specifically for this agent has
never once run on it in this epoch.

**Finding 2 — a narrated ratio with no levels is never examined at all.**
`_annotate_rr_against_levels` is reachable only through a full triple. 2/18 Trader turns contain an
`N:N` ratio; the AMD `0.00:1.00` — the epoch's only fabricated Trader figure, and the one carrying the
whole thesis — matched **neither** gate: `_extract_stated_rr` returns `None` on it, and there was no
triple to reach the check anyway. Separately, BAC's `**R:R**: ~1:1` was not rewritten inline either,
because `_RR_CLAIM_RE` (`:1161`) has no allowance for the `**` bold markers `_PROSE_FORMAT` asks the
same agent to use.

**Finding 3 — `_LEVEL_PATTERNS` has no thousands-separator group, and the Trader is where that lands.**
Recorded by CR151 outside its own scope; **verified live here**:

```text
Entry: $1,507.00   -> entry  = 1.0
Target of $1,073.46 -> target = 1.0
stop at $2,120     -> stop   = 2.0
Entry: $1507.00    -> entry  = 1507.0
```

`_LEVEL_NUMBER` (`:1430`) already carries the alternation — DEF234 added it after *"break above
$1,073.46"* parsed as `$1.00` and the check announced the close was *"107900.0% ABOVE $1.00"* — and
`_direction_contradictions` already strips the separators at `:1661`. `_LEVEL_PATTERNS` was never
updated. **Exposure, measured:** 8/18 Trader turns state at least one ≥$1,000 dollar figure and
**4/18 already write the comma form** (`$19,646`, `$1,507.79`, `$10,000.00`, `$9,453.65`, `$6,782.35`);
4 of 18 convenes are on names whose own 50-day range top exceeds $1,000 (MU $1,254.81, SNDK ×2
$2,354.39, LITE $1,049.53). **The prompt itself supplies both templates**: `_format_profile` renders
prices *without* separators (`Reference price: $1224.51`, `50-day range: $998.19–$2354.39`) while
`_build_sim_holdings_block` renders them *with* (`Cash: $10,000.00 | Portfolio value: $9,462.01`,
`:,.2f` at `room_runner.py:736`). Which one the model copies is luck. **One live turn is one character
away:** SNDK's Trader wrote `Target:         $2116.64`; re-run the identical turn with the comma form
and `target` parses as **2.0**. Latent — **0 live instances in 216 turns** — but it is DEF235's
severity class (a silent 1,000× rescale under *"These are the figures of record"*) in a pattern
DEF235 deliberately left standing.

**Finding 4 — the compliance half of the Trader's job is unverifiable from its own prompt.** Measured
across all 18 Trader prompts:

| the prompt states | what is rendered | n |
|---|---|---|
| `## Inputs`: *"the user's current portfolio + remaining drawdown capacity"* | the phrase; **never a figure** | 18/18 promise · **0/18** value |
| *"Total open-risk cap: X% — the sum of (position size % × stop distance %)/100 across all open positions, including this one"* | positions with qty, weight and unrealised P&L — **no stop on any of them**, no current sum | **0/18** |
| *"Trading pace cap: N per day, M per week"* | no trades-today / trades-this-week count | **0/18** |
| *"Post-loss cooldown: …"* | no last-stop-out timestamp | **0/18** |
| *"Sector-concentration cap: 20.0%"* | no sector allocation (`sector_line` is PM-gated, `room_prompts.py:454`) | **0/18** |
| a concrete stop is demanded (`Stop: ${price}`) | no volatility measure — `trading_math/indicators.py` implements `rsi`/`rsi_tone`/`sma` and nothing else | **0/18** |

The first four are **computed every run and thrown at enforcement only**: `sim.risk_limit_context`
(`sim_engine.py:503-515`) returns `(last_loss_closed_at, trade_open_timestamps,
existing_open_risk_pct)` into `_build_room_risk_limit_context` (`room_runner.py:800-826`), and
`ctx.current_drawdown_pct` (`:290`) goes only to `enforce_safety_floor` (`:3269`). `build_room_messages`
has no parameter for any of them. Every open trade already carries its own `stop`
(`sim_engine.py:111,132`); `_build_sim_holdings_block` (`:752-755`) simply does not print it. **Zero
new fetches** for all four.

**Finding 5 — the base prompt names an input that structurally cannot exist yet.** `## Inputs`
lists *"Risk Debators' arguments"* and `## You DO NOT` says *"Ignore the Risk Debators' arguments —
your size must reflect what they collectively allow"*. `PHASES` (`room_runner.py:144-166`) is
ANALYSTS → RESEARCHERS → SYNTHESIS → **EXECUTION** → **RISK** → VERDICT, and the debators receive the
Trader's phase output through `trade_proposal` (`room_prompts.py:400`), never the reverse. The blind
review killed its own version of this against an empty transcript (the Trader now speaks 8th with the
full synthesis, 18/18) — the deeper version survives.

**Finding 6 — DEF231's direction check would fire on 2/18 Trader turns and is wired to the PM only.**
CR151's hand-off, re-derived here by replaying `_direction_contradictions` against each run's own
structured levels: MU — *"reclaim the **$737.88**"* with the last close **$875.18**, already 18.6%
**above** the support it names; SNDK — *"move above the **$998.19**"* with the close at **$1,212.21**,
21.4% above. Both entered `Transcript so far:` for all three debators and the PM, unannotated.
(conservative_debator 1/18; aggressive, neutral, RM 0/18 — the Trader is the worst offender in the
Room.) The checker is called once, on `verdict.reason`, at `room_runner.py:3342`.

---

## Scope — four tiers, ordered by cost

### Tier A — the base prompt, `content/agents/trader.md` (prompt-only, no code)

Four edits, all cheap, none of them safe to make in isolation — read the sequencing note:

1. **`## Inputs`** — drop *"Risk Debators' arguments"* or restate it truthfully (*"the debators will
   challenge your proposal after you speak — pre-empt them"*). Drop *"remaining drawdown capacity"*
   or let Tier C deliver it; today it is a promise the assembler never keeps (18/18 / 0/18).
2. **`Side: BUY | SELL | HOLD | WAIT`** — `SELL` has no meaning under `long_only`, which the same
   prompt states twice. **Measured not to bite: 0/18 turns proposed a short** (15/18 are WAIT), so
   this is coherence, not a live defect. Correct it while the file is open; do not price it.
3. **`## You DO NOT — Size a position over the cap implied by the user's risk_score`** — reword so it
   does not read as an enforced control. It is not one at this phase (see REJECTED #5).
4. **The fenced `Output structure` block** — both reviews say delete it as noise. Accepted, **but not
   for their reason and not before Tier B.** It is the only place in the assembled prompt that asks
   for the line-anchored layout `_LEVEL_PATTERNS` reads. Delete it while the parser still expects it
   and 2/18 becomes 0/18. It goes when DEF236 has decided what shape the Room wants, and the parser
   has been pointed at that shape.

### Tier B — the thousands-separator group in `_LEVEL_PATTERNS` (one regex; DEF-worthy)

Reuse `_LEVEL_NUMBER`'s alternation in all three patterns and strip separators in `_match_level`,
exactly as `_direction_contradictions` already does at `:1661`. **Guards:** `Entry: $1,507.00` →
`1507.0` asserted on the *value*, not on a substring (a substring assertion is what let DEF235's
11.32 pt ship); plus a replay over all 216 epoch turns asserting **no extraction changes** except the
intended ones — the corpus check DEF234's own row says should precede a pattern fix, not follow it.

Ask the Architect to mint a `DEF###` for this: it is a fix against spec in the DEF235 family, not new
behaviour. Sequenced **before** Tier A.4 and **against** DEF236 — resolving the format conflict is
what decides whether this parser gets more input or none.

### Tier C — render the risk state that is already computed (no new provider, no new fetch)

- Per-position `stop` in `_build_sim_holdings_block`, plus the run's `existing_open_risk_pct` as the
  current sum, so the *"including this one"* arithmetic the prompt demands is actually doable.
- `ctx.current_drawdown_pct`, delivering the `## Inputs` promise.
- Trades-today / trades-this-week and the last-stop-out timestamp, so the pace cap and cooldown are
  checkable rather than narrated.

All four ride values built once per run at `room_runner.py:2921`; `build_room_messages` gains
parameters, nothing gains a provider call.

**A `stop=None` must render as "no stop recorded"**, through the existing `field_state` UNAVAILABLE
pattern (`room_runner.py:337-354`) — `sim_engine.py:560` allows a null stop, and a blank rendering
would tell the Trader the riskiest leg carries zero risk, which is the CR040 failure this project
files defects over.

**Yield is bounded and should be stated when this ships:** 8/18 convenes had an open book (4–5
positions); the other 10 are an empty $10,000 book where the open-risk sum is 0 by construction. No
turn in the epoch demonstrably mis-sized for want of these. This tier ships because the prompt already
makes the claim, not because a failure was measured.

### Tier D — two decisions, not code

- **Sector weights for the Trader.** It carries the 20% sector cap in 18/18 prompts and gets 0/18
  allocations. Measured consequence: **1/18** — the AMD reply's *"adding AMD … merely increases sector
  concentration in Semiconductors"*, which requires knowing NVDA's sector. AMD's sector is on the
  sheet; NVDA's is not. One hallucinated categorical fact in 18 convenes. Belongs with **CR145 Tier C**'s
  per-agent visibility matrix, not as a standalone gate flip.
- **ATR (or any volatility measure) for stop placement.** `compute_technicals` (`technicals.py:75-152`)
  already pulls the daily OHLC through the cached provider, so an ATR is pure math over data in hand —
  no new provider, no new rate-limit exposure. But `_format_profile` takes no `agent_id`, so the field
  lands on all 12 agents, and **15 of 18 Trader turns were WAIT and proposed no stop at all**, so the
  measured demand in this epoch is ~3 turns. Sequence behind CR145 Tier C and re-measure on ≥30
  convenes before building.

---

## What this CR REJECTS, and why

1. **"The `trade_proposal` the Risk Debators and PM reason against is the canned scripted number,
   presented as the Trader's"** (data-sufficiency review §4, wiring finding 1) — **half right, and the
   half that matters is already handled.** `ctx.trader_entry/stop/target/size_pct` *are* set once at
   `room_runner.py:3010-3013` to `base` / `base×0.94` / `base×1.13` / `_risk_tier_size_ceiling(mandate)`
   and never updated from the Trader's reply (verified: the only assignments in the file). But the
   RISK/VERDICT prompt does not attribute them to the Trader — `_drawdown_snapshot_line` renders
   *"Reference position (risk-tier ceiling 3.0% size, entry 188.62, stop 177.30) → …"*, and its own
   docstring states it is *"a DETERMINISTIC reference position … not the live Trader's exact words"*
   (audit D-e). Measured: the line appears in 18/18 debator and 18/18 PM prompts, and **0** of them
   call it a proposal. Nothing to fix there. Likewise `ctx.trader_size_pct` is the mandate's resolved
   single-name cap — DEF235 made it that on purpose; do not "restore" a prose parse for it.
2. **"The PM's `entry` fallback labels a scripted default as `trader` provenance"** — **the code claim
   is true, the impact is zero in this epoch.** `entry_src = "pm" if entry_raw else ("trader" if
   ctx.trader_entry else None)` (`:980`) does write `level_provenance["entry"] = "trader"` for a number
   the Trader never stated. All **3** APPROVEs in the epoch carry
   `{'entry':'pm','stop':'pm','target':'pm'}` — the fallback fired **0/18**. It is a real mislabel in a
   ribbon-gating field with no live instance; worth a small DEF, not a tier.
3. **"The Trader's proposal is never compliance-checked"** (§4, wiring finding 2) — **confirmed as
   fact, rejected as a defect.** `enforce_safety_floor` runs on the PM's parsed APPROVE
   (`room_runner.py:3252`); `check_mandate_compliance` runs in the scripted `_assemble_verdict` only.
   That is the designed gatekeeper split — DEF059 and CR101 make the safety floor the *sole* vetoer,
   and a second clamp at EXECUTION would give one trade two. What is wrong is the *prompt's* framing,
   which Tier A.3 fixes.
4. **"Un-gate the Decision Journal for the Trader"** (§4 row 5) — **rejected on measured yield.** The
   gate is real (`room_prompts.py:382-385`, Bull/Bear only; 0/18 Trader prompts carry the block). But
   CR151 already measured the whole-Room yield of that gap at **1/18**, and the claim in question — the
   Bear's *"prior AMD positions hit stop losses around $502.59"* — was **true and verifiable in its own
   prompt**. Adding ~900 chars to a 15,679-char Trader prompt to re-deliver a fact that arrived
   correctly through the transcript is not a trade worth making now. Revisit on the ≥30-convene
   re-measure.
5. **"Extend the deterministic reference position to the Trader too"** — **rejected**, same root as
   CR151's rejection for the RM. The geometry is invariant per ticker, and the Trader is the one agent
   *asked to choose* the stop. Handing it `base×0.94` is an anchor, not data — and the reviews'
   own complaint is that the system already *models* the fabrication its grounding directive forbids.
6. **"The dual output schema is the Trader's whole problem"** (both reviews' headline) — **partially
   rejected as an explanation.** It is real and it is DEF236's. But 15 of 18 Trader turns were a WAIT
   with no position, and 15 of 18 verdicts were PASS. *"Entry: N/A"* is the honest answer in most of
   this epoch, so the parser's starvation is **not purely** a format conflict, and a fix scoped as if
   it were will over-claim. State both when Tier A ships.

---

## Corrections to figures this CR was handed

1. **`real_samples/trader.prompt.txt` is one of the stale samples — confirmed by exact match.** It is
   byte-identical to corpus turn `406d396e-da51-4170-ba0c-51e75f083a6b` (AMD,
   `2026-08-07T13:34:03Z`), the earliest convene in the epoch. It renders `Recent range:
   $424.03–$584.73` and `trend: trading` — **neither shape HEAD can emit**: DEF228 replaced the range
   line with `50-day range: $X–$Y, last close $Z (N% of that range)` (`_range_line`,
   `room_prompts.py:795-813`) and DEF227 replaced `trading` with `uptrend`/`downtrend`/`consolidating`.
   **The epoch straddles that promotion:** only **2 of 18** convenes (24 of 216 turns — one AMD, one
   GRAB, both before 19:17Z) carry the old shape; the other 16 carry HEAD's. Every reply-side rate in
   this CR is over all 18 turns; every prompt-shape claim is scoped explicitly. Both reviews argue
   their motivating example against a fact sheet that no longer ships.
2. **The stub's *"11 of 16 turns state levels inline, not in the parsed ticket layout"* is not
   reproducible as stated and should not be re-quoted.** That was DEF235's count of "turns stating an
   entry" under a looser reading than `_match_level`. Re-derived at HEAD over the same 18 turns:
   `_match_level(entry)` fires on **6/18**, of which **2** are line-anchored `Entry:` labels and 4 are
   inline prose. Separately, the ticket block survives `_PROSE_FORMAT`'s prohibition on **6/18** turns
   (≥3 label lines) and a literal code fence on **3/18**. The *shape* of DEF235's finding is unchanged
   — the parser depends on a format a later layer forbids — the numbers are not those.
3. **The stub's *"numbers stated that are in neither the fact sheet nor the transcript: 6.7%"*.**
   Re-derived by token presence over the whole `system_prompt` (which contains the transcript):
   **2 of 269 numeric tokens = 0.7%**, n=18. Different instrument, so not a contradiction — but neither
   instrument catches the epoch's only real Trader fabrication, because `0.00` and `1.00` are
   individually present all over the prompt. **For this agent "ungrounded number" is the wrong metric.**
   The characteristic failure is an *unverified derived figure*, and Finding 2 is what measures it.
4. **Confirmed unchanged from the stub:** assembled prompt **15,679 chars**; `_LENGTH_GUIDE[TRADER]` =
   *"3–4 sentences"* against a measured median of **5** and **12/18 (67%)** over budget (the stub's 61%
   is one turn away, a sentence-splitting difference, not a disagreement); bullets **11/18**; stance
   envelope emitted **18/18**; truncation **0/18** (0/216 epoch-wide — the longest Trader turn is
   **1,687 chars ≈ 59%** of its 600-token budget, so every token-scarcity argument in both reviews has
   no current basis).

---

## Acceptance

- **Tier A:** no instruction in the Trader's assembled prompt names an input the assembler does not
  supply, and none reads as an enforced control that is not one. Re-measure over ≥30 convenes:
  over-budget rate (67% today), bullet usage (61%), ticket-block emission (33%), code-fence rate
  (17%), stance emission (100%), truncation (0%). A prompt edit whose effect is not re-measured is the
  CR105 Amendment-1 trap.
- **Tier B:** `Entry: $1,507.00` → `1507.0` asserted on the value; a 216-turn corpus replay shows zero
  unintended extraction changes; the SNDK `$2,116.64` comma variant is a named fixture. Mutation the
  fix (revert the group; drop the `replace`) and both must be killed.
- **Tier C:** the Trader's prompt states the current open-risk sum, per-position stops (or an explicit
  "no stop recorded"), current drawdown, trades today/this week and the last stop-out; **no new
  provider call appears on the convene path** — assert it. Then re-measure: does the Trader ever
  reason about open risk or pace? Zero uptake means the tier bought coherence and nothing more, and
  that should be recorded rather than assumed away.
- **Tier D:** not built until the ≥30-convene re-measure shows the sector cap or the missing stop
  basis actually binding. The 1/18 sector leak and ~3/18 stop demand measured here are not enough.
- `pytest backend/tests/unit/ -q` green throughout.

---

## Notes

- **Ordering.** Tier B is one regex and independent — it can ship alone and should, since it closes a
  silent-rescale class in the same family that already shipped a 63× error. Tier A.4 is *blocked* on
  DEF236. Tier C is a real but modest change to the shared prompt assembler and touches
  `test_prompt_data_parity.py`'s expectations. Tier D is behind CR145 Tier C.
- **Recorded, not scoped here.** DEF231's `_direction_contradictions` would fire on **2/18 Trader**
  turns (Finding 6) and is wired to `verdict.reason` only. Extending it to prose agents is a Room-wide
  decision, not the Trader's — and it must stay flag-only (DEF059 keeps the safety floor the sole
  vetoer). Noted so the measurement is not lost.
- **What could not be verified.** (a) How many open sim trades carry `stop=None` — that needs the live
  melehost database, not the corpus, and it sizes the "no stop recorded" branch in Tier C. (b) Whether
  the Trader's behaviour changed after the DEF227/DEF228 promotion mid-epoch: only 2 convenes sit on
  the old fact sheet, far too few to compare. (c) The reviews' accuracy estimates (*"~85–90%"* /
  *"~60–65%"*) are unsourced and are not adopted anywhere in this CR.

## Cross-cutting items — NOT re-litigated here

Owned by [CR145](../CR145_fundamentals_data_and_lane_discipline/CR145_fundamentals_data_and_lane_discipline.md):
the `_LENGTH_GUIDE` / `_PROSE_FORMAT` / `_STANCE_FORMAT` conflict (**DEF236**, open), `_LEVEL_PATTERNS`
vs the prose format (**DEF235**, fixed), `LearningStyle.QUICK`'s *"terse, tabular"* against *"no
tables"*, and the per-agent fact sheet (`_format_profile` takes no `agent_id`). **DEF237** (the missing
plausibility backstop on entry/stop/target) stays open against its own owner — Finding 3 here is the
adjacent *extraction* bug, not that *backstop*, and fixing either does not close the other.

## Inputs

- Blind prompt-coherence review — [`external_review/room/trader.md`](../CR143_agent_prompt_audit/external_review/room/trader.md)
- Codebase-verified data-sufficiency review — [`external_review/room/kimi/trader_data_sufficiency.md`](../CR143_agent_prompt_audit/external_review/room/kimi/trader_data_sufficiency.md)
- Real prompt + reply — [`real_samples/trader.prompt.txt`](../CR143_agent_prompt_audit/real_samples/trader.prompt.txt) · [`.reply.txt`](../CR143_agent_prompt_audit/real_samples/trader.reply.txt) (see correction 1)
- Assembled prompt, layers labelled — [`assembled/room/trader.txt`](../CR143_agent_prompt_audit/assembled/room/trader.txt)
- Supplier + parser maps — [`PHASE1_ground_truth.md`](../CR143_agent_prompt_audit/PHASE1_ground_truth.md)
