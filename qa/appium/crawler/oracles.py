"""Per-screen bug detectors (CR163).

An oracle is anything that can call a screen wrong without a human having
written an assertion about that specific screen. That property is what makes the
crawler scale: coverage grows by walking further, not by writing more tests.

Two of these reuse CR080's mechanical checks unchanged — they were already
oracles in this sense, just wired to a hand-written list of screens instead of
to a crawler.

**Ordering is load-bearing.** `find_scroll_overflow` SWIPES to see whether the
screen moves, so it changes what is on screen. It therefore runs last, after
every observation-only oracle, and the explorer re-reads the control list after
`on_screen` returns rather than tapping nodes it enumerated beforehand.

**No oracle re-walks the accessibility tree.** `labels` is passed in, already
read once by the explorer. On iOS every attribute read is a WebDriverAgent round
trip and they dominate crawl time; the first version of this file walked the
tree a second time per screen for no new information.
"""

from __future__ import annotations

from helpers.layout import find_navbar_overlaps, find_scroll_overflow
from pages.base_page import content_band

# A screen with almost nothing addressable is usually a failed load, an error
# state with no copy, or a spinner that never resolved. Occasionally it is a
# legitimately sparse screen, which is why this is `low` and carries the count.
_MIN_CONTROLS = 2


def _sparse_screen(screen: str, labels: list[str]) -> list[dict]:
    if len(labels) >= _MIN_CONTROLS:
        return []
    return [{
        "check": "sparse_screen",
        "screen": screen,
        "severity": "low",
        "detail": f"{len(labels)} interactive element(s)",
        "suggested_category": "ui_glitch",
        "note": "almost nothing addressable here — often a failed load, a spinner "
                "that never resolved, or an error state with no copy. Check the "
                "screenshot before filing; some screens are legitimately sparse.",
    }]


def _unlabelled_controls(screen: str, labels: list[str]) -> list[dict]:
    """Controls with no accessible label.

    Both a real accessibility defect (a screen reader announces them as a bare
    "button") and the reason the crawler must skip them — an unlabelled control
    cannot be proven not to be "delete". So each one is simultaneously a bug and
    a hole in this tool's own coverage, which is worth reporting rather than
    silently working around.

    Counted from the labels the explorer already read; `element_description`
    returns the "<unlabeled>" sentinel for exactly this case.
    """
    count = sum(1 for l in labels if l == "<unlabeled>")
    if not count:
        return []
    return [{
        "check": "unlabelled_control",
        "screen": screen,
        "severity": "medium",
        "detail": f"{count} control(s)",
        "suggested_category": "ui_glitch",
        "note": "interactive elements with no accessibility label: a screen reader "
                "announces them as a bare 'button', and the crawler skips them "
                "because an unlabelled control cannot be proven safe to tap. "
                "Fixing these widens automated coverage as well as accessibility.",
    }]


def screen_oracles(screen: str, labels: list[str], driver, geom: dict) -> list[dict]:
    """Run every per-screen oracle.

    `geom` is `{"display": (w, h), "navbar_top_y": int, "scale": float,
    "platform": str}` — computed ONCE per run by the caller, not per screen.

    Never raises: one oracle failing must not end a crawl that still has budget,
    so each is isolated and a failure is reported as a HARNESS problem, clearly
    labelled so it is never filed as an application defect. CR080 lost two
    sessions to exactly that confusion.
    """
    findings: list[dict] = []
    bottom_y = geom["navbar_top_y"]

    # Observation-only first.
    checks = [
        ("sparse_screen", lambda: _sparse_screen(screen, labels)),
        ("unlabelled_control", lambda: _unlabelled_controls(screen, labels)),
        ("navbar_overlap", lambda: find_navbar_overlaps(driver, bottom_y, screen=screen)),
        # MUST STAY LAST — this one swipes.
        ("scroll_overflow", lambda: find_scroll_overflow(
            driver, content_band(geom), bottom_y, screen=screen, scale=geom["scale"],
        )),
    ]

    for name, run in checks:
        try:
            findings.extend(run())
        except Exception as exc:
            findings.append({
                "check": "oracle_error",
                "screen": screen,
                "severity": "low",
                "detail": name,
                "suggested_category": "other",
                "note": f"the {name} oracle raised on this screen: {exc}. This is a "
                        f"HARNESS problem, not an application defect — do not file it "
                        f"as one.",
            })
    return findings
