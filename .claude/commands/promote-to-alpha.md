---
description: Promote the current Mac canonical state to the Alpha environment (melehost). Runs the blocking checks, tags the commit, rsyncs to the Ubuntu host, recreates the api-alpha container, runs migrations, smoke-checks the public hostname.
---

# /promote-to-alpha

Promote the current state of the canonical Mac worktree to the Alpha
environment running on `melehost` (Ubuntu Linux server at
`192.168.20.59`, public hostname `https://api-alpha.agenticmarketintel.ai`).

**Read the full protocol in `docs/initial_specs/10_delivery/promotion_protocol.md`
before doing anything destructive.** That doc owns the design;
this file is the operational checklist.

## What to do, in order

Run every step in order. If any step fails or produces an unexpected
result, **stop and explain to the user what happened** — don't try to
auto-recover. The user decides whether to abort, fix, or continue.

### 1. Preflight — blocking checks

Run these from the current worktree root. Any failure aborts.

```bash
# HOLD GATE (AT:R65) — runs FIRST. A green suite does not mean promotable.
# Scoped to the "## ACTIVE HOLDS" section only: a bare `grep '^### '` also matched
# the cleared-hold history kept in the same file, which would have wedged the gate
# shut forever and taught the operator to reason past it. Fails CLOSED if the file
# is unreadable or the section heading is missing.
HOLDS=$(awk '/^## ACTIVE HOLDS/{a=1;next} /^## /{a=0} a&&/^### /{print}' infra/PROMOTION_HOLD.md 2>/dev/null)
if [ -f infra/PROMOTION_HOLD.md ] && ! grep -q '^## ACTIVE HOLDS' infra/PROMOTION_HOLD.md; then
  echo "PROMOTION HOLD FILE MALFORMED — no '## ACTIVE HOLDS' section. Aborting."
  exit 1
fi
if [ -n "$HOLDS" ]; then
  echo "PROMOTION HOLD ACTIVE — aborting. Holds:"
  echo "$HOLDS"
  exit 1
fi

# AUDIT-LANE GATE (AT:R66) — runs SECOND, before the suite, because a green
# suite says nothing about whether an auditor has already told you this code is
# broken. `inbox` exits 1 on a verdict awaiting integration or a submission of
# yours that never reached the auditor. Fails CLOSED if the script is missing.
if [ -x orchestration/dispatch/dispatch.sh ]; then
  if ! orchestration/dispatch/dispatch.sh inbox; then
    echo "AUDIT LANE NOT CLEAR — aborting. Read the verdict above before promoting."
    exit 1
  fi
else
  echo "dispatch.sh missing or not executable — cannot verify the audit lane. Aborting."
  exit 1
fi

# TREE GATE (AT:R68 CR175 Tier D) — runs THIRD. `git status --short` used to be
# printed here for the operator to judge, with no exit code behind it. On this
# shared checkout that prints ~20 lines routinely from other lanes (measured
# 2026-08-12: 21, none the promoter's), so its failing state WAS its normal
# state and it was read as noise. This classifies instead of blanket-failing:
# BLOCKING = paths that reach the running container (derived from
# docker-compose.yml's api-alpha build context + bind mounts), SHIPPED = rsync
# copies it but the container never reads it, NOT SHIPPED = excluded.
# Fails closed only on BLOCKING.
python3 scripts/promotion/preflight_tree.py || {
  echo "TREE GATE — uncommitted code would ship under a tag that does not describe it. Aborting."
  exit 1
}

git status --short
git log --oneline -1
pytest backend/tests/unit/ -q
flutter analyze --no-fatal-infos
```

**The audit-lane gate is not advisory either, and it exists because of a
specific failure (AT:R66, 2026-08-08).** A DEF231 round-2 audit returned a
MAJOR **13 minutes** after the submission was pushed. The architect never read
it — promoted straight off the submission, discovered the *round-1* verdict by
accident during this preflight, and left a reproducible false annotation on the
live Verdict Board for **7 hours**. Every input to that mistake was available:
the verdict was committed, it was on origin, and `dispatch.sh inbox` would have
exited non-zero. Nothing mechanical checked. Now something does. If it fires,
read the verdict — an AWAITING_FIXES on the code you are about to ship is
exactly the case where "the tests are green" is the wrong question.

