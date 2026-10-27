"""Capture one real ticker profile for byte-stable V2 paired experiments."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from library import env_bootstrap, freeze_lab  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    env_bootstrap.ensure_backend_path()
    env_bootstrap.load_repo_env()
    env_bootstrap.require_database_url()
    env_bootstrap.require_real_market_data(allow_mock=False)
    snapshot = freeze_lab.capture_snapshot(args.ticker)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(snapshot, indent=2, allow_nan=False) + "\n")
    print(f"captured {snapshot['ticker']} at {snapshot['captured_at']}")
    print(f"profile_sha256={snapshot['profile_sha256']}")
    print(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
