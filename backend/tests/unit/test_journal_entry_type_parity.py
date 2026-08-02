"""Guard against backend↔Dart enum drift on the Journal (DEF210).

`EntryType` gained `daily_challenge` on 2026-05-22 (e5fbfc6e). The Flutter
enum did not, and nothing noticed for ten weeks: the app's `switch`
statements over `JournalEntryType` are exhaustive, but exhaustiveness only
fires when the *Dart* enum changes, and it never did. Adding a member
server-side is invisible to `dart analyze`.

What made the drift harmful rather than merely incomplete was the coercion
in `JournalEntry.fromJson` — `fromWire(...) ?? JournalEntryType.oneOnOne`.
An unknown wire value did not fall through to the generic payload renderer;
it *impersonated* a 1-on-1, whose branch reads `user_message` /
`assistant_reply`. Neither key exists on a daily-challenge payload, so the
body rendered blank while the card confidently read "1-ON-1" — and the
server-side type filter disagreed with the label it had just drawn.

This test enforces both halves: the value sets must match, and the model
must not re-arm the coercion. A new EntryType member now fails here, at
`pytest`, instead of shipping dark.

Adding a member? Add it to the Dart enum, its `wire` getter, its `fromWire`
switch, and both `switch`es in journal_screen.dart. This test checks the
first three; the Dart compiler checks the fourth.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.schemas.journal import EntryType

_REPO_ROOT = Path(__file__).resolve().parents[3]
_JOURNAL_DART = _REPO_ROOT / "mobile" / "lib" / "models" / "journal.dart"


def _dart_source() -> str:
    assert _JOURNAL_DART.is_file(), f"missing Dart model: {_JOURNAL_DART}"
    return _JOURNAL_DART.read_text(encoding="utf-8")


def _block(src: str, header: str) -> str:
    """The brace-balanced body of the declaration starting at `header`."""
    start = src.index(header)
    depth, i = 0, src.index("{", start)
    for j in range(i, len(src)):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[i : j + 1]
    raise AssertionError(f"unbalanced braces after {header!r}")


def test_from_wire_accepts_every_backend_entry_type():
    body = _block(_dart_source(), "static JournalEntryType? fromWire(")
    handled = set(re.findall(r"case '([a-z_]+)':", body))
    backend = {e.value for e in EntryType}

    missing = backend - handled
    assert not missing, (
        f"EntryType members the Flutter app cannot parse: {sorted(missing)}. "
        f"Add them to JournalEntryType + wire + fromWire in {_JOURNAL_DART.name}."
    )


def test_dart_declares_no_wire_value_the_backend_does_not_send():
    body = _block(_dart_source(), "String get wire {")
    emitted = set(re.findall(r"return '([a-z_]+)';", body))
    backend = {e.value for e in EntryType}

    extra = emitted - backend
    assert not extra, (
        f"Flutter emits entry_type values the backend rejects: {sorted(extra)}. "
        "The filter query sends these verbatim; the API would 422."
    )


def test_unknown_entry_type_is_not_coerced_to_a_known_member():
    """The DEF210 trap itself: a `??` default here mislabels silently.

    Unknown must stay null so the UI falls through to its generic branch —
    CR040, degrade loudly. Rendering a wrong-but-known type is worse than
    rendering an unknown one, because nothing downstream can tell.
    """
    src = _dart_source()
    coercion = re.search(r"fromWire\([^)]*\)\s*\?\?", src)
    assert coercion is None, (
        "JournalEntry.fromJson coerces an unrecognised entry_type to a known "
        "member. That is exactly DEF210: the entry renders as the wrong type "
        "with a blank body. Leave it null."
    )
