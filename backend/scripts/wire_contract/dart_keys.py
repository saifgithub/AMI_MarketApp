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

# DEF367 — a read that is "nested OR flat":
#   final nested = j['next_field'];
#   ... nested is Map<String, dynamic>
#       ? GameFieldSummary.fromJson(nested)
#       : (j['field_id'] != null ? GameFieldSummary.fromJson(j) : null)
# (or the same with `j['next_field']` inline). The server satisfies the client by
# sending EITHER the nested key OR the keys the flat parse of `j` itself reads, so
# the nested key must not be a hard requirement and the flat class's keys are the
# alternative. `guard` is whatever sits between the `:` and the flat `fromJson(j)`
# (typically a `j['field_id'] != null ?` test) — its keys belong to the flat side.
_NESTED_OR_FLAT_VAR_RE = re.compile(
    r"final\s+(\w+)\s*=\s*j\['(\w+)'\]\s*;"
    r".*?\b\1\s+is\s+Map<String,\s*dynamic>\s*\?\s*(\w+)\.fromJson\(\s*\1\s*\)"
    r"\s*:(?P<guard>[^;]{0,200}?)\b\3\.fromJson\(\s*j\s*\)",
    re.DOTALL,
)
_NESTED_OR_FLAT_INLINE_RE = re.compile(
    r"j\['(\w+)'\]\s+is\s+Map<String,\s*dynamic>\s*\?\s*(\w+)\.fromJson\(\s*j\['\1'\]"
    r"[^)]*\)\s*:(?P<guard>[^;]{0,200}?)\b\2\.fromJson\(\s*j\s*\)",
    re.DOTALL,
)

# DEF367 — a nullable static helper that falls back through several keys:
#   static bool? _willQueue(Map<String, dynamic> j) {
#     final explicit = j['will_queue'] as bool?;
#     if (explicit != null) return explicit;
#     final open = j['market_open'] as bool?;
#     ...
# The first key that is non-null wins, so every key it reads is an alternative to
# the others, exactly like `j['a'] ?? j['b']`. The early return on `!= null` is what
# distinguishes this from a helper that genuinely needs all of its keys.
_HELPER_RE = re.compile(
    r"static\s+\w+\?\s+\w+\(\s*Map<String,\s*dynamic>\s+j\s*\)\s*\{"
)
_EARLY_RETURN_RE = re.compile(r"if\s*\(\s*\w+\s*!=\s*null\s*\)\s*return\b")


@dataclass
class ClassContract:
    class_name: str
    file: str
    required_keys: set[str] = field(default_factory=set)  # each must appear
    alt_groups: list[set[str]] = field(default_factory=list)  # >=1 must appear
    nested_lists: dict[str, str] = field(default_factory=dict)  # wire key -> nested class
    # nested-or-flat reads: the nested wire key is satisfied by sending it, OR by
    # sending the keys `flat_class`'s own parse reads (+ `guard_keys`).
    flat_fallbacks: list["FlatFallback"] = field(default_factory=list)


@dataclass
class FlatFallback:
    nested_key: str
    flat_class: str
    guard_keys: set[str] = field(default_factory=set)


def _brace_body(text: str, open_idx: int) -> str:
    depth = 0
    for i in range(open_idx, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[open_idx : i + 1]
    return text[open_idx:]


def _helper_alt_groups(body: str) -> list[set[str]]:
    groups: list[set[str]] = []
    for m in _HELPER_RE.finditer(body):
        helper = _brace_body(body, m.end() - 1)
        keys = set(_KEY_RE.findall(helper))
        if len(keys) >= 2 and _EARLY_RETURN_RE.search(helper):
            groups.append(keys)
    return groups


def _flat_fallbacks(body: str) -> list[FlatFallback]:
    out: list[FlatFallback] = []
    for m in _NESTED_OR_FLAT_VAR_RE.finditer(body):
        out.append(FlatFallback(m.group(2), m.group(3),
                                set(_KEY_RE.findall(m.group("guard")))))
    for m in _NESTED_OR_FLAT_INLINE_RE.finditer(body):
        out.append(FlatFallback(m.group(1), m.group(2),
                                set(_KEY_RE.findall(m.group("guard")))))
    return out


_COMMENT_LINE_RE = re.compile(r"^[ \t]*//.*$", re.MULTILINE)


def _strip_comment_lines(text: str) -> str:
    """Blank out whole-line `//` and `///` comments.

    DEF367 — the slice for one factory runs to the NEXT factory, so it swallows the
    next class's doc comment. `GameTradeResult`'s says "This read `j['status']` and
    defaulted to 'filled'", which made `GameTradeQuote` appear to require `status`.
    Only whole-line comments are removed, so a `//` inside a string literal is safe.
    """
    return _COMMENT_LINE_RE.sub("", text)


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
        text = _strip_comment_lines(path.read_text())
        for cls, body in _slice_by_factory(text).items():
            alt_groups = []
            covered_by_alt: set[str] = set()
            for m in _ALT_GROUP_RE.finditer(body):
                keys = set(re.findall(r"j\['(\w+)'\]", m.group(0)))
                alt_groups.append(keys)
                covered_by_alt |= keys
            for keys in _helper_alt_groups(body):
                alt_groups.append(keys)
                covered_by_alt |= keys
            flat = _flat_fallbacks(body)
            for ff in flat:
                covered_by_alt |= {ff.nested_key} | ff.guard_keys
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
                flat_fallbacks=flat,
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
