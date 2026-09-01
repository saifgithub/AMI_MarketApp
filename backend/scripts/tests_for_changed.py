"""CR216 — which tests actually cover the files you changed.

WHY THIS EXISTS. DEF387 added a supervisor guard to `scripts/backtest_sweep.py`. Its author ran a
targeted subset to check it — `-k` on something like "sweep" or "backtest" — and the subset came
back green, so the change was promoted. It had in fact broken
`test_def358_completion_sentinel_counts_the_batch.py`, which calls `sweep.main()` in-process. That
file matches neither "sweep" nor "backtest", because tests here are named after the DEFECT they pin,
not after the module they exercise. The targeted run was structurally incapable of finding it. Only
the full ~900s suite did, hours later.

That is not a mistake to be more careful about next time; a name filter cannot follow an import edge,
so no amount of care fixes it. This walks the edges instead: parse every import under `backend/`,
invert the graph, and report which test files reach the changed modules — directly or transitively.

HONEST LIMITS, because a selector that quietly under-reports is worse than no selector (CLAUDE.md,
degrade loudly). It sees static `import`/`from` statements only. It cannot see a fixture that reads a
YAML file, a subprocess that shells out, `importlib` by computed name, or a template rendered at
runtime. So a non-Python change makes it say so and recommend the full suite rather than printing a
confident empty list, and its output is a FLOOR — the tests you must run, never proof that the rest
are safe.

USAGE
    python backend/scripts/tests_for_changed.py                  # uncommitted work vs HEAD
    python backend/scripts/tests_for_changed.py --since HEAD~3   # a range
    python backend/scripts/tests_for_changed.py app/services/room_runner.py   # explicit
    python backend/scripts/tests_for_changed.py --why            # show the import chain

Exit: 0 selection printed (possibly empty) · 2 bad usage · 3 full suite required

Non-Python changes have a real blast radius no import graph can see, so they are attributed by the
path literals the tests themselves contain — derived, not a hand-written glob table. A TRACKED
non-Python file that no test names is reported as unknown and forces exit 3; untracked ones (new
files nothing references yet) are listed but do not.
"""
from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from collections import deque
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
ROOTS = ("app", "scripts", "tests")


def _is_tracked(path: Path) -> bool:
    return subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(path)],
        cwd=REPO, capture_output=True, check=False,
    ).returncode == 0


def _py_files() -> list[Path]:
    out: list[Path] = []
    for root in ROOTS:
        out.extend(p for p in (BACKEND / root).rglob("*.py") if "__pycache__" not in p.parts)
    return out


def _module_name(path: Path) -> str:
    rel = path.relative_to(BACKEND).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _resolve(dotted: str, index: dict[str, Path]) -> Path | None:
    return index.get(dotted)


