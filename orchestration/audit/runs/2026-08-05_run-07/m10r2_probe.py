"""M10 r2 audit — re-run MY round-1 A1 construction against the fix: a filtered
spot-check must now value identically to the unfiltered run it is checking."""
from __future__ import annotations

from app.db.session import get_sessionmaker

from tests.unit.test_cr136_backfill import (
    _GRID, _portfolio, _provider, _trade, _flat, _holding, main,
)
from app.db.models import PortfolioValueSnapshotRow
from sqlalchemy import select


def _rows(pid):
    with get_sessionmaker()() as s:
        return [
            (r.as_of, float(r.total_value), float(r.cash), float(r.invested_value))
            for r in s.execute(
                select(PortfolioValueSnapshotRow)
                .where(PortfolioValueSnapshotRow.portfolio_id == pid)
                .order_by(PortfolioValueSnapshotRow.as_of)
            ).scalars().all()
        ]


def _seed():
    """A: trades on day 0 (sets the run-global earliest).
    B: holds ZZZ, first trade on day 5; ZZZ's bars STOP at day 2."""
    with get_sessionmaker()() as s:
        a = _portfolio(s, cash=9000.0)
        _trade(s, a, ticker="AAA", side="buy", qty=10, price=100.0, opened=_GRID[0])
        _holding(s, a, ticker="AAA", qty=10, avg_cost=100.0)
        b = _portfolio(s, cash=9000.0)
        _trade(s, b, ticker="ZZZ", side="buy", qty=10, price=100.0, opened=_GRID[5])
        _holding(s, b, ticker="ZZZ", qty=10, avg_cost=100.0)
        s.commit()
        return a.id, b.id, b.user_id


def test_spot_check_now_matches_the_run_it_checks(capsys) -> None:
    a_id, b_id, b_user = _seed()
    provider = _provider(
        AAA=_flat(_GRID, 100.0),
        ZZZ=_flat(_GRID[:3], 200.0),      # bars stop before B's first trade
    )

    assert main(["--user-id", str(b_user)], provider=provider) == 0
    spot = capsys.readouterr().out
    spot_days = [ln for ln in spot.splitlines() if ln.strip().startswith("2026-")]

    assert main(["--apply"], provider=_provider(
        AAA=_flat(_GRID, 100.0), ZZZ=_flat(_GRID[:3], 200.0),
    )) == 0
    capsys.readouterr()
    written = _rows(b_id)

    print("\n--- spot-check --user-id B (dry run) ---")
    for ln in spot_days:
        print("   ", ln.strip())
    print("--- what --apply actually wrote for B ---")
    for as_of, total, cash, invested in written:
        print(f"    {as_of}  total {total:>10.2f}  cash {cash:>9.2f}  invested {invested:>9.2f}")

    spot_totals = [ln.split()[1] for ln in spot_days]
    written_totals = [f"{t:.2f}" for _d, t, _c, _i in written]
    print(f"\nspot totals   : {spot_totals}")
    print(f"written totals: {written_totals}")
    print(f"AGREE         : {spot_totals == written_totals}")
    assert spot_totals == written_totals

    print(f"\nfetch starts requested: {sorted({(t, str(s)) for t, s in provider.calls})}")


def test_ledger_priced_is_now_surfaced(capsys) -> None:
    """m3 — a book valued off execution prices must say so in the summary."""
    with get_sessionmaker()() as s:
        p = _portfolio(s, cash=9000.0)
        _trade(s, p, ticker="QQQ", side="buy", qty=10, price=100.0, opened=_GRID[0])
        _holding(s, p, ticker="QQQ", qty=10, avg_cost=100.0)
        s.commit()
    code = main(["--user-id", str(p.user_id)], provider=_provider(QQQ=[]))
    out = capsys.readouterr().out
    print(f"\nexit={code}")
    for ln in out.splitlines():
        if "ledger" in ln.lower() or "!!" in ln or "terminal" in ln.lower():
            print("   ", ln.strip())
