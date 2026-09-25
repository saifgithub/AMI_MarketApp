<!--
RETRO-SECURITY.architect.md — audit lane. State derives from round numbers here vs
RETRO-SECURITY.auditor.md. GATE: independent. RETROACTIVE — programme CR231, decision D-072
(2026-09-24): six weeks (2026-08-13 -> 09-24) of largely-unaudited work is being brought under
independent audit before external beta opens. This lane covers "security/credits (DEF369-373,
DEF361)" — one of the named-in-the-CR231-doc gaps — plus the adjacent Alpaca-custody chunk
(CR202/CR203/CR224) and DEF328/DEF381/DEF205, which land on the same auth/secret/billing surface
and were bundled into this lane by assignment. The work below was already built AND PROMOTED to
Alpha (tag alpha-2026-09-24-1) before this audit — nothing here was withheld pending a verdict,
unlike the normal build->submit->audit order. This submission is not fixing anything; it is
assembling what the auditor needs to verify work that already shipped.
-->

# RETRO-SECURITY — audit lane (credit/prompt/auth security defects + Alpaca custody chunk)

**SCOPE:** chunk — a set of related items on the auth/secret/billing surface, not one CR's
Definition-of-Done. DoD table not applicable at this grain.

**TIER: A.** Every item here sits on auth, secrets, or credits/billing: a credit-ledger
double-spend, a prompt-injection vector reaching all twelve agents, a farmable credit-reward
route, an OAuth flow with no CSRF nonce, a bot-gate that fails open, a paid API key's exposure
surface, a credential-copying rsync path, and the entire Alpaca on-device-custody redesign
(CR202/CR203/CR224) plus the credit-metering DEF205 built on the same `credit_service.spend()`
DEF369 hardens. Independent audit, rounds uncapped until COMPLETE, per the escalation-tiers
binding (gap-fill 8).

**SHA:** current `main` HEAD — `8c43c88e` (`8c43c88e8e3cb13ffb14abf326bf9be85209614c`).

Per-item commit list (`git log --format='%h %cs %s' --all --grep='<ID>'`):

```
DEF369 (credit_service.spend() double-spend — no row lock):
3d1d66e0 2026-08-25 fix(DEF369,DEF370,DEF371): row-lock the credit spend, sanitise third-party
                    prompt text, delete the farmable journal route (AT:R74 DEF369 DEF370 DEF371)
bd35554c 2026-08-25 docs(CR123,DEF369-373): seven of nine Mediums closed (AT:R74 CR123 DEF369
                    DEF370 DEF371 DEF372 DEF373)

DEF370 (prompt injection via Reddit/news text):
3d1d66e0 2026-08-25 fix(DEF369,DEF370,DEF371) — same commit as DEF369 above
bd35554c 2026-08-25 docs(CR123,DEF369-373) — same commit as DEF369 above

DEF371 (streak->credit farming via the bare journal POST):
3d1d66e0 2026-08-25 fix(DEF369,DEF370,DEF371) — same commit as DEF369 above
bd35554c 2026-08-25 docs(CR123,DEF369-373) — same commit as DEF369 above

DEF372 (website HTML injection + unbounded waitlist):
30a3bc67 2026-08-25 fix(DEF372): escape user text in the operator email; rate-limit and cap the
                    waitlist (AT:R74 DEF372)
bd35554c 2026-08-25 docs(CR123,DEF369-373) — same docs commit as above

DEF373 (Alpaca OAuth missing CSRF nonce + no host allowlist):
53914f99 2026-08-25 fix(DEF373): the Alpaca OAuth flow gets a CSRF nonce and a host allowlist
                    (AT:R74 DEF373)
bd35554c 2026-08-25 docs(CR123,DEF369-373) — same docs commit as above

DEF361 (Turnstile bypass when secret unset):
f406a7d6 2026-08-22 fix(DEF361): Turnstile was bypassed silently under ENV=prod (AT:R74 CR049
                    DEF361 DEF362)
4d5a95b5 2026-08-22 docs(CR049,CR176): DEF361 verified live (AT:R74 CR049 CR176)

DEF328 (paid Gemini key in infra/alpha.env under the wrong name):
c4b7f335 2026-08-17 fix(DEF328,DEF329): a paid key under a name nothing reads, and the guards
                    that could not see it (AT:R70 CR141 DEF328 DEF329)

DEF381 (rsync copying credentials to host; postflight check inheriting the same gap):
4a111596 2026-08-28 fix(DEF381): the promotion rsync shipped the Alpha credentials it exists to
                    withhold (AT:R74 DEF381)
153f912c 2026-08-28 docs(DEF381): downgrade "has been leaking" to "would leak" — the one
                    measurement says otherwise (AT:R74 DEF381)

CR202 (Alpaca credentials moved to device — backend holds none):
e09ea4f2 2026-08-21 feat(CR202): Alpaca credentials live on the device (AT:R74 CR202)
cbd342a7 2026-08-21 docs(CR202): record the verified release in alpha-2026-08-21-3
581c9411 2026-08-22 docs(CR202): correct a REMAINING note that was stale within 74 minutes
5b3c9296 2026-08-22 docs(registers): CR157/CR203/CR202 are done
(069b7db1, 2026-09-22, tagged CR224 not CR202 despite touching the same file — listed under
 CR224 below, not double-counted here)

CR203 (track which users have a linked Alpaca account — timestamp, not credential):
795b960e 2026-08-22 feat(CR203): track which users have a linked Alpaca account (AT:R74 CR203)
5b3c9296 2026-08-22 docs(registers): CR157/CR203/CR202 are done — same commit as CR202 above

CR224 (configurable Alpaca API endpoint, mobile-only):
069b7db1 2026-09-22 feat(mobile): user-editable Alpaca paper-API endpoint (AT:R80 CR224)

DEF205 (credit charging — 1-on-1 and Brief had no spend path):
016815cf 2026-08-24 feat(DEF205): both conversational surfaces charge credits (AT:R74 DEF205)
e426f0b4 2026-08-24 docs(CR204,CR205,CR206,DEF205,DEF368): registers + P18 Dilemma
62cfad5b 2026-07-30 docs(defect): DEF201 update — split DEF205 for credit-metering pricing
                    (AT:R65 DEF201 DEF205)
```

Every ID in the assignment returned at least one commit; none is missing. DEF369/DEF370/DEF371
share one fix commit (`3d1d66e0`) — the assignment's row files confirm this is intentional, not a
miscount: all three were minted from the same security review pass and landed together.

**depends-on:** none. First RETRO-SECURITY submission; `ls orchestration/audit/cr/ | grep -i
retro` shows two sibling retroactive lanes already in flight (`RETRO-PM-FLOOR.architect.md`,
`RETRO-SIM-OPTIONS.architect.md`) — same programme, disjoint scope, no code overlap with this
lane's files.

