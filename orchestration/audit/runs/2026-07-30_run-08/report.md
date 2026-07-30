# Audit run report — 2026-07-30 run-08

ITEM: SEC-BATCH1 · ROUND: 1 · VERDICT: AWAITING_FIXES (1 MAJOR)
LANE: `lane/SEC-BATCH1.coder.api` @ `9c8caccd` (rebased onto e961dfd1) ·
SCOPE: none stated → audited as `cr`
AUDITOR: track U (Kimi) · worktree `.claude/worktrees/audit-SEC-BATCH1`

## Scope

8 security defects from `docs/governance/security_review_2026-07-29.md`
(umbrella CR123): DEF176, DEF177 (both live-proven Criticals), DEF180,
DEF181, DEF183 (partial, disclosed), DEF184, DEF185, DEF186 (partial,
disclosed). 12 backend files + docker-compose.yml, +376/−59 at rebase
point; 8 new test files, 4 touched.

## The one MAJOR

**M1 — `test_def183_oidc_blocking_dos.py:57-59` leaks
`auth_service._service`** (sets a fake accept-anything verifier, never
restores; conftest resets five other service singletons, not this one).
Proven: `def183 → test_auth_phase1_5::test_apple_endpoint_rejects_unverifiable_token`
in one invocation → fake 200 where 400 asserted, test fails. Reverse
order passes. Full suite green only via alphabetical ordering luck
(`test_auth_…` < `test_def183_…`). False-PASS failure mode for any
future auth test sorting after the polluter. Fix: restore the singleton
(yield-fixture pattern from `test_def176._swap_verifiers`).

## Independent verifications beyond the diff read

- Mobile grep re-run (bridge's explicit request): zero Dart callers of
  `/v1/llm` under `mobile/lib` outside `l10n/README.md`. Gating the LLM
  router breaks no shipped client.
- DEF176 caller census: `sign_in_with_apple/google` called only from the
  two routes; no third untrusted-body caller. No `extra="forbid"`
  anywhere in `schemas/auth.py` — old-client `user_id` silently dropped.
- DEF180 SQL read directly: `challenge_owner_id` condition genuinely
  appended to the active-challenge query.
- DEF185 promotion path: `infra/alpha.env` carries `AMI_ENV` (key
  confirmed, value not read); promote runbook greps it on melehost
  post-ship. Compose `:?` will resolve, not break, next promotion.
- `get_admin`: `hmac.compare_digest` + 503-on-unset (fails loud).

## Blind mutation (auditor's own)

Removed the `conditions.append(AuthChallengeRow.user_id ==
challenge_owner_id)` line in `auth_service.py` → exactly 1 RED
(`test_verify_cannot_guess_against_another_users_challenge`); 3 others
correctly green. Reverted byte-identical, re-green 4/4.

## Measurements (all reproduced from the worktree)

| Check | Builder | Auditor | Result |
|---|---|---|---|
| Full suite | 1702 + 3 pre-existing failures (pre-rebase) | 1719 passed, 0 failed (246s) | rebase absorbed the 3 |
| Targeted (8 new + 4 touched) | — | 89 passed + M1 pollution failure | mechanism isolated |
| `gen_registers.py verify all` | — | DEF 199 / CR 128 OK | clean |

## Judgment calls invited by the bridge — all upheld

- DEF181 regex excluding bare `code` (OTP codes travel only on
  whole-body-scrubbed routes; matching `code` would redact status_code
  noise out of every audit row).
- DEF184 `MAX_TRACKED_KEYS = 50_000` (low single-digit MB worst case;
  alpha traffic).
- DEF186 rate-limits-not-credit-metering (metering is a ledger feature,
  wrong shape for a security patch; 12/min bounds the bleed).

## Round 2 scope

M1 fix only: one test file + a deliberate polluted-order run going
green. No re-audit of the eight fixes needed.

DoD enforcement waived per standing instruction.
