"""Deprecated alias module — use `app.schemas.brief` instead.

Coach Your Agent was renamed to Brief Your Agent in AT:R27. This module
keeps the old import paths working through the deprecation window so
external test files and any straggling imports don't break in lockstep
with the rename. Remove once the codebase is fully swept.

Importing from here is silent (no warnings emitted) — the goal is a clean
swap, not loud refactoring. New code should import from
`app.schemas.brief` directly.
"""

from app.schemas.brief import (  # noqa: F401  re-export for back-compat
    BriefAcceptRequest as CoachAcceptRequest,
    BriefHistoryResponse as CoachHistoryResponse,
    BriefMessageRequest as CoachMessageRequest,
    BriefMode as CoachMode,
    BriefProposal as CoachProposal,
    BriefProposeRequest as CoachProposeRequest,
    BriefRefusal as CoachRefusal,
    BriefRejectRequest as CoachRejectRequest,
    BriefRollbackRequest as CoachRollbackRequest,
    BriefSession as CoachSession,
    BriefStartRequest as CoachStartRequest,
    BriefStartResponse as CoachStartResponse,
    UserOverlay,
)
