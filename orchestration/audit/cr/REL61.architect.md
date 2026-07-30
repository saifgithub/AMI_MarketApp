<!-- architect bridge — track R. CR052 / orchestration/audit/PROTOCOL.md. -->
# REL61 — CR101 bundle audit: does what the user SETS actually BIND, end to end?

ITEM: REL61
INSTANCE: architect (track R)
GATE: independent
SCOPE: release-bundle
BRANCH: `main`
SUBMITTED: round 1

---

# Round 1

## Why this exists, when all three lanes already passed

CR101-BE1, CR101-BE2 and CR101-MOBILE were each audited independently and each returned COMPLETE.
That is not sufficient here, and CR101's own history is the argument: **every serious defect in this
CR lived in the seam between two lanes, not inside one.**

- CR101-BE2 round 1 passed its own tests 1633/1633 with four mutations correctly RED, while three of
  its four limits were **silently unenforced in the Room**. Every test drove the floor directly with
  context populated; nothing exercised the caller. A lane cannot audit the call site it does not own.
- **DEF187**: one user has two single-name caps ~11x apart depending on which screen the trade came
  from. Neither the floor nor the Room is individually wrong.
- **DEF193**: `GET /v1/mandate/{id}` returns `null` for a cap that `GET /v1/portfolio/allocation`
  simultaneously reports as a real enforced number. Both endpoints pass their own tests.

Three instances of one shape — *one rule, N renderers* (`failure_patterns.md` P11 / DEF098) — inside
a single CR. That is the shape this audit is for. **This build ships to Saiful's phone**, and the
whole product claim of CR101 is that a number the user sets is the number that binds.

## The question to answer

For each of the **seven** settable fields, trace ONE value end to end and confirm the same number
appears at every layer:

`Settings UI → PATCH → MandateStore → safety floor (BOTH the trade-ticket path AND the Room path)
→ agent overlay text`

A field passes only if all five agree. Name any field where they do not, and say which layer is
wrong — not merely that they differ.

| Field | Units | Source lane |
|---|---|---|
| `sector_cap_pct` | percent | BE1 |
| `single_name_cap_pct` | percent | BE1 |
| `post_loss_cooldown_hours` | hours | BE2 |
| `max_open_positions` | count | BE2 |
| `max_trades_per_day` | count | BE2 |
| `max_trades_per_week` | count | BE2 |
| `max_open_risk_pct` | percent | BE2 |

## Specific things to attack

1. **The unset user is the majority case and the least tested one.** Every lane's tests set a value
   and watch it bind. Nobody traced the user who sets *nothing* — which is every existing user on
   deploy. For them BE1's two caps fall back to an enforced preset while BE2's five are genuinely
   off, and the UI renders those two states differently on purpose ("Following your risk profile"
   vs "OFF"). Is that distinction correct at every layer, and does the overlay narrate the preset
   the floor actually applies?

2. **Set one field, then check the OTHER six did not move.** `MandateStore.patch` became a recursive
   merge in BE1. A deep merge that drops or resurrects a sibling under a partial nested PATCH is
   exactly the DEF062 failure it was built to fix.

3. **The two paths, per limit.** BE2 round 2 wired `room_runner` and `enforce_safety_floor`. Confirm
   there is no *third* consumer that reads a mandate limit and was missed — the round-1 BLOCKER was
   two call sites, and the auditor found a third I had not named (`room_runner.py:2560`). The AST
   guard covers `check_mandate_compliance` callees only; it does **not** cover `enforce_safety_floor`
   call sites (recorded as BE2 auditor M4, now pinned by an assertion rather than by the guard).

4. **Overlay vs UI numeric agreement.** Both now interpolate per-user values. If the overlay says
   3.0% and the screen says 50% for the same user, the PM is reasoning from a different mandate than
   the one shown — the DEF187 shape arriving in the agent layer.

5. **`0` vs `null`.** `0` is a real value meaning "block everything"; `null` means off (BE2) or
   preset (BE1). Confirm no layer coerces one into the other — a `?? 0` or a falsy check anywhere in
   that chain silently converts "off" into "block everything" or vice versa.

## What I already know and do not need re-derived

- Suites: **backend 1645** (from 1589), **mobile 330** (from 309), both reproduced by me on merged
  `main` in clean trees. Do not spend the round re-running these; spend it on the seams.
- Merged: BE1 `8a056ba3`, BE2 `6717d065`, MOBILE `cf1de0ea`. Shipped as **`0.1.0+61`** to TestFlight
  and Play internal.
- Open and already minted — findings that restate these are not new: **DEF187**, **DEF191**,
  **DEF193**, **DEF194**.

## Disclosed by the builders, accepted by me, open to challenge

1. **BE1** kept `SINGLE_NAME_ABSOLUTE_CAP_PCT` as the floor's unset fallback instead of removing it
   as my assign instructed, because removing it measured as an ~11x silent tightening (43 RED).
2. **BE2** fixed UTC as the day/week boundary rather than the user's `timezone` field, and prices
   open risk per open trade row rather than per aggregated holding (`Holding` carries no stop).
3. **MOBILE** fires the retro-tightening breach check immediately *after* the save, not before,
   because no endpoint evaluates holdings against an unsaved candidate mandate.
4. **MOBILE** renders "Following your risk profile" rather than a number for the two preset-backed
   caps, because no endpoint exposes the resolved value (**DEF193**).

If any of these is wrong, say so with the measurement — three of my own rulings were already
overturned this way in this CR, and that was the cheap outcome each time.

## Not established

- **No device check.** Number-pad behaviour, `Wrap` layout at real widths, and AR/MS at real
  translated lengths are untested beyond a 390x2000 widget surface. AR/MS currently carry flagged EN
  placeholders.
- **No live-LLM read** of the new overlay lines — asserted at the string level, never run through a
  real vLLM completion to see whether the PM reasons from them sensibly.
- **Alpha IS promoted** — `alpha-2026-07-30-2` at `bcee4866`. I drafted the line above saying it
  was not, and writing it is what made me check: Alpha's live OpenAPI reported **all seven fields
  ABSENT** while `0.1.0+61` was already uploading. Worth recording as the near-miss it was, because
  the failure mode was silent rather than loud — the screen would have loaded, the user would have
  set a cooldown, the PATCH would have returned **200**, and the backend would have dropped every
  unknown key (`extra='ignore'`). A control that looks authoritative and writes nothing is
  **DEF129** exactly, the defect CR101 exists to abolish, reintroduced by deployment ORDER rather
  than by any code. Backend should have gone first; it went second. Now verified: all seven read
  **LIVE**, smoke green (`vllm`, `source=yfinance`), config-check clean with no mismatch (3 dark
  gates, all deliberately parked per DEF063).
- **Worth an auditor opinion:** nothing in the promotion protocol checks that a shipped client's API
  expectations exist on the backend it will talk to. `infra/PROMOTION_HOLD.md` covers the reverse
  direction (backend ready, client not yet on devices). This direction — client shipped, backend
  behind — has no gate, and `extra='ignore'` guarantees it fails silently rather than loudly. If you
  agree that is a real hole, say so and I will mint it.
