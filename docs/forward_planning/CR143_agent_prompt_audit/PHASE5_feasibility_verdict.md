# CR143 Phase 5 — are the accuracy suggestions feasible?

**Filed:** 2026-08-10 · **Decision:** Saiful — *"research CR143 and very carefully consider if any of
the suggestions are feasible."*

The suggestions are [`research/accuracy_improvements.md`](research/accuracy_improvements.md), a memo by
track K proposing eight levers (§1–§8) to raise the Room's conclusion accuracy. This document checks
each one against the code as it stands on `main` at `89f975fa` (2026-08-10) — **not** against the
memo's snapshot of 2026-08-08. Two days of build landed in between and it changes the answer twice.

**Verdict: six of eight are feasible, §3 needs splitting, and §4 must be rejected as specified.**

---

## 1. What was verified, and how

Nothing below is taken from the memo on trust. Each row names the instrument.

| Memo claim | Instrument | Result |
|---|---|---|
| §8 — vLLM supports JSON-schema-constrained decoding | live `POST /v1/chat/completions` to `192.168.20.74:8000` with `response_format: {"type":"json_schema"}` | **True.** Server `0.23.1.dev0+g0fc695fc6`; `ami-llm` returned schema-conformant JSON first call |
| §1 — `trade_asymmetry` is computed and never rendered into a prompt | all callers | **True.** Two call sites only: `room_runner.py:1299` (post-hoc `[AMI …]` annotation) and `:3170` (the scripted no-LLM fallback) |
| §2 — risk state is computed per run and reaches no prompt | `_RoomContext` fields vs `room_prompts.py` | **True.** `current_drawdown_pct`, `risk_existing_open_risk_pct`, `risk_trade_open_timestamps` are built at `room_runner.py:3111–3141` and passed only to `enforce_safety_floor` (`:3421`). The renderer emits *caps* (`max_drawdown_pct`, `_max_open_risk_pct_text`) and no current state at all |
| §5 — `_format_profile` takes no `agent_id` | signature, `room_prompts.py:540` | **True.** All 12 agents receive a byte-identical fact sheet |
| §3 — no validate-and-repair loop exists | grep | **False.** `_reformat_pm_response` (`room_runner.py:3958`) is that loop for the PM, with a DEF067 guard against it recovering an APPROVE. Phase 1 measured it firing **0/18** on this epoch |
| §1 — the drawdown half is unbuilt | `git log --grep=DEF241` | **False.** `_drawdown_snapshot_line` already hands each debator the figure for the size its own role argues (`room_prompts.py:337–347`). DEF241 round 2 COMPLETE; it stays `open` only for the Bull Researcher and Research Manager residue |

The last two rows are the ones that would have paid for a build twice.

## 2. Verdict per lever

### §1 Precompute every number the model is tempted to derive — **FEASIBLE, ~60% shipped**

The memo's strongest claim and the codebase agrees with it; it simply arrived first on the drawdown
half (DEF066 → DEF235 → DEF241). What remains is the memo's own worked example, still true:
`trade_asymmetry` is computed every run and printed in no prompt. The Trader's false *"symmetric"*
verdict and the Research Manager's false premise both die the moment upside%/downside%/R:R appear in
the block.

Remaining work: render asymmetry and position-in-range into the RISK/EXECUTION/VERDICT blocks; close
DEF241's residue. Render-only, blast radius all 11 prose agents ⇒ CR142 Tier A, acceptance is a
post-promotion re-measure.

### §2 Render the risk state the roles already demand — **FEASIBLE, the cheapest real gain**

Seven agents are instructed to weigh drawdown, open risk, pace and sector exposure; none of it is in
any prompt; all of it is one field away from the renderer because the safety floor already needs it.

**This is the only lever that puts information in front of an agent it has never had.** Everything else
restates or restructures what is already there.

Constraint the memo misses: DEF236 (open) measured every prose agent over its length guide 61–100% of
the time, and `_AGENT_MAX_TOKENS` was sized *to that guide* (DEF125). Adding blocks before resolving
DEF236 buys truncation. **Subtract before you add** — or ship §2 with re-derived token budgets in the
same commit.

