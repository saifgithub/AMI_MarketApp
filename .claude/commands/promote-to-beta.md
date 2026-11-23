---
description: Promote an existing alpha-* tag (one that passed postflight on Alpha) to the Beta VPS (ami-beta, api-beta.agenticmarketintel.ai). Ships from a clean temporary worktree of that tag, never HEAD; tags beta-YYYY-MM-DD-N on the same commit; builds, migrates, swaps, runs postflight.
---

# /promote-to-beta

Promote an **existing `alpha-*` tag** to the Beta environment: one Singapore
VPS (SSH alias `ami-beta`, created at gate S4 / WP-42) running the same Docker
Compose stack as Alpha, `AMI_ENV=beta`, public hostname
`https://api-beta.agenticmarketintel.ai` through its own Cloudflare Tunnel.
CR267 WP-43. Companion to [/promote-to-alpha](./promote-to-alpha.md) — read it
for the reasoning behind every step this file repeats; this file only records
what is different.

Invoke as `/promote-to-beta [alpha-YYYY-MM-DD-N]`. With no argument, list the
newest `alpha-*` tags that hold a postflight record (step 1c) and ask which.

## Rules that differ from Alpha

1. **Beta promotes a tag, never HEAD.** The tree shipped is
   `git worktree add --detach <tmp> <alpha-tag>`. Nothing from the invoking
   checkout (uncommitted work, newer commits, other lanes) can reach the box.
2. **The Beta tag is `beta-YYYY-MM-DD-N`** (`Asia/Kuala_Lumpur`), created on the
   **same commit** as the alpha tag. Sequence is per day over `beta-*` tags.
3. **Credentials never cross.** `infra/beta.env` (gitignored, main checkout) goes
   to the Beta host's `.env`. `infra/alpha.env` is never sent there, and both env
   files are excluded from the rsync in both directions.
4. **Same stack, same names.** Service `api-alpha`, container `ami_api_alpha`
   and the `ALPHA_TAG` build arg are Beta's too (one `docker-compose.yml`). The
   identity stamp therefore reads `alpha_tag=beta-YYYY-MM-DD-N` in `/v1/ready`
   and `/v1/health` — the field name is historical, the value is the Beta tag.
5. **Every ssh/scp/rsync below targets `ami-beta` and `~/ami_trade/`.** Never
   `melehost`. If a command here would name `melehost`, stop.

## What to do, in order

Run every step in order. Any failure or surprise: **stop and explain** — no
auto-recovery. The user decides whether to abort, fix, or continue.

### 1. Preflight — blocking checks

Run from the invoking checkout (the main checkout or any worktree). Any failure
aborts. **Run bare, never through a pipe or a background task (DEF405).**

#### 1a. Hold gate and audit-lane gate

Identical to `/promote-to-alpha` step 1 — copy those two blocks verbatim:
the `infra/PROMOTION_HOLD.md` hold gate (fails closed; "do not reason your way
past it"), then `orchestration/dispatch/dispatch.sh inbox` (exit 1 aborts, exit 2
is a warning). They stay because both are statements about the *code*: a hold
names a precondition that must clear before **any** environment gets this code,
and an unread auditor verdict may already say the tag is broken.

#### 1b. Resolve and validate the source tag

```bash
SOURCE_ALPHA_TAG=<alpha-YYYY-MM-DD-N>          # argument, or the one the user picked
echo "$SOURCE_ALPHA_TAG" | grep -Eq '^alpha-[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]+$' \
  || { echo "not an alpha-YYYY-MM-DD-N tag — aborting."; exit 1; }
git rev-parse --verify --quiet "refs/tags/${SOURCE_ALPHA_TAG}^{commit}" >/dev/null \
  || { echo "tag ${SOURCE_ALPHA_TAG} does not exist — aborting."; exit 1; }
export GIT_SHA="$(git rev-parse "${SOURCE_ALPHA_TAG}^{commit}")"
git log --oneline -1 "$GIT_SHA"
```

If the tag is not the newest `alpha-*`, say so to the user (it is allowed —
promoting an older, better-soaked tag is a normal reason — but never silent).

#### 1c. Alpha postflight record gate (replaces the suite / local-gate / CI gates)

```bash
python3 scripts/promotion/postflight.py --target beta --pre-gate \
  --source-alpha-tag "$SOURCE_ALPHA_TAG" --expect-sha "$GIT_SHA" || {
  echo "ALPHA RECORD GATE — ${SOURCE_ALPHA_TAG} has no PASS postflight record on this commit. Aborting."
  exit 1
}
```

