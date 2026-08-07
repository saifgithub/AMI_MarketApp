"""CR121 — client version-gate resolution.

Pure query/decision logic shared by three callers:
  - `GET /v1/client/release-floor` (main.py) — the unauthenticated read path
  - `VersionGateMiddleware` (middleware/version_gate.py) — server-side 426
    enforcement, belt-and-braces on top of the client's own check
  - `POST /v1/admin/release-floor` (api/admin.py) — the write side's
    operational footgun guard

No mutable state here: the active floor is always re-derived from
`client_release_floors` (highest `min_build` among `active=true` rows), and
the highest-observed-build footgun check is always re-derived from
`users.last_app_version` / `user_devices.app_version` — both queried fresh,
never cached, because a stale cache would defeat the entire "one API call,
no deploy" point of the append-only table.
"""

from __future__ import annotations

import re
from typing import Literal, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.db.models import ClientReleaseFloorRow, User, UserDeviceRow
from app.schemas.client_release_floor import ReleaseFloorResponse

# Android's applicationId is a compile-time constant
# (mobile/android/app/build.gradle.kts:38), not an operational secret — no
# Settings field needed. iOS has no numeric App Store ID yet (no App Store
# record exists — DEF100/CR084's provisioning gap), so its URL is
# Settings-driven (`ios_testflight_join_url`) and falls back to the generic
# TestFlight marketing page, loudly logged, when unset.
_ANDROID_PLAY_STORE_URL = (
    "https://play.google.com/store/apps/details?id=ai.agenticmarketintel.ami_trade"
)
_TESTFLIGHT_GENERIC_FALLBACK = "https://testflight.apple.com/"

# Matches the trailing "+<build>" of pubspec.yaml's `version: <semver>+<build>`
# convention (e.g. "0.1.0+69" -> 69). Falls back to a bare integer string so a
# hand-typed admin/CLI value ("69") also parses.
_BUILD_SUFFIX_RE = re.compile(r"\+(\d+)\s*$")


def parse_build_number(version: Optional[str]) -> Optional[int]:
    """Extract the integer build number from a version string, or None if it
    can't be parsed. Never raises — a malformed stored value must degrade to
    "unknown", not 500 the request that happens to read it."""
    if not version:
        return None
    m = _BUILD_SUFFIX_RE.search(version)
    if m:
        return int(m.group(1))
    stripped = version.strip()
    if stripped.isdigit():
        return int(stripped)
    return None


def get_active_floor(session: Session) -> Optional[ClientReleaseFloorRow]:
    """The active floor: highest `min_build` among `active=true` rows.
    None when the table is empty or every row has been retracted — both
    resolve to "no floor configured", never an error."""
    return session.execute(
        select(ClientReleaseFloorRow)
        .where(ClientReleaseFloorRow.active.is_(True))
        .order_by(ClientReleaseFloorRow.min_build.desc())
        .limit(1)
    ).scalars().first()


def resolve_action(
    build: Optional[int], floor: Optional[ClientReleaseFloorRow],
) -> Literal["block", "nag", "ok"]:
    """Server decides the action, not the client — so raising or retracting
    the floor changes behaviour with no client release."""
    if floor is None or build is None:
        # No floor configured, or the caller's build is unknown (e.g. an
        # unauthenticated health-style probe with no ?build= at all) — there
        # is nothing to assert against, so nothing is blocked.
        return "ok"
    if build < floor.min_build:
        return "block"
    if floor.recommended_build is not None and build < floor.recommended_build:
        return "nag"
    return "ok"


def resolve_body(floor: ClientReleaseFloorRow, locale: Optional[str]) -> str:
    """Locale-resolved copy for this specific raise. `body_ar`/`body_ms` are
    nullable and fall back to `body_en` — the per-raise message is
    operational copy authored at raise time, not shipped ARB content, so it
    can't wait on a translation cycle. An unrecognised locale falls back the
    same way as a null one."""
    if locale == "ar" and floor.body_ar:
        return floor.body_ar
    if locale == "ms" and floor.body_ms:
        return floor.body_ms
    return floor.body_en


