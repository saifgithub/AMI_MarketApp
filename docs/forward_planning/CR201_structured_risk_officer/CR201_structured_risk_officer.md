# CR201 — Replace the three-way risk debate with one structured Risk Officer

**Status:** proposed · **Filed:** 2026-08-20 · **Track:** AT:R71
**Depends on:** CR197 (the measurement that justifies this), which shipped
`app/services/risk_officer.py`, `app/trading_math/option_ladder.py`, and the ablation harness.

---

## 1. Why

CR197 measured the RISK phase end to end. Three findings, in the order that matters:

1. **The debate is load-bearing.** Strip all three officers from the Chief Investment
   Officer's prompt and approvals halve — 22 → 10 of ~135 (16.3% → 7.4%), APPROVE→PASS 14
   against PASS→APPROVE 2, exact McNemar **p = 0.004**, spread over 9 tickers and 3 epochs.
   Cutting the stage is not an option.
2. **But the three roles are not.** The Aggressive argued "for" in **117 of 118** convenes and
   the Conservative "against" in **117 of 118** — stance is a role constant carrying ~0 bits
   about the ticker (mutual information with the verdict 0.0024 and 0.0321). Removing both
   extremes changes nothing measurable: net **−1** verdict, **p = 1.0**, the tightest null in
   the experiment. The Aggressive also *structurally cannot debate* — it speaks first in a
   single sequential pass, so CR153 F3 measured 0/18 compliance with its own engagement
   instruction.
3. **What the CIO actually uses is a menu of sized options with ticker-specific reasons.**
   Supplying the sizes alone (deterministic ladder, no prose) recovers only half the effect:
   11.8% against a 16.3% baseline. The other half is the *reasons*.

A single structured Risk Officer supplies both halves, and CR197 measured it:

| arm | design | APPROVE | rate | net vs today | p |
|---|---|---|---|---|---|
| v1a | today — 3 officers debate | 22 | 16.3% | — | — |
| v1b | today, resampled (noise floor) | 21 | 15.7% | net 0 (8↑/8↓) | 1.00 |
| **v8** | **one structured Risk Officer** | **22** | **16.4%** | **net 0 (9↑/9↓)** | **1.00** |
| v6 | deterministic ladder only | 16 | 11.8% | +6 | 0.24 |
| v2 | debate removed entirely | 10 | 7.4% | +12 | 0.004 |

v8 lands on the baseline's exact approval count with a flip pattern the same symmetric shape
as replaying an identical prompt. The difference from today is indistinguishable from the
model's own sampling noise.

**What that buys:** 1 LLM call instead of 3 in the risk stage, 1 serial round-trip instead of
3, machine-readable output, and — structurally, not by instruction — the end of the
DEF066 → DEF235 → DEF241 → CR166-Tier-D arithmetic-error class.

---

## 2. The design

### 2.1 Compute and presentation are separated

The current design pays for **presentation** with **inference**: three models each write ~800
tokens of assigned advocacy so the UI can render three hexagons. This CR keeps the three
voices on screen and collapses the three calls into one.

- **Compute:** one new internal agent, `risk_officer`, makes one LLM call and returns JSON.
- **Presentation:** the existing three `AgentId`s (`aggressive_debator`,
  `conservative_debator`, `neutral_debator`) remain as transcript turns, rendered from that
  JSON with **no further LLM calls**.

This is why `D-012` ("exactly 12 agents … don't add or remove without reason") is **not**
violated: the twelve display roles are untouched. `risk_officer` is an internal compute agent
outside `TWELVE_AGENT_IDS`, the same way `CONCIERGE` is the 13th and distinct
(`app/schemas/agents.py:23-24`).

### 2.2 The contract

Already built and unit-tested in `app/services/risk_officer.py`:

```json
{"options": [
   {"size_pct": 1.5, "case_for": "...", "case_against": "...", "key_number": "RSI 43"},
   {"size_pct": 3.0, "case_for": "...", "case_against": "...", "key_number": "123.5x P/E"},
   {"size_pct": 5.0, "case_for": "...", "case_against": "...", "key_number": "..."}],
 "recommended": 3.0, "confidence": "low|medium|high", "decisive_number": "..."}
```

**The model may not emit a computed number.** Sizes come from `risk_debator_sizes` via
`build_option_ladder`; `render_risk_assessment` reads every figure from the ladder and never
from the payload; a size the model invents is dropped, and a rung it skips renders as
"the Risk Officer did not assess this size" rather than vanishing. That is the structural
closure of P5 ("an LLM asked to compute a number it presents as fact") — `failure_patterns`
P2 is explicit that asking nicely measures ~30%.

### 2.3 Stance becomes derived, not parsed — and not constant

