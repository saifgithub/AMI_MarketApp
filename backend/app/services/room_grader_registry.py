"""CR267 WP-23: resolves the configured Room grader by name.

The grader is not chosen yet (gate S3). `ROOM_GRADER` names one; the WP-22 graders
register a factory here under that name once the bake-off picks a winner. An empty or
unknown name resolves to None and the Room ends "decision unavailable", loudly logged,
never a default verdict.
"""

from __future__ import annotations

from typing import Callable

from app.services.room_grader_contract import Grader

_FACTORIES: dict[str, Callable[[], Grader]] = {}


def register_grader(name: str, factory: Callable[[], Grader]) -> None:
    _FACTORIES[name] = factory


def unregister_grader(name: str) -> None:
    _FACTORIES.pop(name, None)


def registered_graders() -> tuple[str, ...]:
    return tuple(sorted(_FACTORIES))


def resolve_grader(name: str | None) -> Grader | None:
    if not name:
        return None
    factory = _FACTORIES.get(name.strip())
    return factory() if factory is not None else None
