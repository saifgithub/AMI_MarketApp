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
_SUITE_VERDICT = _REPO_ROOT / ".deliveryos" / "suite_verdict.json"
_FULL_SUITE_TARGET = "backend/tests/unit/"
_SUITE_VERDICT_MAX_AGE_H = 6

# Keys that live in the env file and are legitimately NOT `Settings` fields.
#
# **Imported, never re-listed.** `backend/tests/unit/test_config_compose_parity.py`
# already owns this table as `_ENV_KEYS_WITHOUT_SETTINGS`, with a stated reason
# per key, and it already asserts at preflight that every env key either maps to
# a Settings field or appears there. Keeping a second copy here is precisely the
# hand-maintained-list failure CR175 F3 is about — the two would drift, and the
# drift would surface as a permanent false positive that trains the operator to
# ignore this check.
_LOCAL_ONLY: dict[str, str] = {
    "GIT_SHA": "build arg (CR175 F2), not a runtime env var",
    "ALPHA_TAG": "build arg (CR175 F2), not a runtime env var",
    "POSTGRES_USER": "compose-level: postgres service credential",
    "POSTGRES_DB": "compose-level: postgres service credential",
}


def _keys_without_settings() -> dict[str, str]:
    import importlib.util

    path = (_REPO_ROOT / "backend" / "tests" / "unit"
            / "test_config_compose_parity.py")
    spec = importlib.util.spec_from_file_location("_parity", path)
    if spec is None or spec.loader is None:
        raise CannotRun(f"cannot import the excuse table from {path}")
    mod = importlib.util.module_from_spec(spec)
    # That module imports `app.core.config`, so `backend/` has to be importable.
    # This script runs under the system python (no backend venv), which is fine:
    # pydantic-settings is the only thing `config.py` needs and the import is
    # for a dict literal, not for running anything.
    backend = str(_REPO_ROOT / "backend")
    added = backend not in sys.path
    if added:
        sys.path.insert(0, backend)
    try:
        spec.loader.exec_module(mod)
    except ImportError as exc:
        raise CannotRun(
            f"cannot import the excuse table ({exc}). Run with the backend "
            f"venv: {_REPO_ROOT}/backend/.venv/bin/python "
            "scripts/promotion/postflight.py …"
        ) from exc
    finally:
        if added:
            sys.path.remove(backend)
    return {**mod._ENV_KEYS_WITHOUT_SETTINGS, **_LOCAL_ONLY}


_ENV_LINE = re.compile(r"^([A-Z][A-Z0-9_]*)=(.*)$")

# A `bool` Settings field set to a falsey literal is a deliberate off-switch, not
# a missing compose line. `SUPPRESS_ANALYST_CONSENSUS=false` is populated in the
# env file and correctly reports `configured: false` from the container, because
# for a bool `configured` means "the feature is on", not "the key is present".
#
# This cost a false positive on the very first live postflight run. Left in, the
# check would have failed on a non-problem every single promotion — which is
# exactly the F5 pathology (a check whose failing state is its normal state) that
# this tool exists to remove, reproduced by the tool itself.
_FALSEY_LITERALS = {"false", "0", "no", "off"}


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
        if not value or value.lower() in _FALSEY_LITERALS:
            continue
        out[key] = "<set>"
    return out


def _admin_secret(env_path: Path) -> str:
    # DEF381 — a missing file is COULD-NOT-RUN, not a failed promotion. This
    # read was unguarded, so promoting from a checkout without a local
    # `infra/alpha.env` ended in an unhandled FileNotFoundError and exit 1 —
    # the exact conflation this script's own docstring says must never happen,
    # committed by the script itself.
    try:
        lines = env_path.read_text().splitlines()
    except OSError as exc:
        raise CannotRun(
            f"cannot read {env_path} ({exc.strerror}) — so the config check did "
            f"not run. That is not a passing promotion and not a failing one."
        ) from exc
    for raw in lines:
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


