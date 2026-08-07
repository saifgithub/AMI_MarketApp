# Run report — 2026-08-07_run-13

Item: **CR125**, round 2. Architect SHA `92d3bd23` (on `main`). Verdict: **COMPLETE (round 2)**
— 0 BLOCKER, 0 MAJOR, 2 MINOR (both non-blocking).
Full findings appended as an ADDENDUM to `orchestration/audit/cr/CR125.auditor.md`.

## Setup (DEF159)

```
git worktree add /private/tmp/.../scratchpad/audit_cr125_r2 92d3bd23
```

Declared-file drift `92d3bd23` → `main` (`ff12a3f8` at audit time): only `ff12a3f8`
(CR095 audit round-3 submission, "no source delta" per its own message) landed on top —
confirmed no CR125-relevant files touched.

Diffed `a0f122f0..92d3bd23` in full (30 files, `git diff --stat`) and separated CR125's own
changes from concurrent unrelated CR095/CR121 work that also landed on `main` in between:
CR125-relevant = `backend/app/api/dependencies.py`, `backend/app/core/config.py`,
`backend/app/services/auth_service.py`, `backend/tests/unit/test_cr125_secure_session.py`,
`backend/tests/unit/test_cr125_rebootstrap_flags_have_one_caller.py` (new),
`backend/tests/unit/test_def141_audit_pins_are_collected.py`, `docker-compose.yml`,
`mobile/lib/services/api/api_client.dart` (the `_notifyIfUnauthorized` hunk only —
`_VersionGateInterceptor`/`onUpgradeRequired` in the same file is CR121, verified separately),
`mobile/lib/state/auth_providers.dart`. Everything else in the 30-file diff (CR095/CR121 lane
files, `version_gate_providers.dart`, `main.py`'s `Query(ge=0)`) is unrelated, independently
attributed to other lanes' commits, not re-audited here.

## Regression suite (independent, scratch worktree, absolute interpreter)

```
cd audit_cr125_r2/backend
"/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python" -m pytest tests/unit/ -q
2702 passed, 13 warnings in 339.72s
```
Matches the architect's clean per-SHA figure (`2702`) exactly — re-derived, not copied. (The
architect's own submission flags that their FIRST figure, 2705, was contaminated by another
track's uncommitted CR139 work in the shared checkout — exactly the DEF159 trap; their corrected
number is the one that matches here.)

Targeted CR125 test files, standalone, for fast iteration during the adversarial pass:
```
pytest tests/unit/test_cr125_secure_session.py tests/unit/test_cr125_rebootstrap_flags_have_one_caller.py \
       tests/unit/test_auth_dependency.py tests/unit/test_config_compose_parity.py \
       tests/unit/test_def141_audit_pins_are_collected.py -q
44 passed
```

