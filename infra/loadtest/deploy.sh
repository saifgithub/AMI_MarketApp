#!/usr/bin/env bash
# CR246 — deploy (or redeploy) the disposable ami-loadtest stack to minihost.
#
# Run from the repo root on the Mac:
#   infra/loadtest/deploy.sh
#
# What it does:
#   1. rsyncs backend/, content/, infra/loadtest/ to minihost:~/ami_loadtest/
#      (secrets and local state excluded — same transport rule as
#      /promote-to-alpha: code moves by rsync, env moves separately)
#   2. generates ~/ami_loadtest/infra/loadtest/.env on minihost on FIRST deploy
#      only (random secrets; never overwritten afterwards, never on the Mac)
#   3. builds the api image, brings the stack up, runs alembic migrations
#   4. smoke-checks /v1/health and /v1/llm/status (expects provider=mock)
#
# Idempotent: re-running redeploys current code onto the same data. To reset
# the world: ssh minihost "cd ~/ami_loadtest/infra/loadtest && docker compose down -v"
# then run this again.

set -euo pipefail

HOST="${LOADTEST_HOST:-minihost}"
REMOTE_DIR="~/ami_loadtest"
COMPOSE_DIR="~/ami_loadtest/infra/loadtest"

echo "== 1/4 rsync code to ${HOST}:${REMOTE_DIR}"
rsync -az --delete \
  --exclude='.env' \
  --exclude='.venv' \
  --exclude='__pycache__' \
  --exclude='*.egg-info' \
  --exclude='.pytest_cache' \
  --exclude='.mypy_cache' \
  --exclude='.ruff_cache' \
  --exclude='.local.db*' \
  backend content "${HOST}:${REMOTE_DIR}/"
rsync -az --delete \
  --exclude='.env' \
  infra/loadtest "${HOST}:${REMOTE_DIR}/infra/"

echo "== 2/4 ensure env on ${HOST} (first deploy only)"
ssh "${HOST}" "
  set -euo pipefail
  cd ${COMPOSE_DIR}
  if [ ! -f .env ]; then
    umask 077
    {
      echo \"POSTGRES_PASSWORD=\$(openssl rand -hex 32)\"
      echo \"REDIS_PASSWORD=\$(openssl rand -hex 32)\"
      echo \"SECRET_KEY=\$(openssl rand -hex 32)\"
      echo \"ADMIN_SECRET=\$(openssl rand -hex 32)\"
      echo \"POSTGRES_USER=postgres\"
    } > .env
    echo 'generated fresh .env'
  else
    echo '.env already present — kept'
  fi
"

echo "== 3/4 build + up + migrate"
GIT_SHA="$(git rev-parse HEAD)"
ssh "${HOST}" "
  set -euo pipefail
  cd ${COMPOSE_DIR}
  GIT_SHA='${GIT_SHA}' docker compose build api
  docker compose up -d --wait postgres redis
  docker compose run --rm --no-deps api alembic upgrade head
  GIT_SHA='${GIT_SHA}' docker compose up -d api
"

echo "== 4/4 smoke check"
for i in $(seq 1 30); do
  STATUS=$(ssh "${HOST}" "docker inspect ami_loadtest_api --format '{{.State.Health.Status}}'" 2>/dev/null || echo unknown)
  [ "${STATUS}" = "healthy" ] && break
  sleep 2
done
if [ "${STATUS}" != "healthy" ]; then
  echo "API did not go healthy — last 50 log lines:"
  ssh "${HOST}" "docker logs ami_loadtest_api --tail 50"
  exit 1
fi

curl -fsS "http://192.168.20.14:8000/v1/health"
echo
ADMIN=$(ssh "${HOST}" "grep '^ADMIN_SECRET=' ${COMPOSE_DIR}/.env | cut -d= -f2-")
PROVIDER=$(curl -fsS -H "Authorization: Bearer ${ADMIN}" "http://192.168.20.14:8000/v1/llm/status")
echo "${PROVIDER}"
echo "${PROVIDER}" | grep -q '"active_provider":\s*"mock"' || echo "${PROVIDER}" | grep -q mock || {
  echo "SMOKE FAIL: LLM provider is not mock on the loadtest instance"
  exit 1
}

echo
echo "DEPLOY OK — loadtest API at http://192.168.20.14:8000 (mock LLM)"
