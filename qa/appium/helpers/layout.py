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
"""

from __future__ import annotations

import io

import numpy as np
from PIL import Image

from helpers.gestures import Band, screenshot_png, swipe_up
from helpers.locators import interactive_elements, scrollable_exists


def bounds(element) -> tuple[int, int, int, int]:
    rect = element.rect
    x1, y1 = rect["x"], rect["y"]
    x2, y2 = x1 + rect["width"], y1 + rect["height"]
    return x1, y1, x2, y2


def label(element) -> str:
    text = (element.text or "").strip()
    if text:
        return text
    desc = element.get_attribute("content-desc") or ""
    return desc.strip() or "<unlabeled>"


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
                "element_label": label(element),
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


def _pixels(png_bytes: bytes, band: Band) -> np.ndarray:
    left, top, width, height = band
    image = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    return np.asarray(image.crop((left, top, left + width, top + height)))


def swipe_moved(driver, band: Band, *, diff_threshold: float = 0.005) -> bool:
    """True if a swipe over `band` visibly changed its pixels — i.e. the
    screen actually scrolled. `band` must already exclude any always-animating
    chrome (home_shell.dart's TickerTape, in particular) or it will read as
    false movement on every screen, masking real findings."""
    before = _pixels(screenshot_png(driver), band)
    swipe_up(driver, band, percent=0.75)
    after = _pixels(screenshot_png(driver), band)
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
) -> list[dict]:
    if swipe_moved(driver, band):
        return []  # something responded to the swipe — has a working scroller (or closed/changed)

    if scrollable_exists(driver):
        return []  # a scrollable ancestor exists even if this particular swipe didn't move it

    bottoms = [bounds(element)[3] for element in interactive_elements(driver)]
    last_bottom = max(bottoms) if bottoms else 0
    reaches_fold = last_bottom >= (navbar_top_y - safe_margin)
    if not reaches_fold:
        return []  # short screen, legitimately doesn't need to scroll

    return [
        {
            "check": "scroll_overflow",
            "screen": screen,
            "severity": "medium",
            "last_element_bottom": last_bottom,
            "navbar_top_y": navbar_top_y,
            "suggested_category": "ux",
            "note": "static screen: content reaches the fold, no scrollable ancestor, swipe produced no visible movement",
        }
    ]
