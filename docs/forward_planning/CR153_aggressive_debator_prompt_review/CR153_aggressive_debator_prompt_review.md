# CR153 — Aggressive Debator: the opener that eats the stance, and a hard floor with no numbers behind it

**Filed:** 2026-08-08 · **Status:** proposed · **Decision:** Saiful, 2026-08-08 — *"book CRs one for
each agent."* One CR per agent so each remedy is decided on its own evidence rather than bundled.

**Source:** CR143 Phase 1/3b plus two independent reviews of this agent — a blind prompt-coherence
audit ([`external_review/room/aggressive_debator.md`](../CR143_agent_prompt_audit/external_review/room/aggressive_debator.md))
and a codebase-verified data-sufficiency audit ([`external_review/room/kimi/aggressive_debator_data_sufficiency.md`](../CR143_agent_prompt_audit/external_review/room/kimi/aggressive_debator_data_sufficiency.md)).
Both are **hypotheses**. Everything below was re-checked against the code and against the live
corpus before it became scope, per CR105 Amendment 1.

**Corpus:** [`corpus/llm_audit_2026-08-07-epoch.json`](../CR143_agent_prompt_audit/corpus/llm_audit_2026-08-07-epoch.json)
— 216 real Alpha turns, 18 per agent, one epoch (2026-08-07), plus
[`corpus/room_runs_2026-08-07-epoch.json`](../CR143_agent_prompt_audit/corpus/room_runs_2026-08-07-epoch.json)
(18 convenes, 15 PASS / 3 APPROVE). **n=18 convenes.** Every rate below was computed against those
files in the same session; none is carried over from an earlier document.

---

## Why

Two problems, and the same shape underneath both: **this agent's base prompt asks it to do things the
Room's assembly does not let it do, and the failures land in the two places that cost something — the
machine channel the UI reads, and the compliance sentence the user believes.**

1. **Its first output-style rule fights the stance envelope for line 1, and the parser loses.**
   `content/agents/aggressive_debator.md:23` says *"Open with: \"I'd push for [bigger / longer /
   less hedged]\""*. `_STANCE_FORMAT` (`room_prompts.py:264`) says the envelope *"must be this one
   line"*, *"your VERY FIRST line"*. The model satisfies both by writing the opener on line 1 and the
   envelope on line 3 — and `parse_stance_envelope` (`room_runner.py:1728`) only inspects the first
   and last non-blank line, with a tail-anchored fallback. An envelope in the middle is **neither
   parsed nor stripped**: the stance is lost *and* raw `[STANCE: … | CONVICTION: … | HEADLINE: …]`
   ships into the transcript and onto the user's screen.

   Exactly three of the twelve base prompts carry an `Open with:` line — `aggressive_debator.md:23`,
   `conservative_debator.md:23`, `neutral_debator.md:23`. Those are exactly the three agents that lose
   their stance:

   | agent | envelope not on line 1 | stance lost | raw envelope shown to user |
   |---|---|---|---|
   | aggressive_debator | 1/18 | **1/18** | **1/18** |
   | conservative_debator | 3/18 | **3/18** | 1/18 |
   | neutral_debator | 6/18 | **6/18** | 2/18 |
   | the other 8 prose agents (144 turns) | 0/144 | **0/144** | 0/144 |

   10 of 54 debator turns (18.5%) versus 0 of 144 elsewhere. The `Open with:` line is the only prompt
   layer that differs. The Portfolio Manager's 18/18 is excluded throughout — it is deliberately not
   given `_STANCE_FORMAT` (`room_prompts.py:390-395`), not a failure.

   This is `failure_patterns` **P4** — contradictory instruction sets across prompt layers — but
   unlike DEF236 the cost is not verbosity. CR106's collapsed transcript renders a null stance in the
   *"did not state a view"* gutter, which is a lie about an agent that stated one emphatically, and
   the leaked bracket line is machine syntax inside what CR106 calls a quotation. DEF147 fixed this
   defect class once by moving the envelope to the front; the base prompt puts something in front of
   the front.

