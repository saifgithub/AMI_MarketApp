# CR154 — Conservative Debator: the opener that eats the stance, and the one number this role exists to produce

**Filed:** 2026-08-08 · **Status:** proposed · **Decision:** Saiful, 2026-08-08 — *"book CRs one for
each agent."* One CR per agent so each remedy is decided on its own evidence rather than bundled.

**Source.** CR143 Phase 1/3b, plus two independent reviews of this agent — a blind prompt-coherence
audit ([`external_review/room/conservative_debator.md`](../CR143_agent_prompt_audit/external_review/room/conservative_debator.md))
and a codebase-verified data-sufficiency audit ([`external_review/room/kimi/conservative_debator_data_sufficiency.md`](../CR143_agent_prompt_audit/external_review/room/kimi/conservative_debator_data_sufficiency.md)).
Both are **hypotheses**. Everything below was re-checked against the code and re-measured against the
live corpus (`corpus/llm_audit_2026-08-07-epoch.json`, 216 turns / 18 convenes, each turn carrying its
own verbatim `system_prompt`) before it became scope. Rates are epoch-scoped to 2026-08-07 and state
their n; every one was produced by importing the production function and running it over the real
replies, not by reading them.

**Corpus caveat, stated once.** The same ticker appears in more than one convene with a *different*
mandate: AMD twice (50%/10.0% caps and 30%/3.0%), GRAB twice, KTOS twice, SNDK twice, NVDA twice. Every
figure below is derived per-turn from that turn's own stored prompt. Pooling by ticker is what produced
the withdrawn claim in DEF235's row, and it is available to make again here.

**Second caveat.** 2 of the 18 convenes (13:34 and 15:50 UTC) predate the DEF228 range line and render
`Recent range: $X–$Y` with no `last close`; the other 16 render the current `50-day range: … last close
$Z (P% of that range)`. **The AMD sample both external reviews are built on is one of the two old
ones** — it is not the shipping prompt shape.

## Why

The Conservative Debator is the only agent in the Room whose job description is an *arithmetic*: its
`## Output style` requires it to state *"if X happens, we're down Y%, and that uses up **Z% of our
drawdown cap**"*. Three things are true of that number today.

1. **It is not in the prompt, by construction, and cannot be.** The prompt's grounding directive says
   *"ONLY numbers from the data block above"*. Z is a derivation over a size the agent is choosing. Of
   205 numeric tokens across the 18 turns, **10 (4.9%) appear nowhere in that turn's prompt — and all
   10 are arithmetic on block numbers** (a stop distance, a size proposal, five drawdown
   contributions). **Zero are recalled facts.** The "ungrounded number" metric for this agent is
   measuring its job, not a hallucination.
2. **When the agent does the job, it gets it wrong nearly half the time.** 9 of 18 turns state a
   numeric contribution or cap-consumption figure. **4 of those 9 are wrong** — and one is the exact
   error the mandate paragraph exists to forbid: on KTOS, *"a drop to the $43.09 52-week low would
   trigger a **29%** loss, consuming **29%** of our **50%** portfolio drawdown cap with a minimal
   position"*. That is a stop distance read straight off against a portfolio cap — DEF066's ~20×
   overstatement, live, in the sentence the role exists to write. (The other 3: a units swap `pt` →
   `% of cap` on LITE, a correct 0.555 pt followed by *"which is 3% of our 30% cap"* when it is 1.85%,
   and a 1.17% where the correct figure is 1.14%.)
3. **Nothing checks it.** `_verify_and_annotate_geometry` (`room_runner.py:1851`, called for every
   prose agent at `:3526`) needs a full entry+stop+target triple; **0 of 18** conservative turns state
   one, so it fires **0/18**. `_annotate_direction_against_price` (`:3299`) reads only the PM's
   `verdict.reason`. The one number the Room's capital-preservation voice produces is unread by any
   parser and unverified by any annotation.

Meanwhile the data that would make the arithmetic *meaningful* — how much of the cap is already spent —
is computed on every single run and thrown away:

