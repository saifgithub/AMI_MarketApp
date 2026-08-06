# CR140 — Portfolio Health evaluation cadence

**Status:** proposed · **Raised:** 2026-08-06 (AT:R66) · **Origin:** found while fixing
DEF219 · **Relates to:** CR136 (the feature), DEF219 (the trial half, fixed), CR137
(reserved — Portfolio Room / CR136 Phase B)

---

## What

Implement a **cadence** for Portfolio Health Findings. Saiful's stated cadence for
portfolio-level evaluation is **monthly**; there is no cadence in the code at all.

## Why — the gap, measured

While fixing DEF219 I grepped `app/services/health_gate.py` and
`app/services/portfolio_health_constants.py` for any monthly or cadence concept. There is
none. What the gate actually limits is:

| Limit | Where | What it bounds |
|---|---|---|
| Trial budget | `trial_active = used < budget` | total Findings in the trial (3 after DEF219) |
| Daily cap | `daily_used >= daily_cap` | 2/day — **unreachable** for a single-portfolio user |
| Same-day dedupe | `dedupe_key = <portfolio_id>:<date>` | 1 Finding per portfolio per day |

The binding limit for an **entitled** user (Trader / Floor Manager) is therefore the
same-day dedupe: **one Finding per day, forever.** That is 30× the stated cadence.

Saiful's own words on why it should be monthly (2026-08-05): portfolio-level evaluation
*"should be done only 1's a month. This level of assesment is too expensive to run on a
daily basis."*

**The cost premise, measured rather than assumed** (this was owed and unmeasured when the
cadence call was made — recorded in DEF219): the one real Finding on live Alpha cost
**4,322 prompt / 257 completion tokens, 6,539 ms**, tier `mid`, provider `vllm`. On the
on-prem box that is **~6.5 s of GPU occupancy per portfolio, not a per-token bill** — so
"expensive" here is queue and throughput, not spend. `n=1`, one reading, not an average.

That does not overturn the monthly call. It does mean the cadence should be chosen against
a real number, and it changes what "expensive" is protecting: **GPU queue contention with
the 12-agent Room**, not money. A hundred users pulling daily is ~11 minutes of serialised
GPU per day — which is survivable today and is not the point. The point is that the
product's own claim is *"re-read your book monthly and watch what changed"*, and shipping
a surface that answers daily teaches the opposite habit.

## Scope

**In:**

1. A cadence limit for entitled users — the shape is the first decision (see below).
2. It must be **config-driven** and forwarded in `docker-compose.yml`'s `api-alpha` block,
   or `test_config_compose_parity.py` fails the build (CR040 / P1 — DEF038 and DEF063 are
   both instances of exactly this being skipped).
3. A refusal that **says when**, not just no. A 429 whose body carries the next eligible
   date, so the client can render "your next reading is due 12 March" rather than an error.
4. Tests pinning the cadence itself, and pinning that the trial is **not** subject to it
   (DEF219 exists because a clock and a budget were conflated once already).

**Out:**

- Pricing / credit metering — that is DEF205, Saiful's call, and it is a different lever.
- The Portfolio Room (CR137) and the re-annualisation half (CR139).
- Any change to the *tiles*, which are free in every mode and stay that way.

## The decision this CR carries

Three shapes, and the choice is a product call before it is a code one:

| Shape | Behaviour | Cost |
|---|---|---|
| **(a) Calendar month** | one Finding per calendar month, resets on the 1st | simplest; a user who joins on the 28th gets two readings in four days |
| **(b) Rolling 30 days** | next Finding 30 days after the last | no boundary gaming, but "when do I get my next one" needs the API to say so — see scope 3 |
| **(c) On material change** | evaluate when the book actually moves (new position, weight drift > X, drawdown breach), with a floor between readings | best product answer — the reading arrives when it means something — but it needs a definition of "material", which is its own argument |

**Recommendation: (b) rolling 30 days**, with (c) noted as the better long-run answer once
there is enough real usage to define "material" against. (b) is the smallest change that
matches the stated intent, has no boundary artefact, and its one weakness — the user
cannot see when they are next eligible — is already in scope as item 3.

## Acceptance

1. An entitled user who has generated a Finding cannot generate another until the
   configured cadence has elapsed; the refusal carries the next eligible date.
2. A **trial** user is bounded by budget only, not by cadence — DEF219's fix survives.
3. The cadence setting is forwarded in `docker-compose.yml` and
   `test_config_compose_parity.py` passes.
4. Setting the cadence to zero/disabled restores today's behaviour exactly, so the change
   is revertible by config rather than by a rollback.
5. A test that the tiles remain ungated in every mode and at every cadence state.

## Open questions for Saiful

- Which shape — (a), (b) or (c)?
- Does **Floor Manager** get a different cadence from **Trader**, or is cadence orthogonal
  to plan? (Today `portfolio_health_plans` gates *access*; cadence would be a second axis.)
- Should a user be able to **buy** an off-cadence reading with credits? That couples this
  to DEF205 and is worth deciding together rather than twice.
