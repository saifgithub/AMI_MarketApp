"""Device-level operations that sit outside the Appium session: adb on Android,
`xcrun simctl` on iOS.

Android runs on melehost, where the Galaxy A17 is attached over USB. iOS runs on
the Mac — the only machine with Xcode — against the Simulator first (CR162).

Reading the obstructed bottom band is the one genuinely non-obvious piece, and
the two platforms differ in kind, not just in tooling:

- **Android** draws edge-to-edge *behind* the system nav bar (that is the DEF075
  scenario), so the FlutterView's own rendered bounds run to the full display
  height and carry no signal about where the bar sits. The real inset has to
  come from the window manager, and it is read live.
- **iOS** has no system nav bar and exposes no equivalent query. The
  home-indicator inset is a documented platform constant (34pt on every
  notch/Dynamic-Island iPhone), so it is used as one and labelled as one. It is
  not a measurement and this module does not pretend otherwise.
"""

from __future__ import annotations

import json
import re
import subprocess

from config.devices import IOS, DeviceProfile


def _adb(serial: str, *args: str) -> str:
    result = subprocess.run(
        ["adb", "-s", serial, *args],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout


def _simctl(*args: str) -> str:
    result = subprocess.run(
        ["xcrun", "simctl", *args],
        capture_output=True,
        text=True,
        timeout=120,
    )
    return result.stdout


# --------------------------------------------------------------------------
# iOS simulator resolution
# --------------------------------------------------------------------------


def resolve_ios_udid(name_fragment: str) -> str:
    """Find a booted-or-bootable simulator UDID by name.

    A simulator's UDID is machine-specific, so it must never be committed —
    hence config/devices.py leaves IOS_SIM.serial empty and this resolves it at
    run time. Prefers an already-booted device so a session attaches to the one
    the operator is actually looking at.
    """
    raw = _simctl("list", "devices", "available", "--json")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"could not parse `simctl list devices --json`: {raw[:200]!r}") from exc

    candidates = [
        device
        for devices in payload.get("devices", {}).values()
        for device in devices
        if name_fragment.lower() in device.get("name", "").lower()
    ]
    if not candidates:
        available = sorted(
            d.get("name", "?")
            for devices in payload.get("devices", {}).values()
            for d in devices
        )
        raise RuntimeError(
            f"no available simulator matching {name_fragment!r}. Available: {available}"
        )
    booted = [d for d in candidates if d.get("state") == "Booted"]
    return (booted or candidates)[0]["udid"]


def boot_ios(udid: str) -> None:
    """Boot the simulator if it is not already up. `simctl boot` on an
    already-booted device exits non-zero with 'Unable to boot device in current
    state: Booted' — that is success for our purposes, so it is not raised."""
    subprocess.run(["xcrun", "simctl", "boot", udid], capture_output=True, text=True, timeout=180)
    subprocess.run(["xcrun", "simctl", "bootstatus", udid], capture_output=True, text=True, timeout=300)


# --------------------------------------------------------------------------
# Cross-platform surface — every function takes the profile, not a bare serial
# --------------------------------------------------------------------------


def display_size(profile: DeviceProfile) -> tuple[int, int]:
    """Display size in the DRIVER's coordinate space: pixels on Android, points
    on iOS. Callers band-scope swipes and bounds checks in this space; see
    helpers/gestures.screen_scale() for converting to screenshot pixels."""
    if profile.platform == IOS:
        # simctl reports pixels, not points, and the ratio differs per model —
        # so this comes from the live Appium session instead (see the `device`
        # fixture in conftest.py, which passes the driver's window size in).
        raise RuntimeError(
            "iOS display size comes from the live driver session "
            "(driver.get_window_size()), not simctl — see conftest.device"
        )
    out = _adb(profile.serial, "shell", "wm", "size")
    override = re.search(r"Override size:\s*(\d+)x(\d+)", out)
    if override:
        return int(override.group(1)), int(override.group(2))
    physical = re.search(r"Physical size:\s*(\d+)x(\d+)", out)
    if physical:
        return int(physical.group(1)), int(physical.group(2))
    raise RuntimeError(f"could not parse `wm size` output: {out!r}")


def obstructed_bottom_y(profile: DeviceProfile, *, display_height: int) -> tuple[int, bool]:
    """Return `(y, was_measured)` — the y-coordinate where the bottom system
    furniture begins, and whether it was read live or fell back to a constant.

    The caller logs a fallback loudly rather than silently accepting a
    less-precise number (this project's degrade-loudly convention).
    """
    if profile.platform == IOS:
        # No query exists; the platform constant IS the answer, and it is
        # reported as unmeasured so no report claims otherwise.
        return display_height - profile.bottom_inset_pt, False

    # Primary: `dumpsys window displays` insets-source frame (SDK 30+ shape).
    out = _adb(profile.serial, "shell", "dumpsys", "window", "displays")
    insets_match = re.search(
        r"InsetsSource[^\n]*type=navigationBars[^\n]*?frame=\[(\d+),(\d+)\]\[(\d+),(\d+)\]",
        out,
    )
    if insets_match:
        return int(insets_match.group(2)), True

    # Fallback: `dumpsys window windows`, the NavigationBar window's mFrame.
    # Empirically (Galaxy A17, Android 11/SDK 30) the gap between the
    # "NavigationBar0}:" marker and its own `mFrame=` line is ~1.8KB of
    # verbose per-window dump — a short window here just silently misses
    # and falls through to the fallback constant, which is worse than a
    # slightly-too-wide window that risks the next window's frame.
    out = _adb(profile.serial, "shell", "dumpsys", "window", "windows")
    nav_block = re.search(r"NavigationBar\d*[\s\S]{0,2500}?mFrame=\[(\d+),(\d+)\]\[(\d+),(\d+)\]", out)
    if nav_block:
        return int(nav_block.group(2)), True

    return display_height - profile.navbar_height_px_fallback, False


def app_version(profile: DeviceProfile) -> str:
    if profile.platform == IOS:
        # A simulator app bundle's version is not queryable through simctl
        # without locating the container and reading Info.plist; the driver's
        # own session does not expose it either. Reported honestly as unknown
        # rather than guessed — the run id and the build script's own log carry
        # the version on this platform.
        return "unknown"
    out = _adb(profile.serial, "shell", "dumpsys", "package", profile.app_package)
    match = re.search(r"versionName=(\S+)", out)
    return match.group(1) if match else "unknown"


def reset_app(profile: DeviceProfile) -> None:
    """Force a cold anonymous session. Tests that need a fresh-install state
    call this explicitly rather than relying on capability-level reset
    (noReset stays True by default so everything else reuses one onboarded
    session, which is much faster)."""
    if profile.platform == IOS:
        subprocess.run(
            ["xcrun", "simctl", "terminate", profile.serial, profile.bundle_id],
            capture_output=True,
            text=True,
            timeout=60,
        )
        subprocess.run(
            ["xcrun", "simctl", "uninstall", profile.serial, profile.bundle_id],
            check=True,
            timeout=120,
        )
        return
    subprocess.run(
        ["adb", "-s", profile.serial, "shell", "pm", "clear", profile.app_package],
        check=True,
        timeout=30,
    )


def install_app(profile: DeviceProfile, artifact_path: str) -> None:
    if profile.platform == IOS:
        subprocess.run(
            ["xcrun", "simctl", "install", profile.serial, artifact_path],
            check=True,
            timeout=300,
        )
        return
    subprocess.run(
        ["adb", "-s", profile.serial, "install", "-r", artifact_path],
        check=True,
        timeout=300,
    )
