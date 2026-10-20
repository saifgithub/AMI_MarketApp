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
from crawler import routes as R
from crawler.intents import Catalogue, _norm, _surface_present, check_expectation, label_pattern
from helpers.gestures import hide_keyboard_if_shown, scroll_to_top, swipe_up, tap_xy
from helpers.platform import is_ios
from helpers.system_alerts import dismiss_system_alert_if_present

_BACK_LABELS = {"back", "close", "done", "dismiss"}
_MAX_SCROLLS = 12


class Fatal(RuntimeError):
    """The session is unrecoverable; coverage so far is still written."""


class ReplayFailed(RuntimeError):
    pass


def _step(node: C.Node, nav: str | None = None, *, to: str = "", screen: str = "", intent: str = "") -> dict:
    if nav:
        return {"nav": nav}
    d = {"ident": node.ident, "label": node.label, "type": node.type}
    if to:
        d["to"] = to
    if screen:
        d["screen"] = screen
    if intent:
        d["intent"] = intent
    return d


def _step_name(step: dict) -> str:
    return step.get("nav") or step.get("ident") or step.get("label") or step.get("pat") or step.get("intent") or "?"


def _masked(label: str) -> str:
    return C._id_label(label)


# One-off prompts that are gone on the second visit: a replay that cannot find
# them has not failed, the prompt was simply answered already.
_OPTIONAL_STEPS = {"not now", "later", "maybe later", "skip", "no thanks"}