2. **Its role guidance states a HARD CONSTRAINT keyed on a number the prompt never supplies, and when
   the agent needed that number it invented one.** `_aggressive_block` (`overlay_generator.py:415-427`)
   emits *"HARD CONSTRAINT: a position's portfolio-drawdown contribution (size% × stop-distance%)
   **plus existing drawdown** cannot exceed {max_drawdown_pct}%"*. `build_room_messages`
   (`room_prompts.py:321-335`) has no `current_drawdown_pct` parameter, no `existing_open_risk_pct`
   parameter and no pace-count parameter. All three exist on the run and are enforced downstream; none
   reaches the prompt. On the BAC convene the agent wrote:

   > *"your existing risk budget (currently **~13%** of the drawdown cap via DIS/HPQ/NVDA) easily
   > supports a **5.0%** position at the **60.0%** total open-risk limit"*

   The string `13` appears nowhere in that prompt, and the holdings block renders weight and unrealised
   P/L only — **no per-position stop distance is supplied anywhere**, so existing open risk is not
   derivable at any precision. This is `failure_patterns` **P5** — the LLM asked to compute a number it
   presents as fact — inside the one paragraph whose entire purpose is a safety floor. It entered the
   transcript. In this instance it did not change the verdict (the PM approved 4.0% on its own
   arithmetic), but n=1 is not a control.

**A correction this CR is built on.** The CR153 stub's headline evidence — *"cited a 100% single-name
cap on KTOS while its own prompt said 3.0%"* — **is a misattribution and is withdrawn.** There are two
KTOS convenes in this epoch. The turn quoting *"the **100%** single-name cap … the **60%** total
open-risk cap"* ran against a mandate whose prompt states `Single-name position-size cap: 100.0%` and
`Total open-risk cap: 60.0%`. Both figures are correct. The same holds for the SNDK *"50% drawdown
cap"* against a prompt stating `Max acceptable drawdown: 50%`. See **R1** below for the measurement
that replaced it — and for the four genuine cap mis-citations it turned up in other agents.

---

## Verified findings

Each carries the supplier check (does the code inject what the prompt claims?) and the parser check
(does anything read the output this instruction shapes?).

### F1 — The opener displaces the stance envelope past the parser's reach

- **Supplier:** `content/agents/aggressive_debator.md:23` is unconditional; `_STANCE_FORMAT` is
  appended for all eleven prose agents (`room_prompts.py:390-395`). Both are in every assembled prompt,
  ~150 lines apart, and they compete for the same physical line.
- **Parser:** `parse_stance_envelope` (`room_runner.py:1728-1790`) scans `filled[0]` and `filled[-1]`
  only; the `_STANCE_TAIL_RE` fallback requires the envelope at the end of the text. Run over the real
  corpus, the AMD sample returns `stance=None, conviction=None, headline=None` and leaves
  `[STANCE: for | CONVICTION: medium | HEADLINE: 22.9% upside to $608.23]` sitting in the body.
- **Measured:** table above. Follow rate of the opener itself: **18/18**. The base prompt wins the
  collision every time.
- **Not DEF147.** DEF147's split find/strip already tolerates a malformed envelope — 3 of 18
  aggressive turns emit one with no closing `]` and all three parse cleanly. Position, not syntax, is
  what defeats it.

### F2 — The HARD CONSTRAINT's inputs are computed per run, enforced downstream, and never rendered

| input | computed | reaches enforcement | reaches the prompt |
|---|---|---|---|
| current portfolio drawdown | `SimEngine.valuation_snapshot` → `api/room.py:188` → `_RoomContext.current_drawdown_pct` (`room_runner.py:2882`) | `room_runner.py:1900`, `:3177` → `enforce_safety_floor` | **no** |
| existing open-risk sum | `_build_room_risk_limit_context` (`room_runner.py:800-826`) → `SimEngine.risk_limit_context` (`sim_engine.py:503-515`) | same two call sites | **no** |
| trade pace counts (day / week) | same context tuple (`room_runner.py:2864-2869`) | same | **no** |
| sector weights | `_build_room_sector_context` (`room_runner.py:774-798`) | safety floor | **PM only** — `_format_sector_allocation` gated at `room_prompts.py:453-455` (CR026) |