`/promote-to-alpha` step 7c writes `<main checkout>/.deliveryos/postflight/<tag>.json`
on every PASS. No record, a non-PASS record, or a record for another commit
means the tag was never proven on Alpha, and Beta does not ship it. There is no
`--force`. A tag promoted to Alpha before this record existed must be
re-promoted to Alpha (a new `alpha-*` tag), not waved through.

#### 1d. UAT ledger gate — the API cases for this tag passed on Alpha

```bash
env -u UAT_GATE_OVERRIDE backend/.venv/bin/python scripts/uat/uat_gate.py \
  --for alpha-post --runs-only || {
  echo "UAT LEDGER — API cases are not green on Alpha. Aborting."
  echo "  run: scripts/uat/run_uat.sh --api --changed-only   (against Alpha)"
  exit 1
}
```

`--runs-only` checks only the ledger's `alpha-post` targets (API cases green at
their current fingerprint). The override variable is unset on purpose: an
override is a decision about an *Alpha* promotion; it does not carry to Beta.

#### 1e. Beta env file

```bash
if [ ! -f infra/beta.env ]; then
  MAIN_WORKTREE=$(git worktree list --porcelain | grep '^worktree ' | head -1 | cut -d' ' -f2-)
  if [ -n "$MAIN_WORKTREE" ] && [ -f "$MAIN_WORKTREE/infra/beta.env" ] && [ "$MAIN_WORKTREE" != "$(pwd)" ]; then
    cp "$MAIN_WORKTREE/infra/beta.env" infra/beta.env
    echo "auto-sourced infra/beta.env from $MAIN_WORKTREE"
  fi
fi
[ -f infra/beta.env ] || { echo "ERROR: infra/beta.env missing — copy infra/beta.env.example and fill it (WP-41/S4)"; exit 1; }

grep -q '^AMI_ENV=beta$' infra/beta.env || { echo "infra/beta.env does not say AMI_ENV=beta — aborting."; exit 1; }

# Beta has its own keys. Compare WITHOUT printing either value.
A=$(grep '^SECRET_KEY=' infra/alpha.env 2>/dev/null | cut -d= -f2-)
B=$(grep '^SECRET_KEY=' infra/beta.env | cut -d= -f2-)
[ -n "$B" ] || { echo "SECRET_KEY empty in infra/beta.env — aborting."; exit 1; }
[ -n "$A" ] && [ "$A" = "$B" ] && { echo "infra/beta.env SECRET_KEY equals Alpha's — Beta needs a fresh key. Aborting."; exit 1; }
```

(The app itself refuses to boot on the other Beta posture mistakes — LAN LLM
URLs, Anthropic/Kimi/Google keys, no spend ceiling, age gate off — see
`infra/beta.env.example` and `backend/app/core/beta_boot.py`. Step 5's health
wait surfaces that refusal; it is not duplicated here.)

#### 1f. Reachability and the one question

```bash
ssh -o BatchMode=yes -o ConnectTimeout=10 ami-beta true
```

Failure here means the SSH alias or key is not set up (WP-42 / S4). Do not try
to fix SSH from this command.

Then **ask the user one yes/no question**:

> "Promote `<SOURCE_ALPHA_TAG>` (`<short sha> — <subject>`) to Beta? It has run
>  on Alpha since `<alpha tag date>`; the Alpha postflight record and UAT API
>  ledger are green. (y/n)"

`n` aborts.

**Deliberately NOT re-run for Beta, and why.** The suite gate, flutter analyze,
the local release gate, the UAT guards/script-updated checks, the CI warning and
the tree gate are all statements about a *working tree at a moment*. Beta ships
an immutable tag from a throwaway clean checkout, so (i) the tree gate has
nothing to find — `git worktree add` of a tag cannot carry uncommitted files;
(ii) re-running the suites on the invoking checkout would test a different tree
than the one shipped, producing a green or red that describes the wrong thing;
(iii) the tag already passed all of them when it went to Alpha, and step 1c
proves that mechanically instead of trusting memory. Postflight's `suite` and
`local_gate` checks are replaced by the `alpha_record` check for the same
reason (their records are hours old by design).

### 2. Compute the Beta tag and create the shipping worktree

