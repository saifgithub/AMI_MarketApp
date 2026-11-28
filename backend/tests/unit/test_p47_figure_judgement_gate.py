"""P47 guard — no AMI-voiced sentence judging a desk figure ships by default until a
market's gate is recorded as passed.

House rule (Saiful, 2026-11-27): no AMI-voiced sentence judging a desk figure ships to
users until it has been replayed on >=300 stored Rooms per market and a random sample of
300 of its listings adjudicated with 0-1 false (US and Bursa gated separately).

`docs/initial_specs/08_tech/figure_judgement_gates.json` holds one record per market
(`null` = not passed). This test (a) pins the `log` default in Settings and compose,
(b) rejects any recorded gate that does not meet the rule, (c) refuses `annotate` as a
default while no market has a passing record. The code-path side (no unlisted code can
emit a correction sentence) is `test_cr288_figure_provenance.py`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.core.config import Settings

_REPO = Path(__file__).resolve().parents[3]
_GATES = _REPO / "docs" / "initial_specs" / "08_tech" / "figure_judgement_gates.json"
_COMPOSE = _REPO / "docker-compose.yml"
_MARKETS = {"US", "MY"}


def _gates() -> dict:
    return json.loads(_GATES.read_text(encoding="utf-8"))


def _violations(market: str, rec) -> list[str]:
    if rec is None:
        return []
    if not isinstance(rec, dict):
        return [f"{market}: record must be null or an object"]
    out = []
    if not isinstance(rec.get("rooms"), int) or rec["rooms"] < 300:
        out.append(f"{market}: rooms {rec.get('rooms')!r} < 300")
    if not isinstance(rec.get("sampled"), int) or rec["sampled"] < 300:
        out.append(f"{market}: sampled {rec.get('sampled')!r} < 300")
    if not isinstance(rec.get("false"), int) or rec["false"] > 1:
        out.append(f"{market}: false {rec.get('false')!r} > 1")
    report = rec.get("report")
    if not isinstance(report, str) or not report or not (_REPO / report).is_file():
        out.append(f"{market}: report {report!r} does not exist in the repo")
    if not rec.get("date"):
        out.append(f"{market}: no date")
    return out


def _compose_default() -> str:
    m = re.search(r"ROOM_FACTCHECK_NOTES:\s*\$\{ROOM_FACTCHECK_NOTES:-([^}]*)\}", _COMPOSE.read_text(encoding="utf-8"))
    assert m, "docker-compose.yml no longer forwards ROOM_FACTCHECK_NOTES with a default"
    return m.group(1)


def test_gate_file_names_exactly_the_gated_markets():
    assert set(_gates()) == _MARKETS


def test_every_recorded_gate_meets_the_house_rule():
    problems = [v for market, rec in _gates().items() for v in _violations(market, rec)]
    assert not problems, "a recorded figure-judgement gate does not meet the rule:\n" + "\n".join(problems)


def test_the_checker_rejects_a_weak_record():
    ok = {"rooms": 300, "sampled": 300, "false": 1, "report": "docs/initial_specs/08_tech/figure_judgement_gates.json", "date": "2026-12-01"}
    assert _violations("US", ok) == []
    for patch in ({"rooms": 299}, {"sampled": 299}, {"false": 2}, {"report": "docs/nope.md"}, {"date": ""}):
        assert _violations("US", {**ok, **patch}), patch


def test_settings_default_is_log():
    assert Settings.model_fields["room_factcheck_notes"].default == "log"


def test_compose_default_is_log():
    assert _compose_default() == "log"


def test_annotate_default_requires_a_passing_gate_record():
    gates = _gates()
    passed = any(rec is not None and not _violations(m, rec) for m, rec in gates.items())
    defaults = {Settings.model_fields["room_factcheck_notes"].default, _compose_default()}
    assert "annotate" not in defaults or passed, (
        "`annotate` is a default while no market has a passing gate record in "
        "figure_judgement_gates.json (P47)"
    )
