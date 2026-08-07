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


def _code_only(text: str, markers: tuple[str, ...] = ("#", "--")) -> str:
    """Drop whole-line comments, in every comment syntax this file inspects.

    Every "must NOT contain" assertion below runs against this rather than the
    raw file. Three guards in this file have now failed against their own
    targets: the comment explaining what was removed necessarily *quotes the
    removed thing*, so a naive substring check on raw text can only pass if the
    fix ships undocumented. Asserting on executable lines is the honest reading
    of "the old form is gone".

    `--` was added after the SQL guard hit the same wall that `#` was added for
    — `01_website_role.sql`'s own header explains that the website API *used to
    be* the Postgres SUPERUSER, and the guard asserting the role is not granted
    SUPERUSER matched that sentence. Defaulting to both markers means the next
    file type does not repeat it a fourth time; `--` is not a comment in Python
    or YAML, so including it costs those callers nothing.
    """
    return "\n".join(
        line
        for line in text.splitlines()
        if not line.lstrip().startswith(markers)
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
    different images.

    Covers services with an `image:` key. Services built from a Dockerfile are
    covered by `test_every_dockerfile_base_image_is_pinned_by_digest` below —
    see its docstring for why splitting them is load-bearing rather than tidy.
    """
    for name, service in compose["services"].items():
        image = service.get("image")
        if image is None:
            continue  # built from a Dockerfile — asserted by the next test
        assert "@sha256:" in image, f"{name} uses the floating tag {image!r} (CR124/M14)"


def test_every_dockerfile_base_image_is_pinned_by_digest(compose: dict) -> None:
    """M14, the other half — and the half CR124 round 1 shipped unpinned.

    The audit found `backend/Dockerfile` still on a bare `FROM python:3.13-slim`
    while the register claimed "all five images digest-pinned". The claim was
    false, and the reason the suite did not catch it is the more useful lesson:
    the test above `continue`s on any service without an `image:` key, and BOTH
    application services are `build:`-only. So the digest guard covered exactly
    the three services nobody was going to unpin, and neither application image
    was ever checked.

    The mutation proof offered for M14 (unpin the postgres digest → red) was
    real but only ever exercised the compose path, so it was never evidence
    about the Dockerfile-FROM class at all. A mutation that cannot reach a
    surface is not proof about that surface.

    Discovers Dockerfiles from the compose `build:` context rather than a
    hardcoded list, so a service added later is covered without anyone
    remembering to extend this.
    """
    checked = 0
    for name, service in compose["services"].items():
        build = service.get("build")
        if build is None:
            continue
        if isinstance(build, str):
            context, dockerfile = build, "Dockerfile"
        else:
            context = build.get("context", ".")
            dockerfile = build.get("dockerfile", "Dockerfile")
        path = (_REPO_ROOT / context / dockerfile).resolve()
        assert path.is_file(), f"{name}: build context resolves to no Dockerfile at {path}"
        froms = [
            line.split(maxsplit=1)[1].strip()
            for line in _code_only(path.read_text()).splitlines()
            if line.strip().upper().startswith("FROM ")
        ]
        assert froms, f"{name}: {path} has no FROM instruction"
        for image in froms:
            base = image.split(" AS ")[0].split(" as ")[0].strip()
            assert "@sha256:" in base, (
                f"{name}: {dockerfile} builds on the floating tag {base!r}. "
                "A rebuild of this same commit can silently resolve a different "
                "image (CR124/M14)."
            )
        checked += 1
    assert checked >= 2, (
        f"only {checked} build-from-Dockerfile services found; expected both "
        "application images. If a service was renamed, fix this guard rather "
        "than letting it pass vacuously."
    )


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


def test_the_backend_image_gives_the_non_root_user_a_writable_home() -> None:
    """Audit MAJOR 3 — the non-root switch silently broke yfinance's cache.

    `--no-create-home` still records `/home/ami` in passwd, and Docker sets no
    `HOME` on a `USER` switch, so `expanduser("~")` resolved under root-owned
    `/home`. yfinance caches to `platformdirs.user_cache_dir()` and does NOT
    crash on failure — it catches the `OSError`, logs to its own plain logger
    (not our structlog stream), and never memoises the failure, so it retried
    the failing `makedirs` on every single call while permanently losing the
    cookie/crumb cache Yahoo's rate limiting needs.

    Nothing about that is visible from a passing test suite, which is why this
    asserts the *precondition* — a HOME the runtime uid can write — rather than
    trying to simulate yfinance.
    """
    code = _code_only((_REPO_ROOT / "backend" / "Dockerfile").read_text())
    homes = [
        line.split("HOME=", 1)[1].strip().strip('"').split()[0]
        for line in code.splitlines()
        if line.strip().startswith("ENV ") and "HOME=" in line
    ]
    assert homes, (
        "backend/Dockerfile sets no HOME. A non-root USER without one resolves "
        "~ under root-owned /home and every library that caches to "
        "user_cache_dir() fails silently (CR124 audit MAJOR 3)."
    )
    home = homes[-1]
    assert home != "/home/ami", "HOME points at the uncreated default home dir"
    # Must be a path the image actually chowns to the runtime user.
    chowned = [
        line for line in code.splitlines() if "chown -R ami:ami" in line
    ]
    assert chowned, "no chown to the runtime user at all"
    assert any(home.split("/")[1] in line for line in chowned), (
        f"HOME={home} is not under any path chown'd to ami — it will not be writable"
    )


def test_the_redis_healthcheck_can_actually_authenticate(compose: dict) -> None:
    """Audit MINOR 1 — `requirepass` without a matching healthcheck credential
    makes the container permanently unhealthy, which blocks `depends_on:
    service_healthy` and takes the whole stack down. The password is supplied
    via `REDISCLI_AUTH` (which `redis-cli` reads) rather than `-a`, so it stays
    out of the process args."""
    redis = compose["services"]["redis"]
    check = " ".join(map(str, redis["healthcheck"]["test"]))
    assert "redis-cli" in check
    env = redis.get("environment") or {}
    supplies_auth = "REDISCLI_AUTH" in env or "-a" in check
    assert supplies_auth, (
        "redis requires a password but the healthcheck supplies none — the "
        "container never reports healthy (CR124/C3)"
    )


def test_the_website_role_sql_actually_restricts_the_app_database() -> None:
    """Audit MINOR 2 — M8's whole point is that a second role is only a boundary
    if PUBLIC's default CONNECT is revoked. A file that creates a role and stops
    there looks like privilege separation and is not."""
    sql = (_REPO_ROOT / "infra" / "local" / "postgres-init" / "01_website_role.sql").read_text()
    upper = _code_only(sql).upper().replace("\n", " ")
    assert "CREATE ROLE AMI_WEBSITE" in upper, "the low-privilege role is not created"
    assert "REVOKE CONNECT ON DATABASE AMI_TRADE FROM PUBLIC" in upper, (
        "PUBLIC may connect to any database by default — without this revoke the "
        "separate role grants nothing (CR124/M8)"
    )
    for forbidden in ("SUPERUSER", "CREATEROLE", "CREATEDB"):
        assert forbidden not in upper, f"ami_website is granted {forbidden}"


def test_the_backup_script_refuses_to_write_plaintext_by_default() -> None:
    """M13 — a plaintext dump is every user record and magic-link challenge in
    one file, and it is rsynced offsite."""
    code = _code_only((_REPO_ROOT / "infra" / "backups" / "pg-backup.sh").read_text())
    assert "BACKUP_ENCRYPTION_PASSPHRASE" in code
    assert "chmod 600" in code, "dumps are not mode-600"
    assert "PGPASSWORD:-postgres" not in code, "backup script still defaults to the old password"
