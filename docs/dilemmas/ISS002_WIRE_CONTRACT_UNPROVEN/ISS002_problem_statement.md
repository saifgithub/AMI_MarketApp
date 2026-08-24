# ISS002 — a feature proven on the builder, never on the caller that must feed it

**Status:** open, contributors invited. **Convened:** 2026-08-24 (AT:R74), on Saiful's ruling
*"Convene it — you may spawn agents."*

**Why this is a Dilemma and not a defect.** `CLAUDE.md` sets the trigger: *third occurrence, or a
guard that failed twice, is a Dilemma, not another point fix.* This class occurred **three times
inside a single CR** (CR172, 2026-08-24), each time found by hand, each time after the covering
tests were green. The instinctive answer — "add another test" — is what was already done three
times. That is the condition the protocol describes as *the obvious fix is the one that already
failed.*

**This brief contains no proposed solution. That is deliberate and enforced.** Read the protocol's
"Why independent, blind attempts" section before you begin. Analysis of *what is broken* is shared;
ideas about *what to do* are not, including the convening agent's.

---

## The symptom, stated once

A component is built, tested and shipped. Its tests pass. It is never reached at runtime, because
the thing that must feed it does not — or feeds it something it does not read. **No test fails**,
because each side's tests construct their own inputs.

## The three instances, with evidence

### 1. `OptionProposalTicket` — shipped with exactly one referencing file: its own test

A response model, fully defined, fully tested. A repository-wide search for callers returned only
its test module. No service ever called the options API that would have produced it. It was live,
green, and unreachable.

### 2. DEF363 — the client read `greeks_reason`; the server sends `greeks_not_evaluated`

Two names for one fact, one on each side of the wire. What makes this the interesting instance:
**both covering tests supplied the wrong key themselves.** The Dart test built a fixture map
containing `greeks_reason` and asserted the model read it. The Python test asserted the server
emitted `greeks_not_evaluated`. Both passed. Both were correct about their own half. Nothing
compared the halves, so the disagreement had no place to surface.

### 3. DEF365 — a whole portfolio card rendered off a field the server did not have

`SimPortfolio.fromJson` read `options`, and `mobile/lib/widgets/sim/option_positions_section.dart`
rendered a complete UI section from it. `PortfolioSnapshot` — the response model the route actually
returns — had **no `options` field at all**. Coverage at the time: **4 backend tests** driving the
builder directly, **13 Flutter tests** building their own fixture maps. Seventeen tests, zero of
which consumed the other side's output. A user could consent to an option structure and then not
see it.

## What is common to all three

- Every one was written by someone testing carefully. None is a case of missing tests.
- The suite **cannot see across the wire**: Python tests assert on Python objects, Dart tests on
  Dart maps, and the contract between them has no home in either.
- Each was found by a human reading code, never by a check.
- The failure is silent in the direction that matters: the feature simply does not appear.

## What has already been tried, and its measured limits

`backend/tests/unit/test_wire_contract_parity.py` (shipped 2026-08-24) asserts that a **declared
pair** of one Dart class and one Pydantic model agree on key names. It provably catches both DEF363
and DEF365 when those pairs are declared.

**Its limit is the important part of this brief.** The first version of that test compared every
`j['…']` key under `mobile/lib/models/` against every Pydantic field in `app.api` + `app.schemas`
and reported **~250 orphans**, almost all false. The reason is structural: this codebase serialises
a great deal through **untyped `list[dict]`**. `PortfolioSnapshot.holdings` is literally
`list[dict]`, and its `mark` / `value` / `unrealised_pnl` / `stop` / `target` keys are dict
literals written inline in the route body. No schema-based check can see inside those. An allowlist
of 250 keys would be a rubber stamp.

So the shipped guard covers only surfaces whose response models are fully typed, and **growing it
requires a human to declare each pair** — which is the same manual act that failed three times.

## The inventory a solution has to cover

Any proposal must state how it handles each of these, because they are the actual shape of the
codebase, not edge cases:

1. Response fields typed as `list[dict]` / `dict` with keys written as literals in route bodies.
2. Dart models reading keys with fallbacks across several spellings (`j['run_id'] ?? j['id']`) —
   deliberately, because two lanes built from one plan in parallel.
3. Wire keys with `?? <default>` on the Dart side, where a missing key renders as a plausible value
   rather than an error.
4. Endpoints returning a bare `dict` built in the route function (`get_close_payload` returns
   `dict`; the whole games Close surface is this shape).
5. Fields that legitimately exist on only one side.
6. Newly added fields on either side, which is when the class actually strikes.

## Constraints a solution must satisfy

- **Solo maintainer.** One founder and Claude. Anything requiring a second reviewer, a schedule, or
  sustained human discipline has already failed here three times.
- **The stack is intentionally lean.** New dependencies must be justified, not assumed.
- **`CLAUDE.md`: prompt instructions are not controls.** *"Agents ignore even emphatic 'never
  present this as real' ~70% of the time. If it must hold, make it structural."* A convention, a
  checklist or a documented rule is not an answer to this brief.
- **`CLAUDE.md`: an entry without an enforcing check is not done.**
- **Degrade loudly.** A check that cannot evaluate must not pass silently — that property is itself
  one of the recurring classes here (DEF169, DEF190).
- Mac is a pure editor; the backend runs on `melehost`; tests run `backend/.venv/bin/python`.

## What "done" means

A mechanism that would have caught **all three** instances above **without a human declaring
anything per-surface**, that produces no false positives large enough to be ignored (the ~250-orphan
measurement is the bar), and that fails loudly when it cannot evaluate a surface rather than
passing it.

## Out of scope

Rewriting the app's serialisation strategy as an end in itself; anything requiring the two lanes to
stop working in parallel; anything that only works for surfaces already typed.

## Required output shape

Write `SOLUTION.md` in **your own folder only**. Cover, in this order:

1. **Your reading of the problem** — one paragraph. If you think the framing above is wrong, say so
   here; that is the most valuable thing you can contribute.
2. **The mechanism**, concretely enough to implement.
3. **How it handles each of the six inventory items.** Item by item. A proposal that covers only
   the interesting ones is not yet an answer.
4. **What it costs** — runtime, maintenance, dependencies, false-positive rate.
5. **How it fails** — what it cannot catch, and what happens when it cannot evaluate.
6. **What would have to be true for this to be the wrong choice.**

Prototypes, tests and measurements in your folder are welcome and count for a great deal. **Do not
read any other contributor's folder before submitting.**
