# CR063 — In-app delivery of the competition rules + league information

**Status:** proposed · **Raised:** 2026-07-23 (AT:R65) · **Owner:** dev/build team
**Related:** CR004 (release readiness, competition workstream) · CR010 (league API layer) ·
CR011 (league surface) · CR040 (degrade loudly) · CR064 (legal terms) · CR065 (spec drift) ·
D-060

---

## What / Why

AMI Trade runs a live competition — weekly reputation leagues — and scores every user by it
today. **The product never explains it.**

`mobile/lib/screens/league/league_screen.dart` renders standings, a tier chip, a "rolls in"
countdown, and green/red promotion/relegation tints. That is the entire user-facing
explanation. Specifically, nothing anywhere in the app tells a user:

- how a single point is earned (the `POINTS` table is invisible),
- that there is a **25 points/day cap**,
- what the green/red row tints mean,
- what the tiers are or how you move between them,
- that their leaderboard identity is a pseudonymous handle regenerable only once,
- that **trading P&L never counts** — the single most trust-relevant fact about the design.

Worse, one rule fails **silently**. Once a user hits the daily cap,
`reputation_service.py:179` grants **0 points** and the app shows nothing — the user keeps
playing and keeps earning nothing, with no signal. That is precisely the silent-degradation
class CLAUDE.md's "degrade loudly" rule (CR040) exists to prevent, and it is live today.

This CR makes the competition legible: a native explainer, served from the engine's own
constants, plus loud surfacing of the rules that currently bite in silence.

---

## The rules of the game (code-truth, 2026-07-23)

Authoritative sources: `backend/app/services/reputation_service.py`,
`backend/app/services/league_service.py`, `backend/app/core/config.py`. Values below
verified against the live melehost config (all defaults, no env overrides).

### Scoring (`POINTS`)

| Action | Points |
|---|---|
| Daily challenge attempted | +2 |
| Daily challenge correct | +3 (→ 5 total for a right answer) |
| Lesson passed | +5 |
| Agent unlocked | +10 |
| Room convened to verdict | +3 |
| Disciplined trade | +2 (max **3/day**) |
| Reviewed trade | +3 (max **3/day**) |
| Streak 7 / 30 / 100 days | +10 / +25 / +50 |

### Limits and integrity

- **Global cap: 25 points/day**, measured in the user's own timezone.
- **Per-type daily limit of 3** on the two repeatable trade events (`trade_disciplined`,
  `trade_reviewed`) so they can't be farmed inside the global cap.
- **Ref-based dedup** — re-passing a lesson or re-unlocking an agent scores 0.
- **One attempt per daily challenge** (UNIQUE constraint); a re-attempt returns the stored
  result rather than accepting a fresh answer.
- **Streak milestones fire once ever**, race-safe.

### Streaks

Consecutive days with *any* activity in the user's timezone — daily-challenge attempts,
lesson starts/completions, and journal entries (journal captures room runs, trades, 1-on-1
chats and briefs). Milestones at 7/30/100 days additionally grant **credits: 5 / 25 / 100**.

### Weekly league

- Resets **Monday 00:00 UTC**.
- Cohorts of **≤30**, assembled from users active in the prior 7 days, grouped by tier and
  randomly shuffled.
- Ranked by points earned **that week only** — lifetime totals carry nothing, so a newcomer
  can win their first week. Ties broken by earlier join.
- **Top 5 promote, bottom 5 relegate.** Relegation applies **only when the cohort has ≥10
  members** (`MIN_COHORT_FOR_RELEGATION`).
- Ladder: **Apprentice → Analyst → Trader → Senior → Floor Veteran** — cosmetic/badge only,
  **no functional gating**. Never competed → Apprentice.

### Identity

Pseudonymous `Adjective Noun` handle (e.g. "Cobalt Falcon") minted on first league contact,
regenerable **exactly once ever**. Real name displayed only where the user opted in
(`users.show_display_name`).

### Eligibility

`LEAGUE_ELIGIBLE_PLANS` is empty ⇒ **all plans compete, including free Floor Pass.**

### The hard rule

**Zero P&L, anywhere.** No points derive from trading profit or loss, by design
(D-060 + the store age-rating declaration in `store_compliance.md`).

---

## Scope

### 1. Backend — serve the rules from the engine, never a hardcoded copy

New `GET /v1/league/rules` in `backend/app/api/league.py`, built by reflecting the **live**
constants:

| Source | Constants |
|---|---|
| `reputation_service.py` | `POINTS`, `PER_TYPE_DAILY_LIMIT`, `STREAK_MILESTONES`, `STREAK_CREDITS` |
| `league_service.py` | `TIERS`, `MIN_COHORT_FOR_RELEGATION` |
| `config.py` settings | `reputation_daily_cap`, `league_cohort_size`, `league_promote_count`, `league_relegate_count`, `league_eligible_plans` |

