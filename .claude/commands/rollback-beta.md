---
description: Roll the Beta VPS (ami-beta) back to a previous successful beta-* promotion. Lists recent beta-* tags that hold a PASS postflight record, confirms the target with the operator, re-deploys that tag from a clean temporary worktree, smoke-checks and runs postflight. Does NOT touch the database unless the operator explicitly asks.
---

# /rollback-beta

Re-deploy a previous `beta-*` tag to the Beta VPS (`ami-beta`). Companion to
[/promote-to-beta](./promote-to-beta.md) and the Beta twin of
[/rollback-alpha](./rollback-alpha.md) (CR267 WP-43). Use when a recent Beta
promotion broke the testers' environment. Read `/rollback-alpha` for the
reasoning behind the DB-handling step; this file records what differs.

Every ssh/scp/rsync here targets `ami-beta`. Never `melehost`.

## What to do, in order

### 1. List the last 10 successful beta promotions

A tag counts only if it has a **PASS postflight record** — that is what proves
it was once a healthy Beta state, not merely a tag someone created before a
failed deploy.

```bash
MAIN_WORKTREE=$(git worktree list --porcelain | grep '^worktree ' | head -1 | cut -d' ' -f2-)
for t in $(git tag --list 'beta-*' --sort=-version:refname); do
  [ -f "$MAIN_WORKTREE/.deliveryos/postflight/$t.json" ] && echo "$t  $(git rev-parse --short "$t^{commit}")  $(git log -1 --format=%s "$t^{commit}")"
done | head -10
```

Identify the **currently live** tag
(`curl -fsS https://api-beta.agenticmarketintel.ai/v1/health` → the tag field)
and the **target** (default: the newest recorded tag older than the live one).
If the list is empty, stop: there is no known-good Beta state to return to, and
that is a finding to report, not something to improvise around.

### 2. Confirm the target

**Ask one question:**

> "Roll Beta back from `<live-tag>` to `<target-tag>`? (y/n, or paste a different beta-* tag)"

A pasted tag must exist and match `^beta-[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]+$`
**and** be in the step 1 list (a recorded one). Resolve its source alpha tag:

```bash
TARGET_TAG=<chosen>
export GIT_SHA="$(git rev-parse "${TARGET_TAG}^{commit}")"
SOURCE_ALPHA_TAG=$(git tag --points-at "$GIT_SHA" --list 'alpha-*' | while read t; do
  [ -f "$MAIN_WORKTREE/.deliveryos/postflight/$t.json" ] && echo "$t"; done | tail -1)
[ -n "$SOURCE_ALPHA_TAG" ] || { echo "no recorded alpha tag on $GIT_SHA — aborting."; exit 1; }
export ALPHA_TAG="$TARGET_TAG"     # compose's identity-stamp build arg; carries the Beta tag
```

No hold gate and no audit-lane gate: a hold or an unread verdict is a reason not
to ship *new* code, and a rollback ships code Beta already ran. Gating the way
back to a known-good state on them would be backwards.

### 3. Check out the target in a clean worktree

```bash
RB_WT="$(mktemp -d /tmp/ami-beta-rollback-XXXXXX)/tree"
git worktree add --detach "$RB_WT" "$TARGET_TAG"
[ "$(git -C "$RB_WT" rev-parse HEAD)" = "$GIT_SHA" ] || { echo "worktree is not at $GIT_SHA — aborting."; exit 1; }
```

Clean up on success **and** failure:
`git worktree remove --force "$(dirname "$RB_WT")/tree" && rmdir "$(dirname "$RB_WT")"`.
Never delete the tag.

### 4. Rsync the target tag to ami-beta

Same rsync as `/promote-to-beta` step 3 (including `--exclude='infra/alpha.env'`
and `--exclude='infra/beta.env'`), source `"$RB_WT"/`, destination
`ami-beta:~/ami_trade/`.

