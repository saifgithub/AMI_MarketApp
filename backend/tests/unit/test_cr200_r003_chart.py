"""CR200-R003 — /v1/admin/chart.svg: get_admin gate, series whitelist,
day bounds, SVG shape, and the renderer's honest empty-state vs flat-zero
distinction (CR040 — an all-zero series is data, never a fake "no data").
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.admin_chart import router as admin_chart_router
from app.core.config import settings
from app.services import chart_svg

_SECRET = "test-admin-secret-cr200-r003"
_HDR = {"Authorization": f"Bearer {_SECRET}"}

_VALID_SERIES = ("signups", "active_users", "room_runs", "credits_spent")


@pytest.fixture(autouse=True)
def _set_admin_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "admin_secret", _SECRET)


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(admin_chart_router)
    return TestClient(app, raise_server_exceptions=False)


def _polyline_points(svg: str) -> list[str]:
    root = ET.fromstring(svg)
    for el in root.iter():
        if el.tag.endswith("polyline"):
            return el.attrib["points"].split()
    raise AssertionError("no <polyline> in SVG")


# ── Gating ───────────────────────────────────────────────────────────────────


def test_no_auth_rejected(client: TestClient) -> None:
    # get_admin raises 403 (not 401) for missing/invalid credentials — the
    # CR200 gate's actual behaviour, same as every other /v1/admin route.
    assert client.get("/v1/admin/chart.svg", params={"series": "signups"}).status_code == 403
    assert (
        client.get(
            "/v1/admin/chart.svg",
            params={"series": "signups"},
            headers={"Authorization": "Bearer nope"},
        ).status_code
        == 403
    )


# ── Happy path + validation ──────────────────────────────────────────────────


def test_happy_path_svg_shape(client: TestClient) -> None:
    r = client.get(
        "/v1/admin/chart.svg",
        params={"series": "signups", "days": 30},
        headers=_HDR,
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/svg+xml"
    svg = r.text
    root = ET.fromstring(svg)  # parses as XML
    assert root.tag.endswith("svg")
    assert "signups" in svg
    points = _polyline_points(svg)
    assert len(points) == 30  # one vertex per day
    assert "no data" not in svg


@pytest.mark.parametrize("series", _VALID_SERIES)
def test_each_valid_series_accepted(client: TestClient, series: str) -> None:
    r = client.get(
        "/v1/admin/chart.svg",
        params={"series": series, "days": 7},
        headers=_HDR,
    )
    assert r.status_code == 200
    assert len(_polyline_points(r.text)) == 7


def test_unknown_series_422(client: TestClient) -> None:
    r = client.get(
        "/v1/admin/chart.svg",
        params={"series": "mrr"},
        headers=_HDR,
    )
    assert r.status_code == 422


@pytest.mark.parametrize("days", [0, 366])
def test_days_out_of_bounds_422(client: TestClient, days: int) -> None:
    r = client.get(
        "/v1/admin/chart.svg",
        params={"series": "signups", "days": days},
        headers=_HDR,
    )
    assert r.status_code == 422


def test_empty_database_zero_series_is_honest_flat_line(client: TestClient) -> None:
    # The isolated test DB has no rows, so every series comes back all-zero —
    # real data, which must render a polyline, never the "no data" state.
    r = client.get(
        "/v1/admin/chart.svg",
        params={"series": "room_runs", "days": 14},
        headers=_HDR,
    )
    assert r.status_code == 200
    svg = r.text
    assert "no data" not in svg
    points = _polyline_points(svg)
    assert len(points) == 14
    ys = {p.split(",")[1] for p in points}
    assert len(ys) == 1  # flat line


# ── Renderer unit tests ──────────────────────────────────────────────────────


def test_renderer_empty_inputs_render_no_data_state() -> None:
    for labels, values in ([[], []], [[], [1]], [["a"], []]):
        svg = chart_svg.render_line_chart("t", labels, values)
        assert "no data" in svg
        assert "<polyline" not in svg
        ET.fromstring(svg)


def test_renderer_empty_state_carries_title() -> None:
    svg = chart_svg.render_line_chart("signups (last 30 days)", [], [])
    assert "signups (last 30 days)" in svg
    assert "no data" in svg


def test_renderer_length_mismatch_raises() -> None:
    with pytest.raises(ValueError):
        chart_svg.render_line_chart("t", ["a", "b"], [1])


def test_renderer_all_zero_series_is_flat_line_data() -> None:
    svg = chart_svg.render_line_chart("t", ["a", "b", "c"], [0, 0, 0])
    assert "no data" not in svg
    points = _polyline_points(svg)
    assert len(points) == 3
    ys = {p.split(",")[1] for p in points}
    assert len(ys) == 1
    assert "max 0" in svg and "min 0" in svg


def test_renderer_min_max_annotated() -> None:
    svg = chart_svg.render_line_chart("t", ["a", "b", "c"], [3, 9, 1])
    assert "max 9" in svg
    assert "min 1" in svg


def test_renderer_x_labels_first_and_last() -> None:
    svg = chart_svg.render_line_chart("t", ["2026-09-01", "2026-09-02", "2026-09-03"], [1, 2, 3])
    assert "2026-09-01" in svg
    assert "2026-09-03" in svg
    assert "2026-09-02" not in svg  # sparse X labels


def test_renderer_is_deterministic() -> None:
    labels = [f"2026-09-{d:02d}" for d in range(1, 31)]
    values = list(range(30))
    assert chart_svg.render_line_chart("t", labels, values) == (
        chart_svg.render_line_chart("t", labels, values)
    )


def test_renderer_escapes_title() -> None:
    svg = chart_svg.render_line_chart("a<b", ["x"], [1])
    assert "a<b" not in svg
    assert "a&lt;b" in svg
