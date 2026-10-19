"""The whole-app UAT catalogue (CR263): loads and validates `cases/*.yaml`.

One YAML file per feature area is the single source of truth for the UAT
script. `render.py` turns it into the human-readable `UAT_SCRIPT.md`; the API
suite (`qa/uat/api/`) and the Appium harness (`qa/appium/tests/`) execute it,
each test citing its case with `@pytest.mark.uat("UAT-<AREA>-NNN")`.

One file per area keeps parallel authors on disjoint write paths — the same
reason the CR/DEF registers are one row-file per item (CR081).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

UAT_ROOT = Path(__file__).resolve().parent
CASES_DIR = UAT_ROOT / "cases"

LAYERS = ("api", "device", "manual")
STATUSES = ("active", "blocked")
PLANS = ("anon", "floor_pass", "trial_trader", "trader", "floor_manager", "any")
ID_RE = re.compile(r"^UAT-([A-Z0-9]+)-(\d{3})$")

_AREA_KEYS = {"area", "code", "title", "order", "summary", "covers", "cases"}
_CASE_KEYS = {
    "id", "title", "layer", "plans", "preconditions", "steps", "expected",
    "status", "blocked_on", "llm", "platforms", "notes",
}
_CASE_REQUIRED = {"id", "title", "layer", "steps", "expected"}


@dataclass(frozen=True)
class Case:
    id: str
    title: str
    layer: str
    steps: tuple[str, ...]
    expected: tuple[str, ...]
    plans: tuple[str, ...] = ("any",)
    preconditions: tuple[str, ...] = ()
    status: str = "active"
    blocked_on: str = ""
    llm: bool = False
    platforms: tuple[str, ...] = ()
    notes: str = ""


@dataclass(frozen=True)
class Area:
    area: str
    code: str
    title: str
    order: int
    summary: str
    covers: tuple[str, ...] = ()
    cases: tuple[Case, ...] = field(default_factory=tuple)
    source: str = ""


class CatalogueError(ValueError):
    pass


def _tuple(value, where: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise CatalogueError(f"{where}: expected a string or list of strings")
    return tuple(value)


def _load_area(path: Path) -> Area:
    raw = yaml.safe_load(path.read_text())
    where = path.name
    if not isinstance(raw, dict):
        raise CatalogueError(f"{where}: top level must be a mapping")
    unknown = set(raw) - _AREA_KEYS
    if unknown:
        raise CatalogueError(f"{where}: unknown keys {sorted(unknown)}")
    for key in ("area", "code", "title", "order", "covers", "cases"):
        if key not in raw:
            raise CatalogueError(f"{where}: missing '{key}'")
    if raw["area"] != path.stem:
        raise CatalogueError(f"{where}: area '{raw['area']}' must match the file name")
    if not raw["covers"]:
        raise CatalogueError(f"{where}: covers must list the source globs this area tests")
    code = raw["code"]
    if not re.fullmatch(r"[A-Z0-9]+", str(code)):
        raise CatalogueError(f"{where}: code must be upper-case alphanumeric")

    cases = []
    for i, rc in enumerate(raw["cases"] or []):
        cw = f"{where} case #{i + 1}"
        if not isinstance(rc, dict):
            raise CatalogueError(f"{cw}: must be a mapping")
        unknown = set(rc) - _CASE_KEYS
        if unknown:
            raise CatalogueError(f"{cw}: unknown keys {sorted(unknown)}")
        missing = _CASE_REQUIRED - set(rc)
        if missing:
            raise CatalogueError(f"{cw}: missing {sorted(missing)}")
        m = ID_RE.match(rc["id"])
        if not m or m.group(1) != code:
            raise CatalogueError(f"{cw}: id '{rc['id']}' must be UAT-{code}-NNN")
        cw = f"{where} {rc['id']}"
        if rc["layer"] not in LAYERS:
            raise CatalogueError(f"{cw}: layer must be one of {LAYERS}")
        status = rc.get("status", "active")
        if status not in STATUSES:
            raise CatalogueError(f"{cw}: status must be one of {STATUSES}")
        if status == "blocked" and not rc.get("blocked_on"):
            raise CatalogueError(f"{cw}: blocked cases must say what they are blocked_on")
        plans = _tuple(rc.get("plans", ["any"]), cw)
        bad = set(plans) - set(PLANS)
        if bad:
            raise CatalogueError(f"{cw}: unknown plans {sorted(bad)}")
        steps = _tuple(rc["steps"], cw)
        expected = _tuple(rc["expected"], cw)
        if not steps or not expected:
            raise CatalogueError(f"{cw}: steps and expected must be non-empty")
        cases.append(Case(
            id=rc["id"], title=rc["title"], layer=rc["layer"], steps=steps,
            expected=expected, plans=plans,
            preconditions=_tuple(rc.get("preconditions"), cw), status=status,
            blocked_on=rc.get("blocked_on", ""), llm=bool(rc.get("llm", False)),
            platforms=_tuple(rc.get("platforms"), cw), notes=rc.get("notes", ""),
        ))
    return Area(
        area=raw["area"], code=code, title=raw["title"], order=int(raw["order"]),
        summary=raw.get("summary", ""), covers=_tuple(raw["covers"], where),
        cases=tuple(cases), source=where,
    )


def load(cases_dir: Path = CASES_DIR) -> list[Area]:
    areas = [_load_area(p) for p in sorted(cases_dir.glob("*.yaml"))]
    seen_ids: dict[str, str] = {}
    seen_codes: dict[str, str] = {}
    for a in areas:
        if a.code in seen_codes:
            raise CatalogueError(f"code {a.code} used by {seen_codes[a.code]} and {a.source}")
        seen_codes[a.code] = a.source
        for c in a.cases:
            if c.id in seen_ids:
                raise CatalogueError(f"duplicate id {c.id} ({seen_ids[c.id]}, {a.source})")
            seen_ids[c.id] = a.source
    return sorted(areas, key=lambda a: (a.order, a.area))


def all_cases(areas: list[Area] | None = None) -> dict[str, Case]:
    return {c.id: c for a in (areas or load()) for c in a.cases}
