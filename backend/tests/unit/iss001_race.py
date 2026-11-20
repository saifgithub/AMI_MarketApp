"""ISS001 Phase 3 test helper — make a site's `claim()` LOSE the insert race, deterministically.

`claim()` does not SELECT first, so the only race window is "another transaction commits the same
key before our INSERT". `winner_commits_first` wraps the `claim` name the site under test imported:
the first call for `model` commits the winner's row from a SEPARATE session (its own connection),
then runs the real claim, which hits ON CONFLICT and returns the winner's row with
`created=False`. That is exactly the loser's path, with no timing involved.

Postgres semantics of the same path are covered by `backend/scripts/iss001_pg_concurrency.py`.
"""

from __future__ import annotations

from typing import Any

from app.db import ami_claim, get_session


def winner_commits_first(
    monkeypatch,
    module: Any,
    model: type,
    *,
    winner_values: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Patch `module.claim`. Returns a dict: `fired` (the race was staged) and `winner_id`."""
    real = module.claim
    state: dict[str, Any] = {"fired": False, "winner_id": None}

    def wrapper(session, m, *, key, values=None, **kw):
        if m is model and not state["fired"]:
            state["fired"] = True
            with get_session() as other:
                winner = ami_claim.claim(other, model, key=dict(key), values=dict(winner_values or {})).or_skip()
                state["winner_id"] = winner.id
        return real(session, m, key=key, values=values, **kw)

    monkeypatch.setattr(module, "claim", wrapper)
    return state
