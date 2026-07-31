"""send_notification.py — manual/ops entry point into notification_service.notify().

CR027: the requirement was "a capability for push and in-app
notifications", not an internal helper price alerts happens to call.
This CLI calls `notify()` directly — the same function every automated
consumer (price alerts, and later CR095/CR109/BL11/Room-verdict) calls —
so the capability is usable and testable on its own, independent of any
of those triggers ever firing.

Writes a real `notifications` row and attempts a real OneSignal push
using whatever ONESIGNAL_APP_ID / ONESIGNAL_REST_KEY are configured — so
this needs the real DB and real Settings, i.e. run it INSIDE the
api-alpha container on melehost (same pattern as prune_bug_attachments.py
/ social_cache_warm.py), not on the Mac (pure editor, no DB, no backend):

    docker cp backend/scripts ami_api_alpha:/app/scripts
    docker exec ami_api_alpha python -m scripts.send_notification \\
        --user-id <uuid> --title "Test" --body "hello" --type price_alert

Deep link params: --route sets deep_link["route"]; --ticker is shorthand
for deep_link["ticker"]; repeat --param key=value for anything else.
"""

from __future__ import annotations

import argparse
import sys
from uuid import UUID

from app.services.notification_service import notify


def _parse_param(raw: str) -> tuple[str, str]:
    if "=" not in raw:
        raise argparse.ArgumentTypeError(f"--param must be key=value, got: {raw!r}")
    key, _, value = raw.partition("=")
    return key, value


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--user-id", required=True, type=UUID, help="target user's UUID")
    ap.add_argument("--title", required=True, help="notification title")
    ap.add_argument("--body", required=True, help="notification body (≤280 chars recommended)")
    ap.add_argument(
        "--type", default="price_alert",
        help="notification type (free-form; default: price_alert)",
    )
    ap.add_argument("--route", default=None, help="deep_link route, e.g. open_holding_detail")
    ap.add_argument("--ticker", default=None, help="shorthand for deep_link['ticker']")
    ap.add_argument(
        "--param", action="append", default=[], type=_parse_param, metavar="KEY=VALUE",
        help="extra deep_link field, repeatable",
    )
    ap.add_argument("--source-ref", default=None, help="optional source reference id")
    args = ap.parse_args(argv)

    deep_link: dict[str, str] = {}
    if args.route:
        deep_link["route"] = args.route
    if args.ticker:
        deep_link["ticker"] = args.ticker
    for key, value in args.param:
        deep_link[key] = value

    result = notify(
        args.user_id, args.type, args.title, args.body, deep_link,
        source_ref=args.source_ref,
    )
    print(
        f"notification_id={result.notification_id} "
        f"push_status={result.push_status} push_detail={result.push_detail!r}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
