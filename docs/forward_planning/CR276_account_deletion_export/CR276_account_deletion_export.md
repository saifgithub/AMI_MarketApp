# CR276 — Account deletion and data export

**What:** In-app account deletion (Settings → Delete account) with a 30-day restore window and a scheduled post-grace erasure in one of three modes, plus a downloadable export of the user's own data (Settings → Export my data). Child of CR267, work package WP-30.

**Why:** Apple App Store guideline 5.1.1(v) and Google Play both require in-app account deletion that removes the user's personal data. Beta ships `delete`; `archive` (keep the data, block sign-in) stays off until counsel approves it (gate S6).

**Status:** built on branch `lane/WP30-account-deletion`; backend, mobile, legal drafts and UAT cases done. Live and device checks are Saiful's (UAT-AUTH-045/046/047 are manual).

## Beta default: `delete`

Chosen over `anonymise`. Reasons:

1. It is the only claim that is plain to Apple's reviewer, to Play's data-safety form and to a PDPA access request: the user row and every row of personal data are gone, and what survives has no row to link back to.
2. `anonymise` keeps a tombstone user plus per-user trading history under a stable UUID. Whether that counts as anonymous is a legal argument we do not want to have in Beta, and Room transcripts and the CIO context embed the user's mandate and holdings.
3. The Beta exit report (WP-53) uses data gathered while accounts are live. Deletion requests inside a 6–12 week Beta will be few, so losing their de-identified activity costs little.
4. Hard delete removes the apple/google id, so the same identity signs up as a brand-new account. Nothing to reconcile.

`anonymise` stays one config change away if counsel prefers to keep de-identified activity. The cost of choosing `delete`: head-to-head game records naming the user are removed from the opponent's history too (the board code cannot render a duel whose user row is gone).

## How it works

1. **Close** — `POST /v1/account/close` with `{"confirm": true}` (authenticated). One write sets `users.closure_requested_at` and bumps `token_version` (the CR125 revocation counter), so every outstanding token fails its next call, including the caller's. `get_current_user` also refuses a closed row (second lock). `notify()` sends no push to a closed account. Idempotent.
2. **Restore** — there is no restore route, deliberately: the bearer is dead and an unclaimed account has no credential. Restore is the sign-in itself. Apple, Google and magic-link sign-ins call `account_erasure.gate_sign_in` once they know which account the verified identity belongs to, before mutating anything. A match inside the grace window is answered `409 {code: account_pending_deletion, restorable_until}` and nothing changes; the same call repeated with `restore_account: true` clears the closure and signs in to the same account. Past grace (job not yet run) or erased: `403 account_closed`. The app shows a RESTORE dialog between the two calls. A guest (never claimed) account cannot be restored: it has no sign-in, and the confirm dialog says so.
3. **Erase** — `run_erasure_tick` finds accounts whose `closure_requested_at` is older than `ACCOUNT_CLOSURE_GRACE_DAYS` and runs `erase_account` for each. The DB work is one transaction per account; third-party processors (OneSignal, RevenueCat) are asked to forget the user first, and a real processor failure defers the account to the next tick instead of losing the only row that says whose data to forget. A missing processor key is logged at error and does not block forever. One failing account never stops the batch. Each erasure writes an `admin_audit` row (`account_erased_<mode>`, anonymous id and per-table counts, no email).
4. **Export** — `GET /v1/account/export`, authenticated, 5 per hour per user: a JSON download (`Content-Disposition: attachment`, `no-store`). Whitelisted profile fields plus settings, mandates, agent briefs, journal, lesson progress, agent activations, simulated portfolios/holdings/trades/shorts/options, Room runs (verdicts, no transcript or CIO context), verdict outcomes, watchlist, alerts, analyst conversations, daily-challenge attempts, badges and the user's own bug reports. Every query is keyed on the caller. No secrets: Alpaca keys never reach the host (CR202).

## Per-table behaviour

The contract is `RULES` in `backend/app/services/account_erasure.py`; `test_cr276_account_erasure.py` fails if any table with a user-id column is in neither `RULES` nor `NOT_USER_DATA`. `archive` does nothing to any table and only flags the user row.

