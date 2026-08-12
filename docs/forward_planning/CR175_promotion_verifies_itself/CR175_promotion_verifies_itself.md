# CR175 — Make the promotion pipeline verify itself

**Status:** in_progress · **Filed:** 2026-08-12 · **Category:** infra · **Round:** AT:R68

> **ID note.** Filed first as CR173, re-minted to CR175 within the hour: CR173 (Floor v0.2) and
> CR174 (interactive lesson mode) were both taken by other lanes on the shared checkout while this
> was being scoped, and the `ls _registry/ | tail` used to pick the number was already stale by the
> time it ran. The overwritten CR173 row was restored from `HEAD` before anything was committed.
> This is the ID-collision race CLAUDE.md's single-minter rule exists to prevent, arriving from the
> one direction the rule does not cover — reading the high-water mark rather than being handed one.

> Saiful, 2026-08-12: *"you goal is now to ensure we no longer have issues with promots. There are
> many CRs held back until ypou are done."*

---

## Why

Every promotion incident this project has had shares one shape, and it is not the shape people
expect:

> **The promotion pipeline's own verification checked the wrong thing, or checked nothing, and
> reported green.** Not one incident was caused by the shipped code being wrong.

The incident record, all already fixed, each one evidence of a *class* rather than a one-off:

| Incident | What actually failed |
|---|---|
| **DEF038** (OIDC audiences) | Key populated on the Mac, never forwarded in compose. Feature dark for months. Nothing checked. |
| **DEF063** (Adanos + Alpha Vantage) | Same, twice more, for the entire life of CR023/CR024. `/v1/admin/config-check` exists because of this pair. |
| **DEF215** (2026-08-04) | Migrations ran *after* the new container was already serving. `init_schema()` raced Alembic → `DuplicateTable` → chain aborted → two later migrations never ran → **every journal read on live Alpha failed**. An outage in an already-shipped feature, caused by a migration for a different one. |
| **AT:R66 audit-lane** | A DEF231 round-2 MAJOR landed 13 min after submission, was never read, the flagged code shipped, and a false Verdict Board annotation stayed live 7 hours. Every input was available; nothing mechanical looked. |
| **DEF260** (2026-08-12) | A compose inline default `${VAR:-30}` silently overrode a `Settings` field the code believed it had changed. |
| **DEF271** (2026-08-12) | `prompt_quality_sweep.py` had been dead on import for four days. Six metrics unreachable across the whole Batch 1–9 programme. Nobody ran it to notice. |

Each fix was correct and each was **local to the instance**. None of them asked whether the
verification *layer* is sound. This CR asks that, and the answer measured below is: no.

---

## What was measured, 2026-08-12

Five findings, each verified against the tree or against live Alpha — not argued from the incident
list.

### F1 — The health check cannot fail

[`backend/app/main.py:465-467`](../../../backend/app/main.py):

```python
@app.get("/v1/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0", "env": settings.env}
```

A hardcoded literal. It touches no database, no Redis, no LLM, no schema revision.

This one endpoint is **both**:

- the container's only healthcheck probe — `docker-compose.yml:400-405`,
  `test: ["CMD", "curl", "-f", "http://localhost:8000/v1/health"]`; and
- the promotion's primary smoke check — `/promote-to-alpha` step 7, and step 5 *blocks* on
  `docker inspect … .State.Health.Status` reaching `healthy` before calling the deploy successful.

So "healthy" means **uvicorn is accepting connections** and nothing else. A container with an
unreachable Postgres, a dead Redis, a down vLLM, or a schema behind head reports `healthy`, passes
step 5, passes step 7, and the promotion is reported as successful. **DEF215's outage state is a
state this healthcheck reports as healthy** — the container logs a `db_schema_behind_head` ERROR
while the probe returns 200.

`"version": "0.1.0"` is a constant that has never moved. That is worse than absent: it occupies the
place an operator looks for a deploy identity and answers with a literal.

### F2 — Nothing records which commit is running

```
$ grep -rn "GIT_SHA\|git_sha\|BUILD_SHA\|IMAGE_TAG\|APP_VERSION" backend/app/core/config.py docker-compose.yml
(no matches)
```

No commit, tag, or build stamp reaches the container in any form. After a promotion there is **no
query that answers "is what is running what I shipped?"** Every incident diagnosis to date has begun
from the assumption that it is.

### F3 — The DEF038/DEF063 guard covers 9 of 98 fields, and misses the newest instance