```bash
TODAY=$(TZ='Asia/Kuala_Lumpur' date +%Y-%m-%d)
N=$(( $(git tag --list "beta-${TODAY}-*" | sed 's/.*-//' | sort -n | tail -1 | grep -E '^[0-9]+$' || echo 0) + 1 ))
export BETA_TAG="beta-${TODAY}-${N}"
git tag "$BETA_TAG" "$GIT_SHA"
# compose reads ALPHA_TAG as the build arg for the identity stamp; on Beta it
# carries the Beta tag. Steps 5 and 7 both read it.
export ALPHA_TAG="$BETA_TAG"

BETA_WT="$(mktemp -d /tmp/ami-beta-promote-XXXXXX)/tree"
git worktree add --detach "$BETA_WT" "$SOURCE_ALPHA_TAG"
[ "$(git -C "$BETA_WT" rev-parse HEAD)" = "$GIT_SHA" ] || { echo "worktree is not at $GIT_SHA — aborting."; exit 1; }
[ -z "$(git -C "$BETA_WT" status --porcelain)" ] || { echo "temp worktree is dirty — aborting."; exit 1; }
```

Tags are local; `git push origin "$BETA_TAG"` if a backup is wanted. Clean the
worktree up at the end (step 8) **and** on any abort:
`git worktree remove --force "$(dirname "$BETA_WT")/tree"`.

### 3. Rsync to ami-beta

Same exclude list as `/promote-to-alpha` step 3 (it must stay the same —
`postflight.py`'s tree check uses it, and `test_cr175_postflight.py` guards the
pairing), shipped **from the temp worktree**:

```bash
rsync -az --delete \
  --exclude='.env' \
  --exclude='infra/alpha.env' \
  --exclude='infra/beta.env' \
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
  --exclude='/logs/' \
  "$BETA_WT"/ \
  ami-beta:~/ami_trade/
```

The `audit/`, `reports/`, `backtest_results/` and `.env` excludes carry the same
DEF081 / DEF276 / DEF381 reasoning as on Alpha: host-generated or
credential-bearing paths that `--delete` must not touch.

### 4. Ship the Beta env file (Mac → ami-beta)

```bash
scp infra/beta.env ami-beta:~/ami_trade/.env
ssh ami-beta "grep -E '^(AMI_ENV|SECRET_KEY|ADMIN_SECRET|POSTGRES_PASSWORD|REDIS_PASSWORD|CF_TUNNEL_TOKEN|VLLM_BASE_URL|VLLM_MODEL|VLLM_FALLBACK_BASE_URL|LLM_DAILY_SPEND_CEILING_USD)=' ~/ami_trade/.env | sed 's/=.*/=<set>/'"
ssh ami-beta "grep -c '^AMI_ENV=beta$' ~/ami_trade/.env"
```

Expect every key above to read `<set>` and the count to be `1`. Anything
missing: stop, fix `infra/beta.env` on the Mac, re-promote. **Never edit the
Beta host's `.env` in place** — the next promotion overwrites it. Rotation flows
Mac → host as a side effect of promotion, exactly as on Alpha.

### 5. Build, migrate, swap

Migrations run **before** the new container serves anything (DEF215):

```bash
ssh ami-beta "cd ~/ami_trade && GIT_SHA='${GIT_SHA}' ALPHA_TAG='${ALPHA_TAG}' docker compose --profile tunnel build api-alpha"
ssh ami-beta "cd ~/ami_trade && docker compose run --rm --no-deps api-alpha alembic upgrade head"
```