def _is_dir_mtime_only(line: str) -> bool:
    """Is this itemized line a directory whose ONLY delta is its mtime?

    DEF280 — this check used to count one as drift, so it failed on a promotion
    that had landed perfectly, and it failed only on the *second* run. The
    api-alpha container writes `__pycache__` into the source tree it
    bind-mounts; `__pycache__` is (correctly) excluded above, so the
    *containing directory's* mtime diverges the moment the new container starts
    executing Python. `backend/app/`, `backend/app/core/` and
    `backend/tests/unit/` came back as `.d..t....` — no content flag set — on a
    deploy where re-running the same rsync with directory entries filtered
    returned nothing at all.

    A check guaranteed to start failing a minute after every successful
    promotion is the exact failure CR175 was written to eliminate, reproduced
    by CR175's own code, and it is self-defeating in the one case it exists
    for: a real partial rsync would arrive inside noise the operator had been
    trained to skip.

    Deliberately narrow. rsync's itemize flags are `YXcstpoguax`: position 0 is
    the update type, 1 the file type, and 2 onward the attribute deltas. Only
    `.d` with nothing but `t` set qualifies — a *created* directory is `cd+++++++++`
    and stays drift, `*deleting` stays drift, and a directory whose permissions
    or ownership moved stays drift. The claim being made is only the one the
    evidence supports: a directory whose sole difference is a timestamp is not
    a difference in what the box is running.
    """
    flags = line.split(" ", 1)[0]
    if len(flags) < 3 or flags[0] != "." or flags[1] != "d":
        return False
    return set(flags[2:]) <= {".", "t"}


def split_drift(stdout: str) -> tuple[list[str], int]:
    """Real drift, and how many directory-mtime lines were set aside.

    The count is returned rather than dropped so the failure path can say what
    it ignored — silently discarding lines is how a filter this cheap turns
    into the next "the check said nothing was wrong".
    """
    lines = [ln for ln in stdout.splitlines() if ln.strip()]
    drift = [ln for ln in lines if not _is_dir_mtime_only(ln)]
    return drift, len(lines) - len(drift)


