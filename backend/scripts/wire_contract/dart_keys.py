"""ISS002/CR208 — generalized version of `test_wire_contract_parity.py`'s `_keys_by_dart_class`,
extended to:
  (a) search across every file in mobile/lib/models/ (not one hard-coded stem),
  (b) group `j['a'] ?? j['b']` alternation chains so the comparator treats them
      as "at least one must be present" rather than "all must be present"
      (inventory item 2),
  (c) find one level of nested `X.fromJson` calls reached through a
      `.map((e) => X.fromJson(...))` list expression, and which wire key
      controls that list (inventory item 1/4's nested shape — DEF365 was
      exactly `SimPortfolio` -> (`options` key) -> `SimOptionLeg`).

Deliberately regex/lexical, not a Dart AST parse — see SOLUTION.md §4 for why
that's an accepted tradeoff here and what it costs.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
MODELS_DIR = REPO / "mobile" / "lib" / "models"

_FACTORY_RE = re.compile(r"factory\s+(\w+)\.fromJson\b")
_KEY_RE = re.compile(r"""j\[\s*'([a-z0-9_]+)'\s*\]""")
_ALT_GROUP_RE = re.compile(
    r"j\['(\w+)'\](?:\s*\?\?\s*j\['(\w+)'\])+"
)
_MAP_FROMJSON_RE = re.compile(r"\.map\(\s*\([^)]*\)\s*=>\s*(\w+)\.fromJson")


@dataclass
class ClassContract:
    class_name: str
    file: str
    required_keys: set[str] = field(default_factory=set)  # each must appear
    alt_groups: list[set[str]] = field(default_factory=list)  # >=1 must appear
    nested_lists: dict[str, str] = field(default_factory=dict)  # wire key -> nested class


def _all_model_files() -> list[Path]:
    return sorted(MODELS_DIR.glob("*.dart"))


def _slice_by_factory(text: str) -> dict[str, str]:
    marks = [(m.start(), m.group(1)) for m in _FACTORY_RE.finditer(text)]
    out: dict[str, str] = {}
    for i, (start, cls) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        # Merge: a class can have >1 factory (rare); keep the largest body.
        body = text[start:end]
        if cls not in out or len(body) > len(out[cls]):
            out[cls] = body
    return out


_INDEX: dict[str, ClassContract] | None = None


def _build_index() -> dict[str, ClassContract]:
    idx: dict[str, ClassContract] = {}
    for path in _all_model_files():
        text = path.read_text()
        for cls, body in _slice_by_factory(text).items():
            alt_groups = []
            covered_by_alt: set[str] = set()
            for m in _ALT_GROUP_RE.finditer(body):
                keys = set(re.findall(r"j\['(\w+)'\]", m.group(0)))
                alt_groups.append(keys)
                covered_by_alt |= keys
            all_keys = set(_KEY_RE.findall(body))
            required = all_keys - covered_by_alt
            nested: dict[str, str] = {}
            for mm in _MAP_FROMJSON_RE.finditer(body):
                window = body[max(0, mm.start() - 150) : mm.start()]
                keys = _KEY_RE.findall(window)
                if keys:
                    nested[keys[-1]] = mm.group(1)
            idx[cls] = ClassContract(
                class_name=cls,
                file=path.name,
                required_keys=required,
                alt_groups=alt_groups,
                nested_lists=nested,
            )
    return idx


def index() -> dict[str, ClassContract]:
    global _INDEX
    if _INDEX is None:
        _INDEX = _build_index()
    return _INDEX


if __name__ == "__main__":
    idx = index()
    print(f"{len(idx)} Dart classes with a fromJson factory found under {MODELS_DIR}")
    for name in ("SimPortfolio", "SimOptionLeg", "GameCloseResult", "GameCloseDuel"):
        c = idx.get(name)
        if not c:
            print(f"  {name}: NOT FOUND")
            continue
        print(f"\n{name} ({c.file})")
        print(f"  required: {sorted(c.required_keys)}")
        print(f"  alt-groups (>=1 required): {c.alt_groups}")
        print(f"  nested lists: {c.nested_lists}")
