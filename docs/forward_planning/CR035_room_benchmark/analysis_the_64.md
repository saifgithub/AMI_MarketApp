# CR035 — the 64 differences, and what arm B says about them

Written 2026-07-19 (AT:R59), after arm A (`baseline150-2026-07-17`, 150/150) and
arm B (`ablconsensus150-2026-07-18`, 150/150). Arm C still running.

The single biggest cell in the baseline confusion matrix is **Street Buy / Room PASS = 64**.
Disagreement with the Street is almost entirely one-directional (the opposite cell,
Room Buy / Street Hold, is 7), so this cell *is* the Room's character. This document asks
what those 64 refusals actually are.

---

## 1. Five of the 64 are not judgements — they are a defect (DEF067)

**ADI, DHR, META, NIO, VZ.** In each, the Portfolio Manager emitted well-formed JSON with
`"action": "MODIFY-AND-APPROVE"` — an affirmative decision, outside the two-value enum. The
DEF058 reformatter, prompted to convert a verdict *"written in prose"*, did not map it to
APPROVE. It wrote a complaint, and the complaint parsed cleanly as PASS. The user's verdict text
for VZ reads, verbatim:

> The requested action 'MODIFY-AND-APPROVE' is an invalid enum value for this strict schema,
> which permits only 'APPROVE' or 'PASS'. Consequently, no valid action…

Every instance is a **lost APPROVE**. These are invisible to the existing guard:
`overridden_from_llm` stays `False` and the reason lacks the `machine-readable` sentinel, so
`room_benchmark_report.is_pm_parse_fallback()` does not exclude them and they scored as genuine
conservatism.

Arm B shows the same failure on 8 different names (GIS, QRVO, ABT, PG, PLTR, PM, DAL, EXPE), so
this is a stable ~4–5% tax, not an arm-A artefact.

**Consequence for the headline number:** true DEF058-class loss in arm A is **9/150 (6.0%)**,
not the 2.7% the report states. DEF058 is not closed. Filed as **DEF067**.

Corrected, the cell is **59 genuine refusals**, and every metric below is quoted on the raw 64
only where the report already is — the corrected agreement rate is a point or two higher.

---

## 2. Sixteen of the 64 refuse on arithmetic that is wrong by ~20x (DEF066)

The largest identifiable reason cluster is not valuation or momentum. It is a **unit error in the
risk check**: the Room measures a single position's stop-loss *distance* against the **portfolio**
max-drawdown cap, ignoring position size.

AMD is the cleanest instance:

> The proposed 5% size is rejected; a 19% drawdown to the $407 stop **consumes 63% of the user's
> total 30% max drawdown allowance**, violating the mandate's risk profile.

At the 5% size the Trader proposed, a 19% adverse move costs **0.95% of the portfolio** — 3.2% of
the 30% cap, not 63%. The stated figure overstates the risk by a factor of ~20.

Same error, same shape: BKNG (20.3% stop → "67% of the cap"), NEE (22.5% → "75%"), SCHW ("~27% of
the 30% cap"), plus CVX, EQIX, HUT, MU, PLD, PLTR, RIOT, ROKU and four others — **16 of 64**.

**Mechanism.** `room_prompts.py:153` emits the mandate line bare:

```
- max_drawdown_pct: 30
```

Nothing states what it is a percentage *of*, and nothing says position size scales a stop's
contribution to it. Agents default to reading it as a per-trade stop-distance budget. The effect
is that **any name with a wide technical stop becomes un-buyable regardless of sizing** — which
selects against exactly the volatile growth names the Street rates Buy.

This is not the safety floor working as designed. The floor is a portfolio constraint; the Room is
enforcing it as a position constraint. Filed as **DEF066**. The fix has to be structural — compute
the position-level drawdown contribution and hand the agents the *derived* number — not another
prompt sentence (failure_patterns P2, lesson 1: prompt instruction is not a control).

---

## 3. The remaining ~43 are defensible, and mostly about timing

Classified on the primary stated driver, after removing the two defect classes:

| Driver | n | Character |
|---|---|---|
| No technical trigger — breakout unconfirmed, volume below 20-day, limit order not filled | 14 | "Right name, not yet." Not a disagreement about the thesis at all |
| Horizon mismatch vs mandate | 6 | PM refuses a 12-month trade against a 3–10 year mandate. Correct behaviour, arguably over-literal |
| Concentration / size cap | 3 | Safety floor, working |
| Valuation / insufficient upside to consensus target | ~14 | Genuine analytic disagreement with the Street |
| Balance-sheet / FCF risk | ~6 | Genuine, and the Street is arguably the one being loose (CLSK, MARA, RIOT, HUT) |

The 14 "no trigger yet" refusals deserve their own note: these are **not** Hold opinions. The Room
says buy-above-$X and $X has not printed. Against a static Street rating, a conditional entry
scores as disagreement even when the thesis matches exactly. Any future scoring pass should count
these separately — treating them as Hold understates agreement.

---

## 4. Arm B: the consensus line is doing most of the selecting

Arm B suppressed the analyst-consensus line fed to the Fundamentals agent
(`SUPPRESS_ANALYST_CONSENSUS=true`). This was the circularity check.

| | Arm A (consensus visible) | Arm B (suppressed) |
|---|---|---|
| Agreement vs Street | 73/146 (50%) | 61/150 (41%) |
| APPROVE rate | 36/150 (24%) | 29/150 (19%) |
| Verdict flips A→B | — | **51/146 (35%)** |

35% flips against a ~12% same-config noise floor: the consensus line materially moves verdicts.

**The rate is not the finding — the overlap is.** Of arm A's 36 APPROVEs, only **7** are also
APPROVEs in arm B. If the two arms picked their buys independently, the expected overlap would be
36 × 29 / 146 = **7.15**. Observed: **7**. Hypergeometric P(X ≥ 7) = 0.61, P(X ≤ 7) = 0.58 —
independence cannot be rejected on any margin.

> **Removing the analyst-consensus line makes the Room's choice of *which* names to buy
> statistically indistinguishable from an independent redraw.**

The approve *rate* barely moves (McNemar χ² = 0.71, p ≈ 0.44 — 29 flips down vs 22 up). So the Room
has a stable disposition about *how often* to buy and essentially no stable, self-generated view
about *what* to buy. Its baseline 50% agreement with the Street is, on this evidence, substantially
the Street's own line being read back.

Of the 64 differences specifically, 15 became APPROVE in arm B and 49 stayed PASS — i.e. the
refusals are somewhat stickier than the approvals, which fits §2 and §3: the drawdown-arithmetic
and no-trigger refusals do not depend on the consensus line.

---

## 5. What this means

1. **DEF067 first** — it is a pure loss of correct decisions, cheap to fix, and it is currently
   corrupting the benchmark's own numbers.
2. **DEF066 next** — the largest single identifiable cause of the Room's over-conservatism, and it
   is an arithmetic error, not a stance. Fixing it should be measurable as a rise in the approve
   rate without touching any agent's opinion.
3. **The anchoring result is the one to sit with.** Re-running arm B after DEF066/DEF067 land is
   the honest test of whether the Room has a view of its own. Right now the defensible reading is:
   it has a temperament, not a thesis.
4. Red-line remains clean (**0/2**) and target sanity is tight (**−0.7%** over 36 approvals) —
   the safety-critical behaviours are not implicated in any of the above.
