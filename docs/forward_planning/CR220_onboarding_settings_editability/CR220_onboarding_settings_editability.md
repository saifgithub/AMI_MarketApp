# CR220 — make the onboarding-set settings changeable

**Filed:** 2026-09-02 · **Track:** R · **Status:** in_progress · **Tag:** `(AT:R75 CR220)`

Elicitation transcript: [onboarding-settings-editability.md](../../../.deliveryos/elicitation/onboarding-settings-editability.md)

## Why

The Concierge interview asks seven questions and derives a full `Mandate`. Settings lets the user
change the **risk half** of what it produced — risk score, max drawdown, the seven CR101/CR129 risk
limits, the six compliance toggles. The **identity/goal half** is a wall of `_ReadOnlyRow` at
[`settings_screen.dart:329-337`](../../../mobile/lib/screens/settings/settings_screen.dart): locale,
timezone, path, horizon, primary goal. `display_name`, `learning_style`, `risk_quotes` and the
ticker allow/blocklist are not surfaced at all.

**The backend is not the obstacle.** `PATCH /v1/mandate/{user_id}`
([`api/mandate.py:145`](../../../backend/app/api/mandate.py)) takes an untyped dict →
`MandateStore.patch` ([`mandate_store.py:172-202`](../../../backend/app/services/mandate_store.py)),
which strips only `CLIENT_UNWRITABLE_MANDATE_FIELDS`, deep-merges, re-validates through the full
schema, bumps the version and journals the edit. `primary_goal`, `horizon`, `path`, `display_name`,
`timezone` and `learning_style` are **not** in that set — every one already PATCHes successfully
today. The gap is that nothing in the client offers the control.

This continues CR101's ruling (Saiful, 2026-07-29): *"a risk setting that a user cannot change
violates the user's rights… they should be able to set whatever they like."* CR101 applied it to the
risk parameters; CR220 applies it to the identity/goal fields. Restart-onboarding does genuinely
rewrite the mandate now (DEF160, ruled 2026-07-30), but re-answering seven questions to change one
field is not an edit path — and it cannot reach the fields the interview never asked about.

The payment-derived boundary the request calls out already exists and is reused verbatim:
`CLIENT_UNWRITABLE_MANDATE_FIELDS` ([`schemas/mandate.py:57-70`](../../../backend/app/schemas/mandate.py),
DEF179) — `plan`, `credit_balance`, `credit_allowance`, `trial_*`, plus the read-path-stamped
`resolved` / `day_trader_preset`. No second list is invented.

## What ships

### Backend (to Alpha first — D9, the DEF195 lesson)

1. **Journal diff labels.** `patch_mandate`'s plain-English diff loop has no entry for any newly
   editable field, so they fall through to the bare `"Mandate updated."` — the exact shape DEF197
   filed against the CR101-BE1 pair. Extend the existing tuple loop and the `compliance` sub-loop.
2. **Compliance default inversion.** `_parse_constraints`
   ([`concierge_engine.py:389-401`](../../../backend/app/services/concierge_engine.py)) always
   returns an explicit dict carrying `long_only=False, liquid_only=False`, while `Compliance`
   defaults both to `True`. An onboarded user is therefore **less** constrained than a
   never-onboarded one, and the `or Compliance().model_dump()` guard at `:504` can never fire
   because the dict is never falsy. Only set a key the user's text actually asserts.
3. **Backfill (D10).** Every stored row carrying the inverted pair is corrected, one journaled
   mandate version per user, with the affected count measured before the run.
4. **Ticker list validation.** Validate `ticker_blocklist` / `ticker_allowlist` on PATCH via
   `lookup_ticker` — the resolver already behind `GET /v1/tickers/validate` (CR128). 422 on an
   unresolvable symbol; an empty allowlist normalises to `None`, never stored as `[]` (an empty
   allowlist means nothing is tradable).
5. **`Path.BOTH` (D11).** Wire real prompt text in the Market, News/Macro and Social analyst
   branches so the value means what its name says before the picker can select it.

### Mobile

