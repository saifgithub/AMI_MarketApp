#!/usr/bin/env python3
"""gen_registers.py — regenerate the CR / Defect register tables from per-item row files.

CR081 (generated-register model). The registers `docs/defect/def_list.md` and
`docs/forward_planning/cr_list.md` are GENERATED artifacts, not hand-edited tables. The
source of truth for each item is a single file `<register>/_registry/<ID>.row.md` holding
that item's exact markdown table row — one file per item, a disjoint write-path the item's
DOMAIN OWNER writes. This kills the concurrent-write "sweep" that a shared monolithic table
suffers on the shared `main` checkout (a second committer captures the union of the index),
the same way `board.md` is derived rather than hand-maintained.

Subcommands
  extract  : one-time migration — split the current register table into per-ID row files
             + capture the preamble (intro prose + header + separator) and any footer note.
  gen      : rebuild the register .md from _registry/*.row.md, sorted by numeric ID.
  verify   : assert the set of row-IDs in _registry/ equals the set in the live register
             and that each row's content matches (round-trip / no-drift check).

Row files are the source of truth; the register .md is disposable output. To add an item:
drop `<register>/_registry/<ID>.row.md`, run `gen`, commit both (pathspec) — see CLAUDE.md.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# Per-register binding. Everything else is generic.
REGISTERS = {
    "def": {
        "md": REPO / "docs/defect/def_list.md",
        "registry": REPO / "docs/defect/_registry",
        "prefix": "DEF",
    },
    "cr": {
        "md": REPO / "docs/forward_planning/cr_list.md",
        "registry": REPO / "docs/forward_planning/_registry",
        "prefix": "CR",
    },
}

PREAMBLE = "_preamble.md"   # intro prose + column header + separator, verbatim
FOOTER = "_footer.md"       # optional trailing note (e.g. the DEF backfill note)


def _row_id(line: str, prefix: str) -> str | None:
    """The first cell of a data row is the ID, e.g. '| DEF061 | ...' -> 'DEF061'."""
    m = re.match(rf"^\|\s*({prefix}\d{{3,}})\b", line)
    return m.group(1) if m else None


def _id_num(item_id: str, prefix: str) -> int:
    return int(item_id[len(prefix):])


def extract(reg: dict) -> None:
    prefix = reg["prefix"]
    lines = reg["md"].read_text().splitlines()
    # Header row is the first '| PREFIX | ...' line; the line after it is the '|---|' separator.
    header_idx = next(i for i, ln in enumerate(lines)
                      if re.match(rf"^\|\s*{prefix}\s*\|", ln))
    preamble = lines[: header_idx + 2]           # intro prose + header + separator
    body = lines[header_idx + 2:]

    reg["registry"].mkdir(parents=True, exist_ok=True)
    footer_lines: list[str] = []
    n = 0
    for ln in body:
        item_id = _row_id(ln, prefix)
        if item_id:
            (reg["registry"] / f"{item_id}.row.md").write_text(ln.rstrip("\n") + "\n")
            n += 1
        elif ln.strip():                          # a non-row, non-blank line = footer note
            footer_lines.append(ln)
        # blank lines inside the table region are dropped (they only fragment the table)

    (reg["registry"] / PREAMBLE).write_text("\n".join(preamble) + "\n")
    if footer_lines:
        (reg["registry"] / FOOTER).write_text("\n".join(footer_lines) + "\n")
    print(f"[extract] {prefix}: {n} row files + preamble"
          f"{' + footer' if footer_lines else ''} -> {reg['registry']}")


def _rows_sorted(reg: dict) -> list[str]:
    prefix = reg["prefix"]
    files = list(reg["registry"].glob(f"{prefix}*.row.md"))
    files.sort(key=lambda p: _id_num(p.stem.split(".")[0], prefix))
    return [p.read_text().rstrip("\n") for p in files]


def gen(reg: dict) -> str:
    preamble = (reg["registry"] / PREAMBLE).read_text().rstrip("\n")
    parts = [preamble, *_rows_sorted(reg)]
    footer = reg["registry"] / FOOTER
    if footer.exists():
        parts.append("")                          # blank line before the note
        parts.append(footer.read_text().rstrip("\n"))
    return "\n".join(parts) + "\n"


def verify(reg: dict) -> bool:
    prefix = reg["prefix"]
    live = reg["md"].read_text().splitlines()
    live_rows = {rid: ln.rstrip("\n") for ln in live
                 if (rid := _row_id(ln, prefix))}
    src_rows = {p.stem.split(".")[0]: p.read_text().rstrip("\n")
                for p in reg["registry"].glob(f"{prefix}*.row.md")}
    ok = True
    missing = set(live_rows) - set(src_rows)
    extra = set(src_rows) - set(live_rows)
    if missing:
        ok = False
        print(f"[verify] {prefix}: rows in live NOT in _registry: {sorted(missing)}")
    if extra:
        ok = False
        print(f"[verify] {prefix}: rows in _registry NOT in live: {sorted(extra)}")
    drift = [rid for rid in live_rows.keys() & src_rows.keys()
             if live_rows[rid] != src_rows[rid]]
    if drift:
        ok = False
        print(f"[verify] {prefix}: content drift on {sorted(drift)}")
    if ok:
        print(f"[verify] {prefix}: OK — {len(src_rows)} rows, content identical to live")
    return ok


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "gen"
    which = argv[2] if len(argv) > 2 else "all"
    regs = REGISTERS.values() if which == "all" else [REGISTERS[which]]
    if cmd == "extract":
        for r in regs:
            extract(r)
    elif cmd == "gen":
        for r in regs:
            r["md"].write_text(gen(r))
            print(f"[gen] wrote {r['md'].relative_to(REPO)}")
    elif cmd == "print":                           # gen to stdout (scratch round-trip)
        for r in regs:
            sys.stdout.write(gen(r))
    elif cmd == "verify":
        if not all(verify(r) for r in regs):
            return 1
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
