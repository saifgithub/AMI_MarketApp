<!-- audit bridge — written by coder.mobile on hand-off. CR069-MOBILE. -->
# CR069-MOBILE — audit bridge

SUBMITTED: round 1

**Item:** CR069-MOBILE — Phase 1b UI copy + the four-state Sharia surface
**Instance:** coder.mobile
**Branch:** `lane/CR069-MOBILE.coder.mobile` @ `f21d7b8` (pushed)
**Acceptance:** `docs/forward_planning/CR069_sharia_compliance_indicator/CR069_sharia_compliance_indicator.md`
§Phase 1b, §Design constraints 1-2, §Acceptance 3
**DEPENDS-ON:** CR069-BE (`bdc410f`, merged) — **partially satisfied, see the blocker**

## SHAs

| SHA | Scope |
|---|---|
| `1bfb8fe` | `models/sharia.dart` (new), `models/sim.dart`, `l10n/app_{en,ar,ms}.arb` |
| `7c4d55e` | `widgets/sharia_verdict_banner.dart` (new), `screens/settings/settings_screen.dart`, `screens/sim/trade_ticket_sheet.dart`, `generated/l10n/*` |
| `f21d7b8` | `test/sharia_verdict_test.dart` (new) |

All inside `mobile/lib/**` + `mobile/test/**`. No backend path touched. No version/build bump.

## What changed and why

The DEF084 placeholder ("Curated demonstration universe … not a Sharia screen") was honest
when it shipped and is now false — the backend runs a real sourced AAOIFI screen. Replaced
with copy naming the standard, the source, that AMI reads a published list rather than
issuing a ruling, and the coverage boundary. Added the four-state verdict surface.

Two decisions worth the auditor's attention:

1. **`unknown` renders in neutral slate, not amber.** The trade is permitted (G3). Amber
   would re-introduce through colour the same "this was risky" reading the copy is
   written to avoid.
2. **`ShariaStatus.fromWire` returns null on an unrecognised value** instead of
   defaulting. The seam is hand-mirrored JSON; a `?? default` here converts backend enum
   drift into a confident wrong verdict, which is the failure class this CR exists to close.

## Tests + observed output

```
$ flutter test test/sharia_verdict_test.dart
00:00 +12: All tests passed!                      TEST_EXIT=0

$ flutter test
00:06 +60: All tests passed!                      FULL_TEST_EXIT=0

$ flutter analyze lib/
4 issues found. (ran in 4.1s)                     ANALYZE_EXIT=1
  info • 'copyWith' is deprecated …               lib/main.dart:69:22
  info • 'copyWith' is deprecated …               lib/main.dart:69:44
  info • Don't use 'BuildContext's across async gaps … lib/screens/floor/floor_screen.dart:73:7
  info • Don't use 'BuildContext's across async gaps … lib/screens/floor/floor_screen.dart:313:9
```

All 4 infos are pre-existing, in files this lane did not touch. Exit 1 is `analyze`'s
behaviour on infos, not a new finding.

The lane-mandated assertion — unknown renders the unknown copy and **not** the
screened-out copy — is `test/sharia_verdict_test.dart`, group *"unknown is not
screened-out"*. It asserts absence of `does not pass`, `won't trade it`,
`is in the S&P 500 but`, `blocked`, `rejected`.

## Contract re-verification — this is the finding

Ran **before** any edit, per the roster's contract boundary. Real JSON from
`https://api-alpha.agenticmarketintel.ai`, anon session, `compliance.halal=true`,
`POST /v1/sim/preview` + `/v1/sim/submit`, 2026-07-23.

**Result: the mobile half of the contract is not served.**

- `META` / `JPM` (screened_out) → the sentence arrives as English prose in `violations[]`.
  Renders correctly today.
- `AAPL` (pass) and `ASML` (unknown) → **byte-identical** permitted responses:
  `{"accepted": true, "compliance": {"passed": true, "violations": [], "blocked_by": null}, …}`

`ComplianceResult.sharia_verdict` exists (`backend/app/schemas/trade.py:91`) but the two
handlers hand-build a three-key dict and drop it — `backend/app/api/sim.py:186-190` and
`:230-234`. Confirmed against the deployed `openapi.json`: `ShariaVerdict` appears in **no
response schema across all 102 live paths**, and no Sharia/screen/universe endpoint exists.

**Therefore G3 does not render.** A permitted trade carries no field distinguishing a
screened PASS from an unscreened UNKNOWN, so the disclosure that G3 requires on a
successful trade has nothing to travel in. Verbatim fixtures are checked in as the last
three tests in `sharia_verdict_test.dart`; the final one asserts the payload shape that
lights the surface up the moment the backend emits it.

I did not infer the state from `passed: true`. That is a two-state answer to a four-state
question and would mark every unscreened ticker as screened-and-cleared — DEF084 again.

Fix is ~2 lines in `coder.api`'s owned path; the assign forbids me touching it.
**Q1 in the lane file asks whether a CR069-BE follow-up is filed or this lane widens.**

## Could not verify — named, not omitted

1. **`pass`, `unknown` and the localized `paused` banner have never rendered against the
   live backend.** Widget-tested only. Blocked on the above.
2. **The as-of date is absent from the Settings subtitle** — a knowing miss against
   design constraint 1. No client-side source exists for it; the alternatives were
   fabricating a date or falsely claiming the screen is paused. Rationale in the lane file.
3. **No device run.** No build bump per the assign.
4. **The paused state was never observed live** (`stale=False` throughout).
5. **`_visibleViolations` matches backend prose by ticker+standard** to avoid rendering the
   same fact twice in two languages. Tested against the live META sentence; will drift if
   that sentence is reworded. Fails toward duplication, never omission.

## Revert-proof QA

- Revert `1bfb8fe` → `settingsComplianceHalal` returns to "Curated demonstration universe",
  i.e. the false claim the stakeholder flagged. Nothing else regresses.
- Revert `7c4d55e` → the trade ticket loses the success-path banner entirely; the rejection
  path falls back to raw English `violations[]`, which is today's shipped behaviour.
- Revert `f21d7b8` → the constraint-2 guard disappears and unknown/screened-out copy can be
  merged by a later edit with nothing failing.
