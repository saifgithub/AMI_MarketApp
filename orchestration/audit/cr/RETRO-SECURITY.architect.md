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

SUBMITTED: round 1
