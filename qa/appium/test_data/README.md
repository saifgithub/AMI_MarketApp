# Test data / credentials

## Phase 1 — none needed

Every Phase 1 test in `tests/` reuses (or, for the smoke gate, doesn't care about)
a plain **anonymous** guest session — AMI Trade is anonymous-first, so no
account/credentials are required to reach the 5 bottom-nav tabs, the Convene
sheet, the trade ticket sheet, or the bug-report sheet. `noReset=True` (the
harness default, see `config/capabilities.py`) reuses whatever session is
already on the device; a test that needs a guaranteed-cold anonymous session
calls `helpers.device.pm_clear()` explicitly first.

**Tagging the synthetic account**: whatever anonymous session this harness's
runs create in Alpa's `users` table should get tagged the same way CR035's
room-benchmark rows are (see the `feedback_user_report_exclusions` memory) so
it can be added to the existing real-user exclusion filter. The exact
distinguishing trait (a `last_app_version`/`device_model` value, most likely
`SM_A176B` combined with a recognizable pattern) gets nailed down once a real
run lands a row and we see what it actually writes — don't guess at the SQL
ahead of that.

## Phase 2 — needs real credentials, not fabricated here

Two Phase 2 flows need credentials this harness cannot generate on its own.
Both are stubbed out with `@pytest.mark.skip` in `tests/test_settings.py`
until Saiful supplies them:

1. **Sign-in / account-merge testing** (`screens/auth/sign_in_screen.dart`,
   `screens/auth/merge_sheet.dart`) — federated one-tap sign-in isn't
   reliably automatable via Appium (OAuth browser hand-off), so Phase 2 tests
   the demoted **email-code** path instead. That needs a dedicated test-email
   inbox Appium (or a small script alongside it) can read the code from.
   **Needed from Saiful:** a test email address + a way to read the code that
   lands in it (an app password for IMAP, or a webhook/inbox API).
2. **Alpaca-connect testing** (`screens/settings/alpaca_connect_screen.dart`)
   — needs a real Alpaca **paper-trading** API key/secret (never live-trading
   keys — this app is simulation-only and should never hold real-money
   credentials). **Needed from Saiful:** an Alpaca paper-trading key/secret
   pair, scoped to paper only.

## Where credentials live

Real values go in `test_data/.env` **on melehost only** — created by hand
after the rsync, never committed to git, never written into
`hermes_folder/reports/`. `test_data/.env.example` (committed, this
directory) documents the shape with placeholder values:

```bash
cp test_data/.env.example test_data/.env   # on melehost, after rsync
# then fill in the real values by hand
```

`conftest.py` does not currently load `.env` automatically — Phase 2's
sign-in/Alpaca tests will add that once the credentials above actually exist.