Today each officer's stance is parsed from a `[STANCE: …]` envelope the model must emit, which
DEF247 / DEF251 / DEF257 all exist to patch (DEF251 measured **20% of debator turns emitting
no envelope at all**). Under this CR the three rendered turns are constructed in code, so:

- **the envelope is never parsed on the Room's risk path** — three defect classes stop being
  reachable there;
- stance/conviction/`argued_size_pct` are set from the structured payload.

**Proposed schema refinement (NOT yet measured):** add a per-option `lean: "take" | "avoid"`
so each rendered voice carries the officer's actual read of *that rung* rather than a role
constant. This is the change that would finally make the Verdict Board's comb informative.
It changes the officer's output and therefore **requires its own ablation arm before it
ships** — the v8 result above was measured on the schema as built, without `lean`.

Until then the honest interim mapping is: the rung equal to `recommended` carries the
officer's stance, the others carry `neutral`, and `conviction` comes from `confidence`.

### 2.4 Failure degrades to a measured floor, not to nothing

One call replaces three, so a failure is a single point of failure. It degrades deliberately:

| state | behaviour | measured rate |
|---|---|---|
| officer replies, parses | full assessment | 16.4% |
| officer unparseable / times out | **fall back to the deterministic ladder alone** | 11.8% |
| (never) | no risk input at all | 7.4% |

The fallback is a *designed* state with a known floor, not an outage. CR197's run measured
2 unparseable replies in 136 (1.5%). Per CR040 the fallback must be visible in the transcript
(an `[AMI …]` mark, the established annotation voice) — a silent degrade to the ladder is
exactly the "fires constantly and silently" case CLAUDE.md says to ask about.

---

## 3. Scope — files and changes

### 3.1 Backend, new

| file | change |
|---|---|
| `app/services/risk_officer.py` | **exists** (CR197). May need `lean` if §2.3 is adopted. |
| `app/trading_math/option_ladder.py` | **exists** (CR197). |
| `app/services/room_runner.py` | new `_run_risk_officer()` — build prompt, one gated LLM call, parse, render three turns |

### 3.2 Backend, modified

- **`app/schemas/agents.py`** — add `AgentId.RISK_OFFICER = "risk_officer"`. Do **not** add it
  to `TWELVE_AGENT_IDS`, `AGENT_FAMILIES` display sets, or `AGENT_DISPLAY_NAMES` as a room
  voice; it is a compute identity. Confirm `agent_display_name()` still raises loudly on it if
  anything tries to render it (it should never reach a UI).
- **`app/services/tier_policy.py`** — route `RISK_OFFICER`. It now does the work of three
  agents and its output is parsed, so it warrants at least the Trader's treatment rather than
  the plan default the debators fell through to. Cheapest defensible: `mid` on paid plans,
  `cheap` on FLOOR_PASS, `premium` on FLOOR_MANAGER.
