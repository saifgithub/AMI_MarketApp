# CR082 — Tester / user contact export for engagement comms

**Filed:** 2026-07-24 (AT:R64) · **Status:** in_progress
**Requester:** Saiful — *"be able to communicate with them via e-mail or via WhatsApp to keep them engaged."*

> Register row is Architect-owned (CR081). This folder + `orchestration/dispatch/intake/store-contacts-export.md` are the disjoint paths this track owns; the Architect transcribes the `cr_list.md` row and reconciles the final ID.

## Why

Testers are spread across TestFlight, the Play internal track, and the app's own user table, with no single contactable list. Saiful wants one, re-pullable before each outreach, to keep testers engaged.

## What's obtainable (investigation, R64)

| Source | Emails? | How |
|---|---|---|
| **App DB (alpha)** | ✅ the real engagement list | `scripts/users.sh` transport; `users.email` + `plan` + activity |
| **TestFlight (iOS)** | ✅ | App Store Connect API `/v1/betaTesters`; existing `.p8` key |
| **Play internal (Android)** | ❌ not programmatically | Play API `edits.testers` exposes **Google Groups only**; Console CSV export is for account-users, not testers |

**Two hard limits, stated plainly:**
- **No WhatsApp data source.** Neither store exposes phone numbers; `User` has no phone column. WhatsApp can only use numbers Saiful already holds — this CR can't produce them. Email is the only channel it fills.
- **Anonymous-first ⇒ most rows `email IS NULL`.** The contactable set is *claimed* accounts (5 today), far below total real users (65). The tool prints both so the gap is loud.

## Scope (shipped)

- **`scripts/users.sh --contacts [N]`** — CSV of contactable real users to stdout (summary to stderr): `email, display_name, platform, plan, created, claimed, last_app_version, rooms_convened, last_activity`. Applies the standing synthetic/seed exclusion (`REAL_PRED`, byte-identical to `scripts/analytics/daily_report.py` + `memory/feedback_user_report_exclusions.md`) so fake accounts never reach outreach. Platform derived from `device_model`/`os_version`; `rooms_convened` is the engagement signal (segment "signed up, never convened").
- **`scripts/testflight_testers.py`** — App Store Connect ES256 JWT (reuses `build_testflight.sh` key id/issuer defaults), pages `/v1/betaTesters`, CSV `email, first_name, last_name, invite_type, groups`. **Fails loudly** if the `.p8` is missing (CR040) instead of emitting empty CSV. No new dependency — `PyJWT` + `cryptography` already in `backend/.venv` and system python3; HTTP via stdlib `urllib`.
- **`scripts/contacts_export.sh`** — runs both, dedupes on lowercased email, tags `source = app_db | testflight | both`, writes `contacts_<date>.csv` (gitignored, personal data). A TestFlight failure warns loudly but still emits the app-DB list.
- **`.gitignore`** — `contacts_*.csv`.

## Android — documented, not automated

No script possible for email-list testers. Read the current list in **Play Console → Internal testing → Testers**. **Recommendation (Saiful's call):** point the internal track at a **Google Group** (e.g. `ami-trade-testers@googlegroups.com`) — then a tester add/remove is a group edit (no Console release edit) and the roster becomes API-readable, closing this gap permanently.

## Privacy note

These people opted into a **test**, not a marketing list. Product/build-update mail is a reasonable read of that consent; broad promo is not — Saiful's explicit call. Exported CSVs are personal data and stay out of git.

## Acceptance

- [x] `users.sh --contacts` → contactable count matches dashboard `with_email`; 23 synthetic/seed rows absent.
- [x] `testflight_testers.py` → matches the App Store Connect group (5 in "AMITRADE"); fails loudly without the key.
- [x] `contacts_export.sh` → clean CSV, no duplicate emails, `source` correct (verified: `saifulsaid@me.com` = `both`); output gitignored.
- [ ] Open (Saiful, non-blocking): switch Play internal track to a Google Group so Android becomes scriptable.
