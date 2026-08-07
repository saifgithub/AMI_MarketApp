# Run report — 2026-08-07_run-10

Item: **CR125**, round 1. Architect SHA `a0f122f0` (on `main`, chained from `0a481150`).
Verdict: **AWAITING_FIXES (round 1)** — 1 BLOCKER, 2 MAJOR, 1 MINOR.
Full findings in `orchestration/audit/cr/CR125.auditor.md`.

## Setup (DEF159)

```
git worktree add /private/tmp/.../scratchpad/audit_cr125 a0f122f0
```

Declared-file drift `a0f122f0` → `main` (`f5c47b5b`): only `mobile/lib/services/api/api_client.dart`
touched, entirely by CR121 round 3 (`0423c1a6`, the 426 dead-letter fix) — adds `_client` to
`_VersionGateInterceptor` and a new `onUpgradeRequired` callback. Diffed it explicitly:
`_AuthInterceptor`, `shouldRecoverFromUnauthorized`, `_sseRequest`, `streamBriefMessage`,
`streamOneOnOneMessage`, `streamRoom` are byte-identical. No interference with this audit.

## Regression suite (independent, scratch worktree, absolute interpreter)

```
cd audit_cr125/backend
"/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python" -m pytest tests/unit/ -q
2678 passed, 13 warnings in 330.65s
```
Matches the architect's claimed `2678` exactly.

```
cd audit_cr125/mobile && flutter pub get && flutter analyze --no-fatal-infos
6 issues found (all pre-existing — 2 deprecated copyWith in main.dart, 2 BuildContext-across-async
in floor_screen.dart, 1 in push_notification_listener.dart, 1 super-param lint in a test file)
```
Matches claimed "6 pre-existing".

```
flutter test
00:25 +525: All tests passed!
```
Matches claimed `525` (509 baseline + 16 new).

```
backend/.venv/bin/python -m pytest tests/unit/test_config_compose_parity.py -q
3 passed  # AUTH_TOKEN_TTL_DAYS forwarding confirmed structurally, not just by inspection
```

