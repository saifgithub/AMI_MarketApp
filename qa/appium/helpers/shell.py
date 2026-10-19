"""Is the app shell on screen, and how do we get back to it.

Split out of `helpers/onboarding.py` because two callers need it and they are
not the same caller. Onboarding asks "has the interview handed over yet"; every
*test* asks "is the app in a state I can navigate from". They were the same
question only as long as nothing ever covered the shell.

**Why this exists at all.** The bottom nav is the shell's proof of life, and it
disappears for two completely different reasons:

  1. Onboarding has not finished. The nav does not exist yet. Walk the
     interview.
  2. A modal sheet or a pushed route is on top — a Convene sheet, the Room, a
     trade ticket. The nav exists and is covered. Press back.

Conflating those is expensive, and it was: a Convene sheet left open by an
earlier test hid the nav, `ensure_onboarded` concluded "not onboarded", and set
its exploratory walk loose on a fully working app. The walk taps the
bottom-most labelled control, which on that sheet is CONVENE — so it convened
the Room. Four real 12-agent runs against the on-prem LLM, real credits, on
tickers nobody chose (`BY`, `ANDG`, `BY`, `BY`).

The discriminator is the nav's `Semantics(identifier:)` rather than the word
"FLOOR". The identifier exists exactly when the shell is mounted; the text both
races the first paint AND is a label on a control the walk might tap.
"""

from __future__ import annotations

import time

from config.semantics_ids import NAV_IDS
from helpers.locators import exists_id, exists_text
from helpers.platform import is_ios

# Layers to dismiss before concluding the shell is absent rather than covered.
# Deep enough for a sheet opened from a pushed route; shallow enough that a
# device genuinely mid-onboarding falls through to the walk in a few seconds.
MAX_BACK_OUTS = 5


def shell_is_up(driver, floor_label: str) -> bool:
    """True exactly when the app shell is mounted and reachable.

    Falls back to the rendered label for builds older than CR162, which is the
    weaker test but is all such a build offers.
    """
    if exists_id(driver, NAV_IDS["Floor"], retry=False):
        return True
    return exists_text(driver, floor_label, retry=False)


def wait_for_shell(driver, floor_label: str, *, timeout_s: float) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if shell_is_up(driver, floor_label):
            return True
        time.sleep(0.5)
    return False


def tree_is_dark(driver) -> bool:
    """True when the app is on screen but exposes no accessibility tree.

    Measured on the iOS Simulator: after a long-lived session the Flutter
    semantics tree can drop to the bare Application/Window skeleton while the
    app keeps painting normally, and it STAYS that way across new Appium
    sessions (`noReset=True` keeps the process). Every locator then misses, so
    the failure reads as "shell never appeared" / "onboarding did not reach
    Floor" (a 480s blind walk) rather than what it is. Only an app relaunch
    brings the tree back. Distinguish it from a covered shell by the page
    source carrying no labelled or identified node at all.
    """
    if not is_ios(driver):
        return False
    try:
        source = driver.page_source
    except Exception:
        return False
    return source.count('label="') + source.count(' name="ami.') <= 1


def relaunch_if_dark(driver, app_id: str | None, *, why: str) -> bool:
    """Terminate and re-activate the app when its tree is dark. True if it ran.

    Announces itself — a suite that silently restarts the app under test hides
    the dark-tree app/engine problem this exists to survive."""
    if not app_id or not tree_is_dark(driver):
        return False
    print(f"    [shell] accessibility tree is empty ({why}) — relaunching {app_id}")
    driver.terminate_app(app_id)
    time.sleep(1.0)
    driver.activate_app(app_id)
    time.sleep(6.0)
    return True


def recover_to_shell(driver, floor_label: str, *, quiet: bool = False) -> bool:
    """Dismiss whatever is covering the shell. True if it worked.

    Returns False rather than raising when the shell never appears — the two
    callers want different things then. `ensure_onboarded` wants to walk the
    interview; a per-test precondition wants to say so and let the test fail on
    its own terms.
    """
    for attempt in range(MAX_BACK_OUTS):
        driver.back()
        time.sleep(1.0)
        if shell_is_up(driver, floor_label):
            if not quiet:
                print(
                    f"    [shell] recovered after {attempt + 1} back press(es) "
                    f"— a previous test left a sheet or route open"
                )
            return True
    return False
