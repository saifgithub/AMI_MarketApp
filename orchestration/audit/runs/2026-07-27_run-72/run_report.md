<!--
Auditor run report — run-72 (2026-07-27, session auditor.core/track U). Round-2
audit of CR104-ROOM. Audited SHA a2201ce. Verdict COMPLETE, one MINOR.
Owner: AUDITOR.
-->

# run-72 (round 2) — CR104-ROOM delete the synthetic baseline → COMPLETE

- **Auditor session:** auditor.core (track U), 2026-07-27.
- Round 1 (`b1e4983`) was AWAITING_FIXES with two MAJOR — see run-69.

**Audited SHA:** `a2201ce` (round 1 was `b1e4983`). Scope vs round 1: **4 files, +243/−74** — the
Room path and its tests only, no drift. Isolated worktree `.claude/worktrees/audit-CR104-r2/`, own
venv. **Full suite 1373 passed** in 213s on a clean tree, run to completion before any mutation
(round 1 was 1368; +5 = round 2's new tests).

**Provenance is the weakest of the day and the lane says so.** Both round-2 workers died
backgrounding their verification run and emitting a final message (CR057 / P7) — the second *after
being explicitly instructed not to*. The Architect reviewed the uncommitted work, found it correct,
committed it unchanged, and authored every verification claim. Their instruction was "re-derive from
scratch." I did.

### Both MAJORs closed — my own round-1 probes, re-run verbatim

| Round-1 finding | My probe | Result |
|---|---|---|
| **MAJOR 1(A)** — allowlist over 13 field names | `profile["peg_ratio"]` / `profile["fcf_yield"]` from `rng` | **RED** |
| **MAJOR 1(B)** — one local variable launders into a protected field | `_v = rng.uniform(12.0, 55.0)` → `profile["pe"] = f"{_v:.1f}"` | **RED** |
| **MAJOR 2** — `(LIVE)` labels gated on presence | my `field_state={}` render, **widened** beyond round 1 to all 11 optional values | `(LIVE)` lines: **NONE**; values leaked: **NONE** |

The inversion is the polarity I recommended: deny-by-default over field names, with a fixed-point
taint closure over local assignments and exactly three narrative fields excluded. MAJOR 2 goes
further than the minimum — all five sites route through one `_field_is_live()` helper, and
`_valuation_line` gates each of its four parts independently, so a part with no recorded provenance
is dropped rather than riding under the shared label.

**Closed the gap the lane left open.** It disclosed that the `(LIVE)` sweep covered `room_prompts.py`
only. I swept `backend/app/` entirely: the one hit outside that file is `fundamentals.py:342`, on the
**1-on-1** surface (not the Room), and it is genuinely live-gated — the value comes straight from
`fetch_next_earnings` with no synthetic fallback feeding it. Nothing to carry forward.

### MINOR — the taint tracker misses four shapes, all reproduced

`_local_name_assignments` records only `ast.Assign` with a **single `ast.Name` target** and
`ast.AnnAssign`. Everything else is outside what taint propagates through. Each mutation below was
verified present in the source before running (a silently-failed injection would make "green"
meaningless), each reverted, tree clean after:

| Shape | Guard |
|---|---|
| **E1** — nested helper: `def _p(): return rng.uniform(...)` → `profile["pe"] = f"{_p():.1f}"` | **GREEN** |
| **E2** — tuple unpacking: `_a, _b = rng.uniform(...), 3` → `profile["pe"] = f"{_a:.1f}"` | **GREEN** |
| **E3** — augmented assignment: `_acc = 0.0; _acc += rng.uniform(...)` | **GREEN** |
| **E4** — read of the taint-excluded `profile` local: `_lp = profile["sentiment_score"]` | **GREEN** |

E2 and E3 are ordinary Python the tracker simply does not record; E1 crosses a function boundary a
local analysis cannot follow; E4 is contrived (it would put a narrative string into a numeric field).

**Why MINOR and not MAJOR — stated explicitly, since I scored round 1 MAJOR on the same file.** The
two things that made round 1 a MAJOR are both gone: the *literal original DEF123 shape* no longer
passes (1B is red), and new fields are no longer unprotected (1A is red). D4 asked for an invariant
rather than an allowlist over field names, and that is delivered. What remains is a **completeness
limit of local taint analysis**, not a hole in the polarity — and the shapes that evade are not how
someone reintroducing a fabricated number would naturally write it.

It is still worth closing, and cheaply: handle `ast.Assign` with a `Tuple` target and `ast.AugAssign`
in `_local_name_assignments`, and treat a nested `FunctionDef` whose body references `rng` as
tainted. That is roughly ten lines and closes E1–E3. I am not holding the lane for it.

### Unchanged and still open

- **The DEF123 corpus reading 0 remains an OPEN acceptance item**, agreed by all three of us. It
  needs the fix on Alpha plus a re-run filtered to post-promotion prompts; `main` is under a
  promotion hold, so it cannot close from a coder lane. **The CR is not fully closed until it reads
  0 post-promote** — that is a promotion-gated item, not a reason to bounce the code.
- Round 1's accepted work was not re-opened: the rng numeric baseline is still gone, D1's per-block
  flags still replaced, the fixture still test-only.
- FLAGS 1–3 stand, in particular that the mobile client has no "intentionally thin" rendering —
  bearing on `CR098-MOBILE-LIVE` / `CR098-MOBILE-VERDICT`, both still unbuilt. Same
  promotion-sequencing coupling I have now recorded on CR090-ROOM, CR098-ROOM and here.

### Not verified

- **Live behaviour on Alpha** — promotion hold; unit-level only, for all three of us.
- **The `llm_audit` corpus query** — runs on melehost, unreachable from a pure-editor Mac.

### Findings

1. **MINOR** — the taint tracker misses tuple unpacking, augmented assignment, a nested helper
   function, and a read of the taint-excluded `profile` local (all four reproduced, all GREEN). The
   deny-by-default polarity D4 required is delivered; this is a completeness limit, closable in
   ~10 lines.

### Verdict

**VERDICT: COMPLETE (round 2)** — zero BLOCKER, zero MAJOR.

Both round-1 MAJORs are closed and I re-derived every claim from scratch as instructed, using my own
probes rather than the lane's — which mattered, because this round had no worker hand-off behind it
at all. The renderer fix is better than what I asked for, and the one gap the lane flagged as
unswept turned out clean when I swept it.

