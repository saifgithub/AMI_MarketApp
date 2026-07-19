"""One-off: stamp a permanent group-scoped `code` into every lesson's frontmatter (CR044).

Why this exists as a script rather than a derived property: the code is *frozen*. A derived
per-track rank would renumber a whole track whenever a lesson is inserted mid-corpus,
invalidating every code already spoken, screenshotted, or written into a chat log. CR018
made the same call for `LessonMeta.number` and for the same reason. So the number is computed
once, here, and thereafter lives in the content.

Run once. Re-running is a no-op for lessons that already carry a code — it will NOT
renumber them, and it aborts if it would have to. If you are adding a new lesson, hand it the
next free number in its track; don't re-run this expecting a resequence.

    backend/.venv/bin/python scripts/assign_lesson_codes.py [--check]

--check exits non-zero instead of writing, for use as a dry run.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

CONTENT_DIR = Path(__file__).resolve().parent.parent / "content" / "lessons"

# The 7 lesson groups and their prefixes live with the track taxonomy in the backend, so
# this script and test_lesson_corpus_integrity read the same map.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from app.services.lessons_service import TRACK_PREFIX  # noqa: E402

_TRACK_RE = re.compile(r'^track:\s*"(?P<track>[^"]+)"\s*$', re.MULTILINE)
_CODE_RE = re.compile(r'^code:\s*"(?P<code>[^"]+)"\s*$', re.MULTILINE)
_ID_RE = re.compile(r'^id:\s*"(?P<id>[^"]+)"\s*$', re.MULTILINE)


def _frontmatter(text: str) -> str:
    """The frontmatter block only — so a `track:` line in prose can't be mistaken for one."""
    if not text.startswith("---\n"):
        raise ValueError("no frontmatter")
    end = text.index("\n---\n", 4)
    return text[4:end]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report only, write nothing")
    args = ap.parse_args()

    paths = sorted(CONTENT_DIR.glob("*.en.mdx"))
    if not paths:
        print(f"no lessons under {CONTENT_DIR}", file=sys.stderr)
        return 1

    by_track: dict[str, list[Path]] = defaultdict(list)
    existing: dict[str, str] = {}

    for p in paths:
        fm = _frontmatter(p.read_text(encoding="utf-8"))
        tm = _TRACK_RE.search(fm)
        if tm is None:
            print(f"FAIL {p.name}: no track in frontmatter", file=sys.stderr)
            return 1
        track = tm.group("track")
        if track not in TRACK_PREFIX:
            print(f"FAIL {p.name}: unknown track {track!r}", file=sys.stderr)
            return 1
        by_track[track].append(p)
        cm = _CODE_RE.search(fm)
        if cm is not None:
            existing[p.name] = cm.group("code")

    # Assigning in sorted-id order matches the catalogue's own within-track ordering
    # (lessons_service.catalogue sorts by meta.id), so codes read in the order the user
    # actually meets the lessons.
    planned: dict[str, str] = {}
    for track, files in by_track.items():
        for n, p in enumerate(sorted(files), start=1):
            planned[p.name] = f"{TRACK_PREFIX[track]} {n}"

    # Refuse to renumber. A code that has ever shipped is permanent; if this run would move
    # one, the corpus has been reordered and that needs a human decision, not a rewrite.
    drift = {k: (v, planned[k]) for k, v in existing.items() if planned[k] != v}
    if drift:
        print(f"ABORT — {len(drift)} lesson(s) would be renumbered:", file=sys.stderr)
        for name, (was, now) in sorted(drift.items())[:10]:
            print(f"    {name}: {was!r} -> {now!r}", file=sys.stderr)
        print(
            "\nCodes are frozen. Give new lessons the next free number in their track "
            "by hand rather than resequencing the corpus.",
            file=sys.stderr,
        )
        return 1

    todo = [p for p in paths if p.name not in existing]
    for track in TRACK_PREFIX:
        n = len(by_track.get(track, []))
        print(f"  {TRACK_PREFIX[track]:>4} {track:<22} {n:>3} lessons")
    print(f"\n{len(paths)} lessons · {len(existing)} already coded · {len(todo)} to stamp")

    if args.check:
        return 0 if not todo else 2

    for p in todo:
        text = p.read_text(encoding="utf-8")
        fm_end = text.index("\n---\n", 4)
        head, tail = text[:fm_end], text[fm_end:]
        tm = _TRACK_RE.search(head)
        assert tm is not None
        code_line = f'code: "{planned[p.name]}"'
        # Sits directly under `track:` — the code is a projection of the track, and a reader
        # scanning frontmatter should meet them together.
        head = head[: tm.end()] + "\n" + code_line + head[tm.end() :]
        p.write_text(head + tail, encoding="utf-8")

    print(f"stamped {len(todo)} lessons")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