**Zero new provider calls.** All four are already built once per run for `enforce_safety_floor`;
rendering them adds no fetch, no rate-limit exposure and no cache requirement. That is the whole
difference between this and CR145 Tier D.

Measured consequence, 18/18 convenes: the prompt states a 20.0%/40.0% sector cap and supplies sector
weights **0/18**; states a pace cap and supplies counts **0/18**; states a total open-risk cap and
supplies the running sum **0/18**.

### F3 — The `## Inputs` list names two agents that have not spoken, in 18 of 18 convenes

- **Supplier:** the RISK phase is sequential and ordered `aggressive → conservative → neutral`
  (`room_runner.py:160-164`; `_Phase.parallel` defaults `False` at `:142`, and
  `test_cr077_phase_parallelism.py` asserts the parallel set is exactly `{ANALYSTS}`). No data change
  can supply the Conservative's or the Neutral's argument at this turn.
- **Measured:** the transcript at the aggressive turn ends at `[trader]` in **18/18**. Compliance with
  *"Address the Conservative's specific concerns — don't strawman"* (`aggressive_debator.md:25`):
  **0/18** — no reply mentions the Conservative at all. The instruction's only available failure mode
  is the one it forbids.

### F4 — The opportunity-cost template shipped its own placeholder to a user

`aggressive_debator.md:24` supplies the literal sentence *"If we sit at half-size and the thesis plays
out, we leave X% on the table"*. On the LITE convene the model emitted it **verbatim, with `X%`
unsubstituted**, as its opening body sentence. **1/18.** The blind review predicted this failure as
*hallucinate a number for X*; what actually happened is worse in kind and better in consequence — the
template is a fill-in-the-blank the grounding directive forbids filling when no target price exists,
so the model correctly refused to invent and shipped the blank.

The template is followable when `analyst_target_price` is live (`room_runner.py:351-354`, rendered by
`_analyst_line`, `room_prompts.py:858-872`) and unfollowable when it is a provider gap. It never
degrades.

### F5 — Where the agent leaves the handed reference size, its own risk arithmetic is unverified and sometimes wrong

DEF066 hands this agent a pre-computed figure via `_drawdown_snapshot_line` (`room_prompts.py:280-318`)
for exactly one size: the risk-tier ceiling. Its job is to argue about size.

- 10 of 18 turns state a drawdown or open-risk contribution figure.
- **7/10 restate the handed reference figure** (`0.18 pt` on the 3.0%-cap runs) and are correct.
  DEF066 works where it reaches.
- **4 turns name a size other than the handed reference** (7%, +5% on top of 9.4%, 5.0%, 100%).
  Of those, one derives correctly (TSLA: `7 × 6 / 100 = 0.42` ✓), one is wrong by exactly 2×
  (NVDA: *"14.4%, contributing ~**1.73** percentage points … assuming a 6.0% stop"*; `14.4 × 6 / 100
  = 0.864`), one is the fabricated BAC figure (F2), one states no figure at all.
- **Parser:** nothing checks it. `_verify_and_annotate_geometry` (`room_runner.py:1836-1850`, called
  for every agent at `:3469`) requires a full entry+stop+target triple; **0/18** aggressive turns state
  one, so it fired **0/18**. `_annotate_direction_against_price` has one call site
  (`room_runner.py:3242`) and reads only the PM's `verdict.reason`. No control reads a debator's
  numbers.

Whole-turn grounding, re-derived: **211 numbers stated across 18 turns, 5 absent from their own
prompt = 2.4%** (CR143's 4.9% used a stricter fact-sheet-only match; both are cited, neither is
disputed). Hand-classified, the five are: three correct derivations from supplied figures, one
arithmetic error, one fabrication. **The two bad ones are both risk figures.** The agent is
disciplined about market facts and loose about the numbers that describe the user's own book — which
is precisely the half the prompt never gives it.

