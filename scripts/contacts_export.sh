#!/usr/bin/env bash
# Merge tester/user contacts from both platforms into one CSV for engagement
# comms (CR082). Sources:
#   - app DB (alpha)  → scripts/users.sh --contacts   (email-having real users)
#   - TestFlight iOS  → scripts/testflight_testers.py
# Android has no programmatic source (Play API exposes Google Groups only) — read
# it in Play Console → Internal testing → Testers. See the CR082 doc.
#
# Dedupes on lowercased email; tags each row `source` = app_db | testflight | both.
# Output is PERSONAL DATA — written to the working dir, gitignored (contacts_*.csv),
# never committed.
#
# Usage:
#   scripts/contacts_export.sh                 # -> contacts_<date>.csv
#   CONTACTS_OUT=/path/out.csv scripts/contacts_export.sh
#   scripts/contacts_export.sh --no-testflight # app DB only (skip iOS)

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${CONTACTS_OUT:-contacts_$(date +%Y-%m-%d).csv}"
WANT_TF=1
[[ "${1:-}" == "--no-testflight" ]] && WANT_TF=0

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

echo "▶ app DB contacts…" >&2
"${PROJECT_ROOT}/scripts/users.sh" --contacts > "$tmp/app_db.csv"

if [[ "$WANT_TF" == "1" ]]; then
  echo "▶ TestFlight testers…" >&2
  # A TestFlight failure (no key / no network) must not lose the primary DB list —
  # warn loudly and continue with an empty iOS source (degrade loudly, CR040).
  if ! python3 "${PROJECT_ROOT}/scripts/testflight_testers.py" > "$tmp/testflight.csv" 2>"$tmp/tf.err"; then
    cat "$tmp/tf.err" >&2
    echo "⚠ TestFlight source FAILED — merged CSV has app-DB contacts only. Fix the .p8/network and re-run for iOS." >&2
    : > "$tmp/testflight.csv"
  fi
else
  : > "$tmp/testflight.csv"
fi

python3 - "$tmp/app_db.csv" "$tmp/testflight.csv" "$OUT" <<'PY'
import csv, sys

app_path, tf_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
by_email = {}   # lowercased email -> merged row
order = []

def touch(email):
    key = email.strip().lower()
    if not key:
        return None
    if key not in by_email:
        by_email[key] = {
            "email": email.strip(), "name": "", "platform": "", "plan": "",
            "source": "", "rooms_convened": "", "last_activity": "",
            "created": "", "tf_groups": "",
        }
        order.append(key)
    return by_email[key]

def add_source(row, src):
    row["source"] = "both" if row["source"] and row["source"] != src else src

# app DB
try:
    with open(app_path, newline="") as f:
        for r in csv.DictReader(f):
            row = touch(r.get("email", ""))
            if row is None:
                continue
            row["name"] = r.get("display_name", "") or row["name"]
            row["platform"] = r.get("platform", "") or row["platform"]
            row["plan"] = r.get("plan", "")
            row["rooms_convened"] = r.get("rooms_convened", "")
            row["last_activity"] = r.get("last_activity_my", "")
            row["created"] = r.get("created_my", "")
            add_source(row, "app_db")
except FileNotFoundError:
    pass

# TestFlight
try:
    with open(tf_path, newline="") as f:
        for r in csv.DictReader(f):
            row = touch(r.get("email", ""))
            if row is None:
                continue
            if not row["name"]:
                row["name"] = (r.get("first_name", "") + " " + r.get("last_name", "")).strip()
            row["platform"] = row["platform"] or "ios"
            row["tf_groups"] = r.get("groups", "")
            add_source(row, "testflight")
except FileNotFoundError:
    pass

cols = ["email", "name", "platform", "source", "plan",
        "rooms_convened", "last_activity", "created", "tf_groups"]
with open(out_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    for key in order:
        w.writerow({c: by_email[key].get(c, "") for c in cols})

both = sum(1 for v in by_email.values() if v["source"] == "both")
print(f"▶ merged {len(by_email)} unique emails ({both} on both platforms) -> {out_path}",
      file=sys.stderr)
PY

echo "✓ $(cd "$(dirname "$OUT")" && pwd)/$(basename "$OUT")" >&2
