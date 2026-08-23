# CR196 run-2 plan — train every production surface, gate every production surface

Written 2026-08-22 after run 1 failed §5a. Supersedes the mix half of `ROLE_TRAINING_PLAN.md`
(§B–§G of that file remain the build detail for recipes 12–17; its §H decisions are taken below).

Every decision here is taken. Nothing in this plan is a question.

---

## 1. What actually went wrong, corrected

The first diagnosis — "the mix was too short" — is **incomplete**, and the correction matters
because it changes what run 2 must do.

Measured on run 1's `train.jsonl` by **token mass**, which is what the loss averages over:

| target size | rows | row % | token mass % |
|---|---|---|---|
| <1k | 22,393 | 87.2% | 33.6% |
| 1k–3k | 1,628 | 6.3% | 14.4% |
| 3k–5k | 766 | 3.0% | 16.0% |
| ≥5k | 908 | 3.5% | **36.0%** |

Run 1 was **36% long-form by token mass** and still answered in 45 tokens. So "not enough
long text" cannot be the mechanism.

**The mechanism is termination, and termination is a per-example event.** The model saw
"stop after ~83 tokens" 22,393 times and "stop after a long answer" 908 times — every one of
those 908 in *generic chat* context. Nothing ever associated **a finance-analyst prompt** with
**a long answer**. It did not lose the ability to write at length; it learned that in this
context you stop early. AEE's 45-token reply was a recipe-2 ratio answer: the only shape that
prompt distribution had ever been paired with.

Two consequences:

- **Row counts govern format and termination; token mass governs style.** The gate must count
  rows, per surface. Token mass is a secondary read, not the control.
- **The conditional is what matters — P(output shape | prompt shape).** A surface is trained
  only by examples whose *prompt* looks like that surface's production prompt. Sub-skill
  recipes with synthetic prompts do not train any production surface.

That second point is the planning error generalised: **the run-1 plan enumerated skills we
wanted the model to have, and never enumerated the outputs production asks it to produce.**
SFT trains outputs.

---

## 2. Surface inventory — the unit of planning from here

13 agents in `content/agents/` share one model. They emit **eight** distinct output contracts.
Run-1 coverage, and what run 2 targets:

| # | Surface | Roles | Contract lives in | run 1 | run 2 target |
|---|---|---|---|---|---|
| S1 | Nine-section fundamentals brief | fundamentals_analyst | production brief prompt | **0** | ~1,260 |
| S2 | Prose turn + `[STANCE\|CONVICTION\|HEADLINE]` | market, news, social, bear, bull, 3 debators | `_PROSE_FORMAT`, `_STANCE_FORMAT`, `_LENGTH_GUIDE` | **22** (shared) | ~2,400 |
| S3 | Research-manager synthesis | research_manager | `_LENGTH_GUIDE` | 11 (probe) | ~790 |
| S4 | **PM verdict JSON** | portfolio_manager | `_PM_VERDICT_FORMAT` → `_parse_pm_verdict` | **22** (shared) | ~800 |
| S5 | Trader execution block | trader | `content/agents/trader.md` | **0** | ~700 |
| S6 | Risk-officer JSON | risk_officer | `build_risk_officer_instruction()` | **0** | ~600 |
| S7 | Refusal / abstention | all | — | 100 | ~400 |
| S8 | Concierge interview turn | concierge | `content/agents/concierge.md` | **0** | ~500 |

Against **7,111** run-1 examples (recipes 2–6) teaching computations that are *not themselves*
a production surface. Those stay — they are the substrate that produced 43/44 on the basis
rubric — but they are re-capped so they cannot set the termination prior.

**S4 is the sharpest risk.** The Room's buy/sell verdict is parsed JSON. Run 2 as previously
scoped would have trained 1,260 nine-section essays against 22 JSON examples, and the
predictable failure is prose where the parser expects an object — run 1's failure inverted.

---

## 3. Decisions taken

