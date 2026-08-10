"""Crawler entrypoint (CR163). One run = one report.

    python3 -m crawler.run --out /tmp/crawl-1 [--budget 240] [--depth 3]

Pipeline (scripts/crawl_ios_sim.sh does the build/install before this):
    1. walk the app breadth-first, running per-screen oracles as it goes
    2. read back the errors the app recorded about itself
    3. drop anything the ledger has already triaged
    4. write findings.json + report.md + screenshots

What it deliberately does NOT do: file anything. Promotion is `tools/triage.py`,
a separate step, because CR080 lost two sessions to a harness bug being written
up as 27 application failures. A crawler that files its own findings turns one
bad run into a register full of fiction — and with an agent waiting to fix
whatever is filed, into a branch full of fixes for defects that never existed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from config.devices import IOS_SIM
from config.semantics_ids import NAV_IDS
from crawler.errorsink import SinkUnavailable, ios_sink_path, read_sink
from crawler.explorer import CrawlResult, Explorer
from crawler.ledger import Ledger
from crawler.oracles import screen_oracles
from helpers import device as device_helpers
from helpers.driver_factory import new_driver
from helpers.gestures import screen_scale
from helpers.onboarding import ensure_onboarded


def _report(fresh: list[dict], known: list[dict], result: CrawlResult, sink_error: str | None) -> str:
    lines = [
        "# Crawl report",
        "",
        f"- screens reached: **{result.screens_seen}**",
        f"- taps: **{result.taps}**",
        f"- findings: **{len(fresh)} new**, {len(known)} already triaged",
        "",
    ]

    if sink_error:
        lines += [
            "> ## ⚠ The app's error sink could not be read",
            ">",
            f"> {sink_error}",
            ">",
            "> **Every Flutter-error finding is missing from this run.** Layout findings",
            "> below are still valid; treat the absence of error findings as unknown,",
            "> not as clean.",
            "",
        ]

    if result.replay_failures:
        lines += [
            "## Branches abandoned (coverage gaps, not defects)", "",
            "The crawler could not walk back to these, so anything beyond them is unexplored:",
            "",
        ] + [f"- `{p}`" for p in result.replay_failures[:10]] + [""]

    if result.errors:
        lines += ["## Harness errors (NOT application defects)", ""]
        lines += [f"- {e}" for e in result.errors[:10]] + [""]

    if not fresh:
        lines += [
            "## No new findings", "",
            "Either the surfaces reached are clean, or the crawl did not reach far "
            "enough. Compare `screens reached` against the previous run before "
            "concluding the former.", "",
        ]
        return "\n".join(lines)

    lines += ["## New findings", ""]
    for i, f in enumerate(fresh, 1):
        rule = f.get("check") or f.get("rule")
        screen = f.get("screen")
        lines += [
            f"### {i}. `{rule}` — {f.get('severity', '?')}",
            "",
            f"- **detail:** {f.get('detail') or f.get('element_label') or '—'}",
            f"- **why it matters:** {f.get('note', '')}",
        ]
        if screen:
            path = result.screen_paths.get(screen)
            lines.append(f"- **screen:** `{screen}`")
            if path is not None:
                lines.append(f"- **how to get there:** {' → '.join(path) if path else '(tab root)'}")
        if f.get("stack"):
            lines += ["", "<details><summary>stack</summary>", "", "```", f["stack"], "```", "", "</details>"]
        elif f.get("sample"):
            lines += ["", "```", f["sample"], "```"]
        if f.get("screenshot"):
            lines.append(f"- screenshot: `{f['screenshot']}`")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Autonomously crawl the app and report defects")
    parser.add_argument("--out", type=Path, required=True, help="run directory for evidence")
    parser.add_argument("--budget", type=float, default=240.0, help="wall-clock seconds to explore")
    parser.add_argument("--depth", type=int, default=3)
    parser.add_argument("--sim-name", default="iPhone 17")
    parser.add_argument("--no-ledger", action="store_true",
                        help="report everything, including findings already triaged")
    args = parser.parse_args(argv[1:])

    run_dir: Path = args.out
    (run_dir / "screenshots").mkdir(parents=True, exist_ok=True)

    udid = device_helpers.resolve_ios_udid(args.sim_name)
    device_helpers.boot_ios(udid)
    profile = IOS_SIM.__class__(**{**IOS_SIM.__dict__, "serial": udid})

    driver = new_driver(profile)
    findings: list[dict] = []
    result = CrawlResult()
    onboarding_gap: str | None = None
    try:
        # A fresh install lands on the Concierge interview, where the bottom nav
        # does not exist yet — so every root identifier fails to resolve and the
        # crawl explores exactly nothing. The first real run did precisely that
        # and reported "screens 0", correctly but uselessly.
        #
        # A FAILED walk must not abort the crawl, though. The interview is
        # itself app surface worth exploring, and on a fresh install it is the
        # ONLY surface a user sees first — aborting here would mean the one
        # screen every user hits is the one screen never crawled. Record the
        # gap, then crawl whatever is actually on screen.
        try:
            ensure_onboarded(driver)
        except Exception as exc:
            onboarding_gap = str(exc)
            result.errors.append(
                f"could not reach the shell ({exc}) — crawling from wherever the "
                f"app is instead. Tab roots will not resolve, so this run covers "
                f"the pre-shell surface only."
            )

        window = driver.get_window_size()
        bottom_y, _measured = device_helpers.obstructed_bottom_y(
            profile, display_height=int(window["height"])
        )
        # Computed ONCE — the first version re-read window size per screen,
        # two WebDriverAgent round trips per screen for a constant.
        geom = {
            "display": (int(window["width"]), int(window["height"])),
            "navbar_top_y": bottom_y,
            "scale": screen_scale(driver),
            "platform": "ios",
        }

        def on_screen(fingerprint: str, _depth: int, labels: list[str]) -> None:
            shot = run_dir / "screenshots" / f"{fingerprint}.png"
            driver.get_screenshot_as_file(str(shot))
            for f in screen_oracles(fingerprint, labels, driver, geom):
                f["screenshot"] = str(shot.relative_to(run_dir))
                findings.append(f)

        explorer = Explorer(driver, budget_s=args.budget, max_depth=args.depth, on_screen=on_screen)
        roots = [] if onboarding_gap else list(NAV_IDS.values())
        result = explorer.crawl(roots=roots)
    finally:
        # Always quit: a leaked session wedges the next run, which is how three
        # runs in a row got attributed to the app rather than to the harness.
        try:
            driver.quit()
        except Exception:
            pass

    # Read the app's own error record AFTER the session ends, so the file is
    # complete and nothing is mid-write.
    sink_error: str | None = None
    try:
        findings.extend(read_sink(ios_sink_path(udid, profile.bundle_id)))
    except SinkUnavailable as exc:
        sink_error = str(exc)

    ledger = Ledger()
    if args.no_ledger:
        fresh, known = findings, []
    else:
        fresh, known = ledger.split(findings)
        for f in fresh:
            ledger.record(f)
        ledger.save()

    (run_dir / "findings.json").write_text(json.dumps({
        "new": fresh,
        "known": len(known),
        "screens": result.screens_seen,
        "taps": result.taps,
        "sink_error": sink_error,
    }, indent=2) + "\n")
    (run_dir / "report.md").write_text(_report(fresh, known, result, sink_error))

    print(f"\nscreens {result.screens_seen} · taps {result.taps} · "
          f"{len(fresh)} new finding(s), {len(known)} already triaged")
    if sink_error:
        print("!! error sink unreadable — Flutter-error findings are MISSING from this run")
    print(f"report: {run_dir / 'report.md'}")

    # Findings are the product, not a failure — a non-zero exit would make a
    # scheduled run look broken every time it worked. Exit 2 only when the run
    # could not do its job.
    return 2 if sink_error else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
