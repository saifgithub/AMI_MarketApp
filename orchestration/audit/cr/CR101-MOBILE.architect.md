<!-- architect bridge — track R (bridged by coder.mobile per CR052 §6). CR052 / orchestration/audit/PROTOCOL.md. -->
# CR101-MOBILE — architect bridge

ITEM: CR101-MOBILE
INSTANCE: coder.mobile round 1
GATE: independent
SCOPE: chunk
BRANCH: `lane/CR101-MOBILE.coder.mobile` @ `34faaab1` (from `main` @ `3f423361`)
WORKTREE: `.claude/worktrees/coder.mobile-CR101-MOBILE`
SUBMITTED: round 1

---

# Round 1

## Why this is the screen Saiful is waiting to see

2026-07-29: *"we had a CR related to 4 additional risk parameter to be set for the customer. I
cant see it in the settings page."* Then 2026-07-30: *"I have a problem visualizing this. Lets
just build and release to testflight/play store so I can have a look at it."* This lane is that
screen. It ships to TestFlight/Play immediately after hand-off, so I've erred toward disclosing
every judgment call rather than let a silent gap surface first on his phone.

## Three judgment calls, disclosed — read before the acceptance table

### 1. The assign's field table says "`None` means the limit is OFF" for all seven fields. That is measurably false for two of them.

The assign (`orchestration/dispatch/lanes/CR101-MOBILE.assign.md`, item 1) states: *"`None` means
the limit is OFF, and that is a real, common state a user must be able to see and return to — an
off limit must render as off, not as zero."* Read against the CR101-BE1 bridge, this is only true
for the five CR101-BE2 fields. For `sector_cap_pct`/`single_name_cap_pct`, BE1's own bridge
measured (and disclosed) that unset does NOT mean unenforced — it falls back to a server-side
preset table (`trading_math.sizing.risk_tier_cap`, `resolved_sector_cap_pct`, keyed off
`risk_score`/`concentration_tolerance`) that is still a real, binding cap. `GET /v1/mandate/{id}`
never returns the resolved number for that preset — it echoes `null`, identically to the raw
stored value.

Given that measurement, rendering "OFF" for an unset `sector_cap_pct`/`single_name_cap_pct` would
be a lie of exactly the shape CR046 exists to stop: it would tell the user nothing is enforced
when something is. I did not follow the assign's literal wording here. Instead:

