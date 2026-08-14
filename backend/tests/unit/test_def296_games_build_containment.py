"""DEF296 — a games build must state its containment, on every flag path.

`scripts/build_testflight.sh` printed a banner asserting that a games build was
safe in a store binary *"because a test_… RevenueCat key forces
`--internal-only`, and TestFlight INTERNAL groups skip Beta App Review."* That
forcing was guarded on `DO_BILLING -eq 1`. `--no-billing` sets `DO_BILLING=0`
**and** blanks the key (DEF290, correctly — a `test_` key must not be compiled
into a shipped binary), so the gate short-circuited on its first condition,
`--internal-only` was never demanded, and the banner's entire stated basis was
absent while the banner still printed.

`--no-billing` is not an exotic path. DEF282 removed the purchase SDK from the
app's code path entirely and both RevenueCat keys in `infra/alpha.env` are
`test_…`, so it is the only honest flag for every build we can currently
produce — `0.1.0+90` and `+91` both shipped exactly this way.

**Why these tests EXECUTE the script rather than grep it.** DEF296's own
complaint is that a stated control was a citation rather than a check; a guard
that greps for the sentence would be the same mistake one level up. The refusal
path is reachable in isolation — the script exits at the games gate before the
release-parity check, the pubspec bump, or any `flutter` invocation — so the
direction that matters can be driven for real. The banner-honesty assertions
below are source-level because a banner IS its source text; there is no other
representation of it to test.

Related: DEF301 (the sibling artifact defect, same release pair), DEF290 and
DEF277 (the two gates whose stated reasons had gone untrue), CR182 (removed the
long-press the banner still described).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO_ROOT / "scripts" / "build_testflight.sh"

#: The refusal's own words. Asserted rather than a bare exit code, because
#: every early exit in this script is also `1` — see `test_no_games_fails_for_a
#: _different_reason`, which is only meaningful if the reasons are separable.
_GAMES_REFUSAL = "AMI_GAMES is on and --internal-only was not passed"


@pytest.fixture
def run(tmp_path):
    """Drive the real script far enough to reach the games gate.

    Two things stand between the shebang and that gate, and both are made to
    pass rather than stubbed away: an App Store Connect private key under
    `$HOME` (redirected to a tmp dir — the test never touches the real one) and
    `mobile/ios/ExportOptions.plist`, which is in the repo. `REVENUECAT_IOS_SDK
    _KEY` is exported so the script does not read `infra/alpha.env`, which is
    gitignored and therefore absent on some machines; without that this suite
    would pass or fail depending on whose checkout it ran in.
    """
    key_id = "TESTKEY"
    keys = tmp_path / ".appstoreconnect" / "private_keys"
    keys.mkdir(parents=True)
    (keys / f"AuthKey_{key_id}.p8").write_text("not a real key")

    def _run(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(_SCRIPT), *args],
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

    return _run


def test_the_default_games_build_is_refused_without_internal_only(run) -> None:
    """`DO_GAMES` defaults to 1, so this is what running the script bare does."""
    proc = run()
    assert proc.returncode == 1
    assert _GAMES_REFUSAL in proc.stderr, proc.stderr


def test_no_billing_no_longer_disables_the_containment(run) -> None:
    """The defect itself. `--no-billing` short-circuited the only gate that
    demanded `--internal-only`, so the flag we use for every build we can
    currently produce was also the flag that turned the containment off."""
    proc = run("--no-billing")
    assert proc.returncode == 1
    assert _GAMES_REFUSAL in proc.stderr, proc.stderr


def test_no_games_fails_for_a_different_reason(run) -> None:
    """The negative direction: with no game in the build there is nothing for
    this gate to contain, so it must not be what stops the build.

    It still exits 1 — on the RevenueCat rule, which is correct and unchanged —
    and that is the point: the two refusals are distinguishable, so the test
    above is asserting the games gate rather than any-failure-whatsoever.
    """
    proc = run("--no-games")
    assert _GAMES_REFUSAL not in proc.stderr, proc.stderr


def test_the_gate_does_not_depend_on_the_billing_flags() -> None:
    """The structural half of the same claim.

    Passing on `--no-billing` above could in principle be achieved by a gate
    still nested in the billing block with an inverted condition. This pins the
    shape: the games refusal is a top-level `if` naming `DO_GAMES` and
    `DO_INTERNAL_ONLY` and not `DO_BILLING`.
    """
    src = _SCRIPT.read_text()
    line = next(
        (ln for ln in src.splitlines()
         if ln.startswith("if [[") and "DO_GAMES" in ln and "DO_INTERNAL_ONLY" in ln),
        None,
    )
    assert line is not None, (
        "no top-level games/internal-only refusal — an indented one is inside "
        "another block and inherits its condition, which is the defect")
    assert "DO_BILLING" not in line, (
        f"the containment is coupled to the billing flags again: {line}")


def test_the_banner_states_a_basis_that_is_actually_true() -> None:
    """A gate whose stated reason is untrue is how an operator learns that
    firing does not mean stop — DEF277's words, in this script's own comments.

    Two claims had gone false. The RevenueCat key does not force
    `--internal-only` on the path we build on, and CR182 deleted the
    Floor-footer long-press: `ami_tab.dart` now puts the game in
    `AmiTab.visible`, so it is a fifth TAB. The banner is what the operator
    reads before deciding where a build may go, so both had to move.
    """
    src = _SCRIPT.read_text()
    banner = src[src.index("THIS BUILD CARRIES THE CR109"):]
    banner = banner[:banner.index("BANNER")]

    assert "long-press" not in banner.lower(), (
        "the banner still describes the gesture CR182 removed")
    assert not ("test_" in banner and "forces" in banner), (
        "the banner still cites the RevenueCat key as what forces "
        "--internal-only; that is the claim DEF296 was filed about")
    assert "--internal-only" in banner, (
        "the banner should name the control that actually ran")