6. **Profile section becomes editable** — enum pickers for `primary_goal` (6), `horizon` (4),
   `path` (3), `learning_style` (4); a text field for `display_name`; an IANA picker for `timezone`.
   Generalise the existing `_DrawdownPicker` ChoiceChip shape; do not add a second picker idiom.
   Plan and Credits keep `_ReadOnlyRow`.
7. **Ticker allow/blocklist editor** in the Compliance section, validating through the existing
   `ApiClient.validateTicker` + `TickerNotFoundPanel`. No new route. The allowlist carries a loud
   disclosure: a non-empty allowlist refuses everything outside it.
8. **Risk quotes** — three editable text fields showing the verbatim Q3/Q4/Q5 answers, labelled as
   the user's own recorded words. Inert by decision (D5): not injected into any prompt.
9. **i18n** — every new label, value, disclosure and error string, `retranslate:[ar,ms]`.

## Guards

An entry without an enforcing check is not done.

| # | Guard |
|---|---|
| 1 | Every field in the editable set is absent from `CLIENT_UNWRITABLE_MANDATE_FIELDS`, and `plan`/`credit_balance`/`credit_allowance`/`trial_*` remain in it — pins the D3 boundary against drift |
| 2 | A PATCH to each newly-editable field produces a journal line naming it, never the bare `"Mandate updated."` |
| 3 | A "no hard rules" onboarding answer yields `long_only=True, liquid_only=True`, matching a `get_or_default` user. Mutation: reverting `_parse_constraints` turns it red |
| 4 | An unresolvable ticker is refused; an empty allowlist is never stored as `[]` |
| 5 | Each picker's PATCH body key matches the backend field name exactly — the DEF195 guard, since a typo'd key would 200 and silently drop |
| 6 | `Path.BOTH` produces prompt text distinct from `LONG_HORIZON` in all three branches |

## Deliberate non-goals

- **No onboarding/interview changes** (D8). `display_name` stays `"Trader"` at capture,
  `bootstrapAnon` keeps omitting locale/timezone, the Q7 freeform text keeps being dropped. The
  Settings editors make the bad defaults correctable, which is the scoped ask.
- **No `target_outcome` editor**, no `custom_constraints` editor, no server-side locale write (D4).
- **`risk_quotes` stay inert** (D5) — editable and visible, never injected into a prompt.
- **No mini-Concierge re-interview** (D2) — an edit path was wanted, not a re-ask.

## Coordination

CR219 (`room_prompt_contradictions`) is live on `content/agents/*.md` and `_format_profile`. The
`Path.BOTH` work here touches `overlay_generator.py` branches. Check for conflicts before editing
those files.

## What actually shipped

### Backend

| Change | File |
|---|---|
| `_parse_constraints` OMITS the two restriction flags unless the user asserts something, so the schema default stands. The opt-OUT is matched explicitly rather than inferred from the bare word "short" — the Q7 chip itself contains "no shorting", and freeform "I don't want shorting" is a request FOR the restriction | `services/concierge_engine.py` |
| The readback summary resolves the partial dict through `Compliance` at the single chokepoint `_build_readback_summary`, so the text the user confirms and the mandate built at claim see the same object. Without this, "long-only" would have dropped out of the readback while still being ENFORCED — the DEF158 promise-vs-mechanism shape | `services/concierge_engine.py` |
| The dead `or Compliance().model_dump()` fallback removed — it could never fire and masked the defect | `services/concierge_engine.py` |
| Journal diff labels for `primary_goal`, `horizon`, `path`, `learning_style`, `display_name`, `timezone`, `locale`, `risk_quotes` and both ticker lists, with `_humanise_enum` / `_humanise_list` helpers. `None` and `[]` render differently for an allowlist, because they mean opposite things | `api/mandate.py` |
| `_validate_ticker_lists` on the PATCH path: unresolvable symbol → 422, empty allowlist → 422 (send `null` to clear), casing normalised to the resolver's canonical form. Reuses `lookup_ticker`; no new route. Placed in the API layer, not the store, because the store is also driven by claim-time hydration and the restart upsert | `api/mandate.py` |
| `Path.BOTH` wired in all three branches. The News/Macro branch carries CR147 Tier A.5's "no macro feed" warning verbatim in substance — dropping it would reopen the fabrication surface CR147 closed | `agents/overlay_generator.py` |
| Backfill script, dry-run by default, one journaled mandate version per repaired user, `--only-untouched` escape hatch | `scripts/cr220_backfill_compliance_defaults.py` |

