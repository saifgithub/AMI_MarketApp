"""State seeding for the exhaustive crawl (CR264 phase C).

Many surfaces only exist once the user has state: a holding, an inbox message,
credits, a plan. Seed the app's OWN anonymous user (the QA build tags it
`device_model ami-uat-qa`, so real-user reports exclude it) before the crawl.

What can and cannot be done from the Mac:

1. The user's `device_user_id` is readable on the iOS Simulator: the app keeps
   it in NSUserDefaults (`flutter.ami.device_user_id`), reachable through
   `xcrun simctl get_app_container <udid> <bundle> data`.
2. The user's BEARER TOKEN is not. It lives in the Keychain
   (flutter_secure_storage), and the simulator's keychain-2-debug.db rows are
   encrypted. So everything that needs the user's own API (a trade, a watchlist
   ticker, a price alert) cannot be seeded here; the crawler drives those
   through the UI (crawler/ui_seed.py).
3. Admin endpoints work without the token: plan, credits and a targeted inbox
   broadcast (`mode=user`, one id). Those are what this module seeds.

Android (the A17 rig runs a release APK): no run-as, no plist. Seeding is a
logged no-op there; the Android crawl covers whatever the default state shows.

Never raises into the crawl: every step is independent and a failure is a note.

The admin client is stdlib-only (the Appium venv has no httpx); secret
resolution mirrors qa/uat/api/client.py (CR263): UAT_ADMIN_SECRET, else
`qa/uat/.uat.env`, else `infra/alpha.env` ADMIN_SECRET, all under
UAT_SECRETS_ROOT (the main checkout; a worktree has no secrets).
"""

from __future__ import annotations

import json
import os
import plistlib
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

_UUID = re.compile(r"^[0-9a-fA-F-]{36}$")
DEVICE_USER_KEY = "flutter.ami.device_user_id"
DEFAULT_BASE_URL = "http://192.168.20.59:8000"
_UA = "ami-uat/1.0 (CR264 crawl)"


@dataclass
class SeedResult:
    user_id: str = ""
    notes: list[str] = field(default_factory=list)
    unlocked: list[str] = field(default_factory=list)

    def note(self, msg: str) -> None:
        self.notes.append(msg)


def _read_env_file(path: Path, key: str) -> str | None:
    try:
        for raw in path.read_text().splitlines():
            if raw.startswith(f"{key}="):
                return raw.split("=", 1)[1].strip().strip("'\"") or None
    except OSError:
        return None
    return None


def _secrets_root() -> Path:
    return Path(os.environ.get("UAT_SECRETS_ROOT") or Path(__file__).resolve().parents[3])


def admin_secret() -> str | None:
    return (os.environ.get("UAT_ADMIN_SECRET")
            or _read_env_file(_secrets_root() / "qa" / "uat" / ".uat.env", "UAT_ADMIN_SECRET")
            or _read_env_file(_secrets_root() / "infra" / "alpha.env", "ADMIN_SECRET"))


def base_url() -> str:
    return (os.environ.get("UAT_BASE_URL")
            or _read_env_file(_secrets_root() / "qa" / "uat" / ".uat.env", "UAT_BASE_URL")
            or DEFAULT_BASE_URL).rstrip("/")


class Admin:
    """Minimal admin client: returns parsed JSON, raises RuntimeError on non-2xx."""

    def __init__(self, secret: str, base: str | None = None):
        self.secret, self.base = secret, base or base_url()

    def call(self, method: str, path: str, body=None, params: dict | None = None):
        url = self.base + path + (("?" + urllib.parse.urlencode(params)) if params else "")
        req = urllib.request.Request(
            url, method=method, data=json.dumps(body).encode() if body is not None else None,
            headers={"Authorization": f"Bearer {self.secret}", "User-Agent": _UA,
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"{method} {path} -> {exc.code}: {exc.read()[:160]!r}") from exc
        return json.loads(raw) if raw else None


def read_device_user_id(udid: str, bundle_id: str) -> str:
    """The app's device_user_id from the simulator's NSUserDefaults plist."""
    out = subprocess.run(["xcrun", "simctl", "get_app_container", udid, bundle_id, "data"],
                         capture_output=True, text=True, timeout=30)
    if out.returncode != 0:
        raise RuntimeError(f"simctl get_app_container failed: {out.stderr.strip()[:200]}")
    prefs = Path(out.stdout.strip()) / "Library" / "Preferences" / f"{bundle_id}.plist"
    if not prefs.exists():
        raise RuntimeError(f"no preferences plist at {prefs} (has the app launched yet?)")
    value = plistlib.loads(prefs.read_bytes()).get(DEVICE_USER_KEY)
    if not isinstance(value, str) or not _UUID.match(value):
        raise RuntimeError(f"{DEVICE_USER_KEY} missing or malformed in {prefs.name}")
    return value


def resolve_user(admin: Admin, device_user_id: str) -> dict:
    rows = admin.call("GET", "/v1/admin/users", params={"device_user_id": device_user_id})
    if len(rows or []) != 1:
        raise RuntimeError(f"expected 1 user for device_user_id, admin search returned {len(rows or [])}")
    return rows[0]


def seed_user(admin: Admin, user_id: str, *, plan: str = "trader", credits: int = 200,
              message: bool = True, run_id: str = "crawl") -> SeedResult:
    res = SeedResult(user_id=user_id)
    note = f"CR264 crawl seed {run_id}"
    try:
        admin.call("PATCH", f"/v1/admin/users/{user_id}/plan", {"plan": plan, "note": note})
        res.unlocked.append(f"plan={plan}: plan-gated surfaces open (Brief, 1-on-1, Portfolio Health 'generate' state); house ads/paywall edges go away")
    except Exception as exc:
        res.note(f"seed plan failed: {str(exc)[:160]}")
    if credits:
        try:
            admin.call("POST", f"/v1/admin/users/{user_id}/credits", {"delta": credits, "note": note})
            res.unlocked.append(f"+{credits} credits: Room / 1-on-1 / Brief sends are not blocked by an empty balance")
        except Exception as exc:
            res.note(f"seed credits failed: {str(exc)[:160]}")
    if message:
        try:
            admin.call("POST", "/v1/admin/messages", {
                "title": "UAT crawl message",
                "body": "Seeded by the CR264 crawler so the Inbox has a broadcast to open.",
                "audience": {"mode": "user", "user_ids": [user_id]}})
            res.unlocked.append("inbox broadcast: the Inbox has a message to open (message_detail)")
        except Exception as exc:
            res.note(f"seed inbox message failed: {str(exc)[:160]}")
    return res


def seed_for_crawl(profile, *, plan: str = "trader", credits: int = 200) -> SeedResult:
    """iOS Simulator: admin seed of the app's own user. Anything else: a logged no-op."""
    from config.devices import IOS
    res = SeedResult()
    if profile.platform != IOS:
        res.note("seeding skipped on Android: the rig runs a release APK, so the app's device_user_id "
                 "(SharedPreferences) is not readable without run-as; the crawl uses the default state")
        return res
    try:
        secret = admin_secret()
        if not secret:
            res.note("seeding skipped: no ADMIN_SECRET (set UAT_ADMIN_SECRET, or UAT_SECRETS_ROOT to the main checkout)")
            return res
        admin = Admin(secret)
        dev_id = read_device_user_id(profile.serial, profile.bundle_id)
        user = resolve_user(admin, dev_id)
        res = seed_user(admin, str(user["id"]), plan=plan, credits=credits)
    except Exception as exc:
        res.note(f"seeding failed: {exc.__class__.__name__}: {str(exc)[:200]}")
    return res
