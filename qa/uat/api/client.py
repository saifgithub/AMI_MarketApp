"""HTTP client + test-user seeding for the live-Alpha UAT API suite (CR263).

Every user this suite creates is tagged `last_app_version='uat'` +
`device_model='ami-uat'` (via the normal `POST /v1/auth/anon` body) so it can be
filtered out of real-user counts, the same way CR035's `room-benchmark` rows
are. Plan and credits are set through the admin API — the same route Saiful's
back-office uses — and every user is suspended at teardown.

Target defaults to LAN-direct melehost; set `UAT_BASE_URL` to go through the
public Cloudflare hostname instead (needs the explicit User-Agent below —
Cloudflare 403s `python-httpx/*`, measured for urllib in CR175).
"""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BASE_URL = "http://192.168.20.59:8000"
USER_AGENT = "ami-uat/1.0 (CR263)"
UAT_APP_VERSION = "uat"
UAT_DEVICE_MODEL = "ami-uat"


def _read_env_file(path: Path, key: str) -> str | None:
    try:
        for raw in path.read_text().splitlines():
            if raw.startswith(f"{key}="):
                value = raw.split("=", 1)[1].strip().strip("'\"")
                return value or None
    except OSError:
        return None
    return None


def _secrets_root() -> Path:
    """Git-ignored secret files live only in the main checkout; a worktree
    points back at it with UAT_SECRETS_ROOT."""
    return Path(os.environ.get("UAT_SECRETS_ROOT") or REPO_ROOT)


def env(key: str) -> str | None:
    """Process env first, then the git-ignored `qa/uat/.uat.env`."""
    return os.environ.get(key) or _read_env_file(_secrets_root() / "qa" / "uat" / ".uat.env", key)


def base_url() -> str:
    return (env("UAT_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")


def admin_secret() -> str | None:
    return env("UAT_ADMIN_SECRET") or _read_env_file(_secrets_root() / "infra" / "alpha.env", "ADMIN_SECRET")


def new_client(token: str | None = None, timeout: float = 30.0) -> httpx.Client:
    headers = {"User-Agent": USER_AGENT}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.Client(base_url=base_url(), headers=headers, timeout=timeout)


@dataclass
class UatUser:
    id: str
    token: str
    plan: str
    http: httpx.Client = field(repr=False)

    def get(self, path: str, **kw) -> httpx.Response:
        return self.http.get(path, **kw)

    def post(self, path: str, **kw) -> httpx.Response:
        return self.http.post(path, **kw)

    def patch(self, path: str, **kw) -> httpx.Response:
        return self.http.patch(path, **kw)

    def put(self, path: str, **kw) -> httpx.Response:
        return self.http.put(path, **kw)

    def delete(self, path: str, **kw) -> httpx.Response:
        return self.http.delete(path, **kw)


class Seeder:
    """Creates tagged UAT users and suspends them all on `close()`."""

    def __init__(self, admin: httpx.Client, run_id: str):
        self.admin = admin
        self.run_id = run_id
        self.created: list[UatUser] = []

    def anon_user(self, locale: str = "en") -> UatUser:
        # /v1/auth/anon is limited to 10/min per IP; parallel suites share the
        # Mac's IP, so back off on 429 rather than fail the precondition.
        with new_client() as anon:
            for attempt in range(6):
                r = anon.post("/v1/auth/anon", json=self._anon_body(locale))
                if r.status_code != 429:
                    break
                time.sleep(10 * (attempt + 1))
        r.raise_for_status()
        body = r.json()
        user = UatUser(
            id=str(body["user"]["id"]), token=body["token"],
            plan=body["user"].get("plan", "floor_pass"), http=new_client(body["token"]),
        )
        self.created.append(user)
        return user

    def _anon_body(self, locale: str) -> dict:
        return {
            "device_user_id": str(uuid.uuid4()),
            "locale": locale,
            "timezone": "Asia/Riyadh",
            "device_model": UAT_DEVICE_MODEL,
            "os_version": f"uat-run-{self.run_id}",
            "app_version": UAT_APP_VERSION,
            "device_install_id": str(uuid.uuid4()),
        }

    def set_plan(self, user: UatUser, plan: str) -> None:
        r = self.admin.patch(f"/v1/admin/users/{user.id}/plan",
                             json={"plan": plan, "note": f"CR263 UAT run {self.run_id}"})
        r.raise_for_status()
        user.plan = plan

    def add_credits(self, user: UatUser, delta: int) -> None:
        r = self.admin.post(f"/v1/admin/users/{user.id}/credits",
                            json={"delta": delta, "note": f"CR263 UAT run {self.run_id}"})
        r.raise_for_status()

    def user(self, plan: str = "floor_pass", credits: int = 0, locale: str = "en") -> UatUser:
        u = self.anon_user(locale=locale)
        if plan != u.plan:
            self.set_plan(u, plan)
        if credits:
            self.add_credits(u, credits)
        return u

    def detail(self, user: UatUser) -> dict:
        r = self.admin.get(f"/v1/admin/users/{user.id}")
        r.raise_for_status()
        return r.json()

    def close(self) -> list[str]:
        failures = []
        for u in self.created:
            r = self.admin.post(f"/v1/admin/users/{u.id}/suspend",
                                json={"note": f"CR263 UAT teardown {self.run_id}"})
            if r.status_code not in (200, 409):
                failures.append(f"{u.id}: suspend -> {r.status_code}")
            u.http.close()
        return failures
