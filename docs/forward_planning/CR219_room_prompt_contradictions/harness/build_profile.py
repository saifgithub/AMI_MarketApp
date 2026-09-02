"""Build (or reuse) the cached profile pickle for one or more tickers.

    backend/.venv/bin/python <harness>/build_profile.py CAT MSFT --force

The cache is the reason a comparison is a comparison. Market data moves between
runs (R46), so if each arm refetched, a verdict difference could not be
attributed to the thing the arm varies — the mandate, or the thinking flag. Every
arm in a comparison must load the SAME pickle.

Pickle, not JSON: the profile carries Pydantic news/social objects and a JSON
round-trip degrades them to dicts, which `format_headline` then crashes on.
That is `evidence/README.md` §Reproducing, and it is imported here rather than
restated: this file calls the same `room_runner._profile_for_ticker`.

Pickles are gitignored (`harness/.gitignore`) — a local fixture, never a commit:
it cannot be reviewed in a diff and loading one executes code.
"""
import argparse
import os
import pickle
import sys

from _paths import PROFILES, bootstrap

bootstrap()

from app.core.config import settings  # noqa: E402

settings.use_real_market_data = True
settings.suppress_analyst_consensus = False

from app.services import room_runner  # noqa: E402


def profile_path(ticker: str, profiles_dir: str = PROFILES) -> str:
    return os.path.join(profiles_dir, f"profile_{ticker.upper()}.pkl")


def load_or_build(ticker: str, *, profiles_dir: str = PROFILES, force: bool = False) -> dict:
    """Return the cached profile, fetching it once if absent."""
    path = profile_path(ticker, profiles_dir)
    if os.path.exists(path) and not force:
        with open(path, "rb") as fh:
            return pickle.load(fh)
    os.makedirs(profiles_dir, exist_ok=True)
    profile = room_runner._profile_for_ticker(ticker.upper())
    with open(path, "wb") as fh:
        pickle.dump(profile, fh)
    return profile


def live_fields(profile: dict) -> list[str]:
    return sorted(k for k, v in (profile.get("field_state") or {}).items() if v == "live")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--profiles-dir", default=PROFILES)
    ap.add_argument("--force", action="store_true", help="refetch even if cached")
    args = ap.parse_args()

    for ticker in args.tickers:
        path = profile_path(ticker, args.profiles_dir)
        cached = os.path.exists(path) and not args.force
        profile = load_or_build(ticker, profiles_dir=args.profiles_dir, force=args.force)
        state = profile.get("field_state") or {}
        live = live_fields(profile)
        print(
            f"{ticker.upper():6s} {'cached' if cached else 'fetched'}  "
            f"{len(live)}/{len(state)} LIVE  price={profile.get('base_price')}  -> {path}"
        )
        print(f"       live: {', '.join(live) or '(none)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