---

## Rejected claims and why

The reviews are hypotheses. These did not survive.

### R1 — REJECTED: *"it cites risk caps that contradict its own prompt"* (the stub's headline finding)

Withdrawn as a misattribution — two KTOS convenes, the quote matched to the wrong one (see Why).
Replaced with a measurement. Every `<number>% <cap-name> cap` claim in all 216 turns was extracted and
compared against that turn's own resolved mandate value:

| agent | cap citations | mis-cited |
|---|---|---|
| **aggressive_debator** | **13** | **0** |
| neutral_debator | 14 | 1 |
| bull_researcher | 12 | 1 |
| trader | 12 | 1 |
| conservative_debator | 10 | 1 |
| research_manager / PM / bear / 4 analysts | 35 | 0 |

**The Aggressive Debator is the cleanest cap-citer in the Room: 13 citations, 0 wrong.** The agent
whose entire job is to push sizing to the limit is the one that quotes the limit correctly.

The four real mis-citations are all the same error on the same two runs: *"10% single-name cap"*
against a mandate stating `100.0%` — a dropped zero, on the mandates where the cap is so wide it does
not read as a cap. Worth a control; **not this agent's, and not this CR's** (Tier C).

### R2 — REJECTED: *"risk-tier ceiling 5.0% contradicts the 3.0% single-name cap"*

An audit-fixture artifact, exactly as the brief warned. Verified twice:

- **By measurement:** 72 of 216 assembled prompts carry both numbers. **72 agree, 0 disagree.**
- **By construction:** the reference ceiling is `ctx.trader_size_pct = _risk_tier_size_ceiling(mandate)`
  (`room_runner.py:2913`, `:663-672`) and the narrated cap is `_max_position_pct(mandate)`
  (`overlay_generator.py:519-524`). Both are one call to
  `resolved_single_name_cap_pct(risk_score, single_name_cap_pct)`. They cannot diverge in production.

Do not re-file. This is CR046's "shown == enforced" invariant holding.

### R3 — REJECTED: *"the reference position mis-attributes the Trader's stop"* (kimi gap #7)

Real risk in general, **not realised for this agent, and not a defect for this agent.** The reference
position is the cap-sized position — which is precisely the position this agent's role tells it to
advocate — so for the Aggressive Debator the reference is the *right* anchor, not a foreign one.
Measured: **0/18** turns attribute the reference entry or stop to the Trader; the 7 turns that restate
`0.18 pt` all attach it to the size *they* are arguing for. (The Trader was WAIT-or-against in 14/18
while the reference is handed at full cap in 18/18 — that asymmetry is a genuine reading trap for the
**Conservative** and **Neutral** debators, whose job is to argue for less. Route it there.)

### R4 — REJECTED: *"the safety floor doesn't enforce the hard floor on this agent"*

Correct as an observation, wrong as a defect. `append_safety_floor` no-ops for every agent except the
PM (`safety_floor.py:158-162`) **by design** — DEF059's rule is that the safety floor is the sole
vetoer, and a debator's argument is not a trade. Adding enforcement here would put a second vetoer in
the Room. What is wrong is not the placement of the enforcement; it is a prompt that asserts a
checkable hard floor while withholding half of the comparison (F2). Fix the data, not the floor.

### R5 — REJECTED: *"cut the caps from the mandate block"* (blind review §5)

The blind review's remedy for its own unfollowable-items list was to delete the caps. The supplier
check inverts it: all four figures are already computed per run and enforced downstream, so the caps
are not aspirational — they are live and binding. Deleting them would leave an agent arguing for size
with no ceiling in view. Supply the data (Tier B).

### R6 — REJECTED as live: `_LEVEL_PATTERNS` mis-matches on this agent's turns