### §3 One output contract, enforced server-side — **PART 1 IN FLIGHT · PART 2 DEFER**

Part 1 (delete the losing half of every contradiction) is already booked: DEF236 (open), DEF251 (open —
the stance is asked for twice, so one in five debator turns states it once, in prose), DEF243 and
DEF247 (fixed).

Part 2 (validate → auto-regenerate with the error appended) should wait:

1. The machinery exists for the PM and absorbs **0/18** on this epoch. No measured demand.
2. It doubles worst-case LLM calls on a **streaming path the user watches** — Room turns are
   token-paced by design.
3. DEF067 is the recorded hazard: a reformatter that "recovers" can change a verdict's meaning. Any
   prose-agent repair loop needs the same never-changes-substance guard, which is most of the work.

Do the subtraction, re-measure, build the loop only if E3 survives.

### §4 Numeric grounding check on every reply — **REJECTED AS SPECIFIED**

Proposal: extract every numeral from a reply and flag anything not present in the prompt.

**Phase 3b already measured what that guard would do.** M3: 92.6% grounded, 3.1% inherited, **4.3%
novel** — and every novel figure was hand-read and found legitimate:

- *"$608.23 by 2026-11-03 (88 days), representing a 22.9% potential gain"* — arithmetic on a grounded target
- *"if growth decelerates to 10-15%… implying a -25% to -35% correction"* — an explicitly hypothetical scenario

So on the measured epoch it fires on ~4.3% of numerals at a false-positive rate near 100%. It is also a
**general pattern over agent prose** — the class with the worst record in this repo: DEF231 took nine
audit rounds, and DEF234, DEF235 and DEF242 all shipped from patterns of this shape. CR144 (done) is the
convention written to stop it recurring: *before a pattern reads agent prose, name the field it could
have read instead.*

**The feasible form, already the direction of travel:** check only numbers held structured, against
their structured source — DEF235 (size comes from the mandate cap, never the prose), DEF241 (hand the
agent the figure), DEF242. Keep the general numeral sweep as a **measurement instrument**
(`scripts/prompt_quality_sweep.py` already is one), never a per-turn guard.

### §5 Per-agent fact-sheet views — **FEASIBLE, booked as CR145 Tier C, needs a design call**

Mechanically a renderer change; substantively the one lever with a product question inside it, and
CR145 states it better than the memo: Bull, Bear, Research Manager, Trader and PM **legitimately** need
cross-lane data, so the visibility matrix is a design decision, not a filter. It also interacts with
CR098 (withheld analysts already strip fact-sheet lines) and CR104 `field_state`, and
`test_prompt_data_parity.py` must learn "not this agent's lane" ≠ "dropped" or it turns red.

**Evidence conflict, resolved in CR145's favour.** Phase 3b *rejected* the scope-firewall concern on
M2b = 0.128 (the four analysts were the least-similar pairing measured). That was the wrong instrument —
agents can differ sharply in emphasis while still borrowing each other's facts. CR145's direct
measurement says the opposite: `news_analyst` cites valuation in **16 of 18** convenes, technicals
13/18. **Phase 3b's rejection of this concern is superseded.**

### §6 Verified anchors against transcript contagion — **ONE THIRD FEASIBLE**

§6.1 restates §1. §6.2 (`[unverified figure]` labels on transcript content) inherits §4's
false-positive problem and puts it in prose the user reads — **no**. §6.3 — a deterministic
verified-facts recap above the PM's transcript so the gatekeeper anchors on ground truth rather than 11
turns of telephone — is cheap, independent and worth building. Covered by CR156.

### §7 Eval harness — **FEASIBLE; more exists than the memo credits**

Already built: `scripts/room_benchmark.py` + `room_benchmark_report.py` (CR035, 150-ticker),
`scripts/prompt_quality_sweep.py` (the M1–M6 scorers), `dump_assembled_prompts.py --verify`,
`test_prompt_data_parity.py`, `test_p16_prose_pattern_corpus_parity.py` (the frozen-corpus pattern to
copy), 12 golden `real_samples/` pairs, and **CR158 prompt-version stamp is done** — the dependency
CR157 names.

