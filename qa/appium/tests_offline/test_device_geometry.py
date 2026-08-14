"""Offline guards for the nav-bar band `helpers/device.py` hands the layout
checks.

`obstructed_bottom_y` is the boundary the whole DEF075 class is measured
against: an element whose centre falls below it is reported as sitting under
the system nav bar. Get the boundary wrong and the check either invents
findings or hides them, and either way the report looks the same as a correct
one — which is why the function already returns `was_measured` and why the
fallback path deserves a test even though it is rarely taken.

It used to end in a per-profile px constant, `126  # 48dp * ~2.625 density,
this device`. Neither half held: it is a dataclass default shared by every
profile, and the Android rig measures 320dpi — density 2.0, where 48dp is 96px.
No test could have caught it, because there was nothing to catch: the number
was self-consistent and simply did not describe any device in use.
"""

from __future__ import annotations

import pytest

from config.devices import GALAXY_A17
from helpers import device as device_helpers


@pytest.mark.parametrize(
    "dpi, expected_px",
    [
        (160, 48),   # mdpi, density 1.0 — the definition of dp
        (320, 96),   # the Android rig, measured
        (420, 126),  # density 2.625 — what the old constant actually described
        (560, 168),
    ],
)
def test_the_nav_bar_fallback_scales_with_the_device_density(
    monkeypatch, dpi, expected_px
):
    monkeypatch.setattr(
        device_helpers, "_adb", lambda *a, **k: f"Physical density: {dpi}\n"
    )
    assert device_helpers._navbar_fallback_px(GALAXY_A17) == expected_px


def test_an_override_density_wins_over_the_physical_one(monkeypatch):
    """A device can be running at a density other than its panel's — the Note7
    FE that turned up on the rig cable reports `Physical size: 1440x2560` with
    `Override size: 1080x1920`. `display_size` already prefers the override for
    the same reason: the app is laid out against it, so the nav bar is too."""
    monkeypatch.setattr(
        device_helpers,
        "_adb",
        lambda *a, **k: "Physical density: 560\nOverride density: 320\n",
    )
    assert device_helpers._navbar_fallback_px(GALAXY_A17) == 96


def test_an_unparseable_density_raises_rather_than_guessing(monkeypatch):
    """Both dumpsys parses have already failed by the time this runs. Returning
    some plausible number here would produce a nav-bar band nobody measured,
    reported identically to one that was — the degrade-loudly rule (CR040)."""
    monkeypatch.setattr(device_helpers, "_adb", lambda *a, **k: "wat")
    with pytest.raises(RuntimeError, match="Refusing to guess"):
        device_helpers._navbar_fallback_px(GALAXY_A17)
