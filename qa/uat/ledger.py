"""The UAT run ledger (CR263): which case passed, on what, at which fingerprint.

A case's fingerprint hashes three things: the case itself, the test functions
that cite it (plus their file's shared helpers/fixtures), and every source file
its area `covers:`. Change any of them and the
old pass no longer counts — the release gate (`scripts/uat/uat_gate.py`) then
demands a fresh run. That is how "the added/updated tests must have been run"
is enforced structurally rather than by memory.

The ledger lives in git-ignored `.deliveryos/uat_ledger.json` on the Mac —
every release activity (promote-to-alpha, TestFlight, Play) runs from here, as
does the nightly run. Only `record` writes it.

    python qa/uat/ledger.py record <results.json>
    python qa/uat/ledger.py pending --target api|ios|android   # ids needing a run
"""

from __future__ import annotations

import ast
import fnmatch
import functools
import hashlib
import json
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import catalogue  # noqa: E402

REPO_ROOT = catalogue.REPO_ROOT
LEDGER_PATH = REPO_ROOT / ".deliveryos" / "uat_ledger.json"
TARGETS = ("api", "ios", "android")
PASSING = ("passed", "xfailed")


def _covered_files(area: catalogue.Area) -> list[Path]:
    tracked = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files"], capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    return [REPO_ROOT / f for f in tracked if any(fnmatch.fnmatch(f, g) for g in area.covers)]


def _hash_file(h, path: Path) -> None:
    h.update(path.relative_to(REPO_ROOT).as_posix().encode())
    h.update(b"\0")
    try:
        h.update(path.read_bytes())
    except OSError:
        h.update(b"<missing>")
    h.update(b"\0")


@functools.lru_cache(maxsize=None)
def _test_file_parts(path: Path) -> tuple[str, dict[str, str]]:
    """Split a test file into its shared code (imports, helpers, fixtures —
    everything that is not a top-level test function) and, per case id, the
    source of the test functions citing it. A case's fingerprint takes the
    shared code plus only its own tests, so editing one test does not force a
    re-run of every case in the file."""
    text = path.read_text()
    lines = text.splitlines(keepends=True)
    own: dict[str, list[str]] = {}
    cut: list[tuple[int, int]] = []
    for node in ast.parse(text).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
            start = min([d.lineno for d in node.decorator_list] + [node.lineno]) - 1
            segment = "".join(lines[start:node.end_lineno])
            cut.append((start, node.end_lineno))
            for m in catalogue._CITE_RE.finditer(segment):
                for cid in catalogue._CITED_ID_RE.findall(m.group(1)):
                    own.setdefault(cid, []).append(segment)
    keep = [ln for i, ln in enumerate(lines) if not any(a <= i < b for a, b in cut)]
    return "".join(keep), {cid: "\0".join(segs) for cid, segs in own.items()}


def _hash_test(h, path: Path, case_id: str) -> None:
    shared, own = _test_file_parts(path)
    h.update(path.relative_to(REPO_ROOT).as_posix().encode())
    h.update(b"\0")
    h.update(shared.encode())
    h.update(b"\0")
    h.update(own.get(case_id, "").encode())
    h.update(b"\0")


def fingerprints() -> dict[str, str]:
    """case id -> fingerprint, for every case in the catalogue."""
    areas = catalogue.load()
    cites = {layer: catalogue.citations(layer) for layer in catalogue.EXECUTORS}
    out = {}
    for a in areas:
        area_h = hashlib.sha256()
        for f in _covered_files(a):
            _hash_file(area_h, f)
        area_digest = area_h.hexdigest()
        for c in a.cases:
            h = hashlib.sha256()
            h.update(json.dumps(asdict(c), sort_keys=True).encode())
            h.update(area_digest.encode())
            for f in sorted(cites.get(c.layer, {}).get(c.id, [])):
                _hash_test(h, f, c.id)
            out[c.id] = h.hexdigest()
    return out


def target_layer(target: str) -> str:
    return "api" if target == "api" else "device"


def load() -> dict:
    try:
        return json.loads(LEDGER_PATH.read_text())
    except (OSError, ValueError):
        return {"cases": {}, "releases": {}}


def save(data: dict) -> None:
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = LEDGER_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
    tmp.replace(LEDGER_PATH)


def _git_sha() -> str:
    return subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()


def record(results_path: Path) -> int:
    """Fold a run's results JSON (written by the api or appium conftest) into
    the ledger. A skipped case records nothing — skipping is not evidence."""
    run = json.loads(results_path.read_text())
    target = run.get("platform") if run["layer"] == "device" else "api"
    if target not in TARGETS:
        print(f"unknown target in {results_path}: {target!r}")
        return 2
    fps = fingerprints()
    data = load()
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    sha = _git_sha()
    n = 0
    for case_id, outcome in run["results"].items():
        if outcome == "skipped" or case_id not in fps:
            continue
        data["cases"][f"{case_id}@{target}"] = {
            "outcome": outcome, "fingerprint": fps[case_id],
            "git_sha": sha, "at": stamp, "run": results_path.parent.name,
        }
        n += 1
    save(data)
    print(f"ledger: recorded {n} {target} results from {results_path}")
    return 0


def pending(target: str, include_failed: bool = True) -> list[str]:
    """Active cases for this target with no passing run at their current
    fingerprint."""
    layer = target_layer(target)
    fps = fingerprints()
    data = load()["cases"]
    out = []
    for c in catalogue.all_cases().values():
        if c.layer != layer or c.status != "active":
            continue
        if layer == "device" and c.platforms and target not in c.platforms:
            continue
        entry = data.get(f"{c.id}@{target}")
        ok = entry and entry["fingerprint"] == fps[c.id] and entry["outcome"] in PASSING
        if not ok and (include_failed or not entry or entry["fingerprint"] != fps[c.id]):
            out.append(c.id)
    return sorted(out)


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[0] == "record":
        return record(Path(argv[1]))
    if len(argv) == 3 and argv[0] == "pending" and argv[1] == "--target" and argv[2] in TARGETS:
        ids = pending(argv[2])
        if ids:
            print("\n".join(ids))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
