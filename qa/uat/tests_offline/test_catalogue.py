"""Offline guards for the UAT catalogue (CR263) — no network, no device.

1. The catalogue loads and validates.
2. `UAT_SCRIPT.md` is freshly rendered from it.
3. Parity: every active api/device case is cited by a test with
   `@pytest.mark.uat("<id>")` in the executor that owns its layer, and no test
   cites an unknown id or a manual case. A case with no executing test is a
   script line nobody runs — exactly the gap CR263 exists to close.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

UAT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = UAT_ROOT.parents[1]
sys.path.insert(0, str(UAT_ROOT))

import catalogue  # noqa: E402
import render  # noqa: E402

EXECUTORS = {
    "api": UAT_ROOT / "api",
    "device": REPO_ROOT / "qa" / "appium" / "tests",
}
_CITE_RE = re.compile(r"""mark\.uat\(\s*((?:["']UAT-[A-Z0-9]+-\d{3}["']\s*,?\s*)+)\)""")
_ID_RE = re.compile(r"UAT-[A-Z0-9]+-\d{3}")


def _cited(root: Path) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for path in sorted(root.rglob("test_*.py")):
        for m in _CITE_RE.finditer(path.read_text()):
            for case_id in _ID_RE.findall(m.group(1)):
                out.setdefault(case_id, []).append(path.name)
    return out


def test_catalogue_loads():
    areas = catalogue.load()
    assert areas, "no cases/*.yaml found"


def test_script_is_fresh():
    expected = render.render(catalogue.load())
    actual = render.SCRIPT_PATH.read_text() if render.SCRIPT_PATH.exists() else ""
    assert actual == expected, "UAT_SCRIPT.md is stale — run: python qa/uat/render.py"


def test_every_active_automated_case_has_a_test():
    cases = catalogue.all_cases()
    missing = []
    for layer, root in EXECUTORS.items():
        cited = _cited(root)
        for c in cases.values():
            if c.layer == layer and c.status == "active" and c.id not in cited:
                missing.append(f"{c.id} ({layer}) — no test in {root.relative_to(REPO_ROOT)}")
    assert not missing, "uncovered cases:\n" + "\n".join(missing)


def test_no_test_cites_an_unknown_or_wrong_layer_case():
    cases = catalogue.all_cases()
    bad = []
    for layer, root in EXECUTORS.items():
        for case_id, files in _cited(root).items():
            c = cases.get(case_id)
            if c is None:
                bad.append(f"{case_id} cited in {files} — not in the catalogue")
            elif c.layer != layer:
                bad.append(f"{case_id} is layer '{c.layer}' but cited by the {layer} executor in {files}")
    assert not bad, "\n".join(bad)


def test_validation_rejects_bad_ids(tmp_path):
    (tmp_path / "demo.yaml").write_text(
        "area: demo\ncode: DEMO\ntitle: Demo\norder: 1\ncases:\n"
        "  - id: UAT-OTHER-001\n    title: t\n    layer: api\n    steps: [s]\n    expected: [e]\n"
    )
    try:
        catalogue.load(tmp_path)
    except catalogue.CatalogueError as exc:
        assert "UAT-DEMO-NNN" in str(exc)
    else:
        raise AssertionError("mismatched id prefix was accepted")


def test_validation_requires_blocked_reason(tmp_path):
    (tmp_path / "demo.yaml").write_text(
        "area: demo\ncode: DEMO\ntitle: Demo\norder: 1\ncases:\n"
        "  - id: UAT-DEMO-001\n    title: t\n    layer: api\n    status: blocked\n"
        "    steps: [s]\n    expected: [e]\n"
    )
    try:
        catalogue.load(tmp_path)
    except catalogue.CatalogueError as exc:
        assert "blocked_on" in str(exc)
    else:
        raise AssertionError("blocked case without a reason was accepted")
