# CR278 — Beta build settings, report-this-response and Room thumbs

**What:** Four Beta-only controls for the external test, child of CR267 (work package WP-36): an English-only build define, a free-credits backend setting, a "Report this response" action on AMI's answers, and a thumbs rating after each Room.

**Why:** D-076 defines Beta as English only with credits free. Neither switch existed (a grep found no `locale lock` or `free credits` anywhere). The exit report (WP-53) needs two signals from testers that a bug report alone does not give: "this answer was wrong" tied to a Room and a log line, and "did the verdict and its reasons make sense" for every Room.

**Status:** built on branch `lane/WP36-beta-settings`; backend, mobile, UAT cases done. A build made with the Beta define and the device cases are for the rig.

## 1. English-only Beta builds

- `--dart-define=AMI_BETA=true` (also `1`, `yes`, `on`). Read as a flexible truthy string, not `bool.fromEnvironment`, which reads `AMI_BETA=1` as false without saying so (`features/beta/beta_build.dart`).
- With it, `LocaleNotifier(englishOnly: true)` starts at `en`, ignores `setLocale`, and never reads an Arabic or Malay override stored by an earlier build. Settings drops the whole LANGUAGE section. Content endpoints already follow the locale provider, so they ask for `en`.
- Default builds are unchanged: no define means all three locales and the switch.
- **Where the define goes (not done here; publishing was out of scope).** Both store pipelines pass their dart-defines in one `flutter build` call:
  1. `scripts/build_testflight.sh` — add `--dart-define=AMI_BETA=true \` beside `--dart-define=AMI_GAMES=...` (about line 530, in the `flutter build ios --release` call).
  2. `scripts/build_playstore.sh` — the same line beside `--dart-define=AMI_GAMES=...` (about line 462, in the `flutter build appbundle --release` call). `publish_playstore.sh` calls `build_playstore.sh`, so it needs nothing of its own.
  3. The right shape is a `--beta` flag in each script that sets the define (the way `DO_GAMES` sets `AMI_GAMES`), so a store build cannot ship the define by accident; this is left for the WP-45 / WP-49 build work, which owns those scripts.

## 2. Free credits

- Setting `BETA_FREE_CREDITS` (`settings.beta_free_credits`), default `false`. Forwarded in `docker-compose.yml`'s `api-alpha` block (`test_config_compose_parity.py` enforces it). Logged once at boot as `beta_free_credits_on` (warning level) when on.
- The one switch is `credit_service.spend()`: when on it returns `(balance, 0)` without debiting or writing a ledger row. `spend()` is the single debit for Room, 1-on-1 and Brief, so on means **all three** are free (D-076 says "credits free", not "Rooms free"). A Room still runs and records `credit_cost=0`; the 402 wall is unreachable.
- Two places predict a charge and ask the same helper (`credits_are_free()`): the live-data entitlement probe in `room_runner` (otherwise a user at 0 credits would be denied live news and social data on a free Room) and the mandate read's `room_cost` (so the Convene sheet says "Room: 0 credits" and the existing `insufficient` styling never fires).
- The paywall remains the information card: nothing changes in the paywall widgets; they are simply never reached because no debit fails.
- Allowance re-grants (`_ensure_period`) still run in free mode, so flipping the setting off later finds balances as they would have been.

## 3. Report this response

- It is the existing bug sheet and `POST /v1/feedback/bug`; no second endpoint. `showBugReportSheet(..., response: ResponseReportTarget)` pre-fills category `wrong_data` and the title "Problem with a response from <desk>", shows a caption naming the desk, and sends the response's `route`:

      response:<surface>:<run id or ->:<agent id>[:t<turn>]

  `surface` is `room`, `verdict`, `concierge` or `oneOnOne`. The recent trace ids go along as for every report (`TraceIdStore.recentIds()`, CR239). The admin bug detail already returns `route` and `trace_ids`, so no backend change was needed.
- Entry points: long-press a Room desk row (transcript view) or the verdict card, then "Report this response"; a visible "Report this response" in the desk peek sheet (board view); the same link on the thumbs card for the verdict; long-press a Concierge, 1-on-1 or Brief reply (never the user's own message, never a reply still streaming). The Journal replay is unchanged.

## 4. Room thumbs

- Table `room_ratings` (migration `cr278a0b0c0d1`, chained on `m276a0cr239x276`): `id`, `room_run_id` (FK to `room_runs`, `ON DELETE CASCADE`, UNIQUE), `helpful`, `created_at`, `updated_at`. No user column: the owner is the Room's owner, so ownership has one source of truth, an account merge needs no re-key, and erasure needs no rule (no free text; the row goes with its Room on Postgres via the cascade).
- `POST /v1/room/{run_id}/rating` body `{"helpful": true|false}` (strict bool, no extra fields). Owner only (403 otherwise, 404 unknown run), one row per Room, changeable (`changed` in the response says whether this call replaced a different answer). A Room with no verdict yet is 409.
- `GET /v1/admin/room-ratings?limit=&since=`: admin gated like every admin route; totals (`ratings`, `helpful`, `not_helpful`, `helpful_pct`) plus the newest ratings with ticker and verdict action. This is the read for the WP-53 exit report.
- App: a dismissible card under the verdict and cost line, "Did the verdict and its reasons make sense?" with a thumbs-up and a thumbs-down. It is a plain child of the scrolling column; nothing waits on it. A failed save is a quiet line and the thumbs stay tappable. Dismissal and the answer hold for the app session.

## Tests

1. Backend: `test_cr278_beta_free_credits.py` (on/off, no debit, Room runs and records `credit_cost=0`, off records the real charge, mandate `room_cost`), `test_cr278_room_rating.py` (owner, upsert, owner-only, 404/409/422, admin read, report payload through the existing bug endpoint, migration chain), plus `test_config_compose_parity.py`.
2. Mobile: `cr278_beta_locale_lock_test.dart` (lock, no stored override, default unchanged, Settings with and without the switch), `cr278_room_feedback_test.dart` (thumbs post, change, fail quietly, dismiss; report sheet pre-filled and sent with route and trace ids; long-press on a row and on chat bubbles), `cr278_room_rating_placement_test.dart` (card on the Room screen only for a finished Room with a verdict and a run id).
3. UAT (`qa/uat/cases`): ROOM-025 (rating, API), ROOM-026 (free vs paid price agrees with behaviour, API), SUPP-015 (response report through the bug endpoint, API), ROOM-027 / SUPP-016 / MAND-039 (device, blocked until the rig script and a Beta-define build exist).

## Not done

1. The build scripts are untouched (see the note above).
2. The account export (CR276) does not list ratings; they have no user column and no free text.
3. The Appium scripts for the three device cases.
