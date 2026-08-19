"""DEF044 + DEF182 — at-rest encryption for Alpaca credentials.

DEF044 built it: round-trip, plaintext tolerance, marker, and the
`EncryptedString` ORM column end-to-end.

DEF182 is what the CR123 security review graded a CR040 violation, and it is
two facts rather than one:

  1. `SECRET_KEY` was doing double duty — signing bearer tokens *and* keying
     this cipher — so rotating it (which three other findings all demand)
     would have silently orphaned every ciphertext row.
  2. The layer failed OPEN: `decrypt_secret` returned the raw ciphertext on a
     bad token or a missing key, so post-rotation the Alpaca client would have
     sent `gAAAAA…` as an API key with nothing saying so.

The tests below are grouped by which of those they defend, because the second
is the one with a counter-intuitive shape: the *primitive* raises, and the ORM
layer converts that to `None`. Both halves are asserted — a raise that nothing
catches would lock users out of the whole app, and a `None` produced without a
raise underneath would be the silent fallback all over again.
"""

from __future__ import annotations

import pytest

from app.core.secret_crypto import (
    _ENC_PREFIX,
    _PREFIX_V1,
    _PREFIX_V2,
    SecretDecryptionError,
    SecretEncryptionUnavailable,
    decrypt_secret,
    encrypt_secret,
    is_encrypted,
)

_KEY_A = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
_KEY_B = "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210"


@pytest.fixture
def dedicated(monkeypatch):
    """The configuration every non-local deployment must have: a dedicated key,
    no rollover in progress."""
    from app.core import config as cfg

    monkeypatch.setattr(cfg.settings, "alpaca_encryption_key", _KEY_A)
    monkeypatch.setattr(cfg.settings, "alpaca_encryption_key_previous", "")
    return cfg.settings


# ── DEF044: it encrypts, and the ORM column is transparent ─────────────────


def test_round_trip(dedicated):
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
    # A pre-DEF044 cleartext value has no marker → returned unchanged. The
    # value IS the secret, so refusing it would break a working link for no
    # gain; DEF182 only stops ciphertext being returned as if it were plaintext.
    legacy = "PKVRVPNHHXCIQJGVCRG3ZYHIGM"
    assert not is_encrypted(legacy)
    assert decrypt_secret(legacy) == legacy


def test_ciphertext_is_not_the_plaintext(dedicated):
    secret = "super-secret-key-id"
    token = encrypt_secret(secret)
    assert secret not in token


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

    with get_session() as s:
        row = s.execute(select(User).where(User.id == uid)).scalar_one()
        assert row.alpaca_access_token == key_id
        assert row.alpaca_refresh_token == secret

    with get_session() as s:
        raw = s.connection().exec_driver_sql(
            "select alpaca_refresh_token from users where display_name = 'Crypto Test'"
        ).scalar_one()
        assert raw != secret
        assert is_encrypted(raw)


# ── DEF182 fact 1: the key is dedicated, and SECRET_KEY no longer keys it ──


def test_a_dedicated_key_writes_v2_not_v1(dedicated):
    assert encrypt_secret("x").startswith(_PREFIX_V2)


def test_rotating_secret_key_does_not_touch_v2_ciphertext(dedicated, monkeypatch):
    """The trap DEF182 exists to disarm. Three other findings (H2/DEF185,
    H7/DEF178, M15) call for rotating SECRET_KEY; before this fix, doing so
    orphaned every Alpaca row and the app then shipped the ciphertext to Alpaca
    as an API key."""
    from app.core import config as cfg

    token = encrypt_secret("alpaca-secret")
    monkeypatch.setattr(cfg.settings, "secret_key", "a-completely-different-secret-key")
    assert decrypt_secret(token) == "alpaca-secret"


def test_encrypt_refuses_rather_than_reuse_secret_key_off_a_dev_box(monkeypatch):
    from app.core import config as cfg

    monkeypatch.setattr(cfg.settings, "alpaca_encryption_key", "")
    monkeypatch.setattr(cfg.settings, "alpaca_encryption_key_previous", "")
    monkeypatch.setattr(cfg.settings, "env", "staging")
    with pytest.raises(SecretEncryptionUnavailable):
        encrypt_secret("would-have-been-keyed-by-SECRET_KEY")