def check_tree(host: str, remote: str, timeout: int) -> list[str]:
    """Does the box hold what the Mac holds? — the check the stamp cannot make.

    `docker-compose.yml` bind-mounts `./backend/app`, `./backend/scripts`,
    `./backend/tests` and `./content` read-only over the image. **The running
    Python is the rsync'd host filesystem, not the image contents.** So
    `GIT_SHA` — baked at build time — describes the image, and the image's
    `app/` is shadowed by the mount. The stamp answers "which commit was this
    image built from", never "which bytes is uvicorn importing".

    An rsync dry-run answers the second question directly: an itemized line
    naming a *content* difference means the box differs from the Mac, and after
    a successful promotion there should be none. This is also the only check
    that would catch a partial rsync, which is precisely the failure the stamp
    would report as fine.

    Directory-mtime-only lines are not content differences and are set aside by
    [split_drift] — see [_is_dir_mtime_only] for why that is a correction and
    not a loosening (DEF280).

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
        # DEF381 — the canonical Alpha credentials. `.env` above does NOT match
        # this: rsync's pattern is a filename, and the file that actually holds
        # the secrets is `infra/alpha.env`. Step 4 scps it to `~/ami_trade/.env`,
        # which is the ONE mechanism for moving env values; a second copy on the
        # box under `infra/` is credentials at rest that nothing reads. Excluded
        # here as well as in step 3 so the tree check does not then report its
        # correct absence as drift — which is how this was found.
        "infra/alpha.env",
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

    drift, dir_mtime_only = split_drift(proc.stdout)
    if not drift:
        return []
    problems = [
        f"{len(drift)} path(s) differ between this worktree and "
        f"{host}:{remote} — the box is not running what this worktree holds.",
        "  Run immediately after the rsync, this means the promotion did not "
        "land cleanly.",
        "  Run later on a shared checkout, it may just be another lane's "
        "commits arriving after you promoted — compare against "
        "`git diff --stat <your-alpha-tag>..HEAD` before treating it as a "
        "promotion failure.",
    ]
    problems += [f"  {ln}" for ln in drift[:15]]
    if len(drift) > 15:
        problems.append(f"  … and {len(drift) - 15} more")
    if dir_mtime_only:
        problems.append(
            f"  ({dir_mtime_only} directory-mtime-only line(s) ignored — "
            "DEF280, the container's __pycache__ writes)")
    return problems


def check_suite_verdict(path: Path, expect_sha: str, *, now: float | None = None,
                        max_age_h: float = _SUITE_VERDICT_MAX_AGE_H) -> list[str]:
    """DEF405 — was the suite gate green, on THIS commit, for the WHOLE suite?

    `preflight_suite.sh` ends in an exit code, and on 2026-09-11 that exit code
    was consumed by the `| tail` of a background task: the operator read
    "completed (exit code 0)" and promoted alpha-2026-09-11-1 on a suite that
    had printed `VERDICT: FAIL` — the third DEF326-shaped instance. The gate
    therefore also writes its verdict to a file, stamped with the commit it
    measured, and this check reads it after the deploy. A wrapper can swallow
    an exit code; it cannot swallow a record. Failing, not COULD NOT RUN, on a
    missing file: "the gate never ran" is a failed promotion, not an unknown.
    """
    import datetime as _dt
    import time as _time

    if not path.exists():
        return [f"no suite verdict at {path} — preflight_suite.sh did not run "
                "before this promotion (or ran from another checkout). The suite "
                "gate is step 1; a promotion without it is a promotion on nothing."]
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"suite verdict at {path} is unreadable ({exc}) — treat as no gate"]
    problems: list[str] = []
    verdict = str(rec.get("verdict", ""))
    if verdict != "PASS":
        problems.append(
            f"the suite gate recorded {verdict or 'nothing'} (passed={rec.get('passed')} "
            f"failed={rec.get('failed')} errors={rec.get('errors')}) and this promotion "
            "went ahead anyway — DEF326/DEF405: the exit code was not read")
    sha = str(rec.get("sha", ""))
    if not expect_sha or not sha or not (sha.startswith(expect_sha) or expect_sha.startswith(sha)):
        problems.append(f"the suite gate ran on {sha[:12] or '?'} but {expect_sha[:12]} was "
                        "promoted — the tested tree is not the shipped tree")
    target = str(rec.get("target", ""))
    if target.rstrip("/") != _FULL_SUITE_TARGET.rstrip("/"):
        problems.append(f"the suite gate ran on {target!r}, not the whole unit suite "
                        f"({_FULL_SUITE_TARGET}) — a partial run is not the gate")
    try:
        at = _dt.datetime.fromisoformat(str(rec.get("at", "")).replace("Z", "+00:00"))
        age_h = ((now if now is not None else _time.time()) - at.timestamp()) / 3600
    except ValueError:
        age_h = float("inf")
    if age_h > max_age_h:
        problems.append(f"the suite verdict is {age_h:.1f}h old (limit {max_age_h}h) — "
                        "re-run preflight_suite.sh; a stale pass covers a different tree")
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

    Deliberately narrow. *"Is this key a `Settings` field at all"* is already
    answered statically at preflight by
    `test_config_compose_parity.py::test_every_env_file_key_maps_to_a_settings_field_or_is_declared_non_app`,
    which is where that direction belongs — a static fact does not need a live
    container to check it. Re-asserting it here would only produce a second
    verdict on the same question, and the two would eventually disagree. So an
    unrecognised key is reported as a **note**, not a failure, naming the test
    that owns it.
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

    excused = _keys_without_settings()
    problems: list[str] = []
    unrecognised: list[str] = []
    for key in sorted(_populated_keys(env_path)):
        if key in excused:
            continue
        if key not in container:
            unrecognised.append(key)
        elif not container[key]:
            problems.append(
                f"{key}: populated in infra/alpha.env, configured=false in the "
                f"container — add `{key}: ${{{key}}}` to docker-compose.yml's "
                "api-alpha environment block (this is the DEF038/DEF063 bug)"
            )
    if unrecognised:
        print(f"      note: {len(unrecognised)} env key(s) neither map to a "
              f"Settings field nor are excused — {', '.join(unrecognised)}. "
              "test_config_compose_parity.py owns that direction and runs at "
              "preflight, so it is not re-failed here.")
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
    ap.add_argument("--suite-verdict", default=str(_SUITE_VERDICT),
                    help="the record preflight_suite.sh writes (DEF405)")
    args = ap.parse_args()

    env_path = Path(args.env_file)
    try:
        secret = _admin_secret(env_path)
    except CannotRun as exc:
        print(f"CANNOT RUN — {exc}", file=sys.stderr)
        return 2

    checks = [
        # First, and local: it answers "should this promotion have happened",
        # which the four live checks cannot.
        ("suite", lambda: check_suite_verdict(Path(args.suite_verdict), args.expect_sha)),
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
        except Exception as exc:
            # An unhandled exception in one check must not take the other four
            # down with it — this script crashed on exactly that during its own
            # first live run, which would have left three checks unreported
            # behind a traceback. Reported as COULD NOT RUN (exit 2), never
            # swallowed into a pass.
            print(f"  [?] {name:10s} COULD NOT RUN — unhandled "
                  f"{type(exc).__name__}: {exc}")
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
