#!/usr/bin/env python3
"""Postflight — one command, one exit code, run after a promotion (CR175 Tier C).

`/promote-to-alpha` steps 7 and 7b used to end in "compare this against intent".
Six of the eight steps ended in operator judgement, and the config-gate step in
particular asked a human to set-diff ~40 keys in `infra/alpha.env` against a
JSON response, by eye, after a deploy, at whatever hour the deploy happened.
Measured on 2026-08-12: nobody had ever noticed that the response covered 9 of
98 fields (CR175 F3). That is not an attention failure — it is a check whose
correct execution was never mechanically possible.

This does the comparison. It exits 0 or it does not, and on failure it names
the specific thing to fix rather than printing a body to read.

    scripts/promotion/postflight.py --expect-sha $(git rev-parse HEAD) \
                                    --expect-tag alpha-2026-08-12-4

Checks, in order of what has actually gone wrong here before:

  identity    the container reports the commit and tag that were just promoted
              — F2, because until now nothing recorded what was running
  readiness   /v1/ready green: DB, schema at head (DEF215), LLM resolved
  config      every populated key in infra/alpha.env reads configured=true in
              the container — DEF038, DEF063, and the class DEF260 belongs to
  market      the quote path is not silently on the mock walk

**Never echoes a value.** `infra/alpha.env` is gitignored and stays that way:
this reads key NAMES and the container's booleans, and prints only names.

Exit codes: 0 all checks passed · 1 a check failed · 2 could not run (network,
missing file, no admin secret) — deliberately distinct, because "the promotion
is broken" and "I could not tell" must not look the same to whoever is reading.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ALPHA_ENV = _REPO_ROOT / "infra" / "alpha.env"
_DEFAULT_BASE = "https://api-alpha.agenticmarketintel.ai"

# Keys that live in the env file but are not `Settings` fields — compose-level
# wiring and host-side plumbing. Each states why, so an unexplained entry reads
# as the bug it would be.
_NOT_SETTINGS_FIELDS: dict[str, str] = {
    "AMI_ENV": "forwarded to the container as ENV",
    "POSTGRES_PASSWORD": "compose-level: postgres service credential",
    "POSTGRES_USER": "compose-level: postgres service credential",
    "POSTGRES_DB": "compose-level: postgres service credential",
    "REDIS_PASSWORD": "compose-level: redis service credential",
    "CF_TUNNEL_TOKEN": "cloudflared service, not the api container",
    "GIT_SHA": "build arg (CR175 F2), not a runtime env var",
    "ALPHA_TAG": "build arg (CR175 F2), not a runtime env var",
}

_ENV_LINE = re.compile(r"^([A-Z][A-Z0-9_]*)=(.*)$")


class CheckFailed(Exception):
    """A check ran and the answer was no."""


class CannotRun(Exception):
    """A check could not run. Distinct from failing — see the module docstring."""


def _populated_keys(env_path: Path) -> dict[str, str]:
    """Key names that are uncommented AND carry a non-empty value.

    Values are read only to decide emptiness and are never returned or printed.
    A commented-out key is a deliberate park (DEF063 parked two on purpose), so
    it is not a gap; an uncommented key with an empty value is, and it is
    treated as absent because that is how `bool(settings.x)` treats it.
    """
    if not env_path.exists():
        raise CannotRun(f"{env_path} not found — it is gitignored; see infra/README.md")
    out: dict[str, str] = {}
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _ENV_LINE.match(line)
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip().strip("'\"")
        if value:
            out[key] = "<set>"
    return out


def _admin_secret(env_path: Path) -> str:
    for raw in env_path.read_text().splitlines():
        if raw.startswith("ADMIN_SECRET="):
            secret = raw.split("=", 1)[1].strip().strip("'\"")
            if secret:
                return secret
    raise CannotRun("ADMIN_SECRET not set in infra/alpha.env — cannot authenticate")


# Cloudflare 403s the default `Python-urllib/3.x` User-Agent at the edge, before
# the request reaches the tunnel — measured 2026-08-12: the same URL returns 200
# under `curl/8.7.1` and 403 under `Python-urllib/3.13`, with `server:
# cloudflare` on the failure. Any Python tooling that hits Alpha through the
# public hostname needs its own UA. Naming the tool is also the better answer
# for the CF log: a 403 from an unidentified client is indistinguishable from an
# outage, which is the failure mode this whole CR is about.
_USER_AGENT = "ami-postflight/1.0 (CR175)"


def _get(url: str, secret: str | None, timeout: int) -> tuple[int, dict]:
    req = urllib.request.Request(url)
    req.add_header("User-Agent", _USER_AGENT)
    if secret:
        req.add_header("Authorization", f"Bearer {secret}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read().decode())
        except Exception:
            return exc.code, {}
    except Exception as exc:
        raise CannotRun(f"{url} unreachable: {type(exc).__name__}: {exc}") from exc


# ── checks ────────────────────────────────────────────────────────────────────

def check_identity(base: str, secret: str, expect_sha: str, expect_tag: str | None,
                   timeout: int) -> list[str]:
    """F2. Until this existed, no query answered "is what is running what I
    shipped?" — and every incident diagnosis began by assuming it was."""
    _status, body = _get(f"{base}/v1/ready", secret, timeout)
    got_sha = str(body.get("git_sha", ""))
    got_tag = str(body.get("alpha_tag", ""))
    if not got_sha:
        raise CannotRun(
            "/v1/ready returned no git_sha — either the admin bearer was "
            "rejected (the anonymous view omits it) or the container predates "
            "CR175 Tier A"
        )
    problems: list[str] = []
    if got_sha == "unset":
        problems.append(
            "container is UNSTAMPED (git_sha=unset) — it was built without "
            "GIT_SHA, i.e. not through /promote-to-alpha"
        )
    elif not expect_sha.startswith(got_sha) and not got_sha.startswith(expect_sha):
        problems.append(
            f"running commit {got_sha} != promoted commit {expect_sha} — the "
            "rsync or the image build did not land what you tagged"
        )
    if expect_tag and got_tag != expect_tag:
        problems.append(f"running tag {got_tag!r} != promoted tag {expect_tag!r}")
    return problems


