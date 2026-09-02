# 05 — Further improvements to Room results, beyond the contradiction fixes

Second pass at higher effort, on Saiful's ask: "do you have anything else that may
improve the room results?" Fourteen items, ranked in four tiers. Everything here was
checked against source or probed live on 2026-09-02; anything not verified is labelled
needs-a-look. None of it is built.

The framing rule for all of it: the CR219 package fixes prompts that *lie*. This file
is about the two other levers on result quality — **decision variance** (the answer the
user gets is partly a coin toss today) and **decision inputs** (what the deciding agents
can actually see and do).

---

## Tier 1 — highest impact, evidence in hand

### 1. Default PM self-consistency to n=3 (majority vote)

The single largest *measured* noise source in the user's answer:
`pm_self_consistency_samples` defaults to **1**, and the measured redraw flip rate at
n=1 is **~19.7%** — one verdict in five is sampling noise, not analysis. The voting
infrastructure already exists (`_vote_pm_samples`; 3-sample replay showed a single draw
differs from the majority only 6.6% of the time). Samples are independent and can run
concurrently, so wall-clock cost at VERDICT is roughly one PM call, and the marginal
cost is on-prem GPU time, not dollars.

- **Change:** default the setting to 3 (5 if latency allows) on Alpha.
- **Measure:** verdict stability on re-convene of identical inputs, before/after.
- **Risk:** none to correctness — majority of the same distribution; the safety floor
  still gates every sample's winner.
- Also fixes a UX trust problem: at ~19.7% flip, a user who re-runs the same ticker
  sees the Room reverse itself for no visible reason.

### 2. Thinking mode is OFF on the live model — a verified, untapped lever

Probed LAN-direct on 2026-09-02 against `http://192.168.20.74:8048` (root
`/models/qwen38-flash-next-nvfp4` confirmed per the CLAUDE.md identity rule):

- The serve has a reasoning parser (`reasoning_content` and
  `completion_tokens_details.reasoning_tokens` are present in responses), but both a
  trivial and a quantitative prompt returned **`reasoning_tokens: 0`** — the Room's
  reasoning model is running with thinking disabled.
- The gateway sends nothing to control this on the vLLM path
  (`enable_thinking: False` at `llm_gateway.py:1021` applies only to the DashScope
  cloud provider; the "provider quirks" hook at `:597` is explicitly "unused today").
- The budget comment at `llm_gateway.py:627-629` — Room per-agent budgets "tuned for
  vLLM, **a non-reasoning model**" — predates the CR211 model swap and is stale as a
  description, though currently harmless *because* thinking is off.

**Recommendation — a measured experiment, not a flip-the-switch:** enable thinking for
the **PM only** (per-request `chat_template_kwargs`/`enable_thinking` via the gateway's
quirks hook if this vLLM build honors it; serve-side otherwise), raise the PM decode
budget to cover reasoning tokens (they count inside `completion_tokens` — CR130's exact
failure mode if unbudgeted, and CR210's `_CHARS_PER_TOKEN_WORST_CASE` test must be
re-derived for the visible portion), and replay the banked 136-convene corpus:
verdict-quality proxies (R:R-coherence signal rate, parse rate, floor-agreement rate,
self-consistency flip rate) with thinking on vs off. Qwen3-series models move most on
exactly the PM's task shape — multi-step weighing of conflicting inputs. If it wins,
extend to the Research Manager; the eleven formulaic turns likely never need it.

**Do not** enable thinking Room-wide unmeasured: 12 agents × reasoning tokens is real
GPU latency per convene, and the streaming UX ("typewriter") sits idle during thinking.

### 3. The PM is overridden by checks it cannot see — floor-input parity + pre-verdict preview

`enforce_safety_floor` (safety_floor.py:786) checks ~20 violation kinds — allowlist/
blocklist, halal, classification, locale, **sector cap, post-loss cooldown,
over-trading brake, open-risk cap**. But `room_prompts.py` contains no cooldown or
over-trading token at all (grepped 2026-09-02), so on those checks the PM writes its
verdict blind and gets overridden after the fact. The user then reads a transcript
where the PM approves and a verdict that blocks — the floor is working as designed
(uncoachable, correct), but the *narrative coherence* the Room exists to provide is
broken, and an approve-then-overridden turn is a wasted deliberation.

