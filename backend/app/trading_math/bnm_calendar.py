"""Bank Negara Malaysia MPC calendar and the Overnight Policy Rate (CR282 lane E).

The Macro & Events desk's forward-dated datum for a Bursa Room, the way the FOMC
countdown is for a US one. A data table, never a formula: BNM publishes the next
year's six meeting dates in the last statement of the year.

Source: BNM Monetary Policy Statement of 5 November 2026
(https://www.bnm.gov.my/-/monetary-policy-statement-05112026), which held the OPR
at 2.75% and set out the 2027 schedule; the 2026 dates are from BNM's MPC meetings
page. Dates are the Thursday decision/announcement day (statement at 15:00 MYT).
Cross-checked 2026-11-24 against two news reports of the 2027 schedule.

Past the table's last date the countdown cannot know the next meeting, so it
raises `MpcTableExhausted` — callers render that as an explicit "refresh the
table" line, never as "no meeting scheduled" (CR040: degrade loudly).

Pure — no DB, no network.
"""

from __future__ import annotations

from datetime import date

#: OPR after the 5 Nov 2026 MPC (held at every 2026 meeting). Update with the table, from the same statement.
OPR_PCT = 2.75
OPR_AS_OF = date(2026, 11, 5)

MPC_DECISION_DATES: tuple[date, ...] = (
    date(2026, 1, 22), date(2026, 3, 5), date(2026, 5, 7),
    date(2026, 7, 9), date(2026, 9, 3), date(2026, 11, 5),
    date(2027, 1, 21), date(2027, 3, 4), date(2027, 5, 6),
    date(2027, 7, 8), date(2027, 9, 9), date(2027, 11, 4),
)

LAST_DATE = MPC_DECISION_DATES[-1]


class MpcTableExhausted(ValueError):
    """`today` is past the last scheduled meeting in the table."""

    def __init__(self, today: date) -> None:
        self.today = today
        super().__init__(
            f"BNM MPC table ends {LAST_DATE.isoformat()}; {today.isoformat()} is past it — "
            "refresh MPC_DECISION_DATES and OPR_PCT from BNM's latest Monetary Policy Statement"
        )


def next_mpc_decision(today: date) -> date:
    """The first decision day on or after `today`. Raises `MpcTableExhausted`."""
    for d in MPC_DECISION_DATES:
        if d >= today:
            return d
    raise MpcTableExhausted(today)


def opr_line(today: date) -> str:
    """The OPR and the countdown to the next MPC decision, for the fact sheet."""
    nxt = next_mpc_decision(today)
    days = (nxt - today).days
    when = "today" if days == 0 else f"in {days} day{'s' if days != 1 else ''}"
    return (
        f"BNM Overnight Policy Rate {OPR_PCT:.2f}% (unchanged at the "
        f"{OPR_AS_OF.day} {OPR_AS_OF.strftime('%b %Y')} MPC); next MPC decision "
        f"{nxt.isoformat()} ({when})"
    )
