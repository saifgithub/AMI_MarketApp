"""CR200 — admin console shell: /admin serves the versioned shell and the
static mount resolves every module file the shell references.

Guards the modularization contract: a <script src="/admin/static/X?v=…">
in admin.html whose file does not exist under static/admin/ would 404 in
the browser and silently break a tab — this test fails instead.
"""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


def test_admin_shell_serves_with_version_stamp() -> None:
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/admin")
    assert r.status_code == 200
    assert "__V__" not in r.text
    assert f"?v={settings.git_sha}" in r.text


def test_every_referenced_static_asset_resolves() -> None:
    client = TestClient(app, raise_server_exceptions=False)
    shell = client.get("/admin").text
    refs = re.findall(r"/admin/static/([\w.]+)\?v=", shell)
    assert refs, "shell references no static assets — extraction broken?"
    for name in refs:
        r = client.get(f"/admin/static/{name}")
        assert r.status_code == 200, f"/admin/static/{name} -> {r.status_code}"


def test_each_view_module_registers_itself() -> None:
    client = TestClient(app, raise_server_exceptions=False)
    shell = client.get("/admin").text
    views = [
        n for n in re.findall(r"/admin/static/([\w.]+\.js)\?v=", shell)
        if n != "core.js"
    ]
    assert views, "shell references no view modules"
    for name in views:
        body = client.get(f"/admin/static/{name}").text
        assert "registerView(" in body, f"{name} never registers its tab"
