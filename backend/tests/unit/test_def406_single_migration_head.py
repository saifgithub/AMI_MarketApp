"""DEF406 — the promotion gate refuses a forked alembic chain.

On 2026-09-11 two lanes each added a migration parented on `cr219a0b0c0d3`.
Both lanes verified "single head" against their own pre-merge branch, and both
were right at the time: the fork is a property of the MERGED tree, so no lane's
own gate could see it. `alembic upgrade head` refuses a multi-head chain, so
the promotion would have failed mid-deploy — after the rsync, with the
container already recreated.

The check therefore lives where the merged tree is measured, which is
postflight (the same place, and the same lesson, as DEF405's suite verdict one
layer up). These tests pin three things: the real repo has one head; the actual
DEF406 fork is caught; and an unreadable or empty versions directory fails
loudly rather than reading as "one head" — a parser that matches nothing would
otherwise report every chain as clean.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_POSTFLIGHT = _ROOT / "scripts" / "promotion" / "postflight.py"
_VERSIONS = _ROOT / "backend" / "alembic" / "versions"


@pytest.fixture(scope="module")
def postflight():
    spec = importlib.util.spec_from_file_location("postflight_def406", _POSTFLIGHT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _chain(tmp_path: Path, *files: tuple[str, str, str | None]) -> Path:
    """Write a scratch versions dir. Each entry is (name, revision, parent).

    Alternates the two declaration styles this repo actually contains — bare
    `revision = "x"` / `down_revision = "y"` and annotated
    `revision: str = "x"` / `down_revision: Union[...] = "y"` — so a parser
    that reads only one of them cannot pass. The first cut of this guard
    anchored the annotation before the whitespace (`^down_revision(?:\\s*:...)`),
    which never matched the bare form's space before `=`; those parents went
    unrecorded and 20 healthy revisions read as heads.
    """
    d = tmp_path / "versions"
    d.mkdir(exist_ok=True)
    for i, (name, rev, parent) in enumerate(files):
        down = f'"{parent}"' if parent else "None"
        if i % 2:
            decl = f'revision: str = "{rev}"\n'
            down_decl = f"down_revision: Union[str, Sequence[str], None] = {down}\n"
        else:
            decl = f'revision = "{rev}"\n'
            down_decl = f"down_revision = {down}\n"
        (d / f"{name}.py").write_text(f'"""scratch fixture."""\n{decl}{down_decl}')
    return d


def test_both_declaration_styles_are_read(postflight, tmp_path) -> None:
    """Pins the parser against the bug that shipped in this guard's first cut.

    Two linear chains, one in each declaration style. If either pattern stops
    matching its form — the original miss was `down_revision = "x"`, whose
    space before `=` the annotation-first pattern could not reach — the
    parents go unrecorded and every child reads as a head.
    """
    d = tmp_path / "bare"
    d.mkdir()
    (d / "a.py").write_text('revision = "aaa"\ndown_revision = None\n')
    (d / "b.py").write_text('revision = "bbb"\ndown_revision = "aaa"\n')
    (d / "c.py").write_text('revision = "ccc"\ndown_revision = "bbb"\n')
    assert postflight.check_migration_heads(d) == []

    d2 = tmp_path / "annotated"
    d2.mkdir()
    (d2 / "a.py").write_text(
        'revision: str = "aaa"\n'
        'down_revision: Union[str, Sequence[str], None] = None\n')
    (d2 / "b.py").write_text(
        'revision: str = "bbb"\n'
        'down_revision: Union[str, Sequence[str], None] = "aaa"\n')
    assert postflight.check_migration_heads(d2) == []


def test_the_real_repo_has_exactly_one_head(postflight) -> None:
    """The live chain, read the way postflight reads it."""
    assert postflight.check_migration_heads(_VERSIONS) == []


def test_the_parser_agrees_with_alembic_itself(postflight) -> None:
    """The guard is worthless if it reads the chain differently from the tool
    that will walk it. Both declaration styles exist in this repo — bare
    `revision = "x"` and annotated `revision: str = "x"` — and an earlier cut
    of this parser matched only one, which made 20 healthy revisions look like
    heads."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(_ROOT / "backend" / "alembic.ini"))
    cfg.set_main_option("script_location", str(_ROOT / "backend" / "alembic"))
    real_heads = set(ScriptDirectory.from_config(cfg).get_heads())

    revisions, parents = set(), set()
    for path in sorted(_VERSIONS.glob("*.py")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        rev = postflight._REVISION_LINE.search(text)
        if not rev:
            continue
        revisions.add(rev.group(1))
        down = postflight._DOWN_REVISION_LINE.search(text)
        if down:
            parents.update(postflight._QUOTED_ID.findall(down.group(1)))

    assert revisions - parents == real_heads


def test_the_def406_fork_is_caught_and_names_both_heads(postflight, tmp_path) -> None:
    """The shape that actually happened: two children, one shared parent."""
    d = _chain(
        tmp_path,
        ("base", "cr219a0b0c0d3", None),
        ("lane_a", "cr221a0b0c0d4", "cr219a0b0c0d3"),
        ("lane_b", "cr222a0b0c0d4", "cr219a0b0c0d3"),
    )
    problems = postflight.check_migration_heads(d)
    assert len(problems) == 1
    assert "2 alembic heads" in problems[0]
    assert "cr221a0b0c0d4" in problems[0] and "cr222a0b0c0d4" in problems[0]


def test_the_fix_that_was_applied_reads_clean(postflight, tmp_path) -> None:
    """Re-parenting one onto the other is what DEF406 did; it must pass."""
    d = _chain(
        tmp_path,
        ("base", "cr219a0b0c0d3", None),
        ("lane_a", "cr221a0b0c0d4", "cr219a0b0c0d3"),
        ("lane_b", "cr222a0b0c0d4", "cr221a0b0c0d4"),
    )
    assert postflight.check_migration_heads(d) == []


def test_an_alembic_merge_revision_counts_all_its_parents(postflight, tmp_path) -> None:
    """The other legitimate fix for a fork is `alembic merge`, which names two
    parents on one line. Reading only the first would report the merged-away
    head as still live."""
    d = tmp_path / "versions"
    d.mkdir()
    (d / "base.py").write_text('revision = "aaa"\ndown_revision = None\n')
    (d / "one.py").write_text('revision = "bbb"\ndown_revision = "aaa"\n')
    (d / "two.py").write_text('revision = "ccc"\ndown_revision = "aaa"\n')
    (d / "merge.py").write_text('revision = "ddd"\ndown_revision = ("bbb", "ccc")\n')
    assert postflight.check_migration_heads(d) == []


def test_an_empty_or_missing_directory_fails_loudly(postflight, tmp_path) -> None:
    """Vacuity. A check that parses nothing must not report a clean chain —
    that is the silent-pass shape CR040 exists to forbid."""
    empty = tmp_path / "versions"
    empty.mkdir()
    assert postflight.check_migration_heads(empty), "an empty dir must not read as one head"
    assert postflight.check_migration_heads(tmp_path / "nope"), "a missing dir must not read as one head"


def test_the_check_is_wired_into_the_postflight_driver() -> None:
    """A check nobody calls is not a guard. Pins the registration, not just the
    function — this is the house rule that an entry without an enforcing check
    is not done."""
    source = _POSTFLIGHT.read_text(encoding="utf-8")
    assert '("migrations", lambda: check_migration_heads())' in source
