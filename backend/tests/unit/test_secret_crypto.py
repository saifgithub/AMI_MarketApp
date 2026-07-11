"""DEF044 — at-rest encryption for Alpaca credentials.

Covers the crypto helper (round-trip, plaintext tolerance, marker) and the
EncryptedString ORM column end-to-end: a value written through the ORM is
ciphertext in the raw row but plaintext when read back.
"""

from __future__ import annotations

from app.core.secret_crypto import (
    _ENC_PREFIX,
    decrypt_secret,
    encrypt_secret,
    is_encrypted,
)


def test_round_trip():
    secret = "E3WtwSGv4db9yrnqseA9pmcZHyrorYDMR3kf7VykgYGw"
    token = encrypt_secret(secret)
    assert token != secret
    assert token.startswith(_ENC_PREFIX)
    assert is_encrypted(token)
    assert decrypt_secret(token) == secret


def test_none_passthrough():
    assert encrypt_secret(None) is None
    assert decrypt_secret(None) is None
    assert not is_encrypted(None)


def test_legacy_plaintext_passthrough():
    # A pre-DEF044 cleartext value has no marker → returned unchanged.
    legacy = "PKVRVPNHHXCIQJGVCRG3ZYHIGM"
    assert not is_encrypted(legacy)
    assert decrypt_secret(legacy) == legacy


def test_ciphertext_is_not_the_plaintext():
    secret = "super-secret-key-id"
    token = encrypt_secret(secret)
    assert secret not in token  # plaintext must not appear in stored form


def test_encrypted_string_column_end_to_end():
    """Through the ORM: stored row is ciphertext, ORM read is plaintext."""
    from sqlalchemy import select

    from app.db import get_session
    from app.db.models import User

    key_id = "PKVRVPNHHXCIQJGVCRG3ZYHIGM"
    secret = "E3WtwSGv4db9yrnqseA9pmcZHyrorYDMR3kf7VykgYGw"

    with get_session() as s:
        u = User(display_name="Crypto Test", is_anonymous=False)
        u.alpaca_access_token = key_id
        u.alpaca_refresh_token = secret
        u.alpaca_auth_mode = "apikey"
        s.add(u)
        s.commit()
        uid = u.id

    # ORM read decrypts transparently.
    with get_session() as s:
        row = s.execute(select(User).where(User.id == uid)).scalar_one()
        assert row.alpaca_access_token == key_id
        assert row.alpaca_refresh_token == secret

    # Raw column value is ciphertext, not the plaintext secret.
    with get_session() as s:
        raw = s.connection().exec_driver_sql(
            "select alpaca_refresh_token from users where display_name = 'Crypto Test'"
        ).scalar_one()
        assert raw != secret
        assert raw.startswith(_ENC_PREFIX)