Genuinely missing, and where feasibility thins:

- **The CI gate.** Deterministic scorers can gate a commit — free and reproducible. An LLM-judge scorer
  cannot: slow and non-deterministic. It belongs on the promotion path or in CR157's weekly batch.
- **A pinnable judge.** On-prem, the only option is the model under test judging itself. Kimi via
  `KIMI_API_KEY` is independent but external, unpinned and rate-limited — `EXTERNAL_REVIEW.md` records
  both traps already hit (CR130's shared reasoning/answer budget returning an empty reply; a
  `ConnectionResetError` that killed the pool).

### §8 Secondary levers — **SPLIT**

- **PM structured output — FEASIBLE, proven live.** Bounded cost: `LLMGateway.stream_chat()` has no
  `response_format` parameter, so this touches the ABC plus all four providers. The Anthropic fallback
  needs tool-use rather than `response_format`, so the gateway must **degrade loudly** (CR040) rather
  than silently drop the constraint on failover. `enforce_safety_floor` stays where it is — the probe
  returned a schema-valid `"size_pct": 100`.
- **Few-shot anchoring — REJECTED.** It contradicts the memo's own §10 (*"the direction is
  subtraction"*), and DEF245 is the proof: a worked example in the Bear's prompt carried a literal
  `-25%` and **that became the most common downside figure in the corpus**. A golden reply embedded in a
  prompt is a fabrication vector with a defect already on the board.
- **Freshness honesty** (render social cache age) — feasible, small, honest.
- **Tiering / temperature** — feasible, config-only, gated on §7 having something to measure with.

### §10 "What not to chase" — **endorsed, and strengthened**

Phase 3b already recommended holding Phase 4b. The probe adds to it: the deployed server does
constrained decoding **today**, so the PM's JSON can be made unbreakable without touching the model —
which removes the strongest remaining argument for the model arm.

## 3. Recommended order

By accuracy gained ÷ blast radius, with the memo's dependency inverted — subtract before you add.

| # | Work | Lever |
|---|---|---|
| 1 | DEF236 + DEF251 — unify the output contract, re-derive `_AGENT_MAX_TOKENS` from measured output | §3.1 |
| 2 | Risk-state block + DEF241 residue (Bull, RM) + render `trade_asymmetry` | §1, §2 |
| 3 | CR156 — deterministic verified-facts recap above the PM transcript | §6.3 |
| 4 | CR145 Tier A — market cap / FCF $ / gross debt; delete the `32.4% gross margins` example | §5 prep |
| 5 | Deterministic scorer gate over the frozen golden set | §7 |
| 6 | CR145 Tier C — per-agent fact sheets (**needs Saiful's visibility-matrix call**) | §5 |
| 7 | PM structured output via `response_format` | §8 |

Not scheduled: §4 as specified, §6.2, few-shot anchoring, the model arm.

## 4. Findings dropped after verification

Per this CR's acceptance line — *"findings dropped after verification are listed with the reason"*.

| Dropped | Reason |
|---|---|
| §4 numeric grounding check, as a per-turn guard | ~100% false-positive rate on the measured epoch (M3); a general pattern over agent prose, the class DEF231/234/235/242 came from; barred by CR144 |
| §6.2 `[unverified figure]` transcript labels | Depends on §4 and puts its false positives in prose the user reads |
| §8 few-shot anchoring | DEF245 measured a worked example's literal `-25%` becoming the corpus's most common downside figure |
| §3 part 2, prose-agent repair loop | Not rejected — deferred. Zero measured demand (`0/18`), doubles worst-case calls on a streaming path, and needs DEF067's never-changes-substance guard rebuilt |
| Phase 4b model arm | E1 near zero; three of four remaining failures are our code; constrained decoding is already available on the deployed server |

## 5. Governance

This document mints nothing. Every receiving item already exists: CR145 (proposed, four tiers),
CR146–CR156 (proposed, per agent), CR157 (proposed, outcome loop), CR158 (done), DEF236 / DEF241 /
DEF251 (open). The verdict **re-ranks work already on the board** and records five drops.
