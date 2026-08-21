"""DEF145 — AMI never places an order on a user's brokerage account.

DEF145 asked for a sim stop/target close to propagate to a linked Alpaca paper
account. It is closed `wontfix`, because doing it would cross a **locked
decision**, not because it is hard:

> *"Endpoint of the journey: **Training simulator, simulation-only, forever.**
> AMI is not licensed to give investment advice; **no brokerage integration
> ever.**"* — CLAUDE.md

A paper account is still a real brokerage API, and writing to it would be the
first order AMI ever placed on a user's behalf. `room_runner._compose_portfolio_
block` already labels a linked account an *"informational overlay only — NOT
AMI's portfolio of record"*; propagating closes would make that overlay
authoritative in one direction while staying informational in the other.

**This file is why the closure is done rather than merely decided.** The rule
lived in a markdown table, and CR040's house lesson is that a rule which is only
written down is not a control. The check is exact rather than a floor: every
HTTP call the module makes is pinned by (function, verb), so the next one fails
the build until someone has read this docstring and formed a view — including
the honest case where Saiful decides to revisit the locked decision, which
should be a deliberate edit here and not a quiet new function.

**CR202 strengthened what this pins, and this is that deliberate edit.** The
read path (`_paper_get`, and the four public getters over it) is gone, because
the credential it needed is gone: a user's Alpaca key now lives on their device
and never reaches this host. The property is therefore no longer "the backend
only ever READS a user's brokerage account" but the strictly stronger "the
backend makes **no authenticated call to a user's brokerage account at all**,
and holds no credential with which it could." Removing `_paper_get` from the
pin turned this test red first, exactly as designed — the pin is exact in both
directions, so a shrinking surface is as loud as a growing one.

The single POST that remains is the OAuth token exchange, which sends an
authorization code to Alpaca's *auth* host to obtain a token. It reads nothing
and writes nothing on the account, and its caller hands the token straight back
to the device rather than storing it. It is kept because Alpaca's token
endpoint requires `client_secret` and documents no PKCE, so that one exchange
is the only part of OAuth that cannot run on the device.
"""

from __future__ import annotations

import ast
from pathlib import Path

_MODULE = Path(__file__).resolve().parents[2] / "app" / "services" / "alpaca_service.py"

# (enclosing function, httpx verb). Exact — not a floor.
_ALLOWED_CALLS = {
    ("exchange_code", "post"),  # OAuth token exchange, against the auth host
}

_WRITE_WORDS = (
    "submit", "place", "close_position", "cancel", "order", "liquidate",
    "sell", "buy", "patch", "delete", "replace",
)


def _http_calls() -> set[tuple[str, str]]:
    """Every `httpx.<verb>(...)` in the module, tagged with its function."""
    tree = ast.parse(_MODULE.read_text(encoding="utf-8"))
    calls: set[tuple[str, str]] = set()
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(fn):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "httpx"
            ):
                calls.add((fn.name, node.func.attr))
    return calls


def test_the_alpaca_client_makes_exactly_the_calls_it_is_allowed_to():
    found = _http_calls()

    new = found - _ALLOWED_CALLS
    assert new == set(), (
        f"new HTTP call(s) in alpaca_service.py: {sorted(new)}. AMI is "
        "simulation-only by locked decision and places no order on a user's "
        "brokerage account, paper or otherwise (DEF145). If that decision has "
        "changed, change it here and in the decision log — not by adding a "
        "function."
    )

    gone = _ALLOWED_CALLS - found
    assert gone == set(), (
        f"pinned call(s) no longer present: {sorted(gone)}. Delete them from "
        "the pin — a stale entry hides the next real one."
    )


def test_no_public_function_reads_as_a_write():
    """The second door: a write that goes out through some other client — a
    vendor SDK, a helper module — would not be an `httpx` call and the pin above
    would not see it. The name is the cheap second signal."""
    tree = ast.parse(_MODULE.read_text(encoding="utf-8"))
    offenders = [
        n.name
        for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and any(w in n.name.lower() for w in _WRITE_WORDS)
    ]
    assert not offenders, (
        f"alpaca_service.py grew a function that reads as a write: {offenders}. "
        "See DEF145 and CLAUDE.md's locked decision."
    )


def test_nothing_in_the_backend_calls_an_alpaca_order_endpoint():
    """Corpus-wide, because the call site need not live in the service module."""
    app_dir = _MODULE.parents[1]
    offenders = []
    for path in sorted(app_dir.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for marker in ("/v2/orders", "/v2/positions/"):
            if marker in text:
                offenders.append((str(path.relative_to(app_dir)), marker))
    assert not offenders, (
        f"an Alpaca order/position-close endpoint is referenced: {offenders}"
    )
