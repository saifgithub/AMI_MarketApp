"""CR267 WP-44 — `infra/backups/pg-backup.sh`, `retention_select.py`, `pg-restore-drill.sh`.

The scripts run for real; only the outside world is replaced, by PATH shims in a
temp dir: `pg_dump` (emits incompressible text), `rclone` (a directory stands in
for the bucket), `curl` (records the failure-alert POST), `docker` (restore drill
only). gpg is the real one with a throwaway GNUPGHOME, so "encrypted" and "the
passphrase decrypts it" are proven, not assumed.

What is guarded: the script refuses on missing/partial config; a failure at ANY
step exits non-zero with a FAIL line and an alert; a plaintext dump never reaches
disk when an upload is configured; nothing is left half-written; secrets never
appear on a command line; remote retention deletes the right names.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[3]
_BACKUPS = _REPO / "infra" / "backups"
_SCRIPT = _BACKUPS / "pg-backup.sh"
_DRILL = _BACKUPS / "pg-restore-drill.sh"

_PASS = "correct horse battery staple 0000"
_SECRET_KEY = "SECRETKEY-do-not-leak-0123456789"

pytestmark = pytest.mark.skipif(
    shutil.which("gpg") is None or shutil.which("gunzip") is None or shutil.which("bash") is None,
    reason="needs gpg, gunzip and bash",
)

_PG_DUMP = """#!/usr/bin/env bash
[[ -n "${FAKE_PG_FAIL:-}" ]] && { echo "pg_dump: connection refused" >&2; exit 1; }
echo "-- fake dump"
head -c 40000 /dev/urandom | base64
"""

_RCLONE = """#!/usr/bin/env bash
echo "rclone $*" >> "$SHIM_LOG"
cmd="$1"; shift
name_of() { basename "${1#*:s3:}"; }
case "$cmd" in
  copyto)
    src="$1"; dst="$2"
    if [[ "$dst" == :s3:* ]]; then
      [[ -n "${RCLONE_FAIL_COPY:-}" ]] && { echo "rclone: boom" >&2; exit 1; }
      cp "$src" "$FAKE_BUCKET/$(name_of "$dst")"
      [[ -n "${RCLONE_TRUNCATE:-}" ]] && head -c 10 "$src" > "$FAKE_BUCKET/$(name_of "$dst")"
    else
      cp "$FAKE_BUCKET/$(name_of "$src")" "$dst"
    fi ;;
  lsf)
    if [[ "$1" == "--format" ]]; then
      f="$FAKE_BUCKET/$(name_of "$3")"; [[ -f "$f" ]] && { stat -c %s "$f" 2>/dev/null || stat -f %z "$f"; }
    else
      ls -1 "$FAKE_BUCKET"
    fi ;;
  deletefile) rm -f "$FAKE_BUCKET/$(name_of "$1")" ;;
