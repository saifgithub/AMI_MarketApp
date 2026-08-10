"""Autonomous breadth-first walk of the app (CR163).

This is what CR162 bought. Before the semantics tree was exposed, a crawler on
iOS would have had nothing to enumerate — the app was one opaque rectangle, so
"explore it" could only mean tapping random coordinates. Now every tappable node
is addressable and labelled, so the crawler can enumerate, choose, and know
where it has already been.

**The frontier holds PATHS, not screens.** The first version of this queued
screen fingerprints, which was unimplementable and quietly broken: there is no
`goto(fingerprint)` — the only way back to a screen is to walk to it again. So
each frontier entry is a replayable list of labels from a known root, and a root
is a bottom-nav identifier, which is reachable from anywhere in the shell.
Replay can fail (a modal covers the nav, a list item moved); that branch is
dropped and recorded rather than retried, because a crawler that fights the app
spends its whole budget on one screen.

Other decisions worth keeping:

- **Screens are fingerprinted, not counted.** There is no route to read
  (`home_shell.dart` switches an IndexedStack with setState, no navigation event
  to observe), so "am I somewhere new?" is answered by hashing the set of
  visible control labels. Two screens with the same controls are the same screen
  for this purpose — a list with different rows is not a new bug surface.
- **The budget is wall-clock, not step count.** Steps range from 200ms to
  several seconds depending on what the tap opened, so a step budget produces
  wildly different coverage run to run and makes findings non-comparable.
- **Destructive controls are never tapped.** Not a nicety: this drives the real
  Alpha backend with a real account. A crawler that taps "delete" or "sign out"
  destroys its own session and writes junk into a shared system.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field

from helpers.gestures import hide_keyboard_if_shown
from helpers.locators import by_id, by_text, element_description, interactive_elements
from selenium.common.exceptions import WebDriverException

# Never tapped. Matched case-insensitively as substrings of the control's label.
# Deliberately broad: skipping a safe button costs a little coverage, tapping a
# destructive one costs the session and possibly real data.
FORBIDDEN = (
    "delete", "remove", "sign out", "log out", "logout", "reset",
    "restart onboarding", "clear", "cancel subscription", "unsubscribe",
    "buy", "subscribe", "upgrade", "purchase", "pay", "confirm trade",
    "submit order", "place order", "sell all", "close position",
)

# Controls that leave the app. Tapping them strands the crawler in Safari or
# Mail with no way back.
EXITS = ("open in browser", "privacy policy", "terms", "contact support", "email us")


def is_safe_to_tap(label: str) -> bool:
    low = label.strip().lower()
    if not low or low == "<unlabeled>":
        # No label means no way to prove it is not "delete", and any finding it
        # produced could not be described to a human anyway. The unlabelled
        # controls are separately REPORTED by the oracles, so this is a
        # visible gap in coverage rather than a silent one.
        return False
    return not any(word in low for word in FORBIDDEN + EXITS)


def screen_fingerprint(labels: list[str]) -> str:
    """Stable id for "the set of controls currently on screen"."""
    return hashlib.sha256("|".join(sorted(set(labels))).encode()).hexdigest()[:12]


@dataclass
class CrawlResult:
    screens_seen: int = 0
    taps: int = 0
    screen_labels: dict[str, list[str]] = field(default_factory=dict)
    screen_paths: dict[str, list[str]] = field(default_factory=dict)
    replay_failures: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class Explorer:
    def __init__(
        self,
        driver,
        *,
        budget_s: float = 240.0,
        max_depth: int = 3,
        on_screen=None,
        settle_s: float = 1.0,
    ):
        self.driver = driver
        self.budget_s = budget_s
        self.max_depth = max_depth
        # Called once per newly-discovered screen. Runs where the crawler
        # already is, so the oracles need no second navigation pass.
        # Returns the labels to use for onward exploration — an oracle that
        # swipes (scroll-overflow does) invalidates whatever we read before it,
        # so the explorer re-reads afterwards rather than tapping stale nodes.
        self.on_screen = on_screen
        self.settle_s = settle_s
        self.result = CrawlResult()

    # -- observation ------------------------------------------------------

    def _labels(self) -> list[str]:
        """One accessibility round trip per element, once per observation.
        The oracles are handed this list rather than re-walking the tree —
        on iOS each attribute read is a WebDriverAgent round trip and they
        dominate crawl time.

        The keyboard is dismissed first, and that is not tidiness. The system
        keyboard is reported as ordinary interactive elements sitting at the
        bottom of the screen, so every one of its keys reads as intruding on
        the home-indicator band. The first live crawl produced 8 findings of
        which 4 were keyboard keys — "English (UK)", "Dictate", "العربية" —
        a >50% false-positive rate on the exact check the harness exists for.
        With a fixer agent consuming this queue, that is not noise, it is fixes
        written for defects in Apple's keyboard.
        """
        hide_keyboard_if_shown(self.driver)
        return [element_description(self.driver, el) for el in interactive_elements(self.driver)]

    def _observe(self, depth: int, path: list[str]) -> tuple[str, list[str]]:
        labels = self._labels()
        fingerprint = screen_fingerprint(labels)
        if fingerprint not in self.result.screen_labels:
            self.result.screen_labels[fingerprint] = labels
            self.result.screen_paths[fingerprint] = list(path)
            self.result.screens_seen += 1
            if self.on_screen is not None:
                try:
                    self.on_screen(fingerprint, depth, labels)
                    # Oracles may have swiped; re-read before anyone taps.
                    labels = self._labels()
                except Exception as exc:  # an oracle must never end the crawl
                    self.result.errors.append(f"on_screen({fingerprint}): {exc}")
        return fingerprint, labels

    # -- navigation -------------------------------------------------------

    def _replay(self, root: str | None, path: list[str]) -> bool:
        """Return to a screen by walking to it again. False if the path no
        longer resolves — that branch is then abandoned, not retried."""
        if root is None:
            # No navigable root — we are crawling in place. Nothing to replay,
            # and claiming success is correct: we ARE on the only screen we can
            # be on.
            return True
        try:
            by_id(self.driver, root).click()
            time.sleep(self.settle_s)
        except Exception as exc:
            self.result.replay_failures.append(f"root {root}: {exc}")
            return False

        for label in path:
            try:
                by_text(self.driver, label).click()
                time.sleep(self.settle_s)
            except Exception:
                self.result.replay_failures.append(f"{root} -> {' > '.join(path)} (at {label!r})")
                return False
        return True

    # -- the walk ---------------------------------------------------------

    def crawl(self, roots: list[str]) -> CrawlResult:
        """Breadth-first from each root tab until the wall-clock budget is spent.

        Level by level across ALL roots, not root by root: a deep first tab
        would otherwise consume the entire budget and the remaining four
        surfaces would never be seen at all.
        """
        deadline = time.monotonic() + self.budget_s

        # (root identifier, path of labels from that root). An empty `roots`
        # means the shell was never reached (fresh install parked on onboarding):
        # crawl the current screen in place, with `None` as the root so _replay
        # knows there is nowhere to navigate back to.
        frontier: list[tuple[str, list[str]]] = (
            [(root, []) for root in roots] if roots else [(None, [])]
        )
        tapped: dict[str, set[str]] = {}

        depth = 0
        while frontier and depth < self.max_depth and time.monotonic() < deadline:
            next_frontier: list[tuple[str, list[str]]] = []

            for root, path in frontier:
                if time.monotonic() >= deadline:
                    break
                if not self._replay(root, path):
                    continue

                screen, labels = self._observe(depth, path)
                already = tapped.setdefault(screen, set())
                candidates = [l for l in labels if is_safe_to_tap(l) and l not in already]

                for label in candidates:
                    if time.monotonic() >= deadline:
                        break
                    already.add(label)
                    try:
                        by_text(self.driver, label).click()
                    except Exception:
                        continue  # element went away between read and tap — normal
                    self.result.taps += 1
                    time.sleep(self.settle_s)

                    after, _ = self._observe(depth + 1, path + [label])
                    if after != screen:
                        next_frontier.append((root, path + [label]))
                    # Return to this screen before trying the next sibling.
                    # Replaying from the root is slower than a back gesture but
                    # deterministic: a back gesture on a screen that did not
                    # push a route silently does something else instead.
                    if not self._replay(root, path):
                        break

            frontier = next_frontier
            depth += 1

        return self.result