### Mobile

| Change | File |
|---|---|
| Profile section: pickers for goal / horizon / path / learning style, a text field for display name, an IANA dropdown for timezone. Plan, credits and locale stay read-only | `screens/settings/settings_screen.dart` |
| `MandateChoiceRow` / `MandateTextRow` / `RiskQuotesSection` — the enum generalisation of `_DrawdownPicker`, in their own file so they are unit-testable | `screens/settings/profile_fields_section.dart` |
| Ticker allow/blocklist editors, validating through the existing `ApiClient.validateTicker`; standing warning while an allowlist is non-empty; clearing the last row sends `null`, never `[]` | `screens/settings/ticker_rules_section.dart` |
| `ComplianceFlags` gained value equality + `toPatchJson` now always sends `ticker_allowlist` | `models/mandate.dart` |
| 38 new i18n keys × 3 locales. AR/MS carry the EN string as a VISIBLE placeholder — `retranslate:[ar,ms]` | `l10n/app_{en,ar,ms}.arb` |

### A regression caught by the tests, not by review

`_save()` sent `compliance` on **every** save (`_localCompliance != null`, which `_initFrom` always
populates). That was harmless while the payload was six bools the server merged back to themselves.
It stopped being harmless the moment `toPatchJson` started always carrying `ticker_allowlist`: an
untouched save would have PATCHed `null` over a real allowlist and silently deleted a safety rule.
Fixed by comparing against the server's object — which then required real value equality on
`ComplianceFlags`, since `==` was identity and every `copyWith` looked like a change.

## Shipped

**Alpha:** `alpha-2026-09-03-1` @ `398578db`, promoted 2026-09-03 from a clean detached worktree —
CR219 had 8 uncommitted files on the shared checkout at the time and none of them shipped. All four
preflight gates passed there (hold / audit-lane / tree / suite `VERDICT: PASS`, 5866 passed 0 failed
0 errors, wire contract PASS). Schema at head, container healthy, `/v1/health` reports the tag and
SHA back.

**Backfill: applied to 42 of 45 mandates (93%).** The dry run was read before `--apply`, per the
auditor's promotion condition 1 — and the number is itself the finding: the inversion was systemic,
not an edge case. Two of the 42 were at v4 and v11 (users who had edited since onboarding); Saiful
ruled the full pass with that number in front of him. Re-running the dry run afterwards reports
**0 affected**, which is the idempotency proof. Alpha healthy after the writes.

**Stores:** `0.1.0+103` uploaded to TestFlight (`--internal-only`, forced by the `test_…`
RevenueCat Test Store key in `infra/alpha.env` — purchases are simulated and only INTERNAL groups
can receive it) and published to the Play internal track at the same `+103`.

**The DEF195 guard fired and passed on the way out:** *"✓ every key this client can PATCH exists on
the deployed backend."* That is the check validating CR220's new PATCH keys against the running
Alpha, and it is why the backend-first ordering (D9) mattered.

**Still open:** the round-2 audit verdict. Round 1 returned 2 MAJOR + 3 MINOR, all fixed and
mutation-proven, submitted as round 2 at `398578db`. `NEEDS-DEVICE-CHECK` stands for the pickers,
the ticker chip delete affordance and the allowlist banner.

## Definition of Done

| Item | State |
|---|---|
| Scope | done — 9 fields editable, entitlement boundary reused not reinvented |
| Enforcing check | 35 backend + 11 mobile guards. **9 mutations run and recorded** (5 in round 1, 4 in round 2); that is a count, not a claim of completeness — round 1's audit found three guard-shaped assertions with no guard behind them |
| Degrade loudly | unknown ticker 422s; an allowlist with no real symbol 422s (incl. `[""]`, which round 1 accepted and stored as the exact `[]` it refuses); every repaired user gets a journal disclosure, enforced by a test that reds when the append is deleted |
| Regression risk | three found and fixed by test rather than review: the compliance-always-sent bug, the `[""]` allowlist hole (MAJOR-1), the inverted `--skip-edited` predicate (MAJOR-2) |
