"""Glue for one exhaustive crawl (CR264): used by `crawler.run --exhaustive` and
by `tests/test_every_control.py` so the CLI and the UAT gate run the same thing.

Builds the session, onboards, wires the oracles / error sink / reset callback
into `ExhaustiveCrawler`, then writes `control_coverage.json` + `coverage.md` +
`findings.json` and returns the outcome with the list of gate failures.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from config import semantics_ids
from config.devices import IOS
from config.semantics_ids import NAV_IDS
from crawler import controls as C
from crawler.errorsink import SinkUnavailable, ios_sink_path, read_sink
from crawler.exhaustive import ExhaustiveCrawler, Fatal
from crawler.intents import Catalogue, load_dir
from crawler.ledger import Ledger
from crawler.oracles import screen_oracles
from helpers import device as device_helpers
from helpers.driver_factory import new_driver
from helpers.gestures import screen_scale
from helpers.onboarding import ensure_onboarded

REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass
class Outcome:
    coverage: C.Coverage
    findings: list[dict] = field(default_factory=list)
    gate_failures: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    runtime_s: float = 0.0


def _app_path() -> str | None:
    env = os.environ.get("AMI_IOS_APP")
    if env:
        return env
    p = REPO_ROOT / "mobile" / "build" / "ios" / "iphonesimulator" / "Runner.app"
    return str(p) if p.exists() else None


def run_exhaustive(profile, out: Path, *, per_screen_s: float = 90.0, global_cap_s: float = 5400.0,
                   depth: int = 6, driver=None, catalogue: Catalogue | None = None,
                   use_ledger: bool = True, log=print) -> Outcome:
    out.mkdir(parents=True, exist_ok=True)
    (out / "screenshots").mkdir(exist_ok=True)
    t0 = time.monotonic()
    notes: list[str] = []
    own_driver = driver is None
    if own_driver:
        driver = new_driver(profile)
    holder = {"driver": driver}

    if catalogue is None:
        catalogue = load_dir()
    if not len(catalogue):
        notes.append("control catalogue is EMPTY (qa/uat/controls/*.yaml): every control will read as unexplained")

    try:
        try:
            ensure_onboarded(driver)
        except Exception as exc:
            notes.append(f"could not reach the shell ({exc}); crawl covers the pre-shell surface only")
        window = driver.get_window_size()
        bottom_y, _ = device_helpers.obstructed_bottom_y(profile, display_height=int(window["height"]))
        geom = {"display": (int(window["width"]), int(window["height"])), "navbar_top_y": bottom_y,
                "scale": screen_scale(driver), "platform": profile.platform}

        sink_reader = None
        sink_unavailable = ""
        if profile.platform == IOS:
            sink_path = ios_sink_path(profile.serial, profile.bundle_id)
            try:
                read_sink(sink_path)
                sink_reader = lambda: read_sink(sink_path)  # noqa: E731
            except SinkUnavailable as exc:
                sink_unavailable = f"error sink unreadable: {exc}"
        else:
            sink_unavailable = "error sink not readable on Android yet (release builds are not debuggable)"
        if sink_unavailable:
            notes.append(sink_unavailable)

        def oracles(drv, key, labels):
            return screen_oracles(key, labels, drv, geom)

        def fresh():
            try:
                holder["driver"].quit()
            except Exception:
                pass
            device_helpers.reset_app(profile)
            if profile.platform == IOS:
                app = _app_path()
                if not app:
                    raise Fatal("cannot reinstall the iOS app after reset: set AMI_IOS_APP")
                device_helpers.install_app(profile, app)
            drv = new_driver(profile)
            holder["driver"] = drv
            ensure_onboarded(drv)
            crawler.driver = drv
            return drv

        cov = C.Coverage(C.expected_screens_from(semantics_ids))
        crawler = ExhaustiveCrawler(
            driver, profile, geom, out, coverage=cov, nav_ids=NAV_IDS, catalogue=catalogue,
            per_screen_s=per_screen_s, global_cap_s=global_cap_s, max_depth=depth,
            sink_reader=sink_reader, screen_oracles=oracles, fresh_session=fresh, log=log)
        try:
            crawler.run()
        except Fatal as exc:
            notes.append(f"FATAL: {exc}")
        notes += crawler.notes
        findings = crawler.screen_findings
        if catalogue is not None and len(catalogue):
            seen = {(c.screen, (c.ident or c.label).lower()) for c in cov.controls.values()}
            missed = [e for e in catalogue.unseen(seen) if e.screen in cov.screens]
            if missed:
                notes.append(f"{len(missed)} catalogued control(s) on reached screens were never met: "
                             + ", ".join(f"{e.screen}#{e.name}" for e in missed[:20]))
    finally:
        if own_driver:
            try:
                holder["driver"].quit()
            except Exception:
                pass

    ledger = Ledger()
    fresh_f, known = (findings, []) if not use_ledger else ledger.split(findings)
    runtime = time.monotonic() - t0
    cov.write(out, runtime_s=runtime, notes=notes)
    (out / "findings.json").write_text(json.dumps({"new": fresh_f, "known": len(known)}, indent=2) + "\n")
    failures = cov.gate_failures([
        f"{f.get('check') or f.get('rule')} on {f.get('screen', '?')}: {f.get('detail') or f.get('element_label', '')}"
        + (f" [{f['screenshot']}]" if f.get("screenshot") else "")
        for f in fresh_f
    ])
    if profile.platform == IOS and sink_unavailable:
        failures.append(sink_unavailable)
    failures += [n for n in notes if n.startswith("FATAL") or n.startswith("could not reach the shell")
                 or n.startswith("control catalogue is EMPTY")]
    return Outcome(cov, fresh_f, failures, notes, runtime)
