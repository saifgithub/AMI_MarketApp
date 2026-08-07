"""CR124 — pin the melehost/compose hardening so a later edit cannot quietly undo it.

The C3 finding was proven live: from an ordinary LAN device, Postgres answered
as superuser `postgres`/`postgres` and Redis answered `PING` with no auth,
because `docker-compose.yml` published 5434/6379/8001 on `0.0.0.0` — and Docker
bypasses ufw, so the host firewall was never in the path.

These are text assertions against the compose file rather than behavioural
tests, because the behaviour lives on melehost and the Mac runs no Docker
(CLAUDE.md: pure editor). That makes them a weaker class of guard than a real
connection attempt, and the acceptance evidence in
`infra/CR124_HARDENING_RUNBOOK.md` is what actually proves the port is closed.
What these DO catch is the regression that is actually likely: someone editing
this file months from now, restoring a convenient `"5434:5432"` for a local
debugging session, and shipping it.

Deliberately asserted on SHAPE, not on the exact literal — `_published_ports`
parses the port list and checks the host-interface half, so reformatting the
YAML or renaming a service does not create a false pass (P15: matching a name
tests whether someone followed a convention; matching the shape tests the thing
you care about).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
_COMPOSE_PATH = _REPO_ROOT / "docker-compose.yml"

# Services whose published ports must never be reachable off-host. `api-alpha`
# is deliberately absent: it fronts an authenticated API that is already
# internet-reachable through the Cloudflare Tunnel, and the tunnel's ingress
# target lives in the CF dashboard rather than in this repo, so a loopback bind
# there could take Alpha down. CR124's own acceptance list names these three.
_MUST_BE_LOOPBACK = ("postgres", "redis", "api-website")


def _code_only(text: str) -> str:
    """Drop whole-line `#` comments.

    Every "must NOT contain" assertion below runs against this rather than the
    raw file. Both of these guards initially failed against their own targets:
    the comments explaining what was removed necessarily *quote the removed
    thing*, so a naive substring check on the raw text can never pass unless the
    fix ships undocumented. Asserting on the executable lines is the honest
    reading of "the old form is gone".
    """
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )


@pytest.fixture(scope="module")
def compose() -> dict:
    return yaml.safe_load(_COMPOSE_PATH.read_text())


def _published_ports(service: dict) -> list[str]:
    """The host-side interface of every published port, '' when unqualified.

    Compose short syntax is `[HOST_IF:]HOST_PORT:CONTAINER_PORT`. Splitting from
    the right leaves everything before the last two fields as the interface, so
    an unqualified "5434:5432" yields '' — which is exactly the 0.0.0.0 case.
    """
    out = []
    for entry in service.get("ports") or []:
        if isinstance(entry, dict):  # long syntax
            out.append(str(entry.get("host_ip", "")))
            continue
        parts = str(entry).rsplit(":", 2)
        out.append(parts[0] if len(parts) == 3 else "")
    return out


@pytest.mark.parametrize("service_name", _MUST_BE_LOOPBACK)
def test_datastore_ports_are_bound_to_loopback_only(compose: dict, service_name: str) -> None:
    service = compose["services"][service_name]
    interfaces = _published_ports(service)
    assert interfaces, f"{service_name} publishes no ports — did the service get renamed?"
    for interface in interfaces:
        assert interface == "127.0.0.1", (
            f"{service_name} publishes a port on {interface or '0.0.0.0 (unqualified)'!r}. "
            "Docker bypasses ufw, so this is reachable from the whole LAN (CR124/C3)."
        )


def test_no_service_hardcodes_the_default_postgres_password(compose: dict) -> None:
    """The literal that made C3 exploitable, in any service, in any field."""
    raw = _COMPOSE_PATH.read_text()
    assert "postgres:postgres@" not in raw, (
        "a DSN still carries the default superuser password (CR124/C3)"
    )
    pg_env = compose["services"]["postgres"]["environment"]
    assert pg_env["POSTGRES_PASSWORD"] != "postgres"


@pytest.mark.parametrize(
    "variable",
    ["POSTGRES_PASSWORD", "REDIS_PASSWORD", "WEBSITE_DB_PASSWORD"],
)
def test_credentials_refuse_to_default(variable: str) -> None:
    """`:?` not `:-`.

    A `:-` default would let a host that never got the key boot happily with a
    known credential, which is precisely the silent-fallback shape CR040
    forbids. `:?` makes compose refuse to parse instead.
    """
    raw = _COMPOSE_PATH.read_text()
    assert f"${{{variable}:?" in raw, f"{variable} must use ${{VAR:?...}}, never a default"
    assert f"${{{variable}:-" not in raw, f"{variable} has a silent default — CR040"


def test_redis_requires_a_password(compose: dict) -> None:
    command = compose["services"]["redis"].get("command")
    assert command, "redis has no command override, so --requirepass is not set (CR124/C3)"
    assert "--requirepass" in " ".join(map(str, command))


def test_the_website_api_is_not_the_postgres_superuser(compose: dict) -> None:
    """M8: the public marketing container was a pivot into the app database."""
    dsn = compose["services"]["api-website"]["environment"]["DATABASE_URL"]
    assert "://ami_website:" in dsn, f"website API still connects as a shared role: {dsn}"
    assert "postgres:" not in dsn.split("@")[0]


def test_every_service_has_a_memory_limit(compose: dict) -> None:
    """M13 — containers were unbounded against the host's 14.86 GiB, which is
    what makes the DEF184 body-buffering DoS reach the whole box rather than
    one container."""
    for name, service in compose["services"].items():
        assert service.get("mem_limit"), f"{name} has no mem_limit (CR124/M13)"


def test_every_image_is_pinned_by_digest(compose: dict) -> None:
    """M14 — a floating tag means two builds of the same commit can ship
    different images."""
    for name, service in compose["services"].items():
        image = service.get("image")
        if image is None:
            continue  # built from a Dockerfile in this repo
        assert "@sha256:" in image, f"{name} uses the floating tag {image!r} (CR124/M14)"


def test_the_stack_declares_its_own_network(compose: dict) -> None:
    """N6 — the AMI services sat on the project default network, which
    melehost's separate n8n container had joined, giving an RCE-prone
    automation tool a route to the superuser DB and the internal API."""
    assert compose.get("networks"), "no explicit network — services fall back to the shared default"
    declared = set(compose["networks"])
    for name, service in compose["services"].items():
        nets = service.get("networks")
        assert nets, f"{name} is not on an explicit network (CR124/N6)"
        assert set(nets) <= declared, f"{name} references an undeclared network: {nets}"


@pytest.mark.parametrize(
    "dockerfile",
    ["backend/Dockerfile", "website_api/Dockerfile"],
)
def test_app_images_drop_root(dockerfile: str) -> None:
    """N7 — both application containers ran as root.

    Asserts a USER directive exists and is not root, rather than asserting the
    specific username, so renaming the account does not fail the guard.
    """
    text = (_REPO_ROOT / dockerfile).read_text()
    users = [
        line.split(maxsplit=1)[1].strip()
        for line in text.splitlines()
        if line.strip().startswith("USER ")
    ]
    assert users, f"{dockerfile} has no USER directive — the container runs as root (CR124/N7)"
    assert users[-1] not in ("root", "0"), f"{dockerfile} ends up as root: {users[-1]!r}"


def test_the_backend_image_installs_from_the_lockfile() -> None:
    """M14 — `uv pip install -e '.[dev]'` re-resolved on every rebuild and
    shipped pytest/ruff/mypy into a production image."""
    code = _code_only((_REPO_ROOT / "backend" / "Dockerfile").read_text())
    assert "--locked" in code, "backend image does not install from uv.lock (CR124/M14)"
    assert "--no-dev" in code, "backend image still installs the dev dependency group"
    assert '-e ".[dev]"' not in code


def test_the_backup_script_refuses_to_write_plaintext_by_default() -> None:
    """M13 — a plaintext dump is every user record and magic-link challenge in
    one file, and it is rsynced offsite."""
    code = _code_only((_REPO_ROOT / "infra" / "backups" / "pg-backup.sh").read_text())
    assert "BACKUP_ENCRYPTION_PASSPHRASE" in code
    assert "chmod 600" in code, "dumps are not mode-600"
    assert "PGPASSWORD:-postgres" not in code, "backup script still defaults to the old password"


def test_the_promotion_hold_is_armed_while_the_host_is_unhardened() -> None:
    """The DEF222 lesson, made structural.

    CR124's compose REQUIRES three keys melehost has never been given, and
    compose evaluates `:?` at parse time — so promoting this file to a host
    that has not run the runbook does not degrade, it takes Alpha down and
    cannot bring it back. `infra/PROMOTION_HOLD.md` is the gate that stops
    that, and DEF222 happened because the gate existed and was never armed.

    Delete this test in the same commit that clears the hold — it asserts a
    TEMPORARY state on purpose, and a guard that outlives its condition
    becomes noise that the next person routes around.
    """
    text = (_REPO_ROOT / "infra" / "PROMOTION_HOLD.md").read_text()
    active = text.split("## ACTIVE HOLDS", 1)[1].split("## CLEARED HOLDS", 1)[0]
    assert "CR124" in active, (
        "CR124's hold is not in ACTIVE HOLDS. If melehost has been hardened and the "
        "hold legitimately cleared, delete this test in that same commit."
    )
