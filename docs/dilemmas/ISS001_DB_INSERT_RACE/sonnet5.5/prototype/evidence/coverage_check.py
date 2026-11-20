import ast, sys, pathlib, json, collections
sys.path.insert(0, "backend")
from app.db import models  # noqa
from app.db.base import Base
sys.path.insert(0, "docs/dilemmas/ISS001_DB_INSERT_RACE/sonnet5.5/prototype")
import ami_claim as ac

coll_tables = ac.collidable_tables(Base.metadata)
cls2tbl = {m.class_.__name__: m.local_table.name for m in Base.registry.mappers}
coll_cls = {c for c, t in cls2tbl.items() if t in coll_tables}
d = json.load(open("docs/dilemmas/ISS001_DB_INSERT_RACE/sonnet5.5/prototype/evidence/suite_dryrun.json"))
fired = {(t, s.split(":")[0].replace("app/", "")): n for t, v in d["tripwire"].items() for s, n in v.items() if s != "<test-only>"}
fired_tables_files = {(t, f) for (t, f) in fired}

sites = []
for p in pathlib.Path("backend/app").rglob("*.py"):
    if p.name == "models.py":
        continue
    tree = ast.parse(p.read_text())
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in coll_cls:
            sites.append((n.func.id, str(p.relative_to("backend/app")), n.lineno))
hit = [s for s in sites if (cls2tbl[s[0]], s[1]) in fired_tables_files]
miss = [s for s in sites if (cls2tbl[s[0]], s[1]) not in fired_tables_files]
print("constructor sites of collidable models:", len(sites), " executed by the suite:", len(hit), " never executed:", len(miss))
for s in miss:
    print("  NEVER", s)