Real but **latent, and owned by DEF235.** `_match_level(text, "size")` matched 5 of 18 aggressive
turns and at least 4 matches are wrong — `44.0` from *"half-size with a 44% upside"*, `6.0` twice from
*"3.0% size × 6.0% stop"*, and `1212.21` from *"full-size BUY at $1212.21"* (a share price read as a
position size — DEF235's exact 63× shape). None of them fires, because `_verify_and_annotate_geometry`
requires a full entry+stop+target triple and **0/18** turns state one.

Recorded here as a **constraint on DEF235's fix**, not as scope: any change that relaxes the triple
requirement, or that widens the size pattern to catch the Trader's inline prose, starts publishing
these. Cross-reference, don't re-solve.

### Not re-litigated — owned by [CR145](../CR145_fundamentals_data_and_lane_discipline/CR145_fundamentals_data_and_lane_discipline.md)

`_LENGTH_GUIDE`/`_PROSE_FORMAT`/`_STANCE_FORMAT` length conflict (**DEF236**), `_LEVEL_PATTERNS` vs
the prose format (**DEF235**), `LearningStyle.QUICK`'s *"terse, tabular"* against *"no tables"*, and
`_format_profile(profile)` taking no `agent_id`. This agent's share of DEF236, re-measured for the
baseline: guide **2 sentences**, median **3**, **56%** over budget (10/18), **39%** bullets (7/18),
assembled prompt **15,296 / 16,644 / 18,637** chars (min/median/max), reply median **601** chars.

---

## Scope — three tiers, ordered by cost

### Tier A — one content file, no code, no blast radius outside this agent

Edit `content/agents/aggressive_debator.md`:

| line | today | change |
|---|---|---|
| 23 | `- Open with: "I'd push for [bigger / longer / less hedged]"` | **Delete**, or restate as a *voice* note that cannot claim line 1 (*"lead the argument with the size you want"*). It is the sole cause of F1 and it is followed 18/18. |
| 17–18 | `- Conservative Debator's argument` / `- Neutral Debator's argument` | **Delete or restate**: *"you speak FIRST in the RISK phase — anticipate the capital-preservation case, do not quote it."* Structurally absent 18/18. |
| 25 | `- Address the Conservative's specific concerns — don't strawman` | **Rewrite** against a case that exists at this turn. 0/18 compliance today. |
| 24 | `we leave X% on the table` | **Condition or drop the literal placeholder.** It shipped unsubstituted 1/18. |
| 40 | routing to Conservative / Neutral "when asked something you can't answer" | Low priority; this agent is never asked. Fold into the same pass. |

Free, reversible, and it is the change that recovers a machine field the UI already renders.

### Tier B — render what is already computed (render-only, zero new provider calls)

Thread `current_drawdown_pct` and `existing_open_risk_pct` (and, if cheap, the pace counts) into
`build_room_messages` and render them in the RISK/VERDICT mandate snapshot, next to
`_drawdown_snapshot_line`. Requirements:

- **Loud degrade (CR040).** `_build_room_risk_limit_context` returns `CONTEXT_NOT_SUPPLIED` on
  failure and blocks loudly at the enforcement site; the render site must mirror that — *"existing
  open risk unavailable this run"*, never an omitted line. Silence here is exactly the DEF059 shape.
- **Charge == render.** The enforcement path and the prompt must read the same per-run snapshot, so
  the debator argues against the numbers the PM is vetoed against.
- **Decide the sector line deliberately.** The debator block states a sector cap while
  `_format_sector_allocation` is PM-gated (CR026, a deliberate gate). Either widen the gate to the
  RISK phase — partially reversing CR026, a design decision, not an oversight fix — or drop the
  sector-cap line from the debator mandate block. Leaving a stated cap with no weights is the status
  quo and is not an option.
- **Blast radius:** the mandate snapshot is shared by every RISK and VERDICT prompt, so this
  lengthens four agents' prompts, not one. Interacts with DEF236's transcript-inflation argument.

### Tier C — cross-agent, recorded here because this is where it was measured; **needs its own ID**

1. **A deterministic cap-coherence annotation.** Feasible, and for the right reason: the caps are
   structured values (`resolved_single_name_cap_pct`, `resolved_sector_cap_pct`,
   `max_open_risk_pct`, `max_drawdown_pct`), so this is a **two-number comparison**, not a claim
   extraction from prose — the same argument that made DEF231 tractable where DEF228's general form
   was rejected. The only thing parsed out of text is *which cap the sentence names*. Yield measured
   above: **4 mis-citations / 86 citations across 216 turns (4.7%), on 2 of 18 convenes, and 0 of 13
   on this agent.** It therefore does **not** belong in CR153's scope. Hand it on with the numbers.
2. **DEF235's fix must not start firing the level triple on debator turns** — see R6.

---

## Acceptance

Measurable, and re-measurable post-promotion against the baselines above. A prompt edit whose effect is
not re-measured is the CR105 Amendment-1 trap.

- **A1 (Tier A):** `content/agents/aggressive_debator.md` contains no instruction that competes for the
  first line. Re-measured over ≥18 convenes: stance-null rate for `aggressive_debator` **0** (baseline
  1/18); envelope on line 1 **≥17/18** (baseline 17/18); zero occurrences of `[STANCE` in any
  user-visible body (baseline 1/18).
- **A2 (Tier A):** the `## Inputs` and `## Output style` sections name no agent that has not spoken by
  this turn. Verify the ordering assumption still holds — the transcript at the aggressive turn ends
  at `[trader]` 18/18 — and that `test_cr077_phase_parallelism.py` still asserts the parallel set is
  exactly `{ANALYSTS}`.
- **A3 (Tier A):** literal `X%` placeholder rate **0** (baseline 1/18).
- **A4 (Tier B):** current drawdown and existing open risk appear in the RISK-phase mandate snapshot;
  a unit test asserts that a `CONTEXT_NOT_SUPPLIED` run renders a visible *unavailable* line rather
  than omitting it, and that `docker-compose.yml` parity holds if any new setting is introduced
  (`test_config_compose_parity.py`).
- **A5 (Tier B):** no aggressive turn states an existing-portfolio-risk or drawdown figure absent from
  its own prompt. Baselines to beat: **1/18** fabricated (BAC `~13%`), **1/18** arithmetically wrong
  (NVDA `1.73` vs `0.864`), whole-turn ungrounded-number rate **5/211 = 2.4%**.
- **A6 (separability):** re-measure this agent's DEF236 rates (median sentences 3, 56% over budget,
  39% bullets) in the same pass, so a Tier A effect is distinguishable from CR145 Tier B's.
