# DEF095 — The Trader narrates R:R and drawdown figures nothing checks, and it got them wrong on every live trade in the last two days

**Filed:** 2026-07-23 · **Source:** prompt-reported (Saiful: *"check if the llm had done any math in 2 days"*)
**Track:** AT:R59 (protect-the-Room lane — diagnosis + brief; the build team fixes)

---

## What was asked, and the short answer

Saiful asked whether the LLM had done any math in the last two days. **Yes — three convenes' worth,
and every derived figure it produced was wrong.** The one-step arithmetic was fine. Anything
requiring two steps was not, and nothing in the system noticed.

`llm_audit` on melehost, window `now() - interval '2 days'`, measured 2026-07-23:

| day | flow | calls | errors |
|---|---|---:|---:|
| 2026-07-21 | room | 22 | 0 |
| 2026-07-21 | room_pm | 2 | 0 |
| 2026-07-22 | room | 11 | 0 |
| 2026-07-22 | room_pm | 1 | 0 |
| 2026-07-22 | concierge_floor | 3 | 0 |

39 calls, all `provider=vllm`, zero errors — 3 convenes (SCHD and VGK on 07-21, INGN on 07-22) plus
3 Concierge messages. Every one of the 36 agent turns contains digits. Two of the three convenes
produced a trade with levels; the third was a `WAIT` with no numbers to get wrong.

---

## The measurements

Each stated figure below is checked against **our own** `trading_math` functions —
`risk_reward()`, `trade_asymmetry()` (`trading_math/trade.py:22,47`) and
`drawdown_contribution()` (`trading_math/risk.py:24`) — not against mental arithmetic.

**Convene 1 — SCHD, 2026-07-21.** Trader proposed entry `$32.75`, stop `$29.60`, target `$33.50`,
size 10%.

| stated by the agent | what the levels imply | verdict |
|---|---|---|
| *"Stop: $29.60 (10% below entry)"* | 9.62% | ✅ fine |
| *"contributing only ~1.0pt to portfolio drawdown risk"* | 0.962 pt | ✅ correct |
| ***"R:R: 2.5:1"*** | **0.2:1** | ❌ **12.5× overstated** |

The setup is **2.3% upside against 9.6% downside**. It was narrated as a 2.5:1 trade. In the same
paragraph the Trader writes *"entering at $32.75 near the $33.5 resistance leaves minimal immediate
upside"* — it describes the asymmetry correctly in prose and then states a ratio that contradicts
its own sentence.

**The PM approved it** at 3.0%, and added its own wrong figure:

| stated by the PM | actual | verdict |
|---|---|---|
| *"strictly capping portfolio drawdown exposure at ~0.54%"* | 0.289 pt | ❌ 1.9× overstated |

**Convene 2 — VGK, 2026-07-21.** Trader: entry `$90.00`, stop `$86.50`, targets `$90.75` then
`$95.00+`, size 2.0%.

| stated by the agent | actual | verdict |
|---|---|---|
| *"4% below breakout entry"* | 3.89% | ✅ fine |
| **_"R:R: >2:1"_** | **1.4:1** against the $95 target; **0.2:1** against its own first target | ❌ |
| **_"~2.5% of portfolio drawdown risk"_** | **0.078 pt** | ❌ **32× overstated** |

Also internally contradictory: the prose says *"I will size the position conservatively at 2.0%"*,
the structured line below says `Size: 0%`.

**Convene 3 — INGN, 2026-07-22.** `WAIT`, `R:R: N/A`, no levels. Nothing to check, nothing wrong.

**The pattern is clean and worth naming:** the model reliably computes a *percentage difference
between two prices it was given*. It reliably fails at anything needing two inputs combined — a
ratio of two differences (R:R), or a product (size × stop distance). Those are exactly the figures
`trading_math` exists to compute, and exactly the ones a trading-education app teaches users to
judge a setup by.

---

## Why nothing caught it

Three independent reasons, each fixable.

**1. The coherence check only looks at the PM, and only when the PM volunteers a ratio.**
`_rr_incoherence_flag()` (`room_runner.py:588-604`, CR046 M06) is real and correct — but line 601
reads `if stated is None or rr_is_coherent(...): return None`. SCHD's PM narration stated no ratio,
so the check returned `None` and passed silently. Meanwhile the **Trader's** `R:R: 2.5:1` — the
number that actually drove the debate — is free prose in the transcript, inspected by nothing.

**2. Even when it fires, it is telemetry.** Its own docstring: *"Flag only — the safety floor owns
vetoes; this never changes the verdict."* Nothing reaches the user. A user reading the transcript
sees `R:R: 2.5:1` on a 0.2:1 trade with no annotation.

**3. The transcript is the contagion vector.** The Trader speaks in the EXECUTION phase. The three
Risk debators, and the PM, all read its output as `Transcript so far:`. A wrong ratio doesn't sit in
one message — it becomes the premise the rest of the Room reasons from. The Neutral Debator in
convene 2 is already quoting the Trader's figures back.

**And the drawdown number specifically:** `room_prompts.py:201` sets
`proposal = trade_proposal if phase in ("RISK", "VERDICT") else None` (DEF066), so the Trader —
EXECUTION phase — is the one agent that proposes levels and **never receives** the derived
`drawdown_contribution()` figure. It was structurally required to invent one, and did.

---

## Why this is serious

This is not a cosmetic slip. AMI is a *training simulator*; risk-reward is the single number the
curriculum teaches users to judge a setup by. On SCHD the Room presented a 2.3%-upside /
9.6%-downside trade as 2.5:1 favourable, and approved it. A user learning from that transcript
learns the wrong lesson twice — once about the trade, once about how to compute R:R.

It is also the **CR040 degrade-loudly class again**: the machinery to catch this exists, is wired,
and returns `None` on the path that matters.

---

## Proposed fix (build team decides the shape)

1. **Compute, don't narrate.** Derived figures — R:R, drawdown contribution, upside/downside — are
   computed by `trading_math` from the Trader's own levels and **injected** into the prompt for the
   agents that follow, the same way `_drawdown_snapshot_line()` already does for RISK/VERDICT. Give
   the Trader its own figures too, after it states levels, or have it state levels only.
2. **Extend the coherence check to the Trader**, and make `stated is None` on an agent that
   *proposed levels* a flagged condition rather than a silent pass.
3. **Surface it.** An incoherent narrated ratio should be visible — annotated in the transcript, or
   the figure replaced by the computed one. Telemetry nobody reads is not a control.
4. **Decide whether agents should state derived numbers at all.** The narrower, more robust fix is a
   prompt+parse contract where the Trader emits levels and the *system* renders every ratio. Per
   CR038, an instruction not to miscalculate is not a control; removing the opportunity is.

**Guard:** a test that feeds a known-incoherent Trader proposal through the Room and asserts the
figure a downstream agent receives is the computed one. Second: assert no agent output containing a
`R:R:` line survives without having been checked against `rr_is_coherent()`.

---

## Governance

Relates to **CR046** M06 (`rr_is_coherent`, the check that exists but doesn't reach here),
**DEF066** (the phase gating that starves the Trader of its own derived figure), **CR040**
(degrade loudly), **CR038** (prompt instructions are not controls), and **DEF056** (PM verdict
parsing). Sample size is small — 3 convenes — but it is *every* convene in the window and the
failure rate on derived figures is 4 of 4.
