"""Read the errors the app recorded about itself (CR163).

Replaces an earlier `logcapture.py` that streamed the device log. That approach
was **disproven by measurement**, and the measurement is worth keeping because
it is the kind of thing that otherwise gets rediscovered: a `simctl spawn log
stream` capture of a live Runner process, taken while the app was calling
`debugPrint`, returned **5,685 lines and zero Dart-origin entries** (2026-08-10).
Every apparent "flutter" hit was a CFBundle resource lookup. Dart stdout/stderr
goes to the process's own stdout; `os_log` never sees it, and `flutter run`
only shows it because that command holds the pipe.

So the app records its own errors instead — `mobile/lib/qa/error_sink.dart`,
installed behind `--dart-define=AMI_QA_SEMANTICS=1` — and this reads them back.

Same shape on Android: read the file out of the app's data directory. That is
why the parse is kept separate from the fetch.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

SINK_FILENAME = "ami_qa_errors.jsonl"


class SinkUnavailable(RuntimeError):
    """The sink file could not be located or read.

    A hard failure on purpose. If this were treated as "no errors", every crawl
    against a mis-built app would report a clean bill of health — the exact
    silent-degradation failure this project's conventions forbid. A crawl that
    cannot read the sink has not tested error reporting at all, and must say so.
    """


def ios_sink_path(udid: str, bundle_id: str) -> Path:
    """Resolve `<app data container>/Documents/ami_qa_errors.jsonl`."""
    result = subprocess.run(
        ["xcrun", "simctl", "get_app_container", udid, bundle_id, "data"],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        raise SinkUnavailable(
            f"could not resolve the app data container for {bundle_id} on {udid}: "
            f"{result.stderr.strip()}. Is the app installed and has it been launched "
            f"at least once?"
        )
    return Path(result.stdout.strip()) / "Documents" / SINK_FILENAME


def read_sink(path: Path) -> list[dict]:
    if not path.exists():
        raise SinkUnavailable(
            f"{path} does not exist. The build under test was almost certainly made "
            f"WITHOUT --dart-define=AMI_QA_SEMANTICS=1, so QaErrorSink never "
            f"installed. Rebuild with scripts/build_qa_ios_sim.sh. Treating this as "
            f"'no errors found' would report a broken run as a clean one."
        )
    return parse_sink(path.read_text(errors="replace"))


def parse_sink(text: str) -> list[dict]:
    """JSONL -> findings. Tolerates a truncated final line: the app may be
    killed mid-write, and losing one record is much better than losing the run."""
    findings: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        findings.append(_to_finding(record))
    return findings


# Recognised Flutter error shapes, mapped to a rule id + why it matters. The
# match is on the message the framework produced, so it is stable across our own
# refactors. Unrecognised errors are still reported — as `flutter_error`, with
# the message intact — because an unfamiliar error is more interesting than a
# familiar one, not less.
_SIGNATURES: tuple[tuple[str, str, str, str], ...] = (
    ("overflowed by", "render_overflow", "high",
     "content is being clipped — the classic small-screen / long-translation defect"),
    ("setState() called after dispose()", "setstate_after_dispose", "high",
     "a callback outlived its widget, usually an un-cancelled future or stream"),
    ("Null check operator used on a null value", "null_check_operator", "high",
     "a `!` assertion failed at runtime"),
    ("LateInitializationError", "late_not_initialized", "high",
     "a `late` field was read before it was assigned"),
    ("Failed assertion", "failed_assertion", "high",
     "a framework or app assertion tripped"),
    ("Unable to load asset", "missing_asset", "medium",
     "a referenced asset is not in the build"),
    ("No Material widget found", "missing_ancestor", "medium",
     "a widget was used outside the ancestor it requires"),
    ("A RenderFlex overflowed", "render_overflow", "high",
     "content is being clipped"),
    ("RenderBox was not laid out", "layout_error", "high",
     "a layout constraint violation — usually an unbounded height/width"),
)


def _to_finding(record: dict) -> dict:
    message = str(record.get("message", ""))
    rule, severity, note = "flutter_error", "high", (
        "the app reported a Flutter error. Not in this tool's known-signature "
        "list, which makes it more interesting than a familiar one, not less."
    )
    for needle, rule_id, sev, why in _SIGNATURES:
        if needle.lower() in message.lower():
            rule, severity, note = rule_id, sev, why
            break

    return {
        "rule": rule,
        # `screen` is intentionally absent: the sink has no notion of which
        # screen was up. The crawl path in report.md is how a reviewer locates
        # it, and the ledger fingerprints these on rule+message so the same
        # error is one finding however many screens provoked it.
        "severity": severity,
        "detail": message[:160],
        "note": note,
        "kind": record.get("kind"),
        "library": record.get("library"),
        "sample": (record.get("full") or message)[:400],
        "stack": (record.get("stack") or "")[:600],
        "suggested_category": "mobile",
    }