`/v1/admin/config-check` (step 7b) reports a hand-written list, `_FEATURE_GATES` in
[`backend/app/api/admin.py`](../../../backend/app/api/admin.py). Live against Alpha, 2026-08-12:

```
env staging   dark_count 2
  ADANOS_API_KEY          True     ALPHA_VANTAGE_API_KEY  True
  VLLM_BASE_URL           True     KIMI_API_KEY           True
  USE_REAL_MARKET_DATA    True     ADMIN_SECRET           True
  RESEND_API_KEY          True     SENTRY_DSN             False
  POSTHOG_API_KEY         False
```

Nine gates. `Settings` has **98 fields**, 43 of them key/token/secret/URL-shaped. So the guard built
because a key silently failed to reach the container covers **9.2%** of the fields that could do it.

And the specific miss is the damning one: **`adanos_api_key_secondary` is not in the list.** That key
was wired *this session*, in CR143 Batch 4, precisely because 250 paid calls/month had sat idle
undetected — the DEF063 class, a third time. It reached compose, it reached `Settings`, and it is
**invisible to the check whose entire job is catching exactly that.** Nobody thought to add it,
because the list is hand-maintained and nothing fails when it is incomplete.

Adding it by hand would be the fourth instance of the same fix. The list has to stop being a list.

### F4 — The owning doc still prescribes the DEF215 order

`/promote-to-alpha` opens with: *"Read the full protocol in
`docs/initial_specs/10_delivery/promotion_protocol.md` before doing anything destructive. **That doc
owns the design**; this file is the operational checklist."*

That doc, §"What a promotion to Alpha actually does",
[lines 133-139](../../initial_specs/10_delivery/promotion_protocol.md), still reads:

> 6. `docker compose … up -d --build api-alpha` — rebuild and recreate the backend container.
> 7. Run any pending migrations: `docker compose exec api-alpha alembic upgrade head`.
>    Migration failure aborts the promotion **after** the new container is up.

