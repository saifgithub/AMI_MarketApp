"""CR121 audit round-1 pin (AT:U CR121).

`highest_observed_build` (app/services/client_release_floor.py) claims to
scan `users.last_app_version` AND `user_devices.app_version` and take the
max across both — the footgun guard on `POST /v1/admin/release-floor`
depends on that being true, or an operator can raise the floor past a build
that's actually installed on a real device the `users` row never learned
about.

Round-1 mutation probe: deleting the `user_devices` loop from
`highest_observed_build` left ALL 35 existing CR121 tests green. Every
existing fixture (`_seed_observed_build` in
test_cr121_admin_release_floor.py, via `AuthService().ensure_anonymous`)
writes the SAME build number to both columns, so the two loops are always
redundant in every existing test — neither loop is provably load-bearing on
its own. This pin seeds the two columns with DIFFERENT, non-overlapping
values so a single-column scan provably gives the wrong answer; dropping
either loop now fails one of the two cases below.
"""

from __future__ import annotations

from uuid import uuid4

from app.db import get_session
from app.db.models import User, UserDeviceRow
from app.services.client_release_floor import highest_observed_build


def test_user_devices_column_alone_can_be_the_max():
    with get_session() as s:
        s.add(User(id=uuid4(), last_app_version="0.1.0+40"))
        s.add(UserDeviceRow(
            id=uuid4(), user_id=uuid4(), device_install_id=uuid4(),
            app_version="0.1.0+90",
        ))
        s.flush()
    with get_session() as s:
        assert highest_observed_build(s) == 90, (
            "user_devices.app_version=90 must win over users.last_app_version=40 "
            "— a scan of users.last_app_version alone would wrongly return 40"
        )


def test_users_column_alone_can_be_the_max():
    with get_session() as s:
        s.add(User(id=uuid4(), last_app_version="0.1.0+90"))
        s.add(UserDeviceRow(
            id=uuid4(), user_id=uuid4(), device_install_id=uuid4(),
            app_version="0.1.0+40",
        ))
        s.flush()
    with get_session() as s:
        assert highest_observed_build(s) == 90, (
            "users.last_app_version=90 must win over user_devices.app_version=40 "
            "— a scan of user_devices.app_version alone would wrongly return 40"
        )
