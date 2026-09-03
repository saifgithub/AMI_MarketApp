# Rulings 2026-09-03 — the last three live rows

Saiful ruled R30, R38 and R43 in one message, verbatim:

> RC30. Ok.
> RC43. Mint it and fix it
> Rc38. Ok

These close the register's remaining live decisions. `DECISIONS_2026-09-02.md`
holds the six earlier forks; this file is the same kind of provenance record for
these three. Where a WP instruction or a reviewer doc disagrees, these win.

## R30 — does Acceptance #4 gate the merge?

**Ruled: trail it.** ~1–2 weeks of Alpha traffic, no fixed threshold, no revert
on a null result — a null is a new finding, not a failure. This was Fable's
proposal, unopposed by any reviewer, and had been *treated* as decided since
2026-09-02 without ever being ruled. Now it is. Register row R30 flipped.

## R43 — the PM's JSON-contract break

**Ruled: mint the DEF and fix it.** Minted as **DEF398**; the cheap leg landed in
the same commit (`886355e4`).

Two things worth carrying forward, because neither was in the draft:

1. **The mechanism is sharper than "trailing prose".** DEF352 already trims prose
   after a complete object, by cutting back to the last `}`. What defeats it is
   that the PM's appended section **quotes the contract it is breaking** —
   *"begin with `'{'` and end with `'}'`"* — so the quoted brace is what the trim
   lands on. The fix is `raw_decode`, which reads the first complete value from
   position 0 and cannot be confused by anything written after it.

2. **The fix is small against the measured harm, and the row says so.** Replayed
   against R47's n=5 corpus, it recovers **1 of XOM's 17 lost draws** (17% → 16%
   parse loss). The other 16 never opened a JSON object at all — the
   contract-abandonment class. So DEF398 stays **open**: the structural leg is
   CR210's `pm_verdict_schema()` grammar, gated on its acceptance-3 re-run.

   This matters for R47's conclusion. R47 found every n=5 flip is a parse-loss
   tie, and kept n=5 rather than raising it so as not to mask R43. The parser fix
   does **not** materially move that flip rate; only the grammar will.

## R38 — debt split, industrial vs. captive finance

**Ruled: acknowledged.** The design note (`R38_edgar_design_note.md`, `ecbbd4b7`)
opened with a gate — *design note first, acknowledged in the daily review, THEN
code*. Saiful acknowledged it directly rather than at the review, which is the
same authority in a different venue; the acknowledgment is recorded in the note
itself. EDGAR code is now WP06's to build, behind its config flag with
degrade-loudly failure.

The note's escape hatch still binds: if the dimensional-parser work balloons
beyond a contained change to `parse_companyfacts` plus a small entity registry,
stop and report back — reversing to a declared-absent entry with its own CR is
Saiful's call, not a worker's.

R38's box stays `☐`: the gate is lifted, the code is not written.

## Register state after these

**54/61 ☑.** One live row open (R38, unblocked and awaiting its build) plus the
six parked rows (R53, R55, R57–R60), which are excluded from CR219's completion
target by design — see `PARKING_LOT.md`.

---

# Ruling 2026-09-03 (later the same day) — "Build all"

Asked whether to build R38 or park it and close CR219, Saiful ruled, verbatim:

> Build all

**Scope of the ruling:** every unbuilt register row — R38 AND the six parked
rows (R53, R55, R57, R58, R59, R60). All seven now build inside CR219.
`PARKING_LOT.md` is superseded (header updated; table kept as history). CR219's
completion target is back to 61/61.

Dispatcher scoping calls made under this ruling (each recorded in its WP;
Saiful can override any of them):

- **R55** — the 2026-09-02 "own future CR" half is superseded (rides CR219, the
  one-CR precedent); the **internal-only half stands** (no user-facing
  calibration stats before v1.0). WP11.
- **R57** — "Build all" is not read as amending two pinned design decisions
  (CR210's no-prose-agent-constrained wiring pin; DEF251's
  measurement-channel-never-control comment). What builds is the measurement
  leg the row's own wake-up condition demanded: per-turn emission telemetry +
  per-agent rates + a written revisit rule. Grammar-forcing the envelope stays
  gated on that data and on Saiful amending the pins explicitly. WP14.
- **R58** — the code mechanism ships default-OFF; the harness measurement
  decides the recommendation; flipping the default is Saiful's. WP13.
- **R59** — two phases: read-only inventory first (WP12), fixes + the
  provenance guard dispatched after dispatcher review.
- **R60** — backend-only surface now (PM prompt injection + API field); mobile
  rendering + i18n flagged as follow-up. WP15.
- **R38** — the design note's open flag-OFF framing question is ruled: flag off
  ⇒ no `field_state` key at all. No migration in WP10 (WP11 owns this wave's
  only alembic head). WP10.

**Wave order (P33 single-writer lanes):** Wave 1 = WP10 + WP11 (hook held
back) + WP12 + WP13 in parallel; wave 2 = WP14 + WP11's runner hook after
"WP13 accepted"; wave 3 = WP15 after "WP14 accepted". `room_runner.py` has
exactly one writer per wave.
