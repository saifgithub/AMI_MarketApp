"""Backend↔Dart parity for the notification `type` vocabulary (CR135, DEF210 class).

`NOTIFICATION_TYPES` in `app/schemas/notifications.py` is the canonical
vocabulary; `mobile/lib/models/app_notification.dart` mirrors it as
`NotificationType`. The Dart enum keys the preference toggles' labels and
any typed branching in the centre — a backend type the Dart enum lacks
renders by its raw wire name (honest but unlabelled), and a Dart member the
backend never sends is dead UI. Same failure class as DEF210's ten-week
journal drift: adding a member server-side is invisible to `dart analyze`,
so pytest is where the drift must fail.

Shipped WITH the enum, not after it (CR135 lane brief), in the shape of
`test_journal_entry_type_parity.py`. Adding a type? Add it to
NOTIFICATION_TYPES, the Dart enum + `wire` + `fromWire`, and a label key in
`notificationTypeLabel` (the Dart compiler's exhaustive switch forces the
label once the member exists).
"""

from __future__ import annotations

import re
from pathlib import Path

from app.schemas.notifications import NOTIFICATION_TYPES

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DART_MODEL = _REPO_ROOT / "mobile" / "lib" / "models" / "app_notification.dart"


def _dart_source() -> str:
    assert _DART_MODEL.is_file(), f"missing Dart model: {_DART_MODEL}"
    return _DART_MODEL.read_text(encoding="utf-8")


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


def test_from_wire_accepts_every_backend_notification_type():
    body = _block(_dart_source(), "static NotificationType? fromWire(")
    handled = set(re.findall(r"case '([a-z_]+)':", body))
    backend = set(NOTIFICATION_TYPES)

    missing = backend - handled
    assert not missing, (
        f"NOTIFICATION_TYPES the Flutter app cannot parse: {sorted(missing)}. "
        f"Add them to NotificationType + wire + fromWire in {_DART_MODEL.name} "
        "and a label to notificationTypeLabel."
    )


def test_dart_declares_no_wire_value_the_backend_does_not_send():
    body = _block(_dart_source(), "String get wire {")
    emitted = set(re.findall(r"return '([a-z_]+)';", body))
    backend = set(NOTIFICATION_TYPES)

    extra = emitted - backend
    assert not extra, (
        f"Flutter declares notification types the backend never emits: "
        f"{sorted(extra)}. A preference PATCH naming one would 422."
    )


def test_wire_getter_covers_every_backend_type():
    # `fromWire` parity alone would pass if a member existed with a case but
    # no wire mapping got updated on a rename; the getter is the other half.
    body = _block(_dart_source(), "String get wire {")
    emitted = set(re.findall(r"return '([a-z_]+)';", body))
    missing = set(NOTIFICATION_TYPES) - emitted
    assert not missing, (
        f"NotificationType.wire emits no value for: {sorted(missing)}."
    )
