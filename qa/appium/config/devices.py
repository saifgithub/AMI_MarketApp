"""Known device profiles for this harness.

CR080 wired one device: the Galaxy A17 attached to melehost over USB (the same
device `scripts/install_android.sh` knows as "A17"). CR162 added the iOS side,
which runs on the Mac — the only machine with Xcode — starting on the Simulator.

Add rows here, not scattered constants, when the matrix grows (Galaxy Note FE
per that same script; the real iPhone 17 once WebDriverAgent is signed).
"""

from dataclasses import dataclass

ANDROID = "android"
IOS = "ios"


@dataclass(frozen=True)
class DeviceProfile:
    name: str

    # adb serial on Android, simulator/device UDID on iOS. One field because
    # every caller uses it the same way: "which device do I address?"
    serial: str

    platform: str = ANDROID

    # NOTE the two ids genuinely differ — this is not a typo to be "fixed".
    # mobile/android/app/build.gradle.kts uses snake_case, and
    # mobile/ios/Runner.xcodeproj uses camelCase.
    app_package: str = "ai.agenticmarketintel.ami_trade"
    app_activity: str = "ai.agenticmarketintel.ami_trade.MainActivity"
    bundle_id: str = "ai.agenticmarketintel.amiTrade"

    # Android: the system nav bar's *height* in px, used only if the dumpsys
    # parse in helpers/device.py fails outright — see that module for why a live
    # read is preferred over trusting this constant.
    navbar_height_px_fallback: int = 126  # 48dp * ~2.625 density, this device

    # iOS: the home-indicator / bottom-safe-area height in POINTS. Unlike
    # Android there is no window-manager query to read this from, so it is a
    # constant and is stated as one rather than dressed up as a measurement —
    # 34pt is the standard inset for every notch/Dynamic-Island iPhone. A
    # home-button device would be 0.
    bottom_inset_pt: int = 34

    @property
    def app_id(self) -> str:
        """The identifier the platform's own tooling wants."""
        return self.bundle_id if self.platform == IOS else self.app_package


GALAXY_A17 = DeviceProfile(name="Galaxy A17 (SM-A176B)", serial="R5CY91AY99Y")

# The Simulator is the first iOS target on purpose (CR162): it needs no
# WebDriverAgent provisioning, no Apple developer cert, and no device kept
# unlocked, so the suite can be proven before the signing work starts. The
# serial is resolved at runtime from `xcrun simctl` by name, because a
# simulator's UDID is machine-specific and must never be hardcoded into git.
IOS_SIM = DeviceProfile(
    name="iPhone 17 Simulator",
    serial="",  # filled in by helpers.device.resolve_ios_udid()
    platform=IOS,
)

# The real device, for once WebDriverAgent is signed. Kept here so the follow-up
# is a profile selection rather than new code.
IPHONE_17 = DeviceProfile(
    name="Saiful's iPhone 17",
    serial="00008150-001948640100401C",
    platform=IOS,
)

DEFAULT_DEVICE = GALAXY_A17

PROFILES: dict[str, DeviceProfile] = {
    ANDROID: GALAXY_A17,
    IOS: IOS_SIM,
}
