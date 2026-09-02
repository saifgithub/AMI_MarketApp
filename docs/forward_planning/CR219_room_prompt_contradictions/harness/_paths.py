"""Path + import bootstrap shared by every harness script.

Every script in this folder must run from ANY working directory (the
`../evidence/` convention), so nothing here may assume a CWD. Paths are derived
from THIS file's own location before any `chdir`.

`bootstrap()` puts the repo's `backend/` on `sys.path` and chdirs into it —
`app.core.config` reads relative paths at import time, so the chdir has to
happen before the first `app.*` import, exactly as `evidence/convene_gemini.py`
does it.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CR_DIR = os.path.abspath(os.path.join(HERE, ".."))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
BACKEND = os.path.join(REPO_ROOT, "backend")
EVIDENCE = os.path.join(CR_DIR, "evidence")
PROFILES = os.path.join(HERE, "profiles")
RESULTS = os.path.join(HERE, "results")


def bootstrap() -> None:
    """Make `app.*` importable and chdir into backend/. Idempotent."""
    for p in (HERE, BACKEND, os.path.join(BACKEND, "tests", "unit")):
        if p not in sys.path:
            sys.path.insert(0, p)
    if os.path.abspath(os.getcwd()) != os.path.abspath(BACKEND):
        os.chdir(BACKEND)
