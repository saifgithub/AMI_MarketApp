"""Guard for DEF069 — no doubled apostrophes in the Flutter ARB files.

Flutter gen-l10n runs with `use-escaping` OFF (unset in mobile/l10n.yaml →
default false). Under that config the ICU quote character is not processed, so a
literal ``''`` in an ARB value is emitted verbatim and renders as two
apostrophes on screen (DEF069: the CR047 Winzip card showed "You''ve … AMI''s").
The correct authoring is a single ``'``.

`flutter analyze` does not catch this; pytest is the one automated gate that runs
in the promote preflight, so the guard lives here. It skips cleanly when the
mobile tree isn't present (e.g. a backend-only / mobile-excluded checkout).
"""

from __future__ import annotations

from pathlib import Path

import pytest

_L10N_DIR = Path(__file__).resolve().parents[3] / "mobile" / "lib" / "l10n"


def _arb_files() -> list[Path]:
    if not _L10N_DIR.is_dir():
        return []
    return sorted(_L10N_DIR.glob("app_*.arb"))


@pytest.mark.skipif(not _L10N_DIR.is_dir(), reason="mobile ARB tree not present")
@pytest.mark.parametrize("arb", _arb_files(), ids=lambda p: p.name)
def test_no_doubled_apostrophes_in_arb(arb: Path) -> None:
    text = arb.read_text(encoding="utf-8")
    assert "''" not in text, (
        f"{arb.name} contains a doubled apostrophe (''). With use-escaping off "
        f"this renders literally on screen (DEF069). Use a single apostrophe."
    )
