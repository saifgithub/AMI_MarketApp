# External review — conservative_debator (data sufficiency + supplier check)

> Reviewer: `kimi-for-coding` · Kimi track K session.
> Corpus reviewed: `docs/forward_planning/CR143_agent_prompt_audit/real_samples/conservative_debator.prompt.txt`
> (AMD convene, fact sheet as of 2026-08-07) and its reply `real_samples/conservative_debator.reply.txt`.
> Unlike `external_review/room/conservative_debator.md` (blind prompt-coherence audit),
> this review had codebase access. Every availability claim below is verified against
> the actual fetch/assembly path — these are **findings, not hypotheses**.

## 1. Question

Does the Conservative Debator have enough data in the prompt to do its job to
~95% accuracy?

## 2. Answer

**Yes for the job as scoped by the final instruction, no for the job as the
role profile defines it.**

The prompt carries two job definitions. The final instruction narrows it to
"Write 2 sentences (size cap + one-line reason)" (`room_prompts.py:77`). For
that scoped deliverable the data is nearly complete:

- Everything a sizing decision needs is pre-computed and handed over: reference
  price **$494.31**, single-name cap **10.0%**, and a worked reference position
  (entry 494.31, stop 464.65, −6.0%, ≈0.60 pt of the 50 pt drawdown cap) so the
  agent never has to do drawdown arithmetic from scratch (prompt lines 110–111).
- The Trader's proposal (WAIT, 0%) and the Aggressive Debator's argument are
  both in the transcript — unlike the blind review's corpus, this agent is NOT
  first to speak.
- Portfolio context: cash, total value, four open positions with weights, and
  an explicit "You hold 0% of AMD" (lines 70–78).

Estimated accuracy on the scoped deliverable: **~90–95%**.

Against the full role as its own `## Inputs` section defines it — "The user's
mandate, **current drawdown**, and any **recent loss patterns**" (prompt line
15), plus engagement with the Neutral Debator and quantification against the
total open-risk cap — the data caps out at **~65–70%**: the portfolio-level
risk state (how much of the 50% cap is already consumed, what the open-risk
sum is, whether recent losses argue for restraint) is simply not in the prompt.

## 3. Data gaps (from the prompt alone)

| # | Gap | Impact |
|---|---|---|
| 1 | **Current drawdown** — named as an input (line 15), never delivered | The agent cannot say how much of the 50% cap is already consumed — the core fact a capital-preservation argument rests on. |
| 2 | **Recent loss patterns** — named as an input (line 15), never delivered | The conservative case ("we've been stopped here before") can only be made second-hand, via the Bear's journal quote in the transcript ($502.59, line 139). |
| 3 | **Existing open-risk sum / per-position stops** — the open-risk cap (line 53) is defined as "the sum of (position size % × stop distance %)/100 across all open positions, including this one" | Positions render with weight and unrealised P&L only (lines 73–76) — no stops, so the sum is uncomputable and the 60% cap is unreasoned-about. |
| 4 | **Neutral Debator's argument** — listed as an input (line 14) | Structurally absent: the RISK phase speaks aggressive → conservative → neutral, so the Neutral has not spoken when this agent takes its turn. Not a feed gap — an ordering artifact baked into the role profile. |
| 5 | **Sector exposure** — the 20.0% sector cap is narrated (line 49) and AMD's sector is given (line 104) | Current sector weights are not shown; NVDA's sector appears only as the Trader's transcript assertion (line 149). "Sector correlation risk" is arguable but not verifiable from the data block. |
| 6 | **risk_score mapping** — "Do not recommend against trades that the user's risk_score clearly supports" (line 28) | No threshold anywhere defines what risk_score 3 "clearly supports". Unfollowable as written (blind review 2e — confirmed). |
| 7 | **Canned drawdown example contradicts this user's cap** — line 47: "(e.g. 5% size, 20% stop → 1.0 pt, i.e. 1/30th of a 30% cap)" | The user's cap is **50%** (lines 47, 110). The worked example's "30% cap" is a hard-coded literal shown regardless of the actual mandate — a live internal contradiction in the mandate block. |

