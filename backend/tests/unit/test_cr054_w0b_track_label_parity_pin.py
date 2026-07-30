"""AUDITOR pin (CR054-W0b round 1) — blind adversarial probe on the lane's
riskiest dimension: silent key drift between the backend track taxonomy
(`TRACK_TITLES` in backend/app/services/lessons_service.py) and the mobile
short-label map (`_trackShortLabel` in
mobile/lib/screens/lessons/track_lessons_screen.dart).

A drifted or misspelled key never crashes: TrackLessonsScreen falls back to
`trackId.toUpperCase()` (track_lessons_screen.dart:44), so the user silently
sees a raw enum heading — exactly the outcome W0b exists to prevent. No
in-repo test compared the two files across the language boundary, so this pin
parses BOTH as text (no Flutter toolchain, no backend import — stdlib only)
and asserts:

  1. dart keys == backend TRACK_TITLES keys (set equality, both directions);
  2. the 4 CR054 Wave-0 tracks are present on both sides with the audited
     labels (ASSET CLASSES / ECONOMICS / QUANT / ETHICS);
  3. labels are non-empty, unique, and contain no lowercase letters (heading
     style holds — every existing label is upper-case display copy).

Run: python3 -m pytest "orchestration/audit/regression/test_cr054_w0b_track_label_parity_pin.py" -q
(from repo root; pure text parse, works on any checkout.)
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DART_FILE = REPO_ROOT / "mobile/lib/screens/lessons/track_lessons_screen.dart"
BACKEND_FILE = REPO_ROOT / "backend/app/services/lessons_service.py"

EXPECTED_NEW = {
    "asset_classes": "ASSET CLASSES",
    "economics_macro": "ECONOMICS",
    "quant_methods": "QUANT",
    "ethics_integrity": "ETHICS",
}


def dart_short_labels(path: Path) -> dict[str, str]:
    src = path.read_text(encoding="utf-8")
    block = re.search(
        r"const _trackShortLabel = \{(?P<body>.*?)\};", src, re.DOTALL
    )
    assert block, f"_trackShortLabel map not found in {path}"
    return dict(
        re.findall(r"'([a-z_]+)':\s*'([^']+)'", block.group("body"))
    )


def backend_track_titles(path: Path) -> dict[str, str]:
    src = path.read_text(encoding="utf-8")
    block = re.search(r"TRACK_TITLES = \{(?P<body>.*?)\}", src, re.DOTALL)
    assert block, f"TRACK_TITLES not found in {path}"
    return dict(
        re.findall(r'"([a-z_]+)":\s*"([^"]+)"', block.group("body"))
    )


def test_dart_keys_match_backend_track_titles_exactly() -> None:
    dart = dart_short_labels(DART_FILE)
    backend = backend_track_titles(BACKEND_FILE)
    missing_on_mobile = set(backend) - set(dart)
    stray_on_mobile = set(dart) - set(backend)
    assert not missing_on_mobile, (
        f"backend tracks with NO mobile short label (would render as raw "
        f"uppercased enum via the line-44 fallback): {sorted(missing_on_mobile)}"
    )
    assert not stray_on_mobile, (
        f"mobile short-label keys unknown to the backend taxonomy (dead "
        f"entries / typos): {sorted(stray_on_mobile)}"
    )


def test_cr054_wave0_tracks_present_with_audited_labels() -> None:
    dart = dart_short_labels(DART_FILE)
    backend = backend_track_titles(BACKEND_FILE)
    for track, label in EXPECTED_NEW.items():
        assert track in backend, f"{track} missing from backend TRACK_TITLES"
        assert dart.get(track) == label, (
            f"{track}: expected short label {label!r}, got {dart.get(track)!r}"
        )


def test_labels_are_uppercase_unique_display_copy() -> None:
    dart = dart_short_labels(DART_FILE)
    assert len(dart) == len(set(dart.values())), (
        f"duplicate short labels would make two tracks indistinguishable: "
        f"{sorted(dart.values())}"
    )
    for track, label in dart.items():
        assert label.strip(), f"{track}: empty short label"
        assert not any(c.islower() for c in label), (
            f"{track}: label {label!r} breaks the all-caps heading style"
        )
