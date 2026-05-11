"""User-overlay store. In-memory for dev; Postgres at W5+.

Keyed by (user_id, agent_id). Version 0 is the implicit "no overlay" state and
is never written — get_active returns None for an unedited (user, agent).

Tier-based version retention is enforced on save: when over the cap, the
oldest non-active version is dropped (active is whatever the user last
accepted; rollback resets active to an older version).

The store is the source of truth that build_agent_prompt reads to compose the
runtime prompt — see agent_prompts.append_user_overlay.
"""

from __future__ import annotations

from collections import defaultdict
from threading import RLock
from uuid import UUID

from app.schemas import AgentId, Plan
from app.schemas.coach import UserOverlay


# Tier-based per-agent version retention. None = unlimited.
RETENTION_BY_PLAN: dict[Plan, int | None] = {
    Plan.FLOOR_PASS: 5,
    Plan.TRADER: 20,
    Plan.TRIAL_TRADER: 20,
    Plan.FLOOR_MANAGER: None,
}

# Lifetime edit cap per agent (independent of retention). None = unlimited.
LIFETIME_EDIT_CAP_BY_PLAN: dict[Plan, int | None] = {
    Plan.FLOOR_PASS: 3,
    Plan.TRADER: None,
    Plan.TRIAL_TRADER: None,
    Plan.FLOOR_MANAGER: None,
}


class OverlayStore:
    def __init__(self) -> None:
        # (user_id, agent_id) → list of UserOverlay, newest at the end.
        self._versions: dict[tuple[UUID, AgentId], list[UserOverlay]] = defaultdict(list)
        # (user_id, agent_id) → version number marked as active (default: latest).
        self._active: dict[tuple[UUID, AgentId], int] = {}
        # Lifetime edit counter (only increments on accept).
        self._edit_count: dict[tuple[UUID, AgentId], int] = defaultdict(int)
        self._lock = RLock()

    def _key(self, user_id: UUID, agent_id: AgentId) -> tuple[UUID, AgentId]:
        # Normalise — incoming agent_id may be the string variant due to ConfigDict.
        aid = agent_id if isinstance(agent_id, AgentId) else AgentId(agent_id)
        return (user_id, aid)

    def get_active(self, user_id: UUID, agent_id: AgentId) -> UserOverlay | None:
        with self._lock:
            key = self._key(user_id, agent_id)
            versions = self._versions.get(key, [])
            if not versions:
                return None
            active_v = self._active.get(key, versions[-1].version)
            for v in versions:
                if v.version == active_v:
                    return v
            return versions[-1]

    def list_versions(self, user_id: UUID, agent_id: AgentId) -> list[UserOverlay]:
        with self._lock:
            return list(self._versions.get(self._key(user_id, agent_id), []))

    def active_version(self, user_id: UUID, agent_id: AgentId) -> int:
        v = self.get_active(user_id, agent_id)
        return v.version if v is not None else 0

    def edit_count(self, user_id: UUID, agent_id: AgentId) -> int:
        with self._lock:
            return self._edit_count.get(self._key(user_id, agent_id), 0)

    def can_edit(self, user_id: UUID, agent_id: AgentId, plan: Plan) -> bool:
        cap = LIFETIME_EDIT_CAP_BY_PLAN.get(plan)
        if cap is None:
            return True
        return self.edit_count(user_id, agent_id) < cap

    def edits_remaining(self, user_id: UUID, agent_id: AgentId, plan: Plan) -> int | None:
        cap = LIFETIME_EDIT_CAP_BY_PLAN.get(plan)
        if cap is None:
            return None
        return max(0, cap - self.edit_count(user_id, agent_id))

    def save_new_version(
        self,
        user_id: UUID,
        agent_id: AgentId,
        content: str,
        plain_english: str,
        plan: Plan,
        based_on_session: UUID | None = None,
    ) -> UserOverlay:
        with self._lock:
            key = self._key(user_id, agent_id)
            versions = self._versions.setdefault(key, [])
            next_version = (versions[-1].version + 1) if versions else 1
            overlay = UserOverlay(
                user_id=user_id,
                agent_id=key[1],
                version=next_version,
                content=content,
                plain_english=plain_english,
                based_on_session=based_on_session,
            )
            versions.append(overlay)
            self._active[key] = next_version
            self._edit_count[key] += 1
            self._enforce_retention(key, plan)
            return overlay

    def rollback_to(self, user_id: UUID, agent_id: AgentId, version: int) -> UserOverlay:
        with self._lock:
            key = self._key(user_id, agent_id)
            versions = self._versions.get(key, [])
            target = next((v for v in versions if v.version == version), None)
            if target is None:
                raise ValueError(f"version {version} not found for {agent_id}")
            self._active[key] = version
            return target

    def _enforce_retention(self, key: tuple[UUID, AgentId], plan: Plan) -> None:
        cap = RETENTION_BY_PLAN.get(plan)
        if cap is None:
            return
        versions = self._versions[key]
        if len(versions) <= cap:
            return
        active_v = self._active.get(key)
        # Drop oldest, but never drop the active version
        keep = [v for v in versions if v.version != active_v]
        drop_count = len(versions) - cap
        keep.sort(key=lambda v: v.version)
        survivors = keep[drop_count:]
        if active_v is not None:
            active_obj = next((v for v in versions if v.version == active_v), None)
            if active_obj is not None and active_obj not in survivors:
                survivors.append(active_obj)
        survivors.sort(key=lambda v: v.version)
        self._versions[key] = survivors

    def clear(self) -> None:
        """Test helper — wipe the store."""
        with self._lock:
            self._versions.clear()
            self._active.clear()
            self._edit_count.clear()


_store: OverlayStore | None = None


def get_overlay_store() -> OverlayStore:
    global _store
    if _store is None:
        _store = OverlayStore()
    return _store
