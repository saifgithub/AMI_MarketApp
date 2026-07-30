<!-- lane assign — Architect-owned. CR052. -->
# CR129-MOBILE — presets in the UI, resolved numbers on screen, and the Day Trader entry

KIND: code
INSTANCE: coder.mobile
GATE: independent
BUDGET: $20
DEPENDS-ON: CR129-BE, DEF193

## What and why

Read `docs/forward_planning/CR129_risk_limits_from_risk_tolerance/README.md` first.

CR101-MOBILE shipped the seven-field screen, but two fields render **"Following your risk profile"
with no number**, because no endpoint exposed the resolved value (**DEF193**). After CR129-BE all
seven are profile-derived, so that gap now covers the whole screen — unacceptable for the CR whose
entire claim is that the number shown is the number enforced (CR046).

## What to build

1. **Every limit shows its resolved number**, with provenance — "40% — from your risk profile" —
   not the mechanism alone. Requires **DEF193**; if the backend field is not there, say so loudly
   rather than computing the preset client-side. A client-side preset table is the hard-coded-cap
   defect CR046 forbids and CR101-MOBILE's own acceptance-6 guard will fail it.
2. **L1 becomes a preset picker**: the five risk profiles plus **Day Trader**. Selecting one clears
   overrides so every field re-follows the preset; editing any single field moves the dial to
   **Custom**.
3. **Day Trader selection discloses before it applies** — what it turns off, and what the evidence
   says happens (Barber & Odean: most-active 11.4%/yr vs least-active 18.5%; Taiwan survival
   44/24/15% at 1/2/3yr). **Inform, do not block** (L3: no ceiling, loud disclosure). State plainly
   that compliance, locale and halal limits are NOT removed.
4. **ARB strings** in all three locales, AR/MS as EN placeholders flagged `retranslate:[ar,ms]`.
   Do not ship a fluent translation of a claim you have not verified (**DEF158**).

## Fences

- **Do NOT touch `backend/`.**
- **Do NOT hard-code any preset value or cap** — server-sourced only.
- **Do NOT present the Day Trader preset as removing compliance/halal/locale.** It does not.
- Registers: row file + regenerated table in the SAME commit (**DEF159**).

## Acceptance

1. All seven render a resolved number from the server, with provenance, for both the following-profile
   and explicit-override states.
2. Preset selection round-trips against the **server's** value, not local state.
3. Editing one field flips the dial to Custom; selecting a preset clears overrides.
4. Day Trader disclosure asserted present in the widget tree **before** the save completes, and its
   text names what is NOT removed.
5. **No numeric cap literal anywhere in `mobile/lib`** — the CR101-MOBILE guard test still passes.
6. Mutations: swap a server value for a matching client constant → acceptance 5 RED. Remove the
   Day Trader disclosure → acceptance 4 RED. Report both honestly, **including any GREEN**.
7. Full mobile suite green + `flutter analyze --no-fatal-infos` exit 0 with only the known infos.
   Run from `mobile/` with `/opt/homebrew/bin/flutter test -r compact`; **pipe through `tr '\r' '\n'`
   before grepping**. Baseline **330**, analyze **5** pre-existing infos. Run `flutter gen-l10n`
   after ARB edits.

## Hand-off delivery

`orchestration/dispatch/lanes/CR129-MOBILE.coder.mobile.md` with `STATUS: READY_FOR_AUDIT (round 1)`;
`orchestration/audit/cr/CR129-MOBILE.architect.md` with an explicit `SUBMITTED: round 1` line; BOTH
onto `main` and **push your lane branch to origin** (**DEF175**). Name what you could not verify —
finger-on-glass and AR/MS layout are legitimate NEEDS-DEVICE-CHECK.

ASSIGNED: —
DISPATCH: BLOCKED
