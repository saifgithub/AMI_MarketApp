"""In-memory onboarding session store.

V0: dict-backed, single-process. Good enough for local dev + small alpha.
V1: Redis-backed when we have multiple backend instances.
V2: Postgres-backed for durability beyond restart (tied to anonymous user_id).

The store is intentionally simple — onboarding sessions are short-lived (≤ 24h).
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from uuid import UUID

from app.core.time import now_utc
from app.schemas.onboarding import OnboardingSession


class InMemorySessionStore:
    def __init__(self) -> None:
        self._sessions: dict[UUID, OnboardingSession] = {}
        self._lock = asyncio.Lock()

    async def create(self, session: OnboardingSession) -> OnboardingSession:
        async with self._lock:
            self._sessions[session.id] = session
        return session

    async def get(self, session_id: UUID) -> OnboardingSession | None:
        async with self._lock:
            return self._sessions.get(session_id)

    async def save(self, session: OnboardingSession) -> OnboardingSession:
        async with self._lock:
            session.updated_at = now_utc()
            self._sessions[session.id] = session
        return session

    async def delete(self, session_id: UUID) -> None:
        async with self._lock:
            self._sessions.pop(session_id, None)

    async def cleanup_expired(self, max_age: timedelta = timedelta(hours=24)) -> int:
        """Remove sessions older than max_age. Returns count removed."""
        cutoff = now_utc() - max_age
        async with self._lock:
            stale = [sid for sid, s in self._sessions.items() if s.updated_at < cutoff]
            for sid in stale:
                del self._sessions[sid]
        return len(stale)


# Singleton — replaced by Redis-backed store in v1
_store = InMemorySessionStore()


def get_session_store() -> InMemorySessionStore:
    return _store