| named as an input | supplied 0/18 | where it already exists |
|---|---|---|
| current drawdown (`conservative_debator.md:19`) | ✗ | `sim.valuation_snapshot()` → `room.py:188-190` → `start_run` `:203` → `_RoomContext.current_drawdown_pct` (`room_runner.py:2904`). Read only by the safety floor. |
| recent loss patterns (`:19`) | ✗ | `_risk_limit_context` `last_loss_closed_at` (`sim_engine.py:486-489`); the Decision Journal block exists but is Bull/Bear-gated (`room_prompts.py:381-385`). |
| existing open-risk sum | ✗ | `_build_room_risk_limit_context` (`room_runner.py:800-826`) → `ctx.risk_existing_open_risk_pct` (`:2916`); `sim_engine.py:491-500` computes **exactly** the sum the prompt's open-risk cap line defines. Read only by the safety floor. |
| per-position stops | ✗ | `SimTradeRow.stop`; the holdings block renders qty/weight/unrealised only. |
| sector weights | ✗ | `_build_room_sector_context` computes them; `_format_sector_allocation` is PM-gated (`room_prompts.py:453-455`, CR026). |

The prompt states the caps and withholds the current values. That is not a feed gap — **every value is
already inside the run object**, fetched for enforcement. The cost of rendering them is prompt tokens.

There is one live demonstration of what the gap costs. On the BAC convene the Aggressive Debator wrote
*"your existing risk budget (currently **~13%** of the drawdown cap via DIS/HPQ/NVDA)"* — `13` appears
nowhere in that prompt, and the true sum over those holdings is ~1.4 pt. The Neutral then argued
against it: *"Aggressive overstates capital availability by ignoring current open-risk usage."* One
debator invented the missing number and another debated the invention. n=1 convene; recorded as a
demonstration, not a rate.

## Scope — four tiers, ordered by cost

### Tier A — one content file, no code, no blast radius

**A1. The `Open with:` line is costing this agent its parsed stance, and it is measurable to 3/3.**

`conservative_debator.md:23` says *"Open with: \"I'd argue for [smaller / shorter / hedged / wait]\""*.
`_STANCE_FORMAT` (`room_prompts.py:264-277`) says the envelope must be the **"VERY FIRST line"**. Both
cannot hold. `parse_stance_envelope` (`room_runner.py:1743`) inspects only the first and last non-blank
line (`:1761-1763`) with an **end-anchored** tail fallback (`_STANCE_TAIL_RE`, `:1713-1718`), so an
envelope on line 2 is **neither parsed nor stripped**: the stance is lost *and* the raw machine line
ships to the user.

Measured, and the split is total:

| | n | stance parsed |
|---|---|---|
| turns leading with the envelope | 15 | **15/15** |
| turns leading with `I'd argue for …` | 3 | **0/3** |

**3/18 (16.7%)** of this agent's turns land in CR106's *"did not state a view"* gutter having stated
one, and **1/18** shipped the raw `[STANCE: against | CONVICTION: high | HEADLINE: 0.1% FCF Yield]`
line into the LITE transcript — verified in `room_runs_2026-08-07-epoch.json`, not inferred from the
reply text. All 18 turns contain the opener; the model resolves the conflict in the envelope's favour
15 times and in the profile's favour 3 times.

Control: **0 of 144** turns from the eight non-debator prose agents lose a stance. Exactly the 3 base
prompts carrying an `Open with:` line lose stances (10/54 debator turns, 18.5%) — this agent's slice of
the finding CR153 (Aggressive) and CR155 (Neutral) carry. **Fix all three in one edit.** Reword rather
than delete: *"After the stance line, open your prose with …"* keeps the role's voice and removes the
line-1 collision.

**A2. Two `## Inputs` promises that cannot be kept, and one rule that cannot be followed.**

