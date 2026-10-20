"""Lesson-reader steps for the CR263 journeys: read a lesson to its end and pass
its quiz.

The quiz answers are not in the app (the server holds the key and returns only
pass/fail), so a black-box test cannot know them. It does what a determined user
does: pick, submit, read the verdict, change what was wrong. The reader reports
"{correct} / {total} correct" after a submit, which lets each question be solved
independently (change ONE answer, resubmit, keep it if the count rose) instead of
searching every combination.

Geometry, not locators: the quiz options are plain text nodes with no stable
identifier, and which of them are tappable depends on what is inside the
viewport. So the nodes are read from the page source with their bounds and
tapped by coordinate. Coordinates are in driver units (points on iOS, pixels on
Android), the same space `tap_xy` speaks.
"""

from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from helpers.gestures import tap_xy
from helpers.journeys import drag, scroll_down, scroll_up
from helpers.locators import exists_text, exists_text_contains
from helpers.platform import is_ios

_BOUNDS = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")
_COUNT = re.compile(r"(\d+)\s*/\s*(\d+)\s*correct")


@dataclass(frozen=True)
class Node:
    label: str
    x: int
    y: int
    w: int
    h: int
    enabled: bool = True

    @property
    def cy(self) -> int:
        return self.y + self.h // 2


def nodes(driver) -> list[Node]:
    """Every labelled node in the hierarchy with its bounds."""
    root = ET.fromstring(driver.page_source)
    out: list[Node] = []
    for el in root.iter():
        a = el.attrib
        if is_ios(driver):
            label = (a.get("label") or a.get("name") or "").strip()
            if not label or a.get("visible") == "false":
                continue
            try:
                out.append(Node(label, int(float(a["x"])), int(float(a["y"])), int(float(a["width"])), int(float(a["height"])), a.get("enabled") != "false"))
            except (KeyError, ValueError):
                continue
        else:
            label = (a.get("content-desc") or a.get("text") or "").strip()
            m = _BOUNDS.match(a.get("bounds", ""))
            if not label or not m:
                continue
            x1, y1, x2, y2 = (int(g) for g in m.groups())
            out.append(Node(label, x1, y1, x2 - x1, y2 - y1, a.get("enabled") != "false"))
    return out


def _viewport(driver) -> tuple[int, int]:
    """Top and bottom of the scrolling reader pane, clear of header and nav."""
    size = driver.get_window_size()
    h = size["height"]
    return int(h * 0.16), int(h * 0.80)


def quiz_cards(driver) -> list[tuple[Node, list[Node]]]:
    """Each QUIZ card on screen with the option rows inside it, top to bottom."""
    top, bottom = _viewport(driver)
    ns = nodes(driver)
    cards = [n for n in ns if n.label.startswith("QUIZ") and n.label != "QUIZ ONLY" and n.h > 60]
    found = []
    for card in sorted(cards, key=lambda n: n.y):
        options = [
            n
            for n in ns
            if n is not card
            and n.x >= card.x
            and n.x + n.w <= card.x + card.w + 2
            and n.y >= card.y - 1
            and n.y + n.h <= card.y + card.h + 2
            and n.w >= card.w * 0.7
            and not n.label.startswith("QUIZ")
        ]
        found.append((card, sorted(options, key=lambda n: n.y)))
    return [(c, o) for c, o in found if c.y < bottom and c.y + c.h > top]


def _tap_node(driver, node: Node) -> None:
    """Click the element carrying this node's label — a real element click, which
    Flutter's gesture arena accepts (a raw coordinate tap did not select the
    option on the iOS Simulator). Matches on a distinctive prefix of the label and
    picks the candidate at the node's own position, because long option text
    with typographic characters defeats an exact-equality predicate."""
    from helpers.locators import _all_by_text_contains

    fragment = node.label.split("\n")[0][:28]
    best = None
    for el in _all_by_text_contains(driver, fragment, retry=False):
        try:
            r = el.rect
        except Exception:
            continue
        gap = abs(r["y"] - node.y)
        if best is None or gap < best[0]:
            best = (gap, el)
    if best is None or best[0] > 12:
        raise AssertionError(f"could not find a tappable element for option {node.label[:50]!r}")
    best[1].click()
    time.sleep(0.4)