- **Change (two steps):**
  1. **Parity audit:** for each floor check, name the prompt line that shows the PM
     the same state the check reads (CR069 already did this for the three universes —
     extend the same principle). Add cooldown state and trade-frequency state to the
     PM's risk-state block.
  2. **Pre-verdict compliance preview:** run the deterministic checks against the
     trader proposal *before* the PM turn and inject the results as a code-generated
     line ("AMI compliance pre-check: sector cap headroom 3.2% — proposal 5.0%
     FAILS"). The floor stays the gate; the PM stops narrating against arithmetic
     that is already decided.
- **Measure:** floor-override rate per 100 convenes, before/after. Each override
  prevented is a convene whose transcript and verdict agree.
- **Guard:** a unit test asserting every floor-check kind has a corresponding
  pre-check line in the VERDICT-phase prompt (the CR069 pattern, generalized).

---

## Tier 2 — structural, cheap, no new LLM calls

### 4. Code-generated Room scoreboard for the deciding agents

By VERDICT the PM reads a long prose transcript; the stance envelopes
(`[STANCE | CONVICTION | HEADLINE]`) are already machine-parsed per turn. Prepend to
the RM, Trader, and PM turns a compact code-built table — agent, stance, conviction,
headline — so the deciders weigh the whole Room instead of whatever recency left
salient. Degrade loudly per house rule: DEF251 measured ~20% of debator turns emit no
envelope, so missing rows render as "no envelope emitted", never silently dropped.
Zero extra LLM calls; a few hundred prompt tokens.

### 5. Partial-outage honesty: count scripted fallbacks, disclose, and cap

DEF059 fixed the total-outage case (LLM down → PASS, never fake APPROVE). The partial
case is still silent: `_compute_agent_text` falls back to a scripted `_TEMPLATES` turn
per agent on timeout/error/empty, and no run-level counter surfaces it (grep for any
`fallback`/`degraded` accounting in the runner found none — needs-a-look to confirm).
A convene where 5 desks timed out still produces a confident verdict argued from
boilerplate.

- **Change:** count scripted turns per run; inject the count into the PM prompt
  ("3 of 11 desks unavailable this convene"); disclose it on the verdict card; above a
  threshold (suggest ≥3 of 11, and always if the Trader or RM was scripted — the
  proposal itself is canned then), force PASS with the outage reason, extending the
  DEF059 rule from "no LLM" to "not enough LLM."
- This is the degrade-loudly house rule applied to the Room's own composition.

### 6. A "what would change this call" field in the PM verdict

Add one bounded field to the PM JSON schema: the kill criterion — the concrete
evidence that would flip this verdict ("a quarter of margin-trend reversal", "close
below the stop's level on volume"). CR210's grammar makes it structural for free
(bounded string, both ends). Three payoffs: it forces the PM through disconfirming
evidence before committing (the classic committee failure the bear alone can't fix);
it is the single most teachable line on the verdict card for an education product; and
it pairs with item 14 (next-convene delta) — next run, the Room checks the prior kill
criterion first.

### 7. Make the Room self-measuring: a permanent DATA GAPS tail

The arms experiment bolted a gap-report onto 84 turns once and got the project's best
data-roadmap evidence (interest coverage 21× from 9/12 agents). Institutionalize it:
a one-line structured tail on the four analyst turns only ("GAPS: <=3 short items or
none"), parsed and logged per run, aggregated offline (the `aggregate_arms.py` logic
is the prototype). Future data CRs then rank themselves from production evidence
instead of a one-off harness. Keep it out of the user-visible transcript if noise is a
concern; it is telemetry first.

---

## Tier 3 — measurement infrastructure (how we know any change helps)

### 8. Promote the CR219/CR210 scripts into a standing replay eval harness

Every prompt CR so far measures ad hoc (66-turn corpus here, 68/69 held-out sets
there) and the harnesses live inside CR folders. Promote them to
`scripts/room_eval/`: a fixed fixture set (the banked convenes + a few synthetic
mandates), replayed against any prompt/model change, scoring the same panel every
time — strict-parse rates, stance-envelope emission, LIVE-field citation rates,
PM self-consistency flip rate, floor-agreement rate, scripted-fallback count.
Prompt changes stop being vibes-with-a-one-off-measurement and become diffs on a
scoreboard. This is the prerequisite for items 2, 11, 12 and for CR219's own AC4
becoming routine instead of an event.

### 9. A verdict-outcome ledger (calibration floor, not alpha claims)

Every verdict is persisted with a reference price and a mandate horizon; yfinance
supplies the later prices. Auto-score each verdict at matched horizon and keep a
ledger: APPROVE vs PASS forward-return distributions, conviction-vs-hit-rate
calibration. **Framing discipline:** simulation-only education product — the ledger is
a *sanity floor* ("APPROVEs are not systematically worse than PASSes"; "high
conviction means something"), never a performance claim; surface it internally, not to
users, until someone decides otherwise. This is the only ground-truth signal the
system can ever get about decision quality, it costs a cron job, and it would catch a
prompt regression that citation rates never would. Respect the standing exclusions
(CR035 synthetics, seed rows) when scoring.

---

## Tier 4 — experiments and small guards (measure before shipping)

### 10. Mandate-utilization guard — finding #17 is a class, not an instance

Verified 2026-09-02: of the three `risk_components`, only `concentration_tolerance`
does anything (sector-cap resolution, overlay_generator.py:803 + safety_floor);
**`drawdown_response` and `regret_asymmetry` appear nowhere in any prompt or branch** —
the same dead-field shape as `primary_goal`, twice more. `regret_asymmetry` in
particular is a behavioral-framing lever an education product should want (a
loss-averse user should get drawdown-first framing; its inverse, missed-gain framing).
Recommendation: (a) a unit test asserting every `Mandate` field either branches
somewhere in prompt assembly or is listed in an explicit `NARRATION_ONLY` register —
so the next dead field fails red at introduction; (b) fold `drawdown_response` /
`regret_asymmetry` branching into the `primary_goal` work in
[`03`](03_scope_recommendations.md) while that file is open.

### 11. Stance-envelope grammar — a candidate, with an honest tension

The envelope drives item 4's scoreboard, and ~20% of debator turns omit it (DEF251).
It fits the CR210 "safe to constrain" pattern (`none`/`neutral` exist, so every turn
has an honest value — the Size-line lesson). But two deliberate decisions stand in the
way: the CR210 wiring test pins *no prose agent is ever constrained*, and DEF251's own
comment declares the envelope a **measurement channel, never a control** — forcing it
destroys the compliance signal it exists to measure. Recommendation: leave it until
the scoreboard exists; if missing envelopes measurably degrade the scoreboard's value,
revisit with a held-out replay measurement and amend both pinned decisions explicitly
rather than around them.

### 12. Debate-order randomization

Bull always speaks before Bear; LLM judges anchor on order, and the RM reads both.
Cheap experiment: seed the order per run id, replay the corpus, compare RM stance and
PM verdict distributions. If order moves verdicts, that is variance to remove (fix the
order to whichever the measurement favors, or summarize-then-debate); if it doesn't,
one suspicion retired for the cost of a replay. Note CR077's test pins the *parallel*
set to exactly {ANALYSTS} — sequential-order shuffling does not touch that pin.

### 13. Every number the user reads is computed or checked in code

The house pattern already exists piecewise (R:R recomputed and narration rewritten;
CR179 Leg 4; DEF234/242 money formatting; the trader's derived figures from
`trading_math`). Two additions: (a) extend the RO precompute from
[`03`](03_scope_recommendations.md) with per-rung dollar risk on current portfolio
value, so no agent ever multiplies; (b) an audit enumerating every numeric on the
verdict card and its source (code / LLM-unverified), turning stray LLM arithmetic into
a listed defect class. Live illustration from this review's probe: asked a
position-risk question, the live model got the *conclusion* right (0.13% of portfolio)
while its parenthetical mislabeled the position size as the risk figure — n=1,
illustrative only, but it is the exact failure mode this rule exists for.

### 14. "What changed since your last convene" delta line

Runs are persisted; when a user re-convenes a ticker, inject a code-built delta line
(prior verdict + date, price move since, sheet fields that changed state) into the PM
prompt and show it on the card. Pairs with item 6 (check the prior kill criterion
first). Turns the flip-flop risk (item 1) into a teaching moment — the Room explains
*why* today differs from last week, or holds its ground explicitly.

### 15. One-line check: news headlines are untrusted input

The News Analyst's sheet lines carry third-party headline text into the prompt.
The floor means the blast radius is bad narration, not bad action, but verify the
renderer frames headlines as quoted data (the same "data, not instructions" hygiene
the codebase applies elsewhere) and that a headline containing an instruction-shaped
string cannot land outside a quoted context. Cheap to check; cheap to pin with a
fixture.

---

## Suggested sequencing (if the combined review adopts these)

| Order | Items | Why first |
|---|---|---|
| 1 | 1 (PM n=3), 5 (outage honesty), 10a (mandate guard) | Days of work, no measurement dependency, immediate variance/honesty wins |
| 2 | 8 (eval harness) | Everything after it becomes measurable |
| 3 | 3 (floor parity), 4 (scoreboard), 6 (kill criterion), 13 (numbers audit) | Structural input/output quality, measured on the harness |
| 4 | 2 (thinking experiment), 12 (order), 11 (envelope) | Experiments the harness can now score |
| 5 | 7 (gap telemetry), 9 (outcome ledger), 14 (delta line) | Standing instrumentation and UX |

Items 1–6 and 10 are small enough to ride CR219's umbrella per Saiful's one-CR call;
8 and 9 are infrastructure with their own acceptance shapes — if the combined review
prefers, they are the two candidates to split out without weakening the rest.