- `sector_cap_pct`/`single_name_cap_pct` unset → renders **"Following your risk profile"**, never
  a number (the API doesn't expose one) and never "OFF".
- The five CR101-BE2 fields unset → renders **"OFF"**, exactly as the assign describes — these
  genuinely have no preset; `null` is unenforced.

**What I want the auditor to attack:** is "Following your risk profile" with no number the right
compromise, or should this lane instead have asked backend for a resolved-value field on the
`GET` response (a small addition — `_with_plan_state`-style stamping) rather than living with an
un-renderable number? I judged adding a backend field out of a mobile-only lane's fence, and
"name the mechanism honestly, show no fabricated number" as the correct interim state. See "Found,
NOT fixed" below — I recommend a follow-up CR/DEF for the backend addition.

### 2. Retro-tightening disclosure fires immediately AFTER save, not before it.

The assign (item 3): *"When a new value would put current holdings in breach, say so before
saving."* The BL12 audit endpoint's own docstring (`backend/app/api/mandate.py:270-274`) says
the opposite is the shipped contract: *"Designed to be called by mobile immediately after a
successful PATCH."* It reads `store.get_or_default(user_id)` — the CURRENTLY PERSISTED mandate —
there is no endpoint that evaluates holdings against a CANDIDATE mandate the user hasn't saved
yet. A strict "before saving" implementation isn't achievable against the API as shipped without
either (a) reimplementing the BL12 audit logic client-side against a not-yet-saved mandate — which
would violate "no client-side reimplementation of enforcement logic" as surely as a hardcoded cap
would — or (b) a backend change, out of this lane's fence.

I implemented: PATCH first, then immediately call `GET /v1/mandate/{id}/audit` before the user can
navigate away or believe the save is fully settled, and show the flag-and-block dialog if it
reports a breach. This is the honest reading of the shipped contract, not a silent substitution
for "before saving" — flagged here for the auditor to weigh against the assign's literal wording,
same shape as BE1's single-name-cap-default disclosure and BE2's `proposed_stop` disclosure.

### 3. L1's "writes all caps coherently from a preset" only reaches the two CR101-BE1 caps.

The assign describes L1 as "one Risk Profile dial. Writes all caps coherently from a preset." I
read "all caps" as scoped to what the backend actually defines a preset relationship for.
`sector_cap_pct`/`single_name_cap_pct` have one (BE1's `risk_tier_cap`/`resolved_sector_cap_pct`,
keyed off `risk_score`). The five CR101-BE2 fields (cooldown, max open positions, max
trades/day/week, total open-risk cap) have **no** preset relationship to `risk_score` anywhere in
the backend — BE2's bridge describes them as pure user-set overrides defaulting to OFF, with zero
mention of a risk-profile-driven default. Inventing preset numbers for those five to make L1
"coherent" across all seven would be exactly the client-side-constant defect CR046 forbids.

**What shipped:** moving the L1 risk-profile slider sets `risk_score` AND clears any explicit
override on `sector_cap_pct`/`single_name_cap_pct` (so they re-follow the new profile's preset —
the one relationship the backend actually defines). The five BE2 fields are untouched by L1 and
live purely in L2/L3. Flag if you read the assign's "all caps" as requiring backend follow-up work
to define presets for the other five before this lane could be considered complete.

## Acceptance

| # | Criterion | Result |
|---|---|---|
| 1 | Every one of the seven fields visible/settable in its own units; unset renders OFF (BE2 five) / following-profile (BE1 two) | ✅ `risk_limits_section_test.dart::acceptance 1` |
| 2 | L2 round-trips against the SERVER value | ✅ `settings_screen_risk_limits_test.dart::acceptance 2` — mocked "server" returns a value different from what was sent |
| 3 | L1 writes coherently; an L2 edit to either BE1 cap flips the dial to Custom | ✅ two integration tests |
| 4 | Looser-than-current shows its consequence before save completes | ✅ inline disclosure, tested at 5 concrete transitions + 9 pure-function cases |
| 5 | Retro-tightening: flag + block, never a forced sell | ✅ dialog text asserted, "liquidat*" absent |
| 6 | No numeric cap literal in `mobile/lib` | ✅ behavioural + source-literal guards, both independently mutation-tested |
| 7 | Mutations reported honestly | ✅ both RED, see hand-off |
| 8 | Full suite green + analyze clean | ✅ 309→330, analyze unchanged at 5 pre-existing infos |

## Measured

| Check | Result |
|---|---|
| `flutter test -r compact`, `mobile/`, foreground | **330 passed** (baseline **309**, confirmed by running before any change) |
| `flutter analyze --no-fatal-infos` | exit 0, **5 issues** both before and after (same pre-existing infos, none new) |
| `git status --short` in the worktree, before commit | only this lane's own tracked changes |

Mutation matrix in the hand-off (`CR101-MOBILE.coder.mobile.md`) — two mutations, both RED, both
reverted and diff-confirmed byte-identical.

## What I have NOT established

- **No device check.** Mac is a pure editor; nothing promoted to Alpha. The number-pad keyboard
  behaviour, `Wrap` layout at real device widths, and finger-on-glass interaction with the
  ChoiceChip/TextField pair are untested beyond the 390×2000 widget-test surface. Legitimate
  NEEDS-DEVICE-CHECK.
- **AR/MS layout at real translated string lengths** — today's AR/MS strings are the untranslated
  EN placeholder (flagged `retranslate:[ar,ms]`), so the `Wrap` layout hasn't been exercised
  against genuinely longer/RTL text yet.
- **Whether "Following your risk profile" with no number is the right long-term answer**, versus a
  backend addition exposing the resolved preset value — see judgment call 1.

## Found, NOT fixed

- **No backend endpoint exposes the resolved `sector_cap_pct`/`single_name_cap_pct` preset value
  when unset.** Recommend the Architect mint a CR/DEF for stamping the resolved number onto the
  `GET /v1/mandate/{id}` response (or a dedicated endpoint) so a future revision of this screen can
  show the actual enforced percentage instead of naming the mechanism. Not fixed here — backend
  work, out of this lane's fence.

## Fences honoured

- **Did not touch `backend/`** — confined to `mobile/`.
- **No client-side clamp** on any of the seven fields.
- **Did not surface `drawdown_response`/`regret_asymmetry`.**
- **Registers**: untouched, same precedent as BE1/BE2's own bridges — no row/status change
  requested by this lane's assign, and CR101's overall completion is a call above a single lane.

## Definition of Done

| Row | Disposition |
|---|---|
| **Scope** | 5 modified mobile source files (`models/mandate.dart`, `screens/settings/settings_screen.dart`, `services/api/api_client.dart`, `l10n/app_en.arb`, `l10n/app_ar.arb`, `l10n/app_ms.arb` + 4 generated l10n files), 1 new source file (`screens/settings/risk_limits_section.dart`), 2 new test files. `backend/` untouched. |
| **Tests** | **330 passed** (baseline 309), `flutter analyze` exit 0 with 5 pre-existing infos (unchanged). Two-mutation matrix, both RED, neither left mutated, diff-confirmed. |
| **Manual verification** | **None available** — Mac is a pure editor, nothing promoted to Alpha/TestFlight yet as of this bridge. |
| **Docs** | This bridge, the lane hand-off (`CR101-MOBILE.coder.mobile.md`). Registers untouched — no status change requested by this lane's own assign. |
| **Commit tag** | `34faaab1` `(AT:coder.mobile CR101-MOBILE)` on `lane/CR101-MOBILE.coder.mobile`, pushed to `origin`, unmerged into `main` per protocol. |
| **Scope discipline** | Three disclosed judgment calls (above), one backend gap named and left for the Architect to mint a follow-up rather than fixed inline or silently substituted. |

ARCHITECT VERDICT ON ROUND 1: awaiting auditor review — not yet reviewed by the Architect track.
