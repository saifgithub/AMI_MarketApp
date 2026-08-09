"""CR109 slice 2 — the dark-launch requirement.

`main.py` sets `docs_url="/docs" if settings.env != "prod" else None` and
leaves `openapi_url` at its default, so on Alpha both `/docs` and
`/openapi.json` serve. Without `include_in_schema=False` on the games
router, the entire games API is PUBLISHED with schemas while it is
supposed to be dark. This is the one test standing between "dark" and
"discoverable by anyone who loads /docs".
"""

from __future__ import annotations


def test_no_games_path_appears_in_the_openapi_schema():
    from app.main import app

    schema = app.openapi()
    games_paths = [p for p in schema.get("paths", {}) if p.startswith("/v1/games")]
    assert games_paths == [], (
        f"CR109 slice 2's games API leaked into the OpenAPI schema: {games_paths}. "
        "The router must be registered with include_in_schema=False."
    )


def test_games_router_itself_declares_include_in_schema_false():
    """Belt-and-braces at the router-declaration level — catches the
    mistake even before `app.openapi()` is consulted."""
    from app.api.games import router

    assert router.include_in_schema is False