- *"Neutral Debator's argument"* (`:18`) — `PHASES` RISK order is aggressive → conservative → neutral
  (`room_runner.py:160-164`), sequential. The Neutral has not spoken. **Structural, not a feed gap.**
  Cut the line; do not reorder the phase (the order is the debate's design).
- *"current drawdown, and any recent loss patterns"* (`:19`) — **the stub's assertion survives, with a
  correction to its wording.** The phrase "current drawdown" appears in 18/18 prompts, but only as this
  promise; no *value* is rendered anywhere. `build_room_messages` takes no such parameter.
  `_drawdown_snapshot_line` (`room_prompts.py:280-318`) renders the **cap** and a deterministic
  reference position — never the current figure. Loss history reached the debator in **1 of 18**
  convenes and only second-hand, as the Bear's paraphrase of a journal entry it can see and the
  debator cannot (*"the decision journal shows prior AMD positions hit stop losses around $502.59"*).
  Either supply them (Tier B) or cut the promise. **Do not cut before deciding Tier B** — the promise
  is the only record of what this role was designed to reason from.
- *"Recommend against trades that the user's risk_score clearly supports"* (`:32`) — no threshold
  mapping risk_score → "clearly supports" exists anywhere in the codebase; only the resolved cap is
  surfaced. Unfollowable as written, and it points the wrong way for a capital-preservation voice. Cut
  or operationalise against the resolved cap.

**A3. The canned worked example contradicts the cap it is attached to, in the same sentence.**

`overlay_generator.py:90-91` hard-codes *"(e.g. 5% size, 20% stop → 1.0 pt, i.e. 1/30th of a **30%
cap**)"* into `_mandate_common_block` — interpolated into the bullet that has just stated *"Max
acceptable drawdown: **50%**"*. Present in **18/18** prompts; the mandate's cap is **not 30 in 8/18**
(7× 50, 1× 100). Interpolate `mandate.max_drawdown_pct` or drop the parenthetical.

Cross-cutting (all 12 agents see it) but scoped here deliberately: this is the only agent instructed to
compute a fraction of that cap, and it is the agent measured getting the fraction wrong.

### Tier B — render what the run already computed (zero new provider calls)

Thread `ctx.current_drawdown_pct` and `ctx.risk_existing_open_risk_pct` into `build_room_messages` and
render both in the mandate snapshot, under the **same RISK/VERDICT gate** `_drawdown_snapshot_line`
already uses (`room_prompts.py:400-401`). Two parameters, two lines. No fetch, no cache, no TTL, no
new Yahoo/Reddit exposure — both values are already in `_RoomContext` before the first agent speaks.

Three constraints on the render, all load-bearing:

1. **Preserve the sentinel.** `_build_room_risk_limit_context` returns `CONTEXT_NOT_SUPPLIED` / `None`
   on any failure *precisely so* an unset limit blocks loudly rather than reading as "zero open risk"
   (`room_runner.py:810-826`). A renderer must print "unavailable this run", never omit the line — the
   CR040 rule, same as the holdings block.
2. **Say what the sum counts.** `_risk_limit_context` skips open trades with `stop is None`
   (`sim_engine.py:493`). A figure labelled "your total open risk" that silently excludes stopless
   positions is the next confidently-wrong number. Label it: *"across open positions carrying a stop"*.
3. **Per-position stops are a separate decision.** Rendering the sum makes the cap reasonable-about;
   rendering each position's stop makes it *derivable*, at more tokens in every one of the 12 prompts.
   The sum is the cheap 80%.

Same tier, one deliberate non-decision: `_format_sector_allocation` is PM-gated (CR026) while the
sector-concentration cap is narrated to all 12. A stated cap with no weights behind it is not a stable
resting place — either the debators get the weights or the cap line leaves their block. Flagged, not
decided here; it is identical to CR153's Tier B item and should be decided once.

### Tier C — pick ONE output spec for this agent

Three specs are live at once and the agent obeys none of them fully:

| spec | source | measured |
|---|---|---|
| 4-part analysis (opener, downside scenario, quantification, protective measure) | `conservative_debator.md:21-26` | quantification present 9/18 |
| *"Write 2 sentences (size cap + one-line reason)"* | `_LENGTH_GUIDE` (`room_prompts.py:77`) | **18/18 over budget**, median 3.5 sentence-units |
| *"thesis, then short bullet points"* | `_PROSE_FORMAT` (`:210-215`) | bullets **16/18 (89%)** |

**The generic three-layer conflict is DEF236 / CR145 Tier B and is not re-litigated here.** What is
specific to this agent is the *decision*: its 4-part block is the role's actual value, and the measured
output already sits at 3–4 units. Recommendation: **keep the 4 parts, retire the 2-sentence guide for
this agent, re-derive its `_AGENT_MAX_TOKENS` from measured output** (median reply 612 chars, max
1,132 — the 600-token budget is not binding). DEF236 lands the mechanism; this CR supplies the
per-agent answer it needs.

