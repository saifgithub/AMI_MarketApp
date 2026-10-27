"""CR265 — frozen V2 profiles are validated, isolated and restored."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_TOOLS_DIR = Path(__file__).resolve().parents[3] / "docs" / "tools" / "room_investigation_V2"
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from library import freeze_lab  # noqa: E402
from app.services.cio_snapshot_codec import encode_profile  # noqa: E402
from app.services import room_runner  # noqa: E402


def _snapshot(ticker: str = "AAPL") -> dict:
    encoded = encode_profile({"ticker": ticker, "nested": {"value": 1}})
    return {
        "schema_version": 1,
        "ticker": ticker,
        "profile": encoded,
        "profile_sha256": freeze_lab._digest(encoded),
    }


def test_round_trip_restores_original_and_isolates_mutations():
    snapshot = _snapshot()
    original = room_runner._profile_for_ticker
    with freeze_lab.apply_frozen_profile(snapshot):
        first = room_runner._profile_for_ticker("AAPL")
        first["nested"]["value"] = 99
        second = room_runner._profile_for_ticker("AAPL")
        assert second["nested"]["value"] == 1
        with pytest.raises(ValueError, match="not MSFT"):
            room_runner._profile_for_ticker("MSFT")
    assert room_runner._profile_for_ticker is original


def test_load_rejects_ticker_mismatch(tmp_path: Path):
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(_snapshot()))
    with pytest.raises(ValueError, match="not MSFT"):
        freeze_lab.load_snapshot(path, expected_ticker="MSFT")


def test_load_rejects_content_change(tmp_path: Path):
    snapshot = _snapshot()
    snapshot["profile"]["ticker"] = "MSFT"
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(snapshot))
    with pytest.raises(ValueError, match="hash mismatch"):
        freeze_lab.load_snapshot(path, expected_ticker="AAPL")


def test_ratio_baseline_round_trip():
    from app.services.cio_snapshot_codec import decode_profile
    from app.services.ratio_baselines import RatioBaseline

    freeze_lab._ensure_profile_codec_types()
    encoded = encode_profile({"baseline": RatioBaseline(median=0.46, n=9, window_days=90)})
    decoded = decode_profile(encoded)
    assert decoded["baseline"] == RatioBaseline(median=0.46, n=9, window_days=90)
