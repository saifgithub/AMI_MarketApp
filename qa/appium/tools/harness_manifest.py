"""Integrity manifest for the UAT harness (CR162, closing CR080's open guard).

## Why this exists

This harness is authored in git on the Mac and rsync'd to melehost, where a
different team runs it against the shared device. Twice, melehost's copy was
hand-edited instead:

1. A `_AutoRecoverDriver` wrapper was added to `conftest.py` that silently
   dropped failure-evidence capture for every failure.
2. `base_page.py` gained a `_dismiss_overlays()` calling
   `exists_text(..., timeout_s=1)` while the hand-edited `exists_text()` never
   got a `timeout_s` parameter. That single `TypeError` produced a report
   claiming **27 FAIL / 2 PASS**, which was written up as two harness bugs and a
   recommendation to rewrite the locator strategy around a premise that was
   already false. Zero of the 27 were app defects.

CR080 recorded the second incident as a second occurrence of the same violation
and noted that per this project's failure-patterns convention it should get a
guard, not another re-flag — but that *"No guard designed yet"*. This is that
guard.

## What it does

`write` records a SHA-256 per harness file into `MANIFEST.sha256`, committed to
git alongside the code. `verify` re-hashes and reports divergence.

Two authorities, chosen by where it runs:

- **Inside a git checkout** (the Mac), git already knows the truth, so `verify`
  defers to `git status` and stays quiet about work in progress. A manifest
  check here would fire on every uncommitted edit and be disabled within a day.
- **Outside one** (melehost's rsync'd copy), the manifest is the only
  record of what was delivered, and any modification to a delivered file is
  exactly the incident above. Fatal.

**Modified and missing files are fatal; extra files are not.** The UAT team
legitimately adds operational files on the rig — `start-appium.sh` is theirs —
and rsync deliberately runs without `--delete` so those survive. Both real
incidents were edits to delivered files, which is precisely what this catches.

## Usage

    python3 tools/harness_manifest.py write     # after changing the harness
    python3 tools/harness_manifest.py verify    # what conftest.py runs
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

HARNESS_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = HARNESS_ROOT / "MANIFEST.sha256"

# Runtime/local artefacts that are not part of the delivered harness. Report
# output and the real .env deliberately never leave the machine they're on.
_EXCLUDED_DIRS = {".venv", "__pycache__", ".pytest_cache", "_report", ".ruff_cache"}
_EXCLUDED_NAMES = {"MANIFEST.sha256", ".env"}
_INCLUDED_SUFFIXES = {".py", ".toml", ".txt", ".md", ".cfg", ".ini"}


def _harness_files() -> list[Path]:
    files = []
    for path in sorted(HARNESS_ROOT.rglob("*")):
        if not path.is_file():
            continue
        if any(part in _EXCLUDED_DIRS for part in path.parts):
            continue
        if path.name in _EXCLUDED_NAMES:
            continue
        if path.suffix not in _INCLUDED_SUFFIXES:
            continue
        files.append(path)
    return files


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _in_git_checkout() -> bool:
    try:
        result = subprocess.run(
            ["git", "-C", str(HARNESS_ROOT), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and result.stdout.strip() == "true"


def write() -> int:
    lines = [
        f"{_digest(p)}  {p.relative_to(HARNESS_ROOT).as_posix()}" for p in _harness_files()
    ]
    MANIFEST_PATH.write_text("\n".join(lines) + "\n")
    print(f"wrote {MANIFEST_PATH.name}: {len(lines)} files")
    return 0


def _load_manifest() -> dict[str, str]:
    entries = {}
    for line in MANIFEST_PATH.read_text().splitlines():
        if not line.strip():
            continue
        digest, _, rel = line.partition("  ")
        entries[rel] = digest
    return entries


def verify() -> tuple[bool, str]:
    """Return `(ok, message)`. Never raises — the caller decides how loud to be."""
    if _in_git_checkout():
        return True, "in a git checkout — git is the authority, manifest check skipped"

    if not MANIFEST_PATH.exists():
        return False, (
            f"{MANIFEST_PATH.name} is missing and this is not a git checkout, so there "
            f"is no record of what was delivered. Re-deliver the harness from git "
            f"(rsync from the Mac) rather than running this copy."
        )

    expected = _load_manifest()
    actual = {p.relative_to(HARNESS_ROOT).as_posix(): _digest(p) for p in _harness_files()}

    modified = sorted(r for r, d in expected.items() if r in actual and actual[r] != d)
    missing = sorted(r for r in expected if r not in actual)

    if not modified and not missing:
        return True, f"harness matches the delivered manifest ({len(expected)} files)"

    detail = []
    if modified:
        detail.append("MODIFIED since delivery:\n  " + "\n  ".join(modified))
    if missing:
        detail.append("MISSING since delivery:\n  " + "\n  ".join(missing))

    return False, (
        "This copy of the harness has been edited in place.\n\n"
        + "\n\n".join(detail)
        + "\n\nGit is the source of truth for qa/appium — never hand-edit the copy on "
        "melehost. This has happened twice before (CR080); the second time, one "
        "TypeError introduced by a local edit was reported as 27 application "
        "failures, none of which were real.\n\n"
        "Fix: re-deliver from the Mac (rsync from git), then re-run. If the change "
        "here is genuinely wanted, make it in git and deliver it."
    )


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else "verify"
    if command == "write":
        return write()
    if command == "verify":
        ok, message = verify()
        print(message)
        return 0 if ok else 1
    print(f"usage: {argv[0]} [write|verify]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
