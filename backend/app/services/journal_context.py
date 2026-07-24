"""Real Decision Journal history for Bull/Bear Researcher — Room + 1-on-1.

DEF054/DEF055 (AT:R58): both researchers' prompts claimed "Historical
context from the Decision Journal" as an input, but `journal_store` was
write-only from the Room's perspective — `build_journal_entry_for_run()`
writes a run's outcome *after* it completes; nothing ever read past
entries back into a *future* run's prompt.

Mirrors Concierge's existing real pattern (`concierge_prompts.py::
load_concierge_context()` → `journal_store.list_for_user()`) rather than
inventing a new one. Genuinely ticker-scoped — `list_for_user()` already
supports a `ticker` filter, no schema change needed, so this is real
per-ticker history, not a general-recent fallback.

Shared between Bull (DEF054) and Bear (DEF055) Researcher rather than
duplicated — both need the same real data, just narrated from opposite
theses.

Never raises. Returns None/[] when the user has no history for this
ticker yet (new account, or a ticker never discussed before) — the
caller must disclose "no history yet," never invent one.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.logging import logger
from app.schemas.journal import JournalEntry
from app.schemas.mandate import Plan
from app.services.journal_store import get_journal_store

_MAX_ENTRIES = 5


def fetch_recent_journal_entries(
    user_id: UUID | None, ticker: str, plan: Any = Plan.FLOOR_PASS,
) -> list[JournalEntry]:
    """Real recent Decision Journal entries for this ticker. Never raises.

    Empty list when `user_id` is None (anonymous/1-on-1-preview caller),
    the user has no entries for this ticker, or the store errors.
    """
    if user_id is None:
        return []
    try:
        entries, _, _ = get_journal_store().list_for_user(
            user_id, plan=plan, ticker=ticker, limit=_MAX_ENTRIES,
        )
        return entries
    except Exception as exc:
        logger.warn(
            "journal_context_fetch_error", user_id=str(user_id),
            ticker=ticker, error=str(exc)[:200],
        )
        return []


def format_journal_entry(entry: JournalEntry) -> str:
    date = entry.created_at.strftime("%Y-%m-%d")
    outcome_val = entry.outcome.value if hasattr(entry.outcome, "value") else entry.outcome
    outcome = f" ({outcome_val})" if outcome_val else ""
    line = f"{date}: {entry.title}{outcome}"
    # DEF098: Bull/Bear read this as a decision-*lookback* (DEF054/DEF055) so they
    # can learn from past reasoning — but that reasoning lives in `summary` (the
    # run's synthesis) and `user_note` (the user's own rationale), which this
    # formatter dropped, leaving only date/title/outcome: what was decided, never
    # why. Render them when present so a past call is actually learnable, not just
    # a bare win/loss tally.
    if entry.summary:
        line += f"\n    summary: {entry.summary}"
    if entry.user_note:
        line += f"\n    user's note: {entry.user_note}"
    return line


def build_journal_context_block(
    user_id: UUID | None, ticker: str, plan: Any = Plan.FLOOR_PASS,
) -> str | None:
    """System-prompt-ready block of real Decision Journal history for this
    ticker — Bull/Bear Researcher only, mirroring News/Social's
    Analyst-only-gating contract from CR023/CR024. None when there's no
    real history for this ticker yet.
    """
    entries = fetch_recent_journal_entries(user_id, ticker, plan)
    if not entries:
        return None
    sym = ticker.upper()
    lines = [f"─── DECISION JOURNAL HISTORY — {sym} ───"]
    lines += [f"- {format_journal_entry(e)}" for e in entries]
    lines.append(
        f"(Real past entries for {sym} from this user's own Decision "
        f"Journal — genuine history, not a training-memory recall. If "
        f"nothing is listed above, you have no history for this ticker — "
        f"say so, don't invent any.)"
    )
    return "\n".join(lines)