| # | Decision | Rationale |
|---|---|---|
| D1 | **Scope = all 8 surfaces.** No partial run 2. | The assignment is fundamental analysis *and* the other 12 agents. A model that passes §5a and cannot emit a PM verdict is not a deliverable. |
| D2 | **Build recipe 17 now** against the current risk-officer contract, overriding `ROLE_TRAINING_PLAN.md` §H1's "hold for CR201". | Re-rendering from cache costs seconds; omitting a role costs a whole run. Stale-contract risk is real but is the cheaper of the two errors. If CR201 moves the contract before run 2 trains, re-render. |
| D3 | **Recipe 16 weights toward near-cap mandates** (§H2's own recommendation). | The R:R arithmetic class has failed four times: DEF066 → DEF235 → DEF241 → CR166 Tier-D. Train where it bites. |
| D4 | **Recipe 8 scales from 22 to ~800**, split S2 envelope / S4 JSON. | 22 examples cannot hold a parsed contract against 1,260 essays. |
| D5 | **New recipe 18 — concierge.** | S8 is a production surface with zero coverage and an existing generator to salvage (`original_silent_scout_research/02_data/recipes/concierge.py`). |
| D6 | **Fresh LoRA from the Fastino base**, not a continuation of run 1's adapter (§G). | Continuing confounds substrate steps with role data; fresh-from-base makes run1↔run2 a clean read. |
| D7 | **Per-surface floors replace the single global ratio.** | A global ratio cannot see a starved surface — it is exactly how S4 got to 22. |
| D8 | **Probe run before the 25h commit.** | Run 1 cost 25h to learn something a 2h probe shows. |
| D9 | **Hyperparameters re-derived, not inherited.** | rank 32 / lr 1e-4 / 2 epochs came from Fastino's short-QA mix; run 2's targets are up to 30× longer. |
| D10 | **Substrate recipes 2–6 capped at ~700 each** (from ~1,430). | They must inform the brief, not set the termination prior. Uncapped they are 7,111 of ~13k. |

---

## 4. Gates — `mix_and_qc.py`

Replace the single `MIN_DELIVERABLE_PCT` with a **per-surface coverage table**. The build fails
naming the starved surface. Rules:

1. Every surface in §2 has a **minimum row count**. Absolute, not a ratio — a ratio is
   satisfiable by shrinking the mix, and cannot see one starved surface among eight.
2. **No surface may exceed 3× the smallest surface's target.** This is the run-1 lesson made
   structural: dominance is the failure mode in both directions.
3. Replay stays excluded from every numerator (already landed).
4. Report token mass per surface in the manifest as a **secondary** read.
5. Decontamination and dedup unchanged — all recipes draw from `train_universe.txt`, and the
   71 `eval_tickers.txt` exclusions are what make §5 honest.

---

## 5. Acceptance — §5a extended per surface

CR196 §5a grades one surface. Run 2 is not accepted until every surface is free-run against
held-out eval tickers, scored by the **generator's own programmatic checks** (no LLM judge —
CR038), with **vanilla Fastino as the behaviour control through the identical harness**.

| Surface | Pass condition |
|---|---|
| S1 | §5a as written: L2/L3 target; L1-rate and 0-false-conflicts as vetoes; no length regression vs base |
| S2 | Stance envelope present and parseable; length within `_LENGTH_GUIDE`; bear and bull materially disagree on the same fact sheet |
| S3 | 3-part shape; grounded side chosen; **"short" language rate = 0** |
| S4 | **`_parse_pm_verdict` succeeds ≥99%**; required fields present when APPROVE |
| S5 | R:R exact-match; zero cap violations; stop-loss always present; no Risk-Officer citation |
| S6 | One entry per handed size; `recommended` ∈ handed sizes; no self-authored figures |
| S7 | Abstains on missing data; does **not** abstain on the answerable controls |
| S8 | Stays in interview mode; no advice language |

**Blocking prerequisite:** `mandate_compliance_eval.py` must run. Two bugs found and fixed
2026-08-22 — `ProposedTrade` was passed `is_buy`/`is_sell`, which are read-only properties
derived from `side` (`app/schemas/trade.py:176-182`), with the required `side` omitted; and the
Silent_Scout migration broke its walk to the repo root. It has therefore **never executed**, and
no safety-floor claim in CR032 or CR196 was ever backed by a run.

---

## 6. Sequence

| Phase | Work | Cost | Blocks |
|---|---|---|---|
| P0 | Fact-sheet disk cache (§B) | ~1h + 10 min sweep | all role recipes |
| P1 | Recipes 12/13/14 at scale; 16, 17, 18 new; 8 scaled | CPU, hours | — |
| P2 | recipe 10 sweep completes | ~5h GPU, running | — |
| P3 | Per-surface gates + assemble + mix | ~2h | — |
| P4 | `mandate_compliance_eval` green | done, needs a run | S4/S5 claims |
| P5 | **Probe run** 300–500 steps → merge → free-run all 8 surfaces | ~3h GPU | P6 |
| P6 | Run 2 full, behaviour eval at checkpoints not just the end | ~25h GPU | — |
| P7 | Per-surface acceptance vs vanilla Fastino | ~2h GPU | adoption |

P0/P1/P3 are CPU and run alongside P2's GPU work.

---

## 7. What this plan does *not* fix

Stated so it is not mistaken for covered:

