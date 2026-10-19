"""UAT area: games, dark-launched contract (CR263, cases/games.yaml)."""

import uuid

import pytest


@pytest.mark.uat("UAT-GAME-001")
def test_games_gated_and_dark(api):
    for path in ("/v1/games/cadences", "/v1/games/runs", "/v1/games/record", "/v1/games/desks",
                 "/v1/games/record/prs"):
        assert api.get(path).status_code == 401, path
    assert api.post("/v1/games/enter", json={}).status_code == 401
    spec = api.get("/openapi.json")
    if spec.status_code == 200:
        assert not [p for p in spec.json()["paths"] if p.startswith("/v1/games")]


@pytest.mark.uat("UAT-GAME-002")
def test_game_read_contracts(seed):
    u = seed.user(plan="floor_pass")
    cad = u.get("/v1/games/cadences")
    assert cad.status_code == 200
    week = next(c for c in cad.json() if c["cadence"] == "week")
    assert week["state"] and week["deadline"]
    assert week["already_held"] is False

    desks = u.get("/v1/games/desks")
    assert desks.status_code == 200 and desks.json()
    for d in desks.json():
        assert d["key"] and d["name"] and d["rule"] and d["universe"]

    rec = u.get("/v1/games/record").json()
    assert rec["career_points_net"] == 0
    assert rec["title"] == "apprentice"
    assert rec["finished_count"] == 0
    prs = u.get("/v1/games/record/prs").json()
    assert prs["has_any_finished_runs"] is False
    assert all(v is None for k, v in prs.items() if k.startswith(("best_", "longest_")))


@pytest.mark.uat("UAT-GAME-003")
def test_enter_once_and_runs_are_private(seed):
    a = seed.user(plan="floor_pass")
    b = seed.user(plan="floor_pass")
    before = seed.detail(a)["credit_balance"]

    r = a.post("/v1/games/enter", json={})
    assert r.status_code == 200
    run_id = r.json()["run_id"]
    assert r.json()["state"] == "entered"
    assert seed.detail(a)["credit_balance"] == before
    assert a.post("/v1/games/enter", json={}).status_code == 409

    runs = a.get("/v1/games/runs").json()
    assert [x["run_id"] for x in runs] == [run_id]
    assert a.get(f"/v1/games/runs/{run_id}").status_code == 200
    assert b.get("/v1/games/runs").json() == []

    ghost = str(uuid.uuid4())
    for path in (f"/v1/games/runs/{run_id}", f"/v1/games/runs/{run_id}/close", f"/v1/games/runs/{ghost}"):
        assert b.get(path).status_code == 404, path
    steal = b.post(f"/v1/games/runs/{run_id}/trade", json={"ticker": "AAPL", "quantity": 1})
    assert steal.status_code in (403, 404, 409)


@pytest.mark.uat("UAT-GAME-004")
def test_invalid_trades_refused(seed):
    u = seed.user(plan="floor_pass")
    run_id = u.post("/v1/games/enter", json={}).json()["run_id"]
    trade = f"/v1/games/runs/{run_id}/trade"
    for body in (
        {"ticker": "AAPL", "quantity": 0},
        {"ticker": "AAPL", "quantity": -3},
        {"ticker": "ZZZZNOTATICKER", "quantity": 1},
    ):
        assert u.post(trade, json=body).status_code == 422, body
    quote = f"{trade}/quote"
    assert u.post(quote, json={"ticker": "AAPL"}).status_code == 422
    assert u.post(quote, json={"ticker": "AAPL", "quantity": 1, "notional": 100}).status_code == 422
    orders = u.get(f"/v1/games/runs/{run_id}/orders")
    assert orders.status_code == 200
    body = orders.json()
    queued = body if isinstance(body, list) else body.get("orders", body.get("queued", []))
    assert queued == []
