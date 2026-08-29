"""ISS002/CR208 — auto-discover (HTTP method, path template, Dart class, JSON
navigation-path) triples from mobile/lib/services/api/api_client.dart,
instead of a human hand-declaring each pair (the thing that failed 3x).

Method: slice the file into Dart method bodies (brace-matched), find the
`_dio.<verb>(...)` call's URL literal inside each, then find every
`X.fromJson(...)` call in the same body and the navigation expression that
feeds it (e.g. `r.data!`, `r.data!['trade']`, or a `.map(...)` list source).

This is intentionally a *lexical* extractor, not a Dart AST parser (no such
dependency exists in this stack — see the brief's "new dependencies must be
justified" constraint). It is graded on recall/precision against the real
file below, not asserted as complete.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
API_CLIENT = REPO / "mobile" / "lib" / "services" / "api" / "api_client.dart"

_METHOD_START = re.compile(
    r"Future<[^{]*?>\s+(\w+)\s*\(([^)]*)\)\s*async\s*\{"
)
_VERB_CALL = re.compile(
    # `[^(]*` skips the generic type args (`<Map<String, dynamic>>`) without
    # trying to balance nested `<>` — they never contain '(' in this file.
    # `\s*\.\s*` (not a literal `.`) because a handful of call sites break
    # the line between `_dio` and `.get<...>` — an early version of this
    # extractor missed `simPortfolioHistory` and `simHoldingLots` on exactly
    # this, a real measured miss, not a hypothetical one (see SOLUTION.md §5).
    r"_dio\s*\.\s*(get|post|put|patch|delete)[^(]*\(\s*['\"]([^'\"]+)['\"]"
)
_FROMJSON = re.compile(r"([A-Z]\w*)\.fromJson\(")

# DEF367 — the envelope key a LIST endpoint's items live under.
#
# Five surfaces sat in the unverified baseline while their routes were being
# exercised 1–9 times each by the suite: the client reads `r.data['items']` and
# the comparator was dereferencing the response BODY as a list, which for
# `{"items": [...], "total": n}` yields nothing. They were not coverage debt and
# no test could ever have closed them. The key is taken from the client's own
# navigation rather than from a guessed list of common names, because the
# navigation IS the contract under test — if the client stops reading `items`,
# this stops finding `items`, which is the correct failure.
_ENVELOPE = re.compile(r"""\bdata\s*\??\s*\[\s*['"](\w+)['"]\s*\]""")


@dataclass
class Pair:
    dart_method: str
    verb: str
    url_template: str
    dart_class: str
    nav_snippet: str
    is_list: bool
    envelope_key: str | None = None


def _method_bodies(text: str) -> list[tuple[str, str, str]]:
    """[(method_name, params, body)] by brace-counting from each match."""
    out = []
    for m in _METHOD_START.finditer(text):
        name, params = m.group(1), m.group(2)
        start = m.end() - 1  # at the opening '{'
        depth = 0
        i = start
        while i < len(text):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        out.append((name, params, text[start : i + 1]))
    return out


def _url_to_regex(url: str) -> str:
    """`/v1/sim/portfolio/$userId` -> `^/v1/sim/portfolio/[^/]+$`.

    Handles both `$var` and `${expr}` interpolation forms. Query strings
    (never present in these literals — built via `queryParameters:`) are
    not part of the path so need no handling here.
    """
    # Escape regex-special chars EXCEPT the '$' we're about to consume.
    parts = re.split(r"\$\{[^}]+\}|\$\w+", url)
    parts = [re.escape(p) for p in parts]
    return "^" + "[^/]+".join(parts) + "$"


def discover() -> list[Pair]:
    text = API_CLIENT.read_text()
    pairs: list[Pair] = []
    for name, _params, body in _method_bodies(text):
        vm = _VERB_CALL.search(body)
        if not vm:
            continue
        verb, url = vm.group(1), vm.group(2)
        for fm in _FROMJSON.finditer(body):
            cls = fm.group(1)
            if cls in ("DateTime",):  # not a wire model
                continue
            # Grab ~80 chars before the match as the navigation snippet.
            start = max(0, fm.start() - 80)
            nav = body[start : fm.start()]
            is_list = ".map(" in nav or ".map(" in body[fm.start() : fm.start() + 5]
            # The envelope lookback is deliberately much wider than the nav
            # snippet: `final items = ((r.data?['items'] as List?) ?? const []);`
            # can sit several statements above the `.map((j) => X.fromJson(j))`
            # that names the class, and at 80 chars three of the five affected
            # call sites had the key cut off. Last match wins — the nearest
            # `data[...]` above the parse is the one being parsed.
            env_matches = _ENVELOPE.findall(body[max(0, fm.start() - 400): fm.start()])
            envelope_key = env_matches[-1] if (is_list and env_matches) else None
            pairs.append(
                Pair(
                    dart_method=name,
                    verb=verb.upper(),
                    url_template=url,
                    dart_class=cls,
                    nav_snippet=nav.strip().replace("\n", " ")[-60:],
                    is_list=is_list,
                    envelope_key=envelope_key,
                )
            )
    return pairs


if __name__ == "__main__":
    pairs = discover()
    print(f"Discovered {len(pairs)} (dart_method -> fromJson class) call sites "
          f"across {len({p.dart_method for p in pairs})} api_client.dart methods.")
    by_class: dict[str, int] = {}
    for p in pairs:
        by_class[p.dart_class] = by_class.get(p.dart_class, 0) + 1
    out = {
        "count": len(pairs),
        "pairs": [
            {
                "dart_method": p.dart_method,
                "verb": p.verb,
                "url_template": p.url_template,
                "url_regex": _url_to_regex(p.url_template),
                "dart_class": p.dart_class,
                "is_list": p.is_list,
                "envelope_key": p.envelope_key,
                "nav_snippet": p.nav_snippet,
            }
            for p in pairs
        ],
    }
    out_path = Path(__file__).with_name("discovered_pairs.json")
    out_path.write_text(json.dumps(out, indent=2))
    print(f"Wrote {out_path}")
    print("\nSample (first 15):")
    for p in pairs[:15]:
        print(f"  {p.verb:6s} {p.url_template:45s} -> {p.dart_class}")
