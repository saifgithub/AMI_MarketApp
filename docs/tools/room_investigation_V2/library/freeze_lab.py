"""Frozen ticker profiles for paired V2 experiments.

Captures the production profile through the existing lossless CIO codec and
injects an identical deep copy into every Room arm in one benchmark process.
"""

from __future__ import annotations

import copy
import hashlib
import json
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1


def _ensure_profile_codec_types() -> None:
    from app.services import cio_snapshot_codec
    from app.services.ratio_baselines import RatioBaseline

    registered = cio_snapshot_codec._RECORD_TYPES.get("RatioBaseline")
    if registered not in (None, RatioBaseline):
        raise RuntimeError("CIO codec RatioBaseline registration conflicts with the harness")
    cio_snapshot_codec._RECORD_TYPES["RatioBaseline"] = RatioBaseline


def _digest(encoded_profile: dict[str, Any]) -> str:
    payload = json.dumps(encoded_profile, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def capture_snapshot(ticker: str) -> dict[str, Any]:
    from app.services.cio_snapshot_codec import encode_profile
    from app.services.room_runner import _profile_for_ticker

    _ensure_profile_codec_types()
    profile = _profile_for_ticker(ticker.upper())
    encoded = encode_profile(profile)
    return {
        "schema_version": SCHEMA_VERSION,
        "ticker": ticker.upper(),
        "captured_at": datetime.now(UTC).isoformat(),
        "profile_sha256": _digest(encoded),
        "profile": encoded,
    }


def load_snapshot(path: Path, *, expected_ticker: str | None = None) -> dict[str, Any]:
    snapshot = json.loads(path.read_text())
    if snapshot.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported profile snapshot schema in {path}")
    ticker = snapshot.get("ticker")
    if not isinstance(ticker, str) or not ticker:
        raise ValueError(f"profile snapshot has no ticker: {path}")
    if expected_ticker and ticker != expected_ticker.upper():
        raise ValueError(f"profile snapshot is for {ticker}, not {expected_ticker.upper()}")
    encoded = snapshot.get("profile")
    if not isinstance(encoded, dict) or _digest(encoded) != snapshot.get("profile_sha256"):
        raise ValueError(f"profile snapshot hash mismatch: {path}")
    return snapshot


@contextmanager
def apply_frozen_profiles(snapshots: dict[str, dict[str, Any]]):
    from app.services import room_runner

    _ensure_profile_codec_types()
    decoded = {
        ticker.upper(): room_runner.decode_profile(snapshot["profile"])
        for ticker, snapshot in snapshots.items()
    }
    original = room_runner._profile_for_ticker

    def frozen(requested_ticker: str, **kwargs: Any) -> dict[str, Any]:
        ticker = requested_ticker.upper()
        if ticker not in decoded:
            raise ValueError(f"no frozen profile for {ticker}; have {sorted(decoded)}")
        return copy.deepcopy(decoded[ticker])

    room_runner._profile_for_ticker = frozen
    try:
        for ticker, snapshot in snapshots.items():
            probe = frozen(ticker)
            if room_runner.encode_profile(probe) != snapshot["profile"]:
                raise RuntimeError(f"frozen profile failed its codec round-trip probe: {ticker}")
        yield {ticker: snapshot["profile_sha256"] for ticker, snapshot in snapshots.items()}
    finally:
        room_runner._profile_for_ticker = original


@contextmanager
def apply_frozen_profile(snapshot: dict[str, Any]):
    ticker = snapshot["ticker"]
    with apply_frozen_profiles({ticker: snapshot}) as digests:
        yield digests[ticker]
