"""Admin chart API — /v1/admin/chart/* (CR200-R003).

Server-rendered SVG charts for the conversational admin agent: the agent
embeds the endpoint URL as an image link in chat so time-series questions
("show me signups for the last 30 days") get a real chart instead of a
markdown table. Series come from the existing admin_analytics.timeseries()
queries — this router is pure glue, no new business logic (CR200-R003 §5.1).

Endpoint map:
  GET /v1/admin/chart.svg?series=<name>&days=30   SVG line chart
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response

from app.api.admin import get_admin
from app.services import admin_analytics, chart_svg

router = APIRouter(
    prefix="/v1/admin",
    tags=["admin"],
    dependencies=[Depends(get_admin)],
)

ChartSeries = Literal["signups", "active_users", "room_runs", "credits_spent"]


@router.get("/chart.svg")
def admin_chart_svg(
    series: Annotated[
        ChartSeries, Query(description="timeseries key from admin_analytics.timeseries()")
    ],
    days: int = Query(default=30, ge=1, le=365),
) -> Response:
    ts = admin_analytics.timeseries(days=days)
    svg = chart_svg.render_line_chart(
        title=f"{series} (last {days} days)",
        labels=ts["days"],
        values=ts[series],
    )
    return Response(content=svg, media_type="image/svg+xml")
