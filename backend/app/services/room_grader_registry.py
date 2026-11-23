"""CR267 WP-23: resolves the configured Room grader by name.

`ROOM_GRADER` names one. Gate S3 (Saiful, 2026-11-23) picked the hosted DeepInfra
grader, registered below as "deepinfra"; other graders register a factory here under
their own name. An empty or unknown name resolves to None and the Room ends "decision
unavailable", loudly logged, never a default verdict. A factory that cannot build its
grader (the DeepInfra key is missing) raises, which the runner turns into the same
visible state.
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


def _build_deepinfra() -> Grader:
    from app.services.room_graders.deepinfra import build_from_settings

    return build_from_settings()


register_grader("deepinfra", _build_deepinfra)
