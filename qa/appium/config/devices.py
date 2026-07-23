"""Known device profiles for this harness.

Only one device is wired into the CR080 Phase 1 pass: the Galaxy A17 already
attached to melehost over USB (the same device `scripts/install_android.sh`
already knows as "A17"). Add rows here, not scattered constants, when Phase 3
grows the device matrix (Galaxy Note FE per that same script).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DeviceProfile:
    name: str
    serial: str
    app_package: str = "ai.agenticmarketintel.ami_trade"
    app_activity: str = "ai.agenticmarketintel.ami_trade.MainActivity"
    # Fallback nav-bar height in px, used only if the dumpsys parse in
    # helpers/device.py fails outright — see that module's docstring for why
    # we prefer reading it live over trusting this constant.
    navbar_height_px_fallback: int = 126  # 48dp * ~2.625 density, this device


GALAXY_A17 = DeviceProfile(name="Galaxy A17 (SM-A176B)", serial="R5CY91AY99Y")

DEFAULT_DEVICE = GALAXY_A17
