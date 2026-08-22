# CR203 — Track which users have a linked Alpaca account

**Filed:** 2026-08-22 · **Track:** AT:R74 · **Status:** in_progress

## What

`users.alpaca_linked_at` — a nullable timestamp recording that a user's device
reported holding an Alpaca paper credential. NULL = not linked. The device
reports on link and on unlink via `POST /v1/alpaca/link_state`. The admin
analytics summary gains an `alpaca_linked` count.

## Why

CR202 moved the credential to the device, which was the point — but it also
removed the host's only way to answer *"who has linked an account?"*. Saiful:
*"Can we at least track which user has alpaca?"*

That question is answerable without undoing CR202, because **the fact of a link
and the means to use one are different things.** DEF044, DEF181, DEF182 and
DEF185 were all consequences of holding the *credential*: cleartext at rest, a
key leaking into the audit log, a fail-open cipher, a boot path that disabled
that cipher. None of them is reachable from a timestamp.

## Design

**A timestamp, not a boolean.** This host cannot verify the claim — the user can
revoke the key at Alpaca, wipe the app, or change phones and we never hear about
it. `alpaca_linked = true` would assert a present-tense fact we cannot check,
which is the DEF059 class this codebase keeps paying for. Storing *when it was
last said* means every reader can see how old the claim is, and repeat reports
refresh it so the age stays meaningful.

**Under-report rather than over-report.** A device that never calls simply reads
as not linked. The count is a floor, not a census, and is documented as one at
both the column and the admin field.

**Unlink wipes locally first.** `_disconnect` clears the Keychain before it
reports, and the report failing is swallowed. So the worst case is the backend
briefly over-reporting a link that no longer exists — never a credential
surviving on the device after the user asked for it gone.

**Why not telemetry events.** `persona_telemetry` already ingests per-user
events and would need no schema change, but it is an event log with a 400-day
retention sweep. "Who is linked *now*" would mean reconstructing state from the
last `linked`/`unlinked` pair per user, and going wrong quietly once rows age
out. State belongs in a column.

## The CR202 guard was amended, deliberately

`test_cr202_no_host_side_credentials.py` pinned `alpaca_linked_at` by name among
the columns that must stay gone. That was over-stated: it is a timestamp, and it
only appeared in that list because CR202 dropped it in the same block as the two
secrets beside it. The three credential columns stay pinned by name, and the
generic credential-shaped-column guard is untouched — a secret returning under a
new name still fails the build.

## Acceptance

- Reporting `linked: true` stamps a time; `false` clears it; repeats refresh it.
- Anonymous users are rejected; one user cannot report for another (the body has
  nowhere to name a user — asserted, not assumed).
- Key material posted alongside the flag is stored nowhere on `User`.
- The three credential columns remain absent.
- `pytest backend/tests/unit/ -q` green; `flutter analyze` exit 0.
