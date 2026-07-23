<!-- coder lane file — coder.mobile-owned. CR069-MOBILE. -->
# CR069-MOBILE — coder.mobile

STATUS: READY_FOR_AUDIT (round 1)

Branch `lane/CR069-MOBILE.coder.mobile` @ `f21d7b8`, pushed. Three commits:

| SHA | What |
|---|---|
| `1bfb8fe` | Phase 1b strings + the `ShariaVerdict` wire mirror |
| `7c4d55e` | Four-state rendering; unknown rides a successful trade |
| `f21d7b8` | The constraint-2 guard (12 tests) |

`flutter analyze lib/` → exit 1, **4 infos, all pre-existing** (`main.dart:69` ×2
deprecated `copyWith`, `floor_screen.dart:73,313` `use_build_context_synchronously`).
None in a file this lane touched; no new findings.
`flutter test` → **60 passed, exit 0**.

---

## The contract check found a blocker. Read this before the diff.

Per the roster's contract boundary I re-verified `fromJson` against **real backend JSON**
before editing anything. Anonymous session on `https://api-alpha.agenticmarketintel.ai`,
`PATCH /v1/mandate/{id}` with `compliance.halal=true`, then `POST /v1/sim/preview` and
`POST /v1/sim/submit` for the four tickers the assign named. Captured 2026-07-23.

**The screened-out state works. The other three cannot be rendered, because the field
they need is not on the wire.**

### What actually comes back

`META` and `JPM` — screened out, blocked. The message arrives, but only as English prose
inside `violations[]`:

```json
{"accepted": false,
 "compliance": {"passed": false,
   "violations": ["META is in the parent index but does not pass the AAOIFI screen (S&P 500 Sharia Industry Exclusions Index (via SPUS), as of 2026-07-23), so this mandate won't trade it."],
   "blocked_by": "compliance"},
 "fill_price": 627.1699829101562, "notional": 627.1699829101562,
 "cash_available": 10000.0, "held_quantity": 0.0, "price_source": "yfinance"}
```

`AAPL` (in the compliant set → **pass**) and `ASML` (outside the parent index →
**unknown**) return **byte-identical** bodies apart from price:

```json
{"accepted": true,
 "compliance": {"passed": true, "violations": [], "blocked_by": null},
 "fill_price": 325.8900146484375, "notional": 325.8900146484375,
 "cash_available": 10000.0, "held_quantity": 0.0, "price_source": "yfinance"}
```

### Why

`ComplianceResult` already defines the field — `sharia_verdict: ShariaVerdict | None`
at `backend/app/schemas/trade.py:91`, with the comment saying it is present on a
permitted trade precisely so the disclosure travels. But `/v1/sim/preview` and
`/v1/sim/submit` don't return the model. They hand-build a three-key dict:

- `backend/app/api/sim.py:186-190` (preview)
- `backend/app/api/sim.py:230-234` (submit)

```python
"compliance": {
    "passed": pv.compliance.passed,
    "violations": pv.compliance.violations,
    "blocked_by": pv.compliance.blocked_by,
},
```

`sharia_verdict` is dropped at the serialization boundary. Confirmed against the deployed
`openapi.json`: across **all 102 live paths**, `ShariaVerdict` appears in **no response
schema**, and there is no Sharia/screen/universe endpoint of any kind.

### The consequence, stated plainly

**G3 cannot be satisfied by this lane alone.** The assign is explicit that unknown is
permitted so its copy has to land on a successful trade. On the wire today a successful
trade carries no way to tell a screened PASS from an unscreened UNKNOWN, so the app has
nothing to branch on. The permitted-unknown disclosure — the specific thing G3 exists to
guarantee — **does not render against the live backend.**

This is the DEF089 shape pointing at the mobile half: the lane was unblocked on evidence
that verified the backend's *internal* resolver (`compliant=216 parent=503 as_of=2026-07-23`,
read inside the container) without checking whether the verdict reaches a client. It does not.

### What I built anyway, and why that is not shipping dark code