**The hold gate is not advisory.** `infra/PROMOTION_HOLD.md` exists for the case where `main` is
green, audited, and still must not ship — typically a backend change whose *client* half is on `main`
but not yet on any device. Backend promotion is an rsync; the Flutter half is a store release, and
those are days apart. If a hold is listed, **stop and surface it to the user** — do not reason your
way past it, and do not promote "just the other files" (the rsync ships the whole tree). Only the
user clears a hold, and only against the precondition the hold names.

- The **tree gate** is the enforced half; `git status --short` below it is
  context for the operator, not the check. The gate blocks only on paths that
  reach the container — `backend/`, `content/`, `docker-compose.yml`, `infra/` —
  because those are bind-mounted or built in, so an rsync ships them live under
  a tag that does not describe them. Everything else it prints as *recorded*.
  If it blocks: commit, stash, or promote from a clean checkout. Do not
  `--force` past it; there is deliberately no such flag.
- `git log` — capture the short hash + commit subject. You'll need it
  for the summary at the end.
- pytest must exit 0. Surface the failure summary if not.
- flutter analyze must exit 0. The pre-existing
  `assets/icons/ doesn't exist` warning is OK; only block on real
  issues. (If `flutter` isn't installed or available at the path, ask
  the user how they want to handle that — usually `cd mobile` first.)

