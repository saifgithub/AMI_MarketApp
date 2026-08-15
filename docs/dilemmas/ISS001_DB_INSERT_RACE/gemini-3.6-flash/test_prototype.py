"""Tests for ISS001 Prototype safe_insert and ORM runtime guard."""

from __future__ import annotations

from uuid import uuid4
import pytest
from sqlalchemy import create_engine, Column, String, Integer, UniqueConstraint, select
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from prototype_safe_insert import (
    install_collidable_insert_guard,
    safe_insert,
    OnConflict,
    UnguardedCollidableInsertError,
    with_conflict_handler,
    is_collidable_model,
)

Base = declarative_base()


class AuditLogTest(Base):
    """Non-collidable model (no unique constraints, auto/uuid primary key)."""
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    message = Column(String(255))


class UserTest(Base):
    """Collidable model (unique email)."""
    __tablename__ = "users"
    id = Column(String(36), primary_key=True)
    email = Column(String(255), unique=True)
    display_name = Column(String(255))


class BadgeTest(Base):
    """Collidable model (composite unique constraint)."""
    __tablename__ = "badges"
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36))
    badge_key = Column(String(64))

    __table_args__ = (
        UniqueConstraint("user_id", "badge_key", name="uq_user_badge"),
    )


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionFactory = sessionmaker(bind=engine)

    install_collidable_insert_guard(Session)

    session = SessionFactory()
    yield session
    session.close()


def test_is_collidable_detection():
    assert is_collidable_model(UserTest) is True
    assert is_collidable_model(BadgeTest) is True
    assert is_collidable_model(AuditLogTest) is False


def test_unguarded_insert_on_collidable_model_raises_error(db_session):
    user = UserTest(id=str(uuid4()), email="test@example.com", display_name="Test")
    db_session.add(user)

    with pytest.raises(UnguardedCollidableInsertError) as exc_info:
        db_session.flush()

    assert "Unguarded INSERT detected on collidable model 'UserTest'" in str(exc_info.value)


def test_non_collidable_model_insert_succeeds(db_session):
    log = AuditLogTest(message="action logged")
    db_session.add(log)
    db_session.flush()
    assert log.id is not None


def test_safe_insert_on_conflict_skip(db_session):
    u_id = str(uuid4())
    b1 = BadgeTest(id=str(uuid4()), user_id=u_id, badge_key="streak_7")
    res1, created1 = safe_insert(db_session, b1, on_conflict=OnConflict.SKIP)
    db_session.commit()
    assert created1 is True

    b2 = BadgeTest(id=str(uuid4()), user_id=u_id, badge_key="streak_7")
    res2, created2 = safe_insert(
        db_session,
        b2,
        on_conflict=OnConflict.SKIP,
        fetch_existing_fn=lambda s, obj: s.execute(
            select(BadgeTest).where(BadgeTest.user_id == u_id, BadgeTest.badge_key == "streak_7")
        ).scalar_one_or_none(),
    )
    db_session.commit()
    assert created2 is False
    assert res2.id == b1.id


def test_safe_insert_on_conflict_update(db_session):
    u1_id = str(uuid4())
    u2_id = str(uuid4())
    email = "shared@example.com"

    u1 = UserTest(id=u1_id, email=email, display_name="User 1")
    safe_insert(db_session, u1, on_conflict=OnConflict.SKIP)
    db_session.commit()

    u2 = UserTest(id=u2_id, email=email, display_name="User 2 (Claimed)")

    def _fetch(s, obj):
        return s.execute(select(UserTest).where(UserTest.email == email)).scalar_one_or_none()

    def _update(existing, incoming):
        existing.display_name = incoming.display_name

    res, created = safe_insert(
        db_session,
        u2,
        on_conflict=OnConflict.UPDATE,
        fetch_existing_fn=_fetch,
        update_fn=_update,
    )
    db_session.commit()

    assert created is False
    assert res.id == u1_id
    assert res.display_name == "User 2 (Claimed)"


def test_with_conflict_handler_escape_hatches(db_session):
    user = UserTest(id=str(uuid4()), email="manual@example.com", display_name="Manual")
    with with_conflict_handler():
        db_session.add(user)
        db_session.flush()
    assert user.id is not None