### Tier D — policy, needs Saiful

Widen the Decision Journal gate (`room_prompts.py:381-385`) to the debators. This is not a gate flip:
the block is plan-retention-gated (DEF054/055) and Bull/Bear-only by design, and giving the debate loss
history changes what the debate is allowed to know. It is also the only source that would make
*"recent loss patterns"* real. Decide before Tier A cuts the Inputs line.

## Acceptance

Every baseline below is re-measured **post-promotion** on a fresh epoch. A prompt edit whose effect is
not re-measured is the CR105 Amendment-1 trap.

- **Tier A1:** conservative stance-null **3/18 → 0**; leaked raw envelope **1/18 → 0**; opener still
  present in the prose. Re-measured alongside CR153/CR155 so all three debators move together.
- **Tier A2/A3:** no `## Inputs` entry names a datum the prompt does not carry; the drawdown bullet's
  worked example quotes the mandate's own cap in **18/18** prompts (today 10/18).
- **Tier B:** current drawdown and existing open risk render in every RISK/VERDICT prompt; a forced
  `CONTEXT_NOT_SUPPLIED` renders a visible "unavailable" line and never silence; `pytest
  backend/tests/unit/ -q` green, and `test_config_compose_parity.py` untouched (no new env).
- **The one that matters:** the wrong-cap-consumption rate falls from **4/9 numeric attempts**, and
  **zero** turns compare a stop distance directly against the portfolio cap (today 1/18 explicitly,
  3 more qualitatively). This is a hand-read of ≥30 convenes; there is no parser to automate it.
- **Tier C:** over-budget and bullet rates re-measured for this agent specifically (today 100% / 89%)
  so a Tier C effect stays separable from CR145 Tier B's.
- Ungrounded-token rate re-measured (today 10/205 = 4.9%) with the derived/recalled split reported
  separately — a rise in *recalled* tokens is the regression; a rise in *derived* ones is the agent
  doing more of its job.

## What I rejected, and the evidence that killed it