The Beta `.env` is **not** re-shipped by default — the box already holds the
current `infra/beta.env`, and a rollback is about code. If the bad promotion
also changed env (a key added, a rotation), say so to the user and ship it
deliberately with `/promote-to-beta` step 4 — never silently.

### 5. Rebuild and swap — no migration step

```bash
ssh ami-beta "cd ~/ami_trade && GIT_SHA='${GIT_SHA}' ALPHA_TAG='${ALPHA_TAG}' docker compose --profile tunnel up -d --build api-alpha"
ssh ami-beta "docker inspect ami_api_alpha --format '{{.State.Health.Status}}'"     # poll to healthy
ssh ami-beta "docker logs ami_api_alpha --tail 50"                                   # if it never does
```

`alembic upgrade head` is deliberately **not** run: the older code does not know
the newer revisions the database may already hold, so it cannot upgrade to a
head it has never seen.

### 6. Database handling — the deliberate step

Default: **leave the database alone**. Forward-only migrations can be
destructive to downgrade. Ask:

> "Beta now runs `<target-tag>` against a schema that may be newer than that
>  code. Additive changes are fine; a renamed or dropped column is not. Downgrade
>  the database too? (y/n — default n)"

`y`: the operator names the revision (default: the highest file under
`git show ${TARGET_TAG}:backend/alembic/versions/`), then
`ssh ami-beta "cd ~/ami_trade && docker compose exec -T api-alpha alembic downgrade <revision>"`.
**Take a backup first** (`infra/backups/pg-backup.sh` on the box). Beta carries
tester data that cannot be regenerated; a downgrade without a dump is not an
option.

### 7. Smoke check and postflight

```bash
curl -fsS https://api-beta.agenticmarketintel.ai/v1/health
ADMIN_SECRET=$(grep -E '^ADMIN_SECRET=' infra/beta.env | cut -d= -f2-)
curl -fsS -H "Authorization: Bearer ${ADMIN_SECRET}" https://api-beta.agenticmarketintel.ai/v1/llm/status
curl -fsS https://api-beta.agenticmarketintel.ai/v1/sim/quote/AAPL

python3 scripts/promotion/postflight.py --target beta \
  --expect-sha "${GIT_SHA}" --expect-tag "${TARGET_TAG}" \
  --source-alpha-tag "${SOURCE_ALPHA_TAG}" --root "$RB_WT"
```

`/v1/health` must show `env=beta` and `${TARGET_TAG}` — that is the identity
stamp, and the acceptance for a rollback. Postflight is stricter than
`/rollback-alpha` ever was: if its `readiness` check fails because the schema is
ahead of the rolled-back code (DB not downgraded), read the probe detail and
report it to the user as such; do not hide it and do not treat it as a pass.
Exit `2` is "could not run", never a pass.

### 8. Report

```
Rolled back Beta — now serving beta-2026-12-01-1 (was beta-2026-12-02-1)
  • failing tag preserved (NOT deleted): beta-2026-12-02-1
  • DB downgrade: skipped (per operator)
  • identity: /v1/health env=beta tag=beta-2026-12-01-1 sha=<short>
  • smoke: /v1/health 200 · /v1/llm/status <hosted provider> · /v1/sim/quote AAPL
  • postflight: PASSED | <what failed>
  • cleanup: rollback worktree removed
```

## What NOT to do

- **Don't delete the failing tag** — the post-mortem needs it.
- **Don't auto-downgrade the DB**, and never without a fresh backup.
- **Don't roll back into a tag without a PASS postflight record**, or one that is not `beta-*`.
- **Don't run `alembic upgrade head`** with the older code.
- **Don't leave the temp worktree behind.**

## When this isn't the right move

Same logic as `/rollback-alpha`: a five-minute config or typo fix is faster
fix-forward via a new `/promote-to-beta`; an unknown breakage with testers
blocked is exactly what rollback is for; a half-applied migration is a manual DB
recovery (restore from the nightly dump, WP-44), and no rollback helps.
