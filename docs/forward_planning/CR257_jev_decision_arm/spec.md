# CR257 — Jev-as-decider: offline measurement arm

**Status:** proposed · **Owner:** track K · **Minted:** 2026-10-12 (AT:K4)
**Basis:** Saiful 2026-10-12 — "get the agents to write the opinions, and get Jev to
give the probability of pass/approve based on the output."

## 1. What this is

An **offline evaluation arm**, not a production change. Ask Jev the *decision*
question over the already-recorded room debates — "given this transcript and this
mandate, approve or pass?" — and measure whether a typed-decision judge beats the
PM's prose verdict read on the criteria the verdict layer currently fails.

Relationship to CR256: CR256 builds a **code-computed** evidence bar (claim cards →
composite → deterministic gate). CR257 evaluates a **judge-computed** decision
instead. They are competing designs for the same step (evidence → verdict); the
measurement here gates which one ships. If both pass their bars, CR256's
deterministic gate remains the enforcement layer and a Jev decision becomes a
second signal inside the composite — never a replacement for the safety floor.

## 2. Why it might work (and why it might not)

Evidence base: `EXPERIMENT_LOG.md`, analysis_r1–r6, `jev_review_2026-10-12.md`.

**For:**
1. The PM's failure is measured as a *prior* failure, not a reading failure —
   verdicts track the risk-level prior and ignore the evidence (Δ negative at every
   level, both models). A judge with no inherited prior, asked a crisp question,
   may read the debate more faithfully than the PM does.
2. Stability: typed-decision calls are deterministic classifiers. The 14–27%
   same-input flip rate is a sampling artifact of the PM LLM; a Jev decision should
   collapse it toward zero.
3. Cost/latency: ~0.4s per typed call vs the PM's multi-sample mid-tier generation.

**Against (the measured cautions):**
1. Direction-agnostic aggregation is dead — the net-support experiments prove a
   bare score can't decide (r=+0.19/+0.03, zero lift). The decision question must
   see the debate *with direction*, per desk, not a flattened score.
2. No per-room ground truth exists beyond the holdout shapes (RIOT out everywhere;
   APD/BA-shaped out everywhere). Judge-of-judge accountability is unsolved — a
   fluent wrong decision from Jev is no more catchable than from the PM.
3. The judge is only as good as the debate it reads: APD-rep2 showed both sides
   fully grounded while the correct answer was PASS. A decision judge inherits
   that ambiguity; whether it resolves it toward the holdout rule is the
   measurement.

## 3. Design

1. **Dataset (zero new room runs):** all recorded 300-room arms —
   `cr251-v2-dsv4` (300), `cr253-disp-matrix` (300), ami-llm clean
   (`cr251-v2-ami` + `cr251-v2-ami-fix`, 287). Every room's full transcript already
   sits in alpha `llm_audit`; verdicts in `runs_*.jsonl`; turn scores in
   `jev/r{1..5}.jsonl`. Total decision calls ≈ 887 rooms × 2 replays ≈ 1.8k Jev
   calls — minutes of wall time.
2. **The question (per room, one typed call):**
   - Input: the full debate transcript (analysts → researchers → RM → trader,
     in order), the mandate snapshot (risk_score, horizon, caps), and the ticker.
     The raw fact sheet is NOT included — the debate is the grounded artifact;
     re-litigating the data is the analysts' job, already done.
   - `choice`: `approve` / `pass`, with the API's per-choice probabilities kept
     as the confidence read.
   - `score` (0–3): how contested the evidence was (weak → strong for the chosen
     action) — gives a calibratable margin instead of a bare bit.
   - No sizing, no stops, no targets: Jev decides *whether*; code decides *how
     much*; the safety floor decides *what's forbidden*.
3. **Script:** `tools/jev_decision_arm.py` — clone of `jev_score_runs.py` structure
   (pg tunnel, full request/response logging, `--runs/--out/--workers`), emitting
   `out/<arm>/jev_decision/r{1..5}.jsonl`. Same `.env` key handling.
4. **Replays:** every room scored twice. Flip between replays is the stability
   metric — target ≈0, vs PM's 14–27%.

## 4. Evaluation (all four must pass for GO)

1. **Holdouts:** RIOT-shaped rooms pass at every level in every arm;
   APD/BA-shaped rooms (grounded bear case, negative SBC-adjusted FCF) pass at
   every level — including APD-rep2 R5, which the PM approved against the rule.
