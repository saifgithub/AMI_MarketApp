"""DEF313 — the sector route reported a `total_value` nothing else agreed with.

`GET /v1/portfolio/sector-allocation/{user}` re-derived `invested + current_cash`
and returned it under the name `total_value`. That is a **different number** from
the one the value card shows: `Portfolio.total_value` carries the short leg
(`cash_posted + (entry − mark) × quantity`) and this did not, so the two
disagreed by exactly that leg whenever a short was open — two derivations of one
fact, DEF098's shape, on the wire. Nothing renders the field today
(`SectorAllocation.totalValue` is parsed and unused), which is why this is a
contract fix made before something starts believing it.

The number now comes off `portfolio_marks_snapshot`, which had already computed
it inside the single `to_thread` hop the route makes and which the route was
discarding as `_total_value`. Calling `p.total_value(marks)` out in the handler
instead — the first attempt — trips the DEF116/DEF120 blocking-IO guard, because
`Portfolio.total_value` and `SimEngine.total_value` are one name to a static
reader and the engine's fans out to the network. The guard is right to be
name-based, and the answer was not to waive it.

## The ring itself stays long-only, and that is a decision with a measurement

The same investigation found the donut cannot see a short at all: a book heavily
long tech and heavily short tech draws the same ring as one with no short, and
opening a short *moves* the ring — the margin posted leaves `current_cash`, so
the denominator shrinks while no slice is added and every long weight rises.

It was built, tested, and then **reverted**, because `sim_short_positions` has
never held a row on Alpha. Making the ring gross forces a second choice, and both
branches cost more than the defect: take the safety floor's sector cap gross too
(a floor behaviour change that can newly reject trades, needing its own CR and an
independent audit), or ship a gross picture beside a long-only verdict, which is
a screen saying "over your cap" next to a floor that allows the trade.

The arithmetic that settles it when a short does exist — short 10 XXX at $100,
against a $1,000 long and $1,500 cash:

| mark | NAV | gross-base ring | NAV-base ring |
|---|---|---|---|
| $80 (winning) | $3,200 | 24.2% | 21.9% |
| $100 (flat) | $3,000 | 28.6% | 16.7% |
| $120 (losing) | $2,800 | **32.4%** | **10.7%** |

The gross base grows the slice as the position turns against the user; the NAV
base shrinks it by a third, so the ring would call a $1,200 obligation against
$2,800 of NAV "mostly cash". Gross is the shape. Not today.
"""

from __future__ import annotations


def _api():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.portfolio import router
    from app.services.auth_service import AuthService

    app = FastAPI()
    app.include_router(router)
    user, token, _ = AuthService().ensure_anonymous(device_user_id=None)
    return TestClient(app, raise_server_exceptions=False), user, token


def test_the_route_reports_the_portfolios_own_total_value():
    """One derivation. The route used to compute `invested + current_cash` under
    the same name the value card uses for `Portfolio.total_value`."""
    client, user, token = _api()
    r = client.get(
        f"/v1/portfolio/sector-allocation/{user.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text

    from app.services.sim_engine import get_sim_engine

    sim = get_sim_engine()
    p, marks, _tv, _dd, _src = sim.portfolio_marks_snapshot(user.id)
    assert r.json()["total_value"] == round(p.total_value(marks), 2)


def test_the_total_is_taken_off_the_snapshot_not_recomputed():
    """Pins the DEF116/DEF120 shape, not just the value.

    `p.total_value(marks)` in the handler body is arithmetically identical and
    trips the blocking-IO guard — `SimEngine.total_value` shares the name and
    does fan out to the network. A future edit that "simplifies" this back would
    pass the test above and fail the guard three hundred tests later, so the
    intent is asserted here, where the reason is written down.
    """
    import inspect

    from app.api import portfolio as route_mod

    src = inspect.getsource(route_mod.sector_allocation)
    # Comments only, stripped — the explanation of the defect names the call it
    # forbids, and a check that could not tell those apart would fail on its own
    # documentation.
    code = "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("#")
    )
    assert "snapshot_total_value" in code
    assert "p.total_value(" not in code


def test_the_ring_is_still_long_only():
    """The reverted half, pinned so it is not half-restored by accident.

    Passing `shorts=` here without also taking the safety floor's sector cap
    gross would put a gross picture beside a long-only verdict. Whoever changes
    this should be changing both, under a CR, with the table in this file's
    docstring in front of them.
    """
    import inspect

    from app.api import portfolio as route_mod

    src = inspect.getsource(route_mod.sector_allocation)
    assert "shorts=" not in src