def check_tree(host: str, remote: str, timeout: int) -> list[str]:
    """Does the box hold what the Mac holds? — the check the stamp cannot make.

    `docker-compose.yml` bind-mounts `./backend/app`, `./backend/scripts`,
    `./backend/tests` and `./content` read-only over the image. **The running
    Python is the rsync'd host filesystem, not the image contents.** So
    `GIT_SHA` — baked at build time — describes the image, and the image's
    `app/` is shadowed by the mount. The stamp answers "which commit was this
    image built from", never "which bytes is uvicorn importing".

    An rsync dry-run answers the second question directly: any itemized line
    means the box differs from the Mac, and after a successful promotion there
    should be none. This is also the only check that would catch a partial
    rsync, which is precisely the failure the stamp would report as fine.

    Same exclude list as `/promote-to-alpha` step 3, and it must stay the same:
    `audit/`, `reports/` and `backtest_results/` are melehost-generated and
    absent here (DEF081, DEF276), so omitting them would report every one of
    them as drift — a check that cries wolf is a check that gets ignored, which
    is the F5 failure this CR exists to stop repeating.
    """
    import subprocess

    excludes = [
        ".env", ".venv", "__pycache__", ".dart_tool", "*.egg-info",
        ".pytest_cache", ".local.db*", "mobile/", ".claude/", ".git",
        ".idea", ".vscode", "website/", "audit/", "reports/",
        # DEF276 — bind-mounted `rw` into api-alpha, written by the container,
        # absent from the Mac. The rule: any `rw` bind mount is host-generated.
        "backtest_results/",
    ]
    cmd = ["rsync", "-az", "--delete", "--dry-run", "--itemize-changes"]
    cmd += [f"--exclude={p}" for p in excludes]
    cmd += [f"{_REPO_ROOT}/", f"{host}:{remote}"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout * 6)
    except Exception as exc:
        raise CannotRun(f"rsync dry-run failed to launch: {exc}") from exc
    if proc.returncode != 0:
        raise CannotRun(f"rsync dry-run exited {proc.returncode}: "
                        f"{proc.stderr.strip()[:200]}")

    drift = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    if not drift:
        return []
    problems = [f"{len(drift)} path(s) differ between this worktree and "
                f"{host}:{remote} — the box is not running what you shipped"]
    problems += [f"  {ln}" for ln in drift[:15]]
    if len(drift) > 15:
        problems.append(f"  … and {len(drift) - 15} more")
    return problems


def check_readiness(base: str, secret: str, timeout: int) -> list[str]:
    """DEF215's detector, plus DB and provider resolution."""
    status, body = _get(f"{base}/v1/ready", secret, timeout)
    if status == 200 and body.get("ready") is True:
        return []
    if status == 404:
        return ["/v1/ready returned 404 — the container has no readiness "
                "endpoint, so the code it is running predates CR175 Tier A. "
                "After a promotion that is a failure: what you shipped did "
                "not land."]
    problems = [f"/v1/ready returned {status}, ready={body.get('ready')}"]
    for probe in body.get("probes", []):
        if probe.get("gating") and not probe.get("ok"):
            detail = {k: v for k, v in probe.items()
                      if k not in ("name", "ok", "gating")}
            problems.append(f"  probe {probe['name']}: {detail}")
    return problems