Then **ask the user one yes/no question** (don't auto-confirm):

> "Has this change been exercised end to end — against Alpha, or on a
>  device — or is it backend-only with no client-visible surface? (y/n)"

`n` aborts the promotion. `y` means the operator is taking
responsibility for the smoke test.

**The wording changed at AT:R68 (CR175 F8) and the reason matters.** It used to
ask *"Did you click through onboarding on **the local backend** just now?"* —
and `promotion_protocol.md` and `CLAUDE.md` both state, emphatically, that the
Mac runs **no backend, no database, no services**. There has been no local
backend to click through for a long time, so the question could not be answered
truthfully by anyone: whoever answered `y` was answering some other question they
had quietly substituted for it. That is the worst possible state for the one
gate whose entire job is keeping the operator honest. It now asks something that
is actually available to check.

### 2. Compute the next tag

```bash
TODAY=$(TZ='Asia/Kuala_Lumpur' date +%Y-%m-%d)
PREV_TAGS=$(git tag --list "alpha-${TODAY}-*" --sort=-version:refname)
# N = highest existing sequence + 1, or 1 if none today.
```

Tag format: `alpha-YYYY-MM-DD-N` (e.g., `alpha-2026-05-12-3`). N is
the per-day sequence in Saiful's local timezone (`Asia/Kuala_Lumpur`).

```bash
git tag alpha-${TODAY}-${N}

# CR175 F2 — the deploy identity. EXPORT these; steps 5 and 7c both read them.
# Until this existed nothing recorded which commit was running, so every
# incident diagnosis began by assuming it was the one you meant to ship.
export ALPHA_TAG="alpha-${TODAY}-${N}"
export GIT_SHA="$(git rev-parse HEAD)"
```

The tag is local by default. A GitHub remote (`origin`) exists now, so
push it if you want the `alpha-*` tag backed up
(`git push origin alpha-${TODAY}-${N}`) — promotion itself doesn't push
tags, and the deploy to melehost is rsync (not a git pull), so pushing
the tag is optional.

### 3. Rsync to melehost

The canonical worktree to copy is wherever the user invoked this
command — usually `/Volumes/Extreme Pro/AMI_MarketApp/.claude/worktrees/magical-edison-18bf91/`
or similar.

```bash
rsync -az --delete \
  --exclude='.env' \
  --exclude='.venv' \
  --exclude='__pycache__' \
  --exclude='.dart_tool' \
  --exclude='*.egg-info' \
  --exclude='.pytest_cache' \
  --exclude='.local.db*' \
  --exclude='mobile/' \
  --exclude='.claude/' \
  --exclude='.git' \
  --exclude='.idea' \
  --exclude='.vscode' \
  --exclude='website/' \
  --exclude='audit/' \
  --exclude='reports/' \
  --exclude='backtest_results/' \
  ./ \
  melehost:~/ami_trade/
```

**`audit/`, `reports/` and `backtest_results/` MUST be excluded (DEF081, DEF276).** They are **melehost-generated
runtime data not present in the Mac source** — `reports/` is the CR051 daily-usage
analytics output, `audit/handshake/runs/*` are audit run histories. Without these two
excludes, `--delete` wipes them off the host (134 files in the AT:R64 promote). They are
not backend runtime; the container never reads them. Never let `--delete` destroy them.

**`backtest_results/` is DEF276 — the same class, found three weeks later.** It arrived with
CR164's harness and inherited none of DEF081's reasoning, because that fix was a *list*, not a
rule. `docker-compose.yml` bind-mounts `./backtest_results:/backtest_results:rw`, the container
writes sweep results there as uid 1001, and the Mac has no such directory — so `--delete` flagged
all of it, including the 40-pair replay that closed DEF230's controlled arm.

**The rule, so the next one does not need its own defect:** *any path bind-mounted `rw` into a
container is host-generated and must be excluded from `--delete`.* That is derivable from
`docker-compose.yml` rather than from memory. Today `backtest_results` is the only `rw` bind mount;
named volumes (`bug_attachments`) live outside the rsync path and are unaffected.

**`.env` MUST be excluded from rsync.** rsync has no default dotfile
exclusion. Without `--exclude='.env'`, the rsync would overwrite the
deployed env file — see step 4 for the canonical mechanism that
replaces this footgun.

### 4. Ship the canonical env file (Mac → melehost)

The Mac holds the canonical Alpha env at `infra/alpha.env` (gitignored,
populated). `scp` it into place. This is THE mechanism for moving env
values; rsync step 3 explicitly excludes `.env` so this step is the
only path.

`infra/alpha.env` is **gitignored**, so when this command runs from a
`.claude/worktrees/<name>/` checkout the file won't be present locally —
only the main worktree carries it. The block below auto-sources from
the main worktree in that case (`git worktree list` gives us the path),
so promoting from any worktree just works.

```bash
# Auto-source from the main worktree if missing locally (gitignored
# files don't carry across worktrees). `cut -d' ' -f2-` rather than
# awk so paths with spaces (`/Volumes/Extreme Pro/...`) don't get
# truncated.
if [ ! -f infra/alpha.env ]; then
  MAIN_WORKTREE=$(git worktree list --porcelain | grep '^worktree ' | head -1 | cut -d' ' -f2-)
  if [ -n "$MAIN_WORKTREE" ] && [ -f "$MAIN_WORKTREE/infra/alpha.env" ] && [ "$MAIN_WORKTREE" != "$(pwd)" ]; then
    cp "$MAIN_WORKTREE/infra/alpha.env" infra/alpha.env
    echo "auto-sourced infra/alpha.env from $MAIN_WORKTREE"
  fi
fi

# Abort if still missing (no main worktree copy either).
if [ ! -f infra/alpha.env ]; then
  echo "ERROR: infra/alpha.env missing — see infra/README.md to seed it"
  echo "       (scp melehost:~/ami_trade/.env infra/alpha.env, then re-run)"
  exit 1
fi

scp infra/alpha.env melehost:~/ami_trade/.env
```

Then verify the critical keys landed on melehost:

```bash
ssh melehost "grep -E '^(VLLM_BASE_URL|VLLM_MODEL|USE_REAL_MARKET_DATA|CF_TUNNEL_TOKEN|AMI_ENV|SECRET_KEY)' ~/ami_trade/.env | sed 's/=.*/=<set>/'"
```

Expect all six to read `<set>`. Anything missing → stop, fix the
canonical file on the Mac, re-promote. **Do not edit melehost's `.env`
in-place** — the next promotion will overwrite it.

`AMI_ENV` + `SECRET_KEY` were added by AT:R25 Phase 1.5. Without them the
backend either boots with all security lockdowns disabled (AMI_ENV=local
default — silent regression) or refuses to start (AMI_ENV=staging without
a non-default SECRET_KEY — explicit failure). See `backend/app/main.py`
boot check.

If you're rotating a key: edit `infra/alpha.env` on the Mac first, then
run this command. The rotation flows Mac → melehost as a side-effect of
promotion.

### 5. Recreate the backend container on melehost

**Migrations run BEFORE the new container serves anything.** Build the
image, run the chain against the live DB in a throwaway container, and
only start the real one once it reports head:

```bash
# GIT_SHA/ALPHA_TAG must reach the REMOTE shell — they were exported on the Mac
# in step 2, and ssh does not carry them. Without them compose falls back to
# `unset`, the container ships unstamped, and step 7c's identity check fails
# loudly rather than the stamp silently meaning nothing.
ssh melehost "cd ~/ami_trade && GIT_SHA='${GIT_SHA}' ALPHA_TAG='${ALPHA_TAG}' docker compose --profile tunnel build api-alpha"
ssh melehost "cd ~/ami_trade && docker compose run --rm --no-deps api-alpha alembic upgrade head"
```

If that fails, **stop here** — the old container is still up and serving
the schema it was built for, which is the whole point of doing it in this
order. Surface the error and let the user decide between fix-forward and
abandoning the promotion. Do not start the new container on a schema its
code does not match.

Then swap:

```bash
# GIT_SHA/ALPHA_TAG again — `--build` rebuilds here too, and a rebuild without
# them re-bakes `unset` over the stamp step 5's build just applied.
ssh melehost "cd ~/ami_trade && GIT_SHA='${GIT_SHA}' ALPHA_TAG='${ALPHA_TAG}' docker compose --profile tunnel up -d --build api-alpha"
```

The `--profile tunnel` keeps the cloudflared service running.
`--build` rebuilds the image (picks up backend code changes). Only
the `api-alpha` service is recreated — Postgres, Redis, and the
tunnel keep running so the public hostname stays live during the
swap.

Wait for the new container's healthcheck to pass before considering
the deploy successful:

```bash
ssh melehost "docker inspect ami_api_alpha --format '{{.State.Health.Status}}'"
```

Block until it returns `healthy` (poll every 2s for up to ~30s).
If it never reports healthy, surface the container logs:

```bash
ssh melehost "docker logs ami_api_alpha --tail 50"
```

…and stop. The user decides whether to investigate or roll back.

### 6. Confirm the schema is at head

Migrations already ran in step 5, before the new container served
anything. This step only verifies:

```bash
ssh melehost "cd ~/ami_trade && docker compose exec -T api-alpha alembic current"
```

Expect `<revision> (head)`. Anything else means the running code and the
schema disagree — the container's own logs will carry a
`db_schema_behind_head` ERROR naming both revisions.

**Why the order matters (DEF215, 2026-08-04).** This step used to be
where migrations ran, *after* the container was already up and serving.
`init_schema()` fired on the first request, `create_all()` built the new
CR's tables behind Alembic's back without stamping, and `alembic upgrade
head` then died on `DuplicateTable`. Alembic aborts the whole chain, so
two later migrations that only ALTER `journal_entries` never ran, and
**every journal read on live Alpha failed** on a missing column — an
outage in an already-shipped feature, caused by a migration for a
different one. Both halves are now fixed: `init_schema()` creates
nothing on a database that has `alembic_version` (Alembic owns the
schema; `create_all` is for fresh test fixtures), and migrations run
against the live DB while the OLD container is still serving.

A failed migration is **not auto-rolled-back** — surface the error and
ask the user whether to roll back or fix forward.

### 7. Smoke check the public hostname

```bash
# Health endpoint
curl -fsS https://api-alpha.agenticmarketintel.ai/v1/health

# LLM provider — should be vllm with has_real_provider=true.
# The WHOLE /v1/llm router is admin-gated — `APIRouter(..., dependencies=[
# Depends(get_admin)])` at api/llm.py:27 — which is CR123's C2 fix (an
# unauthenticated LLM proxy was reachable from the internet). This step used to
# curl it bare and could therefore NEVER pass: it returns 403, every time, on a
# perfectly healthy deploy. A smoke check that always fails teaches the operator
# to scroll past a failing smoke check, which is the same "reason your way past
# a gate" habit the hold gate above exists to break. Corrected AT:R66 while
# promoting DEF252.
ADMIN_SECRET=$(grep -E '^ADMIN_SECRET=' infra/alpha.env | cut -d= -f2-)
curl -fsS -H "Authorization: Bearer ${ADMIN_SECRET}" \
  https://api-alpha.agenticmarketintel.ai/v1/llm/status

# Real market data — source is the LEAF that actually served the price:
#   "yfinance"  the current provider (market_data.py:490)
#   "yahoo"     the legacy keyless-endpoint provider
#   "mock_walk" when the live feed 429'd / errored and we fell through
# (Not the stack name — see commit 83d32a7.) The Flutter LIVE/MOCK pill
# substring-matches BOTH "yfinance" and "yahoo"
# (trade_ticket_sheet.dart:626-627), so either reads as LIVE. Only
# "mock_walk" should show MOCK. Verified AT:R65 against a live Alpha
# response — this line previously named "yahoo" alone and read as a
# defect when the API correctly returned "yfinance".
curl -fsS https://api-alpha.agenticmarketintel.ai/v1/sim/quote/AAPL
```

All three must return 200 with sensible bodies. If any returns
non-200 or shows an unexpected shape (e.g., `active_provider=mock`),
surface the diff to the user and stop — the deploy is technically
done but smoke failed; the user decides next step.

### 7b. Config-gate check — catch silently-dark features (CR040)

Twice a shipped feature ran dead in Alpha because its key never reached
the container (DEF038 OIDC audiences; DEF063 Adanos + Alpha Vantage,
dark for the entire life of CR023/CR024). Nothing in this protocol would
have noticed. This step does.

```bash
ADMIN=$(grep '^ADMIN_SECRET=' infra/alpha.env | cut -d= -f2-)
curl -fsS -H "Authorization: Bearer ${ADMIN}" \
  https://api-alpha.agenticmarketintel.ai/v1/admin/config-check
```

Returns each config-gated feature, whether it is `configured` in the
running container, and what silently happens when it isn't. **Booleans
only — it never echoes secret values.**

Compare against intent: every key **populated (uncommented) in
`infra/alpha.env`** must read `configured: true`. A key that is set on
the Mac but `false` in the container is exactly the DEF038/DEF063 bug —
its `${VAR}` line is missing from the `api-alpha` environment block in
`docker-compose.yml`. Stop and fix the compose line; do not hand-edit
melehost.

`dark_count` is informational, not a failure: features are legitimately
off when their key is deliberately parked (Adanos and Alpha Vantage are
parked pending a metered-tier budget decision — see DEF063). The failure
condition is a **mismatch between alpha.env and the container**, not a
non-zero count.

Note the commit-time guard already ran in step 1: `pytest` includes
`test_config_compose_parity.py`, which fails if any `Settings` field is
neither forwarded nor explicitly excused. This step catches what the
static test can't — the deployed container's actual state.

### 7c. Postflight — the checks that end in an exit code (CR175 Tier C)

Steps 7 and 7b above end in *"compare this against intent"*. Six of the eight
steps in this command used to end in operator judgement, and 7b in particular
asked a human to set-diff ~40 keys in a gitignored file against a JSON response,
by eye, after a deploy. Measured 2026-08-12: nobody had ever noticed that the
response covered **9 of 98** `Settings` fields (CR175 F3). That is not an
attention failure — it is a check whose correct execution was never mechanically
possible.

```bash
python3 scripts/promotion/postflight.py \
  --expect-sha "${GIT_SHA}" --expect-tag "${ALPHA_TAG}"
```

Five checks, one exit code:

| check | what it answers | why it exists |
|---|---|---|
| `identity` | is the container running the commit + tag you just promoted? | CR175 F2 — nothing recorded this, so every diagnosis began by assuming it |
| `tree` | does melehost hold what this worktree holds? (`rsync --dry-run`) | the stamp describes the **image**; `./backend/app` and `./content` are bind-mounted, so the running Python is the host filesystem. Only this catches a partial rsync |
| `readiness` | `/v1/ready`: DB, schema at head, LLM resolved | DEF215's outage state is one `/v1/health` returns 200 for |
| `config` | every populated key in `infra/alpha.env` reads `configured: true` | DEF038, DEF063 — the set-diff no human performs reliably |
| `market` | quote source is not `mock_walk` | a silent fall-through to a random walk |

**Exit codes are three, not two, and the distinction is load-bearing:**

- `0` — every check passed.
- `1` — a check **failed**. The promotion completed and something is wrong with
  it. Fix forward or `/rollback-alpha`.
- `2` — a check **could not run** (network, missing file, an endpoint the
  container does not have). **This is not a pass.** "The promotion is broken"
  and "I could not tell" must never look the same to whoever reads the output —
  that conflation is most of this CR's incident record.

Two operational facts it encodes, both measured rather than assumed:

- **Cloudflare 403s the `Python-urllib` User-Agent at the edge**, before the
  request reaches the tunnel. The same URL returns 200 under `curl` and 403
  under stock urllib, with `server: cloudflare` on the failure. Any Python
  tooling hitting the public hostname needs its own UA; this script sends
  `ami-postflight/1.0 (CR175)`.
- The CF edge blips. A transient 502 while the backend is demonstrably serving
  (checked against `docker logs` — live client traffic still 200) reports as
  `COULD NOT RUN`, not as a failed promotion.

**Do not treat a green step 7/7b as a substitute for this.** They report; this
decides.

### 8. Report the outcome

Print a short summary like:

```
Promoted to Alpha — alpha-2026-05-12-3 (a1b2c3d — "fix(compose): pass vLLM env")
  • rsync (code): 28s
  • scp infra/alpha.env: <1s, 4/4 keys verified
  • build + recreate: 47s
  • migrations: no changes
  • smoke: /v1/health 200 · /v1/llm/status vllm · /v1/sim/quote AAPL $221.27 (source=yahoo)
  • postflight: PASSED (identity · tree · readiness · config · market)
  • tree at promote time: 0 blocking, 25 shipped-not-runtime (recorded)
Total elapsed: 1m 23s
```

**Record the tree line even when it is zero.** F5 was that the tag names a
commit while the rsync ships a worktree; saying which is which in the summary is
what stops the deployment log from implying a cleanliness nothing verified.

## What NOT to do

- **Don't delete prior tags.** Tags are permanent; the deployment
  audit log lives there.
- **Don't auto-rollback on failure.** Always surface and let the
  operator decide. `/rollback-alpha` is a separate, deliberate act.
- **Don't recreate Postgres or Redis.** Only the `api-alpha` service.
  The volumes carry the alpha-tester state.
- **Promotion doesn't auto-push tags.** A GitHub remote (`origin`) exists; push `alpha-*` tags manually if you want them backed up — it's not part of this flow (deploy is rsync, not a git pull).
- **Don't sync `mobile/`, `.git/`, `.claude/`** to melehost — they
  bloat the rsync and aren't needed there.
- **Don't touch any worktree other than the one you were invoked
  from.** The canonical Mac may have multiple worktrees in
  `.claude/worktrees/`; each is independent.

## When something goes sideways

Common failure modes and what to do:

| Symptom | Action |
|---|---|
| `git status --short` shows untracked file you don't recognise | Show it to the user, ask whether to add to `.gitignore` or commit it. Don't auto-decide. |
| pytest red | Print the test summary; ask the user to fix before retrying. |
| ssh melehost fails | Check `~/.ssh/config` has `melehost` entry; check the host is up (`ping melehost`). Don't try to "fix" SSH automatically. |
| Container won't go healthy | Show the last 50 lines of `docker logs ami_api_alpha`. Likely: bad env var, missing dependency, port conflict. |
| Migration errors out | Show the migration filename + the SQL it tried; ask whether to roll back or fix the migration and re-promote. |
| Smoke check returns 200 but `active_provider=mock` | The vLLM URL didn't propagate to the container env. Check melehost's `~/ami_trade/.env` has `VLLM_BASE_URL=http://192.168.20.74:8000`. |
| Smoke check returns 502 | The cloudflared dashboard ingress URL may have drifted from `http://api-alpha:8000`. See `infra/cloudflared/README.md`. |
