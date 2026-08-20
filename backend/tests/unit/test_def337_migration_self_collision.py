"""DEF337 — a migration must not create the same index twice.

The bug: `b4c1d2e3f501` (CR192) declared `sampled_at` with `index=True` inside
`op.create_table` and then ran an explicit `op.create_index` with the identical
canonical name (`ix_<table>_<column>`). `create_table` honors `index=True`, so
the migration's second statement collided with its first — on Postgres, on
sqlite, on anything. It shipped anyway, because nothing exercises the alembic
chain before promote time: the unit suite builds schema via `create_all`, and
DEF278's docstring records why a run-the-chain guard is impossible here (the
chain contains Postgres-only DDL, and a Postgres-gated test never runs on this
Mac — the DEF038/DEF063 shape). It was caught by the promotion protocol's
migrate-before-swap ordering: alpha-2026-08-20-1 aborted at the migration
step with the old container still serving, exactly as designed after DEF215.

So the guard is static, which runs everywhere: parse every migration file and
fail if an explicit `op.create_index` names an index that the same file's
`op.create_table` already creates via `index=True`, or if two explicit
`create_index` calls in one file mint the same name. This is narrower than
"the chain applies" and that narrowness is deliberate — it is the class that
actually shipped, checked in a way that cannot be skipped.
"""

from __future__ import annotations

import ast
from pathlib import Path

_VERSIONS = Path(__file__).resolve().parents[3] / "backend" / "alembic" / "versions"


def _index_events(func: ast.FunctionDef) -> list[tuple[int, str, str]]:
    """(lineno, 'create'|'drop', index_name) for every index op in one function.

    Scoped per function, because upgrade() and downgrade() are separate apply
    contexts: a drop-and-recreate pair in upgrade() with its mirror in
    downgrade() (ec77766f771d changes an index's uniqueness exactly that way)
    is the normal idiom, not a collision.
    """
    events: list[tuple[int, str, str]] = []
    for node in ast.walk(func):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        attr = node.func.attr
        if attr == "create_table" and node.args:
            table = node.args[0]
            if not (isinstance(table, ast.Constant) and isinstance(table.value, str)):
                continue
            for col in node.args[1:]:
                if not (
                    isinstance(col, ast.Call)
                    and isinstance(col.func, ast.Attribute)
                    and col.func.attr == "Column"
                    and col.args
                ):
                    continue
                name = col.args[0]
                if not (
                    isinstance(name, ast.Constant) and isinstance(name.value, str)
                ):
                    continue
                for kw in col.keywords:
                    if (
                        kw.arg == "index"
                        and isinstance(kw.value, ast.Constant)
                        and kw.value.value is True
                    ):
                        events.append(
                            (node.lineno, "create", f"ix_{table.value}_{name.value}")
                        )
        elif attr in ("create_index", "drop_index") and node.args:
            name = node.args[0]
            if isinstance(name, ast.Constant) and isinstance(name.value, str):
                kind = "create" if attr == "create_index" else "drop"
                events.append((node.lineno, kind, name.value))
    return sorted(events)


def _collisions(source: str) -> list[str]:
    out: list[str] = []
    for node in ast.parse(source).body:
        if not isinstance(node, ast.FunctionDef):
            continue
        live: set[str] = set()
        for _, kind, name in _index_events(node):
            if kind == "create":
                if name in live:
                    out.append(name)
                live.add(name)
            else:
                live.discard(name)
    return out


def test_no_migration_creates_the_same_index_twice():
    offenders: list[str] = []
    for path in sorted(_VERSIONS.glob("*.py")):
        for name in _collisions(path.read_text()):
            offenders.append(f"{path.name}: {name}")
    assert not offenders, (
        "these migrations create an index twice — index=True inside "
        "create_table already creates ix_<table>_<column>, so the explicit "
        "create_index collides at apply time on every engine (DEF337):\n  "
        + "\n  ".join(offenders)
    )


def test_the_detector_sees_def337_itself():
    # Pin the detector against the exact shape that shipped, so a refactor
    # that quietly stops parsing create_table columns fails here, not on the
    # next broken migration.
    broken = """
from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    op.create_table(
        "vllm_cache_samples",
        sa.Column("sampled_at", sa.DateTime(timezone=True), index=True),
    )
    op.create_index(
        "ix_vllm_cache_samples_sampled_at", "vllm_cache_samples", ["sampled_at"],
    )
"""
    assert _collisions(broken) == ["ix_vllm_cache_samples_sampled_at"]


def test_the_detector_allows_the_legitimate_shapes():
    # index=True with no explicit twin, and an explicit index with no
    # index=True twin, are both the normal idiom.
    fine = """
from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    op.create_table(
        "t",
        sa.Column("a", sa.String(), index=True),
        sa.Column("b", sa.String()),
    )
    op.create_index("ix_t_b", "t", ["b"])
"""
    assert _collisions(fine) == []
