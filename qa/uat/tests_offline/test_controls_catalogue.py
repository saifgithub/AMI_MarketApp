"""Offline guards for the control-intent catalogue (CR264 Phase D).

`qa/uat/controls/<surface>.yaml` states what every tappable control is
supposed to do; the exhaustive crawler asserts it. A catalogue whose targets
point at surfaces nobody described is a script that cannot be checked — the
crawler would have no root id to wait for and no controls to press there.
"""

from __future__ import annotations

from pathlib import Path

import yaml

CONTROLS_DIR = Path(__file__).resolve().parents[1] / "controls"
KINDS = {"button", "icon", "chip", "toggle", "tab", "menu_item", "list_row", "link", "field"}
EXPECTS = {"navigate", "sheet", "dialog", "state", "external", "back", "destructive", "none"}
NEEDS_TARGET = {"navigate", "sheet", "dialog"}
NEEDS_NOTE = {"destructive", "none"}
# A control whose destination is decided at runtime (e.g. a notification's
# deep link) says so explicitly instead of naming a surface.
DYNAMIC = "dynamic"


def _load() -> dict[str, dict]:
    out = {}
    for path in sorted(CONTROLS_DIR.glob("*.yaml")):
        out[path.name] = yaml.safe_load(path.read_text())
    return out


def test_catalogue_exists():
    assert _load(), "qa/uat/controls/ is empty"


def test_every_entry_is_well_formed():
    bad = []
    for name, doc in _load().items():
        if not isinstance(doc, dict) or not str(doc.get("screen", "")).startswith("ami.screen."):
            bad.append(f"{name}: needs `screen: ami.screen.<name>`")
            continue
        if not doc.get("source"):
            bad.append(f"{name}: needs `source:`")
        for i, c in enumerate(doc.get("controls") or [], 1):
            where = f"{name} #{i} ({c.get('label') or c.get('id')})"
            if not (c.get("label") or c.get("id")):
                bad.append(f"{where}: needs label or id")
            if c.get("kind") not in KINDS:
                bad.append(f"{where}: kind {c.get('kind')!r} not in {sorted(KINDS)}")
            if c.get("expect") not in EXPECTS:
                bad.append(f"{where}: expect {c.get('expect')!r} not in {sorted(EXPECTS)}")
            if c.get("expect") in NEEDS_TARGET and not c.get("target"):
                bad.append(f"{where}: expect {c.get('expect')} needs a target")
            if c.get("expect") in NEEDS_NOTE and not c.get("note"):
                bad.append(f"{where}: expect {c.get('expect')} needs a note saying why/what")
            if not isinstance(c.get("line"), int):
                bad.append(f"{where}: needs an integer source line")
    assert not bad, "\n".join(bad)


def test_one_file_per_surface():
    seen: dict[str, str] = {}
    dup = []
    for name, doc in _load().items():
        s = doc.get("screen")
        if s in seen:
            dup.append(f"{s}: {seen[s]} and {name}")
        seen[s] = name
    assert not dup, "\n".join(dup)


def test_every_target_is_a_described_surface():
    docs = _load()
    surfaces = {d.get("screen") for d in docs.values()}
    dangling = sorted({
        f"{c['target']}  (from {name})"
        for name, d in docs.items() for c in d.get("controls") or []
        if c.get("target") and c["target"] != DYNAMIC and c["target"] not in surfaces
    })
    assert not dangling, (
        "targets with no qa/uat/controls/ file — describe the surface (its root id "
        "and its own controls) or use `target: dynamic` with a note:\n" + "\n".join(dangling)
    )
