"""CR267 WP-43 — the promotion scripts are parameterised by target, and Alpha did not move.

`scripts/promotion/postflight.py` hard-coded melehost, `~/ami_trade/`, the Alpha
hostname and `infra/alpha.env`. Beta is a second box running the same stack, so
those became fields of a `TARGETS` table. The two failure modes that matter and
that these tests pin:

1. **Alpha drifted.** `alpha` must carry exactly the old literals, because every
   existing Alpha promotion runs without `--target`.
2. **A typo ran against the wrong box.** An unknown target must refuse, never
   fall back to Alpha and report a green that describes the wrong environment.

Lives in `backend/tests/unit/` for the reason `test_cr175_postflight.py` does:
this is the suite the promotion itself runs.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _ROOT / "scripts" / "promotion" / "postflight.py"
_CMDS = _ROOT / ".claude" / "commands"


def _load():
    spec = importlib.util.spec_from_file_location("postflight_wp43", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pf = _load()


# ── the table ─────────────────────────────────────────────────────────────────

def test_alpha_target_is_exactly_the_old_hardcoded_values() -> None:
    a = pf.resolve_target("alpha")
    assert a["host"] == "melehost"
    assert a["remote"] == "~/ami_trade/"
    assert a["base"] == "https://api-alpha.agenticmarketintel.ai"
    assert a["env_file"] == "infra/alpha.env"
    assert a["tag_prefix"] == "alpha"
    assert a["container"] == "ami_api_alpha"
    assert a["service"] == "api-alpha"
    assert a["promote_cmd"] == "/promote-to-alpha"
    assert a["rollback_cmd"] == "/rollback-alpha"
    assert pf.DEFAULT_TARGET == "alpha"


def test_beta_target_resolves_to_the_vps_values() -> None:
    b = pf.resolve_target("beta")
    assert b["host"] == "ami-beta"
    assert b["remote"] == "~/ami_trade/"
    assert b["base"] == "https://api-beta.agenticmarketintel.ai"
    assert b["env_file"] == "infra/beta.env"
    assert b["tag_prefix"] == "beta"
    # one docker-compose.yml: the service and container names are Alpha's
    assert b["container"] == "ami_api_alpha"
    assert b["service"] == "api-alpha"
    assert b["promote_cmd"] == "/promote-to-beta"
    assert b["rollback_cmd"] == "/rollback-beta"


def test_the_two_targets_share_no_host_url_or_env_file() -> None:
    a, b = pf.resolve_target("alpha"), pf.resolve_target("beta")
    for key in ("host", "base", "env_file", "tag_prefix"):
        assert a[key] != b[key], f"{key} is shared between Alpha and Beta"


@pytest.mark.parametrize("name", ["", "gamma", "prod", "Alpha", "melehost"])
def test_unknown_target_is_refused_not_defaulted(name: str) -> None:
    with pytest.raises(ValueError, match="unknown promotion target"):
        pf.resolve_target(name)


def test_cli_refuses_an_unknown_target(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["postflight.py", "--expect-sha", "abc", "--target", "gamma"])
    with pytest.raises(SystemExit) as exc:
        pf.main()
    assert exc.value.code == 2


# ── main() wiring: defaults come from the target ──────────────────────────────

def _stub_checks(monkeypatch: pytest.MonkeyPatch) -> dict:
    seen: dict = {}
    monkeypatch.setattr(pf, "_admin_secret", lambda p, label="infra/alpha.env": "s3cret")
    monkeypatch.setattr(pf, "check_suite_verdict", lambda *a, **k: seen.setdefault("suite", []) or [])
    monkeypatch.setattr(pf, "check_local_gate_verdict", lambda *a, **k: seen.setdefault("local_gate", []) or [])
    monkeypatch.setattr(pf, "check_migration_heads", lambda *a, **k: seen.update(mig=a) or [])
    monkeypatch.setattr(pf, "check_identity", lambda *a, **k: seen.update(identity=a) or [])
    monkeypatch.setattr(pf, "check_tree", lambda *a, **k: seen.update(tree=a) or [])
    monkeypatch.setattr(pf, "check_readiness", lambda *a, **k: seen.update(ready=a) or [])
    monkeypatch.setattr(pf, "check_config_parity", lambda *a, **k: seen.update(config=a) or [])
    monkeypatch.setattr(pf, "check_market_data", lambda *a, **k: seen.update(market=a) or [])
    return seen


def test_no_target_flag_means_alpha_and_uses_the_old_values(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    seen = _stub_checks(monkeypatch)
    rec = tmp_path / "records"
    monkeypatch.setattr("sys.argv", ["postflight.py", "--expect-sha", "abc123",
                                     "--record-dir", str(rec)])
    assert pf.main() == 0
    assert seen["tree"][:2] == ("melehost", "~/ami_trade/")
    assert seen["ready"][0] == "https://api-alpha.agenticmarketintel.ai"
    assert seen["identity"][5] == "/promote-to-alpha"
    assert "suite" in seen and "local_gate" in seen, "Alpha must still run both local gates"
    assert not rec.exists(), "no --expect-tag, so no record is written"


def test_beta_uses_beta_values_and_swaps_the_local_gates_for_the_record(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    seen = _stub_checks(monkeypatch)
    pf.write_record(tmp_path, tag="alpha-2026-11-30-2", sha="abc123", target="alpha")
    wt = tmp_path / "tree"
    monkeypatch.setattr("sys.argv", [
        "postflight.py", "--target", "beta", "--expect-sha", "abc123",
        "--expect-tag", "beta-2026-12-01-1", "--source-alpha-tag", "alpha-2026-11-30-2",
        "--record-dir", str(tmp_path), "--root", str(wt)])
    assert pf.main() == 0
    assert seen["tree"][:2] == ("ami-beta", "~/ami_trade/")
    assert seen["tree"][3] == wt, "the tree check must compare the shipped temp worktree"
    assert pf._active_root == wt, "the migration-head check must read the shipped tree"
    assert seen["ready"][0] == "https://api-beta.agenticmarketintel.ai"
    assert seen["config"][4] == "infra/beta.env"
    assert seen["identity"][5] == "/promote-to-beta"
    assert "suite" not in seen and "local_gate" not in seen
    # a passing Beta run leaves its own record, for /rollback-beta
    rec = json.loads((tmp_path / "beta-2026-12-01-1.json").read_text())
    assert rec["target"] == "beta" and rec["verdict"] == "PASS" and rec["sha"] == "abc123"


def test_beta_without_a_source_alpha_tag_cannot_run(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    _stub_checks(monkeypatch)
    monkeypatch.setattr("sys.argv", ["postflight.py", "--target", "beta", "--expect-sha", "abc"])
    assert pf.main() == 2
    assert "--source-alpha-tag" in capsys.readouterr().err


def test_a_failed_alpha_run_writes_no_record(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _stub_checks(monkeypatch)
    monkeypatch.setattr(pf, "check_market_data", lambda *a, **k: ["mock_walk"])
    rec = tmp_path / "records"
    monkeypatch.setattr("sys.argv", ["postflight.py", "--expect-sha", "abc",
                                     "--expect-tag", "alpha-2026-11-30-2",
                                     "--record-dir", str(rec)])
    assert pf.main() == 1
    assert not rec.exists()


# ── the Alpha record gate ─────────────────────────────────────────────────────

def test_record_gate_passes_for_a_recorded_alpha_tag(tmp_path: Path) -> None:
    pf.write_record(tmp_path, tag="alpha-2026-11-30-2", sha="abcdef1234", target="alpha")
    assert pf.check_alpha_record(tmp_path, "alpha-2026-11-30-2", "abcdef1234") == []
    # short sha on one side is fine (the identity check does the same)
    assert pf.check_alpha_record(tmp_path, "alpha-2026-11-30-2", "abcdef1234567890") == []


def test_record_gate_fails_loudly_when_there_is_no_record(tmp_path: Path) -> None:
    problems = pf.check_alpha_record(tmp_path, "alpha-2026-11-30-2", "abc")
    assert len(problems) == 1 and "no postflight record" in problems[0]


def test_record_gate_fails_when_the_shipped_commit_is_not_the_verified_one(tmp_path: Path) -> None:
    pf.write_record(tmp_path, tag="alpha-2026-11-30-2", sha="aaaaaaa", target="alpha")
    problems = pf.check_alpha_record(tmp_path, "alpha-2026-11-30-2", "bbbbbbb")
    assert any("not the tree Alpha verified" in p for p in problems)


def test_record_gate_refuses_a_beta_record_or_non_pass(tmp_path: Path) -> None:
    (tmp_path / "alpha-2026-11-30-2.json").write_text(json.dumps(
        {"tag": "alpha-2026-11-30-2", "sha": "abc", "target": "beta", "verdict": "PASS"}))
    assert pf.check_alpha_record(tmp_path, "alpha-2026-11-30-2", "abc")
    (tmp_path / "alpha-2026-11-30-3.json").write_text(json.dumps(
        {"tag": "alpha-2026-11-30-3", "sha": "abc", "target": "alpha", "verdict": "FAIL"}))
    assert pf.check_alpha_record(tmp_path, "alpha-2026-11-30-3", "abc")


@pytest.mark.parametrize("tag", ["beta-2026-11-30-1", "alpha-2026-11-30", "HEAD", "../x", "alpha-2026-11-30-1/../../etc"])
def test_record_gate_refuses_anything_that_is_not_an_alpha_tag(tmp_path: Path, tag: str) -> None:
    problems = pf.check_alpha_record(tmp_path, tag, "abc")
    assert problems and "not a alpha-YYYY-MM-DD-N tag" in problems[0]


def test_record_gate_unreadable_record_is_a_failure_not_a_pass(tmp_path: Path) -> None:
    (tmp_path / "alpha-2026-11-30-2.json").write_text("{not json")
    assert pf.check_alpha_record(tmp_path, "alpha-2026-11-30-2", "abc")


def test_pre_gate_is_beta_only_and_exits_zero_or_one(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    base = ["postflight.py", "--expect-sha", "abc", "--record-dir", str(tmp_path),
            "--source-alpha-tag", "alpha-2026-11-30-2"]
    monkeypatch.setattr("sys.argv", base + ["--target", "beta", "--pre-gate"])
    assert pf.main() == 1
    pf.write_record(tmp_path, tag="alpha-2026-11-30-2", sha="abc", target="alpha")
    assert pf.main() == 0
    monkeypatch.setattr("sys.argv", base + ["--pre-gate"])
    assert pf.main() == 2


# ── the rsync dry-run ─────────────────────────────────────────────────────────

def _capture_rsync(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    calls: list[list[str]] = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    return calls


def test_tree_check_alpha_default_is_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _capture_rsync(monkeypatch)
    assert pf.check_tree("melehost", "~/ami_trade/", 5) == []
    cmd = calls[0]
    assert cmd[-2] == f"{pf._REPO_ROOT}/" and cmd[-1] == "melehost:~/ami_trade/"
    assert "--exclude=infra/alpha.env" in cmd


def test_tree_check_beta_compares_the_given_root_and_excludes_both_env_files(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls = _capture_rsync(monkeypatch)
    assert pf.check_tree("ami-beta", "~/ami_trade/", 5, tmp_path) == []
    cmd = calls[0]
    assert cmd[-2] == f"{tmp_path}/" and cmd[-1] == "ami-beta:~/ami_trade/"
    assert "--exclude=infra/alpha.env" in cmd and "--exclude=infra/beta.env" in cmd


def test_identity_failure_names_the_promotion_command_of_the_target(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pf, "_get", lambda *a, **k: (200, {"git_sha": "unset", "alpha_tag": "unset"}))
    alpha = pf.check_identity("http://x", "s", "abc", None, 5)
    beta = pf.check_identity("http://x", "s", "abc", None, 5, "/promote-to-beta")
    assert "not through /promote-to-alpha" in alpha[0]
    assert "not through /promote-to-beta" in beta[0]


# ── the command documents ─────────────────────────────────────────────────────

def _cmd(name: str) -> str:
    return (_CMDS / name).read_text()


@pytest.mark.parametrize("name", ["promote-to-beta.md", "rollback-beta.md"])
def test_beta_commands_are_real_and_never_touch_melehost(name: str) -> None:
    text = _cmd(name)
    assert "STUB" not in text and "stub" not in text.lower().split("---", 2)[1]
    assert "ssh melehost" not in text and "melehost:" not in text and "scp infra/alpha.env" not in text
    assert "ami-beta" in text and "api-beta.agenticmarketintel.ai" in text
    assert "api-alpha.agenticmarketintel.ai" not in text


def test_promote_to_beta_ships_a_tag_never_head_and_keeps_the_gates() -> None:
    text = _cmd("promote-to-beta.md")
    for needle in (
        "git worktree add --detach",              # ships from a clean temp worktree of the tag
        "PROMOTION_HOLD.md",                       # hold gate kept
        "dispatch.sh inbox",                       # audit-lane gate kept
        "--target beta --pre-gate",                # Alpha postflight record gate
        "uat_gate.py",                             # UAT ledger gate
        "--for alpha-post --runs-only",
        "beta-${TODAY}-${N}",
        "git tag \"$BETA_TAG\" \"$GIT_SHA\"",      # same commit as the alpha tag
        "scp infra/beta.env ami-beta:~/ami_trade/.env",
        "alembic upgrade head",
        "--expect-sha",
        "--expect-tag",
        "Asia/Kuala_Lumpur",
    ):
        assert needle in text, f"promote-to-beta.md lost: {needle}"
    # migrations before the swap
    assert text.index("alembic upgrade head") < text.index("up -d --build api-alpha")


def test_every_rsync_exclude_alpha_has_beta_also_has_and_vice_versa() -> None:
    def excludes(text: str) -> set[str]:
        return {ln.strip().split("--exclude=")[1].strip(" \\") for ln in text.splitlines()
                if ln.strip().startswith("--exclude=")}
    a, b = excludes(_cmd("promote-to-alpha.md")), excludes(_cmd("promote-to-beta.md"))
    assert "'infra/beta.env'" in a and "'infra/alpha.env'" in a, (
        "an Alpha promotion run from the main checkout would copy Beta credentials to melehost")
    assert a == b, f"the two rsync exclude lists diverged: {sorted(a ^ b)}"


def test_the_parked_gcp_artifacts_say_so() -> None:
    assert "PARKED (CR267" in (_ROOT / ".github" / "workflows" / "deploy-beta.yml").read_text()
    assert "PARKED (CR267" in (_ROOT / "infra" / "gcp" / "README.md").read_text()