- **A7:** `pytest backend/tests/unit/ -q` green throughout.
- **Sample-size discipline:** every baseline here is **n=18 convenes on a single epoch**. Post-promotion
  re-measurement should run on ≥18 and say so; a rate moving inside ±1 turn is not evidence.

---

## Out of scope

- **DEF235, DEF236, `LearningStyle.QUICK`, the per-agent fact sheet** — CR145. Cross-referenced above,
  not re-solved.
- **The cap-coherence control** — measured here, filed elsewhere (Tier C).
- **The reference-vs-proposal reading trap for the Conservative and Neutral debators** — real, but it
  is their CR's, not this one's (R3).
- **Whether a mandate should be allowed a 100.0% single-name cap.** 6 of 18 prompts in this epoch carry
  one. On the SNOA convene the agent duly advocated *"full mandate-allowed sizing — 100% of
  portfolio"* into a book already 95.8% GME with $422.50 of cash — its role guidance (*"Push for full
  mandate-allowed sizing"*) has no floor of its own and inherits whatever the mandate states. The PM
  passed for unrelated reasons. That is a **mandate-configuration** question (`single_name_cap_pct`),
  not a prompt one, and it needs Saiful's decision before anyone writes code against it.
- **New providers.** Nothing in Tier A or Tier B adds a fetch.

## Notes

Tier A is free, reversible, confined to one content file, and recovers a field the client already
renders — it can ship alone and should. Tier B is render-only but touches the shared mandate snapshot,
so it lands with a measurement, not on its own. Tier C is a proposal with numbers attached, for
whoever owns the next sweep.
