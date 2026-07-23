<!-- dispatch assign lane — Architect-owned. CR052. -->
# CR069-MOBILE — assign (Phase 1b UI copy + the three-state surface)

KIND: code
INSTANCE: coder.mobile
ACCEPTANCE: docs/forward_planning/CR069_sharia_compliance_indicator/CR069_sharia_compliance_indicator.md (§Phase 1b, §Design constraints 1-2, §Acceptance 3)
DEPENDS-ON: CR069-BE — **hard**. The verdict shape and the as-of stamp come from that lane's API; the contract is hand-mirrored, not type-enforced.
GATE: independent    <!-- recorded upfront at decomposition. Ships to two app stores and states a religious-observance claim — the exact category and the exact surface of DEF084-MOBILE. Irreversible: a wrong string needs a new build and a review cycle, not a redeploy. -->
HOT-FILES: mobile/lib/services/api/api_client.dart (coder.mobile-internal, serialize) · mobile/lib/l10n/app_*.arb

**What:** Replace the DEF084 honesty placeholder — *"Curated demonstration universe … not a Sharia
screen"* — with copy that describes the screen CR069-BE actually runs, and render the **third state**
so "unknown" reads as *no ruling* rather than a soft no.

---

## 0. Do not start before CR069-BE is merged

Its verdict type carries the standard name, source and as-of date. Building against a guess and
mirroring it wrong is the failure mode BINDINGS calls out: the backend↔mobile contract is
**hand-mirrored JSON, not type-enforced**, so a rename fails silently at runtime behind `?? default`.
**Re-verify `fromJson` against real backend JSON** — an actual response body, not a compile.

## 1. Copy — G2 is RESOLVED; build to it

The exact EN strings are in the CR at §Phase 1b. You may tighten wording. You may **not** drop the
standard name, the source, the as-of date, or the coverage boundary — each of those is a
constraint-1 requirement, and together they are the difference between a claim we can defend and
DEF084 again.

Touch: `settingsComplianceHalal` (toggle label), `settingsComplianceHalalSubtitle`,
`_complianceExplanations['halal']` (`mobile/lib/screens/settings/settings_screen.dart:355` and
`mobile/lib/l10n/app_en.arb:395` are the DEF084 sites).

**Four states get copy, not three** — the CR lists the fourth: source unavailable or stale ⇒
*"AMI couldn't refresh the Sharia screen (last updated {date}). The halal filter is paused until it
can."* If CR069-BE pauses the flag and the app has no string for it, the degrade is loud on the
server and silent on the phone, which is the whole failure class.

Render the state wherever a ticker's status appears: Room convene, trade rejection, watchlist.

**G3 is RESOLVED (Saiful, 2026-07-23): unknown is PERMITTED, with the disclosure attached.** That
changes where the unknown copy lives. It is **not** a rejection message — the trade goes through — so
it cannot ride on the rejection surface the way screened-out does. A permitted trade that shows
nothing is a silent pass on an observance decision, which is this CR's failure class pointing the
other way. Find the surface that a *successful* trade renders and put it there, and make sure it
reads as *"AMI has no ruling on this"* rather than as a warning that the trade was risky.

## 2. i18n

- **AR and MS stay placeholder** until reviewed — observance-sensitive, same posture as the DEF084
  strings. Add translator notes in the `@` metadata explaining the standard and the coverage
  boundary, so a translator does not turn "unscreened" into "not permitted."
- **DEF069:** ARB `use-escaping` is off ⇒ write a single `'`, never `''`.
- **AMI by name.** Never "the AI" in anything a user reads.

## 3. Tests

`flutter analyze lib/` clean of new findings, plus `flutter test`. Add a widget-level assertion that
the unknown state renders the unknown copy and **not** the screened-out copy — that specific
confusion is constraint 2, and it is a false assurance in the direction nobody checks.

## 4. Constraints

- Do not touch backend paths. Do not correct SHARIA lesson content — G7, SME-gated, and behind
  DEF082.
- **No version/build bump in this lane.** Shipping to a device is the Architect's call after the
  gate, not a coder's.
- Commit incrementally.

## 5. Delivery

**Push to `lane/CR069-MOBILE.coder.mobile`, NEVER to `main`.** DEF084-MOBILE pushed its source
straight to the shared branch and had its gate waived at hand-off; both rules exist because of this
exact lane's ancestor.

**Hand-off:** `orchestration/dispatch/lanes/CR069-MOBILE.coder.mobile.md` with
`STATUS: READY_FOR_AUDIT (round 1)` + `orchestration/audit/cr/CR069-MOBILE.architect.md` with
`SUBMITTED: round 1`. Chunk evidence list, **not** the Definition of Done. Include the real backend
JSON you verified `fromJson` against.

**Commit both hand-off files to the SHARED branch, not your lane branch** (DEF090) — source goes
to the lane branch; the lane files are shared coordination state and every board reads them on the
shared branch. A hand-off committed only to a lane branch is invisible to both boards and has
already stranded a finished round; an uncommitted one now renders `UNCOMMITTED` (DEF087).

Commit tag `(AT:coder.mobile CR069)`. Report SHA + `flutter analyze` / `flutter test` exit codes.

<!-- CR069-BE merged at bdc410f (VERDICT: COMPLETE round 3), so the code dependency is satisfied —
but this lane is HELD, not assigned, and the open action is the Architect's. See below. -->

## UNBLOCKED — the backend is live with the screen ON

Promoted `alpha-2026-07-23-1`. `SHARIA_SCREEN_ENABLED=true` on Alpha, verified **inside the
deployed container**:

```
enabled: True
compliant=216  parent=503  as_of=2026-07-23  stale=False
AAPL pass · META screened_out (blocking) · JPM screened_out · ASML unknown (permitted)
```

**Get your real backend JSON from `https://api-alpha.agenticmarketintel.ai`.** That is the contract
check this lane owes — an actual response body, not a compile.

**The stakeholder has seen the stale copy in the running app** and called it out: Settings still
reads *"Curated demonstration universe … not a Sharia screen"* while the backend now runs a real
AAOIFI screen. The two surfaces contradict — the DEF084 shape pointing the other way. That copy was
honest when it shipped; it is false now. **This lane is the fix, and it is the visible half.**
DISPATCH: OPEN

ASSIGNED: coder.mobile round 1