**This is the load-bearing design decision.** A hand-written rules table in Dart would
silently lie the first time any constant is tuned — the same failure shape as CR038's
"prompt instructions are not controls": if it must hold, make it structural. The client
renders whatever the engine reports; drift becomes impossible rather than merely discouraged.

Also extend `GET /v1/league/me` with **`points_today`** and **`daily_cap`** so the client can
show the cap at the moment it bites.

Auth: same `get_current_user` dependency as the existing league routes. The rules payload is
non-personal and identical for every user — safe to cache.

### 2. Flutter — native explainer

New `mobile/lib/screens/league/league_rules_screen.dart`, driven entirely by the rules
endpoint. Sections:

1. **How points are earned** — table rendered from the API response (never a local literal).
2. **Limits** — the daily cap, the per-type limits, and the dedup rule in plain language.
3. **The week** — reset at Monday 00:00 UTC shown *in the user's local time*, cohort size,
   promotion/relegation bands, and the ≥10-member relegation condition.
4. **The ladder** — the five tiers and what moving between them does (and does not) change.
5. **Your identity** — handle pseudonymity, the single regeneration, the opt-in real name.
6. **P&L never counts** — a trust panel stating the competition scores process, not profit.
7. **Footer** — link out to the hosted Competition Rules (CR064).

**Reuse, do not rebuild:**

- `mobile/lib/screens/league/league_common.dart` — `leagueTierLabel`, `leagueTierColor`,
  `leagueRollsIn`
- `mobile/lib/widgets/hex/hex_chip.dart`, `hex_avatar.dart`, and `HexToast`
- `mobile/lib/screens/settings/legal_screen.dart` — the existing WebView shell for the
  outbound legal link

**Entry points:** ⓘ action in the `LeagueScreen` AppBar beside the existing history icon ·
`mobile/lib/widgets/streak_chip.dart` · `mobile/lib/screens/floor/daily_challenge_card.dart`
· Settings → Help. Plus a **one-time first-contact sheet** shown on first league assignment
(seen-flag pattern from `mobile/lib/state/onboarding_providers.dart`; must survive
anonymous-first, so prefer a server-side or `device_user_id`-stable flag over a bare
shared_prefs bool that a reinstall clears).

### 3. Degrade-loudly fixes (real defects this CR closes)

| # | Defect today | Required behaviour |
|---|---|---|
| 1 | Daily cap silently awards 0 points | Show `25/25 points today — cap reached`, with when it resets |
| 2 | Green/red standings tints are undocumented colour | Add a promotion/relegation legend to the standings |
| 3 | `leagueUnassigned` empty state explains nothing | State how to get in: earn any points; cohorts assemble Monday from users active in the prior 7 days |

### 4. i18n

Every new string through `AppLocalizations` with a context comment for the translator. EN
ships now; AR/MS follow (translation is not blocking, per CLAUDE.md).

---

## Out of scope

- Changing any scoring value, cap, tier, or league mechanic. **This CR explains the rules;
  it does not alter them.** Any tuning is a separate CR.
- The legal terms themselves — CR064.
- Building the unimplemented spec items (365-day milestone, lifetime tiers, badges, streak
  freezes, reminder push) — logged in CR065.
- Push/email notification of league results (no push infrastructure exists — CR043).

---

## Acceptance

1. `GET /v1/league/rules` returns the live scoring table, caps, limits, tiers, cohort size,
   promote/relegate counts and eligibility, matching `POINTS` and settings exactly.
2. `GET /v1/league/me` includes `points_today` and `daily_cap`.
3. The rules screen renders every section above and is reachable from all four entry points.
4. A user at the cap sees an explicit cap message instead of silent zero-point awards.
5. The standings legend explains both tints; the unassigned empty state explains entry.
6. **No-drift proof:** changing `REPUTATION_DAILY_CAP` in `docker-compose.yml` and
   recreating `api-alpha` changes the number rendered in the app, with no client change.
7. All strings localized through `AppLocalizations`; no user-facing literal says "the AI"
   (it is **AMI** by name).
8. `pytest backend/tests/unit/ -q` green. If a new env var is introduced, extend
   `backend/tests/unit/test_config_compose_parity.py` and forward it in the compose
   `api-alpha` block (CR040 gate).

---

## Verification

- `curl -s https://api-alpha.agenticmarketintel.ai/v1/league/rules` — compare against
  `POINTS` in source.
- Flip `REPUTATION_DAILY_CAP`, `docker compose up -d --force-recreate api-alpha`, confirm the
  app's rules screen moves with it (this is the test that proves the no-drift design).
- Device run, release build per house rule (`flutter build ios --release` + `flutter install`):
  League → ⓘ renders; cap message appears for a capped user; legal link opens in `LegalScreen`.
- Backend unit tests on the Mac (sqlite tempfile fixture).
