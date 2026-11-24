"""DEF530 guard — the tester APK is built with the feature flags its AAB gets.

`publish_playstore.sh` ships two artifacts of ONE version string: the Play AAB
(`build_playstore.sh`, `flutter build appbundle`) and a separate release APK for
the automated tester / device lab (`share_apk_to_tester.sh`, `flutter build apk`).
Every `bool.fromEnvironment` feature flag is baked at compile time, so a flag
the AAB sets and the APK forgets silently ships a different app under the same
version. DEF301 was AMI_GAMES; DEF530 was AMI_BURSA (build 0.1.0+130: AAB on,
APK off). Second occurrence of the class (failure_patterns.md P43), so the
check is structural: this test fails the moment the AAB gains a dart-define
the APK lacks, unless it is named in `_AAB_ONLY` with a reason.
"""

from __future__ import annotations

import re
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
_BUILD_AAB = _SCRIPTS / "build_playstore.sh"
_BUILD_APK = _SCRIPTS / "share_apk_to_tester.sh"
_PUBLISH = _SCRIPTS / "publish_playstore.sh"
_CHANNEL_LIB = _SCRIPTS / "lib" / "release_channel.sh"

# Defines the AAB carries that the tester APK legitimately does not. Anything
# NOT here and NOT in the APK is a failure. Adding a line needs a reason.
_AAB_ONLY = {
    # Store-billing / ads config for a store-distributed binary. The tester APK
    # is a sideloaded rig build that never reaches the Play billing or AdMob
    # production paths; these are secrets-or-unit-ids, not feature flags.
    "REVENUECAT_ANDROID_SDK_KEY": "Play billing key; rig APK does not purchase",
    "ADMOB_MODE": "ads mode for the store build; rig APK shows no real ads",
    "ADMOB_INTERSTITIAL_AD_UNIT_ID": "AdMob unit id, store build only",
    "ADMOB_NATIVE_AD_UNIT_ID": "AdMob unit id, store build only",
    "ADMOB_TEST_DEVICE_IDS": "AdMob test devices, store build only",
    "ADMOB_CONSENT_DEBUG_GEOGRAPHY": "AdMob consent debugging, store build only",
    "AMI_RELEASE_CHANNEL": "gates real ads on store channel; rig APK never serves real ads",
}

# Feature flags that must be in BOTH commands (named so a rename cannot make
# the generic diff vacuous).
_MUST_BE_IN_BOTH = ("AMI_GAMES", "AMI_BURSA")

_DEFINE = re.compile(r"--dart-define=([A-Za-z_][A-Za-z0-9_]*)")


def _command(path: Path, needle: str) -> str:
    """The shell command starting at `needle`, joined across `\\` continuations."""
    lines = path.read_text().splitlines()
    for i, line in enumerate(lines):
        if needle in line and not line.lstrip().startswith("#") and not line.lstrip().startswith("echo"):
            parts = [line]
            while parts[-1].rstrip().endswith("\\") and i + 1 < len(lines):
                i += 1
                parts.append(lines[i])
            return "\n".join(parts)
    raise AssertionError(f"`{needle}` not found in {path.name}")


def _alpha_channel_defines() -> set[str]:
    """The defines `"${CHANNEL_DEFINES[@]}"` expands to for the alpha channel."""
    src = _CHANNEL_LIB.read_text()
    m = re.search(r'if \[\[ "\$CHANNEL" == "alpha" \]\]; then(.*?)return 0', src, re.S)
    assert m, "alpha branch of ami_channel_setup not found in release_channel.sh"
    names = set(_DEFINE.findall(m.group(1)))
    assert names, "alpha CHANNEL_DEFINES parsed empty"
    return names


def _aab_defines() -> set[str]:
    cmd = _command(_BUILD_AAB, "flutter build appbundle")
    names = set(_DEFINE.findall(cmd))
    if "${CHANNEL_DEFINES[@]}" in cmd:
        names |= _alpha_channel_defines()
    return names


def _apk_defines() -> set[str]:
    return set(_DEFINE.findall(_command(_BUILD_APK, "flutter build apk")))


def test_every_aab_define_is_in_the_apk_or_explicitly_aab_only() -> None:
    missing = _aab_defines() - _apk_defines() - set(_AAB_ONLY)
    assert not missing, (
        f"share_apk_to_tester.sh's `flutter build apk` lacks {sorted(missing)}, "
        "which build_playstore.sh's `flutter build appbundle` sets: the tester APK "
        "would run a different app than the AAB under the same version (DEF301, "
        "DEF530). Pass them in the APK too, or list them in _AAB_ONLY with a reason."
    )


def test_games_and_bursa_are_in_both_commands() -> None:
    aab, apk = _aab_defines(), _apk_defines()
    for flag in _MUST_BE_IN_BOTH:
        assert flag in aab, f"{flag} missing from the appbundle command"
        assert flag in apk, f"{flag} missing from the apk command"


def test_aab_only_allow_list_has_no_stale_entries() -> None:
    aab, apk = _aab_defines(), _apk_defines()
    stale = [n for n in _AAB_ONLY if n not in aab or n in apk]
    assert not stale, f"_AAB_ONLY entries no longer AAB-only or no longer in the AAB: {stale}"


def test_publish_forwards_games_and_bursa_to_the_apk_helper() -> None:
    src = _PUBLISH.read_text()
    call = re.search(r'^\s*if (.*?share_apk_to_tester\.sh"?);', src, re.M)
    assert call, "publish_playstore.sh no longer calls share_apk_to_tester.sh"
    for flag in _MUST_BE_IN_BOTH:
        assert re.search(rf"\b{flag}=", call.group(1)), (
            f"publish_playstore.sh does not pass {flag} to share_apk_to_tester.sh"
        )
    # Bursa is derived from the same BUILD_ARGS the AAB is built from.
    assert re.search(r'\[\[ "\$_a" == "--bursa" \]\] && _apk_bursa=true', src)
    assert re.search(r'\[\[ "\$_a" == "--no-games" \]\] && _apk_games=false', src)


def test_helper_defaults_both_flags_to_false() -> None:
    src = _BUILD_APK.read_text()
    assert ': "${AMI_GAMES:=false}"' in src
    assert ': "${AMI_BURSA:=false}"' in src