def _imports_of(path: Path, index: dict[str, Path]) -> set[Path]:
    """Every in-repo file this one imports.

    `from app.services import room_runner` names the PACKAGE in the ast node and the submodule in
    the alias, so both spellings have to be tried — resolving only the node would lose the edge that
    matters and silently under-select.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return set()

    found: set[Path] = set()

    def take(dotted: str) -> None:
        target = _resolve(dotted, index)
        if target is not None and target != path:
            found.add(target)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                take(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative import
                base = _module_name(path).split(".")
                base = base[: len(base) - node.level + 1] if node.level > 1 else base[:-1] if base else []
                prefix = ".".join(base + ([node.module] if node.module else []))
            else:
                prefix = node.module or ""
            if prefix:
                take(prefix)
                for alias in node.names:
                    take(f"{prefix}.{alias.name}")
    return found


def path_literals(files: list[Path]) -> dict[Path, set[str]]:
    """Every string constant in a test file that could name a repo path.

    Non-Python files (compose, the registers, orchestration scripts, the lesson corpus) have a real
    blast radius that no import graph can see, and this repo has many tests that read them. Rather
    than hand-writing a glob table — which would be the same kind of guess this tool exists to
    replace — collect the literals the tests themselves contain and match changed paths against
    those. It over-selects, which is the safe direction for a floor.
    """
    out: dict[Path, set[str]] = {}
    for f in files:
        if not f.is_relative_to(BACKEND / "tests"):
            continue
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        except (SyntaxError, UnicodeDecodeError):
            continue
        lits = {
            n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and 0 < len(n.value) < 200
        }
        out[f] = lits
    return out


def tests_referencing(changed: Path, literals: dict[Path, set[str]]) -> set[Path]:
    """Tests whose literals name this file, its basename, or a distinctive parent segment."""
    rel = changed.relative_to(REPO).as_posix()
    exact = {rel, changed.name}
    hits = set()
    for test, lits in literals.items():
        for lit in lits:
            # An exact path or filename match, or a multi-segment suffix of the path. A BARE
            # directory name is deliberately not enough: "mobile" appears in fifteen unrelated
            # tests, and matching on it attributed every Podfile.lock change to all of them. An
            # over-loose floor is still a wrong answer — it just fails in the tiring direction.
            if lit in exact or ("/" in lit and len(lit) > 3 and rel.endswith(lit.lstrip("./"))):
                hits.add(test)
                break
    return hits


def build_reverse_graph() -> tuple[dict[Path, set[Path]], dict[str, Path]]:
    files = _py_files()
    index = {_module_name(p): p for p in files}
    reverse: dict[Path, set[Path]] = {p: set() for p in files}
    for f in files:
        for target in _imports_of(f, index):
            reverse.setdefault(target, set()).add(f)
    return reverse, index


def changed_paths(since: str | None) -> list[Path]:
    if since:
        cmd = ["git", "diff", "--name-only", f"{since}..HEAD"]
    else:
        cmd = ["git", "status", "--porcelain"]
    proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, check=False)
    out: list[Path] = []
    for line in proc.stdout.splitlines():
        rel = line[3:].strip() if not since else line.strip()
        if not rel or " -> " in rel:
            rel = rel.split(" -> ")[-1] if " -> " in rel else rel
        if rel:
            out.append(REPO / rel)
    return out


def select(targets: list[Path], reverse: dict[Path, set[Path]]) -> tuple[set[Path], dict[Path, Path]]:
    """Reverse-reachability from the changed files. Returns the test files and a parent map."""
    seen: set[Path] = set()
    parent: dict[Path, Path] = {}
    queue = deque(t for t in targets if t in reverse)
    seen.update(queue)
    while queue:
        cur = queue.popleft()
        for importer in reverse.get(cur, ()):
            if importer not in seen:
                seen.add(importer)
                parent[importer] = cur
                queue.append(importer)
    tests = {p for p in seen if p.is_relative_to(BACKEND / "tests") and p.name.startswith("test_")}
    return tests, parent


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="explicit files (repo- or backend-relative)")
    ap.add_argument("--since", help="git ref; compare <ref>..HEAD instead of the working tree")
    ap.add_argument("--why", action="store_true", help="print the import chain for each selected test")
    args = ap.parse_args()

    if args.paths:
        raw = []
        for p in args.paths:
            cand = Path(p)
            for base in (REPO, BACKEND, Path.cwd()):
                if (base / cand).exists():
                    raw.append((base / cand).resolve())
                    break
            else:
                print(f"no such path: {p}", file=sys.stderr)
                return 2
    else:
        raw = [p.resolve() for p in changed_paths(args.since)]

    if not raw:
        print("no changes detected", file=sys.stderr)
        return 0

    backend_py = [p for p in raw if p.suffix == ".py" and p.is_relative_to(BACKEND)]
    other = [p for p in raw if p not in backend_py and p.exists() and p.is_file()]

    reverse, _ = build_reverse_graph()
    tests, parent = select(backend_py, reverse)

    # Non-Python changes: attribute what we can by literal reference, and report the rest as
    # genuinely unknown rather than folding them into a confident selection.
    literals = path_literals(_py_files())
    by_literal: dict[Path, set[Path]] = {}
    unknown: list[Path] = []
    for p in other:
        hits = tests_referencing(p, literals)
        if hits:
            by_literal[p] = hits
            tests |= hits
        else:
            unknown.append(p)

    for t in sorted(tests):
        print(t.relative_to(BACKEND))
        if args.why:
            chain, cur = [], t
            while cur in parent:
                cur = parent[cur]
                chain.append(cur.relative_to(BACKEND))
            print("    imports " + " -> ".join(str(c) for c in chain) if chain else "    (changed directly)", file=sys.stderr)

    print(
        f"\n{len(tests)} test file(s) reach {len(backend_py)} changed Python file(s).",
        file=sys.stderr,
    )
    print(
        "This is a FLOOR, not a proof: static imports only — no subprocess, importlib, "
        "fixture-read data files, or config.",
        file=sys.stderr,
    )
    if by_literal:
        print(
            f"\n{len(by_literal)} non-Python file(s) attributed by test path literals "
            "(no import edge exists; matched by name):",
            file=sys.stderr,
        )
        for q, hits in sorted(by_literal.items())[:10]:
            print(f"  {q.relative_to(REPO)} -> {len(hits)} test(s)", file=sys.stderr)

    tracked_unknown = [q for q in unknown if _is_tracked(q)]
    if tracked_unknown:
        print(
            f"\nFULL SUITE REQUIRED: {len(tracked_unknown)} tracked non-Python file(s) are outside "
            "the import graph and are named by no test literal, so their blast radius is unknown:",
            file=sys.stderr,
        )
        for q in sorted(tracked_unknown)[:10]:
            print(f"  {q.relative_to(REPO)}", file=sys.stderr)
        return 3
    if unknown:
        print(
            f"\n{len(unknown)} untracked non-Python file(s) not analysed (new files nothing "
            "references yet); not treated as a reason to run everything.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