def _question_key(card: Node) -> str:
    return re.sub(r"\s+", " ", card.label.replace("QUIZ", "", 1)).strip()[:60]


def _at_bottom(driver) -> bool:
    """SUBMIT QUIZ is ON SCREEN, not merely in the tree: Flutter keeps nodes just
    outside the viewport in the hierarchy, and tapping one of those does nothing."""
    top, bottom = _viewport(driver)
    return any(
        n.label == "SUBMIT QUIZ" and n.y >= top and n.y + n.h <= bottom + 20
        for n in nodes(driver)
    )


def submit_enabled(driver) -> bool:
    return any(n.label == "SUBMIT QUIZ" and n.enabled for n in nodes(driver))


def scroll_to_end(driver, *, max_scrolls: int = 25) -> None:
    for _ in range(max_scrolls):
        if _at_bottom(driver):
            return
        scroll_down(driver)
    if not _at_bottom(driver):
        raise AssertionError("never reached SUBMIT QUIZ at the end of the lesson")


def read_to_end(driver) -> int:
    """Scroll the lesson body to its end; return how many scrolls it took."""
    count = 0
    while not _at_bottom(driver):
        if count >= 30:
            raise AssertionError("lesson did not end within 30 scrolls")
        scroll_down(driver)
        count += 1
    return count


def wait_settled(driver, *, timeout_s: float = 6.0) -> None:
    """Return once the reader has stopped moving: two reads of the page, 0.5s apart,
    put every node in the same place. A tap during a fling only stops the fling."""
    deadline = time.monotonic() + timeout_s
    prev = None
    while time.monotonic() < deadline:
        snap = [(n.label[:20], n.y) for n in nodes(driver) if n.y > 120 and n.y < 700]
        if snap == prev:
            return
        prev = snap
        time.sleep(0.5)


def _select(driver, answers: dict[str, str]) -> dict[str, list[str]]:
    """Walk upward from the end of the lesson, tapping the option labelled
    `answers[q]` (the first option when unset) for each quiz card as it comes fully
    into view. Returns {question: [option labels]} for every card handled.

    Options are chosen BY LABEL, not position: the reader reshuffles them after
    TRY AGAIN, so "the second option" names a different answer on every attempt."""
    top, bottom = _viewport(driver)
    handled: dict[str, str] = {}
    seen: dict[str, list[str]] = {}  # every option label observed per question, across the whole scroll
    stagnant = 0
    for _ in range(40):
        progress = False
        wait_settled(driver)
        for card, options in quiz_cards(driver):
            key = _question_key(card)
            known = seen.setdefault(key, [])
            for o in options:
                if o.label not in known:
                    known.append(o.label)
            if key in handled or not options:
                continue
            wanted = answers.get(key)
            if wanted:
                opt = next((o for o in options if o.label == wanted), None)
                if opt is None:
                    continue  # the wanted option is not in the tree yet: keep scrolling
            else:
                opt = options[0]
            if opt.y < top or opt.y + opt.h > bottom:
                continue
            print(f"    [quiz] tap {opt.label[:40]!r} for {key[:30]!r}")
            _tap_node(driver, opt)
            handled[key] = opt.label
            answers.setdefault(key, opt.label)
            progress = True
        stagnant = 0 if progress else stagnant + 1
        if stagnant >= 4 and handled and all(k in handled for k in seen):
            break
        drag(driver, 0.975, 0.40, 0.65)  # small steps so every option rests fully in view at least once
        time.sleep(1.0)  # let the fling settle: a tap during momentum only stops the scroll
    return {k: seen[k] for k in handled}