Note what is NOT a gap in this sample (contra the blind review's corpus): the
Trader's proposal IS present, the Aggressive Debator HAS spoken, and the
reference position uses the resolved 10.0% ceiling — matching the 10.0% cap,
so the blind review's 5%-vs-3% cap conflict (its §2d) does not occur here.

## 4. Supplier check — what the codebase can actually deliver

Prompt assembly: `build_room_messages` — `backend/app/services/room_prompts.py:321-483`.
Base role profile: `content/agents/conservative_debator.md` (the `## Inputs`
promise at lines 14–19). Debate order: `PHASES`, `backend/app/services/room_runner.py:160-164`
(RISK = aggressive, conservative, neutral; sequential — only ANALYSTS runs
parallel, `room_runner.py:151-156`). Reference position: deterministic
`ctx.trader_size_pct` = resolved risk-tier ceiling (`room_runner.py:2913`,
resolver at `room_runner.py:663-672`), entry = live base price
(`room_runner.py:2910`), stop = base × 0.94 (`room_runner.py:2911`; 494.31 ×
0.94 = 464.65 ✓), rendered only for RISK/VERDICT via `_drawdown_snapshot_line`
(`room_prompts.py:280-318`, gated at `room_prompts.py:400`).

| # | Item | Verdict | Evidence / effort |
|---|---|---|---|
| 1 | Current drawdown | **FETCHED, NOT SURFACED** | Computed per run: `sim.valuation_snapshot(user_id)` at `backend/app/api/room.py:188-190`, threaded via `start_run` (`room.py:203`) into `_RoomContext.current_drawdown_pct` (`room_runner.py:2882`). Consumed ONLY by the deterministic safety floor (`room_runner.py:1900, 3177`; `safety_floor.py:546-548`). No prompt renderer reads it — the mandate snapshot carries the cap, never the current value. One render line. |
| 2 | Recent loss patterns | **AVAILABLE, NOT WIRED** (to debators) | Two existing sources: (a) `last_loss_closed_at` from `_risk_limit_context` (`sim_engine.py:486-489`) — enforcement-only; (b) the Decision Journal block `build_journal_context_block` (`backend/app/services/journal_context.py:78-98`) — already rendered into prompts, but gated to Bull/Bear only (`room_prompts.py:381-385`). The Bear's "$502.59 stop losses" (prompt line 139) is journal-sourced — researchers see the block, debators don't. Widening the gate is a one-line change plus a plan-retention decision (DEF054/055 gating already exists). |
| 3 | Existing open-risk sum / per-position stops | **FETCHED, NOT SURFACED** | Stops exist per trade row (`SimTradeRow.stop`, `backend/app/db/models.py:467`). The exact sum the prompt's cap line defines is computed every run: `_risk_limit_context` sums `position_pct × stop_distance` per open trade (`sim_engine.py:491-500`), built for the Room at `room_runner.py:2864-2869` (`_build_room_risk_limit_context`, `room_runner.py:800-826`). Consumed only by enforcement (`room_runner.py:1914, 3193`; `safety_floor.py:509-540`). The holdings block renderer (`room_runner.py:746-755`) shows qty/weight/unrealised only. One render line for the sum; a few more for per-position stops. |
| 4 | Neutral's argument | **STRUCTURAL — ordering, not data** | `PHASES` RISK order (`room_runner.py:160-164`) puts conservative second. Either cut "Neutral Debator's argument" from the base profile's Inputs (`content/agents/conservative_debator.md:18`) or reorder the phase. The transcript mechanism itself is fine — `_format_transcript` (`room_prompts.py:886`) renders everything spoken so far. |
| 5 | Sector exposure | **FETCHED, NOT SURFACED** (gated to PM) | `sector_weights` computed per run (`room_runner.py:2856-2860`, `_build_room_sector_context`) but rendered ONLY for the Portfolio Manager (`room_prompts.py:453-455`, CR026). Extending `_format_sector_allocation` to the three debators is a gate change, not a new feed. |
| 6 | risk_score mapping | **NOT AVAILABLE as data — needs prompt text** | No threshold table maps risk_score → what it "clearly supports"; only the resolved cap is surfaced (`trading_math/sizing.py:54,73`). Fix is a sentence in the base profile, not a feed. |
| 7 | Canned 30%-cap example | **CONFIRMED BUG** | `overlay_generator.py:90-91` hard-codes "(e.g. 5% size, 20% stop → 1.0 pt, i.e. 1/30th of a 30% cap)" into `_mandate_common_block` — shown to ALL 12 agents, for ANY mandate. This user's cap is 50%; the Room's own dynamic snapshot line correctly says "the 50 pt cap" (prompt line 110–111, from `_drawdown_snapshot_line`), so the static example directly contradicts the live figure two screens apart. |

## 5. Caveats before wiring #1 / #2 / #3 / #5

1. **These fixes are render-only — zero new provider calls.** Unlike the
   fundamentals gaps (statement endpoints, rate-limit exposure), every value
   above is already computed inside the run for enforcement. No caching, no
   TTL, no Yahoo/Reddit exposure added. The only cost is prompt tokens.
2. **Degrade-loudly already handled.** Both context builders return sentinels
   on failure (`CONTEXT_NOT_SUPPLIED`/`None`, `room_runner.py:811-826`) — a
   renderer must preserve that contract (render "unavailable this run", never
   silently omit), same as the holdings block does (`room_runner.py:692-694,
   728-733`).
3. **Journal widening is a policy decision, not just a gate flip.** The
   journal block is plan-gated (DEF054/055) and currently Bull/Bear-only by
   design (`journal_context.py:81-84` names the gating contract). Giving
   debators loss history changes what the debate is allowed to know — worth an
   explicit line in the CR, and `PHASE1_ground_truth.md`-adjacent docs may
   need updating alongside.

## 6. Recommended slice (if this becomes a CR)

Cheap, high-yield, no new provider:

1. Render current drawdown + existing open-risk sum into the RISK-phase
   mandate snapshot (both already in `_RoomContext`).
2. Fix the canned "30% cap" example in `overlay_generator.py:90-91` to use the
   mandate's actual `max_drawdown_pct` (or drop the parenthetical).
3. Reconcile the output spec: delete the four-part "Output style" block from
   `content/agents/conservative_debator.md:21-26` (it conflicts with the
   2-sentence length guide and the stance header) or promote it and drop the
   2-sentence guide. Keep ONE spec.
4. Cut "Neutral Debator's argument" from the Inputs list (ordering makes it
   undeliverable), and cut or operationalise the "risk_score clearly supports"
   rule.
5. Optional, policy-level: extend the journal gate to debators; extend
   `_format_sector_allocation` beyond the PM.

## 7. Reply-sample verification (`real_samples/conservative_debator.reply.txt`)

The reply, in full: an opener sentence, a blank line, then one long sentence.
Checked line-by-line against the prompt's data block.

**Quoted numbers — all grounded.** $424.03, $494.31, 50% (cap), 9.4% (NVDA
weight), 10.0% (cap), $464.65 and −6.0% (the reference stop, adopted as its
own proposal), 126.4 (P/E) — every one appears verbatim in the prompt. **4.0%**
is the agent's own size proposal — the deliverable, not a hallucination.
"Multiple compression the Bear highlighted" and "sector correlation risk"
(traceable to the Trader's transcript line 149, not the data block) are
mandated transcript engagement, not scope bleed.

**Two derived numbers — one sound, one wrong:**

- **−14.2%** — sound: (494.31 − 424.03) / 494.31 = 14.218%. Legitimate
  arithmetic on block numbers, same class as the fundamentals sample's "~79%
  of range".
- **1.17%** — NOT reproducible. This is the load-bearing risk quantification
  ("consumes 1.17% of our total 50% portfolio drawdown cap"). Under the
  mandate's own formula (P×S/100), the agent's own proposal gives 4.0 × 14.2 /
  100 = **0.57 pp ≈ 1.1% of the cap**; at the 10.0% ceiling it is 1.42 pp
  (2.8%); the reference position's 0.60 pt is 1.2% of the cap. No combination
  of stated numbers yields 1.17, in either units reading (pp or %-of-cap). It
  is an arithmetic error wearing the costume of the mandated "uses up Z% of
  our drawdown cap" template — blind-review failure mode #3, live, on the one
  number this role exists to produce.

**Logic / wording defects (no numbers claimed):**

- "If AMD **reclaims** the $424.03 support floor **on volume**" — $424.03 is
  ~14% BELOW the $494.31 price; falling to it tests or breaks support, it does
  not "reclaim" it. "On volume" is invented colour — the block says volume is
  in-line with the 20-day average. The scenario is directionally confused.
- "drawdown from the $494.31 entry" conflates a per-position price slide with
  portfolio drawdown — the exact confusion the mandate text warns against —
  though the reply does attempt the pp conversion (and gets it wrong).

**Engagement duty — partial.** The DO-NOT list says "Ignore the Aggressive
Debator's points — engage them." The reply never addresses the Aggressive's
actual argument (22.9% upside to $608.23, PEG 1.12, building retail
sentiment); it engages the Bear and the Trader's geometry instead. Arguing
past, not against.

**Format compliance:**

| Rule | Result |
|---|---|
| `[STANCE: …]` as the VERY FIRST line (`room_prompts.py:264-277`, mandatory) | **VIOLATED — absent entirely.** Server-side this lands the turn in the comb's "NOT STATED" gutter (`parse_stance_envelope`, `room_runner.py:3439`; degradation contract at `room_prompts.py:218-248`). Notably the Aggressive Debator in the same transcript DID emit one (prompt line 163) — but misplaced after its first sentence, also a violation. |
| "Write 2 sentences (size cap + one-line reason)" | ✓ obeyed (opener + one long sentence) |
| "Open with: 'I'd argue for [smaller / …]'" | ✓ obeyed |
| Bullets per `_PROSE_FORMAT` (`room_prompts.py:210-215`) | ✗ none — blind-review contradiction §2a/§2c resolved by dropping bullets and the header |
| Bold for key metrics; no headings/tables; no "As the X" preface | ✓ |
| Stance-evidence tension | moot — no header. Body is coherent with the conservative role (smaller size, tighter stop). |

**Conclusion: NOT GROUNDED — narrowly.** Every quoted figure traces to the
block and the −14.2% derivation is sound, but the single most role-critical
number in the reply (1.17% cap consumption) is irreproducible arithmetic, and
the mandated stance header is missing. Facts: bound. Key computation: wrong.
Format: failed on the one machine-parsed line.

## 8. Relationship to the blind review (`../conservative_debator.md`)

**Confirmed live:**

- §2a (multi-part Output style vs "Write 2 sentences") — verified in source
  (`content/agents/conservative_debator.md:21-26` vs `room_prompts.py:77`),
  and observed biting: the reply kept 2 sentences and dropped the mandated
  downside-quantification format's header and bullets (its failure mode 1a).
- §2c (tabular vs bulleted vs no-tables) — "terse, tabular, declarative" tone
  (prompt line 62) vs `_PROSE_FORMAT`'s "no tables" (`room_prompts.py:214`).
- §2e ("risk_score clearly supports" unfollowable) — no threshold exists
  anywhere; rule stays vague.
- Failure mode 3 (drawdown math error) — partially: the reply used the
  reference stop correctly but produced an irreproducible cap-consumption
  figure (1.17%).
- Its unfollowables about missing current drawdown / loss patterns / open-risk
  sum — all confirmed as real absences, AND now explained: every one is
  computed per run and consumed by enforcement, never rendered (§4 rows 1–3).

**Killed / does not apply to this real sample:**

- §2b ("engage arguments that do not exist" / "You are first to speak") — in
  this corpus the Aggressive Debator spoke first (transcript lines 161–165);
  the engagement target exists. The residual truth: the Neutral's argument is
  still undeliverable, by phase ordering (`room_runner.py:160-164`).
- §2d (5.0% reference vs 3.0% cap conflict) — this sample's reference position
  uses the resolved 10.0% ceiling, equal to the narrated cap; the arithmetic
  is coherent. The blind review's corpus predates or differs from the
  CR101/DEF066 resolver path (`room_runner.py:663-672, 2913`).

**New findings the blind review structurally could not see:**

- The Inputs-list promises (drawdown, loss patterns) are not missing data —
  they are **enforcement-only data**, one render line away (§4 rows 1–3).
- The canned "1/30th of a 30% cap" example (`overlay_generator.py:90-91`)
  contradicts any mandate whose cap ≠ 30% — including this one's 50% —
  in the same block that states the real cap.
- The Bear's "$502.59" figure in the transcript is journal-sourced
  (`journal_context.py:78-98`, gated at `room_prompts.py:381-385`), not a
  hallucination — provenance the blind review could not establish.

The two reviews compose: the blind review defines the prompt-internal
contradictions to cut; this review shows the data its Inputs section promises
already exists server-side and only needs rendering.
