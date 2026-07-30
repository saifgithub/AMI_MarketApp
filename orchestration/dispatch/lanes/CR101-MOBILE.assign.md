<!-- lane assign — Architect-owned. CR052. -->
# CR101-MOBILE — the three-layer risk settings UI

KIND: code
INSTANCE: coder.mobile
GATE: independent    <!-- This is the surface where the user exercises the right the CR was amended to grant. A dial that looks authoritative and writes nothing is the exact failure DEF129 and DEF158 were both filed for. -->
BUDGET: $20
DEPENDS-ON: CR101-BE1, CR101-BE2

## What and why

Saiful, 2026-07-29: *"we had a CR related to 4 additional risk parameter to be set for the customer.
I cant see it in the settings page."* This lane is the page.

Today Settings sends exactly three keys (`settings_screen.dart:51-63`): `risk_score`,
`max_drawdown_pct`, `compliance`. Everything else in the Mandate is either unsettable or absent.
The governing rule is Saiful's amendment: *"a risk setting that a user cannot change violates the
user's rights… they should be able to set whatever they like."*

## Three layers — this structure is decided, not a suggestion

- **L1 — one Risk Profile dial.** Writes all caps coherently from a preset. For the user who never
  opens the next layer, the UX is identical to today's single risk slider.
- **L2 — "Set my own limits".** Exposes each cap **in its own units** (a percentage as a
  percentage, a count as a count, a duration as a duration — never an opaque 1-5 ordinal) and
  detaches the dial to **Custom**.
- **L3 — no ceiling, loud disclosure.** 100% is allowed. A **silent** 100% is not (CR040). A
  looser-than-profile value must show its consequence **at set-time**, not after the loss.

Rationale, so it is not re-litigated: in a simulation-only trainer the blow-up **is** the lesson.
Hiding the dial is opacity, and opacity is what CR040 exists to stop.

## What to build

1. L1/L2/L3 as above. **The backend shipped SEVEN settable fields, not six** — read the two bridges
   (`orchestration/audit/cr/CR101-BE1.architect.md`, `CR101-BE2.architect.md`) for exact names,
   units and semantics before you build a single control:

   | Field | Units | From |
   |---|---|---|
   | `sector_cap_pct` | percent (0-100) | CR101-BE1 |
   | `single_name_cap_pct` | percent (0-100) | CR101-BE1 |
   | `post_loss_cooldown_hours` | hours | CR101-BE2 |
   | `max_open_positions` | count | CR101-BE2 |
   | `max_trades_per_day` | count | CR101-BE2 |
   | `max_trades_per_week` | count | CR101-BE2 |
   | `max_open_risk_pct` | percent (0-100) | CR101-BE2 |

   "Max trades per day/week" is **one named limit but two independent fields** — either at its cap
   blocks. Do not collapse them into one control. **`None` means the limit is OFF**, and that is a
   real, common state a user must be able to see and return to — an off limit must render as off,
   not as zero. Zero is a real value meaning "block everything."

   Behaviours that are fixed backend-side, so do not re-invent or contradict them: the day/week
   boundary is **fixed UTC** (calendar day, ISO week from Monday 00:00 UTC), not the user's
   timezone; `max_open_positions` counts **distinct tickers**, so adding to a name already held is
   never a new position; post-loss cooldown is a **hard block** that names when it lifts.
2. **Every displayed number comes from the server's mandate, never a client-side constant.** CR046's
   shown-equals-enforced applies verbatim: the number on screen must be the number enforced. A
   hard-coded `0.40` or `4.5` anywhere in the client is a defect even when it currently matches.
3. **Retro-tightening disclosure.** When a new value would put current holdings in breach, say so
   before saving, and state what actually happens: **affected holdings are flagged and new buys are
   blocked — nothing is force-sold.** Do not invent a different remedy; that behaviour is fixed
   backend-side in BE2. Note only `max_open_positions` and `max_open_risk_pct` have a
   portfolio-state dimension at all — the cooldown and the two trade-pace fields constrain the
   NEXT trade, so there is nothing to flag for them. Do not show a retro-breach warning for a
   limit that cannot have one.

