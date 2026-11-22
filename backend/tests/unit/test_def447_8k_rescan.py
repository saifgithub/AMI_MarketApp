"""DEF447 — the nightly 8-K Item 5.02 re-scan (`scripts/rescan_edgar_8k.py`).

What must hold: a re-run over an unchanged index writes nothing new and
fetches no filing text; a filing that appeared since the last run is
picked up; a fetch failure is loud (non-zero exit, an ERROR naming it),
never a quiet exit 0 with an empty store; the User-Agent names no person.
Fixtures only (CAT's real 8-K from the CR221 corpus) — no network.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from app.db import get_session
from app.db.models import Edgar8kItemRow, Edgar8kScanRow
import rescan_edgar_8k as rescan  # noqa: E402 — the sibling-script import above

_CAT_HTML = (Path(__file__).resolve().parent / "fixtures" / "edgar_8k_cat_0001104659-26-042062.htm").read_text(
    encoding="utf-8"
)
_CAT_CIK = 18230
_CAT_ACC = "0001104659-26-042062"
_NEW_ACC = "0001104659-26-099999"
_TICKER_MAP = {"0": {"cik_str": _CAT_CIK, "ticker": "CAT", "title": "CATERPILLAR INC"}}
_MAP_URL = rescan.ingest.TICKER_MAP_URL
_SUBMISSIONS_URL = rescan.SUBMISSIONS_URL.format(cik=_CAT_CIK)


def _recent_date(days_ago: int) -> str:
    return (datetime.now(timezone.utc).date() - timedelta(days=days_ago)).isoformat()


def _submissions(*, with_new: bool = False) -> dict:
    form = ["10-Q", "8-K"]
    items = ["", "5.02,9.01"]
    acc = ["d", _CAT_ACC]
    doc = ["d.htm", "tm2611571d1_8k.htm"]
    filed = [_recent_date(40), _recent_date(30)]
    if with_new:
        form.insert(0, "8-K")
        items.insert(0, "5.02")
        acc.insert(0, _NEW_ACC)
        doc.insert(0, "new_8k.htm")
        filed.insert(0, _recent_date(1))
    return {"cik": _CAT_CIK, "filings": {"recent": {
        "form": form, "items": items, "accessionNumber": acc, "primaryDocument": doc,
        "filingDate": filed, "reportDate": filed,
    }}}


class _Resp:
    def __init__(self, status_code: int, payload=None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        return self._payload


class _Sec:
    """URL-routed stand-in for httpx.Client; records every URL asked for."""

    def __init__(self, submissions: dict, *, ticker_map_status: int = 200,
                 doc_status: int = 200, user_agent: str | None = None) -> None:
        self.submissions = submissions
        self.ticker_map_status = ticker_map_status
        self.doc_status = doc_status
        self.urls: list[str] = []

    def get(self, url: str):
        self.urls.append(url)
        if url == _MAP_URL:
            return _Resp(self.ticker_map_status, _TICKER_MAP)
        if url == _SUBMISSIONS_URL:
            return _Resp(200, self.submissions)
        if self.doc_status == 200:
            return _Resp(200, text=_CAT_HTML)
        return _Resp(self.doc_status)

    def documents(self) -> list[str]:
        return [u for u in self.urls if "/Archives/" in u]


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(rescan.time, "sleep", lambda s: None)
    monkeypatch.setattr(rescan.ingest.time, "sleep", lambda s: None)


@pytest.fixture
def logged(monkeypatch):
    events: list[tuple[str, str, dict]] = []
    for level in ("error", "warning"):
        monkeypatch.setattr(
            rescan.logger, level, lambda event, _l=level, **kw: events.append((_l, event, kw))
        )
    return events


def _items() -> list[tuple[str, str]]:
    with get_session() as session:
        return [(r.accession_no, r.extract_status) for r in session.execute(select(Edgar8kItemRow)).scalars()]


def _scans() -> int:
    with get_session() as session:
        return len(session.execute(select(Edgar8kScanRow)).scalars().all())


def test_rescan_is_idempotent_and_refetches_nothing(logged) -> None:
    first = _Sec(_submissions())
    assert rescan.run(["--only", "CAT"], client=first) == 0
    assert _items() == [(_CAT_ACC, "extracted")] and len(first.documents()) == 1

    second = _Sec(_submissions())
    assert rescan.run(["--only", "CAT"], client=second) == 0
    assert _items() == [(_CAT_ACC, "extracted")]  # no duplicate row
    assert second.documents() == []  # stored filing text is not re-fetched
    assert _scans() == 2  # but every pass moves the "verified through" date
    assert logged == []


def test_rescan_picks_up_a_filing_that_appeared_since(logged) -> None:
    assert rescan.run(["--only", "CAT"], client=_Sec(_submissions())) == 0
    later = _Sec(_submissions(with_new=True))
    assert rescan.run(["--only", "CAT"], client=later) == 0
    assert sorted(_items()) == sorted([(_CAT_ACC, "extracted"), (_NEW_ACC, "extracted")])
    assert [u.rsplit("/", 1)[-1] for u in later.documents()] == ["new_8k.htm"]


def test_rescan_of_the_stored_universe_needs_no_ticker_list(logged) -> None:
    assert rescan.run(["--only", "CAT"], client=_Sec(_submissions())) == 0
    assert rescan.scanned_tickers() == ["CAT"]
    assert rescan.run([], client=_Sec(_submissions(with_new=True))) == 0
    assert len(_items()) == 2


def test_a_document_fetch_failure_exits_nonzero_and_logs_an_error(logged) -> None:
    code = rescan.run(["--only", "CAT"], client=_Sec(_submissions(), doc_status=404))
    assert code == 1
    assert _items() == [(_CAT_ACC, "fetch_failed")]
    errors = [e for e in logged if e[0] == "error"]
    assert errors and errors[0][1] == "edgar_8k_rescan_failed"
    assert errors[0][2]["failures"]["fetch_failed"] == [f"CAT {_CAT_ACC} (404)"]
    # The next night retries it (status is not `extracted`) and clears the failure.
    assert rescan.run(["--only", "CAT"], client=_Sec(_submissions())) == 0
    assert _items() == [(_CAT_ACC, "extracted")]


def test_a_ticker_map_failure_exits_nonzero_and_writes_nothing(logged) -> None:
    assert rescan.run(["--only", "CAT"], client=_Sec(_submissions(), ticker_map_status=500)) == 1
    assert _items() == [] and _scans() == 0
    assert [e[1] for e in logged if e[0] == "error"] == ["edgar_8k_rescan_failed"]


def test_a_transport_error_is_loud_not_empty(logged, monkeypatch) -> None:
    class Down:
        def get(self, url):
            raise httpx.ConnectError("sec.gov unreachable")

    assert rescan.run(["--only", "CAT"], client=Down()) == 1
    assert _scans() == 0 and any(e[0] == "error" for e in logged)


def test_an_empty_store_is_an_error_not_a_quiet_success(logged) -> None:
    assert rescan.run([], client=_Sec(_submissions())) == 1
    assert logged[0][:2] == ("error", "edgar_8k_rescan_no_universe")


def test_a_window_shorter_than_the_render_window_is_refused(logged) -> None:
    assert rescan.run(["--only", "CAT", "--window-days", "30"], client=_Sec(_submissions())) == 2
    assert _scans() == 0


def test_the_default_window_comes_from_settings(monkeypatch, logged) -> None:
    monkeypatch.setattr(rescan.settings, "edgar_8k_rescan_window_days", 200)
    assert rescan.run(["--only", "CAT"], client=_Sec(_submissions())) == 0
    with get_session() as session:
        assert session.execute(select(Edgar8kScanRow.window_days)).scalars().one() == 200


def test_the_default_user_agent_names_no_person() -> None:
    ua = rescan.DEFAULT_USER_AGENT
    assert "@" in ua  # SEC fair access wants a contact address
    local = ua.split("(")[1].split("@")[0]
    assert local in {"support.ai", "support", "privacy", "noreply"} and "gmail" not in ua


def test_the_cron_line_runs_the_rescan_in_the_container_and_logs_to_the_named_file() -> None:
    cron = (Path(__file__).resolve().parents[3] / "infra/cron/def447_8k_rescan.cron").read_text()
    line = next(row for row in cron.splitlines() if row and not row.startswith("#"))
    assert "cd $HOME/ami_trade" in line
    assert "docker compose exec -T api-alpha python scripts/rescan_edgar_8k.py" in line
    assert "$HOME/ami_trade/logs/def447_8k_rescan.log" in line and "2>&1" in line