def check_config_parity(base: str, secret: str, env_path: Path,
                        timeout: int) -> list[str]:
    """DEF038, DEF063 — the set-diff no human reliably performs.

    Direction that matters: a key POPULATED on the Mac and absent in the
    container. The reverse (configured in the container, not in the env file)
    is legitimate — a `Settings` default, or compose setting it literally.
    """
    status, body = _get(f"{base}/v1/admin/config-check", secret, timeout)
    if status != 200:
        raise CannotRun(f"/v1/admin/config-check returned {status}")
    coverage = body.get("settings_coverage")
    if coverage is None:
        raise CannotRun(
            "config-check has no settings_coverage — the container predates "
            "CR175 Tier B, so only 9 of ~100 fields are visible and this "
            "check would pass by not looking"
        )
    container = {row["setting"]: row["configured"] for row in coverage}

    problems: list[str] = []
    for key in sorted(_populated_keys(env_path)):
        if key in _NOT_SETTINGS_FIELDS:
            continue
        if key not in container:
            problems.append(
                f"{key}: populated in infra/alpha.env, not a Settings field — "
                "either add the field or record it in _NOT_SETTINGS_FIELDS "
                "with a reason"
            )
        elif not container[key]:
            problems.append(
                f"{key}: populated in infra/alpha.env, configured=false in the "
                f"container — add `{key}: ${{{key}}}` to docker-compose.yml's "
                "api-alpha environment block (this is the DEF038/DEF063 bug)"
            )
    return problems


def check_market_data(base: str, timeout: int) -> list[str]:
    """`mock_walk` means the live feed failed through. Unauthenticated route."""
    status, body = _get(f"{base}/v1/sim/quote/AAPL", None, timeout)
    if status != 200:
        raise CannotRun(f"/v1/sim/quote/AAPL returned {status}")
    source = str(body.get("source", ""))
    if source == "mock_walk":
        return ["quote source is mock_walk — the live feed fell through; "
                "prices are a deterministic random walk"]
    if source not in ("yfinance", "yahoo"):
        return [f"quote source is {source!r} — expected yfinance or yahoo"]
    return []


# ── driver ────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--expect-sha", required=True,
                    help="the commit that was promoted (git rev-parse HEAD)")
    ap.add_argument("--expect-tag", default=None,
                    help="the alpha-* tag that was applied")
    ap.add_argument("--base", default=_DEFAULT_BASE)
    ap.add_argument("--env-file", default=str(_ALPHA_ENV))
    ap.add_argument("--host", default="melehost", help="ssh alias for the box")
    ap.add_argument("--remote", default="~/ami_trade/", help="deploy path on the box")
    ap.add_argument("--timeout", type=int, default=20)
    args = ap.parse_args()

    env_path = Path(args.env_file)
    try:
        secret = _admin_secret(env_path)
    except CannotRun as exc:
        print(f"CANNOT RUN — {exc}", file=sys.stderr)
        return 2

    checks = [
        ("identity", lambda: check_identity(
            args.base, secret, args.expect_sha, args.expect_tag, args.timeout)),
        ("tree", lambda: check_tree(args.host, args.remote, args.timeout)),
        ("readiness", lambda: check_readiness(args.base, secret, args.timeout)),
        ("config", lambda: check_config_parity(
            args.base, secret, env_path, args.timeout)),
        ("market", lambda: check_market_data(args.base, args.timeout)),
    ]

    failed = False
    unable = False
    for name, run in checks:
        try:
            problems = run()
        except CannotRun as exc:
            print(f"  [?] {name:10s} COULD NOT RUN — {exc}")
            unable = True
            continue
        if problems:
            print(f"  [x] {name:10s} FAILED")
            for line in problems:
                print(f"        {line}")
            failed = True
        else:
            print(f"  [v] {name:10s} ok")

    if failed:
        print("\nPOSTFLIGHT FAILED — the promotion completed and something is "
              "wrong with it. Fix forward or /rollback-alpha.")
        return 1
    if unable:
        print("\nPOSTFLIGHT INCONCLUSIVE — at least one check could not run. "
              "This is not a pass.")
        return 2
    print("\nPOSTFLIGHT PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
