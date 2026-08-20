#!/usr/bin/env bash
# CR102 — send in-app tester messages and read replies, from the Mac.
#
# Talks LAN-direct HTTP to the Alpha admin API on melehost
# (memory/feedback_lan_route.md) — NOT SSH+psql like users.sh. The main
# app carrying /v1/admin/* is LAN-published on :8000 (docker-compose.yml;
# :8001 is the loopback-bound website API).
#
# Usage:
#   ADMIN_SECRET=... scripts/messages.sh send --to all --title "..." --body "..." [--priority high]
#   ADMIN_SECRET=... scripts/messages.sh send --to build --version-lt 0.1.0+55 --title ... --body ...
#   ADMIN_SECRET=... scripts/messages.sh send --to active  --days 7 --title ... --body ...
#   ADMIN_SECRET=... scripts/messages.sh send --to dormant --days 14 --title ... --body ...
#   ADMIN_SECRET=... scripts/messages.sh send --to user --id <uuid> [--id <uuid> ...] --title ... --body ...
#   ADMIN_SECRET=... scripts/messages.sh list                # broadcasts + reply counts
#   ADMIN_SECRET=... scripts/messages.sh replies [--since 7d]
#
# NOTE: the real-tester exclusion filter (suspended users, house desks,
# CR035 room-benchmark synthetics, 2026-05-24 seed rows, and the 12 by-id
# probe/convene exclusions from memory/feedback_user_report_exclusions.md)
# applies on EVERY audience mode — including an explicit `--to user --id`.
# A message to an excluded id previews -> 0 recipients by design.
#
# `send` ALWAYS calls /preview first and prints the recipient count for
# confirmation before anything is written. ADMIN_SECRET comes from the
# environment, never a literal here.

set -euo pipefail

API="${AMI_ADMIN_API:-http://192.168.20.59:8000}"

if [[ -z "${ADMIN_SECRET:-}" ]]; then
  echo "error: ADMIN_SECRET is not set in the environment" >&2
  exit 1
fi

auth=(-H "Authorization: Bearer ${ADMIN_SECRET}" -H "Content-Type: application/json")

# jq-free JSON plumbing: python3 is always on the Mac, jq may not be.
py() { python3 -c "$1" "${@:2}"; }

cmd="${1:-}"
shift || true

case "$cmd" in

  send)
    to="" title="" body="" priority="normal" version_lt="" days=""
    ids=()
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --to)         to="$2"; shift 2 ;;
        --title)      title="$2"; shift 2 ;;
        --body)       body="$2"; shift 2 ;;
        --priority)   priority="$2"; shift 2 ;;
        --version-lt) version_lt="$2"; shift 2 ;;
        --days)       days="$2"; shift 2 ;;
        --id)         ids+=("$2"); shift 2 ;;
        *) echo "error: unknown flag $1" >&2; exit 1 ;;
      esac
    done
    [[ -n "$to" && -n "$title" && -n "$body" ]] || {
      echo "error: send needs --to, --title, --body" >&2; exit 1; }

    payload=$(TO="$to" TITLE="$title" BODY="$body" PRIORITY="$priority" \
              VERSION_LT="$version_lt" DAYS="$days" IDS="${ids[*]:-}" py '
import json, os, sys
to = os.environ["TO"]
aud = {}
if to == "all":
    aud = {"mode": "all"}
elif to == "build":
    aud = {"mode": "build", "app_version_lt": os.environ["VERSION_LT"]}
elif to == "active":
    aud = {"mode": "activity", "active_within_days": int(os.environ["DAYS"])}
elif to == "dormant":
    aud = {"mode": "activity", "dormant_beyond_days": int(os.environ["DAYS"])}
elif to == "user":
    aud = {"mode": "user", "user_ids": os.environ["IDS"].split()}
else:
    sys.exit(f"error: unknown --to {to!r} (all|build|active|dormant|user)")
print(json.dumps({
    "title": os.environ["TITLE"],
    "body": os.environ["BODY"],
    "priority": os.environ["PRIORITY"],
    "audience": aud,
}))')

    # Preview first, ALWAYS — the mistargeted-blast guard.
    count=$(curl -sf "${auth[@]}" -d "$payload" "$API/v1/admin/messages/preview" \
            | py 'import json,sys; print(json.load(sys.stdin)["recipient_count"])')
    echo "-> $count recipients"
    if [[ "$count" == "0" ]]; then
      echo "nothing to send (0 recipients — excluded/suspended ids preview as 0 by design)" >&2
      exit 1
    fi
    read -r -p "Send? [y/N] " yn
    [[ "$yn" == "y" || "$yn" == "Y" ]] || { echo "aborted"; exit 1; }

    curl -sf "${auth[@]}" -d "$payload" "$API/v1/admin/messages" \
      | py 'import json,sys; r=json.load(sys.stdin); print(f"sent broadcast {r[\"broadcast_id\"]} to {r[\"recipient_count\"]} recipients")'
    ;;

  list)
    curl -sf "${auth[@]}" "$API/v1/admin/messages" | py '
import json, sys
for b in json.load(sys.stdin):
    print(f"{b[\"created_at\"][:16]}  {b[\"id\"][:8]}  [{b[\"priority\"]}] "
          f"{b[\"title\"]!r}  -> {b[\"recipient_count\"]} sent, {b[\"reply_count\"]} replies")'
    ;;

  replies)
    since_param=""
    if [[ "${1:-}" == "--since" ]]; then
      # e.g. --since 7d — converted to an ISO timestamp for the API.
      since_param=$(SPEC="$2" py '
import datetime, os
spec = os.environ["SPEC"]
days = int(spec[:-1]) if spec.endswith("d") else int(spec)
t = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
# 'Z' suffix instead of '+00:00' — a raw '+' in a query string decodes
# as a space and 422s; curl does not URL-encode for us.
print(t.isoformat().replace("+00:00", "Z"))')
    fi
    url="$API/v1/admin/messages/replies"
    [[ -n "$since_param" ]] && url="$url?since=$since_param"
    curl -sf "${auth[@]}" "$url" | py '
import json, sys
rows = json.load(sys.stdin)
if not rows:
    print("no replies")
for r in rows:
    print(f"{r[\"created_at\"][:16]}  user {r[\"user_id\"][:8]}  "
          f"(re broadcast {(r[\"broadcast_id\"] or \"-\")[:8]}, reply_to {(r[\"reply_to_id\"] or \"-\")[:8]})")
    print(f"    {r[\"body\"]}")'
    ;;

  *)
    echo "usage: scripts/messages.sh send|list|replies (see header)" >&2
    exit 1
    ;;
esac
