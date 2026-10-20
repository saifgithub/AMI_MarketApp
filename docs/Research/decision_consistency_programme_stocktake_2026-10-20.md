# The Decision-Consistency Programme — full stock-take, 2026-10-20

A stock-take of every experiment run in the CR251→CR262 programme and the
state now live on Alpha. Written as the raw material for a paper: the
problem, the system, the experimental matrix, what each lever did, and what
remains open.

---

## 1. The problem

**AMI Trade** convenes a 12-agent LLM "trading floor" (4 analysts, 2
researchers, a research manager, an execution desk, 3 risk debators, a
portfolio manager acting as CIO) over a deterministic per-ticker fact sheet,
and must produce an APPROVE/PASS verdict whose **approval rate rises with
the user's stated risk appetite** (risk score 1–5). The target curve is
5/15/30/45/46 approvals per 60 rooms.

**The disease (measured, CR251):** production curves were non-monotone —
ami-llm 0/0/4/10/20 (flat switch), dsv4 5/11/22/27/**17** (inverts at R5).
Worse, re-running the *same* ticker under identical data flipped the verdict
27–47% of the time at R4–R5 on every prompt arm tried. Discrimination and
stability both failed.

## 2. The system (what stays fixed across arms)

Fact sheet → 12 sequential/concurrent agent turns (persona prompts, stance
envelope, transcript) → risk-debator size spread (computed in code) → PM
JSON verdict (5-candidate ensemble) → deterministic safety floor → verdict.
Size is ceiling-clamped to the mandate risk-tier cap; no floor (PM may
state any smaller size). Evidence channels: stance envelopes (CR106),
GAPS tails (CR219), CLAIMS/OBJECTIONS card blocks (CR256, flag-gated).

## 3. The experimental matrix (every arm, all conditions)

Room counts are APPROVE/60 at risk levels 1–5; flips = rep-to-rep verdict
changes per ticker (2–3 reps). Prompt state: "prod" = backend-default,
"disp" = + CR253 disposition ladder (now folded into prod), "tm-all" =
teammate wholesale suite, "cap1" = size pinned at 1%.

| # | model (identity) | thinking | prompts | curve R1–R5 | flips | min/room | rooms |
|---|---|---|---|---|---|---|---|
| 1 | dsv4-Flash-0731 | off | prod | 5/11/22/27/17 | 17% | — | 300 |
| 2 | ami-llm (qwen38-flash-next-abliterated-nvfp4) | off | prod | 0/0/4/10/20 | 19% | ~50 | 300 |
| 3 | dsv4 | off | disp | 1/7/13/15/19 | — | — | 300 |
| 4 | ami | off | disp | 0/0/3/22/36 | 0/0/10/37/27% | ~50 | 300 |
| 5 | ami | off | cap1 | 1/5/9/11/11 | — | — | 300 |
| 6a | dsv4 | off | tm-all | R5 h2h: 20 vs prod 17 | — | — | 60×2 |
| 6b | dsv4 | off | tm-all converted | monotone, 27% flips, horizon still broken | 27% | — | 300 |
| 6c | ami | off | tm-all | 0/1/4/7/16 NO-GO | 20–27% | — | 300 |
| 7 | kolibri-1 (Aleph-Alpha 78B MoE, 3.46B active) | **on** | prod | **0/0/12/17/18** | **10%** | 53.7 | 300 |
| 8 | kolibri-1 | off | disp | 3/1/9/17/14 | 10/3/33/37/27% | 10.9 | 300 |
| 9 | kolibri-1 | off | prod | R5 7/60 → **stopped** (too conservative) | — | ~6 | 101 |
| 10 | ami | **on** | disp | 0/0/1/4/6 (124 rms, in flight) | TBD | 90.4 | 124/300 |
| 11 | **Ling-3.0-flash-Fin-fp4** (Ant Group, 124B/5.1B active, MXFP4, finance-trained) | off | prod+disp | **4/11/19/29/27** | 13/17/23/40/23% | **9.1** | 300 |
| 12 | dsv4 (+ GLM-5.3-Flash, Qwen3.8-Flash on DeepInfra) | off | prod | measured, unpromoted | — | — | ~90 |

Card-channel stability (CR256, layer-2 gate ICC(A,1) ≥ 0.85, dsv4-Flash,
risk 4, 30 tickers × 3 reps): voluntary filing **0.62** → post-hoc repair
0.67 → **in-turn mechanical enforcement 0.868 PASS** (98.3% filing, 4/4
bounded re-asks, zero transcript leaks).

## 4. What each lever did (the findings)

1. **Prompt lever — disposition conversion (CR253).** A 15-line PM block
   (size decoupled from the decision; approval propensity spelled out per
   risk score) is the *only* prompt-side change that fixed discrimination:
   ami R3–R5 correlation r=+0.62, dsv4 smooth 1/7/13/15/19. The wholesale
   teammate suite (tm-all) failed on two models; size-pinning (cap1) killed
   discrimination (r +0.04). Prompt iteration beyond this was measured-dead.
   **The tm-all comparative record (three runs):** (a) a controlled dsv4
   head-to-head at R5 (same tickers/mandate/model/day-window) found tm-all
   contract-viable — zero parse/envelope/NO_VERDICT failures on a third
   model family, slightly more permissive than production (20 vs 17/60),
   sizes argued wider (1.5–5.0% vs 3.5–5.0%) — but its hardcoded constitution
   overrode the mandate horizon (60–365d vs mandate-driven), the D2 refusal;
   (b) the converted suite (mandate-referenced horizon, CR254 salvage) went
   monotone on dsv4 but kept 27% flips and still needed horizon enforcement;
   (c) on ami the full converted matrix was flat (0/1/4/7/16) — NO-GO
   reproduced on a second model. Verdict: the personas' *analysis* content
   moves stances (13/30 tickers on dsv4); their *constitutional overrides*
   are the poison; wholesale adoption dead, per-element salvage only.
2. **Enforcement lever — in-turn card channel (CR256).** LLM evidence
   claims are only reproducible when filing is mechanical: prompts alone
   produced 0–92% per-desk filing rates (salience noise, ICC 0.62); a
   flag-gated envelope + one bounded re-ask produced 98.3% filing and
   ICC 0.868. Post-hoc repair is a fresh generation — top-up only, never
   foundation.
3. **Cognition lever — thinking (CR259).** The cleanest attribution in the
   programme: same model, same prompts, thinking on vs off (kolibri 13 v
   14): stability 10%→27–37% flips, willingness halved, latency 54→11 min.
   **Thinking is the stability lever; it costs ~5× latency.** On ami-llm
   the picture darkens: thinking-on blows the 900s per-turn envelope
   (~1.9 scripted desk fallbacks/room vs 0.17) and drives willingness to
   near-zero — the lever is model-specific, not universal.
4. **Model lever.** At identical prompts and data: the finance-trained
   model (Ling) produced the best-calibrated curve — strictly monotone
   R1→R4, closest to target, unanimous-approve cohort exactly the
   mega-cap quality names; the general reasoning model (kolibri) was
   steadiest with thinking on but too slow, and over-conservative with it
   off; the general incumbents (ami/dsv4) discriminate only with the
   disposition ladder. With the fact sheet supplying the finance data, a
   model's marginal value is **calibration and judgment discipline**, not
   finance knowledge.
5. **Measurement infrastructure.** Everything above rests on a harness that
   runs the production code path against real market data with full audit:
   30×5×2 matrices per arm, rep-level flip census, per-ticker verdict
   matrices, bounded re-ask telemetry. The audit-watcher outage (Oct 18)
   demonstrated why mechanical gates exist: two lanes shipped red in its
   absence.

## 5. What is in production now (alpha-2026-10-18-2)

1. **PM disposition ladder** — folded into `content/agents/portfolio_manager.md`;
   every convene on Alpha reasons with the risk-scaled approval disposition.
2. **Explicit `enable_thinking: false`** on every vLLM call (CR259
   amendment) — thinking is OFF fleet-wide by construction, not by server
   default.
3. **Model: ami-llm** (qwen38-flash-next-abliterated-nvfp4) on all tiers at
   `vllm > anthropic > mock` preference; DGX Spark :8000.
4. **Built, validated, NOT enabled:** the CR256 CLAIMS/OBJECTIONS card
   envelope (`ROOM_CARDS_ENVELOPE_ENABLED`, default OFF — ICC 0.868 on
   dsv4; needs per-model acceptance before fold-in).
5. Deliberately parked: tm-all, cap1, kolibri (both modes), Ling (pending
   R4-flip root-cause + license confirmation), thinking tiers (pending the
   paid/async product decision).

## 6. Open questions (the paper's future-work section)

1. **Arm 15 completion** (ami thinking-on, 124/300): does the near-zero
   willingness curve hold? Implication: thinking on incumbents is a dead end
   at production timeouts.
2. **Ling thinking-on arm**: does finance-calibration + thinking reproduce
   kolibri-on's 10% flips at acceptable latency? Ling's probe reasoning was
   modest (381 tokens vs ami's heavy traces).
3. **Card-envelope fold-in per model**: layer-2 passed on dsv4 (0.868);
   ami/Ling arms needed; then the deterministic evidence-bar verdict gate
   (CR256's original purpose) can be acceptance-tested.
4. **R4 flip root-cause** (Ling 40% at R4, concentrated in DHR/SEDG/TMO):
   is "approve any defensible thesis" inherently straddle-prone, or a
   prompt-precision fix?
5. **CR257 (Jev-as-decider)**: the LLM-judge decision arm — agents opine,
   the judge emits the call; competing design against CR256's code-computed
   bar. Drafted, unsent.
6. **Sized conviction**: code allows below-cap sizes today (ceiling-clamped
   only); the disposition ladder currently instructs size=cap. Letting the
   PM approve borderline theses at half-cap is a prompt change with
   re-measurement obligations.
7. **The 30×5 acceptance run per model** — the final gate for any
   production model change; the programme's definition of done.

## 7. Numbers worth quoting in the paper

- 5 models × 4 prompt states × 2 cognition modes ≈ **3,400+ measured rooms**
  since 2026-10-01; every arm ≥ 90 rooms, most 300.
- Best curve: Ling 4/11/19/29/27 (target 5/15/30/45/46) at 9.1 min/room.
- Steadiest: kolibri-on 10% flips at 53.7 min/room.
- Fastest stable-enough: kolibri-off 10.9 min at 27–37% flips; Ling 9.1 min
  at 13–40%.
- Card channel: 0.62 → 0.868 ICC via enforcement, 98.3% filing.
- Thinking attribution: 10% → 27–37% flips on the same weights, same data.