def test_encrypt_never_stores_plaintext_even_with_no_key_at_all(monkeypatch):
    """The original degraded mode logged a warning and stored the secret in the
    clear — the exact leak DEF044 was filed to close, reachable by unsetting an
    env var (P1). It must be an error, not a fallback."""
    from app.core import config as cfg

    monkeypatch.setattr(cfg.settings, "alpaca_encryption_key", "")
    monkeypatch.setattr(cfg.settings, "alpaca_encryption_key_previous", "")
    monkeypatch.setattr(cfg.settings, "secret_key", "")
    monkeypatch.setattr(cfg.settings, "env", "local")
    with pytest.raises(SecretEncryptionUnavailable):
        encrypt_secret("plaintext-must-never-be-stored")


def test_v1_rows_still_read_under_the_secret_key_derived_key(monkeypatch):
    """Read compatibility is the whole reason the marker is versioned rather
    than swapped."""
    from app.core import config as cfg

    monkeypatch.setattr(cfg.settings, "alpaca_encryption_key", "")
    monkeypatch.setattr(cfg.settings, "alpaca_encryption_key_previous", "")
    monkeypatch.setattr(cfg.settings, "secret_key", "the-old-shared-secret")
    monkeypatch.setattr(cfg.settings, "env", "local")
    legacy_token = encrypt_secret("written-before-DEF182")
    assert legacy_token.startswith(_PREFIX_V1)

    monkeypatch.setattr(cfg.settings, "alpaca_encryption_key", _KEY_A)
    assert decrypt_secret(legacy_token) == "written-before-DEF182"


# ── DEF182 fact 2: it fails CLOSED, and the ORM turns that into None ───────


def test_decrypt_raises_instead_of_handing_back_ciphertext(dedicated, monkeypatch):
    """The core of the defect. Returning `stored` here is what put `gAAAAA…`
    into an Alpaca API-key header."""
    from app.core import config as cfg

    token = encrypt_secret("alpaca-secret")
    monkeypatch.setattr(cfg.settings, "alpaca_encryption_key", _KEY_B)
    with pytest.raises(SecretDecryptionError):
        decrypt_secret(token)


def test_the_raise_never_returns_the_ciphertext_by_any_path(dedicated, monkeypatch):
    """Non-vacuity: pins that the failure is an exception and not a value that
    merely differs from the plaintext."""
    from app.core import config as cfg

    token = encrypt_secret("alpaca-secret")
    monkeypatch.setattr(cfg.settings, "alpaca_encryption_key", _KEY_B)
    try:
        result = decrypt_secret(token)
    except SecretDecryptionError:
        result = None
    assert result is None
    assert result != token


def test_dual_key_rollover_keeps_old_rows_readable(dedicated, monkeypatch):
    """Step 1 of the documented rotation: old key moves to _PREVIOUS, new key
    takes its place, and nothing breaks at the instant of the swap."""
    from app.core import config as cfg

    old_row = encrypt_secret("written-under-key-A")
    monkeypatch.setattr(cfg.settings, "alpaca_encryption_key", _KEY_B)
    monkeypatch.setattr(cfg.settings, "alpaca_encryption_key_previous", _KEY_A)

    assert decrypt_secret(old_row) == "written-under-key-A"
    new_row = encrypt_secret("written-under-key-B")
    assert decrypt_secret(new_row) == "written-under-key-B"

    # Step 3: clearing _PREVIOUS is what ends the rollover — and it must
    # genuinely stop opening old rows, or the rollover never actually completed.
    monkeypatch.setattr(cfg.settings, "alpaca_encryption_key_previous", "")
    assert decrypt_secret(new_row) == "written-under-key-B"
    with pytest.raises(SecretDecryptionError):
        decrypt_secret(old_row)


def test_the_orm_column_degrades_to_none_rather_than_locking_the_user_out(monkeypatch):
    """`User` is loaded by `get_current_user` on EVERY authenticated request,
    so a raise reaching the caller would turn one unreadable credential into a
    total account lockout. None means "not linked", which every call site
    already handles."""
    from app.db.models import EncryptedString

    col = EncryptedString()
    from app.core import config as cfg

    monkeypatch.setattr(cfg.settings, "alpaca_encryption_key", _KEY_A)
    monkeypatch.setattr(cfg.settings, "alpaca_encryption_key_previous", "")
    token = encrypt_secret("alpaca-secret")

    monkeypatch.setattr(cfg.settings, "alpaca_encryption_key", _KEY_B)
    assert col.process_result_value(token, None) is None
    # …and specifically NOT the ciphertext, which is the bug being fixed.
    assert col.process_result_value(token, None) != token


