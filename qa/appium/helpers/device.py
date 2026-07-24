"""adb wrappers, serial-scoped. Everything here runs on melehost, where the
target device is attached over USB — see config/devices.py.

Reading the nav-bar band is the one non-obvious piece: Flutter draws
edge-to-edge *behind* the system nav bar (that's the DEF075 scenario), so the
FlutterView's own rendered bounds run all the way to the physical display
height and carry no signal about where the bar actually sits. The real inset
has to come from the window manager itself.
"""

from __future__ import annotations

import re
import subprocess


def _adb(serial: str, *args: str) -> str:
    result = subprocess.run(
        ["adb", "-s", serial, *args],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout


def display_size(serial: str) -> tuple[int, int]:
    """Return (width, height) in px. Prefers an override size if adb reports
    one (e.g. a device running in a forced-density/testing mode), else the
    physical size."""
    out = _adb(serial, "shell", "wm", "size")
    override = re.search(r"Override size:\s*(\d+)x(\d+)", out)
    if override:
        return int(override.group(1)), int(override.group(2))
    physical = re.search(r"Physical size:\s*(\d+)x(\d+)", out)
    if physical:
        return int(physical.group(1)), int(physical.group(2))
    raise RuntimeError(f"could not parse `wm size` output: {out!r}")


def navbar_top_y(serial: str, *, display_height: int, fallback_height_px: int) -> int:
    """Return the y-coordinate (px) where the system navigation bar begins.

    Two independent parses, most-reliable first; a fixed fallback if both
    fail so a flaky dumpsys parse degrades to "less precise" rather than
    "crashes the whole run" — but the fallback firing is logged loudly by the
    caller (see conftest.device fixture), never silent, per this project's
    degrade-loudly convention. `fallback_height_px` is the bar's *height*,
    not a y-coordinate — the fallback y is `display_height - fallback_height_px`.
    """
    # Primary: `dumpsys window displays` insets-source frame (SDK 30+ shape).
    out = _adb(serial, "shell", "dumpsys", "window", "displays")
    insets_match = re.search(
        r"InsetsSource[^\n]*type=navigationBars[^\n]*?frame=\[(\d+),(\d+)\]\[(\d+),(\d+)\]",
        out,
    )
    if insets_match:
        return int(insets_match.group(2))

    # Fallback: `dumpsys window windows`, the NavigationBar window's mFrame.
    # Empirically (Galaxy A17, Android 11/SDK 30) the gap between the
    # "NavigationBar0}:" marker and its own `mFrame=` line is ~1.8KB of
    # verbose per-window dump — a short window here just silently misses
    # and falls through to the fallback constant, which is worse than a
    # slightly-too-wide window that risks the next window's frame.
    out = _adb(serial, "shell", "dumpsys", "window", "windows")
    nav_block = re.search(r"NavigationBar\d*[\s\S]{0,2500}?mFrame=\[(\d+),(\d+)\]\[(\d+),(\d+)\]", out)
    if nav_block:
        return int(nav_block.group(2))

    return display_height - fallback_height_px


def app_version(serial: str, package: str) -> str:
    out = _adb(serial, "shell", "dumpsys", "package", package)
    match = re.search(r"versionName=(\S+)", out)
    return match.group(1) if match else "unknown"


def pm_clear(serial: str, package: str) -> None:
    """Force a cold anonymous session — Phase 1 onboarding-adjacent tests
    that need a fresh install state should call this explicitly rather than
    relying on capability-level reset (noReset stays True by default so
    everything else reuses one onboarded session, much faster)."""
    subprocess.run(["adb", "-s", serial, "shell", "pm", "clear", package], check=True, timeout=30)