If that fails, **stop** — the old container is still serving. (First-ever
promotion: the database is empty and Alembic builds it; Postgres and Redis come
up as `api-alpha`'s dependencies.) Then swap:

```bash
ssh ami-beta "cd ~/ami_trade && GIT_SHA='${GIT_SHA}' ALPHA_TAG='${ALPHA_TAG}' docker compose --profile tunnel up -d --build api-alpha"
# Tunnel: start it only if it is not running (first promotion). Never recreate
# Postgres / Redis.
ssh ami-beta "docker ps --format '{{.Names}}' | grep -q '^ami_tunnel$' || (cd ~/ami_trade && docker compose --profile tunnel up -d cloudflared)"
```

Wait for health (poll every 2s, ~30s; the Beta boot checks may refuse to start —
the logs say which):

```bash
ssh ami-beta "docker inspect ami_api_alpha --format '{{.State.Health.Status}}'"
ssh ami-beta "docker logs ami_api_alpha --tail 50"      # if it never goes healthy
```

Then confirm head: `ssh ami-beta "cd ~/ami_trade && docker compose exec -T api-alpha alembic current"`
must read `<revision> (head)`.

### 6. Smoke check the public hostname

```bash
curl -fsS https://api-beta.agenticmarketintel.ai/v1/health
ADMIN_SECRET=$(grep -E '^ADMIN_SECRET=' infra/beta.env | cut -d= -f2-)
curl -fsS -H "Authorization: Bearer ${ADMIN_SECRET}" https://api-beta.agenticmarketintel.ai/v1/llm/status
curl -fsS https://api-beta.agenticmarketintel.ai/v1/sim/quote/AAPL
```

`/v1/health` must show `env=beta` and the `ALPHA_TAG` you just exported. The LLM
status must name the **hosted** provider, never the on-prem address. Any non-200
or unexpected shape: stop and surface.

### 7. Postflight — run from the invoking checkout, pointed at the temp tree

```bash
python3 scripts/promotion/postflight.py --target beta \
  --expect-sha "${GIT_SHA}" --expect-tag "${BETA_TAG}" \
  --source-alpha-tag "${SOURCE_ALPHA_TAG}" --root "$BETA_WT"
```

Why from the invoking checkout: the alpha tag may predate `--target`, so its own
copy of `postflight.py` cannot check Beta. `--root` makes the `tree` and
`migrations` checks read the tree that was actually shipped.

Checks and exit codes are `/promote-to-alpha` step 7c's, with one swap:
`alpha_record` stands in for `suite` + `local_gate`. So: `alpha_record`,
`migrations`, `identity` (container reports the commit and **beta** tag),
`tree` (`rsync --dry-run` of the temp worktree vs `ami-beta:~/ami_trade/`),
`readiness`, `config` (every populated key in `infra/beta.env` is
`configured=true`), `market`. Exit `0` pass; `1` failed — fix forward or
`/rollback-beta`; `2` could not run — **not a pass**. On PASS it records
`.deliveryos/postflight/${BETA_TAG}.json`, which `/rollback-beta` uses to pick
known-good targets.

### 8. Clean up and report

```bash
git worktree remove --force "$(dirname "$BETA_WT")/tree" && rmdir "$(dirname "$BETA_WT")"
```

```
Promoted to Beta — beta-2026-12-01-1 = alpha-2026-11-30-2 (a1b2c3d — "<subject>")
  • gates: hold · audit lane · alpha postflight record PASS · UAT api ledger green
  • not re-run (tag already gated on Alpha): suite · flutter · local gate · CI
  • rsync (from temp worktree of the tag): 31s
  • scp infra/beta.env: <1s, 10/10 keys <set>, AMI_ENV=beta
  • build + migrate + swap: 52s · alembic current: <rev> (head)
  • smoke: /v1/health env=beta tag=beta-… · /v1/llm/status <hosted provider> · /v1/sim/quote AAPL (source=yfinance)
  • postflight: PASSED (alpha_record · migrations · identity · tree · readiness · config · market)
```

## What NOT to do

- **Don't promote HEAD, a branch, or an untagged commit.** Only an `alpha-*` tag with a postflight record.
- **Don't use the Alpha host, the Alpha env file or the Alpha hostname anywhere here.** Wrong box, wrong credentials, wrong hostname.
- **Don't delete tags; don't auto-rollback.** `/rollback-beta` is a separate deliberate act.
- **Don't recreate Postgres or Redis.** Only `api-alpha` (and the tunnel, once).
- **Don't edit the Beta host's `.env` in place** or hand-edit anything on the box.
- **Don't point Beta at on-prem vLLM or an Anthropic key**, in any form — the app will refuse to boot and so should you.
- **Don't leave the temp worktree behind.**

## When something goes sideways

| Symptom | Action |
|---|---|
| ALPHA RECORD GATE fails | The tag never passed Alpha postflight from this machine. Re-promote to Alpha; do not hand-write a record. |
| `ssh ami-beta` fails | SSH config entry / key / firewall (WP-42). Don't auto-fix. |
| Container never healthy, log says a Beta refusal | `backend/app/core/beta_boot.py` listed the offending key — fix `infra/beta.env`, re-promote. |
| `/v1/health` shows `env=local` or the wrong tag | `.env` did not land or `ALPHA_TAG` did not reach the remote shell — step 4/5. |
| Postflight `tree` fails right after the rsync | Partial rsync. Re-run step 3, then postflight. |
| Smoke 502 | The Beta tunnel ingress is not `http://api-alpha:8000`, or `ami_tunnel` is down (`docker logs ami_tunnel`). WP-42 owns the tunnel. |
