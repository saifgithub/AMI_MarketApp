"""ISS001 Prototype: Runtime Model-Aware ORM Enforcement & Collision Policy API

This module implements a working prototype for ISS001:
1. Dynamic detection of Collidable Models (models carrying UniqueConstraints, unique Indexes, unique columns, or natural PKs).
2. Runtime Session Listener (`before_flush`) that intercepts `session.new` and raises `UnguardedCollidableInsertError` whenever an unguarded `session.add()` is attempted on a collidable model.
3. The `safe_insert()` unified API and `OnConflict` enum implementing all 4 required collision strategies:
   - OnConflict.SKIP
   - OnConflict.UPDATE
   - OnConflict.RETRY
   - OnConflict.RAISE
"""

from __future__ import annotations

import threading
from enum import Enum, auto
from typing import Any, Callable, TypeVar, Optional, Tuple, Set, Type

from sqlalchemy import event, inspect, UniqueConstraint, Index
from sqlalchemy.orm import Session, Mapper
from sqlalchemy.exc import IntegrityError

T = TypeVar("T")


class OnConflict(Enum):
    """Collision policies for unique constraint violations."""
    SKIP = auto()      # Idempotent writes (badges, sentiment cache) -> skip insert if exists
    UPDATE = auto()    # Re-read existing row & apply state change (devices, edit counter)
    RETRY = auto()     # Recalculate sequence (version numbers) & re-attempt insert
    RAISE = auto()     # Explicitly acknowledged domain error -> raise named exception


class UnguardedCollidableInsertError(RuntimeError):
    """Raised when an unguarded session.add() is executed on a model with unique constraints."""
    pass


# Thread-local context to mark explicit guarded blocks
_guard_state = threading.local()


def _is_in_guarded_context() -> bool:
    return getattr(_guard_state, "active", False)


class with_conflict_handler:
    """Context manager to mark a block as explicitly handling IntegrityError."""
    def __enter__(self):
        self._prev = getattr(_guard_state, "active", False)
        _guard_state.active = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        _guard_state.active = self._prev


_collidable_cache: set[type] = set()
_non_collidable_cache: set[type] = set()


def is_collidable_model(model_cls: type) -> bool:
    """Return True if model_cls carries a UniqueConstraint, unique Index, unique column, or natural PK."""
    if model_cls in _collidable_cache:
        return True
    if model_cls in _non_collidable_cache:
        return False

    mapper = inspect(model_cls, raiseerr=False)
    if not mapper or not hasattr(mapper, "local_table") or mapper.local_table is None:
        _non_collidable_cache.add(model_cls)
        return False

    table = mapper.local_table

    # 1. UniqueConstraint on table
    for const in table.constraints:
        if isinstance(const, UniqueConstraint):
            _collidable_cache.add(model_cls)
            return True

    # 2. Unique Index on table
    for idx in table.indexes:
        if idx.unique:
            _collidable_cache.add(model_cls)
            return True

    # 3. Column unique=True or natural primary key without default
    for col in table.columns:
        if col.unique:
            _collidable_cache.add(model_cls)
            return True
        if col.primary_key and col.default is None and col.server_default is None and not col.autoincrement:
            _collidable_cache.add(model_cls)
            return True

    _non_collidable_cache.add(model_cls)
    return False


def install_collidable_insert_guard(session_class: type = Session) -> None:
    """Register before_flush event listener on SQLAlchemy Session class."""
    @event.listens_for(session_class, "before_flush")
    def _enforce_safe_inserts(session: Session, flush_context: Any, instances: Any) -> None:
        if _is_in_guarded_context():
            return

        for obj in session.new:
            model_cls = type(obj)
            if is_collidable_model(model_cls):
                if not getattr(obj, "_ami_insert_guarded", False):
                    raise UnguardedCollidableInsertError(
                        f"Unguarded INSERT detected on collidable model '{model_cls.__name__}'. "
                        f"Model carries unique constraints. You must use safe_insert(session, obj, on_conflict=...) "
                        f"or wrap in `with with_conflict_handler():`."
                    )


def safe_insert(
    session: Session,
    instance: T,
    *,
    on_conflict: OnConflict,
    fetch_existing_fn: Optional[Callable[[Session, T], Optional[T]]] = None,
    update_fn: Optional[Callable[[T, T], None]] = None,
    retry_fn: Optional[Callable[[int], T]] = None,
    max_retries: int = 3,
    conflict_exception: Optional[Type[Exception]] = None,
) -> Tuple[T, bool]:
    """Execute safe insert of instance into session according to on_conflict policy.

    Returns:
        (result_instance, created_bool)
    """
    setattr(instance, "_ami_insert_guarded", True)

    if on_conflict == OnConflict.RAISE:
        session.add(instance)
        return instance, True

    if on_conflict == OnConflict.SKIP:
        try:
            with session.begin_nested():
                session.add(instance)
                session.flush()
            return instance, True
        except IntegrityError:
            if instance in session:
                session.expunge(instance)
            if fetch_existing_fn:
                existing = fetch_existing_fn(session, instance)
                if existing is not None:
                    return existing, False
            return instance, False

    if on_conflict == OnConflict.UPDATE:
        try:
            with session.begin_nested():
                session.add(instance)
                session.flush()
            return instance, True
        except IntegrityError:
            if instance in session:
                session.expunge(instance)
            if fetch_existing_fn is None:
                raise ValueError("OnConflict.UPDATE requires fetch_existing_fn callback")
            existing = fetch_existing_fn(session, instance)
            if existing is not None and update_fn is not None:
                update_fn(existing, instance)
                return existing, False
            elif existing is not None:
                return existing, False
            raise

    if on_conflict == OnConflict.RETRY:
        if retry_fn is None:
            # First attempt with provided instance
            try:
                with session.begin_nested():
                    session.add(instance)
                    session.flush()
                return instance, True
            except IntegrityError:
                session.expunge(instance)
                if conflict_exception:
                    raise conflict_exception("Constraint conflict on initial insert")
                raise
        else:
            for attempt in range(1, max_retries + 1):
                candidate = retry_fn(attempt)
                setattr(candidate, "_ami_insert_guarded", True)
                try:
                    with session.begin_nested():
                        session.add(candidate)
                        session.flush()
                    return candidate, True
                except IntegrityError:
                    session.expunge(candidate)
                    continue
            if conflict_exception:
                raise conflict_exception(f"Retries exhausted after {max_retries} attempts")
            raise IntegrityError(f"Retries exhausted after {max_retries} attempts", params=None, orig=None)

    raise ValueError(f"Unknown OnConflict policy: {on_conflict}")