def _match(nodes, step: dict, catalogue: Catalogue | None = None, claimed: set[str] | None = None):
    """The control a replay step means, or None.

    Order: root id, exact id, masked label, catalogue label pattern (route steps),
    the catalogue entry the recorded press resolved to (the label drifts, the
    entry does not), and finally - for a placeholder row such as `<lesson title
    row>` - the first control the catalogue has no entry for."""
    live = [n for n in nodes if n.interactive and n.visible]
    for n in live:
        if step.get("nav") and n.ident == step["nav"]:
            return n
        if step.get("ident") and n.ident == step["ident"]:
            return n
    if step.get("nav"):
        return None
    for n in live:
        if step.get("label") and _masked(n.label) == _masked(step["label"]) and n.type == step.get("type", n.type):
            return n
    if step.get("pat"):
        pat = label_pattern(step["pat"])
        for n in live:
            if n.label and pat.fullmatch(_norm(n.label)):
                return n
    if catalogue is not None and step.get("intent") and step.get("screen"):
        for n in live:
            it = catalogue.lookup(step["screen"], n.ident, n.label)
            if it is not None and it.name == step["intent"]:
                return n
    if step.get("row") and catalogue is not None:
        for n in live:
            if n.ident.startswith("ami.nav.") or (claimed and n.ident in claimed):
                continue
            if n.label.lower() in _BACK_LABELS or n.ident.endswith((".back", ".close")):
                continue
            if catalogue.lookup(step.get("screen", ""), n.ident, n.label) is None and n.cy > 120:
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
        self.limits = C.load_spend_limits()
        self.spend_used: dict[str, int] = {}
        self.unreach_reason: dict[str, str] = {}
        self.route_log: list[str] = []

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

    def _m(self, nodes, step: dict):
        return _match(nodes, step, self.catalogue)

    def _await(self, to: str, timeout: float = 7.0) -> bool:
        """Wait for a surface root id (`ami.screen.*`) rather than a fingerprint:
        the id appears when the route has actually finished building."""
        deadline = time.monotonic() + timeout
        while True:
            snap = self._observe()
            if snap.key == to or to in {n.ident for n in snap.nodes if n.visible}:
                return True
            if self.catalogue is not None and _surface_present(to, snap, self.catalogue) and not to.startswith(C.SCREEN_PREFIX):
                return True
            if time.monotonic() > deadline:
                return False
            time.sleep(0.6)

    def _reveal(self, step: dict) -> C.Node | None:
        snap = self._observe()
        n = self._m(snap.nodes, step)
        if n and self._visible_controls(snap).count(n):
            return n
        from pages.base_page import content_band
        band = content_band(self.geom)
        for _ in range(3):
            self._swipe_down_content()
            n = self._m(self._observe().nodes, step)
            if n and n in self._visible_controls(self.snap):
                return n
        for _ in range(6):
            swipe_up(self.driver, band)
            n = self._m(self._observe().nodes, step)
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
        self._await_shell()

    def _await_shell(self, timeout: float = 30.0) -> None:
        """A cold start takes several seconds before the tab bar is in the tree;
        relaunching again before then (the old behaviour) restarts the clock
        forever. Wait for it, answering the one-off 'Not now' soft ask."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            snap = self._observe()
            if any(n.ident.startswith("ami.nav.") and n.visible for n in snap.nodes):
                return
            for n in snap.nodes:
                if n.interactive and n.visible and n.label.lower() in _OPTIONAL_STEPS:
                    self._tap(n)
                    break
            else:
                time.sleep(1.0)

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
            # A tab remembers its last pane (portfolio.orders vs portfolio.positions):
            # any id in the tab's own family means the tab root is showing.
            fam = R.NAV_TO_ROOTS.get(nav, ())
            if any(n.visible and n.ident.startswith(f) for n in snap.nodes for f in fam):
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
                if (step.get("label") or "").lower() in _OPTIONAL_STEPS:
                    continue
                raise ReplayFailed(f"step {_step_name(step)!r} not found")
            self._tap(n)
            to = step.get("to", "")
            if to.startswith(C.SCREEN_PREFIX):
                if not self._await(to, 7.0 if step.get("strict") else 4.0) and step.get("strict"):
                    raise ReplayFailed(f"step {_step_name(step)!r} pressed but {to} did not appear")
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

    def _visit(self, path: list[dict], depth: int, parent_key: str | None, queue: deque,
               *, already_there: bool = False) -> None:
        try:
            if already_there:
                self._observe()
            else:
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
        for n in snap.nodes:  # a pane's host screen (portfolio under portfolio.positions) is on screen too
            if n.ident.startswith(C.SCREEN_PREFIX) and n.visible and n.ident not in self.cov.screens \
                    and n.ident in self.cov.expected:
                self.cov.see_screen(n.ident, path=[_step_name(x) for x in path] + [f"(host of {key})"])
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
                if cls not in ("destructive", "unlabelled") and self._spend_blocked(key, n, ctl):
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
            self._spend_count(key, node)
            started = time.monotonic()
            before = snap
            after = self._press(ctl, node, before, parent_prev)
            if after.key != key or after.sheets != before.sheets:
                child_key = after.key
                it = self.catalogue.lookup(key, node.ident, node.label) if self.catalogue is not None else None
                step = _step(node, to=child_key if child_key.startswith(C.SCREEN_PREFIX) else "",
                             screen=key, intent=it.name if it else "")
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

    def _spend_group(self, screen: str, node: C.Node) -> str | None:
        it = self.catalogue.lookup(screen, node.ident, node.label) if self.catalogue is not None else None
        return C.spend_group(self.limits, screen, node, it.expect if it else None,
                             it.label if it else "", it.target if it else "")

    def _spend_blocked(self, screen: str, node: C.Node, ctl: C.Control) -> bool:
        """Once a spend group's per-crawl limit is used, further presses are
        exempt (the intent is still catalogue-checked on the first one)."""
        g = self._spend_group(screen, node)
        if g and self.spend_used.get(g, 0) >= int(self.limits[g].get("limit", 1)):
            self.cov.exempt(ctl, f"covered by intent, not pressed: {g} budget used ({self.limits[g].get('why', '')})")
            return True
        return False

    def _spend_count(self, screen: str, node: C.Node) -> None:
        g = self._spend_group(screen, node)
        if g:
            self.spend_used[g] = self.spend_used.get(g, 0) + 1

    def _scroll_down(self, band, key: str) -> bool:
        before = {C.control_id(key, n) for n in self._visible_controls(self.snap)}
        before_sig = self.snap.sig
        swipe_up(self.driver, band)
        time.sleep(0.4)
        after = self._observe()
        now = {C.control_id(key, n) for n in self._visible_controls(after)}
        return after.key == key and bool(now - before) and after.sig != before_sig

    # -- the whole crawl ---------------------------------------------------

    def _drain(self, queue: deque) -> None:
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

    def run(self, targets: list[str] | None = None) -> None:
        for f in self._sink_new():
            self.screen_findings.append({**f, "screen": "(before the crawl: install / onboarding)"})
        queue: deque = deque(([{"nav": nav}], 0, None) for nav in self.nav_ids.values())
        if targets:
            queue.clear()
        self._drain(queue)
        self._route_phase(queue, targets)
        self._press_deferred()

    # -- route-driving (catalogue graph) -------------------------------------

    def _route_phase(self, queue: deque, targets: list[str] | None = None) -> None:
        """Reach every known screen the press-everything pass missed, by
        replaying the cheapest catalogue path to it (id-awaited at each step)."""
        if self.catalogue is None or not len(self.catalogue):
            return
        graph = R.build_graph(self.catalogue)
        failed: dict[str, str] = {}
        tried: set[str] = set()
        for _round in range(3):
            todo = [t for t in (targets or self.cov.unreached_screens())
                    if t not in self.cov.screens and t not in tried]
            if not todo or self._over_cap():
                break
            for target in todo:
                if self._over_cap():
                    break
                tried.add(target)
                self._route_to(graph, target, failed, queue)
                self._drain(queue)
        for t in self.cov.unreached_screens():
            if t not in self.cov.screens:
                self.unreach_reason[t] = R.explain_unreachable(graph, t, failed=failed)
        self.cov.reasons.update(self.unreach_reason)

    def _route_to(self, graph, target: str, failed: dict[str, str], queue: deque) -> bool:
        banned: set[str] = set()
        for _attempt in range(3):
            live_roots = {scr: nav for scr, nav in R.roots().items() if nav in self.nav_set}
            planned = R.plan(graph, target, banned=frozenset(banned), start_roots=live_roots)
            if planned is None:
                return False
            nav, edges = planned
            path = R.path_steps(nav, edges)
            label = " > ".join(_step_name(s) for s in path)
            try:
                self._goto(path)
            except ReplayFailed as exc:
                bad = next((e for e in edges if e.control in str(exc) or (e.ident and e.ident in str(exc))),
                           edges[-1] if edges else None)
                if bad is not None:
                    banned.add(bad.key)
                    failed[bad.key] = str(exc)
                self.route_log.append(f"{target}: {label} FAILED ({str(exc)[:100]})")
                continue
            if self.snap.key != target and not _surface_present(target, self.snap, self.catalogue):
                failed[edges[-1].key] = f"arrived at {self.snap.key}, not {target}"
                banned.add(edges[-1].key)
                self.route_log.append(f"{target}: {label} landed on {self.snap.key}")
                continue
            self.route_log.append(f"{target}: {label} OK")
            self._visit(path, len(path), None, queue, already_there=True)
            return True
        return False

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
                if self._spend_blocked(parent, node, ctl):
                    continue
                self._spend_count(parent, node)
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