`alembic heads` in the scratch worktree → `8c5b1a70f4d2 (head)` — single head, independently
derived (not copy of the architect's claim). `alembic history` confirms the chain
`2851822570ac -> 8c5b1a70f4d2`, `1d3f04e6d806 -> 2851822570ac (cr125_token_version)` — no fork.

## The BLOCKER — reproduced live against the actual code, twice, two different root causes

The architect's a0f122f0 fix (relax `exp` on `/v1/auth/anon` only) is sound and its own tests pass
adversarial replay (confirmed independently below). But CR125's own **written Acceptance
criterion** — `CR125_mobile_secure_session.md` line 46-47 and `CR125_implementation_plan.md`
line 123-124, verbatim: *"a device on the old build re-authenticates cleanly on update; the
`user_id` survives, only the credential is reissued — no silent lockout of legitimate data"* — is
violated, and by the exact orphaning mechanism a0f122f0 itself was written to prevent, just via
two different triggers a0f122f0 didn't cover.

### (1) The token-FORMAT migration itself orphans every existing installed user, on the very
    first post-update launch — not a 30-day timer, immediate and certain

`parse_scaffold_token(token, allow_expired=True)` only relaxes the `exp` branch inside the 4-part
current-format parse. The pre-CR125 2-part signed format (`scaffold:<hex>:<sig>`) falls through
BOTH the `len(parts)==4` and `len(parts)==1` branches regardless of `allow_expired`, and hits the
"reject outright" fallthrough — exactly as intended for *ordinary* auth (CR040 degrade-loudly,
confirmed correct below), but this is also `get_rebootstrap_identity_optional`'s ONLY path, so
`/v1/auth/anon` gets `current_user=None` for literally every installed pre-CR125 client, on its
very first bootstrap call after upgrading. `ensure_anonymous` then applies the A2 anti-spoof rule
correctly (`authenticated_user_id is None` → `trust_device_id=False`) and mints a fresh user.

Reproduced directly against the built code (`repro_format_migration.py`, run from the scratch
worktree):

```
minted user: 7b4bcd10-d70d-4f12-8830-d24aa501f2a0 is_new: True
old-format token: scaffold:7b4bcd10d70d4f128830d24aa501f2a0:7b429b...
POST /v1/auth/anon  device_user_id=<that same id>  Bearer=<old-format token for it>
status: 200
returned user id: 1c59cf35-c98d-4447-b444-db375defe165 is_new: True
SAME USER? False
```

This is not a corner case — it is the **default** behaviour for **100% of the alpha cohort** the
moment this is promoted, since every installed token today is pre-CR125 format. It hits everyone
at once, on day zero, which is a worse version of the exact catastrophe the commit message for
a0f122f0 describes ("it would have hit the entire alpha cohort at once, on a timer") — except here
there is no timer and no mitigation window.

### (2) Independently, the mobile 401-recovery path (`AuthNotifier._handleUnauthorized`) defeats
    the backend's own leniency even for a token that WOULD have been honoured

`_handleUnauthorized` in `auth_providers.dart`:
```dart
Future<void> _handleUnauthorized() async {
    await _pushLogout();
    _ref.read(apiClientProvider).setToken(null);
    await DeviceUser.clearTokenOnly();   // wipes the token BEFORE re-bootstrapping
    state = const AuthState();
    await bootstrap();
}
```
`bootstrap()` reads `DeviceUser.getToken()` — now `null`, since it was just wiped — so
`api.setToken()` is never called and `POST /v1/auth/anon` goes out with **no Authorization
header at all**. On the backend that is `current_user=None` in `get_rebootstrap_identity_optional`,
identical code path to (1): `trust_device_id=False`, fresh user minted, even though the dying
token (if it had been *sent*, the way a normal cold-start bootstrap sends it) would have passed
`get_rebootstrap_identity_optional` fine for a plain-expiry 401 — a0f122f0's whole point.

This is a second, independent trigger: any mid-session 401 on a guarded Dio route (the routine
case post-CR125 — 30-day expiry hit while the app was backgrounded-not-killed, or a sign-out
elsewhere) reaches `_handleUnauthorized` and orphans the account. The `device_user_test.dart`
test `'wipes the token but preserves device_user_id'` documents that the LOCAL `device_user_id`
survives `clearTokenOnly()` — true, and reassuring-looking — but nothing in the mobile or backend
suite asserts the SERVER treats that survivor as the same user, because it does not: local
survival of `device_user_id` is irrelevant once `authenticated_user_id` is `None`.

The one backend test that looks adjacent, `test_fresh_token_after_reauth_works_again`, actually
avoids the real case: it POSTs `/v1/auth/anon` with `device_user_id: None` (not the real id), so it
never exercises "bearer-less re-bootstrap with the correct device_user_id attached" — which is
what `_handleUnauthorized` → `bootstrap()` actually sends.

### Why this is a BLOCKER, not a MAJOR

It fails CR125's own written Acceptance criterion outright, on the single most consequential axis
(data loss on 100% of the anonymous-first user base), reproduced live against the exact built
code with no assumptions. Doubt bounces toward MAJOR per protocol; this isn't in doubt.

### Recommended direction (not mandating exact code)

- (1): `get_rebootstrap_identity_optional` — and ONLY that dependency — should also accept the
  legacy 2-part signed format as proof of ownership (same HMAC-over-hex_id check the pre-CR125
  parser used), exactly the same "relax one more axis for this one route" pattern already applied
  to `exp`. It should still mint/return a current-format token in the response so the client is
  upgraded on that very call. Ordinary auth (`get_current_user`/`_optional`) keeps rejecting the
  old format outright — CR040 degrade-loudly is preserved everywhere it matters.
- (2): `_handleUnauthorized` should not pre-emptively wipe the token before asking the backend.
  It should attempt the re-bootstrap call WITH the dying bearer attached (mirroring what
  `bootstrap()`'s normal cold-start path already does), and only treat it as "this identity is
  gone" if the backend actually returns a different `user.id` — trusting the backend's judgment
  instead of deciding client-side, before asking, that the token is worthless.

## Other adversarial checks (all held)

Independent repro script (`repro_adversarial.py`) against the same worktree, not the architect's
own tests:

1. Two tokens minted for one user (simulating two devices) — sign-out via token A also kills
   token B (`401`/`401`) — confirms real per-user revocation via `token_version`, not per-token.
2. Unexpired-but-revoked token replayed at `/v1/auth/anon` → new user minted, does not resurrect
   (`200`, `returned_id != original`).
3. Hand-edited `ver` digit (no re-sign) → `401` on an ordinary route (HMAC catches it) AND does
   not prove ownership on `/v1/auth/anon` either.
4. Hand-written token for a victim's `user_id` with a garbage signature → `401` ordinary route,
   does not prove ownership on `/v1/auth/anon`.
5. Expired token swept across 10 distinct guarded routes (mandate, auth/me, journal, watchlist,
   price_alerts, lessons/progress, portfolio/health, league/me, billing/identity, sim/portfolio)
   → `401` on every one that resolved (4 of the 14 URL guesses were wrong paths → `404`, not an
   auth bypass; re-tested with correct paths for portfolio/league/billing/sim, all `401`).
6. `allow_expired=True` — grepped for every call site: exactly one
   (`api/dependencies.py::get_rebootstrap_identity_optional`), which itself has exactly one
   caller (`api/auth.py::anon_session`). No structural guard exists (no pin, no lint rule)
   preventing a second caller from appearing later — flagged as MINOR, architect explicitly asked.
7. `parse_scaffold_token_user_id` (feedback.py, http_audit.py) — still requires the HMAC
   signature, so it cannot be used to spoof attribution for a user_id the caller doesn't hold a
   real token for. It does not check `token_version`, so a signed-out-but-unexpired token still
   attributes correctly to its real owner (accurate, not a spoof) — consistent with "attribute,
   not authenticate."

## MAJOR — SSE routes never reach the 401-recovery guard

`streamBriefMessage`, `streamOneOnOneMessage`, `streamRoom` build a raw `http.Request` via
`_sseRequest()` and send it through `_httpClient.send()` directly (pre-existing since AT:R33,
finding A8 — bypasses ALL Dio interceptors, not just auth). A 401 on any of the three is caught as
a generic `Exception('HTTP 401 from ... stream')`, never routed through `ApiClient.onUnauthorized`.
Before CR125 this was low-consequence (only a forged/corrupted token could 401 there). CR125 makes
401 on these three routes routine (expiry, revocation), and they are the app's flagship
interactive surfaces (Room convene, Brief Your Agent, 1-on-1 chat). Traced the exception forward
in `room_providers.dart`: it IS caught and shown via `friendlyError` (does not crash), but the
token is never cleared and no re-bootstrap fires, so retrying the SAME action keeps 401ing until
some unrelated Dio-routed call happens to trigger recovery, or the user force-quits. This is
squarely inside CR125's own stated concern ("does a genuine mid-session revocation land somewhere
the user understands, or look like data loss") for 3 of the app's core loops.

## MAJOR — residual-risk call: the architect's stated risk is understated

Architect's framing: "a stolen unexpired token already grants full access, and revocation kills
both, so relaxing exp costs nothing the revocation story depends on." Checked this against what
(1)/(2) above imply about real-world sign-out frequency: for an anonymous-first product, there is
no session-timeout and no natural reason a user ever calls `DELETE /v1/auth/session` unless they
explicitly claim + sign out. An **unexpired** stolen token is naturally bounded — it stops working
once the *legitimate* holder's own copy is refreshed past it or 30 days pass without a refresh.
An **expired** stolen token under the current design is NOT bounded: `allow_expired` never checks
`exp` at all, so a token exfiltrated once (old backup, leaked log despite scrubbing, disposed
device) can be replayed against `/v1/auth/anon` indefinitely, forever, minting a fresh valid
current-format token every time, with zero time pressure on the attacker. That materially
defeats one of CR125's two stated purposes ("closes the Low/Info 'tokens never expire' item") for
exactly the leak vector TTL exists to bound. Recommend the bounded grace window the architect
already floated (e.g. `exp + 180 days`) rather than fully open-ended `allow_expired`.

## MINOR

`allow_expired=True` / `get_rebootstrap_identity_optional` has exactly one caller today, verified
by grep, but nothing structural stops a second one appearing under future refactors. A cheap pin
(assert-by-grep or an explicit route-allowlist check) would catch that early — architect explicitly
asked whether this needs a guard; recommend yes, low cost.

## NEEDS-DEVICE-CHECK (carried from the architect's own declaration, not independently verifiable
from this Mac)

- Old build re-auth on a real iPhone (moot until the BLOCKER above is fixed — a device run today
  would visibly reproduce the same orphaning).
- Keychain plist no longer holding the token post-migration.
- iOS Keychain accessibility class (`first_unlock_this_device`) behaving as documented on-device.

## Confirmed correct (independent verification, not the architect's word)

- `DELETE /v1/auth/session` bumps `token_version` and kills every outstanding token for that user,
  not just the presented one (§ two-device repro above).
- `_scaffold_sig` HMACs all three of `hex_id|exp|ver` jointly — a single-field hand-edit (tested:
  `ver`) breaks verification everywhere, including on `/v1/auth/anon`.
- `android:allowBackup="false"` + `fullBackupContent="false"` present on `<application>`.
- iOS: `KeychainAccessibility.first_unlock_this_device` set in `device_user.dart`'s
  `FlutterSecureStorage` config (static-only check, per NEEDS-DEVICE-CHECK above for behaviour).
- Migration `2851822570ac`: `token_version` `NOT NULL DEFAULT 1`, matches `User.token_version`
  model default; chain intact, single head, independently re-derived.
- `test_config_compose_parity.py` passes structurally with `AUTH_TOKEN_TTL_DAYS` present in both
  `config.py` and `docker-compose.yml`'s `api-alpha` block.
