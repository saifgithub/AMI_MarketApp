# analysis_r7_parity — ami-llm × arm parity vs dsv4 (INTERIM 1)

**Status: INTERIM.** Covers disposition 30×5 (complete) + cap1 30×5 (R2–R5
complete, R1 in flight). tm-all 30×5 and the 7 probe arms are still running on
melehost (`/tmp/ami_parity_v2.sh`); Jev evidence-scoring for these arms is
pending (fund 402). Verdict-layer read only — no Jev r in this interim.

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

## 4. PM vote distribution (CR228 bar context)

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

- Evidence-tracking r (Jev) for these arms — fund 402; the discrimination
  question (does ami track evidence better or worse than dsv4?) stays open.
- tm-all + probes: whether ami reproduces dsv4's tm-all NO-GO shape.
- Holdout behavior at the fitted bar (CR256 AC3): needs the full arm set +
  Jev scores before the Step-0 extension can run on ami.

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