esac
exit 0
"""

_CURL = """#!/usr/bin/env bash
echo "curl $*" >> "$SHIM_LOG"
exit 0
"""


@pytest.fixture
def env(tmp_path):
    shims = tmp_path / "shims"
    shims.mkdir()
    for name, body in (("pg_dump", _PG_DUMP), ("rclone", _RCLONE), ("curl", _CURL)):
        p = shims / name
        p.write_text(body)
        p.chmod(p.stat().st_mode | stat.S_IEXEC)
    bucket = tmp_path / "bucket"
    bucket.mkdir()
    # gpg-agent's socket path must be short (<104 bytes on macOS), so GNUPGHOME
    # cannot live under pytest's long tmp_path.
    gnupg = Path(tempfile.mkdtemp(prefix="g", dir="/tmp"))
    backups = tmp_path / "backups"
    e = {
        "PATH": f"{shims}:{os.environ['PATH']}",
        "HOME": str(tmp_path),
        "GNUPGHOME": str(gnupg),
        "PGPASSWORD": "pw",
        "BACKUP_DIR": str(backups),
        "FAKE_BUCKET": str(bucket),
        "SHIM_LOG": str(tmp_path / "shim.log"),
    }
    yield e, backups, bucket, tmp_path
    subprocess.run(["gpgconf", "--kill", "gpg-agent"], env=e, capture_output=True)
    shutil.rmtree(gnupg, ignore_errors=True)


def _s3(e: dict) -> dict:
    return {
        **e,
        "BACKUP_S3_ENDPOINT": "https://acct.r2.cloudflarestorage.com",
        "BACKUP_S3_BUCKET": "ami-beta-backups",
        "BACKUP_S3_ACCESS_KEY_ID": "AKIDEXAMPLE",
        "BACKUP_S3_SECRET_ACCESS_KEY": _SECRET_KEY,
        "BACKUP_ENCRYPTION_PASSPHRASE": _PASS,
    }


def _run(script: Path, e: dict, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(script), *args], env=e, capture_output=True, text=True, timeout=120, cwd=_REPO
    )


def _files(d: Path) -> list[str]:
    return sorted(p.name for p in d.iterdir()) if d.exists() else []


def _log(tmp: Path) -> str:
    p = tmp / "shim.log"
    return p.read_text() if p.exists() else ""


def test_scripts_parse():
    for s in (_SCRIPT, _DRILL):
        assert subprocess.run(["bash", "-n", str(s)]).returncode == 0


# ── refusals: nothing is written ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "mutate, needle",
    [
        (lambda e: e.pop("PGPASSWORD"), "PGPASSWORD unset"),
        (lambda e: None, "BACKUP_ENCRYPTION_PASSPHRASE unset"),
        (lambda e: e.update(BACKUP_S3_BUCKET="b", BACKUP_ENCRYPTION_PASSPHRASE=_PASS), "partly set"),
        (lambda e: e.update(BACKUP_REQUIRE_OFFSITE="1", BACKUP_ENCRYPTION_PASSPHRASE=_PASS), "never leaves the server"),
        (lambda e: e.update(BACKUP_ENCRYPTION_PASSPHRASE_FILE="/nonexistent"), "PASSPHRASE_FILE"),
    ],
)
def test_refuses_without_required_config(env, mutate, needle):
    e, backups, bucket, tmp = env
    mutate(e)
    r = _run(_SCRIPT, e)
    assert r.returncode != 0
    assert needle in r.stderr
    assert "FAIL" in r.stderr
    assert [n for n in _files(backups) if n.startswith("ami_trade-")] == []
    assert _files(bucket) == []


def test_upload_never_accepts_a_plaintext_opt_out(env):
    e, backups, bucket, _ = env
    e = _s3(e)
    e["BACKUP_ENCRYPTION_PASSPHRASE"] = ""
    e["BACKUP_ALLOW_PLAINTEXT"] = "1"
    r = _run(_SCRIPT, e)
    assert r.returncode != 0 and "needs encryption" in r.stderr
    assert _files(bucket) == []
    assert [n for n in _files(backups) if n.endswith(".sql.gz")] == []


# ── happy path ───────────────────────────────────────────────────────────────


def test_encrypted_dump_is_uploaded_and_leaves_no_plaintext(env):
    e, backups, bucket, tmp = env
    r = _run(_SCRIPT, _s3(e))
    assert r.returncode == 0, r.stderr
    local = [n for n in _files(backups) if n.startswith("ami_trade-2")]
    assert len(local) == 1 and local[0].endswith(".sql.gz.gpg")
    assert not [n for n in _files(backups) if n.endswith(".tmp") or n.endswith(".sql.gz") or n.endswith(".sql")]
    assert _files(bucket) == local
    assert (bucket / local[0]).read_bytes() == (backups / local[0]).read_bytes()
    assert b"-- fake dump" not in (bucket / local[0]).read_bytes()
    assert "upload verified" in r.stdout

    # the passphrase really decrypts it, and it really is a gzipped dump
    dec = subprocess.run(
        f'gpg --batch --quiet --pinentry-mode loopback --decrypt --passphrase "{_PASS}" "{bucket / local[0]}" | gunzip -c',
        shell=True, env=e, capture_output=True, text=True,
    )
    assert dec.returncode == 0, dec.stderr
    assert dec.stdout.startswith("-- fake dump")

    # secrets are env-only: never on a command line (the shim log records argv)
    assert _SECRET_KEY not in _log(tmp) and _PASS not in _log(tmp)
    assert _SECRET_KEY not in r.stdout + r.stderr


def test_passphrase_file_is_honoured(env):
    e, backups, _, tmp = env
    e = _s3(e)
    e["BACKUP_ENCRYPTION_PASSPHRASE"] = ""
    pf = tmp / "pass"
    pf.write_text(_PASS + "\n")
    e["BACKUP_ENCRYPTION_PASSPHRASE_FILE"] = str(pf)
    assert _run(_SCRIPT, e).returncode == 0


def test_local_only_plaintext_opt_out_still_works_without_upload(env):
    e, backups, _, _ = env
    e["BACKUP_ALLOW_PLAINTEXT"] = "1"
    r = _run(_SCRIPT, e)
    assert r.returncode == 0 and "PLAINTEXT" in r.stderr


# ── failures are loud and clean ──────────────────────────────────────────────


def _assert_failed_clean(r, backups, tmp, *, alert=True):
    assert r.returncode != 0
    assert "FAIL" in r.stderr
    assert not [n for n in _files(backups) if n.endswith(".tmp")]
    if alert:
        assert "curl" in _log(tmp) and "hooks.example.test" in _log(tmp)


def test_pg_dump_failure_fails_and_alerts_and_leaves_nothing(env):
    e, backups, bucket, tmp = env
    e = _s3(e)
    e.update(FAKE_PG_FAIL="1", BACKUP_ALERT_WEBHOOK_URL="https://hooks.example.test/x")
    r = _run(_SCRIPT, e)
    _assert_failed_clean(r, backups, tmp)
    assert [n for n in _files(backups) if n.startswith("ami_trade-2")] == []
    assert _files(bucket) == []


def test_upload_failure_is_fatal_and_alerts(env):
    e, backups, bucket, tmp = env
    e = _s3(e)
    e.update(RCLONE_FAIL_COPY="1", BACKUP_ALERT_WEBHOOK_URL="https://hooks.example.test/x")
    r = _run(_SCRIPT, e)
    _assert_failed_clean(r, backups, tmp)
    assert "upload failed" in r.stderr
    assert _files(bucket) == []


def test_size_mismatch_after_upload_is_fatal(env):
    e, backups, _, tmp = env
    e = _s3(e)
    e.update(RCLONE_TRUNCATE="1", BACKUP_ALERT_WEBHOOK_URL="https://hooks.example.test/x")
    r = _run(_SCRIPT, e)
    _assert_failed_clean(r, backups, tmp)
    assert "uploaded size" in r.stderr


def test_remote_retention_prunes_only_what_the_rule_says(env):
    e, backups, bucket, _ = env
    # 30 consecutive past days, plus a foreign object that must never be touched
    from datetime import datetime, timedelta, timezone

    base = datetime(2026, 9, 1, 2, 30, tzinfo=timezone.utc)
    for i in range(30):
        (bucket / f"ami_trade-{(base + timedelta(days=i)):%Y%m%dT%H%M%SZ}.sql.gz.gpg").write_bytes(b"x")
    (bucket / "notes.txt").write_text("keep me")
    r = _run(_SCRIPT, {**_s3(e), "BACKUP_KEEP_DAILY": "5", "BACKUP_KEEP_WEEKLY": "2"})
    assert r.returncode == 0, r.stderr
    left = sorted(p.name for p in bucket.iterdir())
    assert "notes.txt" in left
    backups_left = [n for n in left if n.startswith("ami_trade-")]
    assert len(backups_left) == 5 + 2  # 5 daily (incl. today's) + 2 weekly
    assert "remote prune" in r.stdout


# ── retention rule, pure ─────────────────────────────────────────────────────


def _load_retention():
    spec = importlib.util.spec_from_file_location("retention_select", _BACKUPS / "retention_select.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_retention_keeps_newest_daily_then_one_per_week():
    from datetime import datetime, timedelta

    mod = _load_retention()
    start = datetime(2026, 10, 1)
    names = [f"ami_trade-{(start + timedelta(days=i)):%Y%m%d}T023000Z.sql.gz.gpg" for i in range(100)]
    deleted = set(mod.select_deletions(names, daily=14, weekly=8))
    kept = [n for n in names if n not in deleted]
    assert len(kept) == 14 + 8
    assert set(sorted(names)[-14:]) <= set(kept)
    weeks = {datetime.strptime(n[10:18], "%Y%m%d").isocalendar()[:2] for n in kept[:-14]}
    assert len(weeks) == 8  # one per ISO week


def test_retention_ignores_foreign_names_and_short_lists():
    mod = _load_retention()
    assert mod.select_deletions(["README", "ami_trade-latest.sql.gz.gpg", "x.sql"], 1, 0) == []
    few = [f"ami_trade-202610{d:02d}T000000Z.sql.gz.gpg" for d in range(1, 4)]
    assert mod.select_deletions(few, 14, 8) == []


# ── restore drill refusals (docker is shimmed to prove no container starts) ─


def test_drill_refuses_without_passphrase_or_source(env):
    e, _, _, tmp = env
    docker = tmp / "shims" / "docker"
    docker.write_text('#!/usr/bin/env bash\necho "docker $*" >> "$SHIM_LOG"\nexit 0\n')
    docker.chmod(docker.stat().st_mode | stat.S_IEXEC)
    r = _run(_DRILL, e)
    assert r.returncode != 0 and "cannot decrypt" in r.stderr
    r = _run(_DRILL, {**e, "BACKUP_ENCRYPTION_PASSPHRASE": _PASS})
    assert r.returncode != 0 and "BACKUP_S3_* incomplete" in r.stderr
    assert "docker run" not in _log(tmp)


# ── restore drill end to end, against a docker shim ─────────────────────────

_DOCKER = """#!/usr/bin/env bash
echo "docker $*" >> "$SHIM_LOG"
case "$1" in
  run|rm) exit 0 ;;
