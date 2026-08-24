# ISS002 — verdict

**Judged:** 2026-08-25 (AT:R74). **Contributors:** `opus5.0` (convening, wrote first and blind),
`sonnet5`, `haiku4.5`. All three answered the same brief without reading each other.

**Winner: `sonnet5`,** with one mandatory correction and one graft from `haiku4.5`.

---

## What each proposed, in one line

| Folder | Mechanism | Prototype |
|---|---|---|
| `sonnet5` | Auto-discover (endpoint → Dart class) pairs by parsing `api_client.dart`; capture real responses during the existing pytest run; diff Dart-read keys against observed bodies | **Yes, end to end, with measurements** |
| `opus5.0` | Capture real responses and replay them through the real parser; route→model binding read from the API client | No — design only |
| `haiku4.5` | Explicit JSON pair registry + doc-comment shape contracts for untyped dicts + unreachable-`fromJson` detection | Yes, a discovery scanner |

`opus5.0` and `sonnet5` converged independently on the same core insight — **make one side's real
output be the other side's test input** — which is itself a result: two contributors reaching it
blind is stronger evidence than either reaching it alone. `sonnet5` wins between them because it
solved the part `opus5.0` waved at. `opus5.0` said the route→model binding "is discovered rather
than declared… the app already maps route to model in `mobile/lib/services/`". `sonnet5` went and
found that `api_client.dart` is the **single file every wire call passes through** (verified during
judging: it is the only file under `mobile/lib/services/api/` that performs HTTP), parsed it, and
recovered **85 pairs with zero hand-declared**.

## The measurements that decided it

Both prototypes were re-checked during judging rather than taken on trust.

- `sonnet5`: **1,280 responses captured** across 5,176 tests; **44 PASS / 1 FAIL / 40 UNVERIFIED**.
- `haiku4.5`: naming-heuristic auto-pairing matches **3 of 129** Dart models — **2.3%**.

`haiku4.5`'s measurement is the more useful of the two, and it *argues against its own proposal's
premise as much as for it*: it proves that any name-based discovery is hopeless, which is precisely
why `sonnet5`'s choice to parse the call site instead of guessing names is the right one. Recorded
here because a losing idea that was right about something is half the value of asking.

## The correction the winner needs before implementation

**Its one reported FAIL is a false positive, and the failure mode is general.**

`SimSubmitResult` reads `j['order']`; across 21 observed `/v1/sim/submit` responses, `order` never
appeared. Verified by hand during judging: `backend/app/api/sim.py:726` **does** send `order` — on
the `resting: True` branch only, and none of the 21 captured submissions rested. The code is
correct on both sides.

So the winner's headline claim of *"1 real FAIL, zero false positives"* is wrong: it is **0 real
failures and 1 false positive.** The general defect is that **a branch-conditional key is
indistinguishable from a key the server never sends** — observation can only ever prove presence,
never absence. Left unfixed this is the ~250-orphan problem returning in a smaller, more
persuasive form, and a guard that cries wolf gets ignored, which is the exact end-state this
exercise exists to prevent.

**Required fix:** a key absent from all observations is reported only when the server-side source
shows no branch that emits it. Where that cannot be established, the finding is `UNVERIFIED`, not
`FAIL` — the same honest third state the proposal already uses well elsewhere.

## The graft from `haiku4.5`

**Layer 3 — unreachable-`fromJson` detection.** It is the only proposal that directly catches
instance 1 (`OptionProposalTicket`, shipped with its own test as the sole caller), and it catches it
by construction rather than as a side effect. `sonnet5`'s capture approach cannot: a model nothing
calls produces no observation, so it lands in `UNVERIFIED` alongside forty legitimately-untested
surfaces and is invisible. Take Layer 3 as-is.

## What was rejected, and why

**`haiku4.5`'s Layer 1 (explicit JSON registry) and Layer 2 (doc-comment shape contracts).**

Layer 1 is the shipped guard's declared-pairs model moved into JSON. It is honest about being
intentional friction, but the brief's definition of done was explicitly *"without a human declaring
anything per-surface"*, and manual declaration is the mechanism that already failed three times.
`sonnet5` demonstrated the bar is achievable, so conceding it is no longer necessary.

Layer 2 asks that every `list[dict]` field carry a doc comment naming its keys, and tests against
that comment. This fails `CLAUDE.md`'s own rule: *"Prompt instructions are not controls… If it must
hold, make it structural."* A doc comment is a promise a human keeps, checked against a client that
may be equally wrong — two descriptions again, not an observation. It also inverts the cost: the
untyped `list[dict]` fields are the surfaces capture handles **best**, because at the byte level the
opacity does not exist.

**`opus5.0`'s own proposal** loses to `sonnet5` on the point above and is recorded as a loss.

## What none of the three solved

Semantic disagreement — the right key carrying the wrong meaning or the wrong unit. All three say
so explicitly. Out of scope and stays out.

## Implementation

A normal CR, laned and audited, referencing `ISS002`:

1. `sonnet5`'s discovery + capture + compare, as prototyped.
2. The conditional-key correction above. **Non-negotiable** — without it the guard's first real
   output is a false alarm.
3. `haiku4.5`'s Layer 3 unreachable-`fromJson` scan.
4. `UNVERIFIED` is a hard failure in CI, never a silent pass (all three agree; it is also DEF169 and
   DEF190's rule).
5. Retrofit: `failure_patterns.md`'s P18 entry gets this as its enforcing check, and DEF357 /
   DEF363 / DEF365 point at the CR.

**The 40 UNVERIFIED surfaces are a finding in their own right** — 47% of discovered pairs have no
route-level test producing an observable response. That is a coverage number nobody had before this
exercise, and it should be filed separately rather than absorbed into the CR.
