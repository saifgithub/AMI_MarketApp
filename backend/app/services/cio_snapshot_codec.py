"""CR237 round 3 — a lossless JSON codec for the CIO-retry snapshot's `profile`.

`run()` persists the desk-phase fact sheet (`profile`) into the JSONB column
`room_runs.cio_context_snapshot` so "Ask the CIO again" can replay the CIO's
turn on the same desk arguments. The profile is not JSON-native:
`news_headlines` holds `LiveHeadline` NamedTuples (JSON turns them into lists,
and the CIO prompt then crashes on `.title`); `dividend_growth` and
`buyback_price` are frozen dataclasses with `date`s and nested tuples (JSON
cannot encode them at all, so the snapshot write itself raised). Auditor U66,
round 2, MAJOR-B.

`encode_profile` turns every value into plain JSON (dict/list/str/int/float/
bool/None) and tags the few typed values it knows how to rebuild;
`decode_profile` rebuilds them exactly. An unknown type is refused with
`TypeError` rather than coerced, so a new non-JSON field makes the snapshot
fail loudly (the run is then not offered a retry) instead of coming back as a
different type on the retry path. Only the classes in `_RECORD_TYPES` are
ever instantiated from stored data.
"""

from __future__ import annotations

import dataclasses
import json
import math
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.services.buyback_price import BuybackPrice
from app.services.dividend_growth import DividendGrowth
from app.services.news_context import LiveHeadline

TAG = "__cr237__"

_RECORD_TYPES: dict[str, type] = {
    "LiveHeadline": LiveHeadline,
    "DividendGrowth": DividendGrowth,
    "BuybackPrice": BuybackPrice,
}


def _encode(value: Any, path: str) -> Any:
    if value is None or isinstance(value, (bool, str)):
        return value
    if type(value).__module__ == "numpy" and hasattr(value, "item"):
        return _encode(value.item(), path)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        if math.isfinite(value):
            return float(value)
        return {TAG: "float", "v": repr(float(value))}
    if isinstance(value, Decimal):
        return {TAG: "decimal", "v": str(value)}
    if isinstance(value, datetime):
        return {TAG: "datetime", "v": value.isoformat()}
    if isinstance(value, date):
        return {TAG: "date", "v": value.isoformat()}
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if not isinstance(k, str) or k == TAG:
                raise TypeError(f"cio snapshot: unencodable key {k!r} at {path}")
            out[k] = _encode(v, f"{path}.{k}")
        return out
    name = type(value).__name__
    if _RECORD_TYPES.get(name) is type(value):
        if dataclasses.is_dataclass(value):
            fields = {f.name: getattr(value, f.name) for f in dataclasses.fields(value)}
        else:
            fields = value._asdict()
        return {
            TAG: name,
            "v": {k: _encode(v, f"{path}.{k}") for k, v in fields.items()},
        }
    if isinstance(value, list):
        return [_encode(v, f"{path}[{i}]") for i, v in enumerate(value)]
    if type(value) is tuple:
        return {TAG: "tuple", "v": [_encode(v, f"{path}[{i}]") for i, v in enumerate(value)]}
    raise TypeError(
        f"cio snapshot: {type(value).__module__}.{name} at {path} has no JSON encoding"
    )


def _decode(value: Any) -> Any:
    if isinstance(value, list):
        return [_decode(v) for v in value]
    if not isinstance(value, dict):
        return value
    tag = value.get(TAG)
    if tag is None:
        return {k: _decode(v) for k, v in value.items()}
    raw = value["v"]
    if tag == "float":
        return float(raw)
    if tag == "decimal":
        return Decimal(raw)
    if tag == "datetime":
        return datetime.fromisoformat(raw)
    if tag == "date":
        return date.fromisoformat(raw)
    if tag == "tuple":
        return tuple(_decode(v) for v in raw)
    cls = _RECORD_TYPES.get(tag)
    if cls is None:
        raise ValueError(f"cio snapshot: unknown tag {tag!r}")
    return cls(**{k: _decode(v) for k, v in raw.items()})


def encode_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """JSON-native copy of `profile`. Raises `TypeError` on any value it
    cannot rebuild exactly; the result always passes a strict `json.dumps`."""
    encoded = _encode(profile, "profile")
    json.dumps(encoded, allow_nan=False)
    return encoded


def decode_profile(encoded: dict[str, Any]) -> dict[str, Any]:
    """Inverse of `encode_profile`."""
    return _decode(encoded)
