"""Exhaustive crawl (CR264): visit every reachable screen, press every control.

CR163's explorer samples: one global budget, label-fingerprinted screens,
destructive controls never touched. This one is a census. Differences:

1. **Budget per screen** (default 90s) plus a global cap (default 90 min), so a
   deep screen cannot starve the rest and a runaway cannot run all night.
2. **Screens are `ami.screen.<name>`** when the app exposes it (CR264 phase A),
   else the old label fingerprint, prefixed `fp:` in the output.
3. **One page-source parse per observation** (controls.parse_snapshot), not a
   round trip per attribute.
4. **Every press is judged** (controls.press_outcome + the intent catalogue +
   crash / error-sink / layout oracles). Dead taps and intent mismatches are
   findings.
5. **Destructive controls are pressed LAST**, then the app is reset and
   re-onboarded. `never_press.json` holds the few that can never be pressed.
"""

from __future__ import annotations

import re
import time
from collections import deque
from pathlib import Path

from crawler import controls as C
from crawler.errorsink import SinkUnavailable
from crawler.intents import Catalogue, check_expectation
from helpers.gestures import hide_keyboard_if_shown, scroll_to_top, swipe_up, tap_xy
from helpers.platform import is_ios
from helpers.system_alerts import dismiss_system_alert_if_present

_BACK_LABELS = {"back", "close", "done", "dismiss"}
_MAX_SCROLLS = 12


class Fatal(RuntimeError):
    """The session is unrecoverable; coverage so far is still written."""


class ReplayFailed(RuntimeError):
    pass


def _step(node: C.Node, nav: str | None = None) -> dict:
    return {"nav": nav} if nav else {"ident": node.ident, "label": node.label, "type": node.type}


def _step_name(step: dict) -> str:
    return step.get("nav") or step.get("ident") or step.get("label") or "?"


def _masked(label: str) -> str:
    return C._id_label(label)


def _match(nodes, step: dict):
    for n in nodes:
        if not (n.interactive and n.visible):
            continue
        if step.get("nav") and n.ident == step["nav"]:
            return n
        if step.get("ident") and n.ident == step["ident"]:
            return n
    for n in nodes:
        if (n.interactive and n.visible and not step.get("nav") and step.get("label")
                and _masked(n.label) == _masked(step["label"]) and n.type == step.get("type", n.type)):
            return n
    return None