esac
# docker exec [-i] <container> <cmd> ...
shift; [[ "$1" == "-i" ]] && shift; shift
cmd="$1"; shift
case "$cmd" in
  pg_isready) exit 0 ;;
  psql)
    sql=""; while (( $# )); do [[ "$1" == "-c" ]] && sql="$2"; shift; done
    if [[ -z "$sql" ]]; then cat > "$SHIM_RESTORED"; exit "${FAKE_PSQL_RC:-0}"; fi
    case "$sql" in
      *pg_tables*) printf 'alembic_version\\nusers\\nmandates\\n'; for i in $(seq 1 ${FAKE_TABLES:-25}); do echo "t$i"; done ;;
      *alembic_version\\ limit*) echo "cr278a0b0c0d1" ;;
      *public.users*) echo 7 ;;
      *count*) echo "${FAKE_ROWS:-3}" ;;
    esac ;;
esac
exit 0
"""


def _drill_env(env):
    e, backups, bucket, tmp = env
    docker = tmp / "shims" / "docker"
    docker.write_text(_DOCKER)
    docker.chmod(docker.stat().st_mode | stat.S_IEXEC)
    e = {**e, "SHIM_RESTORED": str(tmp / "restored.sql")}
    # a real encrypted backup, made by the real backup script
    assert _run(_SCRIPT, _s3(e)).returncode == 0
    backup = next(p for p in backups.iterdir() if p.name.startswith("ami_trade-2"))
    return {**e, "BACKUP_ENCRYPTION_PASSPHRASE": _PASS}, backup, tmp


def test_drill_restores_a_real_backup_and_prints_timings(env):
    e, backup, tmp = _drill_env(env)
    r = _run(_DRILL, e, "--file", str(backup))
    assert r.returncode == 0, r.stderr
    assert "RESTORE DRILL PASSED" in r.stdout
    for phase in ("download=", "start_postgres=", "decrypt_and_restore=", "sanity_checks=", "total="):
        assert phase in r.stdout
    assert "alembic_version: cr278a0b0c0d1" in r.stdout
    assert (tmp / "restored.sql").read_text().startswith("-- fake dump")  # decrypted + gunzipped
    assert "docker rm -f ami_restore_drill_" in _log(tmp)  # throwaway removed


def test_drill_fails_on_wrong_passphrase(env):
    e, backup, tmp = _drill_env(env)
    r = _run(_DRILL, {**e, "BACKUP_ENCRYPTION_PASSPHRASE": "wrong"}, "--file", str(backup))
    assert r.returncode != 0 and "decrypt failed" in r.stderr
    assert "docker rm -f ami_restore_drill_" in _log(tmp)


def test_drill_fails_on_sql_errors(env):
    e, backup, _ = _drill_env(env)
    r = _run(_DRILL, {**e, "FAKE_PSQL_RC": "3"}, "--file", str(backup))
    assert r.returncode != 0 and "SQL errors" in r.stderr


def test_drill_fails_when_too_few_tables_restored(env):
    e, backup, _ = _drill_env(env)
    r = _run(_DRILL, {**e, "FAKE_TABLES": "2"}, "--file", str(backup))
    assert r.returncode != 0 and "public tables restored" in r.stderr


def test_drill_downloads_the_newest_object_from_the_bucket(env):
    e, backup, tmp = _drill_env(env)
    bucket = Path(e["FAKE_BUCKET"])
    (bucket / "ami_trade-20200101T000000Z.sql.gz.gpg").write_bytes(b"old")
    r = _run(_DRILL, _s3(e) | {"BACKUP_ENCRYPTION_PASSPHRASE": _PASS})
    assert r.returncode == 0, r.stderr
    assert f"newest backup: {backup.name}" in r.stdout
