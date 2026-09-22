"""DEF145 — the AMI *backend* never places an order on a user's brokerage account.

DEF145 asked for a sim stop/target close to propagate to a linked Alpaca paper
account. It was closed `wontfix` against the old absolute rule ("no brokerage
integration ever," no paper/live distinction). **D-071 (2026-09-22, CR227)**
narrowed that rule: AMI may route an order to a linked brokerage account when
it is confirmed **paper**, checked by endpoint (`baseUrl`), never by label. A
live/production account is still strictly forbidden from ever receiving an
order — that half of DEF145's concern is unchanged and this file still pins it.

**What CR227 does NOT change about this file.** The order call itself is
mobile-side by design (CR227 scope point 3 — "mobile places the Alpaca order
directly," preserving CR202's device-local credential custody). The backend
never receives the Alpaca key/secret and gains **no new code path** to
`/v2/orders` — its only job for the Alpaca-paper leg is the same mandate/
compliance verdict it already produces for a sim order, via the existing
`/v1/sim/preview` endpoint. So the backend's posture pinned here — no
authenticated write to any Alpaca account, paper or live — is **unchanged**,
even though a paper order can now be placed elsewhere (from the device). This
file does not and cannot see that mobile-side call; it only guarantees the
backend stays out of it.

**This file is why the closure is done rather than merely decided.** The rule
lived in a markdown table, and CR040's house lesson is that a rule which is only
written down is not a control. The check is exact rather than a floor: every
HTTP call the module makes is pinned by (function, verb), so the next one fails
the build until someone has read this docstring and formed a view — including
the honest case where Saiful decides to revisit the locked decision, which
should be a deliberate edit here and not a quiet new function. CR227 is exactly
that deliberate edit: read it, confirm the pin still holds, and move on rather
than loosening it in passing.

**CR202 strengthened what this pins, before CR227 existed.** The read path
(`_paper_get`, and the four public getters over it) is gone, because the
credential it needed is gone: a user's Alpaca key now lives on their device and
never reaches this host. The property is therefore not "the backend only ever
READS a user's brokerage account" but the strictly stronger "the backend makes
**no authenticated call to a user's brokerage account at all**, and holds no
credential with which it could." That property is what makes CR227's mobile-
direct design possible in the first place, and CR227 does not weaken it.

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
        f"new HTTP call(s) in alpaca_service.py: {sorted(new)}. Per D-071/"
        "CR227, the backend still never places an order on a user's brokerage "
        "account — a paper order is placed mobile-side, never from here. If "
        "this call is intentional, it likely belongs on the mobile client "
        "instead; if the backend's role is genuinely changing, that's a new "
        "decision-log entry, not a quiet new function."
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
        "See DEF145, D-071 and CR227 — order placement is mobile-side only."
    )


def test_nothing_in_the_backend_calls_an_alpaca_order_endpoint():
    """Corpus-wide, because the call site need not live in the service module.

    D-071/CR227 permits a **paper** order, but that order is placed from the
    mobile client (`mobile/lib/services/alpaca/alpaca_client.dart`), which this
    test does not and should not scan — CR227's whole point is that the
    backend has no path to `/v2/orders` at all, live or paper. If this test
    ever needs to allow a backend reference to that endpoint, CR227's design
    has changed and that's a decision-log conversation first.
    """
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
