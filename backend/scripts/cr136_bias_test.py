"""CR136 F16 bias test (dev script, not a route) — sd of z = daily realised return / (predicted_vol_ann/√252) per portfolio over a date range; acceptance band [0.911, 1.089] at T=252.

This is the institutional check that makes CR136's Tier-1 model auditable rather
than merely plausible. If the engine's predicted volatility is right, realised
returns divided by it have sd ≈ 1. Systematically below 1 means the model is
over-stating risk; above 1 means it is under-stating it, which is the direction
that matters.

Run on melehost:

    docker exec ami_api_alpha python -m scripts.cr136_bias_test
    docker exec ami_api_alpha python -m scripts.cr136_bias_test --start 2026-08-01

The band applies AT T=252. This script prints `n` and never verdicts on a small
sample — quoting a [0.911, 1.089] band against thirty observations would be
exactly the over-confident reading the uncertainty contract exists to prevent.
"""

from __future__ import annotations

import argparse
from datetime import date
from uuid import UUID

from sqlalchemy import select

from app.db import get_session
from app.db.models import PortfolioValueSnapshotRow
from app.services.portfolio_health_constants import BIAS_SD_BAND
from app.services.portfolio_snapshot import SnapshotPoint, bias_z_stats


def _load(
    portfolio_id: UUID | None, start: date | None, end: date | None,
) -> dict[UUID, list[SnapshotPoint]]:
    stmt = select(PortfolioValueSnapshotRow)
    if portfolio_id is not None:
        stmt = stmt.where(PortfolioValueSnapshotRow.portfolio_id == portfolio_id)
    if start is not None:
        stmt = stmt.where(PortfolioValueSnapshotRow.as_of >= start)
    if end is not None:
        stmt = stmt.where(PortfolioValueSnapshotRow.as_of <= end)
    stmt = stmt.order_by(
        PortfolioValueSnapshotRow.portfolio_id, PortfolioValueSnapshotRow.as_of,
    )
    grouped: dict[UUID, list[SnapshotPoint]] = {}
    with get_session() as session:
        for row in session.execute(stmt).scalars():
            grouped.setdefault(row.portfolio_id, []).append(SnapshotPoint(
                as_of=row.as_of,
                total_value=float(row.total_value),
                cash=float(row.cash),
                invested_value=float(row.invested_value),
                drawdown_pct=float(row.drawdown_pct),
                source=row.source,
                predicted_vol_ann=(
                    float(row.predicted_vol_ann)
                    if row.predicted_vol_ann is not None else None
                ),
            ))
    return grouped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--portfolio-id", type=UUID, default=None)
    parser.add_argument("--start", type=date.fromisoformat, default=None)
    parser.add_argument("--end", type=date.fromisoformat, default=None)
    ns = parser.parse_args()

    grouped = _load(ns.portfolio_id, ns.start, ns.end)
    if not grouped:
        print("no snapshot rows matched")
        return 0

    low, high = BIAS_SD_BAND
    print(f"acceptance band for sd(z): [{low}, {high}] — applies AT T=252\n")
    print(f"{'portfolio':38s} {'n':>5s} {'mean_z':>9s} {'sd_z':>9s}  verdict")
    for portfolio_id, points in sorted(grouped.items(), key=lambda kv: str(kv[0])):
        stats = bias_z_stats(points)
        if stats.sd_z is None:
            verdict = "n<2 — nothing to say"
        elif stats.n < 252:
            verdict = f"n={stats.n} < 252 — band does not apply yet"
        elif low <= stats.sd_z <= high:
            verdict = "IN BAND"
        else:
            verdict = "OUT OF BAND"
        mean_z = f"{stats.mean_z:9.4f}" if stats.mean_z is not None else f"{'-':>9s}"
        sd_z = f"{stats.sd_z:9.4f}" if stats.sd_z is not None else f"{'-':>9s}"
        print(f"{str(portfolio_id):38s} {stats.n:5d} {mean_z} {sd_z}  {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