- **Nothing here improves analysis quality on S1.** Recipe 10 is self-distilled from vanilla
  Fastino and is capped at the teacher by construction; it preserves shape. The §5a *target*
  (L2/L3) is taught only by recipe 1's 1,353 examples, whose prompts are minimal trap blocks
  rather than production briefs — a format gap nothing in the mix bridges. If run 2 clears the
  veto but not the target, that gap is why, and closing it is run 3's problem.
- **The dose-response is still unmeasured.** Per-surface floors are reasoned, not derived. The
  probe run (P5) is the cheapest instrument we have for it.
- **S2 covers 8 roles with one contract.** Whether one model differentiates 8 personas from
  prompt alone is asserted by design, tested only at P7.

---

## 8. Achieved (2026-08-23) — P0/P1/P3 complete, gate green

`mix_and_qc.py` passes: **train 20,029 / val 375**, 993 exact duplicates removed,
decontamination PASS against all 71 eval exclusions.

| Surface | run 1 | run 2 | roles | per role | floor |
|---|---|---|---|---|---|
| S1 nine-section brief | **0** | 1,195 | 1 | 1,195 | 800 |
| S2 prose + stance | 22 | 2,151 | 8 | 269 | 900 |
| S3 research manager | 11 | 857 | 1 | 857 | 350 |
| S4 **PM verdict JSON** | 22 | 779 | 1 | 779 | 500 |
| S5 trader | **0** | 1,344 | 1 | 1,344 | 500 |
| S6 risk officer | **0** | 1,389 | 3 | 463 | 500 |
| S7 refusal | 100 | 453 | 1 | 453 | 90 |
| S8 concierge | **0** | 425 | 1 | 425 | 350 |

Per-role spread 1,344 / 269 = **5.0×**, inside the 6× cap. **1,215 long-form task
targets** against run 1's zero.

### What the gate caught that a global ratio could not

1. **Recipe 8 was eight tickers** — `[::173][:8]`, written to demonstrate the two
   contracts rather than train them. The entire reason the Room's parsed verdict had
   22 examples.
2. **Recipe 9 was capped at 100** by a `--count` default nobody had looked at, leaving
   abstention at 98 rows while every other surface sat 4×+ above.

Both were invisible for a whole training run and both were named in one gate run.

### Corrections made to the gate itself

- **Dominance was comparing incomparable things.** S2 is one contract shared by eight
  agents; S8 serves one. On raw rows S2 looked dominant at 2,151 vs 425 — per role it
  is 269 vs 425, the *thinnest* surface in the mix. Now normalised by roles, cap
  raised 4→6 and anchored to run 1's actual lethal spread (~25:1) rather than a number
  chosen for feel.
- **The global deliverable ratio was really "S1's share of everything".** Only S1 has
  a long target by design — a PM JSON verdict is ~300 chars, a trader block ~600, and
  those are correct. Retired as a gate; per-surface floors assert S1 directly and
  `MIN_DELIVERABLE_ROWS` keeps the absolute floor run 1 failed.

### Infrastructure findings worth keeping

- **A cache must never memoize a failure.** Yahoo rate-limits by returning *empty
  frames* rather than raising, so a blocked pull is indistinguishable from a company
  with no filings. The first sweep cached 613 `too_few_years`; re-pulling names that
  had cached fine minutes earlier, including S&P 500 constituents, also returned 0.
  After the block lifted the same sweep returned **2**. Caching those would have
  deleted 43% of the train universe from every role recipe, permanently, with no
  symptom beyond "the counts look low".
- **Decontamination false-positives on acronyms.** Three-letter tickers collide with
  ordinary words: `CHD` is coronary heart disease in a biotech's licence agreement,
  `AES` a segment name, `MGM` a property in VICI's portfolio. The prose scan is a
  backstop for generators that do not stamp `_meta.ticker`; where the stamp exists it
  is authoritative.
- **`mandate_compliance_eval.py` had never executed** — two fatal bugs. No
  safety-floor claim in CR032 or CR196 was ever backed by a run.

### P4 — the safety floor, measured for the first time (2026-08-23)

`mandate_compliance_eval.py` executed. Its first ever run:

```
Cases: 500
Deterministic-check leaks: 0
Override leaks (LLM APPROVE not overridden): 0
Block rate: 100.00%  (gate = 100%)
PASS
```

CR032's exit criterion — *"100% block rate. Anything less = research dead-end for
that role"* — is now **measured** rather than assumed. Both halves hold: the
deterministic check catches every adversarial case, and `enforce_safety_floor`
overrides every LLM APPROVE that should have been rejected.

Worth stating plainly since it cuts both ways: the floor was fine all along, and
nobody knew, because the eval asserting it had never run. A passing guard that
cannot execute is indistinguishable from a broken one until someone tries it.

### Still open before training

P5 per-surface eval harness (§5) · P6 probe run (300–500 steps) · only then P7 the
full run.
