"""At-rest symmetric encryption for sensitive user secrets (DEF044).

Motivation: Alpaca brokerage credentials (`users.alpaca_access_token` /
`alpaca_refresh_token`) were persisted in cleartext, so a DB dump or backup
leaked every user's key + secret. This module encrypts them with Fernet
(AES-128-CBC + HMAC-SHA256), via the `cryptography` lib already pulled in by
`python-jose[cryptography]` — no new top-level dependency.

Design choices:
  - **Key source.** Derived from the app `SECRET_KEY` (SHA-256 → urlsafe base64
    → 32-byte Fernet key) unless a dedicated `ALPACA_ENCRYPTION_KEY` is set,
    which takes precedence. So encryption activates on deploy with no new env
    var; a rotatable dedicated key can be introduced later without a schema
    change.
  - **Plaintext tolerance.** `decrypt_secret` passes through any value lacking
    the `enc::v1::` marker, so legacy cleartext rows (written before DEF044)
    keep working and get encrypted on their next write. This makes the change
    deploy-safe with zero data migration.
  - **Degraded mode.** If no key material is available at all, values are stored
    as-is (a logged warning) rather than blocking account linking.

The `enc::v1::` prefix both versions the scheme and disambiguates our
ciphertext from legacy plaintext (a bare Fernet token can be valid base64 and
would otherwise be indistinguishable from a real key).
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.core.logging import logger

_ENC_PREFIX = "enc::v1::"


def _fernet() -> Fernet | None:
    """Build the Fernet cipher from the dedicated key or the app SECRET_KEY."""
    raw = settings.alpaca_encryption_key or settings.secret_key
    if not raw:
        return None
    derived = base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest())
    return Fernet(derived)


def encrypt_secret(plaintext: str | None) -> str | None:
    """Encrypt a secret for storage. None → None. No key → passthrough (warned)."""
    if plaintext is None:
        return None
    f = _fernet()
    if f is None:
        logger.warning("secret_crypto_no_key", action="store_plaintext")
        return plaintext
    return _ENC_PREFIX + f.encrypt(plaintext.encode()).decode()


def decrypt_secret(stored: str | None) -> str | None:
    """Decrypt a stored secret. Passes through legacy plaintext unchanged."""
    if stored is None:
        return None
    if not stored.startswith(_ENC_PREFIX):
        return stored  # legacy cleartext (pre-DEF044) — return as-is
    f = _fernet()
    if f is None:
        logger.warning("secret_crypto_no_key", action="decrypt_failed")
        return stored
    try:
        return f.decrypt(stored[len(_ENC_PREFIX):].encode()).decode()
    except InvalidToken:
        # Key rotated or corrupt ciphertext — surface raw rather than crash.
        logger.warning("secret_crypto_invalid_token")
        return stored


def is_encrypted(stored: str | None) -> bool:
    """True if the value is ciphertext this module produced."""
    return stored is not None and stored.startswith(_ENC_PREFIX)
