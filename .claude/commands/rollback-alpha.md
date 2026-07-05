---
description: Roll the Alpha environment (melehost) back to a previous successful promotion. Lists recent alpha-* tags, confirms the target with the operator, re-deploys, smoke-checks. Does NOT touch the database unless the operator explicitly asks.
---

# /rollback-alpha

Re-deploy a previous `alpha-*` tag to `melehost`. Companion to
[/promote-to-alpha](./promote-to-alpha.md). Use when a recent
promotion broke Alpha and the testers are blocked.

Full design rationale lives in `docs/initial_specs/10_delivery/promotion_protocol.md`
under "What a rollback to Alpha actually does".

## What to do, in order

### 1. List the last 10 successful alpha promotions

```bash
git tag --list 'alpha-*' --sort=-version:refname | head -10
```

Show the list to the user. Identify two things:

- The **currently-live** tag (the most recent one — usually first in
  the list, unless a manual rollback already happened).
- The **target rollback tag** (default: the second one, i.e. the
  previous promotion).

### 2. Confirm the target with the operator

**Ask one question:**

> "Roll back from `<current-tag>` to `<target-tag>`? (y/n, or paste a
>  different alpha-* tag to use instead)"

If the user pastes a tag, validate it exists in `git tag --list` and
matches the `alpha-YYYY-MM-DD-N` pattern before continuing.

### 3. Check out the target in a clean worktree

Don't disturb the operator's primary worktree. Create a temp worktree
just for the rollback:

```bash
TARGET_TAG=<the-chosen-tag>
ROLLBACK_WT="/tmp/ami-rollback-${TARGET_TAG}"
git worktree add "$ROLLBACK_WT" "$TARGET_TAG"
cd "$ROLLBACK_WT"
```

When the rollback completes (or fails), clean up:

```bash
git worktree remove "$ROLLBACK_WT" --force
```

(Don't delete the tag — it's permanent.)

### 4. Rsync the target tag's contents to melehost

Same rsync invocation as `/promote-to-alpha` step 3. Run it from the
temp worktree so the file contents reflect the rollback tag.

### 5. Recreate the backend container

Same as `/promote-to-alpha` step 4 — `docker compose --profile tunnel up -d --build api-alpha` on melehost, wait for healthy.

### 6. Database migration handling

This is the **deliberate** step. By default a rollback does NOT
downgrade the database. Forward-only migrations (drops, type changes)
can be destructive to downgrade.

**Ask the user:**

> "The rolled-back code is at `<target-tag>`. Migrations from the
>  forward direction are still applied at HEAD revision. Most
>  rollbacks are fix-forward-friendly and don't need DB downgrade.
>  Do you want to downgrade the database too? (y/n)"

- `n` (default): leave the DB alone. The rolled-back app talks to a
  schema that's a bit newer than what it was built against. This is
  fine for additive changes (new column with default, new table) and
  problematic for breaking ones (renamed column, dropped column).
- `y`: run `docker compose exec api-alpha alembic downgrade <revision>`.
  The operator picks the revision; default is the revision at the
  target tag (which you can introspect via
  `git show ${TARGET_TAG}:backend/alembic/versions/` — pick the
  highest revision file that exists at that tag).

If unsure, the operator should keep the DB alone (`n`) and inspect.

### 7. Smoke check

Same three curls as `/promote-to-alpha` step 6:

```bash
curl -fsS https://api-alpha.agenticmarketintel.ai/v1/health
curl -fsS https://api-alpha.agenticmarketintel.ai/v1/llm/status
curl -fsS https://api-alpha.agenticmarketintel.ai/v1/sim/quote/AAPL
```

### 8. Report

```
Rolled back Alpha — now serving alpha-2026-05-12-2 (was alpha-2026-05-12-3)
  • previous-tag preserved (NOT deleted): alpha-2026-05-12-3
  • DB downgrade: skipped (per operator)
  • smoke: /v1/health 200 · /v1/llm/status vllm · /v1/sim/quote $221.27
  • cleanup: rollback worktree at /tmp/ami-rollback-... removed
```

## What NOT to do

- **Don't delete the failing tag.** Keeping it makes the post-mortem
  possible. The next forward promotion just creates a new tag with a
  higher sequence; the failing one stays in the history.
- **Don't auto-downgrade the DB.** Always ask.
- **Don't rollback into a tag that doesn't exist or doesn't match
  the `alpha-*` pattern.** Surface the error to the user.
- **Don't leave the temp worktree behind.** `git worktree remove`
  on success or failure (the `--force` flag is safe — the temp
  worktree was just a checkout, no work in progress).

## When this isn't the right move

Rollback is a defensive action for "production breakage during
Alpha". Sometimes the right move is fix-forward instead:

- If the failure is a typo / config issue you can fix in 5 minutes,
  just fix-forward and `/promote-to-alpha` again. Faster than a
  rollback round-trip.
- If you don't yet know what broke, rollback gets testers unblocked
  while you diagnose — that's exactly what rollback is for.
- If the migration itself failed (DB is now in a half-applied state),
  the rollback won't help — that's a manual DB recovery scenario
  with `docker exec ami_postgres psql` and the dump from
  `infra/backups/`.
