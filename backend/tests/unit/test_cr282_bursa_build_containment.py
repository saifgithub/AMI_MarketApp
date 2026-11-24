"""CR282 ruling 3 — `--bursa` compiles AMI_BURSA=true into INTERNAL builds only.

Bursa is built and tested on Alpha and stays off for testers until counsel
answers the CMSA investment-advice question (S6 Question 4). The build scripts
are the one place a tester-facing binary could get the switch, so the refusal
is driven through the real iOS script (same harness as DEF296) and pinned in
the Android script's source.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_IOS = _REPO_ROOT / "scripts" / "build_testflight.sh"
_ANDROID = _REPO_ROOT / "scripts" / "build_playstore.sh"
_PUBSPEC = _REPO_ROOT / "mobile" / "pubspec.yaml"
_REFUSAL = "--bursa is for INTERNAL Alpha builds only"
_INERT = ("--no-bump", "--no-commit", "--no-upload")


@pytest.fixture
def run(tmp_path):
    key_id = "TESTKEY"
    keys = tmp_path / ".appstoreconnect" / "private_keys"
    keys.mkdir(parents=True)
    (keys / f"AuthKey_{key_id}.p8").write_text("not a real key")

    def _run(*args: str) -> subprocess.CompletedProcess:
        before = _PUBSPEC.read_text()
        proc = subprocess.run(
            ["bash", str(_IOS), *_INERT, *args],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(_REPO_ROOT),
            env={
                "HOME": str(tmp_path),
                "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
                "APP_STORE_API_KEY_ID": key_id,
                "REVENUECAT_IOS_SDK_KEY": "test_stub",
            },
        )
        assert _PUBSPEC.read_text() == before, "the script modified mobile/pubspec.yaml"
        return proc

    return _run


def test_bursa_without_internal_only_is_refused(run) -> None:
    proc = run("--bursa")
    assert proc.returncode == 1
    assert _REFUSAL in proc.stderr, proc.stderr


def test_bursa_on_a_production_build_is_refused(run) -> None:
    proc = run("--internal-only", "--production", "--bursa")
    assert proc.returncode == 1
    assert _REFUSAL in proc.stderr, proc.stderr


def test_bursa_on_the_beta_channel_is_refused(run) -> None:
    proc = run("--internal-only", "--no-games", "--channel", "beta", "--bursa")
    assert proc.returncode == 1
    assert _REFUSAL in proc.stderr, proc.stderr


def test_an_internal_bursa_build_passes_this_gate(run) -> None:
    proc = run("--internal-only", "--bursa")
    assert _REFUSAL not in proc.stderr, proc.stderr


@pytest.mark.parametrize("script", [_IOS, _ANDROID], ids=["ios", "android"])
def test_the_switch_defaults_off_and_reaches_the_dart_define(script: Path) -> None:
    src = script.read_text()
    assert "DO_BURSA=0" in src
    assert '--dart-define=AMI_BURSA="$([[ "$DO_BURSA" -eq 1 ]] && echo true || echo false)"' in src
    assert _REFUSAL in src
