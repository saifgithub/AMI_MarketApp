<!-- dispatch lane hand-off. CR052. -->
# CR101-MOBILE — hand-off

BRANCH: `lane/CR101-MOBILE.coder.mobile` @ `34faaab1` (from `main` @ `3f423361`)
WORKTREE: `.claude/worktrees/coder.mobile-CR101-MOBILE`

## Read the bridge first — the field-semantics deviation, the retro-tightening timing gap, and the L1 scope call

`orchestration/audit/cr/CR101-MOBILE.architect.md` covers three disclosed judgment calls in
detail: (1) the assign's "None means OFF for all seven fields" is measurably false for
`sector_cap_pct`/`single_name_cap_pct` — the CR101-BE1 bridge shows unset there still enforces
via a server preset the API never returns a number for, so this screen renders "Following your
risk profile" instead, never "OFF"; (2) retro-tightening disclosure runs immediately AFTER save,
not before it, because BL12's audit endpoint reads the currently-persisted mandate and there is
no preview-a-candidate-mandate endpoint; (3) L1's "writes all caps coherently from a preset" only
actually re-asserts the two CR101-BE1 caps — the five CR101-BE2 fields have no backend-defined
preset relationship to `risk_score` at all, so a preset value for them would be a client
invention, which the fence forbids.

## What shipped

- `RiskLimitsSection` (new file, `mobile/lib/screens/settings/risk_limits_section.dart`): all
  seven fields, each in its own units, wired into Settings' Mandate section.
- `UserMandate` (`models/mandate.dart`) gained the seven fields + a `HoldingsAuditResult` model
  for the BL12 audit response.
- `ApiClient.auditMandateHoldings` (new method) — `GET /v1/mandate/{id}/audit`.
- 30 new ARB keys in `app_en.arb`, all flagged `retranslate:[ar,ms]`; `app_ar.arb`/`app_ms.arb`
  carry the literal EN text as an honest placeholder, not a fabricated translation (DEF158).

## Acceptance, one line each

| # | Criterion | Result |
|---|---|---|
| 1 | All seven fields visible/settable, own units, unset renders OFF/following-profile | ✅ `risk_limits_section_test.dart` — "all seven fields render" + the distinct-value test below |
| 2 | L2 round-trips against the SERVER's value, not local state | ✅ `settings_screen_risk_limits_test.dart` — mocked "server" deliberately returns a value DIFFERENT from what was typed; screen renders the server's |
| 3 | L1 writes the two BE1 caps coherently; an L2 edit to either flips the dial to Custom | ✅ two tests: moving the slider clears both overrides (no Custom badge); an explicit L2 edit sets it — both integration-level, through the real `SettingsScreen` |
| 4 | A looser-than-current edit discloses its consequence at set-time, inline | ✅ 5 cases in `risk_limits_section_test.dart` (looser count, cleared-to-off, 100%-percent special case, BE1 unset->explicit, negative case: tightening discloses nothing) + 9 pure `classifyLimitEdit` unit tests |
| 5 | Retro-tightening: flag + block, never implies a forced sell | ✅ `RetroTighteningDialog` test asserts "nothing is sold automatically" present, "liquidat*" absent |
| 6 | No numeric cap literal anywhere in `mobile/lib` | ✅ two independent guards — a behavioural test (two mandates, two distinct rendered values, rules out ANY hardcoded substitute) + a source-literal grep for the six known backend preset numbers |
| 7 | Mutations, honest report incl. any GREEN | ✅ both RED — see below, no green surprises |
| 8 | Full suite green + `flutter analyze` clean | ✅ 309 → 330 (baseline confirmed before starting), analyze 5 issues both before and after (pre-existing infos, unchanged) |

## Measured

**Full suite**, `flutter test -r compact` from `mobile/`: **330 passed** (baseline **309**,
confirmed by running the suite before any change — matches the assign's stated baseline exactly).
**`flutter analyze --no-fatal-infos`**: exit 0, 5 issues both before and after — the same 5
pre-existing infos named in the assign, no new ones introduced. `git status --short` (in the
worktree) showed only this lane's own tracked changes before both measurements.

**Mutation matrix**, both reverted immediately after measurement, neither left mutated:

| Mutation | Result |
|---|---|
| CLEAN | 330 passed |
| M1 — `RiskLimitsSection._serverValue('sector_cap_pct')` hardcoded to `mandate.sectorCapPct ?? 40.0` | **RED — 2**: the behavioural distinct-value test AND the source-literal guard both caught it independently |
| M2 — `_isCustomRiskProfile` in `settings_screen.dart` hardcoded to always return `false` | **RED — 2**: both acceptance-3 integration tests (slider-clears-overrides, L2-edit-sets-Custom) |

Both diffed against a pre-mutation backup and confirmed byte-identical after revert. No mutation
came back green.

## Not verified — named, not omitted

- **No device check.** Every claim above is a `flutter test`/`flutter analyze` result on the Mac,
  which is a pure editor — nothing promoted to Alpha, no on-device finger-on-glass pass on the
  actual TextField/keyboard interaction, no verification that the number pad shows correctly for
  the percent/count/hours fields on iOS or Android. This is a legitimate NEEDS-DEVICE-CHECK, not
  a gap I could close from here.
- **The `Wrap`-based chip+field layout at narrow widths** was fixed once (an `Overflow`ing `Row`
  the widget test surfaced at 390pt) by switching to `Wrap`, but I have not confirmed it reads
  well at every locale's text length (AR/MS placeholder strings are the same EN length for now,
  since they're untranslated placeholders — a real AR/MS translation could be longer and re-wrap
  differently).
- **Whether the retro-tightening dialog's post-save timing is acceptable UX**, given the assign
  literally said "before saving" — see the bridge's judgment call 2. I judged this the honest
  reading of a contract the backend doesn't support any other way, not a silent substitution.

## Found, NOT fixed

- **No backend endpoint exposes the resolved preset number for `sector_cap_pct`/`single_name_cap_pct`
  when unset.** `trading_math.sizing.risk_tier_cap`/`resolved_sector_cap_pct` compute it
  server-side but nothing returns it over the wire — `GET /v1/mandate/{id}` echoes `null` for both
  fields when unset, same as the raw stored value. This screen therefore cannot show what an
  unset cap currently enforces to, and does not guess: it names the mechanism ("Following your
  risk profile") instead of a number. If Saiful wants the ACTUAL number shown for an unset cap,
  that needs a backend follow-up (e.g. stamp the resolved value onto the `GET` response, mirroring
  how `_with_plan_state` already stamps plan/credit state) — recommend the Architect mint a CR/DEF
  for it; not something a mobile-only lane can close.

## Fences honoured

- **Did not touch `backend/`** — `git diff --stat` against `main` confined to `mobile/`.
- **No client-side clamp** — every field accepts any value `num.tryParse` parses; nothing caps
  the typed value below what the server would accept.
- **Did not surface `drawdown_response`/`regret_asymmetry`** as settings.
- **Registers**: no row-file/table change made. CR101's row still reads `started` — my read is
  that flipping it to a terminal state is the auditor/Architect's call once this round is
  reviewed, matching the precedent BE1/BE2's own bridges set (both left the register untouched
  for the same reason).

STATUS: READY_FOR_AUDIT (round 1)
