"""DEF367 — client-side adapters the wire check cannot infer from `fromJson` alone.

Almost every route in `api_client.dart` hands the response (or one key of it)
straight to `X.fromJson`, so the keys `fromJson` reads ARE the contract. A few
routes do not: the client reshapes the body first, and then `fromJson` reads keys
the SERVER never sends because the client itself synthesised them. Checking
`fromJson`'s keys against that body reports a disagreement that does not exist
(and, because every key is also emitted somewhere else in the server, it lands
on UNVERIFIED forever — a baseline entry no test can ever close).

The honest check for such a route is the keys the ADAPTER reads from the server.
That is declared here, once, by hand and in the open, because it is the one place
the method "the client's own navigation is the contract" cannot be lifted
mechanically. An adapter that drifts from `api_client.dart` shows up as a unit
test failure (`test_def367_extractor_rules.py` re-reads the Dart source and pins
the mapping below to it).

One adapter today: `gamesRecordPrs` (`GET /v1/games/record/prs`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from dart_keys import ClassContract


@dataclass(frozen=True)
class Adapter:
    dart_method: str
    # body -> list of (branch, object handed to `fromJson`). `branch` selects which
    # contract that object is checked against.
    transform: Callable[[object], list[tuple[str, dict]]]
    # Contract for objects the ADAPTER synthesised (branch "adapted").
    adapted_contract: ClassContract
    # Objects the client passes through untouched (branch "passthrough") are checked
    # against the class's own `fromJson` contract, so no override is needed there.


# `GET /v1/games/record/prs` — `ApiClient.gamesRecordPrs`.
#
# The server answers an object keyed by CATEGORY, each value `null` or
# `{entry_id, <value key>, ...}`. The client:
#   1. if `data['prs']` is a list -> `GamePersonalRecord.fromJson(e)` per element
#      (an older/plan-doc shape; the server does not send it, so this branch is
#      never taken against this server and the client falls through to 2);
#   2. otherwise, for each category in `_prCategoryValueKeys` whose value is a Map,
#      builds `{kind: <category, 'longest_hold_days' -> 'longest_hold'>,
#      entry_id: raw['entry_id'], value: raw[<value key>]}` and parses that.
# So the keys the SERVER must send are `entry_id` and the category's value key on
# every non-null category. `kind` is the category name itself (always present);
# `cadence` and `achieved_at` are never put in the synthesised object, so they read
# null for every record on this route — that is the client's choice, recorded here.
PR_CATEGORY_VALUE_KEYS = {
    "best_weekly_twr": "final_twr_pct",
    "best_alpha": "alpha_scored_pct",
    "best_drawdown_control": "max_drawdown_pct",
    "longest_hold_days": "days",
    "longest_finish_streak": "count",
}


def _prs_transform(body: object) -> list[tuple[str, dict]]:
    if not isinstance(body, dict):
        return []
    flat = body.get("prs")
    if isinstance(flat, list):
        return [("passthrough", e) for e in flat if isinstance(e, dict)]
    out: list[tuple[str, dict]] = []
    for category, value_key in PR_CATEGORY_VALUE_KEYS.items():
        raw = body.get(category)
        if not isinstance(raw, dict):
            continue
        obj: dict = {"kind": category}
        if "entry_id" in raw:
            obj["entry_id"] = raw["entry_id"]
        if value_key in raw:
            obj["value"] = raw[value_key]
        out.append(("adapted", obj))
    return out


ADAPTERS: dict[str, Adapter] = {
    "gamesRecordPrs": Adapter(
        dart_method="gamesRecordPrs",
        transform=_prs_transform,
        adapted_contract=ClassContract(
            class_name="GamePersonalRecord(adapted)",
            file="api_client.dart",
            required_keys={"kind", "entry_id", "value"},
        ),
    ),
}
