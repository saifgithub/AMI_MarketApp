#!/usr/bin/env bash
# Cloudflare-tunnel watchdog — DEF402.
#
# Why this exists: on 2026-09-03 the `ami_tunnel` connector wedged twice.
# The retry loop froze (log went silent for 3+ minutes) while `docker ps`
# kept reading "Up 2 days" — container status is USELESS as a signal, it
# never flipped. Public `https://api-alpha.agenticmarketintel.ai` served
# 530 the whole time even though the origin answered `/v1/health` 200 on
# localhost. The wedge itself is silent; nothing we already run would ever
# notice it. `docker restart ami_tunnel` fixed it instantly both times —
# this script is that fix, automated and bounded to a 2-minute blind spot
# instead of "whoever happens to be mid-promotion of something else".
#
# Decision rule (deliberately narrow — this is the whole point of the
# guard): restart ONLY when the fault is provably the connector, i.e.
# public is down AND origin is healthy. If origin is also down, this is
# not a tunnel problem — do nothing, let the real outage alert some other
# way. If public is down because the CF edge itself is down, origin will
# still read healthy on localhost... which is indistinguishable from the
# wedge from in here. That's what the cooldown is for: one restart per
# window, so a persistent edge-side outage doesn't get restarted forever
# for no benefit (DEF402 row: "CF-edge-down means public fails while
# origin is fine, and restarting forever helps nothing").
#
# Degrade loudly (CR040): every branch appends a dated line to the log —
# healthy runs, restarts, cooldown stand-downs, and the script's own
# internal errors. Nothing exits silently.
#
# Usage: run standalone or via cron (see README.md for the install line).
# Env overrides (used by tests — never point these at production without
# reading the "testing" section in README.md first):
#   PUBLIC_HEALTH_URL   default https://api-alpha.agenticmarketintel.ai/v1/health
#   ORIGIN_HEALTH_URL    default http://localhost:8000/v1/health
#   RESTART_CMD          default "docker restart ami_tunnel"
#   LOG_FILE             default <script dir>/cf_tunnel_watchdog.log
#   COOLDOWN_SECONDS      default 600 (10 minutes)
#   CURL_TIMEOUT_SECONDS  default 10

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PUBLIC_HEALTH_URL="${PUBLIC_HEALTH_URL:-https://api-alpha.agenticmarketintel.ai/v1/health}"
ORIGIN_HEALTH_URL="${ORIGIN_HEALTH_URL:-http://localhost:8000/v1/health}"
RESTART_CMD="${RESTART_CMD:-docker restart ami_tunnel}"
LOG_FILE="${LOG_FILE:-$SCRIPT_DIR/cf_tunnel_watchdog.log}"
COOLDOWN_SECONDS="${COOLDOWN_SECONDS:-600}"
CURL_TIMEOUT_SECONDS="${CURL_TIMEOUT_SECONDS:-10}"
STATE_FILE="${STATE_FILE:-$SCRIPT_DIR/.last_restart_epoch}"

log() {
  # $1 = message. Always dated, always appended — never overwritten.
  printf '%s %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$1" >> "$LOG_FILE"
}

probe() {
  # $1 = URL. Prints the HTTP status code, or "TIMEOUT"/"ERROR" on failure.
  # Any non-200 (including a failed curl) is treated as down per the spec.
  local url="$1" code
  code="$(curl -s -o /dev/null -w '%{http_code}' \
    --max-time "$CURL_TIMEOUT_SECONDS" "$url" 2>/dev/null)"
  if [[ -z "$code" ]]; then
    echo "ERROR"
  else
    echo "$code"
  fi
}

main() {
  if ! command -v curl >/dev/null 2>&1; then
    log "ERROR script=cf_tunnel_watchdog reason=curl_not_found — cannot probe, standing down"
    return 1
  fi

  local public_code origin_code
  public_code="$(probe "$PUBLIC_HEALTH_URL")"

  if [[ "$public_code" == "200" ]]; then
    # Healthy path: heartbeat line, not silence — makes "the watchdog is
    # actually running" verifiable from the log alone.
    log "OK public=$public_code"
    return 0
  fi

  # Public is down (or errored/timed out). Check whether the origin is
  # actually healthy before touching anything.
  origin_code="$(probe "$ORIGIN_HEALTH_URL")"

  if [[ "$origin_code" != "200" ]]; then
    # Origin is unhealthy too — not a connector-only fault. Restarting the
    # tunnel would not help a dead backend. Record and stand down.
    log "DOWN public=$public_code origin=$origin_code action=none reason=origin_unhealthy_not_a_tunnel_fault"
    return 0
  fi

  # Provable connector fault: public down, origin up. Check cooldown
  # before restarting so a persistent edge-side outage (public down,
  # origin fine, but the fault is CF's edge, not our connector) doesn't
  # get restarted every 2 minutes forever.
  local now last_restart elapsed
  now="$(date -u +%s)"
  if [[ -f "$STATE_FILE" ]]; then
    last_restart="$(cat "$STATE_FILE" 2>/dev/null || echo 0)"
    [[ "$last_restart" =~ ^[0-9]+$ ]] || last_restart=0
  else
    last_restart=0
  fi
  elapsed=$(( now - last_restart ))

  if (( last_restart > 0 && elapsed < COOLDOWN_SECONDS )); then
    log "DOWN public=$public_code origin=$origin_code action=none reason=cooldown elapsed=${elapsed}s cooldown=${COOLDOWN_SECONDS}s"
    return 0
  fi

  # Fire the restart.
  local restart_output restart_status
  restart_output="$($RESTART_CMD 2>&1)"
  restart_status=$?
  echo "$now" > "$STATE_FILE"

  if [[ $restart_status -eq 0 ]]; then
    log "DOWN public=$public_code origin=$origin_code action=restart cmd=\"$RESTART_CMD\" result=ok output=\"$restart_output\""
  else
    log "DOWN public=$public_code origin=$origin_code action=restart cmd=\"$RESTART_CMD\" result=FAILED status=$restart_status output=\"$restart_output\""
  fi
}

main "$@"