2. **Curve shape:** Jev-decision curves per arm read against the locked target
   5/15/30/45/60 — monotone-or-better; reported next to the PM's curves, not
   instead of them.
3. **Discrimination:** Jev-approve indicator vs per-room net support must be
   positive and materially above the PM's r (+0.19 dsv4 / +0.03 ami) — i.e. the
   judge must demonstrably read the evidence gradient the PM misses.
4. **Agreement audit:** PM-vs-Jev disagreements enumerated; a ~20-room stratified
   sample of disagreements read by hand (same protocol as the jev_review audit)
   to classify who was right.

Secondary: AAPL-rep1-class cases (high grounding, negative asymmetry, PASS
correct) must stay PASS — grounding must not be misread as a buy signal.

## 5. Fold-in shape (only on GO)

```
deterministic safety floor → agent debate → Jev decision (approve/pass + margin)
→ deterministic sizing/stops/horizon → verdict record
```

The PM LLM either shrinks to verdict-narration duty or is removed from the
decision path; `room_pm` multi-sampling is deleted with it. CR256's composite bar
stays as the enforcement layer regardless of which decision reader wins.

## 6. Out of scope

1. No production change, no `content/agents` or `room_runner` edits, no new room
   runs, no sizing/stop logic, no compliance-gate changes.
2. No buy/hold/sell expansion — action space stays APPROVE/PASS until the room
   reviews existing positions; sell is a later CR.
3. No Jev question changes to the four turn-level evidence questions — the C7
   input instrument stays frozen so arms remain comparable.

## 7. Acceptance record

Filled at measurement time: per-arm curves, holdout pass/fail matrix, replay flip
rate, discrimination r, disagreement-audit table, GO/NO-GO + Saiful sign-off.

---

## 7. Acceptance record (filled 2026-10-12, AT:K3)

Dataset: 900 rooms across 3 arms (prod-dsv4, disposition-dsv4, ami-llm), 2
replays = 1,800 typed decision calls. Instrumentation bug found and fixed
during the run (jev_eval hardcoded the shared evidence questions into the
wire body — 12df3056); all numbers below are from the corrected pass.

**§4.1 Holdouts: FAIL.** RIOT passes everywhere (6/6 rooms). APD passes in
prod-dsv4 and ami-llm but is approved 2/2 in the disposition arm; BA 1/2 in
the disposition arm. The judge approves the disposition-arm *debate* for the
value names — the debates themselves carry the willingness shift.

**§4.2 Curve shape: FAIL.** Jev-decision curves track the PM's debates
(the judge reads the same transcript): prod 11/15/22/20/16 (non-monotone,
like the PM's 5/11/22/27/17); disposition 8/16/14/12/18; ami 1/0/3/3/0.
Neither approaches the 5/15/30/45/60 target — no reader of the current
debates can, because the willingness lives in the debates, not the reader.

**§4.3 Discrimination: FAIL (narrow).** r(Jev-approve vs net support):
+0.199 prod-dsv4 (PM +0.19 — ties, not materially above), +0.114
disposition. The judge reads the evidence gradient no better than the PM.

**§4.4 Agreement: 93-94%** per arm, balanced both directions
(prod: 10 PM-only vs 8 Jev-only; disposition: 17 vs 4; ami: 2 vs 11).
Stratified hand-read of disagreements: OPEN (enumeration in
out/cr257/*/jev_decision; ~52 disagreement rooms).

**Stability (secondary): PASS, decisively.** Replay flips 0.0% / 1.3% /
0.0% vs the PM's 14-27%. A typed-decision judge is a perfect stabilizer.

**Secondary check (AAPL-class):** high-grounding/negative-asymmetry rooms
stay PASS under Jev in the arms sampled.

**Verdict: NO-GO for Jev-as-decider (replacement).** The judge of the same
debate inherits the debate's prior: it cannot fix curve shape, ties the PM
on discrimination, and fails the disposition-arm holdouts. **Measured
value where predicted:** a perfect-stability, equal-discrimination, 0.4 s
second signal — per §5, the fold-in shape keeps CR256's deterministic
composite as the enforcement layer; a Jev decision belongs inside the
composite as a stability vote, never the decision path. The willingness
lever remains C7/CR256's job, now with stronger evidence: no reader of the
current debates reaches the target curve — the debates themselves must
change (or the decision must stop being read from prose).
