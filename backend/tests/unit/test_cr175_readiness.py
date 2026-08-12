"""CR175 Tier A — the promotion's success signal must be able to fail.

`/v1/health` returns a hardcoded literal and is simultaneously the container
healthcheck and (until this CR) `/promote-to-alpha`'s primary smoke check. So
every promotion's "green" was a constant. DEF215's outage state — schema behind
head, migrations never run, live journal reads failing — is a state that
endpoint returns 200 for.

The load-bearing test here is `test_schema_behind_head_*`: it drives the DEF215
condition and asserts **both halves** — `/v1/health` still 200 (proving the old
signal was blind, not merely weak) and `/v1/ready` 503. A guard nobody has seen
fail is not known to work, so each probe is exercised against a broken state
rather than only against a healthy one.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.services import readiness

_ADMIN = {"Authorization": "Bearer test-admin-secret"}


@pytest.fixture
def client() -> TestClient:
    from app.main import app

    return TestClient(app, raise_server_exceptions=False)


def test_health_is_liveness_only_and_stays_200_when_everything_is_broken(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The blindness itself, asserted — this is F1, not a hypothetical.

    Every gating probe is forced to fail and `/v1/health` still answers 200 with
    `status: ok`. That is exactly what the container healthcheck and the old
    smoke check were reading.
    """
    monkeypatch.setattr(
        readiness, "_probe_db",
        lambda: readiness.Probe("db", ok=False, gating=True, detail={"error": "OperationalError"}))
    monkeypatch.setattr(
        readiness, "_probe_schema",
        lambda: readiness.Probe("schema", ok=False, gating=True,
                                detail={"current_revision": "old", "head_revision": "new"}))

    health = client.get("/v1/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    ready = client.get("/v1/ready")
    assert ready.status_code == 503
    assert set(ready.json()["failed_probes"]) == {"db", "schema"}


def test_schema_behind_head_fails_ready_and_names_both_revisions(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DEF215's exact condition. The revisions must be in the body: an operator
    reading `ready: false` needs to know which migration never ran, which is the
    whole difference between this and an `UndefinedColumn` traceback.

    Authenticated, because the revision ids are the privileged half — the
    anonymous view carries the verdict and the probe names only."""
    monkeypatch.setattr(settings, "admin_secret", "test-admin-secret")
    monkeypatch.setattr(
        readiness, "_probe_schema",
        lambda: readiness.Probe("schema", ok=False, gating=True,
                                detail={"current_revision": "abc123", "head_revision": "def456"}))

    resp = client.get("/v1/ready", headers=_ADMIN)
    assert resp.status_code == 503
    body = resp.json()
    assert body["ready"] is False
    assert "schema" in body["failed_probes"]
    schema = next(p for p in body["probes"] if p["name"] == "schema")
    assert schema["current_revision"] == "abc123"
    assert schema["head_revision"] == "def456"


def test_schema_at_head_passes(client: TestClient) -> None:
    """The sqlite fixture stamps itself to head via `init_schema()`, so the real
    probe — not a monkeypatched one — must agree."""
    probe = readiness._probe_schema()
    assert probe.ok, probe.detail
    assert probe.gating is True


def test_mock_llm_provider_is_gating_in_staging_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DEF059: with no real provider the Room fell through to a confident fake
    APPROVE. Shipping a container whose gateway resolves to `mock` has shipped
    that. But `local` runs on the mock deliberately, so gating there would make
    every developer's readiness endpoint red and train them to ignore it."""
    class _Gateway:
        def status(self) -> dict[str, object]:
            return {"active_provider": "mock", "has_real_provider": False}

    monkeypatch.setattr(
        "app.services.llm_gateway.get_llm_gateway", lambda: _Gateway())

    assert readiness._probe_llm("staging").gating is True
    assert readiness._probe_llm("staging").ok is False
    assert readiness._probe_llm("local").gating is False


def test_a_probe_that_raises_reports_instead_of_500ing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A readiness endpoint that 500s tells the operator less than one that
    names the dependency that is down.

    The DB is made to raise at the point `_probe_db` actually touches it, so
    this exercises the probe's own except-branch rather than a stand-in for it.
    """
    def _boom(*_a: object, **_k: object) -> None:
        raise ConnectionRefusedError("connection refused")

    monkeypatch.setattr("app.db.get_session", _boom)

    probe = readiness._probe_db()
    assert probe.ok is False
    assert probe.gating is True
    assert probe.detail["error"] == "ConnectionRefusedError"

    resp = client.get("/v1/ready")
    assert resp.status_code == 503
    assert "db" in resp.json()["failed_probes"]


def test_redis_is_reported_but_never_gates(monkeypatch: pytest.MonkeyPatch) -> None:
    """`redis_url` is configured, `redis>=5.2` is a main dependency, and compose
    blocks api-alpha on `redis: condition: service_healthy` — but no application
    code opens a connection. Failing a promotion over an unused service would be
    a check that fires without meaning anything."""
    probe = readiness._probe_redis()
    assert probe.gating is False
    assert probe.detail["opened_by_app_code"] is False


def test_unstamped_build_is_reported_but_does_not_gate_readiness(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unstamped container is a promotion-protocol failure, caught by
    postflight comparing the sha it promoted. Making it a readiness failure
    would brick a hand-started container over a diagnostic field."""
    monkeypatch.setattr(settings, "admin_secret", "test-admin-secret")
    resp = client.get("/v1/ready", headers=_ADMIN)
    body = resp.json()
    assert body["git_sha"] == "unset"
    assert body["deploy_stamped"] is False
    assert "git_sha" not in body["failed_probes"]


def test_health_version_is_the_build_stamp_not_a_constant(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The old `"version": "0.1.0"` never moved and sat exactly where an
    operator looks for a deploy identity."""
    monkeypatch.setattr(settings, "git_sha", "deadbeef", raising=False)
    monkeypatch.setattr(settings, "alpha_tag", "alpha-2026-08-12-9", raising=False)

    body = client.get("/v1/health").json()
    assert body["version"] == "deadbeef"
    assert body["alpha_tag"] == "alpha-2026-08-12-9"
    assert body["version"] != "0.1.0"


def test_ready_withholds_operational_detail_from_anonymous_callers(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CR123 C2 gated `/v1/llm/status` because provider config disclosure to
    anonymous callers is a real finding. Revision ids, the build stamp and the
    provider name are the same category, so they need the bearer — while the
    verdict itself stays callable by a platform probe."""
    monkeypatch.setattr(settings, "admin_secret", "test-admin-secret")

    anon = client.get("/v1/ready").json()
    assert set(anon) == {"ready", "env", "failed_probes"}
    assert "git_sha" not in anon
    assert "probes" not in anon

    priv = client.get(
        "/v1/ready", headers={"Authorization": "Bearer test-admin-secret"},
    ).json()
    assert "git_sha" in priv
    assert "probes" in priv
    assert any(p["name"] == "schema" for p in priv["probes"])


def test_wrong_bearer_gets_the_anonymous_view_not_a_403(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A readiness probe must answer even when the caller cannot authenticate —
    403ing a platform health probe would make the endpoint unusable for the job
    it exists to do."""
    monkeypatch.setattr(settings, "admin_secret", "test-admin-secret")
    r = client.get("/v1/ready", headers={"Authorization": "Bearer wrong"})
    assert r.status_code in (200, 503)
    assert set(r.json()) == {"ready", "env", "failed_probes"}