| Table | `delete` | `anonymise` | Why |
|---|---|---|---|
| users | row deleted | email/phone/apple/google/hms ids, name, handle, device ids and model, reminder hour, Alpaca link time nulled; stamped `erased_at`/`erased_mode` | identity |
| user_devices | deleted | deleted | device-level data |
| mandates, user_overlays, overlay_edit_counts | deleted | deleted | personal financial profile, free-text briefs |
| journal_entries | deleted | deleted | user notes and tags |
| sim_watchlists, price_alerts | deleted | deleted | notes, commentary |
| notifications, notification_preferences, inbox_messages (incl. replies to support), persona_events | deleted | deleted | per-user content and telemetry |
| one_on_one_messages | deleted | deleted | the user's conversations |
| bug_reports | deleted, screenshot file removed | same | free text plus attachment |
| auth_challenges | deleted (by user id and by target email) | same | email + code hash |
| http_audit | deleted | deleted | client IP, request/response bodies |
| llm_audit | prompt, messages and reply blanked, `user_id` NULLed; tokens/cost/latency/model kept | same | LLM spend cap and cost accounting read these |
| room_runs | deleted | transcript and CIO context blanked, verdict and metadata kept | transcript embeds mandate and holdings |
| verdict_outcomes | deleted | kept | ticker/action/return, no free text |
| sim_portfolios, sim_holdings, sim_trades, short/option/resting-order rows, portfolio_value_snapshots, portfolio_nav_daily | deleted | kept | simulated activity, de-identified once the user row is scrubbed |
| lessons_progress, agent_activations, daily_challenge_attempts, reputation_events, league_members, badges, streak_freezes, career_events | deleted | kept | progress counters |
| alpaca_order_audit | deleted | kept | paper-order audit; no credentials (CR202) |
| game_entries, game_queued_orders, game_short_positions | deleted (champion pointer on the field cleared first) | kept | game state |
| game_duels | deleted (also leaves the opponent's history) | kept | names two users |
| game_fields | `owner_user_id` NULLed | same | private field keeps running for others |
| subscription_events | kept, `note` blanked | same | billing ledger, accounting retention |
| revenuecat_events | kept | kept | webhook dedup and accounting trail, no PII |
| admin_audit | untouched | untouched | operator log; may name a user id; permanent by design (CR200) |
| OneSignal, RevenueCat (external) | asked to delete the external id | same | processors |

## Settings (all forwarded in `docker-compose.yml` api-alpha block)

1. `ACCOUNT_ERASURE_MODE` — `delete` (default) | `anonymise` | `archive`.
2. `ACCOUNT_ARCHIVE_COUNSEL_APPROVED` — default `false`. `archive` without it refuses to boot (settings validator), is refused again at run time (`ArchiveNotApproved`, error log `account_erasure_archive_refused`) and the tick reports `refused`.
3. `ACCOUNT_CLOSURE_GRACE_DAYS` — default 30.
4. `ACCOUNT_ERASURE_TICK_INTERVAL_SECONDS` — default 3600.

## Mobile

Settings → Account gains **Export my data** and **Delete account**, for guests and signed-in users. The dialog is the DEF479 `_confirmDestructive` and states what is deleted, what is kept and for how long, and the restore window. The wording reads "Delete account" in Beta and "Close account" only when `GET /v1/account/policy` reports `wording: close` (archive with counsel approval). The sign-in screen shows RESTORE YOUR ACCOUNT? on a 409. New ARB keys in en/ar/ms carry `retranslate:[ar,ms]`; AR/MS are best effort.

## Legal drafts (not published; `website/` untouched)

`legal/policies/terms_of_service.md` §10, `privacy_policy.md` clauses 8A (Singapore hosting, PDPA cross-border transfer), 10 and 12, and `data_deletion_policy.md` §0 and §2 are marked BETA DRAFT with `[LAWYER REVIEW REQUIRED]` on the retention period and the transfer basis.

## Open items

1. Counsel (gate S6): archive-instead-of-delete; the 7-year billing-record period; PDPA cross-border transfer basis and consent wording.
2. The OneSignal erase call (`DELETE api.onesignal.com/apps/{app}/users/by/external_id/{id}`) is written from the vendor's documented user-model API and has not been run live. UAT-AUTH-046 checks the log for `account_erasure_deferred`.
3. Singapore hosting is stated in privacy clause 8A from the Beta plan; confirm once the host exists.
4. Migration `cr276a0b0c0d1` revises `cr273a0b0c0d1`; if another lane lands a migration first, re-chain.
