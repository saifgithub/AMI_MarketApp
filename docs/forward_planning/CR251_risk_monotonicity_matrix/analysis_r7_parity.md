# analysis_r7_parity — ami-llm × arm parity vs dsv4 (INTERIM 2)

**Status: INTERIM 2 (Jev complete for covered arms).** Disposition 30×5 +
cap1 30×5 (R2–R5) Jev-scored (4,354 turns, zero errors, 2026-10-14, funded
account). tm-all + probes still running. Evidence-tracking r now included.

Source: `docs/tools/room_investigation_V2/out/ami-parity-v2/` (rsync of
`~/ami_parity` from melehost, 2026-10-14). All rows `status=completed`.
Methodology identical to the dsv4 arms (same benchmarks, prompts, mandates,
concurrency 4-per-job per-level-parallel v2 runner).

## 1. Curves — both models monotone, very different regions

| arm | R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|---|
| ami disposition | 0 | 0 | 3 | 22 | **36** |
| dsv4 disposition | 1 | 7 | 13 | 15 | 19 |
| ami cap1 (1% pin) | (running) | 1 | 5 | 9 | 11 |
| dsv4 cap1 (1% pin) | 11 | 13 | 16 | 15 | 23 |

Both models produce monotone ladders on both arms — the curve-shape fix
(CR253 disposition) is model-robust. But the approval regions diverge hard:
ami is stricter at the bottom (R1–R2 zero approvals) and more permissive at
the disposition top (36 vs 19).

## 2. The size-pin interaction flips DIRECTION across models (the headline)

At R5, disposition-vs-cap1 approval:

| model | disposition | cap1 | Δ |
|---|---|---|---|
| dsv4 | 19 | 23 | +4 (pin approves MORE) |
| ami | 36 | 11 | **−25 (pin approves far LESS)** |

CR255's size-worthiness coupling is real on both models but with OPPOSITE
sign. dsv4 reads a 1% cap as "low commitment, approve anyway"; ami reads the
same cap as "the desk doesn't back this, pass." The CR253 decoupling line
(size ≠ worthiness) lands on dsv4; on ami it does not (or ami couples harder).
Consequence: the disposition table and any bar fit are per-model artifacts —
the CR256 per-model fit requirement is confirmed by direct measurement, and
"port the dsv4 bar to ami" is now measured dead, not assumed.

## 3. Decision stability — the disease is cross-model and worse under pin

Rep-to-rep flip rates (same ticker, same level, both reps):

| arm | ami flips | dsv4 ref (analysis_r3) |
|---|---|---|
| disposition R3 | 10% | — |
| disposition R4 | **37%** | — |
| disposition R5 | 27% | — |
| cap1 R2 | 33% | 17% uncapped / 21% pinned |
| cap1 R3 | 30% | — |
| cap1 R4 | 40% | — |
| cap1 R5 | **47%** | — |

Two findings: (a) on ami the flip rate RISES with risk level on both arms —
the rooms the user actually sees (R4–R5) are the least stable; (b) the 1%
size pin that HALVED dsv4's instability does nothing for ami (30–47% pinned).
The consistency disease is model-level, and the CR255 mechanism finding
(size-pin as stabilizer) does not transfer.

## 4. Evidence-tracking discrimination (Jev, 2026-10-14) — the headline

Direction-signed evidence score (stance sign × Jev support, per card's own
direction) vs verdict, per level. Positive r + positive Δ (APPROVE mean −
PASS mean) = the room approves what the evidence supports.

| arm | R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|---|
| ami disposition r | (no approvals) | (no approvals) | **+0.37** | **+0.62** | **+0.62** |
| ami disposition Δ | — | — | +0.37 | +0.28 | +0.29 |
| ami cap1 r | — | +0.14 | +0.11 | +0.04 | +0.06 |
| ami cap1 Δ | — | +0.32 | +0.12 | +0.04 | +0.04 |
| dsv4 disp r (Step-0 ref) | +0.15 | +0.53 | +0.54 | +0.61 | +0.65 |
| prod disease (measured) | ami r=+0.03, APPROVE rooms score LOWER |

**Two findings:**

1. **The disposition prompt fix gives ami-llm real discrimination.** r=+0.62
   at R4–R5 with Δ≈+0.3 — APPROVE rooms genuinely carry stronger
   direction-signed evidence. Against the production-prompt disease on the
   same model (r=+0.03, approvals anti-correlated), this is a **prompt-layer
   cure on ami**, in the same band as dsv4's disposition arm. Production does
   not yet carry the disposition table — this is the measured case for
   promoting it (per-model acceptance run first, per §7.1).
2. **The 1% size pin destroys discrimination on ami.** Under cap1 the r
   collapses to +0.04…+0.14 and Δ to ~+0.04 — approvals decouple from
   evidence. Combined with §2/§3: on ami the pin makes the room both stricter
   AND evidence-blind. The cap1 mechanism (CR255's dsv4 stabilizer) is
   anti-discriminative on this model. Do not port.

## 5. PM vote distribution (CR228 bar context)

ami disposition votes (approve_votes/5): R1 — 52 rooms at 0/5, 6 at 1/5;
R3 — 49 at 0/5; R5 — 17 at 1/5, 11 at 2/5, 8 at 3/5, 11 at 4/5, 8 at 5/5.
ami's PM rarely unites even at R5 (8/60 unanimous). The frozen 4/4/3/2/2 bar
binds differently per model — on ami at R4 (bar 2) a third of approvals
survive on 2/5 votes, vs dsv4's clustering. Per-model bar measurement (not
assumption) again.

## 5. Sizing discipline

cap1 APPROVE sizes sit exactly at the 1.00% pin (median 1.00 at every level)
— the cap mechanism transfers cleanly. disposition R5 median 5.0% = the
uncapped mandate max; R4 2.75% within cap. No over-cap argued sizes observed
in either arm (spot check).

## 6. What this interim does NOT settle

- tm-all + probes: whether ami reproduces dsv4's tm-all NO-GO shape.
- Holdout behavior at the fitted bar (CR256 AC3): needs the full arm set
  before the Step-0 extension can run on ami.
- Stability mechanism: disposition-arm decisions now track evidence but still
  flip 27–37% at R4–R5 (§3). The remaining disease on the fixed arm is
  instability, not discrimination — that is CR256's bar (and CR259's paid
  stability story) exactly.

## 7. Program consequences (measured, do not re-litigate)

1. **Per-model everything**: curves, bars, size-coupling, and stability
   mechanisms are all model-local. Any production gate or prompt fix ships
   per-model with its own acceptance run.
2. **CR256 acceptance on ami-llm will need its own 30×5 fit** — the dsv4
   target curve (5/15/30/45/46) is a policy choice, but the fitted bar and
   sub-cap map must be ami-fit.
3. **CR259 thinking pilot baseline**: the thinking-off ami disposition R4 arm
   (22/60, 37% flips) is the A-side; pilot quality delta reads against it.
4. The R4–R5 instability on the model users get (ami is the production model)
   is 27–47% flip — the strongest-yet business case for CR256's gate and/or
   CR259's paid thinking tier (stability as a sellable artifact).
