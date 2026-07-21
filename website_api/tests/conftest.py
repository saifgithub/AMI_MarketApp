"""Shared test fixtures — sqlite tempfile DB + per-test rate-limiter reset.

No Postgres required. Each test gets a fresh sqlite file (tables auto-created by
`Base.metadata.create_all` on engine init) and the in-process rate limiters are
cleared so counts don't leak across tests.
"""

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _sqlite_db(tmp_path):
    db_file = tmp_path / "test_website.db"
    os.environ["WEBSITE_TEST_DATABASE_URL"] = f"sqlite:///{db_file}"

    import app.db.session as sess
    sess._engine = None
    sess._SessionLocal = None

    from app.services import rate_limit as rl
    rl.concierge_rate_limit.reset()
    rl.contact_rate_limit.reset()
    rl.data_request_rate_limit.reset()

    yield

    sess._engine = None
    sess._SessionLocal = None
    os.environ.pop("WEBSITE_TEST_DATABASE_URL", None)


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)
