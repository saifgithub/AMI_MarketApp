"""ISS001 verify — derive the collidable-model registry from the REAL schema.

Runs the derivation proposed in SOLUTION.md against `backend/app/db/models.py`
itself and prints the set. The AST guard's measured count is 32 collidable
models; this must agree, and it must keep agreeing as models are added —
that is the property the AST parse cannot have (it re-derives its OWN
approximation of the schema; this reads the schema).

Run from anywhere:
    backend/.venv/bin/python docs/dilemmas/ISS001_DB_INSERT_RACE/kimi-k2/verify_registry.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[3] / "backend"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("AMI_TEST_DATABASE_URL", "sqlite:///:memory:")

from sqlalchemy import Integer, UniqueConstraint  # noqa: E402

from app.db.base import Base  # noqa: E402
import app.db.models  # noqa: E402,F401 — registers every mapper


def derive_collidable(metadata) -> dict[str, list[tuple[str, ...]]]:
    """UniqueConstraint, unique Index, unique=True column, or a defaultless
    (natural) primary key. uuid4-defaulted and autoincrement PKs cannot
    collide client-side and are excluded."""
    out: dict[str, list[tuple[str, ...]]] = {}
    for table in metadata.tables.values():
        keys: set[tuple[str, ...]] = set()
        for c in table.constraints:
            if isinstance(c, UniqueConstraint):
                keys.add(tuple(sorted(col.name for col in c.columns)))
        for idx in table.indexes:
            if idx.unique:
                keys.add(tuple(sorted(col.name for col in idx.columns)))
        for col in table.columns:
            if col.unique:
                keys.add((col.name,))
        pk = list(table.primary_key.columns)
        if (
            pk
            and all(c.default is None and c.server_default is None for c in pk)
            and not (
                len(pk) == 1
                and isinstance(pk[0].type, Integer)
                and pk[0].autoincrement in (True, "auto")
            )
        ):
            keys.add(tuple(sorted(c.name for c in pk)))
        if keys:
            out[table.name] = sorted(keys)
    return out


def main() -> int:
    collidable = derive_collidable(Base.metadata)
    print(f"tables inspected: {len(Base.metadata.tables)}")
    print(f"collidable tables derived: {len(collidable)} (AST guard's measured count: 32)")
    for name, keys in sorted(collidable.items()):
        print(f"  {name}: {keys}")
    users_keys = collidable.get("users", [])
    print()
    print(f"users collision keys: {users_keys}")
    print("note: apple_id / google_id / device_user_id are NOT among them —")
    print("two inventory sites in the brief cannot even raise; they duplicate silently.")
    return 0 if len(collidable) == 32 else 1


if __name__ == "__main__":
    sys.exit(main())
