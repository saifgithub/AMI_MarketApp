# CR069 — decomposition record (Architect)

**Written:** 2026-07-23 · **Track:** `AT:architect` · **Against:** the R59 brief in
[`CR069_sharia_compliance_indicator.md`](CR069_sharia_compliance_indicator.md)

The protocol requires **all** chunks be written down before any is dispatched. That is the only way
to check the decomposition is complete, and it is what the CR-level audit diffs against the CR
document — a chunk nobody wrote down is a hole the terminal gate cannot catch. This is that record.

## Lanes

| Lane | Instance | `GATE:` | Depends on | State at write |
|---|---|---|---|---|
| `CR069-BE` | `coder.api` | **independent** | — | **dispatched, round 1** |
| `CR069-MOBILE` | `coder.mobile` | **independent** | CR069-BE (hard) | written, unassigned |
| `CR069-DIVERGE` | `coder.api` | spawned | CR069-BE | written, unassigned |
| `CR069-MY` | `coder.api` | **independent** | CR069-BE | **blocked — Saiful** |
| `CR069-VENDOR` | `coder.api` | spawned | CR069-BE | **blocked — Saiful (G5, G6)** |
| `CR069` | `architect` | **independent** | all dispatched chunks | terminal gate |

Only `CR069-BE` is assigned. `-MOBILE` and `-DIVERGE` wait on a real dependency; `-MY` and `-VENDOR`
wait on the stakeholder. All five unassigned lanes render `UNASSIGNED` on the board, which is
correct — the open action on each is the Architect's.

## Gate routing — the reasoning, since it is the point of the exercise

Routed on **reversibility, not size** (D-5).

- **`CR069-BE` → independent.** It changes what the safety floor enforces and what the product
  claims about a religious-observance screen. It is the fourth occurrence of the degrade-loudly
  class and sits on the exact path DEF084 got wrong. A backend bug is a redeploy away from fixed,
  which argues for `spawned`; the user-facing observance claim is what tips it. Ruled independent.
- **`CR069-MOBILE` → independent.** Ships to two app stores. A wrong string needs a new build and a
  review cycle, not a redeploy. This is DEF084-MOBILE's exact surface and exact category.
- **`CR069-DIVERGE` → spawned.** Log-only, no user-visible output, no input to any verdict. Its
  gate note carries a trip-wire: if the diff comes back touching `safety_floor.py` or a render path,
  the gate is void and it escalates.
- **`CR069-MY` → independent.** Same class as BE, second jurisdiction, different authority.
- **`CR069-VENDOR` → spawned.** No code, no user surface — `none` was tempting. But the deliverable
  *is* numbers a purchase decision rests on, and a fabricated number is precisely what a cheap
  worker produces. The gate checks the numbers were measured, not that code is correct.
- **`CR069` → independent, mandatory.** Per D-3 the CR-level audit exists whether or not chunks are
  audited. That is what makes `GATE: none` safe on any chunk: there is no path to a finished CR that
  skips the terminal gate.

**Load on the stakeholder's auditor: three independent audits** (BE, MOBILE, CR-level), sequenced by
dependency, so never more than one is in flight. The global audit cap is 3 `IN_AUDIT` per auditor.

## Two findings from reading the code that the brief does not have

**1. A fourth hardcoded copy of the demo universe.** `room_runner.py:1293` is a *literal duplicate*
of the 7-ticker set, not an import of `DEFAULT_HALAL_DEMO_UNIVERSE`:

```python
# Halal universe: tiny demo set. Real screen ships at W8+.
halal = halal_universe or {"AAPL", "MSFT", "NVDA", "GOOGL", "META", "TSLA", "AMZN"}
```

Swapping the constant leaves the Room path on the old set — the same flag enforcing two different
standards. The brief lists `sim_engine.py:80/:463/:624` and `api/mandate.py:274`; this is the fifth
site and the only one that would not have been found by following the constant.

**2. Three states need a source the brief does not name.** Constraint 2 requires *pass* / *screened
out* / *unknown*. SPUS publishes only the compliant set, so absence means "excluded" and "never
looked at" identically — distinguishing them needs **parent-index membership** (an S&P 500 ETF's
published holdings, same regulatory basis, no key). Without it the third state cannot be built
honestly, and a two-state screen that calls unknown tickers "screened out" is constraint 2 violated
in the direction nobody checks. The lane instructs `BLOCKED` over faking it.

## Deliberately not decomposed

- **Surfacing divergence to users** as the "standards differ" teaching moment. It is user-facing
  content, it would change `CR069-DIVERGE`'s gate, and lesson content is G7/SME territory. Log
  first; decide whether to teach from it later.
- **SHARIA lesson corrections (G7).** 8 of 10 lessons state 33% where AAOIFI is 30/30/5. SME-gated
  per CR060, also behind DEF082, and sequenced after Phase 1 behaviour locks or it documents a
  behaviour about to change again. **No agent lane may touch this.**
- **`sharia_screen()` activation.** Constraint 4 — the three-ratio math stays dormant until a source
  supplies real inputs. That is Phase 3 territory, not a chunk.

## Open, carried to the stakeholder

- **G3 — unknown-ticker behaviour.** Building to the CR's stated safe default, **block + disclose**.
  A ruling the other way is a one-line change, so no lane is stalled.
- **G4 — index-constituent licensing.** Lawyer question. Does not block building or internal
  testing; **does** block marketing or public launch. No agent resolves this.
- **G5/G6** — vendor account and quotes, which block `CR069-VENDOR` entirely.

## Defect found while decomposing

**DEF086** — `dispatch.sh` returned the `UNASSIGNED` state before reading the lane's `GATE:`, so all
five unassigned CR069 lanes printed a bare `-` regardless of the gate recorded in them. The one
state the record-upfront rule exists to create was the one state the board could not verify. Fixed
in the same commit; see
[`DEF086`](../../defect/DEF086_unassigned_lanes_hide_their_gate/DEF086_unassigned_lanes_hide_their_gate.md).
