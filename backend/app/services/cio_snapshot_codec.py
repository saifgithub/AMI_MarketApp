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

DEF512 — the registry used to be the only way in, so a typed value added to the
sheet without a registry line (CR253's `RatioBaseline`) made every freeze and
every CIO snapshot fail on live Alpha while unit fixtures, which never carry
real-data types, stayed green. Any dataclass or NamedTuple defined under `app.`,
and any `Enum` defined under `app.`, now encodes under its dotted path
(`app.services.x:Name`) and is rebuilt by importing that path. The decode side
accepts only a class that is a dataclass, NamedTuple or Enum and whose module
starts with `app.`: stored data can never name an arbitrary callable. Types from
anywhere else are still refused. The four short-named records below stay
registered so rows written before DEF512 keep decoding.
"""

from __future__ import annotations

import dataclasses
import importlib
import json
import math
from enum import Enum
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.services.buyback_price import BuybackPrice
from app.services.dividend_growth import DividendGrowth
from app.services.news_context import LiveHeadline
from app.services.put_call import PutCallRatio

TAG = "__cr237__"

_RECORD_TYPES: dict[str, type] = {
    "LiveHeadline": LiveHeadline,
    "DividendGrowth": DividendGrowth,
    "BuybackPrice": BuybackPrice,
    # CR247 Phase 1B — the Room profile carries the aggregated put/call
    # object for the Flow & Positioning lane; without this entry the
    # snapshot write would fail loudly on every convene where it resolved.
    "PutCallRatio": PutCallRatio,
}


_APP_PREFIX = "app."


def _dotted(cls: type) -> str:
    return f"{cls.__module__}:{cls.__qualname__}"


def _is_namedtuple(value: Any) -> bool:
    return isinstance(value, tuple) and hasattr(type(value), "_fields")


def _auto_record_tag(value: Any) -> str | None:
    """The dotted tag for an `app.` dataclass / NamedTuple / Enum instance."""
    cls = type(value)
    if not cls.__module__.startswith(_APP_PREFIX) or "<locals>" in cls.__qualname__:
        return None
    if isinstance(value, Enum) or _is_namedtuple(value):
        return _dotted(cls)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _dotted(cls)
    return None


def _resolve_auto(tag: str) -> type:
    module_name, _, qualname = tag.partition(":")
    if not module_name.startswith(_APP_PREFIX) or not qualname:
        raise ValueError(f"cio snapshot: unknown tag {tag!r}")
    obj: Any = importlib.import_module(module_name)
    for part in qualname.split("."):
        obj = getattr(obj, part)
    ok = isinstance(obj, type) and (
        issubclass(obj, Enum)
        or dataclasses.is_dataclass(obj)
        or (issubclass(obj, tuple) and hasattr(obj, "_fields"))
    )
    if not ok or obj.__module__ != module_name:
        raise ValueError(f"cio snapshot: tag {tag!r} is not a rebuildable record type")
    return obj


def _encode(value: Any, path: str) -> Any:
    if isinstance(value, Enum):
        tag = _auto_record_tag(value)
        if tag is None:
            raise TypeError(
                f"cio snapshot: {type(value).__module__}.{type(value).__name__} at {path} "
                "has no JSON encoding"
            )
        return {TAG: tag, "v": _encode(value.value, f"{path}.value")}
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
    tag = name if _RECORD_TYPES.get(name) is type(value) else _auto_record_tag(value)
    if tag is not None:
        if dataclasses.is_dataclass(value):
            if any(not f.init for f in dataclasses.fields(value)):
                raise TypeError(
                    f"cio snapshot: {type(value).__module__}.{name} at {path} has "
                    "init=False fields and cannot be rebuilt"
                )
            fields = {f.name: getattr(value, f.name) for f in dataclasses.fields(value)}
        else:
            fields = value._asdict()
        return {
            TAG: tag,
            "v": {k: _encode(v, f"{path}.{k}") for k, v in fields.items()},
        }
    if isinstance(value, list):
        return [_encode(v, f"{path}[{i}]") for i, v in enumerate(value)]
    if type(value) is tuple:
        return {TAG: "tuple", "v": [_encode(v, f"{path}[{i}]") for i, v in enumerate(value)]}
    if type(value) in (set, frozenset):
        items = sorted(
            (_encode(v, f"{path}{{}}") for v in value),
            key=lambda e: json.dumps(e, sort_keys=True, separators=(",", ":")),
        )
        return {TAG: type(value).__name__, "v": items}
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
    if tag == "set":
        return {_decode(v) for v in raw}
    if tag == "frozenset":
        return frozenset(_decode(v) for v in raw)
    cls = _RECORD_TYPES.get(tag)
    if cls is None:
        cls = _resolve_auto(tag)
    if issubclass(cls, Enum):
        return cls(_decode(raw))
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