Everything except the wire itself. `models/sharia.dart` mirrors the backend enum and
model exactly; `SimSubmitResult` reads `compliance.sharia_verdict` on **both** branches;
`ShariaVerdictBanner` renders all four states from the ARB. The mobile half is complete
and tested — the last test in `sharia_verdict_test.dart` asserts the exact payload shape
that lights it up, and it passes today against a hand-built body.

What I did **not** do is fake it. No inferring "pass" from `passed: true` — that is the
DEF084 error exactly, a two-state answer to a four-state question, and it would silently
label every unscreened ticker as screened-and-cleared. `ShariaStatus.fromWire` returns
`null` on anything unrecognised for the same reason: drift surfaces as an empty surface,
never a confident wrong one.

### Q1 — for the Architect

The fix is ~2 lines in `backend/app/api/sim.py`, adding `sharia_verdict` to the two dicts
(`pv.compliance.sharia_verdict.model_dump(mode="json") if … else None`). It is
`coder.api`'s owned path and the assign forbids me touching backend paths, so I have not.

**Does a CR069-BE follow-up lane get filed to serialize the field, or should this lane's
scope be widened?** Until one of those happens, CR069 §Acceptance 3's "a ticker outside the
parent index returns unknown, not a rejection" holds in the backend's own logic but is
**invisible to the user**, which is the half the stakeholder was looking at.

---

## What this lane delivers as-is

The visible half the assign called out — the false Settings copy — is **fixed and works
with no backend change**, since none of it is per-ticker.

| Surface | State |
|---|---|
| Settings toggle label | ✅ `Sharia screen — AAOIFI` |
| Settings subtitle | ✅ `AAOIFI standard, S&P 500 Sharia index` |
| Settings explanation sheet | ✅ standard + source + AMI-reads-not-rules + coverage boundary |
| Trade rejection (screened-out) | ✅ renders live today |
| Trade success (pass) | ⛔ blocked — no field on the wire |
| Trade success (unknown) | ⛔ blocked — no field on the wire (**this is G3**) |
| Paused / unavailable | ⚠️ partial — blocking, so it lands in `violations[]` as prose; the localized banner needs the field |

### The as-of date in Settings — a deliberate, documented omission

The assign says I may not drop the standard, source, as-of date or coverage boundary. The
Settings strings carry three of the four. **The as-of date is not there**, because the app
has no source for it: no endpoint serves the screen's status, and the only place a date
appears is inside a per-ticker verdict, which is exactly what is missing from the wire.

The two alternatives were both worse. Rendering a fabricated or client-side date is DEF084
with a fresh coat. Rendering the *paused* copy because no date resolved would tell every
user the screen is down while it is healthily serving 216 names — false in a new direction.
So the date is stated on each per-ticker verdict (where the backend does stamp it, and
where it is live today on the rejection path) and the `@`-note in the ARB records why the
subtitle omits it. **Flagging this as the one acceptance item I knowingly did not meet**
rather than meeting it with an invented number.

## AR / MS

The stale values said "not a Sharia screen" (`ليست فحصًا شرعيًا` / `bukan saringan Syariah`)
— now false in those locales too. I **removed** them so the keys fall back to English, and
kept the `@`-entry as the record of why. Re-translating observance-sensitive copy without a
qualified reviewer is the thing the DEF084 posture forbids; leaving a known-false religious
claim standing because "AR/MS stay placeholder" would have been the literal reading of the
instruction and the wrong one. Untranslated counts went 113 → ar, 114 → ms.

## Not verified

- **No device run.** No version/build bump per the assign; the four states are verified by
  widget test, not by eye on hardware.
- **The paused state has never been observed live** — the screen was healthy
  (`stale=False`) throughout. Its copy is exercised by test only.
- The narrow duplicate-suppression match in `_visibleViolations` (ticker AND standard) is
  tested against the live META sentence, but it is a string match against backend prose and
  will drift if that sentence is reworded. It fails toward duplication, never omission.
