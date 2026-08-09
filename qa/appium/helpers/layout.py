"""The two mechanical usability checks this harness exists for (CR080):

1. Nav-bar overlap — the DEF075 class. An interactive element's bounds
   intrude on the real system nav-bar band (read live via helpers.device,
   since Flutter's own edge-to-edge rendering carries no signal about where
   the bar actually is).
2. Non-scrolling overflow — a screen whose content reaches the fold, has no
   scrollable ancestor, and doesn't visibly move on a swipe probe.

Both return lists of finding dicts (never raise on "found nothing" — an empty
list is a clean screen) shaped to drop straight into helpers.report's
summary.json, using docs/defect/def_list.md's existing category vocabulary
as `suggested_category` so a human reviewing the report can promote a
confirmed finding into that register with no translation step.

CR162 — two platform notes:

- `navbar_top_y` keeps its name, and the check keeps the id `navbar_overlap`,
  so historical reports stay comparable. On iOS it means the top of the
  home-indicator / bottom-safe-area band. Same defect class, different
  furniture.
- Coordinates and screenshots are NOT the same unit on iOS. `element.rect` and
  gesture coordinates are in points; `get_screenshot_as_png` returns device
  pixels (3× on these iPhones). Android has no such split. Every band here is
  in the *driver's* coordinate space, and `_pixels()` scales it at the moment
  it crops. Getting this wrong does not error — it silently diffs the wrong
  third of the screen, which is why it is stated rather than assumed.
"""

from __future__ import annotations

import io

import numpy as np
from PIL import Image

from helpers.gestures import Band, screenshot_png, swipe_up
from helpers.locators import element_description, interactive_elements, scrollable_exists


def bounds(element) -> tuple[int, int, int, int]:
    rect = element.rect
    x1, y1 = rect["x"], rect["y"]
    x2, y2 = x1 + rect["width"], y1 + rect["height"]
    return x1, y1, x2, y2


def label(driver, element) -> str:
    """Kept as a thin alias so call sites read naturally; the platform
    dispatch lives in helpers/locators.element_description (asking XCUITest for
    `content-desc` is a WebDriverAgent 500, not an empty string)."""
    return element_description(driver, element)


def find_navbar_overlaps(driver, navbar_top_y: int, *, tol: int = 2, screen: str = "") -> list[dict]:
    findings = []
    for element in interactive_elements(driver):
        x1, y1, x2, y2 = bounds(element)
        overlap = y2 - navbar_top_y
        if overlap <= tol:
            continue
        center_y = (y1 + y2) / 2
        severity = "high" if center_y >= navbar_top_y else "medium"
        findings.append(
            {
                "check": "navbar_overlap",
                "screen": screen,
                "element_label": label(driver, element),
                "bounds": [x1, y1, x2, y2],
                "navbar_top_y": navbar_top_y,
                "overlap_px": overlap,
                "severity": severity,
                "suggested_category": "ui_glitch",
                "note": (
                    "element center falls inside the nav-bar band — a tap would land on the "
                    "system nav bar, not the button"
                    if severity == "high"
                    else "element's bottom edge is clipped by/under the nav-bar band"
                ),
            }
        )
    return findings


def _pixels(png_bytes: bytes, band: Band, scale: float = 1.0) -> np.ndarray:
    """Crop `band` — expressed in the driver's coordinate space — out of a
    screenshot, which is in device pixels. `scale` is pixels-per-point: 1.0 on
    Android, ~3.0 on a Retina iPhone. See the module docstring."""
    left, top, width, height = band
    image = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    box = (
        int(left * scale),
        int(top * scale),
        int((left + width) * scale),
        int((top + height) * scale),
    )
    return np.asarray(image.crop(box))


def swipe_moved(driver, band: Band, *, diff_threshold: float = 0.005, scale: float = 1.0) -> bool:
    """True if a swipe over `band` visibly changed its pixels — i.e. the
    screen actually scrolled. `band` must already exclude any always-animating
    chrome (home_shell.dart's TickerTape, in particular) or it will read as
    false movement on every screen, masking real findings."""
    before = _pixels(screenshot_png(driver), band, scale)
    swipe_up(driver, band, percent=0.75)
    after = _pixels(screenshot_png(driver), band, scale)
    if before.shape != after.shape:
        return True  # shape changed (e.g. a sheet closed/opened) — not a "didn't scroll" case
    differing = np.mean(np.any(np.abs(before.astype(int) - after.astype(int)) > 15, axis=-1))
    return bool(differing > diff_threshold)


def find_scroll_overflow(
    driver,
    band: Band,
    navbar_top_y: int,
    *,
    safe_margin: int = 24,
    screen: str = "",
    scale: float = 1.0,
) -> list[dict]:
    if swipe_moved(driver, band, scale=scale):
        return []  # something responded to the swipe — has a working scroller (or closed/changed)

    # Tri-state on purpose (CR162): True = a scrollable container is present,
    # None = this platform cannot tell us. Only a definite True suppresses the
    # finding. Treating None as False would manufacture findings on iOS screens
    # that scroll fine; treating it as True would suppress every real one.
    scrollable = scrollable_exists(driver)
    if scrollable is True:
        return []  # a scrollable ancestor exists even if this particular swipe didn't move it

    bottoms = [bounds(element)[3] for element in interactive_elements(driver)]
    last_bottom = max(bottoms) if bottoms else 0
    reaches_fold = last_bottom >= (navbar_top_y - safe_margin)
    if not reaches_fold:
        return []  # short screen, legitimately doesn't need to scroll

    corroborated = scrollable is False
    return [
        {
            "check": "scroll_overflow",
            "screen": screen,
            "severity": "medium" if corroborated else "low",
            "last_element_bottom": last_bottom,
            "navbar_top_y": navbar_top_y,
            "scrollable_check": "absent" if corroborated else "undetermined",
            "suggested_category": "ux",
            "note": (
                "static screen: content reaches the fold, no scrollable ancestor, "
                "swipe produced no visible movement"
                if corroborated
                else "content reaches the fold and a swipe produced no visible movement, "
                "but this platform cannot confirm the absence of a scrollable "
                "container — verify by hand before filing"
            ),
        }
    ]
