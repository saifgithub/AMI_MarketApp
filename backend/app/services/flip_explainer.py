"""CR267 WP-25 — the flip explainer.

When a user's verdict on a ticker differs from their previous completed one, this
module builds the diff: which inputs changed (price, news, filings, mandate, ...)
and which narrow coded-rule answers changed, plus which desk claim cards moved
when both Rooms ran with cards. Everything is computed in code from stored fields;
no agent writes any of it.

Two layers:

- `explain_flip(previous, current)` is pure over two `RoomSide`s.
- `stamp_flip(...)` gathers the previous Room and its stored fact sheet and mandate
  from the database, calls the pure layer, and returns the verdict with
  `previous_action` / `flip_explainer` set. It never raises: a gather failure still
  yields an explainer that says the comparison was incomplete (degrade loudly).

`assert_flip_recorded` is the structural guard the Room write path calls: a verdict
whose action differs from its recorded `previous_action` cannot be stored without
an explainer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping
from uuid import UUID

from sqlalchemy import select

from app.core.logging import logger
from app.db import get_session
from app.db.models import RoomFactSheetRow, RoomRunRow
from app.schemas.room import (
    FlipCardChange,
    FlipChangedAnswer,
    FlipChangedInput,
    FlipExplainer,
    Verdict,
    VerdictAction,
)

NOT_ASKED = "not asked"
_MAX_LISTED = 5
_PRIOR_SCAN_LIMIT = 10

_HANDLED_SHEET_KEYS = frozenset({
    "news_headlines", "catalyst", "catalyst_on_ticker", "recent_filings_items",
    "field_state", "last_close",
})

_COMPARED_PARTS = (
    "mandate", "fact_sheet", "policy", "model_root", "portfolio", "journal",
    "alpaca", "brief", "universe", "roster", "tier",
)

_PART_INPUTS: dict[str, tuple[str, str]] = {
    "mandate": ("mandate", "your mandate changed"),
    "policy": ("policy", "AMI's decision policy changed (prompt, rule or setting version)"),
    "portfolio": ("portfolio", "your sim portfolio changed (cash, holdings, lots or trades)"),
    "alpaca": ("portfolio", "your linked paper account's cash or positions changed"),
    "brief": ("brief", "your Brief Your Agent overlays changed"),
    "journal": ("other", "the Decision Journal entries the Bull and Bear desks read for this ticker changed"),
    "universe": ("other", "compliance reference data for this ticker changed (Sharia, exclusions or liquidity)"),
    "roster": ("other", "the set of desks your plan and tenure withheld changed"),
    "tier": ("model", "the model tier your plan gets for the desks changed"),
}


@dataclass(frozen=True)
class RoomSide:
    """One Room as the diff sees it. `bank_inputs` is the stored key-parts dict (the
    per-part digests); `sheet` the decoded fact sheet; `mandate` the mandate's
    content dump. Any of the three may be None when not stored."""

    run_id: str
    verdict: Verdict
    bank_inputs: Mapping[str, str] | None = None
    sheet: Mapping[str, Any] | None = None
    mandate: Mapping[str, Any] | None = None


class FlipWithoutExplainer(Exception):
    """A verdict that flips its previous action was about to be stored with no
    explainer."""


def _action(value: Any) -> str:
    return str(getattr(value, "value", value))


def is_flip(previous_action: str | None, action: Any) -> bool:
    return previous_action is not None and _action(action) != previous_action


def assert_flip_recorded(verdict: Verdict | None) -> None:
    """Refuse a flip with no explainer. Called by the Room write path."""
    if verdict is None:
        return
    if is_flip(verdict.previous_action, verdict.action) and verdict.flip_explainer is None:
        raise FlipWithoutExplainer(
            f"verdict {verdict.previous_action} -> {_action(verdict.action)} "
            "has no flip_explainer"
        )


def _money(value: float) -> str:
    return f"${value:,.2f}"


def _price_input(prev: Verdict, cur: Verdict) -> FlipChangedInput | None:
    before, after = prev.reference_price, cur.reference_price
    if before is None or after is None or round(before, 2) == round(after, 2):
        return None
    move = (after - before) / before * 100 if before else 0.0
    return FlipChangedInput(
        kind="price",
        summary=f"price moved from {_money(before)} to {_money(after)} ({move:+.1f}%)",
    )


def _titles(sheet: Mapping[str, Any]) -> list[str]:
    out: list[str] = []
    for item in sheet.get("news_headlines") or []:
        title = item.get("title") if isinstance(item, Mapping) else getattr(item, "title", None)
        if title:
            out.append(str(title))
    return out


def _clip(text: str, limit: int = 90) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _filing_key(item: Any) -> tuple[str, str, str] | None:
    if not isinstance(item, Mapping):
        return None
    return (
        str(item.get("form") or ""),
        str(item.get("filed_date") or ""),
        str(item.get("label") or ""),
    )


def _news_input(prev: Mapping[str, Any], cur: Mapping[str, Any]) -> FlipChangedInput | None:
    before, after = _titles(prev), _titles(cur)
    seen = set(before)
    new = [t for t in after if t not in seen]
    if new:
        return FlipChangedInput(
            kind="news",
            summary=(
                f"{len(new)} new news item{'s' if len(new) != 1 else ''} since the "
                f"previous Room, latest: \"{_clip(new[0])}\""
            ),
        )
    now = set(after)
    dropped = [t for t in before if t not in now]
    if dropped:
        return FlipChangedInput(
            kind="news",
            summary=(
                f"{len(dropped)} news item{'s' if len(dropped) != 1 else ''} the "
                "previous Room read dropped out of the feed"
            ),
        )
    return None


def _filings_input(prev: Mapping[str, Any], cur: Mapping[str, Any]) -> FlipChangedInput | None:
    before = {k for k in map(_filing_key, prev.get("recent_filings_items") or []) if k}
    after = [k for k in map(_filing_key, cur.get("recent_filings_items") or []) if k]
    new = [k for k in after if k not in before]
    if not new:
        return None
    listed = ", ".join(f"{form or 'filing'} filed {filed}" for form, filed, _ in new[:_MAX_LISTED])
    return FlipChangedInput(
        kind="filings",
        summary=f"{len(new)} new SEC filing{'s' if len(new) != 1 else ''}: {listed}",
    )


def _humanize(name: str) -> str:
    return name.replace("_", " ")


def _residue_input(prev: Mapping[str, Any], cur: Mapping[str, Any]) -> FlipChangedInput | None:
    keys = sorted(
        k for k in (set(prev) | set(cur))
        if k not in _HANDLED_SHEET_KEYS and prev.get(k) != cur.get(k)
    )
    if not keys:
        return None
    shown = ", ".join(_humanize(k) for k in keys[:_MAX_LISTED])
    more = f" and {len(keys) - _MAX_LISTED} more" if len(keys) > _MAX_LISTED else ""
    return FlipChangedInput(
        kind="other",
        summary=f"{len(keys)} other fact-sheet field{'s' if len(keys) != 1 else ''} changed: {shown}{more}",
    )


def _sheet_inputs(prev: RoomSide, cur: RoomSide) -> list[FlipChangedInput]:
    out: list[FlipChangedInput] = []
    price = _price_input(prev.verdict, cur.verdict)
    if price is not None:
        out.append(price)
    if prev.sheet is None or cur.sheet is None:
        if price is None:
            out.append(FlipChangedInput(
                kind="other",
                summary="the fact sheet changed (the previous sheet was not stored, so no detail)",
            ))
        return out
    for built in (
        _news_input(prev.sheet, cur.sheet),
        _filings_input(prev.sheet, cur.sheet),
        _residue_input(prev.sheet, cur.sheet),
    ):
        if built is not None:
            out.append(built)
    return out


def _pct(value: Any) -> str:
    return f"{value:g}%" if isinstance(value, (int, float)) and not isinstance(value, bool) else str(value)


def _show(name: str, value: Any) -> str:
    if value is None:
        return "unset"
    if name.endswith("_pct"):
        return _pct(value)
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value) or "none"
    return str(getattr(value, "value", value))


_MANDATE_LABELS = {
    "single_name_cap_pct": "single-name cap",
    "sector_cap_pct": "sector cap",
    "max_drawdown_pct": "max drawdown",
    "risk_score": "risk score",
}


def _mandate_label(key: str) -> str:
    return _MANDATE_LABELS.get(key) or _humanize(key.replace(".", " ")).removesuffix(" pct")


def _flatten(data: Mapping[str, Any], prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in data.items():
        if isinstance(v, Mapping):
            out.update(_flatten(v, f"{prefix}{k}."))
        else:
            out[f"{prefix}{k}"] = v
    return out


def _mandate_input(prev: RoomSide, cur: RoomSide) -> FlipChangedInput:
    if prev.mandate is None or cur.mandate is None:
        return FlipChangedInput(kind="mandate", summary="your mandate changed (the previous one was not stored, so no detail)")
    before, after = _flatten(prev.mandate), _flatten(cur.mandate)
    changed = sorted(k for k in (set(before) | set(after)) if before.get(k) != after.get(k))
    if not changed:
        return FlipChangedInput(kind="mandate", summary="your mandate changed")
    parts = [
        f"{_mandate_label(k)} {_show(k, before.get(k))} → {_show(k, after.get(k))}"
        for k in changed[:_MAX_LISTED]
    ]
    more = f", and {len(changed) - _MAX_LISTED} more" if len(changed) > _MAX_LISTED else ""
    return FlipChangedInput(kind="mandate", summary="mandate: " + "; ".join(parts) + more)


def _changed_inputs(prev: RoomSide, cur: RoomSide) -> tuple[list[FlipChangedInput], bool]:
    """(inputs, compared). `compared` is False when either Room's parts were not
    stored or lack a part, in which case the list is what could be established."""
    pa, ca = prev.bank_inputs, cur.bank_inputs
    compared = pa is not None and ca is not None and all(
        p in pa and p in ca for p in _COMPARED_PARTS
    )
    out: list[FlipChangedInput] = []
    mandate_changed = (
        (pa or {}).get("mandate") != (ca or {}).get("mandate")
        if compared
        else prev.mandate is not None and cur.mandate is not None and prev.mandate != cur.mandate
    )
    if mandate_changed:
        out.append(_mandate_input(prev, cur))
    sheet_changed = (
        pa["fact_sheet"] != ca["fact_sheet"] if compared and pa and ca
        else prev.verdict.reference_price != cur.verdict.reference_price
    )
    if sheet_changed:
        out.extend(_sheet_inputs(prev, cur))
    if compared and pa and ca:
        for part, (kind, text) in _PART_INPUTS.items():
            if part != "mandate" and pa[part] != ca[part]:
                out.append(FlipChangedInput(kind=kind, summary=text))  # type: ignore[arg-type]
        if pa["model_root"] != ca["model_root"]:
            out.append(FlipChangedInput(
                kind="model",
                summary=f"the model serving the desks changed from {_clip(str(pa['model_root']), 60)} to {_clip(str(ca['model_root']), 60)}",
            ))
    return out, compared


def _answer_map(verdict: Verdict) -> dict[str, str] | None:
    record = verdict.coded_decision
    if record is None or record.outcome == "UNAVAILABLE" or not record.answers:
        return None
    return {a.question: a.answer for a in record.answers}


def _answers(prev: Verdict, cur: Verdict) -> tuple[list[FlipChangedAnswer], bool, str | None]:
    before, after = _answer_map(prev), _answer_map(cur)
    if before is None or after is None:
        which = "the previous Room" if before is None else "this Room"
        if before is None and after is None:
            which = "neither Room"
        return [], False, f"narrow answers were not recorded for {which} (the coded rule was off or unavailable)"
    changed = [
        FlipChangedAnswer(
            question=q, before=before.get(q, NOT_ASKED), after=after.get(q, NOT_ASKED),
        )
        for q in sorted(set(before) | set(after))
        if before.get(q) != after.get(q)
    ]
    return changed, True, None


def _cards(prev: Verdict, cur: Verdict) -> list[FlipCardChange] | None:
    if prev.claim_summary is None or cur.claim_summary is None:
        return None
    out: list[FlipCardChange] = []
    for desk in sorted(set(prev.claim_summary) | set(cur.claim_summary)):
        b, a = prev.claim_summary.get(desk, {}), cur.claim_summary.get(desk, {})
        for item in sorted(set(b) | set(a)):
            if b.get(item) != a.get(item):
                out.append(FlipCardChange(
                    desk=desk, item=item, before=b.get(item, NOT_ASKED), after=a.get(item, NOT_ASKED),
                ))
    return out


def explain_flip(previous: RoomSide, current: RoomSide) -> FlipExplainer:
    """Pure diff of two Rooms. Call only when the actions differ."""
    inputs, compared = _changed_inputs(previous, current)
    answers, available, why_not = _answers(previous.verdict, current.verdict)
    return FlipExplainer(
        previous_run_id=previous.run_id,
        previous_action=_action(previous.verdict.action),
        new_action=_action(current.verdict.action),
        changed_inputs=inputs,
        inputs_compared=compared,
        same_inputs_flip=compared and not inputs,
        changed_answers=answers,
        answers_available=available,
        answers_unavailable_reason=why_not,
        cards_changes=_cards(previous.verdict, current.verdict),
    )


def claim_summary_from_cards(cards_by_desk: Mapping[Any, Any]) -> dict[str, dict[str, str]] | None:
    """desk -> card item -> "direction/grade" from the parsed claim cards, or None
    when the Room produced none."""
    out: dict[str, dict[str, str]] = {}
    for desk, desk_cards in cards_by_desk.items():
        items = {
            str(c.item): f"{c.direction}/{c.grade}" for c in getattr(desk_cards, "cards", ())
        }
        if items:
            out[str(getattr(desk, "value", desk))] = items
    return out or None


def _mandate_content(user_id: UUID, version: int) -> dict[str, Any] | None:
    from app.services.mandate_store import get_mandate_store
    from app.services.room_bank import MANDATE_KEY_EXCLUDED

    mandate = get_mandate_store().get_version(user_id, version)
    if mandate is None:
        return None
    return mandate.model_dump(mode="json", exclude=set(MANDATE_KEY_EXCLUDED))


def _stored_sheet(ticker: str, sheet_hash: str | None) -> dict[str, Any] | None:
    if not sheet_hash:
        return None
    from app.services.cio_snapshot_codec import decode_profile

    with get_session() as s:
        row = s.execute(
            select(RoomFactSheetRow)
            .where(RoomFactSheetRow.ticker == ticker.upper())
            .where(RoomFactSheetRow.sheet_hash == sheet_hash)
            .limit(1)
        ).scalar_one_or_none()
        encoded = row.sheet if row is not None else None
    return decode_profile(encoded) if encoded is not None else None


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None or dt.tzinfo is not None:
        return dt
    return dt.replace(tzinfo=timezone.utc)


def find_previous_room(
    *,
    run_id: UUID,
    user_id: UUID,
    ticker: str,
    finished_at: datetime | None,
    is_decision: Callable[[dict], bool],
) -> RoomRunRow | None:
    """The user's latest completed Room on `ticker` that reached a real decision
    and finished before this one."""
    with get_session() as s:
        rows = s.execute(
            select(RoomRunRow)
            .where(RoomRunRow.user_id == user_id)
            .where(RoomRunRow.ticker == ticker)
            .where(RoomRunRow.status == "completed")
            .where(RoomRunRow.verdict.isnot(None))
            .where(RoomRunRow.id != run_id)
            .order_by(RoomRunRow.finished_at.desc())
            .limit(_PRIOR_SCAN_LIMIT)
        ).scalars().all()
        cutoff = _aware(finished_at)
        for row in rows:
            done = _aware(row.finished_at)
            if cutoff is not None and (done is None or done >= cutoff):
                continue
            verdict = row.verdict
            if verdict.get("action") == VerdictAction.NO_VERDICT.value or not is_decision(verdict):
                continue
            s.expunge(row)
            return row
    return None


def _side(row: RoomRunRow, ticker: str) -> RoomSide:
    verdict = Verdict.model_validate(row.verdict)
    inputs = row.bank_inputs if isinstance(row.bank_inputs, dict) else None
    return RoomSide(
        run_id=str(row.id),
        verdict=verdict,
        bank_inputs=inputs,
        sheet=_stored_sheet(ticker, (inputs or {}).get("fact_sheet")),
        mandate=_mandate_content(row.user_id, row.mandate_version),
    )


def stamp_flip(
    *,
    verdict: Verdict,
    run_id: UUID,
    user_id: UUID,
    ticker: str,
    finished_at: datetime | None,
    mandate_version: int,
    bank_inputs: Mapping[str, str] | None,
    sheet: Mapping[str, Any] | None,
    is_decision: Callable[[dict], bool],
) -> Verdict:
    """`verdict` with `previous_action` set when a previous real Room exists and
    `flip_explainer` set when the action differs. Never raises."""
    if verdict.action == VerdictAction.NO_VERDICT or not is_decision(verdict.model_dump(mode="json")):
        return verdict
    try:
        row = find_previous_room(
            run_id=run_id, user_id=user_id, ticker=ticker,
            finished_at=finished_at, is_decision=is_decision,
        )
    except Exception as exc:  # noqa: BLE001 — a failed lookup must not fail the Room
        logger.error("flip_prior_lookup_failed", run_id=str(run_id), error=str(exc)[:200])
        return verdict
    if row is None:
        return verdict
    try:
        prior_action = str(row.verdict.get("action"))
    except Exception:  # noqa: BLE001
        return verdict
    if prior_action == _action(verdict.action):
        return verdict.model_copy(update={"previous_action": prior_action})
    try:
        current = RoomSide(
            run_id=str(run_id),
            verdict=verdict,
            bank_inputs=bank_inputs,
            sheet=_stored_sheet(ticker, (bank_inputs or {}).get("fact_sheet")) or sheet,
            mandate=_mandate_content(user_id, mandate_version),
        )
        explainer = explain_flip(_side(row, ticker), current)
    except Exception as exc:  # noqa: BLE001 — the flip is still explained, as incomplete
        logger.error(
            "flip_explainer_build_failed",
            run_id=str(run_id), error=str(exc)[:200],
            detail="the explainer records that the comparison could not be built",
        )
        explainer = FlipExplainer(
            previous_run_id=str(row.id),
            previous_action=prior_action,
            new_action=_action(verdict.action),
            inputs_compared=False,
            answers_unavailable_reason="the comparison could not be built",
            changed_inputs=[FlipChangedInput(
                kind="other", summary="the inputs of the two Rooms could not be compared",
            )],
        )
    return verdict.model_copy(update={
        "previous_action": prior_action, "flip_explainer": explainer,
    })
