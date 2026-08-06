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
        # DEF203. The vocabularies differ because the lifecycles do: a defect is
        # broken or it is not, while a CR is planned work that can legitimately
        # sit in progress or stand open forever.
        "statuses": ("open", "fixed", "wontfix", "dropped"),
        "open_statuses": ("open",),
    },
    "cr": {
        "md": REPO / "docs/forward_planning/cr_list.md",
        "registry": REPO / "docs/forward_planning/_registry",
        "prefix": "CR",
        "statuses": ("proposed", "in_progress", "done", "dropped", "standing"),
        "open_statuses": ("proposed", "in_progress"),
    },
}

# DEF203 — why this vocabulary is enforced rather than merely documented.
#
# The status column was free text, and free text is not a state. Measured 2026-08-06 across
# all 221 DEF + 134 CR rows: 22 distinct DEF values and 10 CR values, including FOUR
# spellings of "this is fixed" (`resolved` 94, `fixed` 76, `done` 10, `closed` 2), two of
# "in progress" (`in_progress`, `in progress`, plus `started` and `partial`), and 20 cells
# holding whole sentences.
#
# The cost is not tidiness. Every status-based count of the backlog was wrong by an unknown
# amount, ALWAYS in the same direction — a filter matching a token silently drops the rows
# whose cell holds prose, so the backlog reads shorter than it is. DEF100's cell said
# `**open** — Saiful-liaison (via coder.store)...` and it was invisible to exactly that
# filter. Three more (DEF063, DEF084, DEF093) carried a fixed-family token whose own prose
# said a half was still open; normalising them moved them to `open`, which is a correction
# to the backlog and not a formatting change.
#
# A qualifier is not banned, it just does not live here — it goes in the description column,
# where it is readable and where nothing parses it.


def status_of(row: str) -> str:
    """The status cell of one register row. Layout is
    `| ID | date | source | area | description | status | files | tag |`, so the
    status is the fourth cell from the end once the trailing empty split is counted."""
    cells = row.rstrip("\n").split("|")
    return cells[-4].strip() if len(cells) >= 4 else ""

PREAMBLE = "_preamble.md"   # intro prose + column header + separator, verbatim
FOOTER = "_footer.md"       # optional trailing note (e.g. the DEF backfill note)