def resolve_store_url(platform: Optional[str]) -> str:
    if platform == "ios":
        url = settings.ios_testflight_join_url
        if not url:
            # CR040 degrade-loudly: an iOS user on the block screen with no
            # working link is a silent brick unless this is at least logged
            # somewhere an operator can find it.
            logger.warning("release_floor_ios_store_url_unconfigured")
            return _TESTFLIGHT_GENERIC_FALLBACK
        return url
    # Android, or platform unspecified. Bundle IDs differ per platform
    # (ai.agenticmarketintel.amiTrade on iOS vs ai.agenticmarketintel.ami_trade
    # on Android) — nothing here derives one from the other; this branch only
    # ever emits the Android constant above.
    return _ANDROID_PLAY_STORE_URL


def highest_observed_build(session: Session) -> int:
    """The highest build number the server has EVER seen, across both
    `users.last_app_version` (bootstrap-time, one row per user) and
    `user_devices.app_version` (one row per install). Backs the admin
    write-path footgun guard: raising `min_build` above this number bricks
    every client on a build the server has never actually seen installed.
    0 when nothing has ever reported a parseable version — the safe floor
    for "we have no evidence any build exists yet"."""
    highest = 0
    for (v,) in session.execute(select(User.last_app_version)).all():
        b = parse_build_number(v)
        if b is not None and b > highest:
            highest = b
    for (v,) in session.execute(select(UserDeviceRow.app_version)).all():
        b = parse_build_number(v)
        if b is not None and b > highest:
            highest = b
    return highest


def build_release_floor_response(
    session: Session,
    *,
    build: Optional[int],
    locale: Optional[str],
    platform: Optional[str],
) -> ReleaseFloorResponse:
    floor = get_active_floor(session)
    action = resolve_action(build, floor)
    if floor is None:
        return ReleaseFloorResponse(action=action)
    return ReleaseFloorResponse(
        min_build=floor.min_build,
        recommended_build=floor.recommended_build,
        action=action,
        headline=floor.headline,
        body=resolve_body(floor, locale),
        store_url=resolve_store_url(platform),
    )


class ReleaseFloorFootgunError(Exception):
    """Raised by `create_floor_raise` when `min_build` exceeds every build
    the server has ever observed and `force` was not passed."""

    def __init__(self, min_build: int, highest_observed: int) -> None:
        self.min_build = min_build
        self.highest_observed = highest_observed
        super().__init__(
            f"min_build {min_build} exceeds the highest observed build "
            f"{highest_observed} — pass force=true to override"
        )


class ReleaseFloorDuplicateError(Exception):
    """Raised when a row for this exact `min_build` already exists (the
    column is unique) — a clearer 409 than letting the DB's IntegrityError
    surface as an unhandled 500."""

    def __init__(self, min_build: int) -> None:
        self.min_build = min_build
        super().__init__(f"a release floor for min_build={min_build} already exists")


def create_floor_raise(
    session: Session,
    *,
    min_build: int,
    recommended_build: Optional[int],
    headline: str,
    body_en: str,
    body_ar: Optional[str],
    body_ms: Optional[str],
    created_by: Optional[str],
    force: bool,
) -> tuple[ClientReleaseFloorRow, int]:
    """Insert a new floor raise. Returns (row, highest_observed_build) so the
    caller can echo the comparison value back to the operator regardless of
    whether `force` was needed.

    Raises `ReleaseFloorFootgunError` when `min_build` exceeds the highest
    build ever observed and `force` is False; `ReleaseFloorDuplicateError`
    when a row for this `min_build` already exists.
    """
    from uuid import uuid4

    highest = highest_observed_build(session)
    if not force and min_build > highest:
        raise ReleaseFloorFootgunError(min_build, highest)

    existing = session.execute(
        select(ClientReleaseFloorRow).where(
            ClientReleaseFloorRow.min_build == min_build
        )
    ).scalars().first()
    if existing is not None:
        raise ReleaseFloorDuplicateError(min_build)

    row = ClientReleaseFloorRow(
        id=uuid4(),
        min_build=min_build,
        recommended_build=recommended_build,
        headline=headline,
        body_en=body_en,
        body_ar=body_ar,
        body_ms=body_ms,
        created_by=created_by,
        active=True,
    )
    session.add(row)
    session.flush()
    return row, highest
