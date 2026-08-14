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


_PUBSPEC = _REPO_ROOT / "mobile" / "pubspec.yaml"

#: Passed on EVERY invocation, and the reason is not tidiness.
#:
#: Writing this suite cost a spurious commit. The mutation run that re-coupled
#: the gate to `DO_BILLING` meant `--no-billing` skipped the (broken) gate and
#: then skipped the billing refusals too — nothing was left to stop it, so it
#: reached the pubspec bump at `build_testflight.sh:253`, ran
#: `sed -i` on `mobile/pubspec.yaml`, and `git add && git commit`-ed
#: `0.1.0+93 → 0.1.0+94` into the repo. It only stopped at `flutter build`
#: because this fixture's scrubbed PATH has no `flutter`.
#:
#: The commit even carried the wrong author, which is the tell: `HOME` points
#: at a tmp dir here, so git found no `.gitconfig` and fell back to the machine
#: default. Reverted in the same commit as this hardening.
#:
#: A test that drives a real release script must disarm every side effect that
#: script has, not rely on an early exit landing before them — because the
#: thing under test IS where the early exits are, and a mutation is exactly the
#: case where they do not fire.
_INERT = ("--no-bump", "--no-commit", "--no-upload")


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

    Every run is bracketed by a `pubspec.yaml` snapshot. `_INERT` should make
    that impossible; the assertion is there because "should" is what produced
    the commit described above, and a side effect this suite cannot see is one
    it will reintroduce.
    """
    key_id = "TESTKEY"
    keys = tmp_path / ".appstoreconnect" / "private_keys"
    keys.mkdir(parents=True)
    (keys / f"AuthKey_{key_id}.p8").write_text("not a real key")

    def _run(*args: str) -> subprocess.CompletedProcess:
        before = _PUBSPEC.read_text()
        proc = subprocess.run(
            ["bash", str(_SCRIPT), *_INERT, *args],
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
        assert _PUBSPEC.read_text() == before, (
            f"running the script with {args} modified mobile/pubspec.yaml — a "
            "test drove a real release script past its bump. Restore the file "
            "and disarm the path before re-running.")
        return proc

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


def _games_banner(script: Path) -> str:
    src = script.read_text()
    banner = src[src.index("THIS BUILD CARRIES THE CR109"):]
    return banner[:banner.index("BANNER")]


@pytest.mark.parametrize("script_name", ["build_testflight.sh", "build_playstore.sh"])
def test_the_banner_describes_an_entry_point_that_exists(script_name: str) -> None:
    """Both release scripts, because the false claim was in both.

    DEF296 was filed against the iOS banner and fixed there first. The next
    Play release printed the identical sentence — *"The game is reachable by
    long-pressing the Floor footer"* — which CR182 deleted;
    `ami_tab.dart:54` puts the game in `AmiTab.visible`, so it is a fifth TAB
    reachable by tap from launch. Caught by watching a real release print it,
    not by a test, which is why this one is parametrised over both scripts
    rather than pinned to the one the defect was filed against.

    This is the sentence the whole guideline-2.3.1 argument rests on, and it is
    what an operator reads before deciding where a build may go.
    """
    banner = _games_banner(_REPO_ROOT / "scripts" / script_name)
    assert "long-press" not in banner.lower(), (
        f"{script_name}'s banner still describes the gesture CR182 removed")
    assert "easter egg" not in banner.split("\n")[1].lower(), (
        f"{script_name} still calls a visible tab an easter egg in its "
        "headline; the closing quote from Saiful may keep the phrase")


def test_the_ios_banner_states_a_basis_that_is_actually_true() -> None:
    """The iOS half, which had a second false claim the Play banner never had.

    Android's stated basis — the Play track is pinned to `internal` — is a real
    control (`publish_playstore.sh:69` refuses a `test_` key on any other
    track). iOS cited the RevenueCat key as what forces `--internal-only`, and
    that was untrue on the flag we build with. A gate whose stated reason is
    untrue is how an operator learns that firing does not mean stop — DEF277's
    words, in this script's own comments.
    """
    banner = _games_banner(_SCRIPT)
    assert not ("test_" in banner and "forces" in banner), (
        "the banner still cites the RevenueCat key as what forces "
        "--internal-only; that is the claim DEF296 was filed about")
    assert "--internal-only" in banner, (
        "the banner should name the control that actually ran")