# DEF159 — the seam in CR081's disjoint-write-path design.
#
# `gen` reads whatever row files are ON DISK. On the shared `main` checkout that includes another
# track's UNTRACKED row, so "regenerate, then pathspec-commit only my own row" quietly commits a
# TABLE containing a row whose source file is in nobody's index. The guarantee holds for the row
# files and silently does not hold for the generated artifact.
#
# What that cost: at `b79dd445` CR121's untracked row was baked into the committed `cr_list.md`.
# `test_registers_no_drift` went RED at HEAD from that moment — for every checkout EXCEPT the one
# holding the untracked file. The architect's own pre-submission run reported 1589 passed; the
# auditor's detached worktree at the same SHA got 1588 passed, 1 failed. A green measurement taken
# in a dirty shared checkout is not evidence about the repository.
#
# Deliberately NOT a hard failure in `gen`: creating a new row means the file is untracked at the
# moment you generate, which is the normal, correct flow (`write row` -> `gen` -> `commit both`).
# Failing there would train people to pass a bypass flag. So `gen` warns loudly and hands back the
# exact `git add` line, while `verify` FAILS on the state that is actually broken — a row present
# in the live table whose source file is not in the index, which is the thing a clean checkout
# cannot reproduce.
def _git_lines(args: list[str]) -> list[str]:
    """Run a git command under REPO; empty list if git is unavailable or this is not a repo."""
    import subprocess
    try:
        out = subprocess.run(
            ["git", *args], cwd=REPO, capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if out.returncode != 0:
        return []
    return [ln for ln in out.stdout.splitlines() if ln.strip()]


def _row_ids_by_state(reg: dict) -> tuple[set[str], set[str]]:
    """(untracked, unstaged-modified) row IDs for this register, per git."""
    rel = reg["registry"].relative_to(REPO).as_posix()
    prefix = reg["prefix"]

    def ids(paths: list[str]) -> set[str]:
        found = set()
        for p in paths:
            name = p.rsplit("/", 1)[-1]
            if name.endswith(".row.md") and name.startswith(prefix):
                found.add(name.split(".")[0])
        return found

    untracked = ids(_git_lines(["ls-files", "--others", "--exclude-standard", "--", rel]))
    dirty = ids(_git_lines(["diff", "--name-only", "--", rel]))
    return untracked, dirty


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
        print(f"[verify] {prefix}:   the live table carries a row with no source file. Either the "
              f"row file was deleted without regenerating, or this checkout never had it — which "
              f"is what DEF159 looks like from the OTHER side: someone regenerated the table while "
              f"the row file was untracked in their tree, so it was never committed.")

    # DEF159's real check: a row that IS in both, whose source file is not in the index. This
    # checkout passes drift, and every clean checkout of the same SHA fails it.
    untracked, dirty = _row_ids_by_state(reg)
    published_untracked = sorted(untracked & set(live_rows))
    if published_untracked:
        ok = False
        print(f"[verify] {prefix}: PUBLISHED BUT UNCOMMITTED — {published_untracked}")
        print(f"[verify] {prefix}:   these rows are in the committed table but their row files are "
              f"UNTRACKED. The table references a source that is not in the repo, so a clean "
              f"checkout regenerates a DIFFERENT table and the drift guard fails there while it "
              f"passes here (DEF159). Fix: git add -- " +
              " ".join(f"{reg['registry'].relative_to(REPO).as_posix()}/{r}.row.md"
                       for r in published_untracked))
    if extra:
        ok = False
        print(f"[verify] {prefix}: rows in _registry NOT in live: {sorted(extra)}")
    drift = [rid for rid in live_rows.keys() & src_rows.keys()
             if live_rows[rid] != src_rows[rid]]
    if drift:
        ok = False
        print(f"[verify] {prefix}: content drift on {sorted(drift)}")

    # DEF203: the status cell must hold a state, not a sentence. Checked against the
    # ROW FILES rather than the live table, so a bad status fails on the commit that
    # writes it instead of waiting for someone to regenerate.
    bad = {rid: status_of(row) for rid, row in src_rows.items()
           if status_of(row) not in reg["statuses"]}
    if bad:
        ok = False
        print(f"[verify] {prefix}: {len(bad)} row(s) with a status outside "
              f"{list(reg['statuses'])}:")
        for rid, status in sorted(bad.items()):
            shown = status if len(status) <= 60 else status[:57] + "..."
            print(f"[verify] {prefix}:   {rid}: {shown!r}")
        print(f"[verify] {prefix}:   A status-based count of the backlog silently DROPS "
              f"these, always reading shorter than the truth. Put the qualifier in the "
              f"description column, where nothing parses it.")

    if ok:
        counts: dict[str, int] = {}
        for row in src_rows.values():
            counts[status_of(row)] = counts.get(status_of(row), 0) + 1
        still_open = sum(counts.get(s, 0) for s in reg["open_statuses"])
        tally = " ".join(f"{s}={counts.get(s, 0)}" for s in reg["statuses"])
        print(f"[verify] {prefix}: OK — {len(src_rows)} rows, content identical to live")
        print(f"[verify] {prefix}: {tally}  ({still_open} open)")
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
            # DEF159: say out loud whose rows just went into the table but are not in the index.
            # On the shared `main` checkout the answer is routinely "another track's", and
            # committing the table without their row file is what leaves `main` red for everyone
            # but you.
            untracked, dirty = _row_ids_by_state(r)
            rel = r["registry"].relative_to(REPO).as_posix()
            if untracked:
                print(f"[gen] !! {r['prefix']}: baked in UNTRACKED row files: {sorted(untracked)}")
                print(f"[gen]    Commit them WITH the table or the table points at nothing "
                      f"(DEF159). If any belong to another track, do NOT commit the table:")
                print(f"[gen]    git add -- " +
                      " ".join(f"{rel}/{i}.row.md" for i in sorted(untracked)))
            if dirty:
                print(f"[gen] !! {r['prefix']}: baked in UNCOMMITTED EDITS to: {sorted(dirty)}")
                print(f"[gen]    If any of those are not yours, committing this table publishes "
                      f"another track's unreleased row (DEF159).")
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