3b. **Known backend gap you must not paper over (auditor M1 on CR101-BE2).** The trade-ticket
   **preview** path cannot price a proposal's OWN contribution to `max_open_risk_pct`, because
   `preview()` has no stop parameter. So a trade that would tip an under-cap portfolio over the
   open-risk cap **shows as fine in preview and then blocks at submit**. Do not present preview as
   authoritative for that one limit. Either say plainly that open-risk is confirmed at submit, or
   leave it unstated — but never render a green "within your limits" for open-risk on the preview
   path, because that is a shown-vs-enforced lie of exactly the kind CR046 exists to stop. If you
   think the honest fix is a `stop` param on `preview()`, say so in the hand-off; that is backend
   scope, not yours.
4. **ARB strings** in `app_en.arb` + `app_ar.arb` + `app_ms.arb`, EN placeholders in AR/MS flagged
   `retranslate:[ar,ms]`. Do not ship a fluent translation of a claim you have not verified — that
   was **DEF158**.

## Fences

- **Do NOT touch `backend/`.** Both halves land before you; the API is fixed by then.
- **Do NOT add a client-side clamp.** If the server accepts it, the client shows it. A client that
  silently refuses a value the mandate allows re-creates the unsettable-field defect one layer up.
- **Do NOT surface `drawdown_response` or `regret_asymmetry` as settings.** They are write-once
  onboarding inputs to the initial risk-score derivation (`concierge_engine.py:409-415`), not
  enforced limits — a slider on them would be a control that changes nothing.
- **Registers:** row file and regenerated table in the SAME commit (**DEF159**).

## Acceptance

1. Every one of the **seven fields** in the table above is visible and settable, each in its own
   units, and an unset (`None`) limit renders as OFF rather than as `0`.
2. A value set in L2 round-trips: set, save, reload from server, and the **server's** value is what
   renders. Test asserts against the server value, not local state.
3. L1 preset selection writes all caps coherently; changing any single cap in L2 moves the dial to
   **Custom**.
4. A looser-than-profile value renders its consequence **before** the save completes, and the test
   asserts the disclosure text is present in the tree — not merely that the save succeeded.
5. Retro-tightening shows the flag-and-block disclosure and never offers or implies a forced sell.
6. **No numeric cap literal anywhere in `mobile/lib`.** A guard test greps for hard-coded cap values
   and fails on any. This is the client half of CR046 and I will read it first.
7. Mutations: replace a server-sourced value with a client constant that happens to match → the
   acceptance-6 guard goes RED. Detach the L2-to-Custom wiring → acceptance 3 RED. Report both,
   honestly, **including any that come back GREEN**.
8. Full mobile suite green + `flutter analyze --no-fatal-infos` exit 0 with only the known
   pre-existing infos. State your starting baseline; it will have moved past 309.

## Hand-off delivery — read this, it has failed three times today

Your work is not done when it is green on your branch. `dispatch.sh` derives lane state from files on
**`main`**, and the auditor's watcher globs `orchestration/audit/cr/*.architect.md` on **`main`**. A
lane whose hand-off lives only on its own branch is finished and **invisible at the same time** —
CR120, DEF142 and CR112 all did this today. Minted as **DEF175**.

As your final act:

1. Write `orchestration/dispatch/lanes/CR101-MOBILE.coder.mobile.md` with
   `STATUS: READY_FOR_AUDIT (round 1)`.
2. Write `orchestration/audit/cr/CR101-MOBILE.architect.md` **with an explicit `SUBMITTED: round 1`
   line** — without one it silently enqueues at round 0 (the DEF142 trap).
3. Get both onto `main`. If you cannot, say so **loudly** in your hand-off.

**Write the bridge for a real audit.** This screen is where the user exercises the right the CR was
amended to grant, and it ships to testers in the same build. Name your numbers, state what you could
not verify (finger-on-glass behaviour is a legitimate NEEDS-DEVICE-CHECK), and disclose every
judgment call rather than letting the auditor find it.

ASSIGNED: coder.mobile round 1
DISPATCH: ACCEPTED