- **`app/services/room_prompts.py`** — `_AGENT_MAX_TOKENS[RISK_OFFICER]`. The three it replaces
  summed to 3,200 (800 + 1,300 + 1,100); the structured reply needs roughly 1,200–1,500.
  Derive it from measurement (CR179's method), not by guess.
- **`app/services/room_runner.py`** — `PHASES`: RISK becomes one compute step. The three
  rendered turns are appended without LLM calls (precedent: `_assemble_no_verdict` +
  `_typewriter` on the CR098 withheld-Market path).
- **`app/core/config.py` + `docker-compose.yml`** — `ROOM_RISK_OFFICER_ENABLED: bool = False`.
  Forwarded in the `api-alpha` block or `test_config_compose_parity.py` fails the build (the
  DEF038/DEF063 guard).
- **`app/services/audit.py` call site** — new `flow="room_risk_officer"` so the call is
  attributable and its token cost queryable alongside the three it replaces.

### 3.3 Explicitly unchanged

- **Mobile — no client change required.** `kCombVoices` is derived
  (`mobile/lib/models/agent.dart:194-197`: every agent in `kAgentPhase` except
  `portfolio_manager`), so keeping the three IDs keeps eleven comb voices. SSE still emits
  three `agent_done` events with `stance`/`conviction`/`headline`/`argued_size_pct`.
- **The three `content/agents/*_debator.md` personas stay.** They are the 1-on-1 chat
  personas, gated by five lessons each (`app/services/agent_gateways.py:108-130`). They are no
  longer the Room's risk prompts. **Do not delete them** — that would silently break three
  unlockable personas the lesson tree points at.
- **Safety floor and sizing.** `enforce_safety_floor` remains the only vetoer (DEF059); the
  risk-tier clamp still bounds whatever the CIO picks. This CR moves no enforcement.
- **Credits.** `ROOM_COST_BASIC = 8` / `ROOM_COST_PREMIUM = 25` unchanged. Pricing is a product
  decision, not cost-plus; the saved calls are margin, not a price cut.
- **Journal and old runs.** Existing transcripts already carry three risk turns and replay
  unchanged; nothing is migrated.

### 3.4 A CR197 artifact this supersedes — decide deliberately

CR197 added a `SIZE:` field to the risk officers' stance envelope
(`AgentMessage.argued_size_pct`, `_STANCE_FORMAT_RISK`). If the Room stops generating those
turns by LLM, **that field is no longer exercised on the Room path** — the size becomes
structural rather than declared. Options, to be chosen not drifted into:

- **keep** the field and populate it from the structured payload (recommended — it is the
  channel `prompt_quality_sweep.m4_risk_spread` reads, and the metric finally works);
- **retire** `_STANCE_FORMAT_RISK` and leave `argued_size_pct` populated only in code.

Whichever is chosen, `test_cr197_size_envelope.py` needs its scope assertion revisited.

---

## 4. Tests

### 4.1 Guards that must be updated deliberately, not "fixed until green"

- **`test_cr077_phase_parallelism.py`** — `test_debate_phases_are_never_parallel` and its
  anti-vacuity twin exist because *"marking a debate phase parallel would silently delete the
  debate while every other test passes and the UI still renders every contribution"*
  (`room_runner.py:139-148`). The RISK phase's shape changes here, so the guard's invariant
  must be **rewritten to the new one** — "the risk turns are rendered from exactly one
  officer call, and that call happens before any of them is appended" — with a mutation test
  proving it still goes red.
- **`test_room_runner.py:63`** pins the phase order; RISK's membership changes.
- **`test_def241_def243_debator_arithmetic_and_stance.py`** — its pinned strings still apply to
  the `.md` files (now 1-on-1 only). The *Room-path* assertions (each debator handed its own
  size via `build_room_messages`) no longer describe production and must be re-scoped rather
  than deleted, or the DEF241 lesson silently loses its guard.
- **`test_cr106_stance_envelope.py`** — the risk agents no longer parse an envelope in the
  Room; keep the assertions for the eight prose agents that still do.

### 4.2 New

- Renderer produces exactly three transcript turns from one payload, with the ladder's figures
  and never the payload's.
- One and only one LLM call is made in the RISK phase (assert on the audit flow / gateway call
  count — the direct analogue of the CR077 guard).
- Unparseable / timed-out officer degrades to the ladder **and marks the transcript**.
- `stance` / `conviction` / `argued_size_pct` on all three rendered turns trace to the payload.
- Flag off ⇒ byte-identical behaviour to today (the DEF251-class regression check).
- `risk_officer` never reaches a user-facing label.

---

## 5. Rollout

1. Land behind `ROOM_RISK_OFFICER_ENABLED=false`. Full suite green.
2. Re-run `scripts/pm_debate_ablation.py` arm v8 against the *production* code path (the CR197
   run reconstructed the officer's context from recorded prompts; this confirms the real
   assembly gives the same answer).
3. Enable on Alpha. Compare a fresh 150-ticker room benchmark against the CR035 harness —
   approval rate, latency, and cost per convene.
4. Only then consider `lean` (§2.3), which needs its own arm.

**Rollback:** flip the flag. No schema migration, no data change.

---

## 6. Acceptance

1. Flag off: behaviour byte-identical to today; suite green.
2. Flag on: RISK phase makes **exactly one** LLM call; three turns still reach the transcript,
   the SSE stream, the Journal, and the comb.
3. Ablation arm v8 re-run on the production path lands within the noise floor of baseline
   (net flip ≈ 0, p > 0.05), not merely "close".
4. Measured latency of the RISK phase drops materially (three serial round-trips → one).
5. No figure in a rendered risk turn originates from the model — verified by a test that
   feeds a payload with a wrong contribution and asserts it never appears.
6. Degradation path exercised and visible in the transcript.

## 7. Risks

| risk | mitigation |
|---|---|
| Single point of failure | Designed fallback to the ladder, floor measured at 11.8% vs 7.4% for nothing |
| The room feels less alive | Three voices still render; this is a compute change, not a UI one |
| n=136 over 13 tickers — net 0 bounds the difference, does not prove equivalence | Step 3 of rollout re-measures on the real path; step 3 of §5 re-measures on 150 tickers |
| CR077 guard weakened while being rewritten | Anti-vacuity mutation test is a hard acceptance item, not a nicety |
| Cheaper tier degrades the officer's reasoning | Tier chosen deliberately (§3.2), and the officer's output is parsed — a bad reply fails loudly rather than reading as prose |

## 8. Out of scope

- The `lean` field (§2.3) — proposed, unmeasured, its own arm.
- CIO self-consistency (`PM_SELF_CONSISTENCY_SAMPLES`, CR197) — orthogonal, already shipped
  behind its own flag.
- The option ladder in the CIO prompt (`PM_OPTION_LADDER_ENABLED`, CR197) — orthogonal, and
  measured to shift approvals ~5pp on its own; do not enable it in the same window as this
  change or neither effect is attributable.
- Any change to the safety floor, sizing caps, credits, or the 12-agent roster.

---

## 9. Interaction with CR196 (the finance-tuned model) — training impact only

Added 2026-08-21 by the CR196 lane at Saiful's direction. Scope is deliberately narrow:
what CR201 changes about what we should TRAIN, and what CR196 changes about how CR201
must be validated. No CR201 design decision is reopened here.

### 9.1 The run-1 training job is unaffected — no change needed

CR196's run-1 mix (25,695 examples, recipes 1–9, in training since 2026-08-21 10:02 +03)
contains **no debator data at all**. Recipe 8 trains the Fundamentals prose contract and
the PM verdict JSON (`_PM_VERDICT_FORMAT`); CR201 changes neither. Verified by reading the
recipe, not assumed. The run continues as-is.

### 9.2 A planned run-2 recipe is cancelled by this CR, correctly

CR196 §2c.4 had scoped **recipe 15** as "one brief, three debator prompts, check the three
outputs differ and each holds its assigned posture." CR201 makes that untrainable *and
pointless*: the three risk turns are rendered by `render_officer_turns()` from one parsed
JSON payload with **no further LLM calls**, so posture distinctness is no longer a model
behaviour at all on the Room path. Training it would target a code path that does not execute.

The justification recipe 15 leaned on also disappears — and this is the more important half.
DEF251's "20% of debator turns emitted no envelope" was cited as the reason to train envelope
compliance. CR201 retires DEF247/DEF251/DEF257 **by construction** (stance/conviction/size
become derived, not parsed). Per CLAUDE.md's standing rule — *prompt instructions are not
controls; if it must hold, make it structural* — a structural fix beats a training fix, and
training the same property afterwards would be redundant work against an already-closed class.

**What survives:** the three `content/agents/*_debator.md` files remain live as 1-on-1
unlockable personas (`agent_gateways.py:108-130`, five lesson gates each), so they are still
LLM-generated — just outside the Room, without a transcript or the stance envelope. Low
training value; not scheduled.

**What replaces recipe 15:** a `risk_officer` **JSON-contract** recipe, the same shape as
recipe 8's PM verdict work, against `build_risk_officer_instruction()`. That contract is
unusually verifiable, which makes it a better recipe than the one it replaces — every property
below is machine-checkable without an LLM judge:

- exactly one entry per handed size, and **no invented size** (sizes come from
  `risk_debator_sizes` and are fixed in the prompt)
- `recommended` ∈ the handed sizes
- `key_number` **quoted** from the evidence, never computed
- no self-authored drawdown or cap figure (those are computed upstream)
- `confidence` genuinely separating — "a confident call and an uncertain one … must not read
  the same"

### 9.3 The dependency that runs the other way — sequencing, not a blocker

CR201's equivalence result (arm v8: 22 vs 22 approvals, net 0, p=1.0) was measured **against
`ami-llm` = Qwen3.6-35B-A3B-NVFP4**, stated in CR197's row as the model that produced the
corpora. That result is a property of *that* model reading *that* contract. If CR196 later wins
its adoption gate and the `:8000` slot changes model, **the v8 equivalence does not
automatically carry** — a differently-tuned model can parse-fail or size-select differently on
the same JSON contract.

This is the identical argument §8 already makes for `PM_OPTION_LADDER_ENABLED` ("do not enable
it in the same window as this change or neither effect is attributable"), and it applies with
the same force to a base-model swap. Two consequences, both sequencing only:

1. **Do not enable `ROOM_RISK_OFFICER_ENABLED` and swap the `:8000` model in the same window.**
   Whichever lands second re-measures against the other's baseline.
2. `_AGENT_MAX_TOKENS[RISK_OFFICER]` = 1800 was derived by CR179's method from the v8 arm's
   censored 1200 ceiling and is already flagged for clean re-measure post-enable. A model swap
   is a second reason that re-measure cannot be skipped — CR196's own adoption gate sets
   `max_tokens_floor` from measurement for exactly this reason (`llm_gateway.py:440-484`).

Neither point blocks CR201: it is ahead of CR196, whose run-1 model does not exist yet and
must clear its own eval and adoption gate first.
