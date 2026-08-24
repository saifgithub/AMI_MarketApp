# ISS002 — opus5.0

*Written before any other contributor was invited (protocol step 4), so it cannot be anchored by
theirs, and so the brief is proven usable by someone reading it rather than the one who wrote it.*

## 1. My reading of the problem

The brief frames this as "the suite cannot see across the wire." I think that is right but one step
short of the actual defect. The deeper fact is that **every test in this repository asserts against
an input it authored itself.** A Python test builds a Python object and checks the builder; a Dart
test builds a map and checks the parser. Both are testing a function against its own imagination.
The wire is not an unlucky blind spot — it is the only place where one side's *output* is the other
side's *input*, and it is therefore the only place this style of testing structurally cannot reach.

That reframing matters because it says what a solution must do: **make one side's real output be
the other side's test input.** Anything that instead compares two *descriptions* of the contract
(schemas, declared pairs, type stubs, a shared IDL) is still two imaginations, and will drift the
same way — it just moves the drift somewhere harder to see. The shipped `test_wire_contract_parity`
is exactly this shape, which is why it can only cover what someone remembered to declare.

## 2. The mechanism — capture the real response, replay it through the real parser

Two halves, neither of which requires anyone to declare a surface.

**Half A — capture.** An autouse pytest fixture wraps the FastAPI `TestClient` used by the existing
route-level tests. Every 2xx JSON response is written to a corpus at
`backend/tests/_wire_corpus/<method>_<route-template>/<hash>.json`, alongside the route template,
the status, and the test that produced it. Captured, not authored: it is the bytes the route
actually emitted. Writing is keyed on content hash, so the corpus is stable across runs and
reviewable in a diff. This is ~40 lines and no new dependency.

**Half B — replay.** A Dart test loads the corpus (it is in the repo; Flutter tests read files) and,
for each captured payload, runs the model `fromJson` that the app actually uses for that route.
Then two assertions, in both directions:

- **Every key the parser reads must be present in the captured payload.** This is DEF363 and DEF365.
  Reading requires instrumenting `fromJson` — see §3.2 for how, without touching the models.
- **Every key the payload carries must be read by someone**, or appear in an explicit waiver file
  with a reason. This is the direction that catches a *server* field the client silently ignores,
  which is the same class arriving from the other end.

The route→model binding is the one thing that must be known, and it is discovered rather than
declared: the app already maps route to model in its API client (`mobile/lib/services/`), and that
mapping is read by the test. If a route is captured and no client calls it, that is itself the
`OptionProposalTicket` finding, reported as such.

## 3. The six inventory items, one at a time

**3.1 `list[dict]` / `dict` with literal keys in route bodies.** Handled, and this is the item that
motivates the whole approach. Capture is of emitted JSON, so `PortfolioSnapshot.holdings` arrives as
a concrete list of concrete objects with `mark` / `value` / `unrealised_pnl` present. The opacity
that defeats a schema-based check does not exist at the byte level. **This is the reason to prefer
capture over any schema comparison.**

**3.2 Dart fallback spellings (`j['run_id'] ?? j['id']`).** Handled, and improved. Instrument by
parsing the model source for `j['…']` occurrences grouped by `??` chain, then check that **at least
one** spelling in each chain appears in the captured payloads — a chain where *none* appears is
DEF363. A chain where a *later* alternative is the only one ever present is reported as a soft
finding: the fallback is load-bearing and the plan-doc name is fiction. Neither is guessable from
schemas.

**3.3 `?? <default>` masking absence.** Handled by the same read-side assertion, and this is where
capture earns its keep: a key that is absent from **every** captured payload for that route is
reported regardless of whether a default made it render plausibly. The default is exactly what hides
this today.

**3.4 Bare `dict` route functions (`get_close_payload`, the whole games Close surface).** Handled
with no special case — the capture happens at the HTTP boundary, so a route with no response model
is captured identically to one with a fully typed model. The games Close is the largest surface in
this shape and gets covered by default.

**3.5 Fields legitimately on one side only.** The waiver file, with a reason string per entry.
Crucially it is a waiver over **observed** keys, so it is bounded by what actually ships — not the
~250-entry allowlist the brief measures as a rubber stamp. My estimate is tens, not hundreds; I have
not measured it and say so.

**3.6 A newly added field on either side.** This is the case that matters and the one capture is
weakest on, honestly: a new Dart key fails immediately (no captured payload contains it), but a new
*server* key is only caught once a test exercises that route. See §5.

## 4. Costs

- **Runtime:** capture is a dict write per response in tests that already run; negligible. Replay is
  one Flutter test iterating a few hundred JSON files — seconds.
- **Repo size:** the corpus. Content-hashed and deduplicated; a few hundred KB. It is also the
  single most useful artefact for a future reader trying to learn what a route returns.
- **Maintenance:** the corpus changes when responses change, which shows up as a reviewable diff.
  That is a feature — a silent contract change becomes a visible one — but it is real churn.
- **Dependencies:** none.
- **False positives:** the waiver file absorbs the legitimate one-sided fields; after that a failure
  should mean a real disagreement. Unmeasured, and that is the main thing I would want to test
  before believing this.

## 5. How it fails

**The honest weakness: coverage is only as good as the route-level tests.** A route no test
exercises produces no captured payload, and a surface with no payload cannot be checked. This must
**fail loudly, not pass** — the replay test enumerates the app's route→model map and reports every
route with zero captures as *uncovered*, in the same report as the mismatches. A silently-uncovered
surface would reproduce exactly the class this exercise exists to close (and would repeat DEF169 /
DEF190: an unevaluable check that does not say so).

It also cannot catch semantic disagreement — the right key carrying the wrong meaning, or the right
number in the wrong unit. Nothing here addresses that, and I would not claim otherwise.

## 6. What would make this the wrong choice

- **If route-level test coverage is much thinner than I believe.** I have not measured how many
  routes are exercised through `TestClient` versus tested at the service layer. If most are
  service-level, the corpus is sparse and this degrades to a loud report of "uncovered" that nobody
  can act on quickly — in which case the honest answer is that typing the response models is the
  prerequisite, and this is premature.
- **If the corpus churn is intolerable in review.** A solo maintainer seeing a large JSON diff on
  every response change may start rubber-stamping it, which recreates the failure at a new site.
- **If a contributor finds a way to make the two sides share one artefact rather than compare two.**
  Generating the Dart models from the Python schemas would make whole categories of this
  unrepresentable rather than merely detectable, which is strictly stronger than any checking
  approach — including this one. I did not propose it because the `list[dict]` inventory item looks
  fatal to it, but I hold that loosely and would want it argued.