```
cd audit_cr125_r2/mobile && flutter pub get && flutter analyze --no-fatal-infos
6 issues found (all pre-existing, same set as round 1)
flutter test
00:30 +534: All tests passed!
```
`534` matches the architect's claim. Note: none of the 9-test delta over round 1's `525` is
CR125-round-2 coverage — `git diff --stat` confirms the only mobile test file touched between
`a0f122f0` and `92d3bd23` is `version_gate_raise_from_server_test.dart` (CR121, unrelated). The
actual round-2 mobile fixes (`auth_providers.dart`'s `_handleUnauthorized`,
`api_client.dart`'s `_notifyIfUnauthorized` wired into 3 SSE streams) ship with **zero** dedicated
mobile test coverage. Verified both by direct code trace AND my own throwaway test (below) rather
than accepting that gap as "probably fine."

## Item 1 — re-ran `repro_format_migration.py` logic against `92d3bd23`: user_id survives now

```
minted user: bcd01e9a-... is_new: True
old-format token: scaffold:bcd01e9a...:4ca09a8f...
POST /v1/auth/anon  device_user_id=<same>  Bearer=<pre-CR125-shaped token for it>
status: 200
returned user id: bcd01e9a-...  is_new: False
SAME USER? True                                          <-- was False in round 1, now fixed
```

Widening check — can a legacy token do anything beyond that one ownership decision?
```
legacy token on GET /v1/mandate/<uid>       -> 401   (still refused everywhere else)
legacy token on GET /v1/auth/me             -> 401
forged legacy token (garbage sig) for a
  victim user_id on /v1/auth/anon           -> 200, returned_id != victim (does not prove ownership)
```
Confined exactly as claimed: ownership-proof on one route, never a credential.

One property worth stating rather than treating as new: a **legacy** token for a user who has
since signed out under the new scheme (`token_version` bumped) still resurrects on
`/v1/auth/anon`, because legacy tokens carry no version field and `_version_matches` treats
`token_version=None` as "skip." Confirmed by direct repro. This is not a round-2 regression — the
architect's own docstring states it explicitly ("a legacy token carries no version field, so it
cannot be revoked... not a regression, nothing could revoke it before CR125 either") — and it is
bounded by the same wall-clock cutoff as the rest of the legacy-acceptance path. Recorded as
confirmed-as-designed, not a finding.

## Item 2 — the two new bounds, attacked at every edge named

`AUTH_LEGACY_REBOOTSTRAP_UNTIL` (date, string-typed):
```
empty string        -> refused (does not prove ownership)
whitespace only      -> refused
malformed garbage     -> refused, logs auth_legacy_rebootstrap_until_unparseable
malformed near-date (2027-13-45) -> refused, logs the same
past date (yesterday) -> refused
today (boundary, <=)  -> ACCEPTED  (inclusive boundary, matches `<=` in the code, correct)
far future             -> accepted
```
Exactly matches the stated intent: every unparseable/expired case refuses, never silently accepts.

`AUTH_REBOOTSTRAP_GRACE_DAYS` (int, unvalidated) — this is where a real gap turned up:
```
default 180, 5-day-dead token          -> accepted (inside grace)
zero grace, 1-day-dead token           -> refused  (0 correctly disables leniency, matches docstring)
negative -10, 5-day-dead (EXPIRED)     -> refused  (expected direction)
negative -10, NOT EXPIRED (ttl +5d)    -> REFUSED  <-- a currently-VALID, non-expired token
                                                        fails the /v1/auth/anon ownership check
huge grace 999999, 400-day-dead        -> accepted (an operator's explicit, documented choice)
```
`_within_rebootstrap_grace` runs unconditionally on every 4-part token, expired or not, and only
behaves as a no-op for `grace >= 0` (`cutoff = exp + grace*86400 >= exp` always holds then, so a
still-valid token's `now <= cutoff` is trivially true). A negative value breaks that invariant:
`cutoff` moves to *before* `exp`, so the function can reject a token that has not actually
expired — contradicting its own docstring ("how long **past** `exp`..."). Bounded to the ownership
decision only (the SAME token still authenticates every ordinary route fine, since
`get_current_user`/`_optional` never call this function) — not a security hole, but a
misconfiguration foot-gun in exactly the same "silently causes the thing this CR exists to
prevent" class DEF038/DEF063 already hit twice. Filed as MINOR: recommend `Field(ge=0)` (or an
explicit clamp+log, matching the discipline already applied to the date field) on
`auth_rebootstrap_grace_days`.

## Item 3 — `_handleUnauthorized` carries the bearer; confirmed by trace, not by a shipped test

Diffed `mobile/lib/state/auth_providers.dart`: the two lines that used to wipe the token
(`apiClientProvider.setToken(null)`, `DeviceUser.clearTokenOnly()`) before `bootstrap()` are
gone. `bootstrap()`'s own `DeviceUser.getToken()` read is now the FIRST thing that happens on
recovery, so the dying bearer is what the recovery `POST /v1/auth/anon` carries — matching a
normal cold-start bootstrap exactly. No shipped test (backend or mobile) exercises this path
end-to-end; the backend's `test_a_pre_cr125_token_still_proves_ownership_on_anon` and
`test_an_expired_token_inside_the_grace_window_still_proves_ownership` cover the SERVER side of
what this mobile fix now correctly triggers, which is adequate — the mobile half is a
2-line deletion whose correctness is fully determined by "does `bootstrap()` still read the
token before clearing it," visibly yes by inspection.

Loop check: `_lastUnauthorizedToken`'s retry-guard (unchanged, round 1) still prevents the SAME
token from firing `onUnauthorized` twice — the fix doesn't touch that guard, so no new loop risk.
A genuinely revoked token: the recovery POST carries it, the server's `token_version` check
correctly refuses it (confirmed in Item 1's repro-4 equivalent — a signed-out token cannot
resurrect regardless of the legacy/grace leniency), so the client ends up with a **fresh, clean
identity** returned by the same `/v1/auth/anon` call — not a loop, one clean re-bootstrap.

## Item 4 — SSE 401-only wiring: independently proven with a throwaway test, not just read

`_notifyIfUnauthorized(statusCode)` guards on `== 401` internally; `streamRoom` still checks 402
and `>=500` BEFORE falling through to the `!= 200` branch that calls it, so 5xx/402 never reach it
either. Wrote a scratch test (`_auditor_sse_401_repro_test.dart`, injected `http.BaseClient` fake
per the existing DEF114 pattern, NOT part of the submission, deleted after use — not committed
anywhere) directly driving all three streams:
```
streamRoom            401 -> onUnauthorized fires : PASS
streamRoom             403 -> does NOT fire         : PASS
streamRoom             500 -> does NOT fire (ServerUnavailableException precedence) : PASS
streamBriefMessage    401 -> fires                  : PASS
streamBriefMessage     403 -> does NOT fire          : PASS
streamOneOnOneMessage 401 -> fires                  : PASS
streamOneOnOneMessage  403 -> does NOT fire          : PASS
7/7 passed
```

## Item 5 — the flag guard: confirmed evadable, two concrete techniques, matches architect's own disclosure

`test_cr125_rebootstrap_flags_have_one_caller.py`'s AST walk matches `kw.value` as
`isinstance(ast.Constant) and value is True` — a **literal** `True` only. Proved two evasions by
feeding synthetic "attack" source through the pin's own `_truthy_flag_calls()` function:
```python
# Attack 1 — variable indirection
_ALWAYS = True
def sneaky_bypass_via_variable(token):
    return parse_scaffold_token(token, allow_expired=_ALWAYS)
# -> detected offenders: []  (EVADES)

# Attack 2 — dict-splat
def sneaky_bypass_via_splat(token):
    return parse_scaffold_token(token, **{"allow_expired": True})
# -> detected offenders: []  (EVADES)

# Sanity: the direct-literal shape the real code uses IS caught
def somewhere_else(token):
    return parse_scaffold_token(token, allow_expired=True)
# -> detected offenders: [('somewhere_else', 4)]  (correctly caught)
```
Confirms the architect's own disclosed hole is real, not hypothetical, via two independent
techniques. Both require a deliberate second step (introduce an indirection specifically to dodge
the guard) rather than an accidental trigger — matches the architect's own "contrived" framing.
MINOR, same severity as round 1's version of this finding (unchanged — the guard is a real
improvement over nothing, not a false sense of security, since the obvious/accidental shape is
caught). Recommend, not mandate: flag any keyword literally named `allow_expired`/`allow_legacy`
regardless of value-shape (not just literal `True`) outside the sanctioned function — a legitimate
call never needs to pass `False` explicitly (it's the default), so this closes both evasions with
no false-positive cost; `**kwargs` splats into a call whose target resolves to `parse_scaffold_token`
would need one more AST pass (matching `ast.Call.func`) but is a bounded, known technique.

## Confirmed unchanged / not touched by round 2 (spot-checked, not from architect's word)

- `DELETE /v1/auth/session` cross-token revocation — file untouched by round 2 diff; targeted
  suite includes `test_sign_out_*` and all pass.
- HMAC joint-field signing, forged-token rejection on ordinary routes — untouched, all pass.
- `android:allowBackup`, iOS Keychain accessibility, migration chain/single head — untouched files.
- `test_config_compose_parity.py` — 3 passed, both new settings (`AUTH_REBOOTSTRAP_GRACE_DAYS`,
  `AUTH_LEGACY_REBOOTSTRAP_UNTIL`) forwarded in `docker-compose.yml`'s `api-alpha` block, confirmed
  structurally.

## Verdict

0 BLOCKER, 0 MAJOR. 2 MINOR, both non-blocking: (a) `auth_rebootstrap_grace_days` needs a
lower-bound guard (new this round), (b) the flag guard is evadable via non-literal values (carried
forward from round 1's version of the same concern, now mitigated but not fully closed — proven,
not just asserted). **COMPLETE (round 2).**