class ExhaustiveCrawler:
    def __init__(self, driver, profile, geom, out_dir: Path, *, coverage: C.Coverage,
                 nav_ids: dict[str, str], catalogue: Catalogue | None = None,
                 per_screen_s: float = 90.0, global_cap_s: float = 5400.0,
                 max_depth: int = 6, settle_s: float = 1.0, sink_reader=None,
                 screen_oracles=None, fresh_session=None, never_press=None, log=print):
        self.driver, self.profile, self.geom = driver, profile, geom
        self.out = out_dir
        self.cov = coverage
        self.nav_ids = nav_ids
        self.nav_set = set(nav_ids.values())
        self.catalogue = catalogue
        self.per_screen_s, self.global_cap_s = per_screen_s, global_cap_s
        self.max_depth, self.settle_s = max_depth, settle_s
        self.sink_reader = sink_reader
        self.screen_oracles = screen_oracles
        self.fresh_session = fresh_session  # callable() -> new driver (reset + re-onboard)
        self.never = never_press if never_press is not None else C.load_never_press()
        self.log = log
        self.t0 = time.monotonic()
        self.spent: dict[str, float] = {}
        self.visited: set[str] = set()
        self.root_key: dict[str, str] = {}
        self.deferred: list[tuple[C.Control, list[dict], dict]] = []
        self.screen_findings: list[dict] = []
        self.notes: list[str] = []
        self.sink_seen = 0
        self.snap: C.Snapshot | None = None
        self._shots = 0
        self.app_id = profile.app_id
        self._last_phase = False

    # -- observation ------------------------------------------------------

    def _observe(self) -> C.Snapshot:
        self.snap = C.take(C.parse_snapshot(self.driver.page_source, "ios" if is_ios(self.driver) else "android"))
        return self.snap

    def _over_cap(self) -> bool:
        """Main phase stops at 85% of the cap so the destructive phase (and the
        reset after it) always gets time; `_over_hard_cap` guards that phase."""
        return time.monotonic() - self.t0 > self.global_cap_s * (0.85 if not self._last_phase else 1.0)

    def _shot(self, tag: str) -> str:
        self._shots += 1
        name = re.sub(r"[^A-Za-z0-9_.-]+", "_", tag)[:60]
        rel = f"screenshots/{self._shots:03d}-{name}.png"
        try:
            self.driver.get_screenshot_as_file(str(self.out / rel))
        except Exception:
            return ""
        return rel

    def _app_state(self) -> int:
        try:
            return int(self.driver.query_app_state(self.app_id))
        except Exception:
            return -1

    def _visible_controls(self, snap: C.Snapshot) -> list[C.Node]:
        h = self.geom["display"][1]
        floor = self.geom["navbar_top_y"]
        out = []
        for n in snap.nodes:
            if not (n.interactive and n.visible) or n.w <= 0 or n.h <= 0:
                continue
            if n.ident in self.nav_set:
                continue
            if not (0 < n.cy < min(floor, h)):
                continue
            out.append(n)
        return sorted(out, key=lambda n: (n.cy, n.cx))

    # -- navigation -------------------------------------------------------

    def _tap(self, n: C.Node) -> None:
        tap_xy(self.driver, n.cx, n.cy)
        time.sleep(self.settle_s)

    def _swipe_down_content(self) -> None:
        from pages.base_page import content_band
        from helpers.gestures import swipe_down
        swipe_down(self.driver, content_band(self.geom))

    def _reveal(self, step: dict) -> C.Node | None:
        snap = self._observe()
        n = _match(snap.nodes, step)
        if n and self._visible_controls(snap).count(n):
            return n
        from pages.base_page import content_band
        band = content_band(self.geom)
        for _ in range(8):
            self._swipe_down_content()
            n = _match(self._observe().nodes, step)
            if n and n in self._visible_controls(self.snap):
                return n
        for _ in range(_MAX_SCROLLS):
            swipe_up(self.driver, band)
            n = _match(self._observe().nodes, step)
            if n and n in self._visible_controls(self.snap):
                return n
        return None

    def _unfocus(self) -> None:
        """Dismiss the keyboard WITHOUT submitting. WDA cannot hide it on this
        app, and Return/Go on a ticker field would convene the Room, so only a
        key literally named Done (or its Arabic form) is ever tapped."""
        try:
            if not self.driver.is_keyboard_shown():
                return
        except Exception:
            return
        try:
            from appium.webdriver.common.appiumby import AppiumBy
            keys = self.driver.find_elements(
                AppiumBy.IOS_PREDICATE,
                'type == "XCUIElementTypeButton" AND (label IN {"Done","done","\u062a\u0645"})') if is_ios(self.driver) else []
            if keys:
                keys[0].click()
                time.sleep(0.4)
        except Exception:
            pass

    def _back_once(self) -> bool:
        if not is_ios(self.driver):
            try:
                self.driver.back()
                time.sleep(self.settle_s)
                return True
            except Exception:
                return False
        snap = self._observe()
        for n in snap.nodes:
            if n.interactive and n.visible and (
                    n.label.lower() in _BACK_LABELS or n.ident.endswith((".back", ".close"))):
                self._tap(n)
                return True
        return False

    def _relaunch(self) -> None:
        try:
            self.driver.terminate_app(self.app_id)
            time.sleep(1)
            self.driver.activate_app(self.app_id)
            time.sleep(self.settle_s * 3)
        except Exception as exc:
            raise Fatal(f"could not relaunch the app: {exc}") from exc

    def _recover_foreground(self) -> None:
        for _ in range(3):
            if self._app_state() == 4:
                return
            try:
                self.driver.activate_app(self.app_id)
            except Exception:
                pass
            time.sleep(self.settle_s * 2)
        if self._app_state() != 4:
            self._relaunch()

    def _to_root(self, nav: str) -> None:
        for attempt in range(4):
            snap = self._observe()
            n = next((x for x in snap.nodes if x.ident == nav and x.visible), None)
            if n is None:
                if attempt == 1:
                    self._tap_barrier()
                if attempt >= 2:
                    self._relaunch()
                elif not self._back_once():
                    time.sleep(self.settle_s)
                continue
            self._tap(n)
            snap = self._observe()
            want = self.root_key.get(nav)
            if not want or not want.startswith(C.SCREEN_PREFIX) or snap.key == want:
                return
            if not self._back_once():
                self._tap_barrier()
        raise ReplayFailed(f"could not reach tab root {nav}")

    def _tap_barrier(self) -> None:
        w, _ = self.geom["display"]
        try:
            tap_xy(self.driver, w // 2, 60)
            time.sleep(self.settle_s)
        except Exception:
            pass

    def _goto(self, path: list[dict]) -> None:
        self._to_root(path[0]["nav"])
        for step in path[1:]:
            n = self._reveal(step)
            if n is None:
                raise ReplayFailed(f"step {_step_name(step)!r} not found")
            self._tap(n)
        self._observe()

    def _return(self, path: list[dict], parent_key: str) -> None:
        """Cheapest way back: a back control; failing that, replay the path."""
        if self._back_once():
            snap = self._observe()
            if snap.key == parent_key:
                return
        self._goto(path)

    # -- the per-press judgement -----------------------------------------

    def _sink_new(self) -> list[dict]:
        if not self.sink_reader:
            return []
        try:
            allf = self.sink_reader()
        except SinkUnavailable:
            return []
        new = allf[self.sink_seen:]
        self.sink_seen = len(allf)
        return new

    def _press(self, ctl: C.Control, node: C.Node, before: C.Snapshot, prev_key: str | None) -> C.Snapshot:
        try:
            self._tap(node)
        except Exception as exc:
            if self._app_state() in (1, -1):
                self.cov.mark(ctl, "crashed", finding=f"app gone while pressing ({exc.__class__.__name__})")
                self._relaunch()
                return self._observe()
            self.cov.mark(ctl, "press_failed", finding=f"press raised {exc.__class__.__name__}: {str(exc)[:120]}")
            return self._observe()

        state = self._app_state()
        left_app = False
        if state == 1:
            ctl_shot = self._shot("crash-" + ctl.label)
            self.cov.mark(ctl, "crashed", finding=f"app crashed / is not running after press [{ctl_shot}]")
            self._relaunch()
            return self._observe()
        if state in (2, 3, 0):
            left_app = True
            self._recover_foreground()
        after = self._observe()
        if any(n.type.endswith("Alert") for n in after.nodes):
            dismiss_system_alert_if_present(self.driver)
            after = self._observe()
        if node.is_input:
            self._unfocus()
            after = self._observe()

        outcome = "left_app" if left_app else C.press_outcome(before, after, node)
        finding = ""
        intent = None
        if self.catalogue is not None:
            intent = self.catalogue.lookup(ctl.screen, node.ident, node.label)
            if intent is None:
                ctl.intent = "unexplained"
                finding = "unexplained control (no entry in the control catalogue)"
            else:
                ctl.expect = intent.expect
                if intent.expect in ("navigate", "sheet", "dialog") and intent.target.startswith("ami.screen.") and not left_app:
                    # The root id can lag the transition by a frame or two.
                    for _ in range(3):
                        from crawler.intents import _surface_present
                        if _surface_present(intent.target, after, self.catalogue):
                            break
                        time.sleep(0.8)
                        after = self._observe()
                v = check_expectation(intent, before, after, left_app=left_app, prev_key=prev_key,
                                      catalogue=self.catalogue)
                ctl.intent = v.status
                if v.status == "mismatch":
                    finding = v.detail
        dead_ok = intent is not None and intent.expect == "none"
        if outcome == "dead" and not dead_ok and not (intent and intent.expect != "none" and ctl.intent == "precondition_not_met"):
            shot = self._shot("dead-" + (node.label or node.ident))
            self.cov.mark(ctl, outcome, finding=f"dead tap: nothing observable changed [{shot}]")
        else:
            self.cov.mark(ctl, outcome, leads_to=after.key if after.key != before.key else "")
        if finding:
            ctl.finding.append(finding + f" [{self._shot('intent-' + (node.label or node.ident))}]")

        for f in self._sink_new():
            shot = self._shot("sink-" + (node.label or node.ident))
            ctl.finding.append(f"{f.get('rule', 'flutter_error')}: {f.get('detail', '')} [{shot}]")
            self.screen_findings.append({**f, "screen": ctl.screen, "control": ctl.id, "screenshot": shot})
        return after

    # -- one screen -------------------------------------------------------

    def _kind(self, node: C.Node, cls: str) -> str:
        if cls in ("destructive", "unlabelled", "external"):
            return cls
        if node.ident in self.nav_set:
            return "nav"
        if node.is_input:
            return "input"
        return "toggle" if node.is_toggle else "button"

    def _visit(self, path: list[dict], depth: int, parent_key: str | None, queue: deque) -> None:
        try:
            self._goto(path)
        except ReplayFailed as exc:
            self.notes.append(f"abandoned branch {' > '.join(_step_name(s) for s in path)}: {exc}")
            return
        snap = self.snap
        key = snap.key
        self.visited.add(key)
        if path and len(path) == 1:
            self.root_key.setdefault(path[0]["nav"], key)
        first = self.cov.see_screen(key, path=[_step_name(s) for s in path])
        labels = [n.label or "<unlabeled>" for n in snap.nodes if n.interactive and n.visible]
        if first:
            shot = self._shot("screen-" + key)
            self.cov.screens[key]["screenshot"] = shot
            if self.screen_oracles:
                for f in self.screen_oracles(self.driver, key, labels):
                    f["screenshot"] = shot
                    self.screen_findings.append(f)
                try:
                    scroll_to_top(self.driver, __import__("pages.base_page", fromlist=["x"]).content_band(self.geom))
                except Exception:
                    pass
                self._observe()
        self.log(f"  screen {key} (depth {depth}, {len(self.cov.screens)} seen, {int(time.monotonic() - self.t0)}s)")

        from pages.base_page import content_band
        band = content_band(self.geom)
        top_pass_done = False
        scrolls = 0
        budget_hit = False
        parent_prev = parent_key
        while True:
            if self._over_cap() or self.spent.get(key, 0) > self.per_screen_s:
                budget_hit = True
                break
            snap = self.snap
            if snap.key != key:
                try:
                    self._return(path, key)
                except ReplayFailed:
                    break
                snap = self.snap
            todo = None
            for n in self._visible_controls(snap):
                cls = C.classify(n)
                if self.catalogue is not None:
                    it = self.catalogue.lookup(key, n.ident, n.label)
                    if it is not None and it.expect == "destructive":
                        cls = "destructive"
                ctl = self.cov.discover(key, n, self._kind(n, cls))
                if ctl.pressed or ctl.exempt or ctl.id in {d[0].id for d in self.deferred}:
                    continue
                reason = C.never_press_reason(key, n, self.never)
                if reason:
                    self.cov.exempt(ctl, f"never_press: {reason}")
                    continue
                if not n.enabled:
                    self.cov.exempt(ctl, "disabled (enabled=false)")
                    continue
                if cls in ("destructive", "unlabelled"):
                    self.deferred.append((ctl, list(path), _step(n)))
                    ctl.outcome = "deferred (pressed last)"
                    continue
                todo = (ctl, n)
                break
            if todo is None:
                moved = self._scroll_down(band, key)
                if moved:
                    scrolls += 1
                    continue
                pending = [c for c in self.cov.controls.values()
                           if c.screen == key and not c.pressed and not c.exempt
                           and c.id not in {d[0].id for d in self.deferred}]
                if pending and not top_pass_done:
                    top_pass_done = True
                    try:
                        scroll_to_top(self.driver, band)
                    except Exception:
                        pass
                    self._observe()
                    continue
                break

            ctl, node = todo
            started = time.monotonic()
            before = snap
            after = self._press(ctl, node, before, parent_prev)
            if after.key != key or after.sheets != before.sheets:
                child_key = after.key
                step = _step(node)
                if depth < self.max_depth and child_key not in self.visited and child_key not in (key,):
                    self.visited.add(child_key)
                    queue.append((path + [step], depth + 1, key))
                elif child_key not in self.visited:
                    self.notes.append(f"depth cap: {child_key} not explored (via {ctl.id})")
                try:
                    self._return(path, key)
                except ReplayFailed:
                    pass
            self.spent[key] = self.spent.get(key, 0.0) + (time.monotonic() - started)

        if budget_hit:
            self.notes.append(f"per-screen/global budget hit on {key}")

    def _scroll_down(self, band, key: str) -> bool:
        before = {C.control_id(key, n) for n in self._visible_controls(self.snap)}
        before_sig = self.snap.sig
        swipe_up(self.driver, band)
        time.sleep(0.4)
        after = self._observe()
        now = {C.control_id(key, n) for n in self._visible_controls(after)}
        return after.key == key and bool(now - before) and after.sig != before_sig

    # -- the whole crawl ---------------------------------------------------

    def run(self) -> None:
        for f in self._sink_new():
            self.screen_findings.append({**f, "screen": "(before the crawl: install / onboarding)"})
        queue: deque = deque(([{"nav": nav}], 0, None) for nav in self.nav_ids.values())
        while queue and not self._over_cap():
            path, depth, parent = queue.popleft()
            try:
                self._visit(path, depth, parent, queue)
            except Fatal:
                raise
            except Exception as exc:
                self.notes.append(f"visit {' > '.join(_step_name(s) for s in path)} raised {exc.__class__.__name__}: {str(exc)[:160]}")
                try:
                    self._recover_foreground()
                except Fatal:
                    raise
        self._press_deferred()

    def _press_deferred(self) -> None:
        if not self.deferred:
            return
        self._last_phase = True
        self.log(f"  pressing {len(self.deferred)} destructive/unlabelled control(s) last")
        pressed_any = False
        for ctl, path, step in self.deferred:
            if self._over_cap():
                self.cov.exempt(ctl, "global cap reached before the destructive phase")
                continue
            try:
                self._goto(path)
                node = self._reveal(step)
                if node is None:
                    ctl.outcome = "not found at destructive phase"
                    continue
                parent = self.snap.key
                self._press(ctl, node, self.snap, None)
                pressed_any = True
                if self.snap.key != parent or not any(n.ident in self.nav_set for n in self.snap.nodes):
                    self._after_destructive()
            except Exception as exc:
                ctl.outcome = f"destructive phase error: {exc.__class__.__name__}"
                self.notes.append(f"{ctl.id}: {exc}")
        if pressed_any:
            self._after_destructive(force=True)

    def _after_destructive(self, force: bool = False) -> None:
        if self.fresh_session is None:
            self.notes.append("no fresh_session callback: app NOT reset after the destructive phase")
            return
        self.driver = self.fresh_session()
        self._observe()
