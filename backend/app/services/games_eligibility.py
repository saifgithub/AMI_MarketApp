"""CR109 slice 8 — §8.5, who can rank but cannot win.

Saiful: *"we can say that employees and the family of AMI Trading cannot win
awards etc."* §8.5 collapses that into ONE principle rather than a list,
because a list has to be reopened for every case nobody thought of yet — a
future contractor, a partner integration, a demo account:

> **Anything operated by, employed by, or affiliated with AMI Trading may
> rank, but may not hold a title, a champion reward, or permanent flair.**

**This is not hypothetical and it is not distant.** Slice 3c's house desks
fill every field to `GAMES_DESK_TARGET_FIELD_SIZE`, and they trade a
published rule through the same path a human does. At alpha field sizes the
desks ARE most of the field, so the most likely winner of the first weekly
field with desks in it is a desk. Without this module the game's first
champion would be the house.

**Ineligible does not mean invisible, and that distinction is the design.**
Ineligible entrants still enter, still trade, still rank, and the board still
shows what actually happened. Only the TITLE passes down, to the highest
eligible entrant — and when it does, the payload says so plainly
(`champion_displaced_by`), because §8.5 is explicit: *"A board that quietly
promotes second place looks like a bug; one that explains itself looks like
a rule."*

**Scope is narrow on purpose.** Ineligibility covers titles, champion rewards
and permanent flair only. Career points still accrue — Saiful dogfoods
progression, and the desks populate a meaningful spread — which is why
nothing here touches `career_ledger`.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from app.db import get_session
from app.db.models import User

# The reasons, as stored/reported values rather than sentences. Copy is the
# client's, so a translator can hold it to §8.5's "published rule, honest
# ranking" framing.
REASON_HOUSE_DESK = "house_desk"
REASON_AFFILIATED = "affiliated"


def ineligibility_reason(*, is_desk: bool, title_ineligible: bool) -> str | None:
    """§8.5's single rule, as a pure predicate over the two flags that
    express it. `None` means eligible.

    A desk is ineligible **derived from `is_desk`**, never from the stored
    flag alone: a desk minted by a future `ensure_desk_users()` that forgot
    to set the column would otherwise be eligible for the title it was built
    to be excluded from, and the failure would be silent — the house simply
    wins, which reads as a strong strategy rather than as a bug.
    """
    if is_desk:
        return REASON_HOUSE_DESK
    if title_ineligible:
        return REASON_AFFILIATED
    return None


def title_eligible(user_id: UUID) -> bool:
    """Whether this user may HOLD a title. A user row that does not exist is
    treated as ineligible: an unknown entrant is not a person we can award
    to, and defaulting the other way would make a missing row an award."""
    with get_session() as s:
        row = s.execute(
            select(User.is_desk, User.title_ineligible).where(User.id == user_id)
        ).first()
    if row is None:
        return False
    return ineligibility_reason(is_desk=row[0], title_ineligible=row[1]) is None


def reason_for(user_id: UUID) -> str | None:
    with get_session() as s:
        row = s.execute(
            select(User.is_desk, User.title_ineligible).where(User.id == user_id)
        ).first()
    if row is None:
        return REASON_AFFILIATED
    return ineligibility_reason(is_desk=row[0], title_ineligible=row[1])
