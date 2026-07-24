#!/usr/bin/env python3
"""Dump TestFlight (iOS) beta testers as CSV for engagement comms (CR082).

Reads the App Store Connect API — the same `.p8` key + issuer that
`scripts/build_testflight.sh` uses — mints a short-lived ES256 JWT, pages
through `/v1/betaTesters`, and writes CSV to stdout (summary to stderr).

  email, first_name, last_name, invite_type, groups

Android has no equivalent: the Play Developer API exposes Google Groups only,
not the email-list testers (CR082 doc). This covers the iOS side only.

Auth (defaults match build_testflight.sh; override via env):
  APP_STORE_API_KEY_ID   default 44VJ5WADL2
  APP_STORE_API_ISSUER   default 289e6201-8fc9-44a3-abde-59e8e278527c
  key file               ~/.appstoreconnect/private_keys/AuthKey_<KEY_ID>.p8

Fails loudly if the key is absent (CR040 degrade-loudly) rather than emitting
an empty CSV that would read as "no testers".

Usage:
  scripts/testflight_testers.py > testflight.csv
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request

import jwt  # PyJWT — present in backend/.venv and system python3

KEY_ID = os.environ.get("APP_STORE_API_KEY_ID", "44VJ5WADL2")
ISSUER = os.environ.get("APP_STORE_API_ISSUER", "289e6201-8fc9-44a3-abde-59e8e278527c")
KEY_FILE = os.path.expanduser(
    os.environ.get("APP_STORE_API_KEY_FILE", f"~/.appstoreconnect/private_keys/AuthKey_{KEY_ID}.p8")
)
BASE = "https://api.appstoreconnect.apple.com/v1"


def die(msg: str) -> None:
    print(f"✗ {msg}", file=sys.stderr)
    sys.exit(1)


def make_token() -> str:
    if not os.path.isfile(KEY_FILE):
        die(
            f"no App Store Connect key at {KEY_FILE}\n"
            f"  Download AuthKey_{KEY_ID}.p8 from App Store Connect → Users and Access\n"
            f"  → Integrations, then: mkdir -p ~/.appstoreconnect/private_keys && "
            f'mv ~/Downloads/AuthKey_*.p8 "$_" && chmod 600 "$_"/AuthKey_*.p8'
        )
    with open(KEY_FILE) as f:
        private_key = f.read()
    now = int(time.time())
    return jwt.encode(
        {"iss": ISSUER, "iat": now, "exp": now + 600, "aud": "appstoreconnect-v1"},
        private_key,
        algorithm="ES256",
        headers={"kid": KEY_ID, "typ": "JWT"},
    )


def fetch_all(token: str) -> tuple[list[dict], dict]:
    """Page through betaTesters, returning (testers, group_id -> group_name)."""
    testers: list[dict] = []
    groups: dict[str, str] = {}
    url = (
        f"{BASE}/betaTesters?include=betaGroups&limit=200"
        "&fields[betaTesters]=firstName,lastName,email,inviteType,betaGroups"
        "&fields[betaGroups]=name"
    )
    while url:
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.load(resp)
        except urllib.error.HTTPError as e:
            die(f"App Store Connect API {e.code}: {e.read().decode(errors='replace')[:400]}")
        except urllib.error.URLError as e:
            die(f"could not reach App Store Connect: {e.reason}")
        testers.extend(payload.get("data", []))
        for inc in payload.get("included", []):
            if inc.get("type") == "betaGroups":
                groups[inc["id"]] = inc.get("attributes", {}).get("name", "")
        url = payload.get("links", {}).get("next")
    return testers, groups


def main() -> None:
    token = make_token()
    testers, groups = fetch_all(token)

    writer = csv.writer(sys.stdout)
    writer.writerow(["email", "first_name", "last_name", "invite_type", "groups"])
    for t in testers:
        attr = t.get("attributes", {})
        rel = t.get("relationships", {}).get("betaGroups", {}).get("data", []) or []
        group_names = "; ".join(groups.get(g["id"], g["id"]) for g in rel)
        writer.writerow(
            [
                attr.get("email", ""),
                attr.get("firstName", ""),
                attr.get("lastName", ""),
                attr.get("inviteType", ""),
                group_names,
            ]
        )
    print(f"▶ testflight: {len(testers)} testers across {len(groups)} groups", file=sys.stderr)


if __name__ == "__main__":
    main()