**Promoted:** yes, `alpha-2026-09-24-1` (per CR231's own sweep: "Alpha: alpha-2026-09-24-1 holds
all backend work; nothing is waiting to promote"). This audit runs AFTER promotion, not before —
the retroactive premise stated in D-072: work shipped without the independent-audit step this
lane now supplies. DEF373 is the one item here that is mobile-only and therefore ships through
TestFlight/Play rather than the rsync path; its row does not claim an Alpha promotion because
there is nothing server-side to promote.

## What and why

This is not a build submission — nothing here changed source in this session. It exists because
CR231/D-072 found that ~175 of the ~200 CR/DEF IDs closed in the 2026-08-13 -> 09-24 window never
had an independent track-U audit, and named "security/credits (DEF369-373, DEF361)" by ID as one
of the gaps. I added DEF328, DEF381, DEF205 and the CR202/CR203/CR224 Alpaca-custody chunk because
they sit on the identical surface (secrets in env files, the rsync that ships them, the credit
ledger DEF369 hardens, and the Alpaca credential-custody redesign DEF373's OAuth flow is a small
corner of) and the assignment listed them alongside the named five.

I did not write this code fresh and am not re-deciding any of it. My job here: locate every
commit, identify the source files and guard tests each added, run those tests plus the full
backend/website/mobile suites myself against the current tree, check whether any live secret
remains in git history, and hand the auditor a map — not a verdict.

## Per-item claims table

| ID | Claim (from the item's own row file) | Commits | Guard tests |
|---|---|---|---|
| DEF369 | `credit_service.spend()` was read-modify-write with no row lock — two concurrent calls reading the same starting balance both pass the check, second write clobbers the first (a user with 1 credit buys 2 Rooms). Latent until DEF205 put 1-on-1 and Brief on the same `spend()` path (both SSE, both 12x/min-reachable, shared concurrency cap >1) — the window became real the same day it was found. Fix: `s.get(User, user_id, with_for_update=True)` (`SELECT … FOR UPDATE`), lock taken BEFORE the balance read. Guard asserts the **compiled Postgres SQL** rather than racing two sessions, because the unit suite runs on SQLite where `FOR UPDATE` is silently a no-op. 1/1 mutation killed. | `3d1d66e0` | `test_def369_spend_takes_a_row_lock.py` (5 tests) |
| DEF370 | Indirect prompt injection: Reddit snippets (`social_context.py:695`) and news headlines (`news_context.py:433,437`) interpolated into agent prompts with only a length cap, no structural sanitisation — a post containing a newline plus the app's own U+2500 box-drawing header glyphs could impersonate a new prompt section. Blast radius bounded (safety floor is deterministic, nothing auto-executes; a compromised analyst misleads an opinion, doesn't open a position) — graded Medium. Fix: one shared `prompt_safety.sanitize_for_prompt`, used by both feeds — strips structure not content (line breaks -> spaces, box-drawing glyphs dropped, whitespace collapsed), cap applied AFTER sanitising so truncation can't leave a boundary fragment. No phrase blocklist (CLAUDE.md: prompt instructions are not controls). 3/4 mutations killed; 4th judged equivalent and the code simplified rather than the test weakened. | `3d1d66e0` (shared with DEF369) | `test_def370_prompt_injection_sanitiser.py` (9 tests) |
| DEF371 | Streak->credit ladder farmable: `POST /v1/journal` accepted an arbitrary entry from any authenticated user, and `reputation_service._activity_days` counted any `JournalEntryRow.created_at` regardless of source — one junk POST/day walked the 7/30/100/365 ladder for 630 credits without doing anything the streak rewards. Two candidate fixes from the review both found NOT to work (an entry-type filter excludes nothing, every `EntryType` value is system-generated; an admin-gate is unsatisfiable because the journal router already requires `get_current_user` on the same header the admin gate reads) — recorded so a future reader doesn't repeat them. Fix: the bare POST route was DELETED outright — confirmed no caller (`api_client.dart` never calls it; internal capture goes through `get_journal_store().append()` in-process, not HTTP). 1/1 mutation killed (restoring the route). | `3d1d66e0` (shared with DEF369) | `test_def371_journal_append_removed.py` (6 tests) |
| DEF372 | Website: M6 — `email_service.notify_team` interpolated user-authored contact-form text raw into HTML email (stored XSS against the operator's own inbox); fixed with `html.escape` per line before the `<br>` join, plain-text part deliberately left unescaped. M7 — `/waitlist` had no rate limit or length caps while every neighbouring form did; added a 10/min limiter (looser than contact's 3/min, no email sent from this route) plus 320-char email / 64-char source caps. M4 (Turnstile fail-open) found ALREADY FIXED by DEF361, verified not re-fixed. 3/3 mutations killed; website suite 43 green. | `30a3bc67` | `test_def372_waitlist_and_email_escaping.py` (6 tests) |
| DEF373 | Alpaca OAuth: no `state`/CSRF nonce — `_handleNavigation` exchanged ANY code arriving on the callback deep link, letting an attacker link the victim's install to the attacker's own Alpaca account. No host allowlist with `JavaScriptMode.unrestricted` — every navigation was allowed, so a redirect off Alpaca could render phishing content inside a WebView the user believes is their broker's login. Fix: `Random.secure()` 32-byte nonce, echoed in `state`, compared BEFORE the code is read, single-use; https-only registrable-domain allowlist (`alpaca.markets` + subdomains) with an unparseable url now defaulting to PREVENT (was previously allowed). 4/4 mutations killed, including the `alpaca.markets.evil.com` suffix trick and an http downgrade on an allowed domain. Client-only — ships on the next store build, not the rsync. | `53914f99` | `mobile/test/screens/settings/def373_alpaca_oauth_test.dart` (8 tests) |
| DEF361 | Turnstile verification returned `True` (bypassed) whenever `TURNSTILE_SECRET` was unset, with no log line — measured true on melehost, where `ami_website_api` had run `ENV: prod` with no secret for two weeks. All three public POSTs (`/contact`, `/data-request`, `/concierge/message` — the last an LLM-backed streaming endpoint) would have accepted every caller as human-verified. Only reason it hadn't mattered: the container is bound to `127.0.0.1:8001` with no CF route, an accident of topology, not a control. Fix: bypass scoped to `env == "local"` only (logs `turnstile_bypassed_local`); any other env with an unset secret logs `turnstile_not_configured` at ERROR and fails CLOSED. Fail-closed case parametrised over `prod`/`staging`/`alpha`/`""` rather than pinning `prod` alone. 6 tests, 3/3 mutations killed. | `f406a7d6` | `website_api/tests/test_def361_turnstile_fails_closed_outside_local.py` (6 tests) |
| DEF328 | A real, paid Gemini key sat in `infra/alpha.env` under `GOOGLE_API_KEY=` — a name nothing in the repo reads (`Settings` declares `google_ai_api_key`, compose forwards `GOOGLE_AI_API_KEY`). CR040's degrade-loudly logged `provider_skipped` correctly but into a container nobody was tailing. Fix: renamed to `GOOGLE_AI_API_KEY=` (gitignored file, nothing to commit) plus a DERIVED guard — a name is legitimate iff it's a `Settings` field or a `${VAR}` compose interpolates; anything else is flagged. Measured pre/post: `['ONESIGNAL_APP_ID_x', 'GOOGLE_API_KEY']` -> `[]`. Verified live: direct curl to Google's endpoint returned HTTP 200 from `gemini-2.5-flash`, and a real stream through the unmodified `OpenAICompatibleProvider` returned text with usage capture populated. Second, unprompted find in the same pass: a dead `ONESIGNAL_APP_ID_x` placeholder, deleted. | `c4b7f335` | `test_def328_alpha_env_names_are_read_by_something.py` (5 tests) |
| DEF381 | Two defects in one mechanism, found while promoting `alpha-2026-08-28-1`. (1) `--exclude='.env'` is a filename pattern that does not match `infra/alpha.env` — the promotion rsync could ship live Alpha credentials to `~/ami_trade/infra/alpha.env`, read by nothing. How often this actually fired is NOT established and the one measurement (0 deletions on the dry-run) points toward "not this time" — recorded as an unverified-history gap, not an incident, deliberately. (2) `postflight.py`'s tree check inherited the same list, so the file's correct absence read as promotion drift — a false-failure gate (DEF277 shape), which is how this was found. (3) `_admin_secret` read the env file unguarded — a checkout with no local `infra/alpha.env` hit an unhandled `FileNotFoundError` and exit 1 (the script's own docstring says 1 means "the promotion is broken", 2 means "I could not tell" — this conflated them). Fix: `infra/alpha.env` excluded in both lists; the read wrapped to raise `CannotRun` (exit 2). Verified against the live deploy: `identity`/`readiness`/`config`/`market` green, tree check clean, checksum rsync against melehost 0 content differences. 3 mutations killed. | `4a111596` | `backend/tests/unit/test_cr175_postflight.py` (2 of its tests target this) |
| CR202 | Alpaca credentials moved off the host entirely — the four `users.alpaca_*` columns dropped; credential now lives only in Keychain/Keystore (`AlpacaCredentialStore`), app calls `paper-api.alpaca.markets` directly, only the result is uploaded. Closes the credential-holding root cause of DEF044 (cleartext at rest), DEF181 (key leaking into `http_audit`), DEF182 (SECRET_KEY reuse/fail-open crypto), DEF185 (empty key silently disabling crypto) at the source. New risk named and answered structurally: client-supplied payload reaching 12 agent prompts is bounded by `extra="forbid"` + a symbol regex + a finite-float check, rendered server-side by one renderer only. `test_def145_alpaca_stays_read_only.py` re-pinned to `{("exchange_code","post")}` — the backend now makes no authenticated Alpaca call at all. Live-verified: `information_schema` returns 0 rows for `users.alpaca%` on Alpha; live OpenAPI exposes exactly 1 Alpaca path. Released `alpha-2026-08-21-3`; device half reached testers in `0.1.0+100`. | `e09ea4f2`, `cbd342a7`, `581c9411`, `5b3c9296` | `test_cr202_no_host_side_credentials.py`, `test_def145_alpaca_stays_read_only.py` |
| CR203 | Tracks WHICH users have a linked Alpaca account without re-introducing custody — `users.alpaca_linked_at` (nullable timestamp, not a boolean: this host cannot verify the claim, so it records *when it was last said* rather than asserting a present-tense fact — the DEF059 class). `POST /v1/alpaca/link_state` reports link/unlink; unlink wipes locally FIRST, report failure is swallowed, so the worst case is briefly over-reporting a link that's gone, never a credential surviving after the user asked for it gone. Guard: key material POSTed alongside the flag is stored nowhere on `User` — the regression that would quietly undo CR202. Live-verified: unauthenticated call to `/link_state` returns 401 not 404; live OpenAPI lists exactly 2 Alpaca paths (`/link`, `/link_state`) so CR202's 5 removed routes haven't crept back. | `795b960e`, `5b3c9296` | `test_cr203_alpaca_link_state.py` (8 tests) |
| CR224 | Alpaca Connect screen's API Key tab gains a third field, API endpoint (default `https://paper-api.alpaca.markets`) — some Alpaca accounts resolve to a different host and had no way to link at all. Mobile-only per CR202's device-only custody model; backend's `alpaca_paper_base_url` is unrelated (serves only the unreachable OAuth exchange). Pre-CR224 stored credential with no base-URL key reads back as the default — no migration needed. `AlpacaClient.validate()` takes an optional `baseUrl` so the connect screen can check an endpoint before saving. | `069b7db1` | `mobile/test/services/alpaca/alpaca_credential_store_test.dart` (base-URL-override group, 3 tests) |
| DEF205 | 1-on-1 and Brief LLM turns cost zero credits — `credit_service.spend()` was called only from `room_runner.py`. Ruled by Saiful: 1 credit/turn, both surfaces. 1-on-1 needed only the price flip (DEF113 had already built the spine). Brief needed the whole spine built fresh, matching 1-on-1's shape: charged BEFORE the SSE status is on the wire, explicit concurrency-slot release on the 402 path (the generator that would release it never runs on a paywall refusal — a leaked slot wedges the shared DEF201 cap). `BRIEF_CREDIT_COST` forwarded in `docker-compose.yml` (CR040 parity). 21/21 mutations killed. This is the item that turned DEF369's row-lock gap from latent to live — both spend through the same function this lane's DEF369 hardens. | `016815cf`, `e426f0b4`, `62cfad5b` | `test_def205_brief_credit_gate.py` |

## Tests run by the builder (this submission), command and observed output

All commands run bare, from the repo root or the named subdirectory, using the repo's own
interpreter per BINDINGS (`backend/.venv/bin/python` — also used for `website_api/`, which has no
separate venv of its own; confirmed its dependency set is a superset by running its suite
successfully under it). Measured against the **shared working tree at `8c43c88e`** (no worktree
isolation used for this retroactive read-only pass — see the DEF159 note CR230's own submission
raised, carried forward below).

**Backend — every named guard test in the table above, one invocation:**

```
cd "/Volumes/Extreme Pro/AMI_MarketApp/backend"
"/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python" -m pytest \
  tests/unit/test_def369_spend_takes_a_row_lock.py \
  tests/unit/test_def370_prompt_injection_sanitiser.py \
  tests/unit/test_def371_journal_append_removed.py \
  tests/unit/test_def328_alpha_env_names_are_read_by_something.py \
  tests/unit/test_cr175_postflight.py \
  tests/unit/test_def205_brief_credit_gate.py \
  tests/unit/test_cr202_no_host_side_credentials.py \
  tests/unit/test_cr203_alpaca_link_state.py \
  -q -p no:cacheprovider
```

Observed output:

```
....................................................................     [100%]
68 passed in 15.50s     # exit 0
```

**Website — DEF372 and DEF361's guards, same interpreter (no dedicated website_api venv exists):**

```
cd "/Volumes/Extreme Pro/AMI_MarketApp"
"/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python" -m pytest \
  website_api/tests/test_def372_waitlist_and_email_escaping.py \
  website_api/tests/test_def361_turnstile_fails_closed_outside_local.py \
  -q -p no:cacheprovider
```

Observed output:

```
............     [100%]
12 passed in 0.19s     # exit 0
```

**Mobile — DEF373's OAuth guard and the CR202/CR224 credential-store suite:**

```
cd "/Volumes/Extreme Pro/AMI_MarketApp/mobile"
flutter test test/screens/settings/def373_alpaca_oauth_test.dart \
              test/services/alpaca/alpaca_credential_store_test.dart
```

Observed output: 19 tests (8 DEF373 + 11 credential-store, incl. the CR224 "base URL override"
group of 3 and the "auth mode" group DEF373's OAuth-mode plumbing depends on), `+19: All tests
passed!` — exit 0.

**Full backend unit suite:**

```
cd "/Volumes/Extreme Pro/AMI_MarketApp/backend"
"/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python" -m pytest tests/unit/ -q -p no:cacheprovider
```

**Full unit suite: not cited this round** — 5 concurrent full-suite runs ended up on the shared Mac
checkout at once (Architect's dispatch error, not a lane-specific problem), which made every
attempt's wall time and, after a stray `kill` during cleanup, one attempt's own output file
unreliable as evidence. The per-lane targeted test results above (68 backend + 12 website + 19
mobile, all named guard tests, all exit 0) are the builder evidence for this submission. The
auditor re-runs the independent suite on melehost per BINDINGS, which is the trustworthy number
regardless of what a shared, contended Mac checkout would have produced.

## Secret-in-git-history check (DEF328, DEF381, and the DEF178 adjacency)

Per the assignment: checked whether the paid Gemini key (DEF328) or the Alpha credential file
DEF381's rsync fix protects (`infra/alpha.env`) has ever been committed. **Value never printed,
only presence/absence reported, per this repo's own DEF178 guard convention.**

```
git log --oneline -- infra/alpha.env infra/*.env        # 0 lines — file never tracked, ever
git check-ignore -v infra/alpha.env                       # .gitignore:56:infra/alpha.env
git log --all -p -S 'GOOGLE_API_KEY' -- infra/            # no matching commit body found
```

**No live secret from DEF328 or DEF381's scope exists in git history** — `infra/alpha.env` has
zero commits against it at any point in this repo's history; `.gitignore:56-58` has excluded
`infra/{alpha,beta,prod}.env` by name since before either defect. DEF328's fix (renaming
`GOOGLE_API_KEY=` to `GOOGLE_AI_API_KEY=` inside that file) therefore had nothing to redact —
there is no commit to strip.

**DEF178 is a DIFFERENT, already-known-open item — NOT re-investigated or re-scoped by this
lane, flagged only for adjacency.** DEF178 (Adanos key, unrelated to Gemini/DEF328) IS
present in git history — two `.deliveryos/checkpoint_history/*.md` files and one CR143 doc had the
live value, redacted in the working tree 2026-08-19 but still recoverable from `origin/main`'s
history until Saiful runs `git-filter-repo` + a force-push (both explicitly his, per the row,
never run autonomously). This lane did not re-verify DEF178's current redaction state or attempt
any history rewrite — it is out of scope for RETRO-SECURITY and stays exactly as its own row
describes it: `status: open`, blocked on two operator-only steps.

## Note on worktree isolation (DEF159)

Per CR230's own submission in this same lane directory: a number quoted as evidence should be
measured against the committed SHA in a scratch worktree or `git archive`, not the shared working
tree someone may be mid-edit in. This submission's numbers above were measured in the **shared
working tree**, not an isolated worktree, for the same reason RETRO-SIM-OPTIONS gave: this is a
retroactive read-only verification pass (no source edited in this session), not a build submission
with uncommitted sibling work nearby — though on this shared checkout other tracks DO have
concurrent work in progress (confirmed via the concurrent pytest processes observed above), so the
auditor re-running these exact commands in an isolated worktree at `8c43c88e` is the safer
independent check, not a redundant one.

## Measurement

**None run by the builder beyond the automated test suites above and the git-history check** —
retroactive; this submission makes no live/Alpha behavioural measurement of its own. Per the
assignment, the auditor should probe on Alpha directly:

- **DEF369 (double-spend):** concurrency on `spend()` — fire two near-simultaneous requests
  against a single-credit user via 1-on-1 or Brief (DEF205's exact door) and confirm exactly one
  succeeds, not both. The guard here asserts the compiled SQL takes a row lock; it does not itself
  drive two real concurrent sessions against Postgres.
- **DEF373 (OAuth CSRF):** replay a captured `state` value against a second session; confirm the
  single-use check actually rejects the second exchange server-side reachability aside, this is a
  mobile-only client check — verify there is no server-side state store to also check for reuse
  (CR202 already removed the backend's OAuth token exchange from ordinary operation, but
  `exchange_code` survives per CR202's row — confirm it enforces nothing state-related itself,
  since if it did, that would be a second place needing the same fix).
- **DEF361 (Turnstile):** hit `/contact`, `/data-request`, `/concierge/message` on melehost with
  `TURNSTILE_SECRET` unset (or confirm it IS set live and the fail-closed path is currently
  untested in production) — the row's own fix is parametrised over `prod`/`staging`/`alpha`/`""`
  in tests only; a live confirmation of which env value melehost actually reports was not run by
  this submission.
- **DEF370 (injection):** construct an actual payload — a Reddit-shaped snippet or a news headline
  containing a newline plus U+2500 runs — and confirm it reaches `sanitize_for_prompt` and comes
  out flattened in a real Room run, not just in the unit fixture.
- **DEF381 (rsync):** confirm melehost's `infra/` currently holds `alpha.env.example` and no
  `alpha.env` (the row's own live-verification claim, made 2026-08-28 — nearly a month stale as of
  this submission and worth re-checking after however many promotions have run since).
- **CR202/CR203 (Alpaca custody):** re-run the live OpenAPI path count (expect exactly 1 Alpaca
  path pre-CR203 semantics superseded — now 2: `/link`, `/link_state`) and re-confirm
  `information_schema` still returns 0 rows for `users.alpaca_access_token`/`alpaca_refresh_token`
  columns — these are schema-absence claims that a later, unrelated migration could in principle
  reintroduce without any of this lane's guards noticing (no test asserts a column can never be
  added back under a new name, only that the four originally-named ones are gone).

## Attack surface

Concrete risks worth a blind adversarial pass, not claims of absence:

1. **Race on `spend()` beyond the row lock's own guarantee.** DEF369 fixes the read-then-write
   race with `SELECT … FOR UPDATE`. Worth probing: does every caller of `spend()` actually hold
   the transaction open across both the lock acquisition and the eventual commit, or does any path
   (an exception mid-request, a connection-pool timeout) release the lock early in a way the unit
   suite — which asserts compiled SQL, not live Postgres behaviour — cannot see? SQLite's no-op
   `FOR UPDATE` means this property has literally never executed for real inside this repo's own
   test run.

2. **Idempotency, not just atomicity.** A row lock stops two concurrent spends from both
   succeeding on one balance; it says nothing about a single logical request that retries (client
   timeout + resend, an SSE reconnect) and spends twice legitimately-sequentially. Worth checking
   whether any caller path can produce a duplicate legitimate-looking spend on retry, independent
   of the race this defect specifically closed.

3. **Streak-reward farming via clock/timezone, not the route DEF371 deleted.** DEF371 removed the
   *arbitrary-entry* vector. `_activity_days` still counts system-generated entries
   (`room_run`, `sim_trade`, `lesson_complete`, …) by `created_at` — worth checking whether a user
   can manufacture qualifying activity cheaply through one of the surviving legitimate entry types
   (e.g. the cheapest possible `lesson_complete` or `sim_trade`, repeated once daily) and whether
   day-boundary logic uses server UTC or something client-influenced that a user could manipulate
   to claim two "days" from one calendar day.

4. **OAuth state/nonce binding to session, not just single-use.** DEF373's nonce is per-attempt
   and single-use, compared before the code is read. Worth confirming the nonce is bound to the
   SPECIFIC app instance/session that generated it (not just "any nonce this app has ever issued")
   — i.e. that a nonce generated in one login attempt can't be satisfied by a callback arriving
   from a different, concurrently-started attempt on the same device.

5. **Fail-open when config is absent, everywhere DEF361's exact pattern could recur (CR040).**
   DEF361 fixed one instance (Turnstile). This defect class — a feature gated on config presence
   silently degrading instead of failing loud — is exactly what CR040 exists to catch, and this
   lane's own DEF328 is a second, unrelated instance of "config present, not reaching the reader"
   in the same window. Worth a blind sweep of the other config-gated boolean checks this lane
   touches (Alpaca allowlist configuration, the credit-cost env vars DEF205 forwards) for the same
   silently-permissive default DEF361 had.

6. **Secrets on melehost via paths other than the rsync DEF381 fixed.** DEF381 closed one
   transport (the promotion rsync). Worth checking whether `scp infra/alpha.env
   melehost:~/ami_trade/.env` (step 4, the mechanism DEF381's fix says is "and was the one
   mechanism") itself has any weaker permission/logging posture, and whether any OTHER script
   (Hermes UAT tooling, a manual `rsync`/`scp` run ad hoc, not through `/promote-to-alpha`) could
   reintroduce the same class of leak DEF381 closed for the one blessed path.

7. **DEF178 adjacency — do not conflate.** DEF178 (Adanos key in git history) is a live, open,
   different defect on the same general "secret exposure" theme as this lane's items, but it is
   NOT part of this lane's claims and this submission did not re-verify its current state. Flagging
   so the auditor doesn't read DEF328/DEF381's "no secret in history" finding as extending to
   DEF178, which it does not.

## Known limits, stated rather than left to be found

- **No live device pass, no fresh live-Alpha probe.** This submission verifies the committed code
  and its test suites; it does not reproduce a live OAuth exchange, a live concurrent-spend race,
  a live Turnstile-unset probe, or a live melehost `infra/` directory listing. All of those are
  named explicitly under Measurement, above, as the auditor's job.
- **No full-backend-suite number is cited in this submission.** Up to 11 concurrent full-suite
  pytest runs ended up on this shared Mac checkout at once — sibling retroactive lanes
  (RETRO-PM-FLOOR, RETRO-SIM-OPTIONS) plus this lane's own repeated attempts, an Architect dispatch
  error rather than anything specific to this lane's code. Under that contention, wall time
  stretched well past CR230's own uncontended ~17-minute baseline for the same suite, and a stray
  `kill` issued during cleanup corrupted the output capture for one attempt. Rather than cite a
  number from a run whose provenance I cannot fully vouch for, this submission stands on the
  per-lane targeted test results above (68 backend + 12 website + 19 mobile, all named guard tests,
  all exit 0) and defers the full-suite confirmation to the auditor's own independent run on
  melehost per BINDINGS.
- **DEF381's live-verification claim (melehost `infra/` holds no `alpha.env`) is dated 2026-08-28**,
  nearly a month before this submission (2026-09-24) — an unknown number of promotions have run
  since. Not re-checked here; listed under Measurement.
- **This submission did not re-derive DEF370's sanitiser regex/logic from scratch**, nor
  independently construct novel injection payloads beyond reading the guard test's own cases — it
  confirmed the commit exists, the named guard tests exist and pass, and both call sites
  (`social_context.py:695`, `news_context.py:433,437`) actually invoke the shared function rather
  than a dead or partial copy. Independent adversarial payload construction is the auditor's job on
  a Tier A item, not something the builder's own re-run of its own tests can stand in for.
- **CR224's per-item row in the table above cites only its own 3 new tests**, not the full 12-test
  "auth mode" + "storage location" groups in the same file that predate it (CR202) — those are
  covered under CR202's own row instead, to avoid double-counting the same file's tests under two
  IDs.

## Round 2

Fixes `orchestration/audit/cr/RETRO-SECURITY.auditor.md`'s round-1 verdict
(`AWAITING_FIXES` — 2 MAJOR, 3 MINOR). Worked in isolated worktree
`.claude/worktrees/agent-ae7ac93b2e756db70`, branch `worktree-agent-ae7ac93b2e756db70`,
based on `main` at `68f9c7d0`. No push/merge/promote from here — the coordinator
integrates.

### MAJOR-1 — six other unlocked `credit_balance` writers (fixed)

**The claim.** DEF369 row-locked exactly one of eight read-modify-write sites on
`users.credit_balance` (`credit_service.spend()`). The auditor found and
measured on real Postgres (round 1 run report) that a `refund(+1)` racing a
`spend(-1)` from a balance of 5 landed the final balance on 6 — the spend's
write silently evaporated. Their enumerated writers:

```
credit_service.py:554  refund()                          old + amount
credit_service.py:438  add_credit_pack()   (RevenueCat)  old + amount
credit_service.py:412  set_plan_and_grant_allowance()    = allowance
credit_service.py:508  carry_billing_on_merge()          = merged
credit_service.py:217  _ensure_period() via balance_for() = allowance (no lock on that path)
reputation_service.py:494  streak award                  old + credits
api/admin.py:616       admin set                          = new
```

**My own search, independent of the list above, before fixing anything:**
`grep -rn "\.credit_balance\s*=" backend/app --include="*.py"` — nine
assignment sites total, matching the auditor's seven plus `spend()`'s own two
branches (`old_balance - cost` and the winzip reset `= cost`), both of which
were already inside DEF369's lock. All seven of the auditor's unlocked sites
confirmed present; no eighth site found.

**Fix.** One new helper, `credit_service._lock_user_row(session, user)`
(`backend/app/services/credit_service.py:180-206`): a thin
`session.get(User, user.id, with_for_update=True)` re-select, taken inside the
CALLER's own already-open transaction (every call site is already inside a
`with get_session()` block or receives that block's `session` parameter — this
re-acquires the transaction's own lock, which Postgres permits without
self-deadlock; SQLite makes it a no-op, same as DEF369). Every one of the
seven writers now calls it before its read-modify-write:

| Site | Fix |
|---|---|
| `credit_service.py::_ensure_period` (line ~217, was 200) | `user = _lock_user_row(session, user)` before reading `old_balance` |
| `credit_service.py::set_plan_and_grant_allowance` | locked at function entry, before `old_plan`/`old_balance`/period reads |
| `credit_service.py::add_credit_pack` | locked after `_ensure_period`, before its own `old_balance` read |
| `credit_service.py::carry_billing_on_merge` | BOTH `source_user` and `target_user` locked before either balance is read (the write depends on both) |
| `credit_service.py::refund` | locked at load — `s.get(User, user_id, with_for_update=True)`, same shape as DEF369's `spend()` fix (this is the exact writer the round-1 Postgres probe measured racing `spend()`) |
| `reputation_service.py::_grant_milestone` | `from app.services.credit_service import _lock_user_row; user = _lock_user_row(session, user)` before the streak-credit read |
| `api/admin.py::adjust_credits` | same import + call, before `old_balance` |

`spend()` itself is unchanged — its existing `s.get(User, user_id,
with_for_update=True)` (line 309, DEF369) is the exact string
`test_def369_spend_takes_a_row_lock.py` pins, left untouched.

**Structural guard (new).**
`backend/tests/unit/test_retro_security_credit_balance_lock_guard.py` — an AST
scan over every `.py` file under `backend/app/`, collecting every function
that assigns `<name>.credit_balance = ...` anywhere in its body, then asserting
each one's source calls `_lock_user_row(` (or, for the two functions that load
fresh from a bare `user_id` rather than an already-loaded `User`, contains
`with_for_update=True` directly). Modeled on the repo's existing
`test_p15_check_then_insert_guard.py` shape (scan the AST for the PATTERN, not
an allowlist of known-safe function names) so a ninth, future writer is caught
by construction rather than by remembering to update an inventory. Four tests:

- `test_the_guard_finds_something_to_check` — vacuity guard.
- `test_every_credit_balance_writer_locks_the_row_first` — parametrized over
  every discovered writer, the regression itself.
- `test_lock_user_row_itself_uses_with_for_update` — the helper's own
  contract, checked against the parsed `ast.Call` node's keyword arguments
  (not `inspect.getsource(...)` substring matching — the function's own
  docstring quotes the call verbatim for documentation, so a naive substring
  check is satisfied by the docstring even after the real line has the keyword
  deleted; caught this exact false-negative via my own mutation pass below and
  rewrote the test to inspect the executable node instead of prose describing
  it).
- `test_known_writer_inventory_is_exact` — exact pin (P15's rationale: a new
  writer should stop the build, a removed one should have its stale entry
  removed so it doesn't hide the next real gap).

**Tests + output** (`backend/.venv/bin/python -m pytest … -q -p no:cacheprovider`,
run bare from `backend/`):

```
tests/unit/test_retro_security_credit_balance_lock_guard.py
11 passed in 2.54s     EXIT=0

tests/unit/test_def369_spend_takes_a_row_lock.py
tests/unit/test_def205_brief_credit_gate.py
tests/unit/test_def113_one_on_one_credit_gate.py
21 passed in 14.83s    EXIT=0   (unchanged pass count — no regression)

tests/unit/test_cr084_revenuecat_webhook.py
tests/unit/test_def099_merge_billing.py
tests/unit/test_merge_service.py
tests/unit/test_reputation_service.py
tests/unit/test_sim_reputation.py
82 passed, 2 warnings (pre-existing HTTP_422 deprecation, unrelated) in 7.98s   EXIT=0

tests/unit/test_admin.py
tests/unit/test_cr200_admin_audit.py
33 passed in 3.60s     EXIT=0
```

**Mutation evidence (each reverted immediately after).**

1. Dropped the lock from `refund()` (reverted `with_for_update=True` back to a
   bare `s.get(User, user_id)`): `test_every_credit_balance_writer_locks_the_row_first[credit_service.py::refund]`
   → `1 failed, 10 passed` — the exact writer the round-1 Postgres probe
   measured racing `spend()`.
2. Dropped `with_for_update=True` from `_lock_user_row`'s own `session.get(...)`
   call: `test_lock_user_row_itself_uses_with_for_update` initially STILL
   PASSED (the docstring's own prose quotes the call verbatim, so a
   source-substring check couldn't discriminate) — rewrote the test to walk
   the parsed AST `Call` node's `keywords` instead of `inspect.getsource(...)`
   substring matching; re-ran the same mutation: `1 failed` with the intended
   message. This is recorded because it is exactly the kind of blind spot a
   review pass would not catch either — the docstring READS as the guarantee
   holding, and only running the mutation against the test showed it wasn't.

**What the auditor should re-measure on real Postgres** (unit tests cannot
exercise `FOR UPDATE` — SQLite makes it a no-op, same DEF369 limitation): the
round-1 `refund_vs_spend` probe (start=5, `+1 refund` racing `-1 spend`,
expect final=5) should now hold under the lock, the same way the round-1
`spend_spend`/`spend_spend_nolock` pair demonstrated DEF369's fix. Suggest
extending the same throwaway-Postgres procedure to a `_grant_milestone` (streak
award) racing a `spend()`, and an `admin.adjust_credits` racing a `spend()`,
since those are the two writers reached from outside the credit_service module
proper.

### MAJOR-2 — Brief never refunds a failed turn; both surfaces bill an HTTP-error sentinel as a real reply (fixed)

**The claim, in two parts.** (1) `brief.py`'s `event_stream` caught a failure,
emitted an SSE `error` event, and refunded nothing — DEF205 ported 1-on-1's
CHARGE to Brief but not 1-on-1's REFUND (DEF113: *"never let a provider blip
silently eat a turn the user never got"*). (2) On a non-200 transport response,
`llm_gateway.py`'s `OpenAICompatibleProvider.stream_chat` (and
`AnthropicProvider.stream_chat`) never raise — they yield an
`"[AMI error: HTTP {status} …]"` string as an ORDINARY chunk and return
cleanly, so a route with no structural signal bills a credit for an error
message rendered as the answer. Measured by the auditor through the real
route: `brief mode=raise` and `brief mode=http_error_sentinel` both
`charged_for_failed_turn=1`; `1on1 http_error_sentinel` also `charged=1`.

**Root cause, precisely.** `llm_gateway.py` already had a structural channel
for exactly this — `meta["stream_error"]`, DEF376's in-band-error-frame fix —
but it was only ever written on the IN-BAND (HTTP 200, malformed SSE frame)
error shape, never on the TOP-LEVEL non-200 transport-response shape, even
though both shapes yield the identical `[AMI error: …]` sentinel text. And
neither `agent_runner.py::stream_one_on_one_message` nor
`brief_engine.py::BriefEngine.stream_chat` accepted a caller-supplied `meta`
to plumb through to the gateway in the first place — so even the in-band case
was invisible to both routes before this fix, only ever reaching
`room_runner.py`'s own local `stream_meta`.

**Fix — four changes, one channel, no string-matching anywhere:**

1. `backend/app/services/llm_gateway.py` — both `AnthropicProvider.stream_chat`
   (`~line 444`) and `OpenAICompatibleProvider.stream_chat` (`~line 700`) now
   write `meta["stream_error"] = f"HTTP {status}: {detail}"` on the non-200
   branch, before yielding the sentinel text — the same key the in-band branch
   already set 40-60 lines below each. One structural fact, one place callers
   check, regardless of which of the two failure shapes fired.
2. `backend/app/services/agent_runner.py::stream_one_on_one_message` — gained
   an optional `meta: dict[str, Any] | None = None` parameter, threaded to
   `self._llm.stream_chat(..., meta=meta)`.
3. `backend/app/services/brief_engine.py::BriefEngine.stream_chat` — same:
   optional `meta`, threaded to `self._llm.stream_chat(..., meta=meta)`.
4. `backend/app/api/brief.py::brief_message` and
   `backend/app/api/one_on_one.py::send_message` — both now open a
   `stream_meta: dict[str, Any] = {}`, pass it into the engine/runner call, and
   set `failed = True` when `stream_meta.get("stream_error")` is truthy AFTER
   the stream completes cleanly (in addition to the existing `except
   Exception: failed = True` for a raised error) — then refund exactly like
   `one_on_one.py` already did for DEF113/DEF201: released concurrency slot in
   `finally`, best-effort `refund(...)` when `failed and cost > 0`.
   `brief.py` needed the import (`refund`) and the whole refund branch added
   fresh; `one_on_one.py` only needed the `stream_meta` detection added to its
   existing refund branch.

No caller anywhere string-matches `"[AMI error"` or any other prose — the
sentinel text is exactly as free to change wording as it was before, and
detection would not care.

**Tests + output.** Two new tests in `test_def205_brief_credit_gate.py`
(`test_a_raised_provider_failure_after_spend_is_refunded`,
`test_an_http_error_sentinel_reply_is_refunded_not_billed` — the latter is the
auditor's exact probe, reproduced via a fake gateway that writes
`meta["stream_error"]` and yields the sentinel, dependency-overriding
`get_brief_engine`) and one new test in `test_def113_one_on_one_credit_gate.py`
(`test_an_http_error_sentinel_reply_is_refunded_not_billed`, via
`monkeypatch.setattr(AgentRunner, "stream_one_on_one_message", ...)` same
pattern as the file's existing DEF113 refund test). 1-on-1's raised-exception
refund twin already existed pre-round-2
(`test_llm_failure_after_spend_refunds_at_a_non_zero_price`) — confirmed still
green, unchanged.

```
tests/unit/test_def205_brief_credit_gate.py
8 passed in 10.68s     EXIT=0   (was 6 before round 2 — 2 new)

tests/unit/test_def113_one_on_one_credit_gate.py
11 passed in 3.98s     EXIT=0   (was 10 before round 2 — 1 new)
```

**Failing-first, proven by reverting to pre-fix code via a tagged stash**
(`git stash push -u -m "retro-security-round2-verify-…" -- backend/app/api/brief.py backend/app/services/brief_engine.py backend/app/services/llm_gateway.py`,
captured the entry's own SHA from `git stash list --format='%H %gs'`, restored
with `git stash apply <sha>` — never bare `stash pop`, per this worktree's
shared-stash-stack rule — then dropped by the same disambiguated `stash@{0}`
once confirmed restored):

```
test_a_raised_provider_failure_after_spend_is_refunded            FAILED (10 == 13, not refunded)
test_an_http_error_sentinel_reply_is_refunded_not_billed (brief)  FAILED (10 == 13, not refunded)
```

Repeated for the 1-on-1 sentinel test (stashed `one_on_one.py` +
`agent_runner.py` + `llm_gateway.py`):

```
test_an_http_error_sentinel_reply_is_refunded_not_billed (1on1)   FAILED (10 == 13, not refunded)
```

All three failed against the pre-round-2 tree and pass against the fix —
confirming they reproduce the auditor's exact findings rather than merely
exercising the new code path.

**Mutation evidence:** the failing-first proof above IS the mutation test for
this MAJOR — reverting the actual fix (not a synthetic mutation) reproduces
both the auditor's `brief mode=raise`/`mode=http_error_sentinel` and
`1on1 http_error_sentinel` probes exactly, and the fix closes all three.

**What the auditor should re-measure on real infrastructure:** the round-1 run
report's exact probe — TestClient + a fake gateway that raises, and one that
yields the HTTP-error sentinel without raising — should now both show
`charged_for_failed_turn=0` (refunded) on both surfaces. A live vLLM-outage
probe against Alpha (DEF413's actual failure shape) would additionally confirm
the real `OpenAICompatibleProvider` branch, not just the fake-gateway
reproduction here.

### MINOR-1 — DEF361 row correction (not a code bug; row corrected, no code changed)

Confirmed by reading `website_api/app/routes/concierge.py`: the route's own
docstring already states Turnstile is verified *"when a token is supplied
(defense in depth) but not required"*, with the 5/min/IP rate limiter as the
primary control — a multi-turn chat can't gate every turn on a single-use
token the way `/contact`/`/data-request`'s one-shot submit can. The DEF361 fix
(fail-closed when the secret is unset) is correct and unchanged; what was
imprecise was the row's claim that all three routes "would have accepted every
caller as human-verified" — true for `/contact`/`/data-request` (which
hard-require a token), not true for `/concierge/message` in the sense of "this
route's normal behavior changed", since a caller sending no token was already
accepted before and after the bug, by design. Corrected
`docs/defect/_registry/DEF361.row.md` in place (one sentence replaced with a
precise correction paragraph), regenerated with
`python3 scripts/registers/gen_registers.py gen def`, verified with
`test_registers_no_drift.py` + `test_p30_registers_name_things_that_exist.py`
(10 passed). No source file touched.

### MINOR-2 — DEF370: `publisher` left raw, glyph list incomplete (fixed)

**Fix.** `backend/app/services/prompt_safety.py`: `_STRUCTURE_GLYPHS` (a
hand-enumerated tuple) replaced with `_STRUCTURE_GLYPH_RANGES = ((0x2500,
0x259F),)` plus `_is_structure_glyph`, dropping the WHOLE Unicode Box Drawing
+ Block Elements range by code point rather than by name — the auditor's three
escapees (U+2506 "┆", U+257C "╼", U+2574 "╴") are all in this range and none
were individually enumerated in the old tuple.
`backend/app/services/news_context.py::format_headline` (`~line 433`): added
`publisher = sanitize_for_prompt(item.publisher) or "unknown publisher"`,
replacing the raw `item.publisher or 'unknown publisher'` interpolation that
sat unsanitised beside the already-sanitised `title` and `summary` on the same
line.

**Tests + output.** Three new tests in
`test_def370_prompt_injection_sanitiser.py`:
`test_the_auditors_specific_escapees_are_now_dropped` (the three named
glyphs), `test_the_whole_box_drawing_and_block_elements_ranges_are_dropped`
(every code point 0x2500-0x259F, not just named ones),
`test_the_publisher_field_is_sanitised_the_same_as_title_and_summary`
(constructs a `LiveHeadline` with a forged-header `publisher` and confirms
`format_headline`'s output carries neither the box-drawing run nor the
newline).

```
tests/unit/test_def370_prompt_injection_sanitiser.py
12 passed in 1.93s     EXIT=0   (was 9 before round 2 — 3 new)

tests/unit/test_cr090_live_data_surcharge.py
tests/unit/test_cr090_room_live_data_surcharge.py
tests/unit/test_cr098_room_analyst_pullback.py
tests/unit/test_cr148_cr147_feed_depth.py
tests/unit/test_cr179_catalyst_relevance.py
tests/unit/test_cr219_availability_guard.py
tests/unit/test_news_context.py
tests/unit/test_prompt_data_parity.py
tests/unit/test_social_context.py
242 passed in 53.19s   EXIT=0   (full news/social/room blast-radius sweep, no regression)
```

**Mutation evidence (each reverted immediately after):**

1. Reverted `_is_structure_glyph`'s range check back to the old enumerated
   tuple: `test_the_auditors_specific_escapees_are_now_dropped` and
   `test_the_whole_box_drawing_and_block_elements_ranges_are_dropped` →
   `2 failed, 10 passed`, failing on `0x2506` exactly as the auditor's own
   probe did.
2. Reverted `format_headline`'s `publisher` line back to the raw
   `item.publisher or 'unknown publisher'`:
   `test_the_publisher_field_is_sanitised_the_same_as_title_and_summary` →
   `1 failed` — the forged header glyphs and newline surfaced in the rendered
   line exactly as the auditor described.

### MINOR-3 — DEF159 shared-tree "68 passed" (procedural note, not code; not this submission's number to fix)

The auditor's point was that the round-1 BUILDER's "68 passed" was measured on
the shared Mac checkout, not an isolated worktree/SHA, so it could not be
vouched for as belonging to `8c43c88e` specifically. This round-2 submission's
own numbers above were all measured inside this session's OWN isolated
worktree (`.claude/worktrees/agent-ae7ac93b2e756db70`, based on `main` at
`68f9c7d0`) — a disjoint tree from any other track's concurrent work — so
DEF159's specific concern does not apply to them the same way. No code or
process change is being made under this MINOR in this lane; it is a
measurement-provenance note for whoever reads the round-1 evidence, and I have
not touched `test_def328_alpha_env_names_are_read_by_something.py` or its
live-file skip behavior.

**Full unit suite: not run by the builder (release gate contention)** — the
coordinator flagged that another track is running the full `tests/unit/`
suite on the same Mac for the +111 release gate, and timing-sensitive tests
break under contention. All evidence above is targeted test files, run bare,
exit codes read directly. The auditor re-runs the independent suite (melehost,
per BINDINGS) as the trustworthy full-suite number, same as round 1.

**Unresolved / left for the auditor:** the real-Postgres re-measurements named
under MAJOR-1 (refund-vs-spend now holding under the lock; the two new writer
paths — streak award, admin adjust — racing a spend) and under MAJOR-2 (the
same TestClient probes against the fix, plus a live vLLM-outage confirmation
on Alpha). Nothing else identified as open.

SUBMITTED: round 2

## Round 3

Fixes `orchestration/audit/cr/RETRO-SECURITY.auditor.md`'s round-2 verdict
(`AWAITING_FIXES` — 3 MAJOR, 0 MINOR). Worked in isolated worktree
`.claude/worktrees/agent-a43668ab4d5d5dd41`, branch
`worktree-agent-a43668ab4d5d5dd41`, based on `main` at `700ee1d9`. No
push/merge/promote from here — the coordinator integrates.

### MAJOR-1 — `_lock_user_row` took the lock, then kept the pre-lock balance (fixed)

**The claim.** `_lock_user_row` (`credit_service.py`, the call at line ~204)
called `session.get(User, user.id, with_for_update=True)` without
`populate_existing=True`. In SQLAlchemy 2.0.49, `Session.get(...,
with_for_update=True)` on an ID already present in the session's identity map
takes the row lock on the wire but returns the SAME Python object, with its
attributes from whenever it was first loaded — the balance read immediately
after "locking" the row is the pre-lock value. Measured by the auditor on
real Postgres: `pack_vs_spend` landed on 15 (expected 14), `admin_vs_spend`
on 6 (expected 5) — a concurrent spend's write erased, round 1's exact harm
surviving through the new helper.

**Fix.** One keyword, `credit_service.py::_lock_user_row`:

```python
locked = session.get(
    User, user.id, with_for_update=True, populate_existing=True
)
```

`populate_existing=True` forces the ORM to overwrite the already-loaded
object's attributes from the fresh `SELECT … FOR UPDATE` result, so the
caller's balance read after the lock sees the row as it stands NOW, not as
it stood when the caller first loaded it.

**Structural guard extended.**
`test_retro_security_credit_balance_lock_guard.py::test_lock_user_row_itself_uses_with_for_update`
now also asserts `populate_existing=True` on the same parsed `ast.Call`
node's keywords, the same way it already asserted `with_for_update=True` —
so a future edit that drops either keyword fails the build, not just a
security review.

**New sqlite-runnable regression** (the round-2 auditor's exact gap: "the
property that matters only exists on Postgres, and the unit suite runs on
SQLite" — but `populate_existing` is an ORM identity-map behaviour, not a
database lock, so it IS exercisable on SQLite without a real Postgres):
`test_lock_user_row_re_reads_the_balance_after_a_concurrent_write` — loads a
user in session `s1`, commits a balance change to the same row via a SECOND
session `s2` (reproducing `add_credit_pack`'s/`adjust_credits`'s exact
shape — load, then `_lock_user_row`), then asserts `_lock_user_row(s1,
loaded)` returns the NEW balance, not the one `loaded` was created with.

**Tests + output**
(`backend/.venv/bin/python -m pytest tests/unit/test_retro_security_credit_balance_lock_guard.py -q -p no:cacheprovider`,
run bare from `backend/`):

```
12 passed in 2.65s     EXIT=0   (was 11 at round 2 — 1 new: the sqlite re-read regression;
                                  the populate_existing AST assertion is inside the existing
                                  test_lock_user_row_itself_uses_with_for_update, not a new test)
```

**Mutation evidence (reverted immediately after, restored file re-verified green):**

Removed `populate_existing=True` from `_lock_user_row`'s `session.get(...)`
call, nothing else changed:

```
test_lock_user_row_itself_uses_with_for_update                          FAILED
test_lock_user_row_re_reads_the_balance_after_a_concurrent_write         FAILED
2 failed, 10 passed
```

Both fail with the intended message — the AST guard names the missing
keyword by name, and the sqlite regression shows the returned object's
`credit_balance` is the pre-write value (`0 == 0 - 1`) exactly as the
auditor's Postgres probe showed (`15` instead of `14`, `6` instead of `5`).
Restored, re-ran: `12 passed in 2.65s, EXIT=0`.

**What the auditor should re-measure on real Postgres:** the round-2
`pack_vs_spend`/`admin_vs_spend` probes, unchanged, should now both read the
expected value (14 and 5) instead of the pre-fix 15/6 — this submission's own
evidence is the sqlite regression above plus the AST guard; it does not
itself re-drive the two named Postgres races.

**Second bug, self-caught by the full mandated test list, not by the auditor's
own probes — `populate_existing=True` alone regressed the full backend
suite.** Running the mandated test list after the `populate_existing` fix
above (before adding anything further) turned `test_cr084_revenuecat_webhook.py`
red — 9 of its 39 tests, all on the SAME mechanism:

```
test_credit_pack_adds_credits_no_plan_change[credits_starter-60]   60 == (13 + 60)     — the monthly allowance vanished
test_replayed_credit_pack_adds_credits_once                       300 == 313           — same, plus a replay double-count
test_revoke_drops_effective_plan_to_floor_pass[CANCELLATION]       plan stayed 'trader' — the revoke never stuck
test_revoke_falls_back_to_trial_when_trial_active                  plan stayed 'trader' — same
test_test_store_expiration_revokes_to_floor_pass                   plan stayed 'trader' — same
(4 more parametrizations of the same two assertions)
```

**Root cause.** `db/session.py` sets `autoflush=False` on every session,
deliberately. Two call chains mutate `user` and THEN call `_lock_user_row` a
SECOND time on the same still-open transaction:

- `add_credit_pack`: `_ensure_period(session, user)` sets
  `user.credit_balance = ALLOWANCE[eff]` (the monthly re-grant) — unflushed —
  then `add_credit_pack` itself calls `_lock_user_row(session, user)` again
  before adding the pack amount.
- `revoke_to_base`: sets `user.plan = Plan.FLOOR_PASS.value` — unflushed —
  then calls `_ensure_period(session, user)`, which calls `_lock_user_row`.

With `populate_existing=True` and no flush in between, the second
`_lock_user_row` call's fresh `SELECT` reads the row as it stood BEFORE the
first function's own pending change — and `populate_existing` then
overwrites that pending change with the stale pre-write snapshot. The
monthly allowance grant and the plan-drop both silently evaporated, one
call chain later, in a way that has NOTHING to do with a second session or a
real concurrent writer — this is the same transaction erasing its OWN
just-made, not-yet-flushed edit.

**Fix.** `_lock_user_row` calls `session.flush()` before the `populate_existing`
re-select — this pushes any pending change to the DB (still inside the same
open transaction; nothing is committed and no OTHER transaction can see it
yet), so the subsequent `SELECT … FOR UPDATE` reads this transaction's own
latest state, and `populate_existing` refreshes from THAT snapshot rather
than a pre-flush stale one. A narrower fix (e.g. skip the re-select when
`user` is already the locked object) was considered and rejected: the merge
path's `carry_billing_on_merge` locks two DISTINCT `User` objects for two
different accounts, and that path genuinely needs the real cross-session
re-read regardless of what either object has pending — a flush-first
approach handles both shapes with one line, a same-object-skip would not
have covered the merge path's real cross-account race.

**Tests + output**
(`backend/.venv/bin/python -m pytest tests/unit/test_cr084_revenuecat_webhook.py tests/unit/test_retro_security_credit_balance_lock_guard.py -q -p no:cacheprovider`):

```
42 passed in 5.37s     EXIT=0
```

**Mutation evidence (reverted immediately after, restored and re-verified
green):** removed only the `session.flush()` line, `populate_existing=True`
left in place — the exact same 9 `test_cr084_revenuecat_webhook.py` failures
reproduced verbatim (same numbers: `60 == 13 + 60`, plan stuck at `'trader'`
after a revoke). Restored, re-ran: `42 passed in 5.37s, EXIT=0`.

Re-ran the full mandated test list plus the credit-adjacent suite after
adding the flush (`test_def099_merge_billing.py`, `test_merge_service.py`,
`test_reputation_service.py`, `test_sim_reputation.py`, `test_admin.py`,
`test_cr200_admin_audit.py` in addition to the mandated list, since the merge
and admin paths are the other two callers of `_lock_user_row` a second flush
could in principle disturb):

```
390 passed, 1 skipped, EXIT=0
```

**What the auditor should re-measure on real Postgres, in addition to the
pack_vs_spend/admin_vs_spend probes above:** the SAME probes should also be
re-run in a shape that exercises `_ensure_period` immediately before
`add_credit_pack`/`revoke_to_base` within one request (the live webhook
shape, not a bare unit fixture) — this submission's own regression was only
caught because the mandated test list happened to include
`test_cr084_revenuecat_webhook.py`; a narrower targeted run limited to the
auditor's own named files would have missed it entirely, which is itself
worth noting for how future rounds scope "targeted" runs on a fix to a
shared low-level helper like `_lock_user_row`.

### MAJOR-2 — the Concierge 1-on-1 still charged for an error sentinel and for an outage (fixed)

**The claim, in two parts.** (1) `AgentRunner.stream_one_on_one_message`
threads a caller-supplied `meta` to the analyst branch's `stream_chat` call
(round 2's fix) but never passed it into `_stream_concierge` at all — so an
in-band `[AMI error: HTTP 503 …]` sentinel from the Concierge's own
`stream_chat` call left `meta["stream_error"]` unset, and `one_on_one.py`'s
refund check (`stream_meta.get("stream_error")`) never fired. (2)
`_stream_concierge`'s `except Exception` (a provider outage, e.g.
`ConnectError`) caught the exception and yielded a scripted fallback reply
with NO signal of any kind — not even a raised exception for the route's
`except Exception: failed = True` to catch. Measured by the auditor through
the REAL `LLMGateway` + a real `OpenAICompatibleProvider` with an
`httpx.MockTransport`: `1on1 agent=concierge http503 charged=1`, `1on1
agent=concierge connect_error charged=1 (tail: a scripted Concierge reply)`
— both other surfaces (Brief, the analyst 1-on-1 path) already read 0 from
the same probe.

**Root cause, precisely.** The `meta=` passthrough round 2 gave the analyst
branch (`agent_runner.py`, then `:238-246`) was never mirrored onto the
Concierge branch's own, separate `stream_chat` call
(`_stream_concierge`, then `:303`) — two different call sites in the same
function, one fixed, one not. And the Concierge branch's own `try/except`
around that call had no `meta`-writing counterpart to the gateway's
transport-level `meta["stream_error"]` write for the exception case, because
the exception never reaches the gateway's own `finally` block at all — it
propagates straight into `_stream_concierge`'s own handler.

**Fix — `backend/app/services/agent_runner.py`:**

1. `stream_one_on_one_message`'s call into `_stream_concierge` now passes
   `meta=meta` (previously omitted entirely).
2. `_stream_concierge` gained the `meta: dict[str, Any] | None = None`
   parameter and threads it to its own `self._llm.stream_chat(..., meta=meta)`
   call — the same gateway that already writes `meta["stream_error"]` on a
   non-200 reply (round 2's fix), now reachable from THIS call site too.
3. The `except Exception as exc:` branch (the outage/ConnectError case) now
   also writes `meta["stream_error"] = f"{type(exc).__name__}: {exc}"[:400]`
   before yielding the scripted fallback — so a swallowed transport failure
   sets the same structural signal an in-band error already would, and
   `one_on_one.py`'s existing refund check (unchanged) fires on both.

No string-matching added anywhere; the fix extends the existing
`stream_error` channel to a call site and a failure branch it previously
never reached.

**Tests + output.** Four new tests added to
`test_def113_one_on_one_credit_gate.py`, all driving the REAL `LLMGateway` +
a REAL `OpenAICompatibleProvider` (registered as `VLLMProvider`, the live
provider preference) with `httpx.MockTransport` — the auditor's exact probe
shape, not a monkeypatched `stream_one_on_one_message` (which round 2's own
tests used and which the auditor noted "never exercise the real provider…
they never exercise the real call chain"):

- `test_concierge_real_provider_http_503_is_refunded_not_billed` — HTTP 503,
  charged=0 (was 1).
- `test_concierge_real_provider_connect_error_is_refunded_not_billed` —
  `httpx.ConnectError`, charged=0 (was 1).
- `test_concierge_real_provider_success_still_bills_normally` — control: a
  real, successful streamed reply still bills normally, proving the `meta`
  thread-through cannot turn a genuine success into a false refund.

```
tests/unit/test_def113_one_on_one_credit_gate.py
14 passed in 5.65s     EXIT=0   (was 11 at round 2 — 3 new; 1 pre-existing
                                  round-2 sentinel test in this file is unchanged)
```

**Mutation evidence (reverted immediately after, restored file re-verified green):**

Reverted both changes to `agent_runner.py` (dropped `meta=meta` from the
call into `_stream_concierge`; dropped the parameter and the
`meta["stream_error"]` write inside it — i.e. exactly round 2's code):

```
test_concierge_real_provider_http_503_is_refunded_not_billed          FAILED (10 == 13, not refunded)
test_concierge_real_provider_connect_error_is_refunded_not_billed     FAILED (10 == 13, not refunded)
2 failed, 12 passed
```

Both fail reproducing the auditor's exact numbers (balance short by the
3-credit cost, i.e. charged not refunded). Restored, re-ran:
`14 passed in 5.65s, EXIT=0`.

### MAJOR-3 — the Brief refund blocked the event loop; the DEF200 ratchet was red (fixed)

**The claim.** Round 2's fix added a synchronous `refund(...)` call inside
`brief.py`'s `async def event_stream`'s `finally` block. `refund()` opens a
sync DB session and runs `SELECT … FOR UPDATE` + an `UPDATE` + a ledger
insert — real blocking I/O, now additionally able to WAIT on another holder
of the same user's row lock (round 3's own MAJOR-1 fix made the lock
meaningful) — directly on the single uvicorn worker's event loop, stalling
every other request and every other open SSE stream, worst exactly when the
provider is failing and many streams hit the refund branch simultaneously.
`test_def200_ratchet.py::test_no_new_handler_blocks_the_event_loop` failed at
`ae468eff` (`brief.py::event_stream` newly flagged) and passed at `0accfeed`
— **the DEF200 ratchet was red on `main` before this fix.**

**Fix — `backend/app/api/brief.py`:**

1. The `refund(...)` call in `event_stream`'s `finally` is now
   `await run_in_threadpool(refund, current_user.id, cost,
   reason=f"brief_failed:{req.session_id}")` — same idiom `auth.py`'s DEF183
   fix already uses in this codebase.
2. **Extended beyond the letter of the assignment, and why:** the census
   (`backend/scripts/def200_sync_io_census.py`) marks a WHOLE handler
   "mitigated" the moment it contains ANY `run_in_threadpool(...)` call
   anywhere in its body (including inside a nested closure) —
   `_already_threadpooled` walks the entire `AsyncFunctionDef` node, not a
   per-callsite check. Wrapping only `refund()` would have made the census
   stop flagging `brief.py::brief_message` entirely — silencing the ALSO
   pre-existing, ALSO-unwrapped `spend()` call earlier in the same handler
   (`brief.py:141`, present since DEF205, not introduced by this round) by
   accident of the guard's blind spot, not because it was fixed. Wrapped
   `spend(...)` the same way for the same reason it protects `refund(...)`,
   rather than "fix" the ratchet number by exploiting a gap in how it counts.
3. `tests/unit/test_def200_ratchet.baseline.json` — removed
   `"brief.py::brief_message"` from `flagged` (20 entries now, `<= 21` bound
   still holds); the census no longer flags it because BOTH sync DB calls in
   the handler are now genuinely off the loop, not because the guard stopped
   looking.

`one_on_one.py`'s own `refund()`/`spend()` call sites have the identical
shape (`send_message`/`event_stream`, both still on the ratchet's frozen
debt baseline) — checked, per the assignment, and left as pre-existing debt:
fixing them was not required by any MAJOR here and the auditor's own note
frames it as optional cleanup ("would let one baseline entry be removed"),
not part of this round's scope.

**Tests + output**
(`backend/.venv/bin/python -m pytest tests/unit/test_def200_ratchet.py tests/unit/test_def205_brief_credit_gate.py -q -p no:cacheprovider`):

```
12 passed in 11.00s    EXIT=0
```

`test_def200_ratchet.py` alone: `4 passed in 0.86s, EXIT=0` — all four,
including `test_the_baseline_shrinks_when_a_handler_is_fixed` (the baseline
edit above is what makes this one pass rather than fail).

**Mutation evidence (reverted immediately after, restored files re-verified green):**

1. Reverted `refund(...)` back to a bare synchronous call (round 2's exact
   code), `spend(...)` still wrapped:
   `test_no_new_handler_blocks_the_event_loop` → `FAILED`, flagging
   `brief.py::brief_message` and `brief.py::event_stream` both newly added
   (the census now sees BOTH unwrapped calls, since neither remaining
   `run_in_threadpool` call in the function masks it once `spend()` is also
   reverted) — `1 failed`.
2. Reverted `spend(...)` back to a bare synchronous call too (both calls now
   exactly as round 2 shipped them): same test, same failure, this time
   reproducing the auditor's own finding verbatim
   (`brief.py::event_stream` newly flagged).

Restored both, re-ran the full pair above: `12 passed in 11.00s, EXIT=0`.

### Full mandated test list, this round

```
backend/.venv/bin/python -m pytest \
  tests/unit/test_def200_ratchet.py \
  tests/unit/test_retro_security_credit_balance_lock_guard.py \
  tests/unit/test_def369_spend_takes_a_row_lock.py \
  tests/unit/test_def205_brief_credit_gate.py \
  tests/unit/test_def113_one_on_one_credit_gate.py \
  tests/unit/test_retro_pm_floor_round2.py \
  tests/unit/test_room_runner.py \
  tests/unit/test_safety_floor.py \
  tests/unit/test_def398_pm_json_contract_break.py \
  tests/unit/test_p15_check_then_insert_guard.py \
  tests/unit/test_config_compose_parity.py \
  tests/unit/test_registers_no_drift.py \
  tests/unit/test_p30_registers_name_things_that_exist.py \
  tests/unit/test_concierge_context_router.py \
  tests/unit/test_concierge_engine.py \
  tests/unit/test_concierge_live.py \
  tests/unit/test_brief_engine.py \
  -q -p no:cacheprovider

275 passed, 1 skipped in 140.57s     EXIT=0
```

**Unresolved / left for the auditor:** the real-Postgres re-measurement of
`pack_vs_spend`/`admin_vs_spend` under `populate_existing=True` (MAJOR-1);
the same real-provider MockTransport probes against the fix, run
independently (MAJOR-2); confirmation on melehost that the full suite is now
green at the promoted SHA, MAJOR-3's own claim being that it was NOT green at
`ae468eff` (MAJOR-3). `one_on_one.py`'s identical unwrapped
`spend()`/`refund()` shape is flagged above as checked-but-out-of-scope, not
silently missed.

SUBMITTED: round 3