That is the exact ordering that produced DEF215's outage. The slash command was reordered on
2026-08-04; **the doc that owns the design was not.** Its blocking-checks list (§"What must be true
before a promotion is allowed", items 1-5) also omits the hold gate (AT:R65) and the audit-lane gate
(AT:R66) entirely, and still states *"Currently 152 tests"* against a suite of 3,123.

An operator who does what the command tells them to do — read the owning doc first — is handed the
failure. **Filed as [DEF275](../../defect/def_list.md) and fixed in this CR's first commit**, because
it is docs-only, reversible, and live right now.

### F5 — The tag does not describe what shipped

rsync ships the **worktree** — including untracked files, excluding `.git`. The tag names a
**commit**. The only thing between the two is step 1's `git status --short`, which the command
*prints* and asks the operator to judge. There is no `exit 1`.

On this shared checkout, with three or more concurrent tracks, that command prints **21 lines right
now**, routinely, none of them mine. A gate whose failing state is the normal state is not a gate —
it is training to scroll past a failing check, which is the precise habit the command's own hold-gate
comment says it exists to break.

### F6 — The stamp describes the image; the running code is the bind mount

Found while building Tier C, and it changes what Tier A can honestly claim.

`docker-compose.yml`'s `api-alpha` service mounts:

```yaml
volumes:
  - ./backend/app:/app/app:ro
  - ./backend/tests:/app/tests:ro
  - ./backend/scripts:/app/scripts:ro
  - ./content:/content:ro
```

So **the Python uvicorn imports is the rsync'd host filesystem, not the image
contents.** `GIT_SHA` is baked at build time and answers *"which commit was this
image built from"* — it can never answer *"which bytes is the process running"*,
because the image's `app/` is shadowed by the mount. A partial rsync would leave
a stale mount under a current stamp, and the stamp would report it as fine.

This is not a reason to drop the stamp — without it there is no identity at all.
It is the reason Tier C carries a **`tree`** check: an `rsync --dry-run
--itemize-changes` against melehost, which answers the second question directly
and is the only check that catches a partial sync. The two together are what F2
actually needs; either alone overclaims.

It is also what makes Tier D's BLOCKING set *derivable* rather than guessed — a
change under `backend/app` or `content/` is live on the box the moment the rsync
lands, with no rebuild involved at all.

### F7 — The audit-lane gate conflates two different failures

Measured while running this CR's own preflight, 2026-08-12:

```
$ orchestration/dispatch/dispatch.sh inbox
!! NO AUDITOR WATCHER — last poll 43265s ago (limit 90s), never exited cleanly.
inbox clear — no verdict awaiting integration, no submission of yours undelivered.
$ echo $?
1
```

Read `dispatch.sh` and the two conditions are explicitly separate — `hot` counts
verdicts and undelivered submissions, `dead` counts stale watcher heartbeats,
and **either** returns 1:

```sh
[ "$hot" -gt 0 ] && return 1
[ "$dead" -gt 0 ] && return 1
```

Here `hot=0`. The gate fired entirely on `dead`, i.e. on *"no auditor process
has polled for 12 hours"* — and `dispatch.sh`'s own comment says what that
condition is for: *"Restart it before you **submit** anything else."* It is a
warning about work that would sit unserved, not a statement about the code being
promoted.

The gate the promotion protocol wanted (AT:R66) is *"has an auditor already told
you this code is broken?"*, and that answer is **no**. The gate it got also
blocks on the audit fleet being idle, which is the normal state whenever nobody
is running an audit.

**This is F5's shape again, one layer up**: a gate that fires for a reason other
than the one it was built to catch teaches the operator that firing does not
mean stop. Left alone it will be reasoned past, exactly once, on the day it
matters.

**Not fixed unilaterally.** Loosening a safety gate is Saiful's call, not a
side-effect of another CR, and this CR is specifically about not reasoning past
gates. Recommended fix, for his decision: split the exit codes — `1` for a
verdict or an undelivered submission (abort the promotion), `2` for a dead
watcher (warn, and abort only a *submission*). The promotion gate would then
test for `1`.

### F8 — The one manual gate asks about a machine that does not exist

`/promote-to-alpha` step 1 ends by asking the operator:

> "Did you click through onboarding on **the local backend** just now, end to
> end? (y/n)"

`n` aborts; it is described as *"the only manual gate — keeps the operator
honest."* But `promotion_protocol.md` and `CLAUDE.md` both state, emphatically,
that **the Mac runs no backend, no database, no services** — that is a deliberate
architectural decision, not an accident of setup. There has been no local backend
to click through since well before this session.

So the question cannot be answered truthfully by anyone. Whoever answers `y` is
answering some other question they substituted for it, which is the worst
possible state for the single gate that exists to keep the operator honest.

Fixed here, because it is one sentence and reversible: the question now asks
what is actually available to check — that the change was exercised end-to-end
against Alpha, or that it is backend-only with no client-visible surface.

---

## The through-line

F1, F3 and F5 are the same defect in three places: **a check that reports green regardless of the
state it claims to check.** F2 is why every one of them is expensive — with no deploy identity, an
incident cannot even establish what was running. F4 is the same failure applied to the documentation
layer: the fix landed in the checklist and not in the doc the checklist defers to.

`failure_patterns.md` P16 names this for measurements — *"a count nobody read is not a
measurement."* The promotion pipeline needs the deployment form of it: **a check that cannot fail is
not a check.**

---

## Scope

### Tier A — make the deploy identifiable and the health signal honest *(this is the core)*

1. **Stamp the commit into the image.** `GIT_SHA` + `ALPHA_TAG` as compose build args → `Settings`
   → surfaced. `/promote-to-alpha` passes the tag and hash it just computed. Fails **loudly** if
   absent in `staging` (CR040) — an unstamped container in Alpha is a promotion that did not go
   through the protocol.
2. **Split liveness from readiness.** `/v1/health` stays a liveness probe (that is a legitimate role
   for the container healthcheck, and changing it would change restart behaviour) but stops lying:
   the constant `"version": "0.1.0"` is replaced by the real stamp. A new **`/v1/ready`** actually
   probes: DB reachable, Redis reachable, `alembic current == head`, LLM provider resolved. **The
   promotion checks `/v1/ready`, not `/v1/health`.**
3. Fix `docker-compose.yml`'s healthcheck comment to say what it does and does not cover, so the
   next reader is not misled the way this one was.

### Tier B — the config gate stops being a hand-written list

4. **Derive the gate set from `Settings`**, the same source `test_config_compose_parity.py` already
   walks, so a field added tomorrow is covered the day it is added. `_FEATURE_GATES` survives as an
   *annotation* table (human prose for `effect_when_unconfigured`) over an auto-derived field list;
   an unannotated field still reports its `configured` bool rather than being absent.
5. **A unit test that fails when a `Settings` field appears in neither the derived set nor an
   excused list** — the same structural shape that makes `test_config_compose_parity.py` work,
   applied one layer out. This is what closes F3 permanently instead of adding
   `adanos_api_key_secondary` by hand and waiting for the fifth instance.

### Tier C — step 7/7b becomes an exit code, not an eyeball

6. **`scripts/promotion/postflight.py`** — one command, one exit code, run from the Mac after the
   swap. Asserts: deployed `GIT_SHA` == the promoted commit; `alembic current` == head (parsed, not
   read); `/v1/ready` green on every probe; **every uncommented non-empty key in `infra/alpha.env`
   reads `configured: true`** (the automated set-diff that F3 shows no human reliably performs
   across 40+ keys); LLM provider `vllm` with `has_real_provider`; quote source not `mock_walk`.
   Prints the diff on failure, names the compose line to add.
   **Booleans and names only — it never echoes a value** (`infra/alpha.env` is gitignored and stays
   unechoed).

### Tier D — the preflight tree gate becomes enforceable

7. Replace the printed `git status --short` with a check scoped to **what actually ships**: tracked
   modifications and untracked files under the rsync'd paths, failing closed, naming each file. A
   dirty tree that does not change what ships must pass silently, or the gate returns to being
   ignored — which is the state F5 measured.
8. The promotion report records the shipped-tree identity (tag + hash + any deviation), so the
   deployment audit log stops implying a cleanliness the rsync never verified.

### Tier E — the owning doc *(DEF275, ships first)*

9. Rewrite `promotion_protocol.md` §"What a promotion to Alpha actually does" and §"What must be
   true before a promotion is allowed" to match the shipped command: migrations before the swap, both
   gates listed, the test count claim removed rather than re-pinned to a number that will go stale
   again.

### Out of scope

- **Beta/Prod promotion paths** — stubbed, no GCP project. Tier A's stamp is designed so those
  inherit it, but nothing is built for them here.
- **Rolling back automatically.** `/rollback-alpha` stays a deliberate act (the command is explicit
  about this and it is right).
- **CI.** No GitHub Actions; promotions stay slash-command-triggered. This CR makes the checks
  machine-verifiable, which is the prerequisite for CI if that is ever wanted — it does not add it.

---

## Constraints

- **CR040 — degrade loudly.** Every new setting added here must be forwarded in `docker-compose.yml`'s
  `api-alpha` block or `test_config_compose_parity.py` fails the build. This CR is *about* that rule;
  it does not get to break it.
- **DEF260's shape.** Do not add a compose inline default (`${VAR:-x}`) for any new key — that is the
  silent-override the parity test's third direction was added to catch.
- **The Mac runs nothing.** Every claim about the deployed container is verified against melehost or
  against live Alpha, never inferred from the Mac.
- **`infra/alpha.env` is gitignored.** Referenced by key name, never echoed, in code and in docs.
- **Shared checkout.** Pathspec-commit only.

---

## Acceptance

The gate for this CR is not "the checks exist" — that is the mistake F1 and F3 already are. It is
**each new check demonstrated failing against a real broken state before it is trusted**:

1. **F1** — with the schema deliberately behind head on a throwaway container, `/v1/health` still
   returns 200 (proving the old signal was blind) **and `/v1/ready` returns non-200**. Both halves
   recorded.
2. **F2** — `/v1/ready` on live Alpha reports a `git_sha` that matches `git rev-parse HEAD` at the
   promoted tag, verified by comparison, not by inspection.
3. **F3** — the derived gate set covers `adanos_api_key_secondary` **without anyone adding it by
   hand**, and the new unit test goes **red against the pre-fix `_FEATURE_GATES`** before it goes
   green. A guard that was never seen failing is not known to work.
4. **Tier C** — `postflight.py` exits non-zero against a deliberately mismatched key (one populated
   in `infra/alpha.env` and removed from the compose block in a scratch copy), and names the missing
   compose line in its output.
5. **Tier D** — the preflight gate passes on today's real 21-line dirty tree (none of which ships a
   behaviour change) and fails on a tracked modification under `backend/`.
6. **DEF275** — the protocol doc's promotion sequence matches `/promote-to-alpha` step by step,
   checked line against line, both gates present.
7. The next real promotion runs end-to-end through the new postflight and its output is recorded in
   this folder — **including whatever it finds**, which on the evidence above is unlikely to be
   nothing.

**Not claimed on merge:** that promotions become incident-free. This CR makes the pipeline's own
verification honest about what it checked. An honest check that reports a real failure is the
deliverable; a promotion that never fails again is not something a verification layer can promise.