def test_the_orm_column_is_not_swallowing_everything(monkeypatch):
    """Non-vacuity for the test above: the catch must be narrow enough that a
    readable value still reads."""
    from app.db.models import EncryptedString
    from app.core import config as cfg

    monkeypatch.setattr(cfg.settings, "alpaca_encryption_key", _KEY_A)
    monkeypatch.setattr(cfg.settings, "alpaca_encryption_key_previous", "")
    token = encrypt_secret("alpaca-secret")
    assert EncryptedString().process_result_value(token, None) == "alpaca-secret"


# ── DEF182 round 2: the marker cannot outlive the property it stands for ───
#
# Round 1 removed the *automatic* way `v2` could become a lie (an empty key
# falling back to SECRET_KEY). An independent audit found the configured one
# still open: set the two env vars to the same value by hand and the row is
# stamped `v2` — "independent of SECRET_KEY" — while the SECRET_KEY-derived key
# opens it. That is strictly worse than the original bug, which at least
# labelled such rows `v1` honestly. These pin both ends of the fix.


def test_a_key_equal_to_secret_key_is_refused_at_the_write_site(monkeypatch):
    """MAJOR-1, write half."""
    from app.core import config as cfg

    shared = "one-secret-doing-two-jobs"
    monkeypatch.setattr(cfg.settings, "secret_key", shared)
    monkeypatch.setattr(cfg.settings, "alpaca_encryption_key", shared)
    monkeypatch.setattr(cfg.settings, "alpaca_encryption_key_previous", "")
    monkeypatch.setattr(cfg.settings, "env", "staging")

    with pytest.raises(SecretEncryptionUnavailable) as exc:
        encrypt_secret("alpaca-secret")

    # The operator has to be told *which* mistake this is. "not set" would send
    # them to set it — plausibly to the same value again.
    assert "same value as SECRET_KEY" in str(exc.value)


def test_a_v2_row_written_under_a_reused_key_reads_as_unavailable(monkeypatch):
    """MAJOR-1, read half. A row from before the check existed must not quietly
    keep working, because "it opens" is exactly the false reassurance."""
    from app.core import config as cfg
    from app.core.secret_crypto import _derive

    shared = "one-secret-doing-two-jobs"
    monkeypatch.setattr(cfg.settings, "secret_key", shared)
    row = _PREFIX_V2 + _derive(shared).encrypt(b"alpaca-secret").decode()

    # Non-vacuity: the row is well-formed — the refusal below is the vetting,
    # not a corrupt token.
    assert _derive(shared).decrypt(row[len(_PREFIX_V2):].encode()) == b"alpaca-secret"

    monkeypatch.setattr(cfg.settings, "alpaca_encryption_key", shared)
    monkeypatch.setattr(cfg.settings, "alpaca_encryption_key_previous", "")
    with pytest.raises(SecretDecryptionError):
        decrypt_secret(row)


def test_writing_under_the_retired_rollover_key_is_refused(monkeypatch):
    """MINOR-1. `env=local` on purpose: the only thing that can raise here is
    the _PREVIOUS branch, so this cannot pass by way of the strict-mode refusal."""
    from app.core import config as cfg

    monkeypatch.setattr(cfg.settings, "alpaca_encryption_key", "")
    monkeypatch.setattr(cfg.settings, "alpaca_encryption_key_previous", _KEY_A)
    monkeypatch.setattr(cfg.settings, "env", "local")

    with pytest.raises(SecretEncryptionUnavailable) as exc:
        encrypt_secret("alpaca-secret")
    assert "ALPACA_ENCRYPTION_KEY_PREVIOUS" in str(exc.value)


def test_a_dedicated_key_that_is_actually_dedicated_still_works(monkeypatch):
    """Non-vacuity for the three above: the check must reject the reuse and
    nothing else. A version that refused whenever SECRET_KEY was merely set
    would pass all of them and break every real deployment."""
    from app.core import config as cfg

    monkeypatch.setattr(cfg.settings, "secret_key", "a-populated-and-different-secret")
    monkeypatch.setattr(cfg.settings, "alpaca_encryption_key", _KEY_A)
    monkeypatch.setattr(cfg.settings, "alpaca_encryption_key_previous", "")
    monkeypatch.setattr(cfg.settings, "env", "staging")

    token = encrypt_secret("alpaca-secret")
    assert token.startswith(_PREFIX_V2)
    assert decrypt_secret(token) == "alpaca-secret"