**1. "1.17% is irreproducible arithmetic — no combination of stated numbers yields it"** (kimi §7, the
review's headline reply finding). **Withdrawn.** Under the mandate's own P×S/100 formula the agent's
own proposal gives 4.0% × 14.218% ÷ 50 = **1.14% of the cap**. The model wrote 1.17%. That is a
**0.03 pp slip inside the correct formula**, not a fabricated number wearing the formula's costume —
the same class as its correct `-14.2%` derivation two clauses earlier. The reply's real defects are
elsewhere: the missing stance (A1) and the directional sentence (rejection 5). Over-stating this one
would have aimed the fix at hallucination when the problem is arithmetic discipline.

**2. "5.4% of numbers appear in neither the fact sheet nor the transcript"** (seeded in the stub) as
evidence of hallucination. **Re-derived and reframed.** The rate is **10/205 = 4.9%** (the difference
is tokenizer normalisation), and hand-reading all 10 shows **10/10 are arithmetic derived from block
numbers, 0 are recalled facts**. This agent's grounding is clean. Reported as a bare percentage the
metric would have justified tightening a grounding directive that is already being obeyed.

**3. "Prompt size 17,778 chars."** That is the single AMD sample. Median over 18 is **17,113**
(15,530–19,160). Kept as the sample's figure, not the agent's.

**4. The blind review's §2d — "the 5.0% reference position contradicts the 3.0% single-name cap."**
**Does not occur.** In **18/18** prompts the reference position's size equals the narrated single-name
cap exactly, because both read `resolved_single_name_cap_pct` (`room_runner.py:663-672` and
`overlay_generator.py:519-524`). The blind review's corpus predates the CR101/DEF066 resolver.

**5. Filing the directional confusion (*"If AMD **reclaims** the $424.03 support floor"* while price
sits 14% above it) as a new defect.** Real, and running production's own `_direction_contradictions`
over the 18 replies with each run's structured levels trips **1/18** — that sentence. But
`_annotate_direction_against_price` is scoped to the PM's `verdict.reason` by DEF231's own design, and
that convene is one of the two pre-DEF228 runs whose profile may not have carried `last_close` at all
(I substituted Reference price as the close to get the measurement — a disclosed substitution). One
instance, on the old prompt shape, against a guard whose scope was a deliberate decision. **Recorded as
a candidate for widening the DEF231 check past the PM, with the 1/18 number attached — not scoped.**

**6. The `entry` pattern reading a size percentage as a price.** Real: `_match_level(body, "entry")`
returns **4.0 / 1.5 / 5.0** on 3 of 18 conservative turns (*"Cap the initial entry at **4.0%**"*).
**Already filed — DEF237 names this exact AMD instance.** No new ID. Note for whoever fixes it: on this
agent it is latent, because no turn states a target and `risk_reward`'s ordering check rejects
`stop > entry`. Both guards are luck, which is DEF237's whole argument.

**7. The 100.0% single-name cap in 7 of 18 prompts as a defect.** It is an explicit
`mandate.single_name_cap_pct` override — the risk-tier presets top out at 4.5% — and
`safety_floor.single_name_cap_pct` reads the *same* resolver (CR129), so shown == enforced holds. Not a
prompt defect. Whether such a mandate should be issuable at all is recorded in CR153 as a
mandate-configuration decision for Saiful.

**8. The SNDK turn *"a 6% stop … consumes 6 percentage points of our 50 point drawdown cap"* as an
instance of the forbidden comparison.** It reads like one, but that run's reference position is
100.0% size and the prompt's own line says *"contribution ≈ **6.00 pt** of the 50 pt cap"* — the figure
is correct and copied. Only the KTOS turn is a genuine instance. Counting both would have doubled the
headline rate on a coincidence.

**9. "The Conservative never engages the Aggressive"** (kimi §7, engagement duty). Directionally
supported — **0 of 18** turns name the Aggressive Debator (1 names the Neutral, 3 the Bear) — but
naming is a weak proxy: a turn can engage an argument without citing its author. I did not build a
semantic measure. Kept the DO-NOT rule; recorded that **nothing measures or enforces it**.

**10. Cross-cutting items owned elsewhere, not re-litigated:** the `_LENGTH_GUIDE` / `_PROSE_FORMAT` /
`_STANCE_FORMAT` conflict (DEF236) and `LearningStyle.QUICK`'s *"terse, tabular"* against *"no tables"*
and the per-agent fact sheet (`_format_profile` takes no `agent_id`) → **CR145**. DEF235 (the `size`
prose-parse) is **FIXED** — `size` now comes from `ctx.trader_size_pct`. DEF237 is open.

**11. One mis-cited cap, already recorded.** On the GRAB convene this agent wrote *"we preserve the
**10%** single-name cap"* against a mandate stating **100.0%** — 1 wrong out of 12 cap citations in the
epoch. It is the dropped-zero shape DEF235's correction paragraph already catalogues across
neutral/bull/trader/conservative. Cited, not re-filed.

## What I could not verify

- Whether the 2 pre-DEF228 convenes carried `last_close` in their profile. The corpus stores prompts
  and replies, not profile dicts, so the direction-check measurement in rejection 5 rests on a stated
  substitution.
- Whether widening the journal gate to the debators changes any plan-retention obligation (DEF054/055).
  That is a product decision, not a code fact.
- Whether the 4-part `## Output style` block produces *better* risk reasoning than the 2-sentence
  guide. The corpus cannot answer it — no convene ran with only one spec active.
- n=18 is one epoch and one day. Every rate here should be read as a strong signal with a wide interval,
  not a settled statistic; the 3/3-vs-15/15 stance split is the only finding whose mechanism is proven
  in code independently of its rate.

## Notes

Tier A is one content file plus one f-string and can ship alone — but A1 must ship in the same commit
as CR153's and CR155's identical edits, or the debators' stance rates move for three different reasons
at once and none of the three acceptances is readable. Tier B is the cheapest substantive change in
this review chain: two parameters and two render lines, no provider, and it is the only tier that makes
the agent's mandated arithmetic mean anything. Tier C waits on DEF236. Tier D waits on Saiful.