def submit_and_read(driver) -> tuple[bool, int | None, int | None, str]:
    """Scroll to the end, press SUBMIT QUIZ, and wait for the verdict.
    Returns (passed, correct, total, evidence_text)."""
    from helpers.locators import wait_visible_text

    scroll_to_end(driver)
    wait_visible_text(driver, "SUBMIT QUIZ", timeout_s=5).click()
    deadline = time.monotonic() + 120  # grading can be slow while the shared LLM host is busy
    while time.monotonic() < deadline:
        time.sleep(1.0)
        joined = " | ".join(n.label for n in nodes(driver))
        m = _COUNT.search(joined)
        correct, total = (int(m.group(1)), int(m.group(2))) if m else (None, None)
        if "AGENT UNLOCKED" in joined:
            return True, correct, total, joined  # passing the last gateway quiz replaces the verdict with the unlock celebration
        if "PASSED" in joined and "NOT QUITE" not in joined:
            return True, correct, total, joined
        if "NOT QUITE" in joined or "TRY AGAIN" in joined:
            return False, correct, total, joined
        if "Couldn't submit your answer" in joined or "couldn't submit your answer" in joined.lower():
            raise AssertionError(
                "SUBMIT QUIZ replaced the lesson with an error page: "
                "\"Couldn't submit your answer - AMI is temporarily unavailable\" (backend unavailable)"
            )
        scroll_down(driver)  # the verdict box replaces the button and can start below the fold
    labels = [n.label[:50] for n in nodes(driver)][:14]
    return False, None, None, f"no verdict appeared within 120s of SUBMIT QUIZ; on screen: {labels}"


def _dismiss_verdict(driver) -> None:
    """Press TRY AGAIN and wait for the verdict box to go. Does nothing when there
    is no verdict showing."""
    from helpers.journeys import tap_button

    for _ in range(3):
        if not exists_text(driver, "TRY AGAIN", retry=False):
            return
        try:
            tap_button(driver, "TRY AGAIN", timeout_s=4)
        except Exception:
            pass
        time.sleep(1.5)
    if exists_text(driver, "TRY AGAIN", retry=False):
        raise AssertionError("TRY AGAIN was tapped three times and the verdict box is still showing")


def pass_quiz(driver, *, max_submits: int = 16) -> int:
    """Solve the quiz currently under the reader by coordinate ascent: submit with
    every question on its first option; for each question, try its other options
    one at a time and keep whichever raises the "{correct} / {total} correct"
    count. Returns the number of submits. Raises AssertionError if it cannot be
    passed."""
    scroll_to_end(driver)
    answers: dict[str, str] = {}
    submits = 0
    _dismiss_verdict(driver)  # a previous attempt may have left its verdict on screen

    def attempt() -> tuple[bool, int | None, int | None, dict[str, list[str]]]:
        nonlocal submits
        counts: dict[str, list[str]] = {}
        for _try in range(4):
            time.sleep(1.0)  # a tap on a still-moving list only stops it
            counts = _select(driver, answers)
            scroll_to_end(driver)
            time.sleep(0.8)
            if submit_enabled(driver):
                break
        else:
            raise AssertionError("SUBMIT QUIZ stayed disabled: not every question could be answered")
        passed, correct, total, evidence = submit_and_read(driver)
        submits += 1
        print(f"    [quiz] submit {submits}: passed={passed} correct={correct}/{total}")
        if not passed and correct is None:
            raise AssertionError(f"a wrong answer showed no 'N / M correct' count: {evidence[:300]}")
        return passed, correct, total, counts

    passed, best, total, counts = attempt()
    if passed:
        return submits
    for key, labels in list(counts.items()):
        keep = answers.get(key, labels[0])
        answers.setdefault(key, labels[0])
        for label in labels:
            if label == keep:
                continue
            if submits >= max_submits:
                raise AssertionError(f"quiz not passed within {max_submits} submits (best {best}/{total})")
            _dismiss_verdict(driver)
            answers[key] = label
            passed, got, total, _ = attempt()
            if passed:
                return submits
            if got is not None and got > best:
                best, keep = got, label
                break
        answers[key] = keep
        _dismiss_verdict(driver)
    raise AssertionError(f"quiz not passed after trying every option once per question (best {best}/{total})")
